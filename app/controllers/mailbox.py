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

is_batch_requests = False # toggle when you complete the batching

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
            return []
        result = json.loads(r.text)
        while 'nextPageToken' in result:
            thread_ids.extend([t['id'] for t in result.get('threads', [])])
            r = request.get('&'.join([url, 'pageToken=%s' % result['nextPageToken']]))
            result = json.loads(r.text)
        thread_ids.extend([t['id'] for t in result.get('threads', [])])
        return thread_ids
    except Exception, e:
        logger.debug('Error in getting thread ids for %s from label %s: %s' % (inbox.email, label, e))
        return thread_ids

def do_batch_requests(inbox, threads, payload):
    headers = get_headers(inbox)
    thread_urls = ['/gmail/v1/users/%s/threads/%s/modify?key=%s' % (inbox.email, thread, api_key) for thread in threads]
    count = 0
    while count < len(thread_urls):
        batch_request(thread_urls[count:count+100], payload, headers)
        count += 100

def modify_threads(inbox, addLabel, removeLabel):
    if not addLabel or not removeLabel:
        logger.debug('Threads are still not complete for %s. Not modifying.' % inbox.email)
        return

    payload = dict(removeLabelIds=[removeLabel], addLabelIds=[addLabel])
    threads = _get_thread_ids_from_label(inbox, removeLabel)

    if is_batch_requests:
        return do_batch_requests(inbox, threads, payload)
    else:
        headers = get_headers(inbox, content_type='application/json')
        payload = json.dumps(payload)
        for thread in threads:
            try:
                url = base_url + '/%s/threads/%s/modify?key=%s' % (inbox.email, thread, api_key)
                r = requests.post(url, data=payload, headers=headers)
                if r.status_code != 200:
                    logger.debug('status code %d for url %s for inbox %s' % (r.status_code, url, inbox.email))
            except Exception, e:
                logger.debug('failed %s with error %s for inbox %s' % (url, e, inbox.email))

def batch_request(urls, payload, headers):
    r = requests.post('https://www.googleapis.com',
                      files={num:(url, json.dumps(payload), 'application/json', headers) for num, url in enumerate(urls)})
    logger.debug(r.text)
    logger.debug(r.status_code)
    if r.status_code != 200:
        return False
    return True

def _modifying_mail_check(inbox):
    if not is_fresh_token(inbox):
        logger.debug('We have a problem with refreshing the token for inbox %s.' % inbox.email)
        return False
    if not inbox.custom_label_id and not create_label(inbox):
        logger.debug('We have a problem with generating the label for inbox %s.' % inbox.email)
        return False
    return True

def hide_all_mail(inbox):
    if _modifying_mail_check(inbox):
        modify_threads(inbox, inbox.custom_label_id, 'INBOX')

def show_all_mail(inbox):
    if _modifying_mail_check(inbox):
        modify_threads(inbox, 'INBOX', inbox.custom_label_id)

def create_label(inbox, label_name=None):
    if not is_fresh_token(inbox):
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
    logger.debug('refreshing access')
    url = 'https://www.googleapis.com/oauth2/v3/token'
    payload = {'client_id':app.flask_app.config['GOOGLE_ID'],
               'client_secret':app.flask_app.config['GOOGLE_SECRET'],
               'refresh_token':inbox.google_refresh_token,
               'grant_type':'refresh_token'}
    try:
        r = requests.post(url, payload)
        result = json.loads(r.text)
        inbox.set_google_access_token(result.get('access_token'), result.get('expires_in'))
        return True
    except Exception, e:
        logger.debug('Error in refreshing access: %s' % e)
        logger.debug(r.text)
        return False
