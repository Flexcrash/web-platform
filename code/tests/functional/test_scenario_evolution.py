# Define the fixtures for the following test cases
import json
import os

import pytest
from flask import url_for

from itertools import cycle
from model.user import User
from model.vehicle_state import VehicleState
from persistence.data_access import UserDAO

def initial_state_generator(n_drivers, scenario_id):
    # Fixed
    rotation = 2.33
    speed_md = 1.0
    acceleration_m2s = 0.0
    # The road has one lane and it's slope in xy is -1
    scenario_slope = -1.1
    distance_x = 5
    min_x, min_y = 557.32551, -684.4076
    for idx in range(0, n_drivers):
        position_x = min_x - idx * distance_x
        position_y = min_y + (scenario_slope * - idx * distance_x)

        yield [None, "ACTIVE", 0, None, scenario_id, position_x, position_y, rotation, speed_md,
               acceleration_m2s]


def trajectory_generator(n_drivers, scenario_id):
    # Plan a trajectory for the human drivers
    pass


def test_evolve_scenario_with_one_av(flexcrash_test_app_with_a_scenario_template_and_given_users):

    # Create the app with the factory method
    scenario_creator_user_id = 1
    scenario_template_id = 1

    n_users = 0
    n_avs = 1

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id],
                                                                            scenario_template_id)

    scenario_duration_in_seconds = 0.5

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_data = {
            "template_id": scenario_template_id,
            "duration": scenario_duration_in_seconds,
            "creator_user_id": scenario_creator_user_id,
            "name": "test",
            "n_users": n_users,
            "n_avs": n_avs
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # At this point, the scenario should be COMPLETED since there's only one AV that automatically triggers
        assert response.status_code == 200
        # Assert the status of this scenario is DONE (since the drivers automatically drives till the end)

        mixed_scenario_as_dictionary = json.loads(response.data.decode("utf-8"))
        assert mixed_scenario_as_dictionary["status"] == "DONE"


def test_evolve_scenario_with_two_avs(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    # Create the app with the factory method
    scenario_creator_user_id = 1
    scenario_template_id = 1

    scenario_duration_in_seconds = 0.4

    n_users = 0
    n_avs = 2

    scenario_id = 1

    # Instantiate ONE generator for this test
    state_gen = initial_state_generator(n_avs + n_users, scenario_id)

    # Configure the mocking such that the call to get_vehicle_states_by_scenario_id_at_timestamp returns the expected values
    mock_function = mocker.patch('controller.controller.MixedTrafficScenarioGenerator.generate_random_initial_state')

    def mocked_generate_random_initial_state(driver, goal_region_as_rectangle):
        initial_state = next(state_gen)
        initial_state[3] = driver.user_id
        # Inject the user id
        return tuple(initial_state)

    mock_function.side_effect = mocked_generate_random_initial_state

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id],
                                                                            scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": scenario_duration_in_seconds,
            "creator_user_id": scenario_creator_user_id,
            "name": "test",
            "n_users": n_users,
            "n_avs": n_avs
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # At this point, the scenario should be completed since there's only AVs that automatically triggers
        assert response.status_code == 200

        mixed_scenario_as_dictionary = json.loads(response.data.decode("utf-8"))
        assert mixed_scenario_as_dictionary["status"] == "DONE"

        scenario_id = mixed_scenario_as_dictionary["scenario_id"]
        driver_ids = [d["user_id"] for d in mixed_scenario_as_dictionary["drivers"]]

        # Assert the Images/HTML
        image_folder = flask_app.config["IMAGES_FOLDER"]
        expected_files = []

        # Include the initial state !
        step_duration = 0.1
        scenario_steps = int(scenario_duration_in_seconds / step_duration)

        # # NOTE: This assumes that the scenario has at least that many states better check how many states are there
        # for timestamp in range(0, scenario_steps+1):
        #     for driver_id in driver_ids:
        #         expected_files.append("scenario_{}_timestamp_{}_driver_{}.embeddable.html".format(scenario_id, timestamp, driver_id))
        # actual_files = []
        # # List the images in the folder, check that all of the exists
        # # Iterate directory
        # for path in os.listdir(image_folder):
        #     # check if current path is a file, and store it to temp variable
        #     if os.path.isfile(os.path.join(image_folder, path)):
        #         actual_files.append(path)
        #
        # # For each driver and timestamp there should be a embeddable.html file
        # for expected_file in expected_files:
        #     assert expected_file in actual_files


def test_create_scenario_with_many_avs(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    scenario_creator_user_id = 1
    scenario_template_id = 1

    n_users = 0
    n_avs = 5

    duration_in_seconds = 0.3

    scenario_id = 1

    # Instantiate ONE generator for this test
    state_gen = initial_state_generator(n_avs + n_users, scenario_id)

    # Configure the mocking such that the call to get_vehicle_states_by_scenario_id_at_timestamp returns the expected values
    mock_function = mocker.patch('controller.controller.MixedTrafficScenarioGenerator.generate_random_initial_state')

    def mocked_generate_random_initial_state(driver, goal_region_as_rectangle):
        initial_state = next(state_gen)
        initial_state[3] = driver.user_id
        # Inject the user id
        return tuple(initial_state)

    mock_function.side_effect = mocked_generate_random_initial_state

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id],
                                                                            scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": duration_in_seconds,
            "creator_user_id": scenario_creator_user_id,
            "name": "test",
            "n_users": n_users,
            "n_avs": n_avs
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # At this point, the scenario should be completed since there's only AVs that automatically triggers
        assert response.status_code == 200

@pytest.mark.skip("Random evolution causes flakiness. Re-enable after fixing #134")
def test_evolve_scenario_with_one_driver(flexcrash_test_app_with_a_scenario_template_and_given_users,
                                         random_vehicle_state_data_at_times):
    # Create the app with the factory method
    scenario_creator_user_id = 1
    scenario_template_id = 1

    n_users = 1
    n_avs = 0
    scenario_duration_in_seconds = 0.3 # Keep it short

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id],
                                                                            scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_id = 1
        scenario_data = {
            "scenario_id": scenario_id, # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": scenario_duration_in_seconds,
            "creator_user_id": scenario_creator_user_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code == 202

        # Register the user as driver. This activate the scenario
        driver_data = {
            "user_id": scenario_creator_user_id
        }
        response = test_client.post(url_for("api.scenarios.create_driver", scenario_id=scenario_id),
                                    data=driver_data)
        assert response.status_code == 204

        # Post the states update. This should cause the scenario to end
        # TODO Make this a factory method to generate as many random states as needed
        states_data = random_vehicle_state_data_at_times([1, 2, 3])

        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=1,
                                           driver_id=scenario_creator_user_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204

        # Assert that the scenario is over

        response = test_client.get(url_for("api.scenarios.get_scenario_by_id",
                                           scenario_id=1))
        mixed_scenario_as_dictionary = json.loads(response.data.decode("utf-8"))
        assert mixed_scenario_as_dictionary["status"] == "DONE"

@pytest.mark.skip("Random evolution causes flakiness. Re-enable after fixing #134")
def test_evolve_scenario_with_two_drivers(flexcrash_test_app_with_a_scenario_template_and_given_users,
                                          random_vehicle_state_data_at_times):
    # Create the app with the factory method
    user_1_id = 10
    user_2_id = 11

    scenario_template_id = 1

    n_users = 2
    n_avs = 0
    scenario_duration_in_seconds = 0.3  # Keep it short

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([user_1_id, user_2_id],
                                                                            scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_id = 1
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": scenario_duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code == 202

        # Register the users as driver. This activates the scenario
        response = test_client.post(url_for("api.scenarios.create_driver", scenario_id=scenario_id),
                                    data={
                                        "user_id": user_1_id
                                    })
        assert response.status_code == 204
        response = test_client.post(url_for("api.scenarios.create_driver", scenario_id=scenario_id),
                                    data={
                                        "user_id": user_2_id
                                    })
        assert response.status_code == 204

        # We post one state each time for each user.
        step_duration = 0.1
        scenario_steps = int(scenario_duration_in_seconds/step_duration)
        for time in range(1, scenario_steps+1):
            for user_id in [user_1_id, user_2_id]:
                states_data = random_vehicle_state_data_at_times([time])
                response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_id),
                                   data=states_data)
                # Those states must be accepted, but no content will be returned
                assert response.status_code == 204

        # Assert that the scenario is over

        response = test_client.get(url_for("api.scenarios.get_scenario_by_id",
                                           scenario_id=1))
        mixed_scenario_as_dictionary = json.loads(response.data.decode("utf-8"))
        assert mixed_scenario_as_dictionary["status"] == "DONE"

