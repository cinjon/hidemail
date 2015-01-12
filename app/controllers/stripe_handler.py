import app
import stripe
from flask import jsonify
stripe.api_key = app.stripe_sk
logger = app.flask_app.logger

error_messages = {
  'stripe_invalid_parameters':"Sorry. There was an error processing your card. Please try again.",
  'stripe_auth_fail':"Sorry. We had trouble connecting to Stripe. Please try again.",
  'stripe_network_fail':"Sorry. We had trouble connecting to Stripe's network. Please try again.",
  'stripe_failed':"Sorry. There was an error handling your card. Please try again.",
  'stripe_maybe_not':"Sorry. We hit an error completing the payment. Please try again."
}

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
                return {'success':False, 'errorType':error_messages['stripe_invalid_parameters']}
            except stripe.error.AuthenticationError, e:
                return {'success':False, 'errorType':error_messages['stripe_auth_fail']}
            except stripe.error.APIConnectionError, e:
                return {'success':False, 'errorType':error_messages['stripe_network_fail']}
            except stripe.error.StripeError, e:
                return {'success':False, 'errorType':error_messages['stripe_failed']}
            except Exception, e:
                return {'success':False, 'errorType':error_messages['stripe_maybe_not']}
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


