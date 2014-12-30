import app
from app import db
import random
import os
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import desc

import httplib2
from apiclient.discovery import build
from oauth2client.client import Credentials

time_period_change = 3 # days
account_types = {'inactive':0, 'free':1, 'month':2, 'week':3}
account_costs = {'inactive':0, 'free':0, 'month':20, 'week':10} # at some pt switch to subscription billing

def manage_inbox_queue(obj):
    if isinstance(obj, tuple):
        if obj[0] == 'customer':
            obj = Customer.query.get(obj[1])
        elif obj[0] == 'inbox':
            obj = Inbox.query.get(obj[1])
    obj.runWorker()

class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), index=True)
    account_type = db.Column(db.Integer)
    amount = db.Column(db.Integer)

    def __init__(self, account_type, amount):
        self.creation_time = app.utility.get_time()
        self.account_type = account_type
        self.amount = amount

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime)
    name = db.Column(db.Text)
    last_checked_time = db.Column(db.DateTime) # for the workers to check when they last saw an inbox
    stripe_customer_id = db.Column(db.Integer)
    account_type = db.Column(db.Integer) # See Account Types
    inboxes = db.relationship('Inbox', backref='customer', lazy='dynamic')
    purchases = db.relationship('Purchase', backref='customer', lazy='dynamic')

    def __init__(self, name=None, account_type=None):
        self.creation_time = app.utility.get_time()
        self.name = name
        self.account_type = account_type or account_types['inactive']

    def runWorker(self):
        for inbox in self.inboxes:
            if inbox.is_active:
                app.queue.queues.IQ.get_queue().enqueue(manage_inbox_queue, ('inbox', inbox.id))

    def set_stripe_id(self, stripe_customer_id, commit=True):
        self.stripe_customer_id = stripe_customer_id
        if commit:
            db.session.commit()

    def set_last_checked_time(self, time=None, commit=True):
        self.last_checked_time = time or app.utility.get_time()
        if commit:
            db.session.commit()

class Inbox(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), index=True)
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
    google_credentials = db.Column(db.Text) # json blob
    custom_label_name = db.Column(db.String(25))
    custom_label_id = db.Column(db.String(25))
    last_timezone_adj_time = db.Column(db.DateTime)
    last_timeblock_adj_time = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean)

    def __init__(self, email=None, password=None, name=None,
                 google_id=None, google_access_token=None, google_refresh_token=None,
                 custom_label_name=None, custom_label_id=None,
                 google_access_token_expiration=None, google_credentials=None):
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
        self.google_credentials = google_credentials
        self.custom_label_name = custom_label_name
        self.custom_label_id = custom_label_id
        self.last_timezone_adj_time = None
        self.last_timeblock_adj_time = None
        self.is_active = False

    def runWorker(self):
        if not self.is_active:
            return
        if self.is_show_mail():
            app.controllers.mailbox.show_all_mail(self)
        else:
            app.controllers.mailbox.hide_all_mail(self)

    def is_complete(self):
        return self.timeblocks.count() == 2 and self.timezone

    def is_show_mail(self):
        # this is going to fire all the time in the user's block.
        # not ideal. should make it so that we aren't doing that.
        now = app.utility.get_time()
        offset = self.timezone.offset
        curr_user_time = now - datetime.timedelta(minutes=offset)
        periods = self.get_timeblock_periods()
        warmingTime = datetime.timedelta(seconds=app.queue.queues.warmingTime)
        return any([mins_to_datetime(period['start'], offset) - warmingTime <= curr_user_time and curr_user_time < mins_to_datetime(period['end'], offset) for period in periods])

    def get_gmail_service(self):
        if not self.google_credentials:
            return None

        credentials = Credentials.new_from_json(self.google_credentials)
        http = credentials.authorize(httplib2.Http())
        return build('gmail', 'v1', http=http)

    def clear_access_tokens(self):
        self.google_access_token = None
        self.google_refresh_token = None
        db.session.commit()

    def inactivate(self):
        self.is_active = False
        db.session.commit()

    def activate(self):
        self.is_active = True
        db.session.commit()

    def setup_tz_on_arrival(self, tz_offset, commit=True):
        self.set_timezone(offset=tz_offset, commit=commit)

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

    def set_google_access_token(self, access_token, expires_in, refresh_token=None, credentials=None, commit=True):
        self.google_access_token = access_token or self.google_access_token
        self.google_refresh_token = refresh_token or self.google_refresh_token
        self.google_access_token_expiration = app.controllers.application.get_token_expiry(expires_in)
        self.google_credentials = credentials or app.controllers.application.get_google_credentials(self.google_access_token, self.google_refresh_token, expires_in)
        if commit:
            db.session.commit()

    def check_password(self, password):
        return check_password_hash(self.password, password)

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

    def is_tb_adjust(self):
        if self.email == 'cinjon.resnick@gmail.com':
            return True
        now = app.utility.get_time()
        time = self.last_timeblock_adj_time
        return not time or _is_out_of_range(time, now - datetime.timedelta(time_period_change), now - datetime.timedelta(minutes=15))

    def basic_info(self):
        return {'name':self.name, 'email':self.email, 'isActive':self.is_active}

    def serialize(self):
        tz = self.timezone.offset
        ret = self.basic_info()
        ret['lastTzAdj'] = self.last_timezone_adj_time
        ret['lastTbAdj'] = self.last_timeblock_adj_time
        ret['currTzOffset'] = tz
        ret['timeblocks'] = sorted([tb.serialize() for tb in self.get_timeblocks()], key=lambda k:k['start'])
        return ret

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

def mins_to_datetime(minutes, offset=None):
    """ Minutes is the time since midnight. We want to return a datetime of what that is today. For example, 120 -> 2am today."""
    now = app.utility.get_time()
    if offset:
        now -= datetime.timedelta(minutes=offset)
    return datetime.datetime(now.year, now.month, now.day, int(minutes / 60))