@pytest.mark.skip("Random evolution causes flakiness. Re-enable after fixing #134")
def test_evolve_scenario_with_many_drivers(flexcrash_test_app_with_a_scenario_template_and_given_users,
                                           random_vehicle_state_data_at_times):

    # TODO We need to make the tests predictable, so generation of random scenarios, initial states, and vehicle
    #  data is not possible anymore. Instead we should use predefined scenarios and     trajectories for each driver.

    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12
    user_3_id = 13
    user_4_id = 14

    scenario_template_id = 1

    n_users = 4
    n_avs = 0
    scenario_duration_in_seconds = 0.3  # Keep it short

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([user_1_id, user_2_id, user_3_id, user_4_id],
                                                                            scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_id = 1
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": scenario_duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code == 202

        # Register the users as driver. This activates the scenario
        for user_id in [user_1_id, user_2_id, user_3_id, user_4_id]:
            response = test_client.post(url_for("api.scenarios.create_driver", scenario_id=scenario_id),
                                    data={
                                        "user_id": user_id
                                    })
            assert response.status_code == 204

        # We post some states (sometimes 3 other 1, other 2, to test all cases)
        # Post 3 states (all) for user_1
        states_data = random_vehicle_state_data_at_times([1, 2, 3])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                                   scenario_id=scenario_id,
                                                   driver_id=user_1_id),
                                           data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204

        # Post 1 state for user_2 and user_3 (it can be the same state)
        states_data = random_vehicle_state_data_at_times([1])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_2_id),
                                   data=states_data)
        assert response.status_code == 204

        # Make sure this is not causing GOAL or CRASH!
        states_data = random_vehicle_state_data_at_times([1])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_3_id),
                                   data=states_data)
        assert response.status_code == 204

        # Post 2 states for user_4
        states_data = random_vehicle_state_data_at_times([1, 2])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_4_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204

        # Now User_1 is done. We post 2 states for User_2 so it is also done
        states_data = random_vehicle_state_data_at_times([2, 3])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_2_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204

        # Now User_1 and User_2 are done. We post 1 state for User_3
        states_data = random_vehicle_state_data_at_times([2])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_3_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204


        # TODO The issue is that at this point the scenario state is DONE, while the info a timestamp 3 are not there...
        # Now User_1 and User_2 are done. User_3 not yet. We post 2 state for User_4 so it goes over the duration,
        # but finishes

        # Note at step 3 the scenario ends, so the info about step 4 should be discarded but no errors should be raised
        states_data = random_vehicle_state_data_at_times([3, 4])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_4_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204

        # Finally we post 2 additionnal states for User_3 so it goes over the duration, but finishes
        states_data = random_vehicle_state_data_at_times([3, 4])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_3_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204

        # Assert that the scenario is over
        response = test_client.get(url_for("api.scenarios.get_scenario_by_id",
                                           scenario_id=1))
        mixed_scenario_as_dictionary = json.loads(response.data.decode("utf-8"))
        assert mixed_scenario_as_dictionary["status"] == "DONE"

