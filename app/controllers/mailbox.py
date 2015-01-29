import app
import requests
import string
import random
import json
import datetime
import time

from apiclient.http import BatchHttpRequest

logger = app.flask_app.logger

def get_headers(inbox, content_type=None):
    headers = {'Authorization': 'Bearer {0}'.format(inbox.google_access_token)}
    if content_type:
        headers['Content-Type'] = content_type
    return headers

def get_thread_ids_and_page_token(inbox, labelIds, q=None, pageToken=None, service=None):
    q = q or ''
    service = service or inbox.get_gmail_service()
    response = service.users().threads().list(userId=inbox.email, labelIds=labelIds, q=q, pageToken=pageToken).execute()
    return [t['id'] for t in response.get('threads', [])], response.get('nextPageToken')

def get_all_thread_ids_from_label(inbox, label, q=None):
    backoff = 1
    thread_ids = []
    service = inbox.get_gmail_service()
    nextPageToken = None
    ids, nextPageToken = get_thread_ids_and_page_token(inbox, [label], q, nextPageToken, service)
    while nextPageToken:
        try:
            thread_ids.extend(ids)
            ids, nextPageToken = get_thread_ids_and_page_token(inbox, [label], q, nextPageToken, service)
        except Exception, e:
            time.sleep(backoff)
            backoff = backoff * 2
    thread_ids.extend(ids)
    return list(set(thread_ids))

class Batcher(object):
    def __init__(self, userId, service, payload, threads):
        self.count = 0
        self.backoff = 1
        self.userId = userId
        self.service = service
        self.payload = payload
        self.threads = threads
        self.failed_threads = set()
        self.seen_responses = 0
        self.batch_fail = False
        self.batch_request_limit = 10 # each modify thread takes up a unit quota of 10, can get away with bursting though.
        #     self.batch_request_limit = app.config.batchRequestLimit

    def inc(self):
        if self.backoff < 64:
            self.backoff = self.backoff * 2

    def get(self):
        return self.backoff + random.random()/2 # between 0 and 500ms

    def runWorker(self, service=None, userId=None):
        service = self.service
        if not self.threads:
            return

        batch = BatchHttpRequest()
        count = 0
        while self.threads and count < self.batch_request_limit:
            count += 1
            thread = self.threads.pop(0)
            batch.add(callback=self.cb, request_id=thread,
                      request=service.users().threads().modify(
                          userId=self.userId, id=thread, body=self.payload))
        batch.execute()

    def cb(self, request_id, response, exception):
        """In the response is: historyId, snippet, sizeEstimate, threadId, and labelIds"""
        self.seen_responses += 1
        if exception:
            self.threads.append(request_id)
            self.batch_fail = True
        if self.seen_responses == self.batch_request_limit:
            if self.batch_fail:
                backoff = self.get()
                time.sleep(backoff)
                self.inc()
            self.seen_responses = 0
            self.batch_fail = False
            self.runWorker()

def archive(inbox, dt=None):
    """Archives all mail from any day earlier than the specified dt. Uses exponential backoff if it hits an error"""
    customer = inbox.customer
    dt = dt or app.utility.get_time() - datetime.timedelta(days=15)
    date_string = '%s/%s/%s' % (dt.year, dt.month, dt.day)
    q = 'before:%s' % date_string
    payload = {'removeLabelIds':['INBOX']}
    service = inbox.get_gmail_service()
    email = inbox.email
    label = 'INBOX'

    thread_ids, pageToken = get_thread_ids_and_page_token(inbox, [label], q, None, service)
    thread_ids.reverse()
    batcher = Batcher(email, service, payload, thread_ids)
    thread_count = len(batcher.threads)
    while batcher.threads:
        try:
            batcher.runWorker()
        except Exception, e:
            pass

    if pageToken:
        app.queue.queues.IQ.get_queue().enqueue(
            app.models.manage_inbox_queue, ('inbox', inbox.id, 'archive'))
    elif not inbox.is_active or not customer.is_init_archiving_complete:
        inbox.is_active = True
        inbox.is_archived = True
        if not customer.is_init_archiving_complete:
            customer.is_init_archiving = False
            customer.is_init_archiving_complete = True
        app.db.session.commit()

def modify_threads(inbox, payloadKey, label, thread_ids):
    Batcher(inbox.email, inbox.get_gmail_service(), {payloadKey:[label]}, thread_ids).runWorker()

def hide_all_mail(inbox):
    label = 'INBOX'
    threads = get_all_thread_ids_from_label(inbox, label)
    threads = [app.models.get_or_create_thread(thread, inbox, commit=False) for thread in threads]
    threads = [thread for thread in threads if thread]
    if not threads:
        return
    dt = app.utility.get_time()
    for thread in threads:
        thread.hide(dt, False)
    app.db.session.commit()
    thread_ids = [thread.thread_id.split('-' + str(thread.inbox_unique_id))[0] for thread in threads]
    modify_threads(inbox, 'removeLabelIds', label, thread_ids)

def show_all_mail(inbox):
    dt = app.utility.get_time()
    threads = inbox.threads.filter_by(active=True).all()
    thread_ids = [thread.thread_id.split('-' + str(thread.inbox_unique_id))[0] for thread in threads]
    modify_threads(inbox, 'addLabelIds', 'INBOX', thread_ids)
    for thread in threads:
        thread.show(dt, False)
    app.db.session.commit()

def revoke_access(inbox=None, access_token=None):
    if not inbox or not is_fresh_token(inbox):
        return False

    try:
        show_all_mail(inbox)
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
