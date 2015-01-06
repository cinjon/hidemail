import stripe
stripe.api_key = app.config.STRIPE_LIVE_SK

def stripe_decorator(f):
    def error_wrap(**kwargs):
        try:
            f(**kwargs)
        except stripe.error.CardError, e:
            body = e.json_body
            logger.debug(body)
            return jsonify(
                success=False,
                msg=body.get('error', {}).get('message', 'stripe_card_declined'))
        except stripe.error.InvalidRequestError, e:
            return jsonify(success=False, msg='stripe_invalid_parameters')
        except stripe.error.AuthenticationError, e:
            return jsonify(success=False, msg='stripe_auth_fail')
        except stripe.error.APIConnectionError, e:
            return jsonify(success=False, msg='stripe_network_fail')
        except stripe.error.StripeError, e:
            return jsonify(success=False, msg='stripe_failed')
        except Exception, e:
            return jsonify(success=False, msg='stripe_maybe_not')

class StripeHandler(object):
    @classmethod
    def __init__(cls):
        pass

    @stripe_decorator
    @staticmethod
    def create_customer(card=None, description=None, plan=None):
        stripe_customer = stripe.Customer.create(
            card=card, description=description, plan=plan)
        return jsonify(success=True, id=stripe_customer.id)

    @stripe_decorator
    @staticmethod
    def charge(amount=None, currency=None, stripe_customer_id=None):
        charge = stripe.Charge.create(amount=amount, currency=currency,
                                      customer=stripe_customer_id)
        return jsonify(success=True)


