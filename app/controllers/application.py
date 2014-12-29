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
import stripe

config = app.flask_app.config
logger = app.flask_app.logger

# special file handlers and error handlers
@app.flask_app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.flask_app.root_path, 'static'), 'img/favicon.ico')

# routing for basic pages (pass routing onto the Angular app)
@app.flask_app.route('/')
@app.flask_app.route('/about')
@app.flask_app.route('/me')
def basic_pages():
    return make_response(open('app/public/template/index.html').read())

def create_token(customer):
    payload = {
        'sub': customer.id,
        'iat': datetime.now(),
        'exp': datetime.now() + timedelta(days=14)
        }
    token = jwt.encode(payload, config['SECRET_KEY'])
    return token.decode('unicode_escape')

def get_token_expiry(expires_in):
    return (datetime.utcnow() + timedelta(seconds=expires_in-30)).strftime('%Y-%m-%dT%H:%M:%SZ')

def get_google_credentials(access_token, refresh_token, expires_in):
    token_expiry = get_token_expiry(expires_in)

    return json.dumps({
        '_module': 'oauth2client.client', 'token_expiry': token_expiry, 'invalid': False,
        'access_token': access_token, 'token_uri': 'https://accounts.google.com/o/oauth2/token',
        'token_response': {
            'access_token': access_token, 'token_type': 'Bearer',
            'expires_in': expires_in, 'refresh_token': refresh_token
        },
        'client_id': config['GOOGLE_ID'], 'id_token': None,
        'client_secret': config['GOOGLE_SECRET'], '_class': 'OAuth2Credentials',
        'revoke_uri': 'https://accounts.google.com/o/oauth2/revoke',
        'refresh_token': refresh_token, 'user_agent': None
    })

@app.flask_app.route('/auth/google', methods=['POST'])
def google():
    access_token_url = 'https://accounts.google.com/o/oauth2/token'
    google_profile_url = 'https://www.googleapis.com/plus/v1/people/me/openIdConnect'

    tz_offset = int(request.json.get('state', {}).get('tzOffset', -5*60))
    payload = request.json
    payload = dict(client_id=payload['clientId'],
                   redirect_uri=payload['redirectUri'],
                   client_secret=config['GOOGLE_SECRET'],
                   code=payload['code'],
                   grant_type='authorization_code')

    # Exchange authorization code for access token.
    r = requests.post(access_token_url, payload)
    token = json.loads(r.text)
    access_token = token['access_token']
    refresh_token = token.get('refresh_token')
    expires_in = token['expires_in']
    headers = {'Authorization': 'Bearer {0}'.format(access_token)}

    # Retrieve information about the current inbox.
    try:
        r = requests.get(google_profile_url, headers=headers)
        profile = json.loads(r.text)

        sub = profile.get('sub')
        if not sub:
            return jsonify()

        inbox = app.models.Inbox.query.filter_by(google_id=sub).first()
        google_credentials = get_google_credentials(access_token, refresh_token, expires_in)
        if inbox:
            token = create_token(inbox.customer)
            inbox.google_credentials = google_credentials
            if not inbox.last_timezone_adj_time:
                inbox.setup_tz_on_arrival(tz_offset)
            if not inbox.last_timeblock_adj_time:
                inbox.setup_tb_on_arrival()
            return jsonify(token=token, user=inbox.basic_info(), success=True)

        name = profile.get('displayName') or profile.get('name')
        email = profile.get('email')
        customer = app.models.Customer(name=name)
        inbox = app.models.Inbox(name=name, email=email, google_id=sub)
        inbox.set_google_access_token(access_token, expires_in, refresh_token, google_credentials, commit=False)
        inbox.setup_tz_on_arrival(tz_offset, commit=False)
        inbox.setup_tb_on_arrival(commit=False)
        customer.inboxes.append(inbox)
        app.db.session.add(inbox)
        app.db.session.add(customer)
        app.db.session.commit()
        app.controllers.mailbox.create_label(inbox) # do this asynchronously
        return jsonify(token=create_token(customer), user=inbox.basic_info(), success=True)
    except Exception, e:
        app.controllers.mailbox.revoke_access(access_token=access_token)
        return jsonify(success=False)

@app.flask_app.route('/api/get-time-info/<email>', methods=['GET'])
def get_time_info(email):
    inbox = app.models.Inbox.query.filter_by(email=email).first()
    if not inbox:
        return jsonify(success=False)
    return jsonify(success=True, user=inbox.serialize())

@app.flask_app.route('/update-blocks', methods=['POST'])
def update_blocks():
    payload = request.json['data']
    inbox = app.models.Inbox.query.filter_by(email=payload['email']).first()
    if not inbox or not inbox.is_tb_adjust():
        return jsonify(success=False)

    for block in payload['timeblocks']:
        inbox.set_timeblock(int(block['start']), int(block['length']), commit=False)

    now = app.utility.get_time()
    inbox.last_timeblock_adj_time = now
    if not inbox.customer.last_checked_time and inbox.is_complete(): # for the workers
        inbox.customer.last_checked_time = now

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
    if not inbox.customer.last_checked_time and inbox.is_complete(): # set the customer
        inbox.customer.last_checked_time = now

    app.db.session.commit()
    return jsonify(success=True, user=inbox.serialize())

@app.flask_app.route('/api/user-from-token/<token>')
def user_from_token(token):
    try:
        decoded = jwt.decode(token, config['SECRET_KEY'])
        sub = decoded.get('sub')
        if not sub:
            return jsonify(success=False)
        inboxes = app.models.Inbox.query.filter_by(app.models.Inbox.customer_id == sub)
        if inboxes.count() == 0:
            return jsonify(success=True, token=False)
        return jsonify(user=inboxes.first().basic_info(), success=True, token=token) # Change at some point to include more than one inbox
    except Exception, e:
        logger.debug('exception %s' % e)
        return jsonify(success=False)

@app.flask_app.route('/post-payment', methods=['POST'])
def post_payment():
    payload = request.json['data']
    token = payload['token']
    email = token.get('email')
    if not email:
        return jsonify(success=False, msg="no email")

    selection = token.get('selection')
    if not selection:
        return jsonify(success=False, msg="no selection")

    inbox = app.models.Inbox.query.filter_by(app.models.Inbox.email == email).first()
    if not inbox:
        return jsonify(success=False, msg="no inbox")

    amount = account_costs[selection]
    customer_id = inbox.stripe_customer_id
    if not customer_id:
        customer_id = stripe.Customer.create(card=token, description=inbox.email).id
        inbox.set_stripe_id(customer_id)
    if not customer_id:
        return jsonify(success=False, msg="couldnt make a stripe customer.")

    stripe.Charge.create(
        amount=amount, currency='usd', customer=customer_id)
