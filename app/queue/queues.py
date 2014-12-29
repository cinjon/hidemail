import app
import random
import datetime
from sqlalchemy.sql import func
import os
import redis
from rq import Worker, Queue as rqQueue, Connection
from Queue import Queue
from time import sleep

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
checkedPeriod = 20 # seconds .. 20
maxQueueTime = 10 # seconds
iqmWaitSeconds  = 10 # seconds .. 5
logger = app.flask_app.logger

class InboxQueueManager(object):
    @classmethod
    def get_queue(cls):
        return InboxQueue().get_queue()

    @classmethod
    def enqueue(cls, data=None):
        if not data:
            data = cls
        cls.get_queue().enqueue(app.models.manage_inbox_queue, data)

    @classmethod
    def runWorker(cls):
        sleep(iqmWaitSeconds)
        queue = cls.get_queue()
        now = app.utility.get_time()
        last_checked_param = now - datetime.timedelta(0, checkedPeriod)
        for customer in app.models.Customer.query.filter(app.models.Customer.last_checked_time < last_checked_param):
            customer.set_last_checked_time(now)
            customer.runWorker()
        cls.enqueue()
IQM = InboxQueueManager()

class InboxQueue(object):
    listen = ['high', 'default']
    conn = redis.from_url(app.config.REDIS_URL)

    @classmethod
    def get_queue(cls):
        return rqQueue(connection=cls.conn)

    @classmethod
    def run(cls):
        with Connection(cls.conn):
            worker = Worker(map(rqQueue, cls.listen))
            IQM.enqueue()
            worker.work()
IQ = InboxQueue()

if __name__ == '__main__':
    IQ.run()
