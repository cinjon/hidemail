import app
import os
import httplib2
import json
import jwt
import requests
from datetime import datetime, timedelta
from urllib import urlencode
from functools import wraps
from flask import g, send_from_directory, make_response, request, redirect, render_template, jsonify
from sqlalchemy.sql.expression import func, select
from flask.ext.mobility.decorators import mobile_template

config = app.flask_app.config
logger = app.flask_app.logger

# special file handlers and error handlers
@app.flask_app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.flask_app.root_path, 'static'), 'img/favicon.ico')

@app.flask_app.errorhandler(404)
def page_not_found(e):
    return redirect('/')

# routing for basic pages (pass routing onto the Angular app)
@app.flask_app.route('/')
@app.flask_app.route('/about')
@app.flask_app.route('/timeblocks')
def basic_pages():
    return make_response(open('app/public/template/index.html').read())

def create_token(inbox):
    payload = {
        'sub': inbox.google_id,
        'iat': datetime.now(),
        'exp': datetime.now() + timedelta(days=14)
        }
    token = jwt.encode(payload, config['SECRET_KEY'])
    return token.decode('unicode_escape')

def parse_token(req):
    token = req.headers.get('Authorization').split()[1]
    return jwt.decode(token, config['SECRET_KEY'])

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.headers.get('Authorization'):
            response = jsonify(message='Missing authorization header')
            response.status_code = 401
            return response

        payload = parse_token(request)
        if datetime.fromtimestamp(payload['exp']) < datetime.now():
            response = jsonify(message='Token has expired')
            response.status_code = 401
            return response

        g.inbox_id = payload['sub']
        return f(*args, **kwargs)
    return decorated_function

@app.flask_app.route('/me')
def profile():
    return make_response(open('app/public/template/index.html').read())

@app.flask_app.route('/auth/login', methods=['POST'])
def login():
    inbox = app.models.Inbox.query.filter_by(email=request.json['email']).first()
    if not inbox or not inbox.check_password(request.json['password']):
        response = jsonify(message='Wrong Email or Password')
        response.status_code = 401
        return response
    token = create_token(inbox)
    return jsonify(token=token)

@app.flask_app.route('/auth/signup', methods=['POST'])
def signup():
    inbox = app.models.Inbox(email=request.json['email'], password=request.json['password'])
    db.session.add(inbox)
    db.session.commit()
    token = create_token(inbox)
    return jsonify(token=token)

@app.flask_app.route('/auth/google', methods=['POST'])
def google():
    access_token_url = 'https://accounts.google.com/o/oauth2/token'
    api_url = 'https://www.googleapis.com/plus/v1/people/me/openIdConnect'

    tz_offset = int(request.json.get('state', {}).get('tzOffset', -5*60))
    payload = request.json
    payload = dict(client_id=payload['clientId'],
                   redirect_uri=payload['redirectUri'],
                   client_secret=config['GOOGLE_SECRET'],
                   code=payload['code'],
                   grant_type='authorization_code')

    # Step 1. Exchange authorization code for access token.
    r = requests.post(access_token_url, payload)
    token = json.loads(r.text)
    access_token = token['access_token']
    refresh_token = token.get('refresh_token')
    expires_in = token['expires_in']
    headers = {'Authorization': 'Bearer {0}'.format(access_token)}

    # Step 2. Retrieve information about the current inbox.
    r = requests.get(api_url, headers=headers)
    profile = json.loads(r.text)

    sub = profile.get('sub')
    if not sub:
        return jsonify()

    inbox = app.models.Inbox.query.filter_by(google_id=sub).first()
    if inbox:
        token = create_token(inbox)
        if not inbox.last_timezone_adj_time:
            inbox.setup_tz_on_arrival(tz_offset)
        if not inbox.last_timeblock_adj_time:
            inbox.setup_tb_on_arrival()
        return jsonify(token=token, user=inbox.basic_info(), success=True)

    email = profile.get('email')
    name = profile.get('displayName') or profile.get('name')
    inbox = app.models.Inbox(name=name, email=email, google_id=sub)
    inbox.set_google_access_token(access_token, expires_in, refresh_token, commit=False)
    inbox.setup_tz_on_arrival(tz_offset, commit=False)
    inbox.setup_tb_on_arrival(commit=False)
    app.db.session.add(inbox)
    app.db.session.commit()
    token = create_token(inbox)

    app.controllers.mailbox.create_label(inbox) # do this asynchronously
    return jsonify(token=token, user=inbox.basic_info(), success=True)

@app.flask_app.route('/api/get-time-info/<email>', methods=['GET'])
def get_time_info(email):
    inbox = app.models.Inbox.query.filter_by(email=email).first()
    if not inbox:
        return jsonify(success=False)
    return jsonify(success=True, user=inbox.serialize())

@app.flask_app.route('/update-blocks', methods=['POST'])
def update_blocks():
    payload = request.json['data']
    logger.debug(payload)
    inbox = app.models.Inbox.query.filter_by(email=payload['email']).first()
    if not inbox:
        return jsonify(success=False)
    for block in payload['timeblocks']:
        inbox.set_timeblock(int(block['start']), int(block['length']), commit=False)

    now = app.utility.get_time()
    inbox.last_timeblock_adj_time = now
    if not inbox.last_checked_time and inbox.is_complete():
        inbox.last_checked_time = now

    app.db.session.commit()
    return jsonify(success=True, user=inbox.serialize())

@app.flask_app.route('/update-timezone', methods=['POST'])
def update_timezone():
    payload = request.json['data']
    inbox = app.models.Inbox.query.filter_by(email=payload['email']).first()
    if not inbox:
        return jsonify(success=False)
    inbox.set_timezone(offset=int(payload['tz']), commit=False)

    now = app.utility.get_time()
    inbox.last_timezone_adj_time = now
    if not inbox.last_checked_time and inbox.is_complete():
        inbox.last_checked_time = now

    app.db.session.commit()
    return jsonify(success=True, user=inbox.serialize())

@app.flask_app.route('/api/user-from-token/<token>')
def user_from_token(token):
    try:
        decoded = jwt.decode(token, config['SECRET_KEY'])
        sub = decoded.get('sub')
        if not sub:
            return jsonify(success=False)
        inbox = app.models.Inbox.query.filter_by(google_id=str(sub)).first()
        if not inbox:
            return jsonify(success=True, token=False)
        return jsonify(user=inbox.basic_info(), success=True, token=token)
    except Exception, e:
        app.flask_app.logger.debug('exception %s' % e)
        return jsonify(success=False)
