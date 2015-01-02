from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.mobility import Mobility
from flask_sslify import SSLify
import utility
import config

basedir = config.basedir
baseurl = config.baseurl

flask_app = Flask(__name__, template_folder='public/template')
flask_app.config.from_object('config')
flask_app.debug = config.debug
db = SQLAlchemy(flask_app)
Mobility(flask_app)
if not flask_app.debug:
    sslify = SSLify(flask_app)

import models
import queue
import controllers
