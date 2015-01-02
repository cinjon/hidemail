import app
import requests
import string
import random
import json
import datetime

from apiclient.http import BatchHttpRequest

logger = app.flask_app.logger

def get_headers(inbox, content_type=None):
    headers = {'Authorization': 'Bearer {0}'.format(inbox.google_access_token)}
    if content_type:
        headers['Content-Type'] = content_type
    return headers

def _get_thread_ids_from_label(inbox, label):
    thread_ids = []
    try:
        response = inbox.get_gmail_service().users().threads().list(userId=inbox.email, labelIds=[label]).execute()
        while 'nextPageToken' in response:
            thread_ids.extend([t['id'] for t in response.get('threads', [])])
            response = service.users().threads().list(
                userId=inbox.email, labelIds=[label], pageToken=response['nextPageToken']).execute()
        thread_ids.extend([t['id'] for t in response.get('threads', [])])
        return thread_ids
    except Exception, e:
        logger.debug('Error in getting thread ids for %s from label %s: %s' % (inbox.email, label, e))
        return thread_ids

def do_batch_modify_threads(inbox, threads, payload):
    def batch_callback(request_id, response, exception):
        """In the response is: historyId, snippet, sizeEstimate, threadId, and labelIds"""
        pass

    service = inbox.get_gmail_service()
    batch_request_limit = app.config.batchRequestLimit
    count = 0
    while count < len(threads):
        batch = BatchHttpRequest()
        for thread in threads[count:count + batch_request_limit]:
            batch.add(
                service.users().threads().modify(
                    userId=inbox.email, id=thread, body=payload),
                callback=batch_callback)
        batch.execute()
        count += batch_request_limit

def modify_threads(inbox, addLabel, removeLabel):
    if not addLabel or not removeLabel:
        return

    threads = _get_thread_ids_from_label(inbox, removeLabel)
    do_batch_modify_threads(inbox, threads, {
        'removeLabelIds':[removeLabel], 'addLabelIds':[addLabel]
        })

def _modifying_mail_check(inbox):
    if not inbox.custom_label_id and not create_label(inbox):
        return False
    return True

def hide_all_mail(inbox):
    if _modifying_mail_check(inbox):
        modify_threads(inbox, inbox.custom_label_id, 'INBOX')

def show_all_mail(inbox):
    if _modifying_mail_check(inbox):
        modify_threads(inbox, 'INBOX', inbox.custom_label_id)

def get_labels(inbox):
    if not inbox:
        return None

    try:
        return inbox.get_gmail_service().users().labels().list(userId=inbox.email).execute()
    except Exception, e:
        return []

def get_label_id(inbox, label_name=None):
    if not label_name or not inbox:
        return None

    for label in get_labels(inbox).get('labels', []):
        if label.get('name') == label_name:
            return label.get('id')
    return None

def _delete_label(inbox, label_id=None):
    if not label_id or not inbox:
        return True

    try:
        inbox.get_gmail_service().users().labels().delete(
            userId=inbox.email, id=label_id).execute()
        return True
    except Exception, e:
        logger.debug('exception deleting label %s for inbox %s: %s' % (label_id, inbox.email, e))
        return False

def delete_label(inbox, label_name=None):
    if inbox.custom_label_id:
        return _delete_label(inbox, inbox.custom_label_id)
    else:
        return _delete_label(inbox, get_label_id(inbox, label_name))

def create_label(inbox, label_name=None):
    def prepend_random(base):
        return '-'.join([''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6)), base])

    if not is_fresh_token(inbox):
        return

    label_name = label_name or prepend_random('mailboxFlow')
    if not delete_label(inbox, label_name):
        logger.debug('trouble creating label %s for %s, couldnt delete it.' % (label_name, inbox.email))
        return False

    payload = {
        'labelListVisibility':'labelHide',
        'messageListVisibility':'hide',
        'name':label_name
        }
    try:
        label = inbox.get_gmail_service().users().labels().create(userId=inbox.email, body=payload).execute()
        inbox.custom_label_name = label['name']
        inbox.custom_label_id   = label['id']
        app.db.session.commit()
        return True
    except Exception, e:
        logger.debug('Error in creating label for %s: %s' % (inbox.email, e))
        return False

def revoke_access(inbox=None, access_token=None):
    if not inbox or not is_fresh_token(inbox):
        return False

    try:
        show_all_mail(inbox) # an error doing this will stop the process... even if the error is in creating the label. make it more robust.
        access_token = inbox.google_access_token
        r = requests.get('https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token)
        inbox.clear_access_tokens()
        inbox.inactivate()
    except Exception, e:
        logger.debug('Error in revoking access: %s' % e)
        logger.debug(r.text)

def is_fresh_token(inbox):
    if app.utility.get_time() - datetime.timedelta(seconds=3) > inbox.google_access_token_expiration and not refresh_access(inbox):
        return False
    return True

def refresh_access(inbox):
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
