import app
import requests
import string
import random
import json
import datetime

api_key = app.flask_app.config['GOOGLE_API_KEY']
base_url = 'https://www.googleapis.com/gmail/v1/users'
logger = app.flask_app.logger
warning_invalid_credentials = ['Invalid Credentials']

def get_headers(inbox, content_type=None):
    headers = {'Authorization': 'Bearer {0}'.format(inbox.google_access_token)}
    if content_type:
        headers['Content-Type'] = content_type
    return headers

def is_fresh_token(inbox):
    if datetime.datetime.now() - datetime.timedelta(0, 3) > inbox.google_access_token_expiration and not refresh_access(inbox):
        return False
    return True

def _get_thread_ids_from_label(inbox, label):
    headers = get_headers(inbox)
    url = base_url + '/%s/threads?labelIds=%s&key=%s' % (inbox.email, label, api_key)
    thread_ids = []
    try:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            logger.debug(r.text)
            logger.debug('Error in getting thread ids: %d.' % r.status_code)
            return []
        result = json.loads(r.text)
        while 'nextPageToken' in result:
            logger.debug('dong nextpagetoken')
            thread_ids.extend([t['id'] for t in result['threads']])
            r = request.get('&'.join([url, 'pageToken=%s' % result['nextPageToken']]))
            if int(r.status_code) != 200:
                logger.debug(r.text)
                logger.debug('Error in getting thread ids: %d.' % r.status_code)
                return thread_ids
            result = json.loads(r.text)
        logger.debug(result)
        thread_ids.extend([t['id'] for t in result['threads']])
        logger.debug('length of thread_ids: %d' % len(thread_ids))
        return thread_ids
    except Exception, e:
        logger.debug('Error in getting thread ids for %s from label %s: %s' % (inbox.email, label, e))
        return []

def modify_threads(inbox, addLabel, removeLabel):
    headers = get_headers(inbox, content_type='application/json')
    payload = dict(removeLabelIds=[removeLabel], addLabelIds=[addLabel])
    thread_ids = _get_thread_ids_from_label(inbox, removeLabel)
    logger.debug(thread_ids)
    for thread_id in thread_ids:
        url = base_url + '/%s/threads/%s/modify?key=%s' % (inbox.email, thread_id, api_key)
        try:
            r = requests.post(url, data=json.dumps(payload), headers=headers)
            logger.debug(r.text)
            if r.status_code != 200:
                return False
        except Exception, e:
            logger.debug('Error in modifying threads for inbox %s. Was trying to add to %s and remove from %s.' % (inbox.email, addLabel, removeLabel))
            return False
    return True

def hide_all_mail(inbox):
    if not is_fresh_token(inbox):
        logger.debug('not fresh token in hide mail')
        return
    return modify_threads(inbox, inbox.custom_label_id, 'INBOX')

def show_all_mail(inbox):
    if not is_fresh_token(inbox):
        logger.debug('not fresh token in show mail')
        return
    return modify_threads(inbox, 'INBOX', inbox.custom_label_id)

def create_label(inbox, label_name=None):
    if not is_fresh_token(inbox):
        logger.debug('not fresh token in create_label')
        return

    label_name = label_name or 'BatchMail-%s' % ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    headers = get_headers(inbox, content_type='application/json')
    url = base_url + '/%s/labels?key=%s' % (inbox.email, api_key)
    payload = {
        'labelListVisibility':'labelHide',
        'messageListVisibility':'hide',
        'name':label_name
        }
    try:
        r = requests.post(url, json.dumps(payload), headers=headers)
        result = json.loads(r.text)
        inbox.custom_label_name = label_name
        inbox.custom_label_id = result.get('id')
        app.db.session.commit()
        return True
    except Exception, e:
        logger.debug('Error in creating label for %s: %s' % (inbox.email, e))
        return False

def revoke_access(inbox=None, access_token=None):
    r = None
    try:
        if inbox:
            access_token = inbox.google_access_token
        r = requests.get('https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token)
        if inbox:
            inbox.clear_access_tokens()
    except Exception, e:
        logger.debug('Error in revoking access: %s' % e)
        logger.debug(r.text)

def refresh_access(inbox):
    logger.debug('Refreshing access for %s' % inbox.email)
    url = 'https://www.googleapis.com/oauth2/v3/token'
    payload = {'client_id':app.flask_app.config['GOOGLE_ID'],
               'client_secret':app.flask_app.config['GOOGLE_SECRET'],
               'refresh_token':inbox.refresh_token,
               'grant_type':'refresh_token'}
    try:
        r = requests.post(url, payload)
        logger.debug('in refresh access: %s' % r.text)
        result = json.loads(r.text)
        inbox.set_google_access_token(result.get('access_token'), result.get('expires_in'))
        return True
    except Exception, e:
        logger.debug('Error in refreshing access: %s' % e)
        logger.debug(r.text)
        return False
