from marshmallow import Schema, fields, post_load

# Import the "singleton" db object for creating the model
from persistence.database import db

# Import the custom type Password
from persistence.custom_types import PasswordType

# Make sure we can combine db-stored attributes with transient ones
# See: https://docs.sqlalchemy.org/en/13/orm/constructors.html
from sqlalchemy import orm

class User(db.Model):

    __tablename__ = 'User'

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    is_admin = db.Column(db.Boolean, unique=False, default=False)

    username = db.Column(db.String(250), nullable=False, unique=True)
    email = db.Column(db.String(250), nullable=False, unique=True)
    password = db.Column(PasswordType, nullable=False, unique=False)

    owns = db.relationship('MixedTrafficScenario', back_populates='owner', uselist=True, lazy=True)
    drives = db.relationship('Driver', back_populates='user', uselist=True, lazy=True)

    @orm.reconstructor
    def init_on_load(self):
        self.is_authenticated = False   # Needed by Flask-Login
        self.is_active = False          # Needed by Flask-Login
        self.is_anonymous = False       # Needed by Flask-Login
        self.personal_jwt_token = None  # Needed for the API integration

    # According to https://variable-scope.com/posts/storing-and-verifying-passwords-with-sqlalchemy
    # The @validates decorator is optional but ensures that the password value is converted to
    # a PasswordHash as soon as it is assigned, and does not require committing the session before it’s visible.
    # This does move the expense of the hashing forward to the moment of assignment rather than the moment of flushing.
    # It also means there’s never a plaintext value stored on the user object, which means it can’t accidentally
    # leak, which is definitely a bonus.
    @orm.validates('password')
    def _validate_password(self, key, password):
        return getattr(type(self), key).type.validator(password)

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