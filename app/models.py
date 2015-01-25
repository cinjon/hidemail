import app
from app import db
import os
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import desc
import httplib2
from apiclient.discovery import build
from oauth2client.client import Credentials

logger = app.flask_app.logger
time_period_change = 1 # days

#######
# Inactives are people who have signed up but aren't free, aren't trial, and aren't paying.
# Free are people with free accounts... Me.
# Monthly is people with a subscription.
# Trial are people on a trial. They can only do one.
# Break are people who are using it as a sabbatical. They can do as many as they want.
account_types = {'inactive':0, 'free':1, 'monthly':2, 'trial':3, 'break':4}
account_costs = {'inactive':0, 'free':0, 'monthly':5, 'trial':0, 'break':5}
#######

def manage_inbox_queue(obj):
    if isinstance(obj, tuple): # obj: (ty, id, var)
        if obj[0] == 'customer':
            Customer.query.get(obj[1]).runWorker()
        elif obj[0] == 'inbox':
            Inbox.query.get(obj[1]).runWorker(obj[2])
    else: # queue manager
        obj.runWorker()

class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), index=True)
    account_type = db.Column(db.Integer)
    amount = db.Column(db.Integer)
    stripe_token_id = db.Column(db.Text)

    def __init__(self, account_type, amount):
        self.creation_time = app.utility.get_time()
        self.account_type = account_type
        self.amount = amount

def create_purchase(account_type, amount, commit=True):
    purchase = Purchase(account_type, amount)
    db.session.add(purchase)
    if commit:
        db.session.commit()
    return purchase

class Sabbatical(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime) # time of purchase
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), index=True)
    start_time = db.Column(db.DateTime) # time of start
    length = db.Column(db.Integer) # in days, up to 14

    def __init__(self):
        self.creation_time = app.utility.get_time()

    def set_start_time(self, start_time, commit=True):
        self.start_time = start_time
        if commit:
            db.session.commit()

    def set_length(self, length, commit=True):
        self.length = length
        if commit:
            db.session.commit()

