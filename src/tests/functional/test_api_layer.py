import json
import glob, os

from flask import url_for

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

def initial_state_and_goal_area_generator(n_drivers):
    """ This method assume the simple, one road, test scenario so the goal area is always at the same point """
    rotation = 2.33
    speed_md = 1.0
    acceleration_m2s = 0.0
    # The road has one lane and it's slope in xy is -1
    scenario_slope = -1.1
    distance_x = 5
    min_x, min_y = 557.32551, -684.4076
    #
    goal_area_x, goal_area_y = 529.628465, -651.5852025

    for idx in range(0, n_drivers):
        position_x = min_x - idx * distance_x
        position_y = min_y + (scenario_slope * - idx * distance_x)

        # This was the internal representation of the complete state, now we provide only x, y and speed
        # yield [None, "ACTIVE", 0, None, scenario_id, position_x, position_y, rotation, speed_md,
        #        acceleration_m2s]
        yield ((position_x, position_y), speed_md), (goal_area_x, goal_area_y)


def _generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users, scenario_duration_in_seconds, scenario_id=None, preregistered_users=[]):

    state_gen = initial_state_and_goal_area_generator(n_avs + n_users)
    # Create the scenario using the API to trigger the AV
    scenario_data = {
        "scenario_id": scenario_id,  # enforce this to make the test predictable
        "template_id": scenario_template_id,
        "duration": scenario_duration_in_seconds,
        "creator_user_id": scenario_creator_user_id,
        "name": "test",
        "n_users": n_users,
        "n_avs": n_avs,
    }
    if len(preregistered_users) > 0:
        scenario_data["users"] = ",".join([str(user_id) for user_id in preregistered_users])

    # Initial States and Goal Regions
    scenario_data["id_array"] = ",".join([f"AV_{i}" for i in range(1, n_avs + 1)] + [f"UV_{i}" for i in range(1, n_users + 1 - len(preregistered_users))] + [f"U_{user_id}" for user_id in preregistered_users])

    # Add information for initial state and goal aread
    for i in range(1, n_avs + 1):
        initial_state, goal_area = next(state_gen)
        scenario_data[f"AV_{i}_x"] = initial_state[0][0]
        scenario_data[f"AV_{i}_y"] = initial_state[0][1]
        scenario_data[f"AV_{i}_speed"] = initial_state[1]
        scenario_data[f"AV_{i}_goal_x"] = goal_area[0]
        scenario_data[f"AV_{i}_goal_y"] = goal_area[1]

    for i in range(1, n_users + 1 - len(preregistered_users)):
        initial_state, goal_area = next(state_gen)
        scenario_data[f"UV_{i}_x"] = initial_state[0][0]
        scenario_data[f"UV_{i}_y"] = initial_state[0][1]
        scenario_data[f"UV_{i}_speed"] = initial_state[1]
        scenario_data[f"UV_{i}_goal_x"] = goal_area[0]
        scenario_data[f"UV_{i}_goal_y"] = goal_area[1]

    for user_id in preregistered_users:
        initial_state, goal_area = next(state_gen)
        scenario_data[f"U_{user_id}_x"] = initial_state[0][0]
        scenario_data[f"U_{user_id}_y"] = initial_state[0][1]
        scenario_data[f"U_{user_id}_speed"] = initial_state[1]
        scenario_data[f"U_{user_id}_goal_x"] = goal_area[0]
        scenario_data[f"U_{user_id}_goal_y"] = goal_area[1]

    return scenario_data


def test_authenticate_valid_user_result_in_200_and_a_token(flexcrash_test_app, user_dao):
    """
        GIVEN the flexcrash application configured for testing with one user
        WHEN the '/api/auth' API is requested (POST)
        THEN check that the response is valid 200 and the token is stored in the header
        """
    # Enable login for flask-login
    flexcrash_test_app.config["LOGIN_DISABLED"] = False

    # Create a user directly in the DB
    username = "foo"
    email = "foo@test.baz"
    password_in_clear = "1234"
    #
    user_dao.insert(User(user_id=1, username=username, email=email, password=password_in_clear))

    # Create a test client using the Flask application configured for testing
    with flexcrash_test_app.test_client() as test_client:
        # Login the user and grab the token
        response = test_client.post(url_for("api.auth.login"), data =
        {
            "email": email,
            "password": password_in_clear
        })
        # We expect a new token to be created
        assert response.status_code == 201
        # Token cannot be empty
        token = response.get_data(as_text=True)
        assert token

        # TODO Validate token format and expiry date

        # Logout does not exist anymore, since tokens have an expiry date
        # Use the token in the next request, i.e., Logout
        # response = test_client.delete(url_for("api.auth.logout"),
        #                               headers={'Authorization':
        #                                            'token {}'.format(token)})
        #
        # assert response.status_code == 200

        # Issuing another request while not authenticated, results in 401
        # response = test_client.delete(url_for("api.auth.logout"),
        #                               headers={'Authorization':
        #                                            'token {}'.format(token)})
        #
        # assert response.status_code == 401


