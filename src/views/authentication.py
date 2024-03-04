from datetime import datetime, timedelta
from functools import wraps

from flask import current_app, session, redirect, url_for, render_template, request, Response, jsonify
from flask import Blueprint

from persistence.user_data_access import UserDAO

import jwt
from configuration.config import TOKEN_EXPIRATION_IN_SECONDS
from flask_httpauth import HTTPTokenAuth
# References:
#   - https://flask-httpauth.readthedocs.io/en/latest/
#   - https://realpython.com/token-based-authentication-with-flask/

# This blueprint handles API authentication requests
authentication_api = Blueprint('auth', __name__, url_prefix='/auth')

# The authentication agent based on tokens implemented by flask_httpauth
# token_auth_engine = HTTPTokenAuth("Token")

# Storage of all the tokens to users mappings
# TODO: This should be moved somewhere else?
tokens = {}


# Direct method to avoid API call for internal uses.
def create_the_token(user):
    user_dao = UserDAO()
    return user_dao.generate_token(user.user_id, is_primary=False)


@authentication_api.route('/', methods=['POST'])
def login():
    """
    Authenticate the user and create a JWT token for it.
    The JWT token will be valid until logout or the restart of the app.
    """
    user_dao = UserDAO()

    if 'email' not in request.form:
        return 'Invalid email or password', 401

    # Check if the user exists
    email = request.form['email']

    user = user_dao.get_user_by_email(email)
    if user is None:
        return 'Invalid email or password', 401

    # Check if the password or the password-hash match
    password = None

    if 'password' in request.form:
        password = request.form['password']
        if not user_dao.verify_password(email, password):
            return 'Invalid email or password', 401
    elif password is None and 'password-hash' in request.form:
        password = request.form['password-hash']
        # If the user is valid, configure the tokens
        if not user.password.hash == password:
            return 'Invalid email or password', 401
    else:
        return 'Invalid email or password', 401


    # Create the unique token for the user. Note this allows for multiple tokens to be associated to the same user
    # TODO will this change every time?
    token = create_the_token(user)

    # TODO: not sure this is necessary
    # Store the token into a temporary/cache. Probably there's something like current_app.
    # tokens[token] = user.user_id
    # current_app.logger.debug(tokens)
    # Set the token in a secure cookie?
    response = Response(token)
    # response.set_cookie('auth_token', token, httponly=True)
    # We created a new access token
    return response, 201


# @token_auth_engine.verify_token
# def verify_token(token):
#     """
#     Basic method to verify whether this token exists, hence the token bearer is a valid user
#     :param token:
#     :return:
#     """
#     # Make it possible to specify that login is disabled
#     if 'LOGIN_DISABLED' in current_app.config and current_app.config['LOGIN_DISABLED']:
#         return True
#     if token in tokens:
#         return tokens[token]


# TODO Is this necessary? Yes, but only when we allow temporary tokens for users and AV!
# @authentication_api.route('/', methods=['DELETE'])
# # @token_auth_engine.login_required
# def logout():
#     """
#     Delete the session token for the user if already authenticated
#     """
#     current_app.logger.debug("User {} is logging out.".format(token_auth_engine.current_user()))
#     # Delete the token
#     del tokens[token_auth_engine.get_auth()['token']]
#     return "", 200

# TODO: Isn't this exactly the same logic implemented in the @token_auth_engine.login_required decorator?
def jwt_required(admin_only=False, get_user=False):
    '''
        This is a decorator to secure our api endpoints with jwt tokens.
        admin_only - defines if only admin users will be able to access this endpoint
        get_user - defines if decorator should pass user id of user who send the request
    '''
    def decorator(view):
        @wraps(view)
        def wrapper(*args,**kwargs):

            # For testing, we disable authentication
            if 'LOGIN_DISABLED' in current_app.config and current_app.config['LOGIN_DISABLED']:
                return view(*args, **kwargs)

            try:
                # Try to access the token. If this is not there, an exception triggers
                token = request.headers['Authorization']
                # Try to decode the token. If invalid or expired, an expection triggers
                data = jwt.decode(token, current_app.config['SECRET_KEY'],algorithms=['HS256'])
                # At this point the token is valid syntactically.
                user_id = int(data['user_id'])
                userdao = UserDAO()
                user = userdao.get_user_by_user_id(user_id)
                # If the token does not correspond to ay existing users, we cannot authenticate the request
                if not user:
                    return "Unauthorized: Authorization info are invalid",401
                # If the request requires higher permission, we check whether the user is an admin
                # We respond with Forbidden otherwise (not 401!). See:
                #   https://stackoverflow.com/questions/3297048/403-forbidden-vs-401-unauthorized-http-responses
                if not user.is_admin and admin_only:
                    return "Forbidden: Only admins can perform this operation", 403
            except KeyError:
                return "Unauthorized: Authorization info are missing", 401
            except jwt.ExpiredSignatureError:
                return "Unauthorized: Token is expired",401
            except jwt.InvalidTokenError:
                return "Unauthorized: Token is invalid",401

            # This was created to yield user_id to the decorated view, as we now store it in db, we dont need this for now
            if get_user:
                kwargs['user_id'] = data['user_id']

            return view(*args,**kwargs)
        return wrapper
    return decorator
