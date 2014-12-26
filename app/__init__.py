from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.mobility import Mobility
import utility
import config

basedir = config.basedir
baseurl = config.baseurl

flask_app = Flask(__name__, template_folder='public/template')
flask_app.config.from_object('config')
flask_app.debug = True
db = SQLAlchemy(flask_app)
Mobility(flask_app)

import models
import queue
import controllers
