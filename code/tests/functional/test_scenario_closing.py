#
# Those tests check that scenarios are automatically closed when ending conditions are met:
# - Scenario duration is over and not all cars are GOAL_REACHED or CRASHED
# - All cars are GOAL_REACHED or CRASHED
#
# Tests make use of mocked initial and final states to make tests predictable
#

import json
import os

import pytest
from flask import url_for

from itertools import cycle
from model.user import User
from model.vehicle_state import VehicleState
from persistence.data_access import UserDAO


def test_one_av_that_reaches_goal_area(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    scenario_creator_user_id = 1
    scenario_template_id = 1

    n_users = 0
    n_avs = 1

    # Make sure that we allow enough time for the vehicle to reach the goal area
    scenario_duration_in_seconds = 2.0

    scenario_id = 1

    # Configure the mocking such that the call to get_vehicle_states_by_scenario_id_at_timestamp returns the expected values
    mock_function_generate_random_initial_state = mocker.patch(
        'controller.controller.MixedTrafficScenarioGenerator.generate_random_initial_state')
    mock_function_generate_random_goal_region = mocker.patch(
        'controller.controller.MixedTrafficScenarioGenerator.generate_random_goal_region')

    # Make sure that Goal Region and initial state are close-enough, but NOT overlapping
    def mocked_generate_random_initial_state(driver, goal_region_as_rectangle):
        # Provide ONE initial state, almost at end of the road to Mock Goal Region at the Beginning of the road
        rotation = 2.33
        # Make it drive faster
        speed_md = 10.0
        acceleration_m2s = 0.0
        position_x, position_y = 557.32551, -684.4076
        return (None, "ACTIVE", 0, driver.user_id, scenario_id, position_x, position_y, rotation, speed_md,
                acceleration_m2s)

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

    mock_function_generate_random_initial_state.side_effect = mocked_generate_random_initial_state
    mock_function_generate_random_goal_region.side_effect = mocked_generate_random_goal_area

    # Start the mocked app
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
        # At this point, the scenario should be COMPLETED since there's only one AV that automatically triggers
        assert response.status_code == 200


def test_two_avs_that_reache_goal_area(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    scenario_creator_user_id = 1
    scenario_template_id = 1

    n_users = 0
    n_avs = 2

    # Make sure that we allow enough time for the vehicle to reach the goal area
    scenario_duration_in_seconds = 2.0

    scenario_id = 1

    # Configure the mocking such that the call to get_vehicle_states_by_scenario_id_at_timestamp returns the expected values
    mock_function_generate_random_initial_state = mocker.patch(
        'controller.controller.MixedTrafficScenarioGenerator.generate_random_initial_state')
    mock_function_generate_random_goal_region = mocker.patch(
        'controller.controller.MixedTrafficScenarioGenerator.generate_random_goal_region')

    # Make sure that Goal Region and initial states are close-enough, but NOT overlapping

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
        speed_md = 10.0
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
        # At this point, the scenario should be COMPLETED since there's only one AV that automatically triggers
        assert response.status_code == 200


def test_two_avs_that_timeout(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    scenario_creator_user_id = 1
    scenario_template_id = 1

    n_users = 0
    n_avs = 2

    # Make sure that we finish the scenario before the reach the goal
    scenario_duration_in_seconds = 0.4

    scenario_id = 1

    # Configure the mocking such that the call to get_vehicle_states_by_scenario_id_at_timestamp returns the expected values
    mock_function_generate_random_initial_state = mocker.patch(
        'controller.controller.MixedTrafficScenarioGenerator.generate_random_initial_state')
    mock_function_generate_random_goal_region = mocker.patch(
        'controller.controller.MixedTrafficScenarioGenerator.generate_random_goal_region')

    # Make sure that Goal Region and initial states are close-enough, but NOT overlapping

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
        # At this point, the scenario should be COMPLETED since there's only one AV that automatically triggers
        assert response.status_code == 200


def test_two_registered_human_drivers_crash(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Instantiat the scenario
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
    mock_function_generate_random_initial_state = mocker.patch(
        'controller.controller.MixedTrafficScenarioGenerator.generate_random_initial_state')
    mock_function_generate_random_goal_region = mocker.patch(
        'controller.controller.MixedTrafficScenarioGenerator.generate_random_goal_region')

    # Make sure that Goal Region and initial states are close-enough, but NOT overlapping

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
            "users" : ",".join([str(user_1_id), str(user_2_id)])
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
    user_2_planned_states_data["timestamps"] = user_2_planned_states_data["timestamps"] + "," + str(collide_at_timestemp)
    user_2_planned_states_data["positions_x"] = user_2_planned_states_data["positions_x"] + "," + str(initial_state_1[5] + VEHICLE_WIDTH)
    user_2_planned_states_data["positions_y"] = user_2_planned_states_data["positions_y"] + "," + str(initial_state_1[6] - VEHICLE_LENGTH /2)
    user_2_planned_states_data["rotations"] = user_2_planned_states_data["rotations"] + "," + str(initial_state_1[7])
    user_2_planned_states_data["speeds_ms"] = user_2_planned_states_data["speeds_ms"] + "," + str(initial_state_1[8])
    user_2_planned_states_data["accelerations_m2s"] = user_2_planned_states_data["accelerations_m2s"] + "," + str(initial_state_1[9])

    response = test_client.put(
        url_for("api.scenarios.update_vehicle_states", scenario_id=scenario_id,
                driver_id=user_2_id),
        data=user_2_planned_states_data
    )

    # Those states must be accepted, but no content will be returned (or will this be a 200 signaling the scenario is done?)
    assert response.status_code == 204

    # Check that the scenario is in the DONE state
    response = test_client.get(url_for("api.scenarios.get_scenario_by_id",
                                       scenario_id=scenario_id))
    mixed_scenario_as_dictionary = json.loads(response.data.decode("utf-8"))
    assert mixed_scenario_as_dictionary["status"] == "DONE"

    # Check that the scenario has only three (0 + 2) states for each driver
    for driver_id in [ user_1_id, user_2_id]:
        response = test_client.get(url_for("api.scenarios.get_vehicle_states",
                                       scenario_id=scenario_id, driver_id=driver_id))
        vehicle_states_as_dictionary = json.loads(response.data.decode("utf-8"))
        assert len(vehicle_states_as_dictionary) == 3