def test_evolve_mixed_scenario_with_one_av_and_one_driver(mocker,
                                                          flexcrash_test_app_with_a_scenario_template_and_given_users,
                                                          random_vehicle_state_data_at_times):
    # Create the app with the factory method
    user_1_id = 11

    scenario_template_id = 1

    n_users = 1
    n_avs = 1
    duration_in_seconds = 1.0

    scenario_id = 1

    # Instantiate ONE generator for this test
    state_gen = initial_state_generator(n_avs + n_users, scenario_id)

    # Configure the mocking such that the call to get_vehicle_states_by_scenario_id_at_timestamp returns the expected values
    mock_function = mocker.patch('controller.controller.MixedTrafficScenarioGenerator.generate_random_initial_state')

    def mocked_generate_random_initial_state(driver, goal_region_as_rectangle):
        initial_state = next(state_gen)
        initial_state[3] = driver.user_id
        # Inject the user id
        return tuple(initial_state)

    mock_function.side_effect = mocked_generate_random_initial_state

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([user_1_id], scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code == 202

        # Register the user as driver. This activates the scenario
        for user_id in [user_1_id]:
            response = test_client.post(url_for("api.scenarios.create_driver", scenario_id=scenario_id),
                                        data={
                                            "user_id": user_id
                                        })
            assert response.status_code == 204

        # At this point, AV should compute the next state

        # We post 2 states from the user
        states_data = random_vehicle_state_data_at_times([1, 2, 3, 4, 5])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_1_id),
                                   data=states_data)

        # The AV should compute the states 2 and 3

        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204

        # Check that scenario now is at state 5
        # response = test_client.get(
        #     url_for("api.scenarios.get_vehicle_states", scenario_id=scenario_id, driver_id=user_1_id)
        # )
        #
        # states_as_dict = json.loads(response.data.decode("utf=8"))

        # We post 4 states from the user (over the duration)
        # NOTE We intentionally go over the max duration (10)
        states_data = random_vehicle_state_data_at_times([6, 7, 8, 9, 10, 11, 12])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_1_id),
                                   data=states_data)

        # Check that scenario now is at state 8

        # The AV should not compute any other state

        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204

        # Assert that the scenario is over
        response = test_client.get(url_for("api.scenarios.get_scenario_by_id",
                                           scenario_id=1))
        mixed_scenario_as_dictionary = json.loads(response.data.decode("utf-8"))

        assert mixed_scenario_as_dictionary["status"] == "DONE"

