from marshmallow import Schema, fields, post_load


class User:

    def __init__(self, user_id, username, email, password):
        """
        The constructor takes all the paramters. We delegate the issue of creating unique ids to the persistence layer
        :param user_id:
        :param username:
        :param email:
        :param password:
        """
        self.user_id = user_id
        self.username = username
        self.email = email
        self.password = password

        self.is_authenticated = False   # Needed by Flask-Login
        self.is_active = False          # Needed by Flask-Login
        self.is_anonymous = False       # Needed by Flask-Login

    def get_id(self):                   # Needed by Flask-Login
        return self.user_id

    def __str__(self):
        return str(self.user_id) + " " + str(self.username)

    def __eq__(self, other):
        if not isinstance(other, User):
            # Trivially False
            return False

        return self.user_id == other.user_id and \
               self.username == other.username and \
               self.email == other.email and \
               self.password == other.password

# TODO: Not yet used, part of a WIP refactoring
# class Driver:
#
#     def __init__(self, user, scenario):
#         self.user = user
#         self.scenario = scenario
#         #
#         self.goal_region_as_rectangle = None
#         self.initial_state = None

class UserSchema(Schema):
    """ This class is used to serialize/validate Python objects using Marshmallow """
    user_id = fields.Integer()
    username = fields.String()
    email = fields.String()
    password = fields.String()

    @post_load
    def make_user(self, data, **kwargs):
        return User(**data)

