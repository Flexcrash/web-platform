# Define the fixtures for the following test cases
import json

import pytest
from flask import url_for

from itertools import cycle
from persistence.user_data_access import UserDAO
from persistence.driver_data_access import DriverDAO

from model.vehicle_state import VehicleState

from tests.utils import generate_scenario_data

@pytest.mark.skip("Background processing of AV hard to test. Fix the test first")
def test_evolve_scenario_with_one_av(flexcrash_test_app_with_a_scenario_template_and_given_users):
    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 1
    n_users = 0
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = []

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id],
                                                                            scenario_template_id)
    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Assert that the scenario is ACTIVE
        assert response.status_code == 201

    # TODO Simulate evolution or re-enable the backgroun executor or find another way
        # Assert the status of this scenario is DONE (since the drivers automatically drives till the end)

        mixed_scenario_as_dictionary = json.loads(response.data.decode("utf-8"))
        assert mixed_scenario_as_dictionary["status"] == "DONE"

@pytest.mark.skip("Background processing of AV hard to test. Fix the test first")
def test_evolve_scenario_with_two_avs(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 2
    n_users = 0
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = []

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id],
                                                                            scenario_template_id)
    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # At this point, the scenario should be completed since there's only AVs that automatically triggers
        assert response.status_code == 200

        mixed_scenario_as_dictionary = json.loads(response.data.decode("utf-8"))
        assert mixed_scenario_as_dictionary["status"] == "DONE"

        # # TODO Add assertions?
        # scenario_id = mixed_scenario_as_dictionary["scenario_id"]
        # driver_ids = [d["user_id"] for d in mixed_scenario_as_dictionary["drivers"]]
        #
        # # Assert the Images/HTML
        # image_folder = flask_app.config["IMAGES_FOLDER"]
        # expected_files = []
        #
        # # Include the initial state !
        # step_duration = 0.1
        # scenario_steps = int(scenario_duration_in_seconds / step_duration)

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

@pytest.mark.skip("Background processing of AV hard to test. Fix the test first")
def test_create_scenario_with_many_avs(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 5
    n_users = 0
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = []

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id],
                                                                            scenario_template_id)
    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # At this point, the scenario should be completed since there's only AVs that automatically triggers
        assert response.status_code == 200

        mixed_scenario_as_dictionary = json.loads(response.data.decode("utf-8"))
        assert mixed_scenario_as_dictionary["status"] == "DONE"

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

# TODO: Ideally, we should collect a Dynamic Object trajectory and use it to plan

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
    user_1_id = 11

    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 0
    n_users = 2
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = [user_1_id]

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id, user_1_id],
                                                                            scenario_template_id)
    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Assert that this scenario is WAITING
        assert response.status_code == 202
        created_scenario_as_dict = json.loads(response.data.decode("utf-8"))
        assert created_scenario_as_dict["status"] == "WAITING"

        # Try to update two states of user_1 results in a 425 "Too Early"
        states_data = random_vehicle_state_data_at_times([1, 2])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           user_id=user_1_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 425


def test_cannot_update_a_non_existing_or_finished_scenario(flexcrash_test_app_with_a_scenario_template_and_given_users,
                                                     random_vehicle_state_data_at_times):
    user_1_id = 11

    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 0
    n_users = 1
    scenario_duration_in_seconds = 0.3
    scenario_id = 1
    preregistered_users = [user_1_id]

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id, user_1_id],
                                                                            scenario_template_id)
    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Assert that this scenario is ACTIVE (only one scenario
        assert response.status_code == 201
        # Update the states of user_1 results in a completed scenario
        states_data = random_vehicle_state_data_at_times([1, 2, 3])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           user_id=user_1_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned - At this point the scenario is DONE.
        assert response.status_code == 204

        # Try to update a non-existing scenario
        non_existing_scenario_id = scenario_id + 10
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=non_existing_scenario_id,
                                           user_id=user_1_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 404

        # Try to update a scenario that is DONE
        states_data = random_vehicle_state_data_at_times([4])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           user_id=user_1_id),
                                   data=states_data)

        # Those states must be accepted, but no content will be returned
        assert response.status_code == 422