def test_failed_authentication_results_in_401(flexcrash_test_app, user_dao):
    """
    GIVEN the flexcrash application configured for testing with one user
    WHEN the '/api/auth' API is requested (POST) with a wrong user
    THEN check that the response is 401
    """

    # Enable login for flask-login
    flexcrash_test_app.config["LOGIN_DISABLED"] = False

    # Create a test client using the Flask application configured for testing
    with flexcrash_test_app.test_client() as test_client:
        # Create a user directly in the DB
        username = "foo"
        email = "foo@test.baz"
        password_in_clear = "1234"
        #
        user_dao.insert(
            User(user_id=1, username=username, email=email, password=password_in_clear))

        # Login the user and grab the token
        response = test_client.post(url_for("api.auth.login"), data=
        {
            # For some reason, when we access thi field: test_user.username we start a transaction?!
            "email": email,
            "password": 4321
        })

        assert response.status_code == 401


def test_get_scenarios(flexcrash_test_app):
    """
    GIVEN the flexcrash application configured for testing with one user and no scenarios
    WHEN the '/api/scenarios' API is requested (GET)
    THEN check that the response is valid and returns an empty JSON
    """

    # Create a test client using the Flask application configured for testing
    with flexcrash_test_app.test_client() as test_client:
        # TODO We need to set the current user - TODO Use variables flexcrash_test_app["GET_SCENARIO_URL"] or something?
        response = test_client.get(url_for("api.scenarios.get_scenarios"))
        assert response.status_code == 200





def test_create_scenarios_with_invalid_inputs_result_in_422(flexcrash_test_app, user_dao,
                                                            mixed_traffic_scenario_template_dao, xml_scenario_template):
    """
    GIVEN the flexcrash application configured for testing (two users, one template)
    WHEN the '/api/scenarios' API is requested (POST) with invalid data
    THEN the response is an error code 422
    """

    # Setup the database
    user_1 = user_dao.insert_and_get(User(user_id=1, username="user1", email="foo1@bar.baz", password="12345"))
    user_2 = user_dao.insert_and_get(User(user_id=2, username="user2", email="foo2@bar.baz", password="12345"))
    mixed_traffic_scenario_template_dao.insert(
        MixedTrafficScenarioTemplate(
            template_id = 1,
            name = "name",
            description = "description",
            xml = xml_scenario_template))

    # Make the request to create a new scenario
    with flexcrash_test_app.test_client() as test_client:

        response = test_client.post(url_for("api.scenarios.create"),
                                    data = {
                                        # "name" : "scenario name", - Required param is missing
                                        "n_users" : 2,
                                        "n_avs" : 0,
                                        "template_id" : 1,
                                        "creator_user_id": 1,
                                        "users" : ",".join(["1", "2"])
                                    })
        assert response.status_code == 422

        response = test_client.post(url_for("api.scenarios.create"),
                                    data = {
                                        "name" : "scenario name",
                                        "n_users" : -2, # Negative values are not allowed
                                        "n_avs" : 0,
                                        "template_id" : 1,
                                        "creator_user_id": 1,
                                        "users" : ",".join(["1", "2"])
                                    })
        assert response.status_code == 422

        response = test_client.post(url_for("api.scenarios.create"),
                                    data={
                                        "name": "scenario name",
                                        "n_users": 2,
                                        "n_avs": 0,
                                        "template_id": 10, # Not existing reference
                                        "creator_user_id": 1,
                                        "users": ",".join(["1", "2"])
                                    })
        assert response.status_code == 422

        response = test_client.post(url_for("api.scenarios.create"),
                                    data={
                                        "name": "scenario name",
                                        "n_users": 2,
                                        "n_avs": 0,
                                        "template_id": 10,
                                        "creator_user_id": 1,
                                        "users": ",".join(["100"]) # Not existing references in pre-assigned users
                                    })
        assert response.status_code == 422


def test_get_scenario_templates_do_not_carry_xml_field(flexcrash_test_app, script_loc,
                                                       mixed_traffic_scenario_template_dao, xml_scenario_template):
    """
    GIVEN the flexcrash application configured with one scenario template
    WHEN the '/api/templates' API is requested (GET)
    THEN check that the response is valid and returns the scenario template without the xml
    """

    # Setup the Database

    mixed_traffic_scenario_template_dao.insert_and_get(
        MixedTrafficScenarioTemplate(name="xml",
                                     description="xml",
                                     xml=xml_scenario_template))

    # Create a test client using the Flask application configured for testing
    with flexcrash_test_app.test_client() as test_client:
        response = test_client.get(url_for("api.templates.get_scenario_templates"))

        assert response.status_code == 200
        assert b'"xml":' not in response.data


