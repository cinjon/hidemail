import app
import stripe
from flask import jsonify
stripe.api_key = app.stripe_sk
logger = app.flask_app.logger

class StripeHandler(object):
    def stripe_decorator(f):
        def error_wrap(cls, **kwargs):
            try:
                return f(cls, **kwargs)
            except stripe.error.CardError, e:
                body = e.json_body
                logger.debug(body)
                errorType = body.get('error', {}).get('message', 'stripe_card_declined')
                return {'success':False, 'errorType':errorType}
            except stripe.error.InvalidRequestError, e:
                return {'success':False, 'errorType':'stripe_invalid_parameters'}
            except stripe.error.AuthenticationError, e:
                return {'success':False, 'errorType':'stripe_auth_fail'}
            except stripe.error.APIConnectionError, e:
                return {'success':False, 'errorType':'stripe_network_fail'}
            except stripe.error.StripeError, e:
                return {'success':False, 'errorType':'stripe_failed'}
            except Exception, e:
                return {'success':False, 'errorType':'stripe_maybe_not'}
        return error_wrap

    @stripe_decorator
    def create_customer(cls, card=None, description=None, plan=None):
        stripe_customer = stripe.Customer.create(
            card=card, description=description, plan=plan)
        return {'success':True, 'id':stripe_customer.id}

    @stripe_decorator
    def charge(cls, amount=None, currency=None, stripe_customer_id=None):
        charge = stripe.Charge.create(amount=amount, currency=currency,
                                      customer=stripe_customer_id)
        return {'success':True}


