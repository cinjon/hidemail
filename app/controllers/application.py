import app
import os
import httplib2
import json
import jwt
import requests
from datetime import datetime, timedelta
from urllib import urlencode
from functools import wraps
from flask import send_from_directory, make_response, request, jsonify
from flask.ext.mobility.decorators import mobile_template

logger = app.flask_app.logger

# special file handlers and error handlers
@app.flask_app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.flask_app.root_path, 'static'), 'img/favicon.ico')

# routing for basic pages (pass routing onto the Angular app)
@app.flask_app.route('/')
@app.flask_app.route('/me')
@app.flask_app.route('/plans')
@app.flask_app.route('/faq')
def basic_pages():
    return make_response(open('app/public/template/index.html').read())

def create_token(customer):
    payload = {
        'sub': customer.id,
        'iat': datetime.now(),
        'exp': datetime.now() + timedelta(days=14)
        }
    token = jwt.encode(payload, app.config.SECRET_KEY)
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
        'client_id': app.config.GOOGLE_ID, 'id_token': None,
        'client_secret': app.config.GOOGLE_SECRET, '_class': 'OAuth2Credentials',
        'revoke_uri': 'https://accounts.google.com/o/oauth2/revoke',
        'refresh_token': refresh_token, 'user_agent': None
    })