@pytest.mark.skip("Random evolution causes flakiness. Re-enable after fixing #134")
def test_evolve_mixed_scenario_with_two_avs_and_two_drivers(flexcrash_test_app_with_a_scenario_template_and_given_users,
                                                          random_vehicle_state_data_at_times):
    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12

    scenario_template_id = 1

    n_users = 2
    n_avs = 4
    duration_in_seconds = 0.5

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id, user_2_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_id = 1
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code == 202

        # Register the users as driver. This activates the scenario
        for user_id in [user_1_id, user_2_id]:
            response = test_client.post(url_for("api.scenarios.create_driver", scenario_id=scenario_id),
                                        data={
                                            "user_id": user_id
                                        })
            assert response.status_code == 204

        # All the AV should compute the next state

        # We post some states
        # Post many states for user_1
        states_data = random_vehicle_state_data_at_times([1, 2, 3, 4, 5, 6, 7])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_1_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204

        # Post 1 state for User_2
        states_data = random_vehicle_state_data_at_times([1])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_2_id),
                                   data=states_data)
        assert response.status_code == 204

        # Post 2 state for User_2
        states_data = random_vehicle_state_data_at_times([2, 3])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_2_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204

        # Post 2 state for User_2 (finish at duration)
        states_data = random_vehicle_state_data_at_times([4, 5])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_2_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204

        # Assert that the scenario is over
        response = test_client.get(url_for("api.scenarios.get_scenario_by_id",
                                           scenario_id=1))
        mixed_scenario_as_dictionary = json.loads(response.data.decode("utf-8"))
        assert mixed_scenario_as_dictionary["status"] == "DONE"


