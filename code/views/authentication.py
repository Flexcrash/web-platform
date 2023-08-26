from flask import current_app, session, redirect, url_for, render_template, request,Response
from flask import Blueprint
from persistence.data_access import MixedTrafficScenarioDAO,UserDAO
import jwt
from flask_httpauth import HTTPTokenAuth
# References:
#   - https://flask-httpauth.readthedocs.io/en/latest/
#   - https://realpython.com/token-based-authentication-with-flask/


#This blueprint handles the authentication requests
authentication_api = Blueprint('auth', __name__, url_prefix='/auth')

# The authentication agent based on tokens implemented by flask_httpauth
token_auth_engine = HTTPTokenAuth("Token")

# Storage of all the tokens to users mappings
tokens = {}


@authentication_api.route('/', methods=['POST'])
def login():
    """
    Authenticate the user and create a token for it. The token will be valid until logout or restart.
    """
    # current_app.logger.debug("login")
    # Authenticate the user and generate a token

    user_dao = UserDAO(current_app.config)

    try:
        username = request.form['username']
        password = request.form['password']
    except Exception:
        # The request is not complete, one of the two mandatory fields is missing
        return "Missing username or password", 422

    if not user_dao.verify_password(username, password):
        return 'Invalid username or password', 401

    # If the user is valid, configure the tokens
    authenticated_user = user_dao.get_user_by_username(username)

    # Create the unique token for the user. Note this allows for multiple tokens to be associated to the same user
    # TODO will this change every time?
    token = jwt.encode({'user_id': authenticated_user.user_id},
                       current_app.config["SECRET_KEY"],
                       algorithm='HS256')

    # Store the token into a temporary/cache. Probably there's something like current_app.
    tokens[token] = authenticated_user.user_id
    current_app.logger.debug(tokens)
    # Set the token in a secure cookie
    response = Response(token)
    # response.set_cookie('auth_token', token, httponly=True)
    # We created a new access token
    return response, 201


@token_auth_engine.verify_token
def verify_token(token):
    """
    Basic method to verify whether this token exists, hence the token bearer is a valid user
    :param token:
    :return:
    """
    # Make it possible to specify that login is disabled
    if 'LOGIN_DISABLED' in current_app.config and current_app.config['LOGIN_DISABLED']:
        return True
    if token in tokens:
        return tokens[token]


@authentication_api.route('/', methods=['DELETE'])
@token_auth_engine.login_required
def logout():
    """
    Delete the session token for the user if already authenticated
    """
    current_app.logger.debug("User {} is logging out.".format(token_auth_engine.current_user()))
    # Delete the token
    del tokens[token_auth_engine.get_auth()['token']]
    return "", 200


# Registering a new user is the same as creating new_user, this is already covered in #50 in the user.py view
# @authentication_api.route('/register_user', methods=['POST'])
# def register():
#     # Authenticate the user and generate a token
#     secret_key = 'my-secret-key'
#     userDao = UserDAO(current_app)
#     user = userDao.insert_and_get(request.form['username'],request.form['password'])
#     user_id = user["user_id"]
#     if user_id:
#         token = jwt.encode({'user_id': user_id}, secret_key, algorithm='HS256')
#         tokens[user_id] = token
#         current_app.logger.debug(tokens)
#         # Set the token in a secure cookie
#         response = Response('Registration successful')
#         response.set_cookie('auth_token', token, httponly=True)
#         return response
#
#     else:
#         return 'Invalid username or password', 401