def test_cannot_update_states_beyond_duration_is_not_possible(flexcrash_test_app_with_a_scenario_template_and_given_users,
                                                     random_vehicle_state_data_at_times):
    user_1_id = 11

    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 0
    n_users = 1
    scenario_duration_in_seconds = 0.3
    scenario_id = 1
    preregistered_users = [user_1_id]

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id, user_1_id],
                                                                            scenario_template_id)
    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Assert that this scenario is ACTIVE (only one scenario
        assert response.status_code == 201

        # Update the states of user_1 beyond the scenario duration
        states_data = random_vehicle_state_data_at_times([4])
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           user_id=user_1_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 422


def test_after_driver_crashes_remains_crashed(mocker, flexcrash_test_app_with_a_scenario_template_and_given_users,
                                                     random_vehicle_state_data_at_times):
    user_1_id = 11

    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 0
    n_users = 1
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = [user_1_id]

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id, user_1_id],
                                                                            scenario_template_id)
    # Access the User object that is driving
    user_dao = UserDAO()
    user_driver = user_dao.get_user_by_user_id(user_1_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Assert that this scenario is ACTIVE (only one scenario
        assert response.status_code == 201

        # Random state data as JSON
        states_data = random_vehicle_state_data_at_times([1])

        def split_and_extract(dict, key):
            return dict[key].split(",")[0]

        kwargs = {
            "status": "PENDING",
            "timestamp": split_and_extract(states_data, "timestamps"),
            "position_x": split_and_extract(states_data, "positions_x"),
            "position_y": split_and_extract(states_data, "positions_y"),
            "rotation": split_and_extract(states_data, "rotations"),
            "speed_ms": split_and_extract(states_data, "speeds_ms"),
            "acceleration_m2s": split_and_extract(states_data, "accelerations_m2s"),
        }
        vehicle_state = VehicleState(**kwargs)

        # Configure the mocking to say driver has CRASHed in the given state
        mock_function = mocker.patch('model.collision_checking.CollisionChecker.check_for_collisions')
        mock_function.return_value = [(user_driver, vehicle_state)]

        # Update the states of user_1 "forcing" a crash state in timestamp 1 using the mocked object
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           user_id=user_1_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204

        # Check all the states from timestamp 1 are CRASHED
        response = test_client.get(url_for("api.scenarios.get_vehicle_states", scenario_id=scenario_id, user_id=user_1_id))
        assert response.status_code == 200
        states_as_dict = json.loads(response.data.decode("utf=8"))
        assert all(s["status"] == "CRASHED" for s in states_as_dict if s["timestamp"] != 0)

        # Check that the scenario is over, DONE
        response = test_client.get(url_for("api.scenarios.get_scenario_by_id", scenario_id=scenario_id))
        scenario_as_dict = json.loads(response.data.decode("utf=8"))
        assert scenario_as_dict["status"] == "DONE"


def test_if_driver_crashes_at_beginning_it_remains_crashed(mocker, flexcrash_test_app_with_a_scenario_template_and_given_users,
                                                     random_vehicle_state_data_at_times):
    # References:
    #   - https://stackoverflow.com/questions/24897145/python-mock-multiple-return-values

    user_1_id = 11

    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 0
    n_users = 1
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = [user_1_id]

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id, user_1_id],
                                                                            scenario_template_id)
    # Access the User object that is driving
    user_dao = UserDAO()
    user_driver = user_dao.get_user_by_user_id(user_1_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Assert that this scenario is ACTIVE (only one scenario
        assert response.status_code == 201

        # Now the user is bound to a driver, we need the driver to generate the mock
        driver_dao = DriverDAO(flask_app.config)
        driver = driver_dao.get_driver_by_user_id(scenario_id, user_1_id)

        assert driver.scenario_id == scenario_id
        assert driver.user_id == user_1_id

        # User 1 plans 3 states, but it crashes at the second one
        states_data = random_vehicle_state_data_at_times([1, 2, 3])
        # crashed_state
        vehicle_states = []
        for vehicle_state_data in zip(cycle([None]), cycle(["PENDING"]),
                                                          [int(x) for x in states_data["timestamps"].split(",")],
                                                          cycle([driver.driver_id]), cycle([driver.user_id]), cycle([driver.scenario_id]),
                                                          states_data["positions_x"].split(","),
                                                          states_data["positions_y"].split(","),
                                                          states_data["rotations"].split(","), states_data["speeds_ms"].split(","),
                                                          cycle([0.0])):
            vehicle_states.append(
                VehicleState(
                    vehicle_state_id = vehicle_state_data[0],
                    status = vehicle_state_data[1],
                    timestamp = vehicle_state_data[2],
                    driver_id = vehicle_state_data[3],
                    user_id = vehicle_state_data[4],
                    scenario_id = vehicle_state_data[5],
                    position_x = vehicle_state_data[6],
                    position_y = vehicle_state_data[7],
                    rotation = vehicle_state_data[8],
                    speed_ms = vehicle_state_data[9],
                    acceleration_m2s = vehicle_state_data[10]
                )
            )

        # Configure the mocking to say driver has CRASHed in the given at timestamp 2
        mock_function = mocker.patch('model.collision_checking.CollisionChecker.check_for_collisions')
        mock_function.side_effect = [[], [(user_driver, vehicle_states[1])], []]

        # Update the states of user_1 "forcing" a crash state in timestamp 2 using the mocked object
        response = test_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           user_id=user_1_id),
                                   data=states_data)
        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204

        # Check all the states from timestamp 2 are CRASHED
        response = test_client.get(url_for("api.scenarios.get_vehicle_states", scenario_id=scenario_id, user_id=user_1_id))
        states_as_dict = json.loads(response.data.decode("utf=8"))
        assert all(s["status"] == "CRASHED" for s in states_as_dict if s["timestamp"] > 1)

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

    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 0
    n_users = 2
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = [user_1_id, user_2_id]

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id, user_1_id, user_2_id],
                                                                            scenario_template_id)
    # Access the User object that is driving
    user_dao = UserDAO()
    user_1_driver = user_dao.get_user_by_user_id(user_1_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # At this point, the scenario should be started, and Active == 201
        assert response.status_code == 201

        # We rigenerate the same states
        # Fixed
        rotation = 2.33
        speed_ms = 1.0
        acceleration_m2s = 0.0
        # The road has one lane and it's slope in xy is -1
        position_x, position_y = scenario_data[f"U_{user_1_id}_x"], scenario_data[f"U_{user_1_id}_y"]

        initial_state_1 = [None, "ACTIVE", 0, user_1_id, scenario_id, position_x, position_y, rotation, speed_ms, acceleration_m2s]

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
            url_for("api.scenarios.update_vehicle_states", scenario_id=scenario_id, user_id=user_1_id),
            data=user_1_planned_states_data
        )

        # Those states must be accepted, but no content will be returned
        assert response.status_code == 204

        position_x, position_y = scenario_data[f"U_{user_2_id}_x"], scenario_data[f"U_{user_2_id}_y"]

        initial_state_2 = [None, "ACTIVE", 0, user_2_id, scenario_id, position_x, position_y, rotation, speed_ms, acceleration_m2s]

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
        user_2_planned_states_data["timestamps"] = user_2_planned_states_data["timestamps"] + "," + str(collide_at_timestemp)
        user_2_planned_states_data["positions_x"] = user_2_planned_states_data["positions_x"] + "," + str(initial_state_1[5] + VEHICLE_WIDTH)
        user_2_planned_states_data["positions_y"] = user_2_planned_states_data["positions_y"] + "," + str(initial_state_1[6] - VEHICLE_LENGTH / 2)
        user_2_planned_states_data["rotations"] = user_2_planned_states_data["rotations"] + "," + str(initial_state_1[7])
        user_2_planned_states_data["speeds_ms"] = user_2_planned_states_data["speeds_ms"] + "," + str(initial_state_1[8])
        user_2_planned_states_data["accelerations_m2s"] = user_2_planned_states_data["accelerations_m2s"] + "," + str(initial_state_1[9])

        response = test_client.put(
            url_for("api.scenarios.update_vehicle_states", scenario_id=scenario_id, user_id=user_2_id),
            data=user_2_planned_states_data
        )

        # Those states must be accepted, but no content will be returned (or will this be a 200 signaling the scenario is done?)
        assert response.status_code == 204

        ##### Assert the user1 is reported as CRASHED

        # At this point, since both drivers sent the first state, the status of user_1 should be CRASH from 1 to 3
        response = test_client.get(
            url_for("api.scenarios.get_vehicle_states", scenario_id=scenario_id, user_id=user_1_id)
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
            url_for("api.scenarios.update_vehicle_states", scenario_id=scenario_id, user_id=user_1_id),
            data=new_planned_states_data
        )
        # Those states cannot be accepted because this driver is CRASHED, so the update is Forbidden
        assert response.status_code == 422