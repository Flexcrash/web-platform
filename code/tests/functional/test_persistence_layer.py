# Reference: tmp_path fixture https://docs.pytest.org/en/7.1.x/how-to/tmp_path.html

import pytest
from persistence.database import Database
from persistence.data_access import User, MixedTrafficScenario, MixedTrafficScenarioTemplate, VehicleState

def assert_mixed_traffic_scenario(mixed_traffic_scenario, expected_mixed_traffic_scenario):
    """
    Utility method to compare the two objects attributes except their id

    :param mixed_traffic_scenario:
    :param expected_mixed_traffic_scenario:
    :return:
    """
    assert mixed_traffic_scenario.name == expected_mixed_traffic_scenario.name
    assert mixed_traffic_scenario.description == expected_mixed_traffic_scenario.description
    assert mixed_traffic_scenario.created_by == expected_mixed_traffic_scenario.created_by
    assert mixed_traffic_scenario.status == expected_mixed_traffic_scenario.status
    # TODO This is an approximation. We should definne the _eq_ method of ScenarioTemplate
    assert mixed_traffic_scenario.scenario_template.template_id == expected_mixed_traffic_scenario.scenario_template.template_id


def test_cannot_find_a_user(user_dao):
    """
    GIVEN An empty database
    WHEN User DAO looks for a non-existing user
    THEN User DAO returns None
    """
    user_id = 1
    user = user_dao.get_user_by_user_id(user_id)
    assert user is None


def test_user_dao_can_insert_with_user_id(user_dao):
    """
    GIVEN An empty database
    WHEN User DAO inserts a user into the DB
    THEN the DB accepts the new user and stores it with the given user id
    """
    user_id = 103
    user1 = User(user_id, "username", "email1@mail.com", "foobar")
    the_user = user_dao.insert_and_get(user1)

    assert type(the_user) == User
    assert the_user.user_id == user_id


def test_user_dao_prevents_duplicate_username(user_dao):
    from sqlite3 import IntegrityError
    username = "name"
    user1 = User(None, username, "email1@mail.com", "foobar")
    user_dao.insert(user1)
    # Create a second user with the same username
    user2 = User(None, username, "email2@mail.com", "foobar")
    # Expect that this user is rejected by the persistence
    # sqlite3.IntegrityError: UNIQUE constraint failed: User.username
    with pytest.raises(IntegrityError):
        user_dao.insert(user2)


def test_mixed_traffic_scenario_dao_returns_an_empty_list_for_nonexisting_user(mixed_traffic_scenario_dao):
    """
    GIVEN an empty database
    WHEN Scenario DAO looks for scenario of a (non-existing) user
    THEN return an empty list
    """

    scenarios = mixed_traffic_scenario_dao.get_all_scenarios_created_by_user(1)

    assert len(scenarios) == 0


def test_mixed_traffic_scenario_dao_returns_an_empty_list(user_dao, mixed_traffic_scenario_dao, xml_scenario_template):
    """
    GIVEN an empty database and one inserted user
    WHEN Scenario DAO looks for scenario of that user
    THEN return an empty list
    """

    # Insert one user in the DB
    user = User(1, "username", "email1@mail.com", "foobar")
    user_dao.insert(user)

    scenarios = mixed_traffic_scenario_dao.get_all_scenarios_created_by_user(1)

    assert len(scenarios) == 0


def test_mixed_traffic_scenario_dao_returns_the_scenario_as_list(user_dao,
                                                                 mixed_traffic_scenario_dao,
                                                                 mixed_traffic_scenario_template_dao,
                                                                 xml_scenario_template):
    """
    GIVEN an empty database, one user, one template, and one scenario created by that user
    WHEN Scenario DAO looks for scenarios created by that user
    THEN return a list that contain the scenario
    """
    # Insert one user in the DB
    user = user_dao.insert_and_get(User(1, "username", "email1@mail.com", "foobar"))

    # Insert one scenario template in the DB
    scenario_template = mixed_traffic_scenario_template_dao.insert_and_get(
        MixedTrafficScenarioTemplate(1, "template_name", "template_description", xml_scenario_template))

    # Insert the scenario and get the new instance
    expected_mixed_traffic_scenario =  mixed_traffic_scenario_dao.insert_and_get(
        MixedTrafficScenario(1, "name", "description", user, 5, "WAITING", scenario_template, 10))

    # Do the query
    actual_mixed_traffic_scenarios = mixed_traffic_scenario_dao.get_all_scenarios_created_by_user(user.user_id)

    assert len(actual_mixed_traffic_scenarios) == 1
    actual_mixed_traffic_scenario = actual_mixed_traffic_scenarios[0]
    # How to establish equality using __eq__ but this makes the objects unhashable, basically they are not immutable
    assert actual_mixed_traffic_scenario == expected_mixed_traffic_scenario


