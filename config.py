import os
debug = 'DYNO' not in os.environ
CSRF_ENABLED = True
SECRET_KEY = os.environ.get('HIDEMAIL_SECRET_KEY')
basedir = os.path.abspath(os.path.dirname(__file__))
baseurl = os.environ.get('HIDEMAIL_BASE_URL', None)

warmingTime = int(os.environ.get('HIDEMAIL_WARMING_TIME'))
checkedPeriod = int(os.environ.get('HIDEMAIL_CHECK_PERIOD'))
iqmWaitSeconds = int(os.environ.get('HIDEMAIL_IQM_WAIT'))
batchRequestLimit = int(os.environ.get('HIDEMAIL_BATCH_LIMIT'))

SQLALCHEMY_DATABASE_URI = os.environ.get('HIDEMAIL_DATABASE_URL', os.environ.get('DATABASE_URL', None))
REDIS_URL = os.environ.get('HIDEMAIL_REDIS_URL', os.environ.get('REDISTOGO_URL', None))
GOOGLE_SECRET = os.environ.get('HIDEMAIL_GOOGLE_SECRET')
GOOGLE_ID     = os.environ.get('HIDEMAIL_GOOGLE_ID')
GOOGLE_API_KEY = os.environ.get('HIDEMAIL_GOOGLE_API_KEY')
STRIPE_TEST_SK = os.environ.get('HIDEMAIL_STRIPE_TEST_SK')
STRIPE_TEST_PK = os.environ.get('HIDEMAIL_STRIPE_TEST_PK')
STRIPE_LIVE_SK = os.environ.get('HIDEMAIL_STRIPE_LIVE_SK')
STRIPE_LIVE_PK = os.environ.get('HIDEMAIL_STRIPE_LIVE_PK')
TWILIO_ACCOUNT_SID = os.environ.get('HIDEMAIL_TWILIO_SID')
TWILIO_AUTH_TOKEN = os.environ.get('HIDEMAIL_TWILIO_TOKEN')

