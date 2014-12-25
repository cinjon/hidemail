import app
import random
import datetime
from sqlalchemy.sql import func
import os
import redis
from rq import Worker, Queue, Connection

"""
The plan:
1. Set up a pool of workers
2. Set up two queues, GmailRequestsQueue (GRQ) and InboxManageQueue (IMQ)
3. GRQ is a queue of requests to be sent to gmail to manage inboxes.
    - It will fire when either it receives 100 requests (batch max for gmail api) or
    - It's been 10 seconds since the last time it fired and it has requests in the queue
    - Firing: a worker takes 100 requests off the queue, batches them into a multipart request, and sends to gmail api
4. IMQ is a queue of inboxes and a manager.
    - It is always firing, i.e. workers are handling items from it as soon as they are added.
    - A worker runs runWorker() on the object it receives in the Queue.
    - If the object is an inbox, then runWorker will:
        - Check to see that the current utc time coupled with the inbox's timezone offset falls outside of their timeblocks.
        - If true, and if earlier than <warmingTime> minutes before any timeblock's start or later than any timeblock's end, then add a 'hide all mail' request to the GRQ.
        - If true, and if within <warmingTime> minutes before a timeblock's start, then add a 'show all mail' request to the GRQ.
        - Regardless, stamp the inbox's last_checked timestamp with now.
    - If the object is a manager, then runWorker will:
        - Grab all inboxes with last_checked timestamp greater than <checkedPeriod> minutes before now.
        - Add all of these inboxes to the IMQ. Then add a manager to the IMQ.
"""

def run():
    pass