def test_mixed_traffic_scenario_dao_returns_scenario_where_user_drives(user_dao,
                                                                 mixed_traffic_scenario_dao,
                                                                 mixed_traffic_scenario_template_dao,
                                                                 xml_scenario_template):
    """
    GIVEN an empty database, one user, one template, and one scenario created in which that user drives
    WHEN Scenario DAO looks for scenarios in which that user drives
    THEN return a list that contain that scenario
    """
    # Insert one user in the DB
    user = user_dao.insert_and_get(User(1, "username", "email1@mail.com", "foobar"))

    # Insert one scenario template in the DB
    scenario_template = mixed_traffic_scenario_template_dao.insert_and_get(
        MixedTrafficScenarioTemplate(1, "template_name", "template_description", xml_scenario_template))

    # Insert the scenario and get the new instance
    expected_mixed_traffic_scenario = mixed_traffic_scenario_dao.insert_and_get(
        MixedTrafficScenario(1, "name", "description", user, 5, "WAITING", scenario_template, 10))

    # Insert the second user and make it a driver
    driver = user_dao.insert_and_get(User(2, "username 2", "email2@mail.com", "foobar"))

    mixed_traffic_scenario_dao.add_user_to_scenario(driver, expected_mixed_traffic_scenario)

    # Do the query
    actual_mixed_traffic_scenarios = mixed_traffic_scenario_dao.get_all_scenarios_where_user_is_driving(driver.user_id)

    assert len(actual_mixed_traffic_scenarios) == 1
    actual_mixed_traffic_scenario = actual_mixed_traffic_scenarios[0]

    # How to establish equality?
    assert actual_mixed_traffic_scenario == expected_mixed_traffic_scenario


def test_mixed_traffic_scenario_dao_prevents_adding_the_same_user_twice(user_dao,
                                                                 mixed_traffic_scenario_dao,
                                                                 mixed_traffic_scenario_template_dao,
                                                                 xml_scenario_template):
    """
    GIVEN a database with two users, one template, and one scenario
    WHEN Scenario DAO adds twice the same user for the scenario
    THEN an exception is raised
    """
    # Insert one user in the DB
    creator = user_dao.insert_and_get(User(1, "username", "email1@mail.com", "foobar"))

    # Insert one scenario template in the DB
    scenario_template = mixed_traffic_scenario_template_dao.insert_and_get(
        MixedTrafficScenarioTemplate(1, "template_name", "template_description", xml_scenario_template))

    # Insert the scenario and get the new instance
    expected_mixed_traffic_scenario = mixed_traffic_scenario_dao.insert_and_get(
        MixedTrafficScenario(1, "name", "description", creator, 5, "WAITING", scenario_template, 10))

    # Add the creator also as driver
    mixed_traffic_scenario_dao.add_user_to_scenario(creator, expected_mixed_traffic_scenario)

    with pytest.raises(Exception):
        # Adding the creator as driver AGAIN
        mixed_traffic_scenario_dao.add_user_to_scenario(creator, expected_mixed_traffic_scenario)

    # But adding another user it works
    driver = user_dao.insert_and_get(User(2, "username 2", "email2@mail.com", "foobar"))


    mixed_traffic_scenario_dao.add_user_to_scenario(driver, expected_mixed_traffic_scenario)