def test_get_scenario_templates_xml(flexcrash_test_app, mixed_traffic_scenario_template_dao, xml_scenario_template):
    """
    GIVEN the flexcrash application configured with one scenario template with template_id 1 and given XML
    WHEN the '/api/templates/1/xml' API is requested (GET)
    THEN the response is valid and returns the scenario template xml
    """

    # Setup the Database

    template_id = 123
    mixed_traffic_scenario_template_dao.insert_and_get(
        MixedTrafficScenarioTemplate(template_id=template_id,
                                     name="xml",
                                     description="xml",
                                     xml=xml_scenario_template)
    )

    # Create a test client using the Flask application configured for testing
    with flexcrash_test_app.test_client() as test_client:
        response = test_client.get(
            url_for("api.templates.get_scenario_template_xml", template_id=template_id))

        assert response.status_code == 200
        assert xml_scenario_template in response.data.decode("utf-8")


def test_add_user_as_driver(flexcrash_test_app, user_dao, mixed_traffic_scenario_dao,
                            mixed_traffic_scenario_template_dao, xml_scenario_template):
    """
    GIVEN the flexcrash application configured for testing (two users, one template, one scenario)
    WHEN the '/api/scenarios/<scenario_id>/drivers' API is requested (POST) with an existing user
    THEN the response is 204
    """

    # Create users
    creator = user_dao.insert_and_get(User(user_id=1, username="creator", email="foo1@bar.baz", password="12345"))
    driver = user_dao.insert_and_get(User(user_id=2, username="driver", email="foo2@bar.baz", password="12345"))
    # Create template
    template = mixed_traffic_scenario_template_dao.insert_and_get(
        MixedTrafficScenarioTemplate(template_id=1,
                                     name="xml",
                                     description="xml",
                                     xml=xml_scenario_template)
    )

    # Create Scenario
    scenario = mixed_traffic_scenario_dao.insert_and_get(
        MixedTrafficScenario(scenario_id=1,
                             name="scenario_name",
                             description="scenario_description",
                             created_by=creator.user_id,
                             max_players=5, n_avs=1, n_users=4,
                             status="WAITING",
                             template_id=template.template_id,
                             duration=10)
    )

    non_existing_scenario_id=123

    # Make the request to add driver as driver
    with flexcrash_test_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create_driver", scenario_id=scenario.scenario_id),
                                    data = {"user_id" : driver.user_id})
        assert response.status_code == 204

        # Trying to add the same user once again results in a 422
        response = test_client.post(url_for("api.scenarios.create_driver", scenario_id=scenario.scenario_id),
                                    data={"user_id": driver.user_id})
        assert response.status_code == 422

        # Trying to add the user to a non-existing scenario results in a 404
        response = test_client.post(url_for("api.scenarios.create_driver", scenario_id=non_existing_scenario_id),
                                    data={"user_id": driver.user_id})
        assert response.status_code == 404

def test_deleting_a_scenario_clears_everything(mocker, flexcrash_test_app_with_a_scenario_template_and_given_users,
    random_vehicle_state_data_at_times):
    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12
    user_3_id = 13
    user_4_id = 14

    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 0
    n_users = 2
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = [user_1_id, user_2_id]

    scenario_data = _generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [scenario_creator_user_id, user_1_id, user_2_id, user_3_id, user_4_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code == 201

        # Assert images are there
        scenario_image_folder = flask_app.config["SCENARIO_IMAGES_FOLDER"]
        # List images and check that they are there
        expected_scenario_image_files = [ f for f in glob.glob(os.path.join(scenario_image_folder, "scenario_{}_*".format(scenario_id)))]
        # TODO Inaccurate, but this is not the unit under test
        assert len(expected_scenario_image_files) > 0

        # Delete the scenario
        response = test_client.delete(url_for("api.scenarios.delete", scenario_id=scenario_id))
        assert response.status_code == 200

        # Assert images are not there anymore
        actual_scenario_image_files = [f for f in
                                glob.glob(os.path.join(scenario_image_folder, "scenario_{}_*".format(scenario_id)))]
        assert len(actual_scenario_image_files) == 0

        scenario_dao = MixedTrafficScenarioDAO(flask_app.config)
        # Assert no scenario is there
        assert scenario_dao.get_scenario_by_scenario_id(scenario_id) is None

        # Assert no drivers related to this scenario is there
        driver_dao = DriverDAO(flask_app.config)
        registered_drivers = driver_dao.get_all_drivers(flask_app.config, scenario_id=scenario_id)
        assert len(registered_drivers) == 0
        # TODO Assert the users do not have state
        vehicle_state_dao = VehicleStateDAO(flask_app.config, scenario_dao)
        # TODO Assert that the users are still there?
        all_vehicle_states = vehicle_state_dao.get_vehicle_states_by_scenario_id(scenario_id)
        assert len(all_vehicle_states) == 0