def test_cannot_evolve_a_scenario_that_is_not_active(flexcrash_test_app_with_a_scenario_template_and_given_users,
                                                     random_vehicle_state_data_at_times):

    """
    GIVEN the flexcrash application configured for testing with one user, one template, and one scenario (requiring 2 drivers)
    GIVEN that only user_1 is registered as a driver
    WHEN the '/api/scenarios/<scenario_id>/driver/<driver_id>' API is requested (POST) to update the state of user_1
    THEN the response is 425: “Too Early.” (because the scenario is not yet started, i.e., "ACTIVE"
    References:
        - https://kinsta.com/blog/http-status-codes/
    """

    # Create the app with the factory method
    user_1_id = 11
    scenario_template_id = 1

    n_users = 2
    n_avs = 0
    duration_in_seconds = 0.5
    # Preassign only user 1
    pre_assigned_users = ",".join([str(u_id) for u_id in [user_1_id]])

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id],
        scenario_template_id)

    # Make the request to create a new scenario with the preassigned users
    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_id = 1
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs,
            "users": pre_assigned_users
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Assert that this scenario is WAITING
        assert response.status_code == 202
        created_scenario_as_dict = json.loads(response.data.decode("utf-8"))
        assert created_scenario_as_dict["status"] == "WAITING"

        # Try to update two states of user_1 results in a 425 "Too Early"
        states_data = random_vehicle_state_data_at_times([1, 2])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_1_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 425


def test_cannot_update_a_non_existing_or_finished_scenario(flexcrash_test_app_with_a_scenario_template_and_given_users,
                                                     random_vehicle_state_data_at_times):

    # TODO Test smell: this test checks two different scenarios

    # Create the app with the factory method
    user_1_id = 11
    scenario_template_id = 1

    n_users = 1
    n_avs = 0
    duration_in_seconds = 0.3
    # Preassign the user_1
    pre_assigned_users = ",".join([str(u_id) for u_id in [user_1_id]])

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id],
        scenario_template_id)

    # Make the request to create a new scenario with the preassigned users
    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_id = 1
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs,
            "users": pre_assigned_users
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Assert that this scenario is ACTIVE (only one scenario
        assert response.status_code == 201
        # Update the states of user_1 results in a completed scenario
        states_data = random_vehicle_state_data_at_times([1, 2, 3])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_1_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204

        # Try to update a non-existing scenario
        non_existing_scenario_id = scenario_id + 10
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=non_existing_scenario_id,
                                           driver_id=user_1_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 404

        # Try to update a scenario that is DONE
        states_data = random_vehicle_state_data_at_times([4])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_1_id),
                                   data=states_data)

        # Those states must be accepted, but no content will be returned
        assert response.status_code == 422


