import app
import random
import datetime
from sqlalchemy.sql import func
import os
import redis
from rq import Worker, Queue as rqQueue, Connection
from Queue import Queue

"""
The plan:
1. Set up a pool of workers
2. Set up two queues, GmailRequestsQueue (GRQ) and InboxManageQueue (IMQ)
3. GRQ is a queue of requests to be sent to gmail to manage inboxes.
    - It will fire when either it receives 100 requests (batch max for gmail api) or
    - It's been <maxQueueTime> seconds since the last time it fired and it has requests in the queue
    - Firing: a worker takes 100 requests off the queue, batches them into a multipart request, and sends to gmail api
4. IMQ is a queue of inboxes and a manager.
    - It is always firing, i.e. workers are handling items from it as soon as they are added.
    - A worker runs runWorker() on the object it receives in the Queue.
    - If the object is an inbox, then runWorker will:
        - Check to see that the current utc time coupled with the inbox's timezone offset falls outside of their timeblocks.
        - If true, and if earlier than <warmingTime> before any timeblock's start or later than any timeblock's end, then add a 'hide all mail' request to the GRQ.
        - If true, and if within <warmingTime> before a timeblock's start, then add a 'show all mail' request to the GRQ.
        - Regardless, stamp the inbox's last_checked timestamp with now.
    - If the object is a manager, then runWorker will:
        - Grab all inboxes with last_checked timestamp greater than <checkedPeriod> before now.
        - Add all of these inboxes to the IMQ. Then add a manager to the IMQ.
5. It might be better to think of the GRQ as a GmailRequestManager instead.
    - It has requests and as soon as it hits either 100 requests or its most recent request was more than 10 seconds apart from its first request,
    - It sends them all off in a multipart batch request to Gmail API and clears its cache of requests.
6. Fuck. So the gmail batcher wants it to be s.t. each batch is for one person. We may as well just batch at the function then.
"""

warmingTime = 120 # seconds
checkedPeriod = 60 # seconds
maxQueueTime = 10 # seconds
logger = app.flask_app.logger

def manage_inbox_queue(obj):
    obj.runWorker()

class InboxQueueManager(object):
    last_run_time = None

    @classmethod
    def __init__(cls):
        logger.debug('starting IQM')
        cls.get_queue().enqueue(manage_inbox_queue, cls)

    @classmethod
    def get_queue(cls):
        return InboxQueue().get_queue()

    @classmethod
    def runWorker(cls):
        logger.debug('running iqm')
        queue = cls.get_queue()
        now = app.utility.get_time()
        if last_run_time and last_run_time > now - datetime.timedelta(seconds=60):
            logger.debug('not running, enqueue again')
            queue.enqueue(manage_inbox_queue, cls)
            return

        logger.debug('yes running')
        last_checked_param = now - datetime.timedelta(0, checkedPeriod)
        for inbox in app.models.Inbox.query.filter_by(app.models.Inbox.last_checked_time < last_checked_param):
            logger.debug('doing inbox %s' % inbox.email)
            inbox.set_last_checked_time(now)
            queue.enqueue(manage_inbox_queue, inbox)
        queue.enqueue(manage_inbox_queue, cls)
        cls.last_run_time = now

class InboxQueue(object):
    listen = ['high', 'default', 'low']
    conn = redis.from_url(app.config.REDIS_URL)

    @classmethod
    def get_queue(cls):
        return rqQueue(connection=cls.conn)

    @classmethod
    def run(cls):
        with Connection(cls.conn):
            worker = Worker(map(rqQueue, cls.listen))
            worker.work()

if __name__ == '__main__':
    IQ  = InboxQueue()
    IQ.run()
    IQM = InboxQueueManager()