def create_sabbatical(commit=True):
    sabbatical = Sabbatical()
    db.session.add(sabbatical)
    if commit:
        db.session.commit()
    return sabbatical

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime)
    name = db.Column(db.Text)
    last_checked_time = db.Column(db.DateTime) # last time a worker checked
    stripe_customer_id = db.Column(db.Text)
    account_type = db.Column(db.Integer) # See Account Types
    last_timezone_adj_time = db.Column(db.DateTime)
    last_timeblock_adj_time = db.Column(db.DateTime)
    trial_start_time = db.Column(db.DateTime)
    is_in_trial = db.Column(db.Boolean)
    is_init_archiving = db.Column(db.Boolean)
    is_init_archiving_complete = db.Column(db.Boolean)
    inboxes = db.relationship('Inbox', backref='customer', lazy='dynamic')
    purchases = db.relationship('Purchase', backref='customer', lazy='dynamic')
    sabbaticals = db.relationship('Sabbatical', backref='customer', lazy='dynamic')
    timeblocks = db.relationship('Timeblock', backref='inbox', lazy='dynamic')
    timezones = db.relationship('Timezone', backref='customer', lazy='dynamic')

    def __init__(self, name=None, account_type=None):
        self.creation_time = app.utility.get_time()
        self.name = name
        self.account_type = account_type or account_types['inactive']
        self.last_timezone_adj_time = None
        self.last_timeblock_adj_time = None
        self.trial_start_time = None
        self.is_in_trial = False
        self.is_init_archiving = False
        self.is_init_archiving_complete = False

    def start_trial(self, commit=True):
        now = app.utility.get_time()
        self.trial_start_time = now
        self.is_in_trial = True
        if commit:
            db.session.commit()

    def is_trial(self):
        return self.is_in_trial

    def is_active(self):
        return self.account_type != account_types['inactive']

    def activate(self, commit=True):
        if not self.is_init_archiving_complete:
            self.is_init_archiving = True
            app.db.session.commit()
        for inbox in self.inboxes:
            inbox.activate(commit=False)
        self.last_checked_time = app.utility.get_time()
        if commit:
            db.session.commit()

    def inactivate(self, commit=True):
        for inbox in self.inboxes:
            inbox.inactivate(commit=False)
        self.account_type = account_types['inactive']
        self.is_init_archived = False
        self.is_init_archived_complete = False
        self.is_in_trial = False
        if commit:
            db.session.commit()

    def runWorker(self):
        var = 'show_mail' if self.is_show_mail() else 'hide_mail'
        for inbox in self.inboxes:
            if inbox.is_active:
                app.queue.queues.IQ.get_queue().enqueue(
                    manage_inbox_queue, ('inbox', inbox.id, var))

    def is_show_mail(self):
        # this is going to fire all the time in the user's block.
        # not ideal. should make it so that we aren't doing that.
        now = app.utility.get_time()
        offset = self.get_timezone().offset
        curr_user_time = now - datetime.timedelta(minutes=offset)
        periods = self.get_timeblock_periods()
        warmingTime = datetime.timedelta(seconds=app.queue.queues.warmingTime)
        return any([mins_to_datetime(period['start'], offset) - warmingTime <= curr_user_time and curr_user_time < mins_to_datetime(period['end'], offset) for period in periods])

    def is_tb_adjust(self):
        if any([i.email == 'cinjon.resnick@gmail.com' for i in self.inboxes]):
            return True
        now = app.utility.get_time()
        time = self.last_timeblock_adj_time
        return not self.is_active() or not time or time < now - datetime.timedelta(time_period_change)

    def set_timezone(self, offset, commit=True):
        timezone = create_timezone(offset, not commit)
        self.last_timezone_adj_time = app.utility.get_time()
        self.timezones.append(timezone)
        if commit:
            db.session.commit()

    def set_timeblock(self, start_time, length, commit=True):
        timeblock = create_timeblock(length, start_time, not commit)
        self.timeblocks.append(timeblock)
        if commit:
            db.session.commit()

    def get_timezone(self):
        return self.timezones.order_by(desc(Timezone.creation_time)).first()

    def get_timeblocks(self):
        return self.timeblocks.filter_by(is_active=True)

    def get_timeblock_periods(self):
        ret = []
        for start, end in sorted([(tb.start_time, tb.start_time + tb.length) for tb in self.get_timeblocks()], key=lambda k:k[0]):
            if not ret or start != ret[-1]['end']:
                ret.append({'start':start, 'end':end})
            elif start == ret[-1]['end']:
                ret[-1]['end'] = end
        return ret

    def setup_tz_on_arrival(self, tz_offset, commit=True):
        self.set_timezone(offset=tz_offset, commit=commit)

    def setup_tb_on_arrival(self, commit=True):
        for block in self.get_timeblocks():
            block.is_active = False
        self.set_timeblock(start_time=8*60, length=60, commit=False)
        self.set_timeblock(start_time=17*60, length=60, commit=False)
        if commit:
            db.session.commit()

    def set_stripe_id(self, stripe_customer_id, commit=True):
        self.stripe_customer_id = stripe_customer_id
        if commit:
            db.session.commit()

    def set_last_checked_time(self, time=None, commit=True):
        self.last_checked_time = time or app.utility.get_time()
        if commit:
            db.session.commit()

    def can_trial(self):
        return self.purchases.count() == 0

    def basic_info(self):
        return {
            'name':self.name, 'customer_id':self.id, 'isArchiving':self.is_init_archiving,
            'isArchived':self.is_init_archiving_complete, 'isActive':self.is_active(),
            'inboxes':[inbox.serialize() for inbox in self.inboxes],
            'accountType':self.account_type, 'canTrial':self.can_trial()
            }

    def serialize(self):
        ret = self.basic_info()
        ret['inboxes'] = [inbox.serialize() for inbox in self.inboxes]
        ret['lastTzAdj'] = self.last_timezone_adj_time
        ret['lastTbAdj'] = self.last_timeblock_adj_time
        ret['currTzOffset'] = self.get_timezone().offset
        ret['timeblocks'] = sorted([tb.serialize() for tb in self.get_timeblocks()],
                                   key=lambda k:k['start'])
        return ret

