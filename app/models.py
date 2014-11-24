from app import db
from app import utility
from app import config
from app import flask_app as fapp
import random
import os
import datetime
from flask.ext.script import Command

class Inbox(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    def __init__(self):
        pass
