import pytest

from persistence.user_data_access import UserDAO
from persistence.mixed_scenario_template_data_access import MixedTrafficScenarioTemplateDAO
from persistence.mixed_scenario_data_access import MixedTrafficScenarioDAO
from persistence.driver_data_access import DriverDAO
from persistence.vehicle_state_data_access import VehicleStateDAO

from model.user import User
from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate
from model.mixed_traffic_scenario import MixedTrafficScenario
from model.driver import Driver
from model.vehicle_state import VehicleState

def test_cannot_find_a_user(user_dao):
    """
    GIVEN An empty database
    WHEN User DAO looks for a non-existing user
    THEN User DAO returns None
    """
    user_id = 1
    user = user_dao.get_user_by_user_id(user_id)
    assert user is None


def test_create_a_user_from_dict(user_dao):
    username = "user1"
    email =  "user@email"
    password = "1234"

    data = {
        "username" : username,
        "email" : email,
        "password" : password
    }
    insert_user = user_dao.create_new_user(data)

    assert insert_user.username == username
    assert insert_user.email == email
    # TODO This really, should not be the case!
    assert insert_user.password == password


def test_get_all_users_returns_empty_list(user_dao):
    assert len(user_dao.get_all_users()) == 0


def test_get_all_users_returns_the_single_user(user_dao):
    user1 = User(username="username", email="email1@mail.com", password="foobar")
    user_dao.insert_and_get(user1)
    assert len(user_dao.get_all_users()) == 1


def test_get_user_by_username(user_dao):
    username="username"
    # Make sure we get the user with the ID
    user = user_dao.insert_and_get(User(username=username, email="email1@mail.com", password="foobar"))

    actual = user_dao.get_user_by_username(username)
    assert actual == user


def test_get_user_by_email(user_dao):
    username = "username"
    email = "email1@mail.com"
    # Make sure we get the user with the ID
    user = user_dao.insert_and_get(User(username=username, email=email, password="foobar"))

    actual = user_dao.get_user_by_email(email)
    assert actual == user



def test_user_dao_can_insert_with_user_id(user_dao):
    """
    GIVEN An empty database
    WHEN User DAO inserts a user into the DB
    THEN the DB accepts the new user and stores it with the given user id
    """
    user_id = 103
    user1 = User(user_id=user_id, username="username", email="email1@mail.com", password="foobar")
    the_user = user_dao.insert_and_get(user1)

    assert type(the_user) == User
    assert the_user.user_id == user_id


def test_user_dao_can_insert_without_user_id(user_dao):
    """
    GIVEN An empty database
    WHEN User DAO inserts a user into the DB
    THEN the DB accepts the new user and stores it
    """
    user1 = User(username="username", email="email1@mail.com", password="foobar")
    the_user = user_dao.insert_and_get(user1)
    assert type(the_user) == User
    # The test runs on a fresh db, so the first user should get id == 1 with autoincrement
    assert the_user.user_id == 1


def test_user_dao_prevents_duplicate_username(user_dao):
    """
    GIVEN An empty database
    WHEN User DAO inserts two users with same username
    THEN the DB reject the new second user and does not store it
    """

    from sqlalchemy.exc import IntegrityError

    duplicated_username = "name"
    user1 = User(username=duplicated_username, email="email1@mail.com", password="foobar")
    user_dao.insert(user1)
    # Create a second user with the same username
    user2 = User(username=duplicated_username, email="email2@mail.com", password="barfoo")
    # Expect that this user is rejected by the persistence
    with pytest.raises(IntegrityError):
        user_dao.insert(user2)


def test_user_dao_prevents_duplicate_email(user_dao):
    """
    GIVEN An empty database
    WHEN User DAO inserts two users with same email
    THEN the DB reject the new second user and does not store it
    """

    from sqlalchemy.exc import IntegrityError

    duplicated_email = "email1@mail.com"
    user1 = User(username="username1", email=duplicated_email, password="foobar")
    user_dao.insert(user1)
    # Create a second user with the same username
    user2 = User(username="username2", email=duplicated_email, password="barfoo")
    # Expect that this user is rejected by the persistence
    with pytest.raises(IntegrityError):
        user_dao.insert(user2)

def test_generate_token(user_dao):
    user1 = User(username="username1", email="email@email.com", password="foobar")
    user = user_dao.insert_and_get(user1)
    assert user_dao.generate_token(user.user_id)
