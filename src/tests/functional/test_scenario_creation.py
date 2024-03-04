# Define the fixtures for the following test cases
import json

from flask import url_for
from tests.utils import generate_scenario_data

def initial_overlapping_state_generator(n_drivers, scenario_id):
    # All Fixed means Overlapping
    rotation = 2.33
    speed_md = 1.0
    acceleration_m2s = 0.0
    position_x, position_y = 557.32551, -684.4076
    for idx in range(0, n_drivers):
        yield [None, "ACTIVE", 0, None, scenario_id, position_x, position_y, rotation, speed_md,
               acceleration_m2s]


def test_create_scenario_with_one_av_without_scenario_id(flexcrash_test_app_with_a_scenario_template_and_given_users):
    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 1
    n_users = 0
    scenario_duration_in_seconds = 0.5

    scenario_id = None

    preregistered_users = []

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id], scenario_template_id)
    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Assert that the scenario is ACTIVE
        assert response.status_code == 201


def test_create_scenario_with_one_av(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 1
    n_users = 0
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = []

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id], scenario_template_id)
    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Assert that the scenario is ACTIVE
        assert response.status_code == 201


def test_create_scenario_with_two_avs(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
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
        # Assert that the scenario is ACTIVE
        assert response.status_code == 201


def test_create_scenario_with_two_avs_fail_if_initial_speed_is_wrong(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
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

    # Invalid speed
    scenario_data["AV_1_speed"] = 0.0

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code == 422


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
        # Assert that the scenario is ACTIVE
        assert response.status_code == 201


def test_create_scenario_with_one_human_driver(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 0
    n_users = 1
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = []

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id],
                                                                            scenario_template_id)
    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
    # Scenario created, but in WAITING
    assert response.status_code == 202


def test_create_scenario_with_two_human_drivers(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    scenario_creator_user_id = 1
    user_1_id = 10
    user_2_id = 11
    scenario_template_id = 1
    n_avs = 0
    n_users = 2
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = []

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id, user_1_id, user_2_id],
                                                                            scenario_template_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Scenario created, but in WAITING
        assert response.status_code == 202


def test_create_scenario_with_many_human_drivers(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12
    user_3_id = 13
    user_4_id = 14

    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 0
    n_users = 4
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = []

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [scenario_creator_user_id, user_1_id, user_2_id, user_3_id, user_4_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code == 202


def test_create_scenarios_with_existing_users(mocker, flexcrash_test_app_with_a_scenario_template_and_given_users):
    """
    GIVEN the flexcrash application configured for testing (two users, one template)
    WHEN the '/api/scenarios' API is requested (POST) with pre-assigned users
    THEN the response is 201 (Created) and returns a scenario as JSON
    """

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

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [scenario_creator_user_id, user_1_id, user_2_id, user_3_id, user_4_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Assert that this scenario is (already) ACTIVE
        assert response.status_code == 201

        # Assert that the JSON is a valid scenario (this might be an problem if nested resources have missing fields?
        created_scenario_as_dict = json.loads(response.data.decode("utf-8"))
        # TODO This test now fails because some values are missing!

        assert created_scenario_as_dict["created_by"] == scenario_creator_user_id
        assert created_scenario_as_dict["status"] == "ACTIVE"
        assert len(created_scenario_as_dict["drivers"]) == 2


def test_create_mixed_scenario_with_one_av_and_one_human_driver(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12
    user_3_id = 13
    user_4_id = 14

    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 1
    n_users = 1
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = []

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [scenario_creator_user_id, user_1_id, user_2_id, user_3_id, user_4_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code == 202


def test_create_mixed_scenario_with_two_avs_and_one_human_driver(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    scenario_creator_user_id = 1
    scenario_template_id = 1
    n_avs = 2
    n_users = 1
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = []

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [scenario_creator_user_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code == 202


def test_create_mixed_scenario_with_one_av_and_two_human_drivers(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    scenario_creator_user_id = 1
    user_1_id = 11
    user_2_id = 12

    scenario_template_id = 1
    n_avs = 1
    n_users = 2
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = []


    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [scenario_creator_user_id, user_1_id, user_2_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code == 202


def test_create_mixed_scenario_with_two_avs_and_two_human_drivers(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    scenario_creator_user_id = 1
    user_1_id = 11
    user_2_id = 12

    scenario_template_id = 1
    n_avs = 2
    n_users = 2
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = []

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [scenario_creator_user_id, user_1_id, user_2_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code == 202


def test_create_mixed_scenario_with_many_avs_and_many_human_drivers(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12
    user_3_id = 13
    # user_4_id = 14

    scenario_creator_user_id = 1

    scenario_template_id = 1

    # With 5 AV and 4 User the scenario cannot be created because the vehicles cannot be placed on the road
    # With 3 AV and 3 User the scenario cannot be created because vehicles 6 is on the goal area
    # With 2 AV and 3 User the scenario cannot be created because vehicles 6 is on the goal area
    n_avs = 2
    n_users = 3
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = []

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [scenario_creator_user_id, user_1_id, user_2_id, user_3_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code == 202


def test_create_mixed_scenario_with_one_av_and_one_registered_human_driver(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    # Create the app with the factory method
    user_1_id = 11

    scenario_creator_user_id = 1

    scenario_template_id = 1
    n_avs = 1
    n_users = 1
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = [user_1_id]

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [scenario_creator_user_id, user_1_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Note we expect 201 because the scenario becomes automatically ACTIVE in this case, i.e., no need to waiting for other users to join
        assert response.status_code == 201


def test_create_mixed_scenario_with_two_avs_and_one_registered_human_driver(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    # Create the app with the factory method
    user_1_id = 11

    scenario_creator_user_id = 1

    scenario_template_id = 1
    n_avs = 2
    n_users = 1
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = [user_1_id]

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [scenario_creator_user_id, user_1_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Note we expect 201 because the scenario becomes automatically ACTIVE in this case, i.e., no need to waiting for other users to join
        assert response.status_code == 201


def test_create_mixed_scenario_with_one_av_and_two_registered_human_drivers(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):

    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12

    scenario_creator_user_id = 1

    scenario_template_id = 1
    n_avs = 1
    n_users = 2
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = [user_1_id, user_2_id]

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [scenario_creator_user_id, user_1_id, user_2_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Note we expect 201 because the scenario becomes automatically ACTIVE in this case, i.e., no need to waiting for other users to join
        assert response.status_code == 201


def test_create_mixed_scenario_with_two_avs_and_two_registered_human_drivers(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12

    scenario_creator_user_id = 1

    scenario_template_id = 1
    n_avs = 2
    n_users = 2
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = [user_1_id, user_2_id]

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [scenario_creator_user_id, user_1_id, user_2_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Note we expect 201 because the scenario becomes automatically ACTIVE in this case, i.e., no need to waiting for other users to join
        assert response.status_code == 201


def test_create_mixed_scenario_with_one_av_and_one_registered_human_driver_and_one_human_driver(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12

    scenario_creator_user_id = 1

    scenario_template_id = 1
    n_avs = 1
    n_users = 2
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = [user_1_id]

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [scenario_creator_user_id, user_1_id, user_2_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Note we expect 202 because the scenario is not automatically ACTIVE in this case
        assert response.status_code == 202


def test_create_complex_mixed_scenario(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    # Create the app with the factory method
    user_1_id = 11
    user_2_id = 12
    user_3_id = 13

    scenario_creator_user_id = 1

    scenario_template_id = 1
    n_avs = 1
    n_users = 4
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = [user_1_id, user_3_id]

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [scenario_creator_user_id, user_1_id, user_2_id, user_3_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Note we expect 202 because the scenario is not automatically ACTIVE in this case
        assert response.status_code == 202


def test_create_mixed_scenario_with_overlapping_vehicles_fail(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    # Create the app with the factory method
    user_1_id = 11

    scenario_creator_user_id = 1

    scenario_template_id = 1

    n_avs = 1
    n_users = 1
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = [user_1_id]

    # Generate a complete set of data
    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)


    # Generate new initial states of the vehicles to force overlapping
    overlapping_state_gen = initial_overlapping_state_generator(n_avs + n_users, scenario_id)

    initial_state = next(overlapping_state_gen)
    scenario_data["AV_1_x"] = initial_state[5]
    scenario_data["AV_1_y"] = initial_state[6]
    scenario_data["AV_1_speed"] = initial_state[8]

    initial_state = next(overlapping_state_gen)
    scenario_data[f"U_{user_1_id}_x"] = initial_state[5]
    scenario_data[f"U_{user_1_id}_y"] = initial_state[6]
    scenario_data[f"U_{user_1_id}_speed"] = initial_state[8]

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [scenario_creator_user_id, user_1_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Note we expect 201 because the scenario becomes automatically ACTIVE in this case, i.e., no need to waiting for other users to join
        assert response.status_code == 422


# TODO This is not correct, the position of the goal area should be different !
def test_create_mixed_scenario_with_unreacheable_goal_area(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    # Create the app with the factory method
    user_1_id = 11

    scenario_creator_user_id = 1

    scenario_template_id = 1

    n_avs = 0
    n_users = 1
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = [user_1_id]

    # Generate a complete set of data
    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [scenario_creator_user_id, user_1_id],
        scenario_template_id)


    # def mocked_generate_random_initial_state(driver, goal_region_as_rectangle):
    #     # Provide ONE initial state, almost at end of the road to Mock Goal Region at the Beginning of the road
    #     rotation = 2.33
    #     speed_md = 1.0
    #     acceleration_m2s = 0.0
    #     scenario_slope = -1.1
    #     distance_x = 25
    #     min_x, min_y = 557.32551, -684.4076
    #     position_x = min_x - distance_x
    #     position_y = min_y + (scenario_slope * - distance_x)
    #     return (None, "ACTIVE", 0, driver.user_id, scenario_id, position_x, position_y, rotation, speed_md,
    #                acceleration_m2s)
    # Force a specific initial state for the vehicle
    scenario_data[f"U_{user_1_id}_x"] = 557.32551
    scenario_data[f"U_{user_1_id}_y"] = -684.4076
    scenario_data[f"U_{user_1_id}_speed"] = 1.0

    # def mocked_generate_random_goal_area():
    #     # Provide ONE goal region
    #     from commonroad.geometry.shape import Rectangle
    #     import numpy as np
    #
    #     orientation = 2.33
    #     min_x, min_y = 557.32551, -684.4076
    #     return Rectangle(4.0, 4.0, np.array([min_x, min_y]), orientation)
    # Force a specific goal region that is unreacheable
    scenario_data[f"U_{user_1_id}_goal_x"] = 557.32551
    scenario_data[f"U_{user_1_id}_goal_y"] = -684.4076

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code == 422


def test_create_scenario_with_one_registered_human_driver_on_goal_area(flexcrash_test_app_with_a_scenario_template_and_given_users, mocker):
    # Create the app with the factory method
    user_1_id = 11

    scenario_creator_user_id = 1

    scenario_template_id = 1

    n_avs = 0
    n_users = 1
    scenario_duration_in_seconds = 0.5
    scenario_id = 1
    preregistered_users = [user_1_id]

    # Generate a complete set of data
    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [scenario_creator_user_id, user_1_id],
        scenario_template_id)

    # Returns overlapping elements
    # def mocked_generate_random_initial_state(driver, goal_region_as_rectangle):
    #     # Provide ONE initial state, almost at end of the road to Mock Goal Region at the Beginning of the road
    #     rotation = 2.33
    #     speed_md = 1.0
    #     acceleration_m2s = 0.0
    #     position_x, position_y = 557.32551, -684.4076
    #     return (None, "ACTIVE", 0, driver.user_id, scenario_id, position_x, position_y, rotation, speed_md,
    #             acceleration_m2s)
    scenario_data[f"U_{user_1_id}_x"] = 557.32551
    scenario_data[f"U_{user_1_id}_y"] = -684.4076
    scenario_data[f"U_{user_1_id}_speed"] = 1.0

    # def mocked_generate_random_goal_area():
    #     # Provide ONE goal region
    #     from commonroad.geometry.shape import Rectangle
    #     import numpy as np
    #
    #     orientation = 2.33
    #     min_x, min_y = 557.32551, -684.4076
    #     return Rectangle(4.0, 4.0, np.array([min_x, min_y]), orientation)
    # Force a specific goal region that is where the car is
    scenario_data[f"U_{user_1_id}_goal_x"] = 557.32551
    scenario_data[f"U_{user_1_id}_goal_y"] = -684.4076

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        # Scenario cannot be created
        assert response.status_code == 422