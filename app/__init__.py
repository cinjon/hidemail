from flask import Flask, request, Response
from flask import render_template, send_from_directory, url_for
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.mobility import Mobility
from logging import StreamHandler, DEBUG
import utility
import config

basedir = config.basedir
baseurl = config.baseurl

flask_app = Flask(__name__, template_folder='public/template')
flask_app.config.from_object('config')
db = SQLAlchemy(flask_app)
Mobility(flask_app)

file_handler = StreamHandler()
flask_app.logger.setLevel(DEBUG)  # set the desired logging level here
flask_app.logger.addHandler(file_handler)

import models
import controllers
import scripts