def test_mixed_traffic_scenario_dao_returns_the_inserted_scenario_without_scenario_id(user_dao,
                                                                 mixed_traffic_scenario_dao,
                                                                 mixed_traffic_scenario_template_dao,
                                                                 xml_scenario_template):
    """
    GIVEN a database with a user and a scenario template
    WHEN Scenario DAO adds a new scenario (without scenario_id)
    THEN returns an object representing it
    """
    # Insert one user in the DB
    creator = user_dao.insert_and_get(User(1, "username", "email1@mail.com", "foobar"))

    # Insert one scenario template in the DB
    scenario_template = mixed_traffic_scenario_template_dao.insert_and_get(
        MixedTrafficScenarioTemplate(1, "template_name", "template_description", xml_scenario_template))

    # Insert the scenario without the scenario_id and get the new instance
    mixed_traffic_scenario = MixedTrafficScenario(None, "name", "description", creator, 5,
                                                  "WAITING", scenario_template, 10)

    expected_mixed_traffic_scenario = mixed_traffic_scenario_dao.insert_and_get(mixed_traffic_scenario)

    # Assert all the attributes but the ID match
    assert_mixed_traffic_scenario(mixed_traffic_scenario, expected_mixed_traffic_scenario)

    # Insert another scenario
    mixed_traffic_scenario = MixedTrafficScenario(None, "name2", "description2", creator, 5, "WAITING",
                                                  scenario_template, 10)

    expected_mixed_traffic_scenario = mixed_traffic_scenario_dao.insert_and_get(mixed_traffic_scenario)

    # Assert all the attributes but the ID match
    assert_mixed_traffic_scenario(mixed_traffic_scenario, expected_mixed_traffic_scenario)


def test_mixed_traffic_scenario_dao_returns_the_inserted_scenario_with_scenario_id(user_dao,
                                                                 mixed_traffic_scenario_dao,
                                                                 mixed_traffic_scenario_template_dao,
                                                                 xml_scenario_template):
    """
    GIVEN a database with a user and a template
    WHEN Scenario DAO adds a new scenario (without scenario_id)
    THEN returns an object representing it
    """
    # Insert one user in the DB
    creator = user_dao.insert_and_get(User(1, "username", "email1@mail.com", "foobar"))

    # Insert one scenario template in the DB
    scenario_template = mixed_traffic_scenario_template_dao.insert_and_get(
        MixedTrafficScenarioTemplate(1, "template_name", "template_description", xml_scenario_template))

    # Create the scenario with the scenario_id and get the new instance
    expected_scenario_id = 103
    mixed_traffic_scenario = MixedTrafficScenario(expected_scenario_id, "name", "description", creator, 5, "WAITING",
                                                  scenario_template, 10)
    expected_mixed_traffic_scenario = mixed_traffic_scenario_dao.insert_and_get(mixed_traffic_scenario)

    assert mixed_traffic_scenario.scenario_id == expected_mixed_traffic_scenario.scenario_id
    assert_mixed_traffic_scenario(mixed_traffic_scenario, expected_mixed_traffic_scenario)

    # Insert another scenario
    mixed_traffic_scenario = MixedTrafficScenario(80, "name2", "description2", creator, 5, "WAITING",
                                                  scenario_template, 10)

    expected_mixed_traffic_scenario = mixed_traffic_scenario_dao.insert_and_get(mixed_traffic_scenario)

    assert mixed_traffic_scenario.scenario_id == expected_mixed_traffic_scenario.scenario_id
    assert_mixed_traffic_scenario(mixed_traffic_scenario, expected_mixed_traffic_scenario)


def test_template_scenario_dao_returns_an_empty_list(mixed_traffic_scenario_template_dao):
    """
    GIVEN an empty database
    WHEN Template DAO looks for all templates
    THEN return an empty list
    """

    # Get all templates
    templates = mixed_traffic_scenario_template_dao.get_templates()

    assert templates is not None
    assert len(templates) == 0


def test_template_scenario_dao_returns_the_template_as_list(mixed_traffic_scenario_template_dao,
                                                            xml_scenario_template):
    """
    GIVEN an empty database and one scenario template with given id
    WHEN Template DAO looks for template scenario
    THEN return a list that contains the template scenario
    """
    # Insert one template in the DB
    template_id = 10
    name = "Fancy Template"
    description="A fancy template"
    scenario_template = MixedTrafficScenarioTemplate(template_id, name, description, xml_scenario_template)
    mixed_traffic_scenario_template_dao.insert(scenario_template)

    # Get all the templates
    templates = mixed_traffic_scenario_template_dao.get_templates()

    assert templates is not None
    assert len(templates) == 1

    assert templates[0].template_id == template_id
    assert templates[0].name == name
    assert templates[0].description == description
    assert templates[0].xml == xml_scenario_template


