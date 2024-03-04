#
# Those tests check that scenarios are automatically closed when ending conditions are met:
# - Scenario duration is over and not all cars are GOAL_REACHED or CRASHED
# - All cars are GOAL_REACHED or CRASHED
#
# Tests make use of mocked initial and final states to make tests predictable
#

import json
import pytest

from flask import url_for

from tests.utils import generate_scenario_data

@pytest.mark.skip("Background processing of AV hard to test. Fix the test first")
def test_one_av_that_reaches_goal_area(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 1
    n_users = 0
    scenario_duration_in_seconds = 2.0
    scenario_id = 1
    preregistered_users = []

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id],
                                                                            scenario_template_id)
    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # At this point, the scenario should be COMPLETED since there's only one AV that automatically triggers
        assert response.status_code == 200

@pytest.mark.skip("Background processing of AV hard to test. Fix the test first")
def test_two_avs_that_reache_goal_area(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 2
    n_users = 0
    scenario_duration_in_seconds = 2.0
    scenario_id = 1
    preregistered_users = []

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id],
                                                                            scenario_template_id)
    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # At this point, the scenario should be COMPLETED since there's only one AV that automatically triggers
        assert response.status_code == 200

@pytest.mark.skip("Background processing of AV hard to test. Fix the test first")
def test_two_avs_that_timeout(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 2
    n_users = 0
    scenario_duration_in_seconds = 0.4
    scenario_id = 1
    preregistered_users = []

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id],
                                                                            scenario_template_id)
    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # At this point, the scenario should be COMPLETED since there's only one AV that automatically triggers
        assert response.status_code == 200


def test_two_registered_human_drivers_crash(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    user_1_id = 11
    user_2_id = 12

    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 0
    n_users = 2
    scenario_duration_in_seconds = 1.0
    scenario_id = 1
    preregistered_users = [user_1_id, user_2_id]

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id, user_1_id, user_2_id],
                                                                            scenario_template_id)
    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # At this point, the scenario should be started, and Active == 201
        assert response.status_code == 201

    # Simulate the two users that move. User_1 does not move, User_2 moves, and eventually crash with User_1

    rotation = 2.33
    speed_ms = 1.0
    acceleration_m2s = 0.0

    position_x, position_y = 557.32551, -684.4076
    initial_state_user_1 = [None, "ACTIVE", 0, user_1_id, scenario_id, position_x, position_y, rotation, speed_ms, acceleration_m2s]

    timestamps = range(1, 4)
    user_1_planned_states_data = {
        "timestamps": ",".join([str(timestamp) for timestamp in timestamps]),
        "positions_x": ",".join([str(value) for value in [initial_state_user_1[5] for _ in range(len(timestamps))]]),
        "positions_y": ",".join([str(value) for value in [initial_state_user_1[6] for _ in range(len(timestamps))]]),
        "rotations": ",".join([str(value) for value in [initial_state_user_1[7] for _ in range(len(timestamps))]]),
        "speeds_ms": ",".join([str(value) for value in [initial_state_user_1[8] for _ in range(len(timestamps))]]),
        "accelerations_m2s": ",".join([str(value) for value in [initial_state_user_1[9] for _ in range(len(timestamps))]])
    }
    response = test_client.put(
        url_for("api.scenarios.update_vehicle_states", scenario_id=scenario_id, user_id=user_1_id),
        data=user_1_planned_states_data
    )

    # Those states must be accepted, but no content will be returned as we are waiting for user 2 trajectory
    assert response.status_code == 204


    # Create user 2 trajectory
    # Stay two instants in the initial position, then jump to user 1 position and crash
    position_x = 552.32551
    position_y = -678.9076

    initial_state_user_2 = [None, "ACTIVE", 0, user_2_id, scenario_id, position_x, position_y, rotation, speed_ms, acceleration_m2s]
    collide_at_timestemp = 2
    timestamps = range(1, collide_at_timestemp)

    user_2_planned_states_data = {
        "timestamps": ",".join([str(timestamp) for timestamp in timestamps]),
        "positions_x": ",".join([str(value) for value in [initial_state_user_2[5] for _ in range(len(timestamps))]]),
        "positions_y": ",".join([str(value) for value in [initial_state_user_2[6] for _ in range(len(timestamps))]]),
        "rotations": ",".join([str(value) for value in [initial_state_user_2[7] for _ in range(len(timestamps))]]),
        "speeds_ms": ",".join([str(value) for value in [initial_state_user_2[8] for _ in range(len(timestamps))]]),
        "accelerations_m2s": ",".join([str(value) for value in [initial_state_user_2[9] for _ in range(len(timestamps))]])
    }

    from configuration.config import VEHICLE_WIDTH, VEHICLE_LENGTH
    # now jump to a state closed by the initial_state_1 and crash!
    user_2_planned_states_data["timestamps"] = user_2_planned_states_data["timestamps"] + "," + str(collide_at_timestemp)
    user_2_planned_states_data["positions_x"] = user_2_planned_states_data["positions_x"] + "," + str(initial_state_user_1[5] + VEHICLE_WIDTH)
    user_2_planned_states_data["positions_y"] = user_2_planned_states_data["positions_y"] + "," + str(initial_state_user_1[6] - VEHICLE_LENGTH /2)
    user_2_planned_states_data["rotations"] = user_2_planned_states_data["rotations"] + "," + str(initial_state_user_1[7])
    user_2_planned_states_data["speeds_ms"] = user_2_planned_states_data["speeds_ms"] + "," + str(initial_state_user_1[8])
    user_2_planned_states_data["accelerations_m2s"] = user_2_planned_states_data["accelerations_m2s"] + "," + str(initial_state_user_1[9])

    response = test_client.put(
        url_for("api.scenarios.update_vehicle_states", scenario_id=scenario_id, user_id=user_2_id),
        data=user_2_planned_states_data
    )

    # Those states must be accepted, but no content will be returned (or will this be a 200 signaling the scenario is done?)
    assert response.status_code == 204

    # Check that the scenario is in the DONE state
    response = test_client.get(url_for("api.scenarios.get_scenario_by_id", scenario_id=scenario_id))
    mixed_scenario_as_dictionary = json.loads(response.data.decode("utf-8"))
    assert mixed_scenario_as_dictionary["status"] == "DONE"

    # Check that the scenario has only three (0 + 2) states for each driver
    for user_id in [ user_1_id, user_2_id]:
        response = test_client.get(url_for("api.scenarios.get_vehicle_states",scenario_id=scenario_id, user_id=user_id))
        vehicle_states_as_dictionary = json.loads(response.data.decode("utf-8"))
        assert len(vehicle_states_as_dictionary) == 3