def test_cannot_update_states_beyond_duration_is_not_possible(flexcrash_test_app_with_a_scenario_template_and_given_users,
                                                     random_vehicle_state_data_at_times):

    # Create the app with the factory method
    user_1_id = 11
    scenario_template_id = 1

    n_users = 1
    n_avs = 0
    duration_in_seconds = 0.3
    # Preassign the user_1
    pre_assigned_users = ",".join([str(u_id) for u_id in [user_1_id]])

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id],
        scenario_template_id)

    # Make the request to create a new scenario with the preassigned users
    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_id = 1
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs,
            "users": pre_assigned_users
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Assert that this scenario is ACTIVE (only one scenario
        assert response.status_code == 201

        # Update the states of user_1 beyond the scenario duration
        states_data = random_vehicle_state_data_at_times([4])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_1_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 422


def test_after_driver_crashes_remains_crashed(mocker, flexcrash_test_app_with_a_scenario_template_and_given_users,
                                                     random_vehicle_state_data_at_times):

    # Create the app with the factory method
    user_1_id = 11
    scenario_template_id = 1

    n_users = 1
    n_avs = 0
    duration_in_seconds = 0.3
    # Preassign the user_1
    pre_assigned_users = ",".join([str(u_id) for u_id in [user_1_id]])

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id],
        scenario_template_id)

    # Access the full Driver object
    user_dao = UserDAO(flask_app.config)
    driver = user_dao.get_user_by_user_id(user_1_id)

    # Make the request to create a new scenario with the preassigned users
    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_id = 1
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs,
            "users": pre_assigned_users
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Assert that this scenario is ACTIVE (only one scenario
        assert response.status_code == 201

        # Random state data as JSON
        states_data = random_vehicle_state_data_at_times([1])
        # crashed_state
        vehicle_state = [VehicleState(*vs) for vs in zip(cycle([None]), cycle(["PENDING"]),
                                                          [int(x) for x in states_data["timestamps"].split(",")],
                                                          cycle([user_1_id]), cycle([scenario_id]),
                                                          states_data["positions_x"].split(","),
                                                          states_data["positions_y"].split(","),
                                                          states_data["rotations"].split(","), states_data["speeds_ms"].split(","),
                                                          cycle([0.0]))][0]

        # Configure the mocking to say driver has CRASHed in the given state
        mock_function = mocker.patch('model.collision_checking.CollisionChecker.check_for_collisions')
        mock_function.return_value = [(driver, vehicle_state)]

        # Update the states of user_1 "forcing" a crash state in timestamp 1 using the mocked object
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_1_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204

        # Check all the states from timestamp 1 are CRASHED
        response = test_client.get(url_for("api.scenarios.get_vehicle_states", scenario_id=scenario_id, driver_id=user_1_id))
        states_as_dict = json.loads(response.data.decode("utf=8"))
        assert all(s["status"] == "CRASH" for s in states_as_dict if s["timestamp"] != 0)

        # Check that the scenario is over, DONE
        response = test_client.get(url_for("api.scenarios.get_scenario_by_id", scenario_id=scenario_id))
        scenario_as_dict = json.loads(response.data.decode("utf=8"))
        assert scenario_as_dict["status"] == "DONE"


def test_if_driver_crashes_at_beginning_it_remains_crashed(mocker, flexcrash_test_app_with_a_scenario_template_and_given_users,
                                                     random_vehicle_state_data_at_times):
    # References:
    #   - https://stackoverflow.com/questions/24897145/python-mock-multiple-return-values

    # Create the app with the factory method
    user_1_id = 11
    scenario_template_id = 1

    n_users = 1
    n_avs = 0
    duration_in_seconds = 0.3
    # Preassign the user_1
    pre_assigned_users = ",".join([str(u_id) for u_id in [user_1_id]])

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id],
        scenario_template_id)

    # Access the full Driver object
    user_dao = UserDAO(flask_app.config)
    driver = user_dao.get_user_by_user_id(user_1_id)

    # Make the request to create a new scenario with the preassigned users
    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_id = 1
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs,
            "users": pre_assigned_users
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Assert that this scenario is ACTIVE (only one scenario
        assert response.status_code == 201

        # User 1 plans 3 states, but it crashes at the second one
        states_data = random_vehicle_state_data_at_times([1, 2, 3])
        # crashed_state
        vehicle_states = [VehicleState(*vs) for vs in zip(cycle([None]), cycle(["PENDING"]),
                                                          [int(x) for x in states_data["timestamps"].split(",")],
                                                          cycle([user_1_id]), cycle([scenario_id]),
                                                          states_data["positions_x"].split(","),
                                                          states_data["positions_y"].split(","),
                                                          states_data["rotations"].split(","), states_data["speeds_ms"].split(","),
                                                          cycle([0.0]))]

        # Configure the mocking to say driver has CRASHed in the given at timestamp 2
        mock_function = mocker.patch('model.collision_checking.CollisionChecker.check_for_collisions')
        mock_function.side_effect = [[], [(driver, vehicle_states[1])], []]

        # Update the states of user_1 "forcing" a crash state in timestamp 2 using the mocked object
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=user_1_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204

        # Check all the states from timestamp 2 are CRASHED
        response = test_client.get(url_for("api.scenarios.get_vehicle_states", scenario_id=scenario_id, driver_id=user_1_id))
        states_as_dict = json.loads(response.data.decode("utf=8"))
        assert all(s["status"] == "CRASH" for s in states_as_dict if s["timestamp"] > 1)

        # Check that the scenario is over, DONE
        response = test_client.get(url_for("api.scenarios.get_scenario_by_id", scenario_id=scenario_id))
        scenario_as_dict = json.loads(response.data.decode("utf=8"))
        assert scenario_as_dict["status"] == "DONE"


def test_after_driver_crashes_its_state_cannot_be_updated(mocker,
                                                          flexcrash_test_app_with_a_scenario_template_and_given_users,
                                                     random_vehicle_state_data_at_times):
    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12

    scenario_template_id = 1

    n_users = 2
    n_avs = 0

    # Make sure that we do not finish the scenario before them to crash
    scenario_duration_in_seconds = 1.0

    scenario_id = 1

    # Configure the mocking such that the call to get_vehicle_states_by_scenario_id_at_timestamp returns the expected values
    mock_function_generate_random_initial_state = mocker.patch('controller.controller.MixedTrafficScenarioGenerator.generate_random_initial_state')
    mock_function_generate_random_goal_region = mocker.patch('controller.controller.MixedTrafficScenarioGenerator.generate_random_goal_region')

    # Make sure that Goal Region and initial states are NOT overlapping

    # Use the same goal area for all the vehicles
    def mocked_generate_random_goal_area():
        # Provide ONE goal region
        from commonroad.geometry.shape import Rectangle
        import numpy as np

        orientation = 2.33
        min_x, min_y = 557.32551, -684.4076
        scenario_slope = -1.1
        distance_x = 3
        position_x = min_x - distance_x
        position_y = min_y + (scenario_slope * - distance_x)

        return Rectangle(4.0, 4.0, np.array([position_x, position_y]), orientation)

    def initial_state_generator(scenario_id):
        # Fixed
        rotation = 2.33
        acceleration_m2s = 0.0
        # The road has one lane and it's slope in xy is -1
        min_x, min_y = 557.32551, -684.4076
        scenario_slope = -1.1

        distances_x = [0, -3]
        # Make sure that we finish the scenario before the reach the goal
        speed_md = 1.0
        # Generate two states at 3 and 5 meters from the goal area
        for distance_x in distances_x:
            position_x = min_x - distance_x
            position_y = min_y + (scenario_slope * - distance_x)

            yield [None, "ACTIVE", 0, None, scenario_id, position_x, position_y, rotation, speed_md,
                   acceleration_m2s]

    # Instantiate the generator
    state_gen = initial_state_generator(scenario_id)

    def mocked_generate_random_initial_state(driver, goal_region_as_rectangle):
        initial_state = next(state_gen)
        # Inject the user id
        initial_state[3] = driver.user_id
        return tuple(initial_state)

    mock_function_generate_random_initial_state.side_effect = mocked_generate_random_initial_state
    mock_function_generate_random_goal_region.side_effect = mocked_generate_random_goal_area

    # Start the mocked app
    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([user_1_id, user_2_id],
                                                                            scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": scenario_duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "test",
            "n_users": n_users,
            "n_avs": n_avs,
            "users": ",".join([str(user_1_id), str(user_2_id)])
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)

        # At this point, the scenario should be started, and Active == 201
        assert response.status_code == 201

        # We rigenerate the same states
        state_gen = initial_state_generator(scenario_id)

        initial_state_1 = next(state_gen)
        initial_state_1[3] = user_1_id
        # [None, "ACTIVE", 0, None, scenario_id, position_x, position_y, rotation, speed_md,
        #                    acceleration_m2s]
        # Make user_1 stop: generate n states all the same, with different timestamp
        timestamps = range(1, 4)
        user_1_planned_states_data = {
            "timestamps": ",".join([str(timestamp) for timestamp in timestamps]),
            "positions_x": ",".join([str(value) for value in [initial_state_1[5] for _ in range(len(timestamps))]]),
            "positions_y": ",".join([str(value) for value in [initial_state_1[6] for _ in range(len(timestamps))]]),
            "rotations": ",".join([str(value) for value in [initial_state_1[7] for _ in range(len(timestamps))]]),
            "speeds_ms": ",".join([str(value) for value in [initial_state_1[8] for _ in range(len(timestamps))]]),
            "accelerations_m2s": ",".join([str(value) for value in [initial_state_1[9] for _ in range(len(timestamps))]])
        }
        response = test_client.put(
            url_for("api.scenarios.update_vehicle_states", scenario_id=scenario_id, driver_id=user_1_id),
            data=user_1_planned_states_data
        )

        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204

        # Make user_2 move and crash into it user_1. Since there's no kinematics check during tests, we crash at instant 2

        initial_state_2 = next(state_gen)
        initial_state_2[3] = user_2_id
        collide_at_timestemp = 2
        timestamps = range(1, collide_at_timestemp)
        user_2_planned_states_data = {
            "timestamps": ",".join([str(timestamp) for timestamp in timestamps]),
            "positions_x": ",".join([str(value) for value in [initial_state_2[5] for _ in range(len(timestamps))]]),
            "positions_y": ",".join([str(value) for value in [initial_state_2[6] for _ in range(len(timestamps))]]),
            "rotations": ",".join([str(value) for value in [initial_state_2[7] for _ in range(len(timestamps))]]),
            "speeds_ms": ",".join([str(value) for value in [initial_state_2[8] for _ in range(len(timestamps))]]),
            "accelerations_m2s": ",".join([str(value) for value in [initial_state_2[9] for _ in range(len(timestamps))]])
        }
        from configuration.config import VEHICLE_WIDTH, VEHICLE_LENGTH

        # now jump to a state closed by the initial_state_1 and crash!
        user_2_planned_states_data["timestamps"] = user_2_planned_states_data["timestamps"] + "," + str(
            collide_at_timestemp)
        user_2_planned_states_data["positions_x"] = user_2_planned_states_data["positions_x"] + "," + str(
            initial_state_1[5] + VEHICLE_WIDTH)
        user_2_planned_states_data["positions_y"] = user_2_planned_states_data["positions_y"] + "," + str(
            initial_state_1[6] - VEHICLE_LENGTH / 2)
        user_2_planned_states_data["rotations"] = user_2_planned_states_data["rotations"] + "," + str(initial_state_1[7])
        user_2_planned_states_data["speeds_ms"] = user_2_planned_states_data["speeds_ms"] + "," + str(initial_state_1[8])
        user_2_planned_states_data["accelerations_m2s"] = user_2_planned_states_data["accelerations_m2s"] + "," + str(
            initial_state_1[9])

        response = test_client.put(
            url_for("api.scenarios.update_vehicle_states", scenario_id=scenario_id,
                    driver_id=user_2_id),
            data=user_2_planned_states_data
        )

        # Those states must be accepted, but no content will be returned (or will this be a 200 signaling the scenario is done?)
        assert response.status_code == 204

        ##### Assert the user1 is reported as CRASHED

        # At this point, since both drivers sent the first state, the status of user_1 should be CRASH from 1 to 3
        response = test_client.get(
            url_for("api.scenarios.get_vehicle_states", scenario_id=scenario_id, driver_id=user_1_id)
        )

        states_as_dict = json.loads(response.data.decode("utf=8"))
        assert any(s["status"] == "CRASHED" for s in states_as_dict if s["timestamp"] != 0)

        # TRY TO UPDATE THE STATE of user1 resulting in a failed request
        new_planned_states_data = {
            "timestamps": ",".join([str(collide_at_timestemp + 1)]),
            # Values are not really relevant
            "positions_x": ",".join([str(initial_state_2[5])]),
            "positions_y": ",".join([str(initial_state_2[6])]),
            "rotations": ",".join([str(initial_state_2[7])]),
            "speeds_ms": ",".join([str(initial_state_2[8])]),
            "accelerations_m2s": ",".join([str(initial_state_2[9])])
        }
        response = test_client.put(
            url_for("api.scenarios.update_vehicle_states", scenario_id=scenario_id,driver_id=user_1_id),
            data=new_planned_states_data
        )
        # Those states cannot be accepted because this driver is CRASHED, so the update is Forbidden
        assert response.status_code == 422