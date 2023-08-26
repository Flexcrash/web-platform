# Define the fixtures for the following test cases
import json
import os

import pytest
from flask import url_for

from itertools import cycle
from model.user import User
from model.vehicle_state import VehicleState
from persistence.data_access import UserDAO


# TODO Mock the SCENARIO GENERATOR to provide VALID/NON-CRASHING/PREDEFINED/INITIAL STATES!

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


def initial_overlapping_state_generator(n_drivers, scenario_id):
    # All Fixed means Overlapping
    rotation = 2.33
    speed_md = 1.0
    acceleration_m2s = 0.0
    position_x, position_y = 557.32551, -684.4076
    for idx in range(0, n_drivers):
        yield [None, "ACTIVE", 0, None, scenario_id, position_x, position_y, rotation, speed_md,
               acceleration_m2s]



def test_create_scenario_with_one_av(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    # Create the app with the factory method
    scenario_creator_user_id = 1
    scenario_template_id = 1

    n_users = 0
    n_avs = 1

    scenario_duration_in_seconds = 0.3

    scenario_id = 1

    # Instantiate ONE generator for this test
    # state_gen = initial_state_generator(n_avs + n_users, scenario_id)
    state_gen = initial_state_generator(5, scenario_id)

    # Configure the mocking such that the call to get_vehicle_states_by_scenario_id_at_timestamp returns the expected values
    mock_function = mocker.patch('controller.controller.MixedTrafficScenarioGenerator.generate_random_initial_state')

    def mocked_generate_random_initial_state(driver, goal_region_as_rectangle):
        initial_state = next(state_gen)
        #
        initial_state = next(state_gen)
        #
        initial_state = next(state_gen)
        # Ensure we start with the problematic case
        initial_state = next(state_gen)
        #
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
        # At this point, the scenario should be COMPLETED since there's only one AV that automatically triggers
        assert response.status_code == 200


def test_create_scenario_with_two_avs(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    # Create the app with the factory method
    scenario_creator_user_id = 1
    scenario_template_id = 1

    scenario_duration_in_seconds = 0.3

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


def test_create_scenario_with_one_human_driver(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    scenario_creator_user_id = 1
    scenario_template_id = 1

    n_users = 1
    n_avs = 0
    scenario_duration_in_seconds = 0.3 # Keep it short

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
            "scenario_id": scenario_id, # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": scenario_duration_in_seconds,
            "creator_user_id": scenario_creator_user_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Scenario created, but in WAITING
        assert response.status_code == 202


def test_create_scenario_with_two_human_drivers(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    user_1_id = 10
    user_2_id = 11

    scenario_template_id = 1

    n_users = 2
    n_avs = 0
    scenario_duration_in_seconds = 0.3  # Keep it short

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

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([user_1_id, user_2_id],
                                                                            scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
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


def test_create_scenario_with_many_human_drivers(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12
    user_3_id = 13
    user_4_id = 14

    scenario_template_id = 1

    n_users = 4
    n_avs = 0
    scenario_duration_in_seconds = 0.3  # Keep it short

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

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([user_1_id, user_2_id, user_3_id, user_4_id],
                                                                            scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
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


def test_create_mixed_scenario_with_one_av_and_one_human_driver(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    # Create the app with the factory method
    user_1_id = 11

    scenario_template_id = 1

    n_users = 1
    n_avs = 1
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

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([user_1_id],scenario_template_id)

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


def test_create_mixed_scenario_with_two_avs_and_one_human_driver(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    user_1_id = 11

    scenario_template_id = 1

    n_avs = 2
    n_users = 1

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

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id],
        scenario_template_id)

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


def test_create_mixed_scenario_with_on_av_and_two_human_drivers(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12

    scenario_template_id = 1

    n_avs = 1
    n_users = 2

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

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id, user_2_id],
        scenario_template_id)

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


def test_create_mixed_scenario_with_two_avs_and_two_human_drivers(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12

    scenario_template_id = 1

    n_avs = 2
    n_users = 2

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

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id, user_2_id],
        scenario_template_id)

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


def test_create_mixed_scenario_with_many_avs_and_many_human_drivers(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12
    user_3_id = 13
    user_4_id = 14

    scenario_template_id = 1

    n_avs = 5
    n_users = 2

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

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id, user_2_id, user_3_id, user_4_id],
        scenario_template_id)

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


def test_create_mixed_scenario_with_one_av_and_one_registered_human_driver(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    user_1_id = 11

    scenario_template_id = 1

    n_avs = 1
    n_users = 1

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

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs,
            #     preassigned_user_ids = set(data["users"].split(',') if "users" in data and len(data["users"]) > 0 else [])
            "users": user_1_id
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Note we expect 201 because the scenario becomes automatically ACTIVE in this case, i.e., no need to waiting for other users to join
        assert response.status_code == 201


def test_create_mixed_scenario_with_two_avs_and_one_registered_human_driver(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    user_1_id = 11

    scenario_template_id = 1

    n_avs = 2
    n_users = 1

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

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs,
            #     preassigned_user_ids = set(data["users"].split(',') if "users" in data and len(data["users"]) > 0 else [])
            "users": ",".join([str(user_1_id)])
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Note we expect 201 because the scenario becomes automatically ACTIVE in this case, i.e., no need to waiting for other users to join
        assert response.status_code == 201


def test_create_mixed_scenario_with_one_av_and_two_registered_human_drivers(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12

    scenario_template_id = 1

    n_avs = 1
    n_users = 2

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

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id, user_2_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs,
            #     preassigned_user_ids = set(data["users"].split(',') if "users" in data and len(data["users"]) > 0 else [])
            "users": ",".join([str(user_1_id), str(user_2_id)])
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Note we expect 201 because the scenario becomes automatically ACTIVE in this case, i.e., no need to waiting for other users to join
        assert response.status_code == 201


def test_create_mixed_scenario_with_two_avs_and_two_registered_human_drivers(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12

    scenario_template_id = 1

    n_avs = 2
    n_users = 2

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

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id, user_2_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs,
            #     preassigned_user_ids = set(data["users"].split(',') if "users" in data and len(data["users"]) > 0 else [])
            "users": ",".join([str(user_1_id), str(user_2_id)])
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Note we expect 201 because the scenario becomes automatically ACTIVE in this case, i.e., no need to waiting for other users to join
        assert response.status_code == 201


def test_create_mixed_scenario_with_one_av_and_one_registered_human_driver_and_one_human_driver(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12

    scenario_template_id = 1

    n_avs = 1
    n_users = 2

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

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id, user_2_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs,
            # Preassign ONLY one of the two human drivers
            "users": ",".join([str(user_1_id)])
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code == 202


def test_create_complex_mixed_scenario(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12
    user_3_id = 13

    scenario_template_id = 1

    n_avs = 4
    n_users = 4

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

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id, user_2_id, user_3_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs,
            # Preassign ONLY two of the two human drivers
            "users": ",".join([str(user_1_id), str(user_3_id)])
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code == 202


def test_create_mixed_scenario_with_overlapping_vehicles_fail(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    user_1_id = 11

    scenario_template_id = 1

    n_avs = 1
    n_users = 1

    duration_in_seconds = 0.3

    scenario_id = 1

    # Instantiate ONE generator for this test
    overlapping_state_gen = initial_overlapping_state_generator(n_avs + n_users, scenario_id)

    # Configure the mocking such that the call to get_vehicle_states_by_scenario_id_at_timestamp returns the expected values
    mock_function = mocker.patch('controller.controller.MixedTrafficScenarioGenerator.generate_random_initial_state')

    def mocked_generate_random_initial_state(driver, goal_region_as_rectangle):
        initial_state = next(overlapping_state_gen)
        # Inject the user id
        initial_state[3] = driver.user_id
        return tuple(initial_state)

    mock_function.side_effect = mocked_generate_random_initial_state

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs,
            #     preassigned_user_ids = set(data["users"].split(',') if "users" in data and len(data["users"]) > 0 else [])
            "users": user_1_id
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Note we expect 201 because the scenario becomes automatically ACTIVE in this case, i.e., no need to waiting for other users to join
        assert response.status_code == 422


def test_create_mixed_scenario_with_unreacheable_goal_area(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    user_1_id = 11

    scenario_template_id = 1

    n_avs = 0
    n_users = 1

    duration_in_seconds = 0.3

    scenario_id = 1

    # Configure the mocking such that the call to get_vehicle_states_by_scenario_id_at_timestamp returns the expected values
    mock_function_generate_random_initial_state = mocker.patch('controller.controller.MixedTrafficScenarioGenerator.generate_random_initial_state')
    mock_function_generate_random_goal_region = mocker.patch('controller.controller.MixedTrafficScenarioGenerator.generate_random_goal_region')

    def mocked_generate_random_initial_state(driver, goal_region_as_rectangle):
        # Provide ONE initial state, almost at end of the road to Mock Goal Region at the Beginning of the road
        rotation = 2.33
        speed_md = 1.0
        acceleration_m2s = 0.0
        scenario_slope = -1.1
        distance_x = 25
        min_x, min_y = 557.32551, -684.4076
        position_x = min_x - distance_x
        position_y = min_y + (scenario_slope * - distance_x)
        return (None, "ACTIVE", 0, driver.user_id, scenario_id, position_x, position_y, rotation, speed_md,
                   acceleration_m2s)

    def mocked_generate_random_goal_area():
        # Provide ONE goal region
        from commonroad.geometry.shape import Rectangle
        import numpy as np

        orientation = 2.33
        min_x, min_y = 557.32551, -684.4076
        return Rectangle(4.0, 4.0, np.array([min_x, min_y]), orientation)

    mock_function_generate_random_initial_state.side_effect = mocked_generate_random_initial_state
    mock_function_generate_random_goal_region.side_effect = mocked_generate_random_goal_area

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": duration_in_seconds,
            "creator_user_id": user_1_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs,
            #     preassigned_user_ids = set(data["users"].split(',') if "users" in data and len(data["users"]) > 0 else [])
            "users": user_1_id
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Note we expect 201 because the scenario becomes automatically ACTIVE in this case, i.e., no need to waiting for other users to join
        assert response.status_code == 422


def test_create_scenario_with_one_registered_human_driver_on_goal_area(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    scenario_creator_user_id = 1
    scenario_template_id = 1

    n_users = 1
    n_avs = 0
    scenario_duration_in_seconds = 0.3 # Keep it short

    scenario_id = 1

    # Configure the mocking such that the call to get_vehicle_states_by_scenario_id_at_timestamp returns the expected values
    mock_function_generate_random_initial_state = mocker.patch(
        'controller.controller.MixedTrafficScenarioGenerator.generate_random_initial_state')
    mock_function_generate_random_goal_region = mocker.patch(
        'controller.controller.MixedTrafficScenarioGenerator.generate_random_goal_region')

    # Returns overlapping elements
    def mocked_generate_random_initial_state(driver, goal_region_as_rectangle):
        # Provide ONE initial state, almost at end of the road to Mock Goal Region at the Beginning of the road
        rotation = 2.33
        speed_md = 1.0
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
        return Rectangle(4.0, 4.0, np.array([min_x, min_y]), orientation)

    mock_function_generate_random_initial_state.side_effect = mocked_generate_random_initial_state
    mock_function_generate_random_goal_region.side_effect = mocked_generate_random_goal_area

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id],
                                                                            scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_data = {
            "scenario_id": scenario_id, # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": scenario_duration_in_seconds,
            "creator_user_id": scenario_creator_user_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs,
            # Preassign the user
            "users": ",".join([str(scenario_creator_user_id)])

        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)

        # Scenario cannot be created
        assert response.status_code == 422