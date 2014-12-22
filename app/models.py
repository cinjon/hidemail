from app import db
from app import utility
from app import config
from app import flask_app as fapp
import random
import os
import datetime
from werkzeug.security import generate_password_hash, check_password_hash

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

    def __init__(self, email=None, password=None, name=None, google_id=None, google_access_token=None, google_refresh_token=None, custom_label_name=None, custom_label_id=None, google_access_token_expiration=None):
        self.email = None
        if email:
            self.email = email.lower()
        self.creation_time = utility.get_time()
        self.password = self.set_password(password)
        self.name = name
        self.google_id = google_id
        self.google_access_token = google_access_token
        self.google_access_token_expiration = google_access_token_expiration
        self.google_refresh_token = google_refresh_token
        self.custom_label_name = custom_label_name
        self.custom_label_id = custom_label_id

    def clear_access_tokens(self):
        self.google_access_token = None
        self.google_refresh_token = None
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
            app.db.session.commit()

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def set_timezone(self, timezone=None, offset=None):
        if not timezone:
            timezone = get_or_create_timezone(offset)
        timezone.add_inbox(self)

    def get_timeblocks(self):
        return self.timeblocks

    def serialize(self):
        return {'name':self.name, 'email':self.email}

class Timeblock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inbox_id = db.Column(db.Integer, db.ForeignKey('inbox.id'), index=True)
    length = db.Column(db.Integer) # in minutes
    start_time = db.Column(db.Integer) # minutes since the day started
    creation_time = db.Column(db.DateTime)

    def __init__(self, length, start_time):
        self.length = length
        self.start_time = start_time
        self.creation_time = utility.get_time()

def create_timeblock(inbox, length, start_time):
    timeblock = Timeblock(length, start_time)
    inbox.timeblocks.append(timeblock)
    db.session.add(timeblock)
    db.session.commit()
    return timeblock

class Timezone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inboxes = db.relationship('Inbox', backref='timezone', lazy='dynamic')
    offset = db.Column(db.Integer)

    def __init__(self, offset):
        self.offset = offset

    def add_inbox(self, inbox):
        self.inboxes.append(inbox)
        db.session.commit()

    def inboxes(self):
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
        return timezone.inboxes()
    return None