def test_template_scenario_dao_returns_the_template_as_list_without_giving_template_id(mixed_traffic_scenario_template_dao,
                                                                                       xml_scenario_template):
    """
    GIVEN an empty database and one scenario template without giving any id
    WHEN Template DAO looks for template scenario
    THEN return a list that contains that template scenario with a not null id
    """

    # Insert one template in the DB
    template_id = None
    name = "Fancy Template"
    description="A fancy template"

    scenario_template = MixedTrafficScenarioTemplate(template_id, name, description, xml_scenario_template)
    mixed_traffic_scenario_template_dao.insert(scenario_template)

    # Get all the templates
    templates = mixed_traffic_scenario_template_dao.get_templates()

    assert templates is not None
    assert len(templates) == 1

    assert templates[0].template_id is not None
    assert templates[0].name == name
    assert templates[0].description == description
    assert templates[0].xml == xml_scenario_template


def test_template_scenario_dao_returns_the_template_by_template_id(mixed_traffic_scenario_template_dao,
                                                                   xml_scenario_template):
    """
    GIVEN an empty database and one inserted template scenario
    WHEN Template DAO looks for that template scenario by id
    THEN return the template scenario
    """
    
    # Insert one template in the DB
    template_id = 54
    name = "Fancy Template"
    description="A fancy template"
    scenario_template = MixedTrafficScenarioTemplate(template_id, name, description, xml_scenario_template)
    mixed_traffic_scenario_template_dao.insert(scenario_template)

    # Get all the templates
    template = mixed_traffic_scenario_template_dao.get_template_by_id(template_id)

    assert template is not None

    assert template.template_id is not None
    assert template.name == name
    assert template.description == description
    assert template.xml == xml_scenario_template


def test_template_scenario_dao_returns_none_with_empty_database(mixed_traffic_scenario_template_dao, tmp_path):
    """
    GIVEN an empty database
    WHEN Template DAO looks for that a template scenario by id
    THEN return None
    """

    template_id = 54

    # Get all the templates
    template = mixed_traffic_scenario_template_dao.get_template_by_id(template_id)

    assert template is None


def test_violating_sql_constraints_on_foreing_keys_created_by(mixed_traffic_scenario_dao,
                                                              mixed_traffic_scenario_template_dao,
                                                              xml_scenario_template):
    """
    GIVEN a database without any user
    WHEN Scenario DAO adds a new scenario
    THEN Scenario DAO triggers an error because the user does not exist
    """

    # Insert the Scenario Template
    scenario_template_id = 123
    scenario_template = mixed_traffic_scenario_template_dao.insert_and_get(MixedTrafficScenarioTemplate(scenario_template_id,
                                                                      "template name", "template description",
                                                                      xml_scenario_template))

    non_existing_user_id = 1
    non_existing_user = User(non_existing_user_id, "fake", "fake@fake.com", "1234")

    # Try to insert a scenario
    mixed_traffic_scenario = MixedTrafficScenario(103, "name", "description", non_existing_user,
                                                  5, "WAITING", scenario_template, 10)

    # Insert the scenario fails
    with pytest.raises(Exception) as exc_info:
        mixed_traffic_scenario_dao.insert_and_get(mixed_traffic_scenario)
    # Assert it failed for the right reason
    assert "FOREIGN KEY constraint failed" in str(exc_info.value.args)


def test_violating_sql_constraints_on_foreing_keys_template_id(user_dao,
                                                               mixed_traffic_scenario_dao,
                                                               xml_scenario_template):
    """
    GIVEN a database without any scenario template
    WHEN Scenario DAO adds a new scenario
    THEN Scenario DAO triggers an error because the scenario template does not exist
    """

    # Add the user
    user_id = 234
    user = user_dao.insert_and_get(User(user_id, "foo", "foo@email.boo", "12234"))

    non_existing_template = MixedTrafficScenarioTemplate(1234, "fake", "boo", xml_scenario_template)

    # Try to insert a scenario
    mixed_traffic_scenario = MixedTrafficScenario(103, "name", "description", user, 5,
                                                  "WAITING", non_existing_template, 10)

    # Insert the scenario fails
    with pytest.raises(Exception) as exc_info:
        mixed_traffic_scenario_dao.insert_and_get(mixed_traffic_scenario)
    # Assert it failed for the right reason
    assert "FOREIGN KEY constraint failed" in str(exc_info.value.args)


