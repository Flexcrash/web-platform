from typing import List, Optional

import jwt
from flask import current_app
from model.user import User

# The reference to the DB
from persistence.database import db
from persistence.utils import inject_where_statement_using_attributes, check_password_hash
from datetime import datetime, timedelta
from configuration.config import TOKEN_EXPIRATION_IN_SECONDS

from model.tokens import UserToken


class UserDAO:

    def create_new_user(self, data: dict):
        """
        Create and store a new user from request data, i.e., a dictionary ?
        TODO Consider merging this to insert?
        TODO What's the difference with register_user?
        :param data:
        :return:
        """
        user = User(
            user_id=data["user_id"] if "user_id" in data else None,
            username=data["username"],
            email=data["email"],
            password=data["password"]
        )
        return self.insert_and_get(user)

    def make_admin_user(self, user_id: int):
        # Get the user object, set the is_admin
        stmt = db.select(User)
        kwargs = {
            User.user_id.name: user_id
        }
        updated_stmt = inject_where_statement_using_attributes(stmt, User, **kwargs)

        user: User
        user = db.session.execute(updated_stmt).first()[0]
        user.is_admin = True
        db.session.commit()

    def make_regular_user(self, user_id):
        # Get the user object, set the is_admin
        stmt = db.select(User)
        kwargs = {
            User.user_id.name: user_id
        }
        updated_stmt = inject_where_statement_using_attributes(stmt, User, **kwargs)

        user: User
        user = db.session.execute(updated_stmt).first()[0]
        user.is_admin = False
        db.session.commit()

    def insert(self, user: User):
        """
        Try to insert a user into the database. Fails if a user with the same username is already there.
        :param user:
        :return:
        :raise: Exception
        """
        self.insert_and_get(user)

    def insert_and_get(self, user: User, nested=False):
        """
        Try to insert a user into the database and get the updated object in return.
        Fails if a user with the same username is already there.
        """
        # TODO Fix the transactionns
        # db.session.begin(nested=nested)
        db.session.add(user)
        db.session.commit()
        return user

    def _get_users_by_attributes(self, nested=False, **kwargs) -> List[User]:
        """
        Return a collection of user objects matching the given attributes or an empty list
        :return:
        """
        # Create the basic SELECT for User
        stmt = db.select(User)
        # Add the necessary WHERE clauses
        updated_stmt = inject_where_statement_using_attributes(stmt, User, **kwargs)
        # Execute the statement
        # db.session.begin(nested=nested) -> TODO For some reason this is already started
        users = db.session.execute(updated_stmt)
        # TODO: do we need ? What if this is part of a larger transaction?
        # db.session.commit()
        # Concretize the list as we expect that later
        return list(users.scalars())

    def get_all_users(self):
        kwargs = {}
        return self._get_users_by_attributes(**kwargs)

    def get_user_by_user_id(self, user_id: int, nested=False) -> Optional[User]:
        kwargs = {"user_id": user_id}

        users = self._get_users_by_attributes(nested, **kwargs)
        assert len(users) == 0 or len(users) == 1
        return users[0] if len(users) == 1 else None

    def get_user_by_username(self, username: str) -> Optional[User]:
        kwargs = {"username": username}
        users = self._get_users_by_attributes(**kwargs)
        assert len(users) == 0 or len(users) == 1
        return users[0] if len(users) == 1 else None

    def get_user_by_email(self, email: str) -> Optional[User]:
        kwargs = {"email": email}
        users = self._get_users_by_attributes(**kwargs)
        assert len(users) == 0 or len(users) == 1
        return users[0] if len(users) == 1 else None

    # TODO: Deprecated. Instead do Scenario.drivers after having loaded the entire scenario in one query
    def get_all_users_driving_in_a_scenario(self, scenario_id):
        raise AssertionError("DEPRECATED METHOD")
        # """
        # Return a collection of users that are driving in the scenario
        # :param scenario_id
        # :return:
        # """
        # connection = sqlite3.connect(self.database_name)
        # try:
        #     cursor = connection.cursor()
        #     cursor.execute("""
        #                 SELECT U.user_id, U.username, U.email, U.password
        #                 FROM User as U INNER JOIN Driver as D
        #                 ON U.user_id = D.user_id
        #                 WHERE D.scenario_id = ?""",
        #                    (scenario_id,)
        #                    )
        #     return [User(*tokens) for tokens in cursor.fetchall()]
        # finally:
        #     connection.close()

    def verify_password(self, email_or_username, password):
        user_by_email = self.get_user_by_email(email_or_username)
        if user_by_email is not None:
            # See https://variable-scope.com/posts/storing-and-verifying-passwords-with-sqlalchemy
            return user_by_email.password == password

        user_by_username = self.get_user_by_username(email_or_username)
        if user_by_username is not None:
            return user_by_username.password == password

        return False

    def is_admin(self, user_id) -> bool:
        user_by_id = self.get_user_by_user_id(user_id)
        if user_by_id is None:
            return False
        return user_by_id.is_admin

    def generate_token(self, user_id, is_primary=False) -> str:
        """
        This will fail if the AV is executed by more than one process at the same time, which is EXACTLY what happens in production
        :param user_id:
        :param is_primary:
        :return:
        """
        if is_primary:
            assert not self.get_primary_token(user_id), "Primary token already exists"

        user = self.get_user_by_user_id(user_id)
        # This already contains the current time
        expiration = datetime.utcnow() + timedelta(seconds=TOKEN_EXPIRATION_IN_SECONDS)
        token = jwt.encode(
            {
                'user_id': user.user_id,
                'exp': expiration
            },
            current_app.config["SECRET_KEY"],
            algorithm='HS256')

        try:
            user_token = UserToken(user_id=user.user_id, token=token, expiration=expiration, is_primary=is_primary)
            db.session.add(user_token)
            db.session.commit()
        except Exception as ex_info:
            # Make sure we roll back this exception so the db remain usable..
            db.session.rollback()
            raise AssertionError("Failed to generate the token")
        return token

    def get_user_tokens(self, user_id) -> List[str]:
        stmt = db.select(UserToken.token).where(UserToken.user_id == user_id).where(UserToken.expiration > datetime.utcnow())
        tokens = db.session.execute(stmt)
        return list(tokens.scalars())

    def get_primary_token(self, user_id) -> Optional[str]:
        token_row = db.session.query(UserToken.token).filter(UserToken.user_id == user_id,
                                                             UserToken.expiration > datetime.utcnow(),
                                                             UserToken.is_primary == True).first()
        if token_row:
            return token_row.token
        return None
