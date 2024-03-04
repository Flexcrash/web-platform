import logging

from flask import current_app, session, redirect, url_for, render_template, request,Response
from flask import Blueprint

from views.authentication import authentication_api
# import jwt

from views.scenario import scenarios_api
from views.template import scenario_templates_api
from views.user import users_api
# from views.training import training_scenarios_api

# This blueprint handles the requests to the API layer
api_layer = Blueprint('api', __name__, url_prefix='/api')

# Nested blueprint to handle scenario related requests and token-based authentication
api_layer.register_blueprint(scenarios_api)
api_layer.register_blueprint(scenario_templates_api)
api_layer.register_blueprint(users_api)
api_layer.register_blueprint(authentication_api)


@api_layer.before_request
def log_request_info():
    # Reference: https://stackoverflow.com/questions/31637774/how-can-i-log-request-post-body-in-flask
    """ Log each and every request """
    current_app.logger.debug("API Request: {} at {}".format(request.method, request.url))



@api_layer.errorhandler(AssertionError)
def assertion_error_handler(error):
    validation_msg = f"{error}"
    current_app.logger.debug(f"INVALID REQUEST: {validation_msg}")
    return validation_msg, 422


@api_layer.errorhandler(Exception)
def special_exception_handler(exception):
    # Make sure that this is not an SQL Integrity Error before raising the 500
    if "IntegrityError" in type(exception).__name__:
        current_app.logger.debug("INVALID REQUEST Request: {}".format(exception))
        # Any violation of the DB rules is the result of a request that passed the initial validation (422)
        return 'Forbidden Request', 403
    else:
        current_app.logger.exception("Unhandled exception: {}".format(exception))
        return "Server Error", 500