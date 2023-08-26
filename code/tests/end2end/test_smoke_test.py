import json

from flask import url_for
from model.vehicle_state import VehicleStateSchema

# References:
#   https://flask.palletsprojects.com/en/2.2.x/testing/#faking-resources-and-context
#   https://stackoverflow.com/questions/35684436/testing-file-uploads-in-flask
#   https://blog.filestack.com/api/step-step-guide-curl-upload-file/#:~:text=To%20execute%20a%20CURL%20file,send%20it%20to%20the%20server.
#   https://stackoverflow.com/questions/47216204/how-do-i-upload-multiple-files-using-the-flask-test-client
#   https://stackoverflow.com/questions/34504757/get-pytest-to-look-within-the-base-directory-of-the-testing-script


def test_end2end_api_scenario_evolution(xml_scenario_template_as_file, flexcrash_test_app,flexcrash_user_generator):
    """
    GIVEN a flexcrash test app configured with an empty database
    DO
    1. Create two new users (scenario_creator, scenario_driver)
    2. Create a scenario template named "test" by uploading
    3. Create a scenario named "first scenario" from template "test"
    4. Make scenario_driver join the scenario
    5. Make scenario_driver make some moves in the scenario
    6. Make scenario_driver make all the moves and end the scenario
    :return:
    """

    # Disable login for flask-login
    # flask_app.config['LOGIN_DISABLED'] = True
    # flask_app.login_manager.init_app(flask_app)

    # Create a test client using the Flask application configured for testing
    with flexcrash_test_app.test_client() as test_client:
        # 1. Create two new users (scenario_creator, scenario_driver)
        # curl -X POST http://localhost:5000/api/users/ -H "Content-Type: application/x-www-form-urlencoded" -d "user_id=1&username=scenario_creator&email=creator@flexcrash.eu&password=1234"
        scenario_creator, scenario_creator_data = next(flexcrash_user_generator)
        response = test_client.post(url_for("api.users.create"), data = scenario_creator_data)
        assert response.status_code == 201

        # curl -X POST http://localhost:5000/api/users/ -H "Content-Type: application/x-www-form-urlencoded" -d "user_id=2&username=scenario_driver&email=driver@flexcrash.eu&password=1234"
        scenario_driver, scenario_driver_data = next(flexcrash_user_generator)
        response = test_client.post(url_for("api.users.create"), data=scenario_driver_data)
        assert response.status_code == 201

        #     2. Create a scenario template named "test" and pass the content of an existing xml file to it
        # curl -X POST
        #       -H "Content-Type: application/x-www-form-urlencoded"
        #       -F name=test -F xml=@ftests/scenario_templates/template.xml
        #           http://localhost:5000/api/templates/
        #
        with open(xml_scenario_template_as_file, "rb") as file:
            scenario_template_data = {"name": "test",
                                      "template_id": 1 # this is only for testing
                                      }
            scenario_template_data = {key: str(value) for key, value in scenario_template_data.items()}
            scenario_template_data['file'] = (file, 'template.xml')

            response = test_client.post(url_for('api.templates.create'),
                                        content_type='multipart/form-data',
                                        data=scenario_template_data)
            # Probably we should NOT Send the entire XML Back, instead, we should link it to a "static" file and provide the linkn to it
            assert response.status_code == 201

        # 3. Create a scenario named "first scenario" from template "test"
        # curl -X POST http://localhost:5000/api/scenarios/ -H "Content-Type: application/x-www-form-urlencoded" -d "scenario_id=1&template_id=1&creator_user_id=1&name=test&n_users=1&n_avs=1&duration=10"
        # curl -X POST http://localhost:5000/api/scenarios/ -H "Content-Type: application/x-www-form-urlencoded" -d "template_id=1&creator_user_id=1&name=test&n_users=0&n_avs=1&duration=10"
        scenario_data = {
            "scenario_id": 1,
            "template_id": 1,
            "duration": 5,
            "creator_user_id": scenario_creator.user_id,
            "name": "test",
            "n_users": 1,
            "n_avs": 0
        }

        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)

        # The scenario was created but it is waiting for a user to join, so it is not yet ready to go
        assert response.status_code == 202

        # 4. Scenario_driver joins the "scenario"
        # curl -X POST http://localhost:5000/api/scenarios/1/drivers/
        #       -H "Content-Type: application/x-www-form-urlencoded"
        #       -d "user_id=1"
        driver_data = {
            "user_id": scenario_driver.user_id
        }
        response = test_client.post(url_for("api.scenarios.create_driver", scenario_id=1), data=driver_data)
        # We expect a no content for this one
        assert response.status_code == 204

        # 6. Get all the states
        response = test_client.get(url_for("api.scenarios.get_vehicle_states",
                                           scenario_id=1,
                                           driver_id=scenario_driver.user_id))

        assert response.status_code == 200
        vehicle_state_schema = VehicleStateSchema(many=True)
        # We need to transform the string into a JSON object
        vehicle_states = vehicle_state_schema.load(json.loads(response.data.decode("utf-8")))

        # Assert only the initial state is active
        for vehicle_state in vehicle_states:
            if vehicle_state.timestamp == 0:
                assert vehicle_state.status == "ACTIVE"
            else:
                assert vehicle_state.status == "PENDING"

        # 5. scenario_driver put some new states (duration is 5)
        # curl -X PUT http://localhost:5000/api/scenarios/1/drivers/2/states/ -H "Content-Type: application/x-www-form-urlencoded" -d "timestamps=1,2&positions_x=10,25&positions_y=10.0,10.0&rotations=0.0,12.0&speeds_ms=5.0,5.5"
        states_data = {
            "timestamps": ",".join(["1",  "2",  "3"]), # Cannot be 0 as the initial state is set directly by the server
            "positions_x": ",".join(["10",  "25",  "35"]),
            "positions_y": ",".join(["10",  "10",  "10"]),
            "rotations": ",".join(["0.0",  "0.0",  "0.0"]),
            "speeds_ms": ",".join(["1",  "2",  "3"]),
            "accelerations_m2s": ",".join(["0.0",  "0.0",  "0.0"])
        }

        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=1,
                                           driver_id=scenario_driver.user_id),
                                   data=states_data)
        # Those states must be accepted and needs to trigger all the AV
        assert response.status_code == 204

        # TODO  Assert that status 0, 1, 2, 3 are NOT PENDING Anymore
        response = test_client.get(url_for("api.scenarios.get_vehicle_states",
                                           scenario_id=1,
                                           driver_id=scenario_driver.user_id))
        assert response.status_code == 200

        # We need to transform the string into a JSON object
        vehicle_states = vehicle_state_schema.load(json.loads(response.data.decode("utf-8")))
        # Assert only the states with timestampe < 4 are active
        for vehicle_state in vehicle_states:
            if 0 <= vehicle_state.timestamp <= 3:
                assert vehicle_state.status == "ACTIVE"
            else:
                assert vehicle_state.status == "PENDING"
