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
        'sub': inbox.google,
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

@app.flask_app.route('/api/me')
@login_required
def me():
    inbox = Inbox.query.filter_by(id=g.inbox_id).first()
    return jsonify(inbox.serialize())

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

    payload = request.json
    payload = dict(client_id=payload['clientId'],
                   redirect_uri=payload['redirectUri'],
                   client_secret=config['GOOGLE_SECRET'],
                   code=payload['code'],
                   grant_type='authorization_code')

    #Ok, now how the fuck do I get the refresh token too?
    # Step 1. Exchange authorization code for access token.
    r = requests.post(access_token_url, payload)
    token = json.loads(r.text)
    logger.debug(token)
    headers = {'Authorization': 'Bearer {0}'.format(token['access_token'])}

    # Step 2. Retrieve information about the current inbox.
    r = requests.get(api_url, headers=headers)
    profile = json.loads(r.text)
    logger.debug(r.text)

    api_key = 'AIzaSyBQ_7NKpNxJPiWyiwutKVQM-ur5kbcO718'
    r2 = requests.get('https://www.googleapis.com/gmail/v1/users/me/labels?key=%s' % api_key, headers=headers)
    logger.debug(r2.text)

    sub = profile.get('sub')
    if not sub:
        return jsonify()

    inbox = app.models.Inbox.query.filter_by(google=sub).first()
    if inbox:
        token = create_token(inbox)
        return jsonify(token=token, user=inbox.serialize(), success=True)
    name = profile.get('displayName') or profile.get('name')
    inbox = app.models.Inbox(google=sub, name=name, email=profile.get('email'))
    app.db.session.add(inbox)
    app.db.session.commit()
    token = create_token(inbox)
    return jsonify(token=token, user=inbox.serialize(), success=True)

@app.flask_app.route('/my-timezone')
def mytimezone():
    return 'tz3'

@app.flask_app.route('/update-blocks', methods=['POST'])
def update_blocks():
    payload = request.json
    return jsonify(success="success")
    # payload = dict(client_id=payload['clientId'],
    #                redirect_uri=payload['redirectUri'],
    #                client_secret=config['GOOGLE_SECRET'],
    #                code=payload['code'],
    #                grant_type='authorization_code')

@app.flask_app.route('/update-timezone', methods=['POST'])
def update_timezone():
    payload = request.json
    return jsonify(success="success")

logger = app.flask_app.logger

@app.flask_app.route('/api/user-from-token/<token>')
def user_from_token(token):
    try:
        decoded = jwt.decode(token, config['SECRET_KEY'])
        sub = decoded.get('sub')
        if not sub:
            return jsonify(success=False)
        inbox = app.models.Inbox.query.filter_by(google=str(sub)).first()
        if not inbox:
            logger.debug('no inbox...')
            return jsonify(success=True, token=False)
        return jsonify(user=inbox.serialize(), success=True, token=token) #update token
    except Exception, e:
        app.flask_app.logger.debug('exception %s' % e)
        return jsonify(success=False)
