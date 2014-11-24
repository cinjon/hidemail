from app import db
from app import utility
from app import config
from app import flask_app as fapp
import random
import os
import datetime

class Inbox(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timeblocks = db.relationship('Timeblock', backref='inbox', lazy='dynamic')
    timezone_id = db.Column(db.Integer, db.ForeignKey('timezone.id'))
    name = db.Column(db.Text)
    email = db.Column(db.Text)

    def __init__(self):
        pass

    def set_name(self, name):
        self.name = name

    def set_email(self, email):
        self.email = email

    def set_timezone(self, timezone=None, offset=None):
        if not timezone:
            timezone = get_or_create_timezone(offset)
        timezone.add_inbox(self)

    def get_timeblocks(self):
        return self.timeblocks

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
