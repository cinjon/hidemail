import app
import os
from flask import send_from_directory, make_response, request, redirect
from sqlalchemy.sql.expression import func, select
from flask.ext.mobility.decorators import mobile_template
import random

# special file handlers and error handlers
@app.flask_app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.flask_app.root_path, 'static'), 'img/favicon.ico')

@app.flask_app.errorhandler(404)
def page_not_found(e):
    return redirect('/')

# routing for basic pages (pass routing onto the Angular app)
@app.flask_app.route('/')
@app.flask_app.route('/about')
def basic_pages():
    return make_response(open('app/public/template/index.html').read())

# @app.flask_app.route('/google34d3fe92d155a2aa.html')
# def google_verification(**kwargs):
#     return make_response(open('app/public/template/google34d3fe92d155a2aa.html').read())