class Inbox(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), index=True)
    creation_time = db.Column(db.DateTime)
    name = db.Column(db.Text)
    email = db.Column(db.Text, unique=True)
    google_id = db.Column(db.String(120))
    google_access_token = db.Column(db.Text)
    google_access_token_expiration = db.Column(db.DateTime)
    google_refresh_token = db.Column(db.Text)
    google_credentials = db.Column(db.Text) # json blob
    is_active = db.Column(db.Boolean)
    is_archived = db.Column(db.Boolean)
    threads = db.relationship('Thread', backref='inbox', lazy='dynamic')

    def __init__(self, email=None, name=None,
                 google_id=None, google_access_token=None, google_refresh_token=None,
                 google_access_token_expiration=None, google_credentials=None):
        self.email = None
        if email:
            self.email = email.lower()
        self.creation_time = app.utility.get_time()
        self.name = name
        self.google_id = google_id
        self.google_access_token = google_access_token
        self.google_access_token_expiration = google_access_token_expiration
        self.google_refresh_token = google_refresh_token
        self.google_credentials = google_credentials
        self.is_active = False
        self.is_archived = False

    def runWorker(self, var):
        if var == 'archive':
            app.controllers.mailbox.archive(self)
        elif self.is_active and var == 'show_mail':
            app.controllers.mailbox.show_all_mail(self)
            if not self.is_archived:
                app.controllers.mailbox.archive(self)
        elif self.is_active and var == 'hide_mail':
            self.is_archived = False
            app.db.session.commit()
            app.controllers.mailbox.hide_all_mail(self)

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

    def inactivate(self, commit=True):
        app.controllers.mailbox.show_all_mail(self)
        self.is_active = False
        self.is_archived = False
        if commit:
            db.session.commit()

    def activate(self, commit=True):
        app.queue.queues.IQ.get_queue().enqueue(
            manage_inbox_queue, ('inbox', self.id, 'archive'))

    def set_google_access_token(self, access_token, expires_in, refresh_token=None, credentials=None, commit=True):
        self.google_access_token = access_token or self.google_access_token
        self.google_refresh_token = refresh_token or self.google_refresh_token
        self.google_access_token_expiration = app.controllers.application.get_token_expiry(expires_in)
        self.google_credentials = credentials or app.controllers.application.get_google_credentials(self.google_access_token, self.google_refresh_token, expires_in)
        if commit:
            db.session.commit()

    def serialize(self):
        return {'name':self.name, 'email':self.email, 'isActive':self.is_active}

class Thread(db.Model):
    """
    Tracks the set of threads that have been moved.
    inbox_id is the foreign key to the associated inbox, but because there may be multiple inboxes with a particular thread, need to also have a separate field to uniq id
    """
    thread_id = db.Column(db.Text, primary_key=True) # from google, amended with user ID so that shared thread_ids are made unique
    creation_time = db.Column(db.DateTime)
    last_hide_time = db.Column(db.DateTime)
    last_show_time = db.Column(db.DateTime)
    inbox_id = db.Column(db.Integer, db.ForeignKey('inbox.id'), index=True)
    inbox_unique_id = db.Column(db.Integer)
    active = db.Column(db.Boolean, index=True)

    def __init__(self, thread_id, inbox_unique_id):
        self.thread_id = thread_id
        self.inbox_unique_id = inbox_unique_id
        self.active = True
        self.creation_time = app.utility.get_time()
        self.last_hide_time = None
        self.last_show_time = None

    def hide(self, dt, commit=True):
        self.active = True
        self.last_hide_time = dt
        if commit:
            db.session.commit()

    def show(self, dt, commit=True):
        self.active = False
        self.last_show_time = dt
        if commit:
            db.session.commit()

def make_unique_thread_id(thread_id, inbox_unique_id):
    return thread_id + '-' + str(inbox_unique_id)

def get_or_create_thread(thread_id, inbox, commit=True):
    try:
        thread_id = make_unique_thread_id(thread_id, inbox.id)
        thread = Thread.query.filter_by(thread_id=thread_id, inbox_unique_id=inbox.id).all()
        if not thread:
            thread = Thread(thread_id, inbox.id)
            inbox.threads.append(thread)
            db.session.add(thread)
            if commit:
                db.session.commit()
        else:
            thread = thread[0]
        return thread
    except Exception, e:
        logger.error('Error creating thread for id %s and inbox %d' % (thread_id, inbox.id))
        logger.error(e)
        return None

class Timeblock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), index=True)
    length = db.Column(db.Integer) # in minutes
    start_time = db.Column(db.Integer) # minutes since the day started
    creation_time = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean)

    def __init__(self, length, start_time):
        self.length = length
        self.start_time = start_time
        self.creation_time = app.utility.get_time()
        self.is_active = True

    def serialize(self):
        return {'start':self.start_time, 'length':self.length}

def create_timeblock(length, start_time, commit=True):
    timeblock = Timeblock(length, start_time)
    db.session.add(timeblock)
    if commit:
        db.session.commit()
    return timeblock

class Timezone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), index=True)
    offset = db.Column(db.Integer) # in minutes

    def __init__(self, offset):
        self.creation_time = app.utility.get_time()
        self.offset = offset

def create_timezone(offset, commit=True):
    timezone = Timezone(offset)
    db.session.add(timezone)
    if commit:
        db.session.commit()
    return timezone

def mins_to_datetime(minutes, offset=None):
    """ Minutes is the time since midnight. We want to return a datetime of what that is today. For example, 120 -> 2am today."""
    now = app.utility.get_time()
    if offset:
        now -= datetime.timedelta(minutes=offset)
    return datetime.datetime(now.year, now.month, now.day, int(minutes / 60))
