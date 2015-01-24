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
stripe_sk = config.STRIPE_TEST_SK
stripe_pk = config.STRIPE_TEST_PK
if not flask_app.debug:
    sslify = SSLify(flask_app)
    stripe_pk = config.STRIPE_LIVE_PK
    stripe_sk = config.STRIPE_LIVE_SK
flask_app.logger.debug('using live_pk: %s, using live_sk: %s' % (stripe_sk == config.STRIPE_LIVE_SK, stripe_pk == config.STRIPE_LIVE_PK))
flask_app.logger.debug('using test_pk: %s, using test_sk: %s' % (stripe_pk == config.STRIPE_TEST_PK, stripe_sk == config.STRIPE_TEST_SK))

import models
import queue
import controllers