def test_violating_sql_constraints_on_foreing_keys_user_id(user_dao,
                                                           mixed_traffic_scenario_dao,
                                                           mixed_traffic_scenario_template_dao,
                                                           xml_scenario_template):
    """
    GIVEN a database with only the scenario creator user
    WHEN Driver DAO adds a new driver (with a non-existing user)
    THEN Driver DAO triggers an error because the user does not exist
    """

    # Add the creator user
    creator_user_id = 234
    creator_user = user_dao.insert_and_get(User(creator_user_id, "foo", "foo@email.boo", "12234"))

    # Add the scenario template
    scenario_template_id = 123
    scenario_template = mixed_traffic_scenario_template_dao.insert_and_get(MixedTrafficScenarioTemplate(scenario_template_id,
                                                                      "template name", "template description",
                                                                      xml_scenario_template))

    # Add the scenario
    scenario_id = 345
    mixed_traffic_scenario = MixedTrafficScenario(scenario_id, "name", "description", creator_user, 5,
                                                  "WAITING", scenario_template, 10)

    non_existing_user_id = 1
    non_existing_user = User(non_existing_user_id, "foo1", "foo1@email.boo", "12234")

    # Insert the driver fails
    with pytest.raises(Exception) as exc_info:
        mixed_traffic_scenario_dao.add_user_to_scenario(non_existing_user, mixed_traffic_scenario)
    # Assert it failed for the right reason
    assert "FOREIGN KEY constraint failed" in str(exc_info.value.args)


def test_violating_sql_constraints_on_foreing_keys_scenario_id(user_dao,
                                                           mixed_traffic_scenario_dao,
                                                           mixed_traffic_scenario_template_dao,
                                                           xml_scenario_template):
    """
    GIVEN a database without any scenario
    WHEN Driver DAO adds a new driver
    THEN Driver DAO triggers an error because the scenario does not exist
    """

    # Add the user
    user_id = 234
    user = user_dao.insert_and_get(User(user_id, "foo", "foo@email.boo", "12234"))

    # Add the template
    scenario_template_id = 123
    scenario_template = mixed_traffic_scenario_template_dao.insert_and_get(MixedTrafficScenarioTemplate(scenario_template_id,
                                                                      "template name", "template description",
                                                                      xml_scenario_template))

    # Do not add the scenario
    scenario_id = 345
    mixed_traffic_scenario = MixedTrafficScenario(scenario_id, "name", "description", user, 5,
                                                  "WAITING", scenario_template, 10)

    # Insert the driver fails
    with pytest.raises(Exception) as exc_info:
        mixed_traffic_scenario_dao.add_user_to_scenario(user, mixed_traffic_scenario)
    # Assert it failed for the right reason
    assert "FOREIGN KEY constraint failed" in str(exc_info.value.args)


def test_violating_sql_constraints_on_foreing_keys_user_id_in_vehicle_state_table(user_dao,
                                                                                  mixed_traffic_scenario_dao,
                                                                                  mixed_traffic_scenario_template_dao,
                                                                                  vehicle_state_dao,
                                                                                  xml_scenario_template):
    """
    GIVEN a database with a user, scenario_template, scenario, driver
    WHEN Vehicle State DAO adds a new state for a user that is not a driver in that scenario
    THEN Vehicle State DAO triggers an error because the user is not a driver in that scenario
    """
    # Add the user, that is not a driver
    non_driver_user_id = 234
    non_driver_user = user_dao.insert_and_get(User(non_driver_user_id, "foo", "foo@email.boo", "12234"))


    # Add the template
    scenario_template_id = 123
    scenario_template = mixed_traffic_scenario_template_dao.insert_and_get(MixedTrafficScenarioTemplate(scenario_template_id,
                                                                      "template name", "template description",
                                                                      xml_scenario_template))

    # Add the scenario
    scenario_id = 345
    mixed_traffic_scenario = MixedTrafficScenario(scenario_id, "name", "description", non_driver_user, 5,
                                                  "WAITING", scenario_template, 10)
    mixed_traffic_scenario_dao.insert_and_get(mixed_traffic_scenario)


    # Try to add a state for an existing user but not driver
    vehicle_state_id = 1
    status = "ACTIVE"
    timestamp = 0
    user_id = non_driver_user_id
    scenario_id,
    position_x = 0.0
    position_y = 0.0
    rotation = 0.0
    speed_ms = 0.0
    acceleration_m2s = 0.0

    vehicle_state = VehicleState(vehicle_state_id, status, timestamp, user_id, scenario_id, position_x, position_y, rotation, speed_ms, acceleration_m2s)

    # Insert the vehicle state for that driver fails
    with pytest.raises(Exception) as exc_info:
        vehicle_state_dao.insert(vehicle_state)
    # Assert it failed for the right reason
    assert "FOREIGN KEY constraint failed" in str(exc_info.value.args)