@app.flask_app.route('/auth/google', methods=['POST'])
def google():
    access_token_url = 'https://accounts.google.com/o/oauth2/token'
    google_profile_url = 'https://www.googleapis.com/plus/v1/people/me/openIdConnect'

    state = request.json.get('state', {})
    tz_offset = int(state.get('tzOffset', -5*60))
    customer_id = state.get('customer')
    customer = None
    if customer_id:
        customer = app.models.Customer.query.get(int(customer_id))

    payload = request.json
    payload = dict(client_id=payload['clientId'],
                   redirect_uri=payload['redirectUri'],
                   client_secret=app.config.GOOGLE_SECRET,
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
            return jsonify(success=False, msg="no google sub")

        inbox = app.models.Inbox.query.filter_by(google_id=sub).first()
        google_credentials = get_google_credentials(access_token, refresh_token, expires_in)
        if inbox:
            inbox.google_credentials = google_credentials
            customer = align_customer_with_inbox(inbox, customer)
            token = create_token(customer)
            if not customer.last_timezone_adj_time:
                customer.setup_tz_on_arrival(tz_offset)
            if not customer.last_timeblock_adj_time:
                customer.setup_tb_on_arrival()
            if customer.is_active(): #and not customer.is_paused(): TODO!!!
                inbox.activate()
            return jsonify(token=token, user=customer.serialize(), success=True)

        name = profile.get('displayName') or profile.get('name')
        if not customer:
            customer = app.models.Customer(name=name)
            customer.setup_tz_on_arrival(tz_offset, commit=False)
            customer.setup_tb_on_arrival(commit=False)
        email = profile.get('email')
        inbox = app.models.Inbox(name=name, email=email, google_id=sub)
        inbox.set_google_access_token(access_token, expires_in, refresh_token, google_credentials, commit=False)
        if customer.is_active():
            inbox.activate()
        customer.inboxes.append(inbox)
        app.db.session.add(inbox)
        app.db.session.add(customer)
        app.db.session.commit()
        return jsonify(token=create_token(customer), user=customer.serialize(), success=True)
    except Exception, e:
        app.controllers.mailbox.revoke_access(access_token=access_token)
        return jsonify(success=False)

def align_customer_with_inbox(inbox, customer):
    if not customer:
        return inbox.customer

    if customer and inbox.customer.id != customer.id:
        for i in inbox.customer.inboxes:
            customer.inboxes.append(i)
            i.customer = customer
            app.db.session.commit()
    return customer

@app.flask_app.route('/get-stripe-pk', methods=['GET'])
def get_stripe_pk():
    return jsonify(success=True, stripe_pk=app.stripe_pk)

#TODO: obfuscate the id?
@app.flask_app.route('/get-time-info/<customer_id>', methods=['GET'])
def get_time_info(customer_id):
    customer = app.models.Customer.query.get(int(customer_id))
    if not customer:
        return jsonify(success=False)
    return jsonify(success=True, user=customer.serialize())

@app.flask_app.route('/update-blocks', methods=['POST'])
def update_blocks():
    payload = request.json['data']
    customer = app.models.Customer.query.get(int(payload['customer_id']))
    if not customer or not customer.is_tb_adjust():
        return jsonify(success=False)

    new_blocks = payload['timeblocks']
    curr_blocks = customer.get_timeblocks()
    for new_block in new_blocks:
        if not any([new_block['start'] == curr_block.start_time for curr_block in curr_blocks]):
            customer.set_timeblock(new_block['start'], new_block['length'], commit=False)
    for curr_block in curr_blocks:
        if not any([new_block['start'] == curr_block.start_time for new_block in new_blocks]):
            curr_block.is_active = False
    app.db.session.commit()

    now = app.utility.get_time()
    customer.last_timeblock_adj_time = now
    if not customer.last_checked_time and customer.last_timezone_adj_time:
        customer.last_checked_time = now
    app.db.session.commit()

    return jsonify(success=True, user=customer.serialize())

@app.flask_app.route('/update-timezone', methods=['POST'])
def update_timezone():
    payload = request.json['data']
    customer = app.models.Customer.query.get(int(payload['customer_id']))
    if not customer:
        return jsonify(success=False)

    customer.set_timezone(offset=int(payload['tz']), commit=False)
    now = app.utility.get_time()
    customer.last_timezone_adj_time = now
    customer.last_checked_time = now

    app.db.session.commit()
    return jsonify(success=True, user=customer.serialize())

@app.flask_app.route('/activate-account', methods=['POST'])
def activate_account():
    payload = request.json['data']
    customer = app.models.Customer.query.get(int(payload['customer_id']))
    if not customer:
        return jsonify(success=False)

    customer.activate()
    app.db.session.commit()
    return jsonify(success=True, user=customer.serialize())

@app.flask_app.route('/user-from-token/<token>')
def user_from_token(token):
    try:
        decoded = jwt.decode(token, app.config.SECRET_KEY)
        sub = decoded.get('sub')
        if not sub:
            return jsonify(success=False)
        return jsonify(user=app.models.Customer.query.get(int(sub)).basic_info(),
                       success=True, token=token)
    except Exception, e:
        return jsonify(success=False)

account_types = app.models.account_types
account_costs = app.models.account_costs

@app.flask_app.route('/post-payment', methods=['POST'])
def post_payment():
    payload = request.json['data']
    token = payload['token']
    customer_id = token.get('customer_id')
    if not customer_id:
        return jsonify(success=False, error='request_fail')

    selection = token.get('selection')
    if not selection:
        return jsonify(success=False, error='request_fail')

    customer = app.models.Customer.query.get(int(customer_id))
    if not customer:
        return jsonify(success=False, error='request_fail')

    account_type = account_types[selection]
    if account_type == account_types['monthly']:
        return buy_subscription(customer, token)
    else:
        return jsonify(success=False, error='request_fail')

@app.flask_app.route('/post-trial', methods=['POST'])
def post_trial():
    # free trial, ends after a week.
    payload = request.json['data']
    customer_id = payload['customer_id']
    if not customer_id:
        return jsonify(success=False, error='request_fail')

    customer = app.models.Customer.query.get(int(customer_id))
    if not customer:
        return jsonify(success=False, error='request_fail')

    return buy_trial(customer)

def buy_trial(customer):
    return _complete_purchase(customer, 'trial', account_costs['trial']*100)

def buy_subscription(customer, token):
    handler = app.controllers.stripe_handler.StripeHandler()
    description = '%s' % customer.name
    card = token.get('id')
    stripe_customer = handler.create_customer(card=card, description=description, plan='monthly')
    if not stripe_customer['success']:
        return jsonify(success=False, errorType=stripe_customer['errorType'])
    stripe_customer_id = stripe_customer['id']
    customer.set_stripe_id(stripe_customer_id)
    return _complete_purchase(customer, 'monthly', account_costs['monthly']*100)

def buy_sabbatical(customer, token):
    handler = app.controllers.stripe_handler.StripeHandler()
    description = '%s - %s' % (customer.name, customer.id)
    card = token.get('id')
    stripe_customer = handler.create_customer(card=card, description=description)
    if not stripe_customer['success']:
        return jsonify(success=False, errorType=stripe_customer['errorType'])
    stripe_customer_id = stripe_customer['id']

    customer.set_stripe_id(stripe_customer_id)
    amount = account_costs['break']*100
    charge = handler.charge(amount=amount, currency='usd',
                            stripe_customer_id=stripe_customer_id)

    if not charge['success']:
        return jsonify(success=False, errorType=charge['errorType'])
    return _complete_purchase(customer, 'break', amount)

def _complete_purchase(customer, ty, amount):
    purchase = app.models.create_purchase(
        account_types[ty], amount, commit=False)
    customer.purchases.append(purchase)
    customer.account_type = purchase.account_type
    if ty == 'break':
        sabbatical = app.models.create_sabbatical(commit=False)
        customer.sabbaticals.append(sabbatical)
    if ty == 'trial':
        customer.start_trial(commit=False)
    app.db.session.commit()
    return jsonify(success=True, user=customer.serialize())
