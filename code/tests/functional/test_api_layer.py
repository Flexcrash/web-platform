import json
import glob, os

from flask import url_for
from flexcrash import create_app


# Import the test fixture

def test_authenticate_valid_user_result_in_200_and_a_token(flexcrash_test_app, user_dao):
    """
        GIVEN the flexcrash application configured for testing with one user
        WHEN the '/api/auth' API is requested (POST)
        THEN check that the response is valid 200 and the token is stored in the header
        """
    # Enable login for flask-login
    flexcrash_test_app.config["LOGIN_DISABLED"] = False

    from model.user import User

    # Create a test client using the Flask application configured for testing
    with flexcrash_test_app.test_client() as test_client:

        # Create a user directly in the DB
        username = "foo"
        password_in_clear = "1234"
        test_user = user_dao.insert_and_get(User(1, username, "foo@test.baz", password_in_clear))

        # Login the user and grab the token
        response = test_client.post(url_for("api.auth.login"), data =
        {
            "username": username,
            "password": password_in_clear
        })
        # We expect a new token to be created
        assert response.status_code == 201
        # Token cannot be empty
        token = response.get_data(as_text=True)
        assert token

        # Use the token in the next request, i.e., Logout
        response = test_client.delete(url_for("api.auth.logout"),
                                      headers={'Authorization':
                                                   'token {}'.format(token)})

        assert response.status_code == 200

        # Issuing another request while not authenticated, results in 401
        response = test_client.delete(url_for("api.auth.logout"),
                                      headers={'Authorization':
                                                   'token {}'.format(token)})

        assert response.status_code == 401


def test_failed_authentication_results_in_401(flexcrash_test_app, user_dao):
    """
    GIVEN the flexcrash application configured for testing with one user
    WHEN the '/api/auth' API is requested (POST) with a wrong user
    THEN check that the response is 401
    """

    from model.user import User

    # Create a test client using the Flask application configured for testing
    with flexcrash_test_app.test_client() as test_client:
        # Create a user directly in the DB
        test_user = User(1, "foo", "foo@test.baz", "1234")
        user_dao.insert(test_user)

        # Login the user and grab the token
        response = test_client.post(url_for("api.auth.login"), data=
        {
            "username": test_user.username,
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


def test_create_scenarios_with_existing_users(flexcrash_test_app_with_a_scenario_template_and_given_users):

    """
    GIVEN the flexcrash application configured for testing (two users, one template)
    WHEN the '/api/scenarios' API is requested (POST) with pre-assigned users
    THEN the response is 201 (Created) and returns a scenario as JSON
    """
    
    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12

    scenario_template_id = 1

    n_users = 2
    n_avs = 0
    duration = 5
    pre_assigned_users = ",".join([str(u_id) for u_id in [user_1_id, user_2_id]])

    flexcrash_test_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id, user_2_id],
        scenario_template_id)

    # Make the request to create a new scenario with the preassigned users
    with flexcrash_test_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_id = 1
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": duration,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs,
            "users": pre_assigned_users
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Assert that this scenario is (already) ACTIVE
        assert response.status_code == 201

        # Assert that the JSON is a valid scenario (this might be an problem if nested resources have missing fields?
        created_scenario_as_dict = json.loads(response.data.decode("utf-8"))
        assert created_scenario_as_dict["created_by"]["user_id"] == user_1_id
        assert created_scenario_as_dict["status"] == "ACTIVE"
        assert len(created_scenario_as_dict["drivers"]) == 2
        # assert user_1 in created_scenario.drivers and user_2 in created_scenario.drivers


def test_create_scenarios_with_invalid_inputs_result_in_422(flexcrash_test_app, user_dao,
                                                            mixed_traffic_scenario_template_dao, xml_scenario_template):
    """
    GIVEN the flexcrash application configured for testing (two users, one template)
    WHEN the '/api/scenarios' API is requested (POST) with invalid data
    THEN the response is an error code 422
    """

    from model.user import User
    from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate
    from persistence.data_access import UserDAO, MixedTrafficScenarioTemplateDAO

    # Setup the database
    user_1 = user_dao.insert_and_get(User(1, "user1", "foo1@bar.baz", "12345"))
    user_2 = user_dao.insert_and_get(User(2, "user2", "foo2@bar.baz", "12345"))
    mixed_traffic_scenario_template_dao.insert(MixedTrafficScenarioTemplate(1, "name", "description", xml_scenario_template))

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
    from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate

    mixed_traffic_scenario_template_dao.insert_and_get(MixedTrafficScenarioTemplate(None, "xml", "xml", xml_scenario_template))

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
    from persistence.data_access import MixedTrafficScenarioTemplateDAO
    from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate

    template_id = 123
    mixed_traffic_scenario_template_dao.insert_and_get(MixedTrafficScenarioTemplate(template_id, "xml", "xml", xml_scenario_template))

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

    from model.user import User
    from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate
    from model.mixed_traffic_scenario import MixedTrafficScenario

    # Create users
    creator = user_dao.insert_and_get(User(1, "creator", "foo1@bar.baz", "12345"))
    driver = user_dao.insert_and_get(User(2, "driver", "foo2@bar.baz", "12345"))
    # Create template
    template = mixed_traffic_scenario_template_dao.insert_and_get(MixedTrafficScenarioTemplate(1, "name", "description", xml_scenario_template))
    # Create Scenario
    scenario = mixed_traffic_scenario_dao.insert_and_get(MixedTrafficScenario(1, "scenario_name", "scenario_description",
                                                     creator, 5, "WAITING", template, 10))

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

def test_deleting_a_scenario_clears_everything(flexcrash_test_app_with_a_scenario_template_and_given_users,
    random_vehicle_state_data_at_times):

    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12

    scenario_template_id = 1

    n_users = 2
    n_avs = 0
    scenario_duration_in_seconds = 0.3  # Keep it short

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id, user_2_id], scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger any AV and the generation of images
        # Pre-Register the users
        scenario_id = 1
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": scenario_duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs,
            "users": ",".join([str(id) for id in [user_1_id, user_2_id]])
            }
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


        from persistence.data_access import MixedTrafficScenarioDAO, VehicleStateDAO, get_all_drivers
        scenario_dao = MixedTrafficScenarioDAO(flask_app.config)
        # Assert no scenario is there
        assert scenario_dao.get_scenario_by_scenario_id(scenario_id) is None
        # Assert no drivers related to this scenario is there
        registered_drivers = get_all_drivers(flask_app.config, scenario_id=scenario_id)
        assert len(registered_drivers) == 0
        # TODO Assert the users do not have state
        vehicle_state_dao = VehicleStateDAO(flask_app.config)
        # TODO Assert that the users are still there?
        all_vehicle_states = vehicle_state_dao.get_vehicle_states_by_scenario_id(scenario_id)
        assert len(all_vehicle_states) == 0