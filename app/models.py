import app
from app import db
import random
import os
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import desc

logger = app.flask_app.logger

def manage_inbox_queue(obj):
    if isinstance(obj, tuple):
        if obj[0] == 'inbox':
            obj = Inbox.query.filter_by(email=obj[1]).first()
        else:
            return
    obj.runWorker()

class Inbox(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timeblocks = db.relationship('Timeblock', backref='inbox', lazy='dynamic')
    timezone_id = db.Column(db.Integer, db.ForeignKey('timezone.id'))
    creation_time = db.Column(db.DateTime)
    name = db.Column(db.Text)
    email = db.Column(db.Text, unique=True)
    password = db.Column(db.String(120))
    google_id = db.Column(db.String(120))
    google_access_token = db.Column(db.Text)
    google_access_token_expiration = db.Column(db.DateTime)
    google_refresh_token = db.Column(db.Text)
    custom_label_name = db.Column(db.String(25))
    custom_label_id = db.Column(db.String(25))
    last_timezone_adj_time = db.Column(db.DateTime)
    last_timeblock_adj_time = db.Column(db.DateTime)
    last_checked_time = db.Column(db.DateTime)

    def __init__(self, email=None, password=None, name=None, google_id=None, google_access_token=None, google_refresh_token=None, custom_label_name=None, custom_label_id=None, google_access_token_expiration=None):
        self.email = None
        if email:
            self.email = email.lower()
        self.creation_time = app.utility.get_time()
        self.password = self.set_password(password)
        self.name = name
        self.google_id = google_id
        self.google_access_token = google_access_token
        self.google_access_token_expiration = google_access_token_expiration
        self.google_refresh_token = google_refresh_token
        self.custom_label_name = custom_label_name
        self.custom_label_id = custom_label_id
        self.last_timezone_adj_time = None
        self.last_timeblock_adj_time = None
        self.last_checked_time = None

    def runWorker(self):
        logger.debug('running worker in inbox %s' % self.email)
        now = app.utility.get_time()
        timezone = Timezone.query.get(self.timezone_id)
        curr_user_time = now - datetime.timedelta(minutes=timezone.offset)
        periods = self.get_timeblock_periods()
        if self.is_show_mail(curr_user_time, periods):
            logger.debug('is show mail')
            app.controllers.mailbox.show_all_mail(self)
        else:
            logger.debug('is hide mail')
            app.controllers.mailbox.hide_all_mail(self)

    @staticmethod
    def is_complete():
        return inbox.timeblocks.count() == 2 and Timezone.query.get(inbox.timezone_id)

    @staticmethod
    def is_show_mail(curr_user_time, periods):
        # this is going to fire all the time in the user's block.
        # not ideal. should make it so that we aren't doing that.
        return any([mins_to_datetime(period['start']) - datetime.timedelta(minutes=app.queue.queues.warmingTime) <= curr_user_time and curr_user_time < mins_to_datetime(period['end']) for period in periods])

    def clear_access_tokens(self):
        self.google_access_token = None
        self.google_refresh_token = None
        db.session.commit()

    def setup_tz_on_arrival(self, tz_offset, commit=False):
        self.set_timezone(offset=tz_offset, commit=False)
        if commit:
            db.session.commit()

    def setup_tb_on_arrival(self, commit=True):
        self.set_timeblock(start_time=8*60, length=60, commit=False)
        self.set_timeblock(start_time=17*60, length=60, commit=False)
        if commit:
            db.session.commit()

    def set_name(self, name):
        self.name = name

    def set_email(self, email):
        self.email = email

    def set_password(self, password):
        if not password:
            return None
        return generate_password_hash(password)

    def set_google_access_token(self, access_token, expires_in, refresh_token=None, commit=True):
        self.google_access_token = access_token
        self.google_refresh_token = refresh_token or self.google_refresh_token
        self.google_access_token_expiration = datetime.datetime.now() + datetime.timedelta(0, int(expires_in))
        if commit:
            db.session.commit()

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def set_last_checked_time(self, time=None, commit=True):
        self.last_checked_time = time or app.utility.get_time()
        if commit:
            db.session.commit()

    def set_timezone(self, timezone=None, offset=None, commit=True):
        if not timezone:
            timezone = get_or_create_timezone(offset)
        timezone.add_inbox(self)
        if commit:
            db.session.commit()

    def set_timeblock(self, start_time, length, commit=True):
        create_timeblock(self, length, start_time, commit)

    def get_timeblocks(self):
        return self.timeblocks.order_by(desc(Timeblock.creation_time)).limit(2)

    def get_timeblock_periods(self):
        ret = []
        for start, end in sorted([(tb.start_time, tb.start_time + tb.length) for tb in self.get_timeblocks()], key=lambda k:k[0]):
            if not ret or start != ret[-1]['end']:
                ret.append({'start':start, 'end':end})
            elif start == ret[-1]['end']:
                ret[-1]['end'] = end
        return ret

    @staticmethod
    def is_time_adjust_helper(time):
        now = app.utility.get_time()
        return not time or _is_out_of_range(time, now - datetime.timedelta(2), now - datetime.timedelta(0, 600))

    def is_tz_adjust(self):
        return self.is_time_adjust_helper(self.last_timezone_adj_time)

    def is_tb_adjust(self):
        return self.is_time_adjust_helper(self.last_timeblock_adj_time)

    def basic_info(self):
        return {'name':self.name, 'email':self.email}

    def serialize(self):
        tz = Timezone.query.get(self.timezone_id).offset
        return {'name':self.name, 'email':self.email,
                'lastTzAdj':self.last_timezone_adj_time, 'lastTbAdj':self.last_timeblock_adj_time,
                'currTzOffset':tz, 'timeblocks':sorted([tb.serialize() for tb in self.get_timeblocks()], key=lambda k:k['start'])
                }

def _is_out_of_range(time, beg, end):
    return time < beg or time > end

class Timeblock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inbox_id = db.Column(db.Integer, db.ForeignKey('inbox.id'), index=True)
    length = db.Column(db.Integer) # in minutes
    start_time = db.Column(db.Integer) # minutes since the day started
    creation_time = db.Column(db.DateTime)

    def __init__(self, length, start_time):
        self.length = length
        self.start_time = start_time
        self.creation_time = app.utility.get_time()

    def serialize(self):
        return {'start':self.start_time, 'length':self.length}

def create_timeblock(inbox, length, start_time, commit=True):
    timeblock = Timeblock(length, start_time)
    inbox.timeblocks.append(timeblock)
    db.session.add(timeblock)
    if commit:
        db.session.commit()
    return timeblock

class Timezone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inboxes = db.relationship('Inbox', backref='timezone', lazy='dynamic')
    offset = db.Column(db.Integer) # in minutes

    def __init__(self, offset):
        self.offset = offset

    def add_inbox(self, inbox):
        self.inboxes.append(inbox)
        db.session.commit()

    def get_inboxes(self):
        return self.inboxes

def create_timezone(offset):
    timezone = Timezone(offset)
    db.session.add(timezone)
    db.session.commit()
    return timezone

def get_or_create_timezone(offset):
    timezone = Timezone.query.filter_by(offset=offset).first()
    if timezone:
        return timezone
    return create_timezone(offset)

def get_inboxes_from_offset(offset):
    timezone = Timezone.query.filter_by(offset=offset).first()
    if timezone:
        return timezone.get_inboxes()
    return None

def mins_to_datetime(minutes):
    """ Minutes is the time since midnight. We want to return a datetime of what that is today. For example, 120 -> 2am today."""
    now = app.utility.get_time()
    return datetime.datetime(now.year, now.month, now.day, int(minutes / 60))
