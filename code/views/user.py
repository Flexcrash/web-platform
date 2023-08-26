from flask import Blueprint, current_app, request
from persistence.data_access import UserDAO
from model.user import User, UserSchema

# This blueprint handles the requests to the API Users Endpoint
users_api = Blueprint('users', __name__, url_prefix='/users')

# Marshmallow Integrationn
user_schema = UserSchema(exclude=["password"])
users_schema = UserSchema(many=True, exclude=["password"])



@users_api.route("/", methods=["GET"])
def get_all_users():
    """
    Return all the users that the current user is allowed to see
    :return:
    """
    current_app.logger.debug("Query users using")
    user_dao = UserDAO(current_app.config)
    all_users = user_dao.get_all_users()
    return users_schema.dump(all_users)


@users_api.route("/", methods=["POST"])
def create():
    data = dict(request.form)

    user_dao = UserDAO(current_app.config)
    try:
        # Create the new scenario and store it into the DB
        new_user = user_dao.create_new_user(data)
        return user_schema.dump(new_user), 201
    except Exception as e:  # TODO Too coarse
        # Check error message
        # ('UNIQUE constraint failed: User.email',)
        if "UNIQUE constraint failed" in e.args[0]:
            # References: https://stackoverflow.com/questions/6123425/rest-response-code-for-invalid-data
            return "Invalid request. Cannot create the user", 422

        current_app.logger.error("Error occured while creating new user", e)
        return "Server Error. Cannot create the user", 500

