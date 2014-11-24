import os
CSRF_ENABLED = True
SECRET_KEY = os.environ.get('HIDEMAIL_SECRET_KEY')
basedir = os.path.abspath(os.path.dirname(__file__))
baseurl = os.environ.get('HIDEMAIL_BASE_URL', None)
SQLALCHEMY_DATABASE_URI = os.environ.get('HIDEMAIL_DATABASE_URL', os.environ.get('DATABASE_URL', None))
TWILIO_ACCOUNT_SID = os.environ.get('HIDEMAIL_TWILIO_SID')
TWILIO_AUTH_TOKEN = os.environ.get('HIDEMAIL_TWILIO_TOKEN')
