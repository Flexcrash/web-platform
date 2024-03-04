
from flask import Blueprint, current_app, request
from persistence.user_data_access import UserDAO
from api.serialization import UserSchema

from views.authentication import jwt_required

# This blueprint handles the requests to the API Users Endpoint
users_api = Blueprint('users', __name__, url_prefix='/users')

# Marshmallow Integration
user_schema = UserSchema(exclude=["password"])
users_schema = UserSchema(many=True, exclude=["password"])

@users_api.route("/", methods=["GET"])
@jwt_required(admin_only=True)
def get_all_users():
    """
    Return all the users that the current user is allowed to see.
    Note: This endpoint is restricted to admin users authenticated via JWT token
    :return:
    """
    current_app.logger.debug("Query users using")
    user_dao = UserDAO()
    all_users = user_dao.get_all_users()
    return users_schema.dump(all_users)


@users_api.route("/", methods=["POST"])
@jwt_required(admin_only=True)
def create():
    """
    Create a new user given username, email, and password.
    The request fails if username and email are already in the DB.
    Note: This endpoint is restricted to admin users authenticated via JWT token
    Note: There's on check yet on password format
    :return:
    """
    data = dict(request.form)
    user_dao = UserDAO()
    try:
        # Create the new scenario and store it into the DB
        new_user = user_dao.create_new_user(data)
        return user_schema.dump(new_user), 201
    except Exception as e:  # TODO Too coarse
        # Check error message
        # ('UNIQUE constraint failed: User.email',)
        # if "UNIQUE constraint failed" in e.args[0]:
        #     # References: https://stackoverflow.com/questions/6123425/rest-response-code-for-invalid-data
        error_message = "An exception occurred while creating the new user."

        if type(e).__name__ == "IntegrityError":
            db_error = e.args[0]
            if "UNIQUE constraint failed" in db_error:
                # UNIQUE constraint failed: User.email
                duplicated_field = db_error.split()[-1]
                error_message = f"Duplicate {duplicated_field}"

        ## TODO Not sure if MariaDB generates the same exception

        return f"Cannot create the user. {error_message}", 422
        #
        # current_app.logger.error("Error occured while creating new user", e)
        # return "Server Error. Cannot create the user", 500

