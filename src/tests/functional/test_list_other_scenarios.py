from flask import url_for
from tests.utils import generate_scenario_data
from persistence.mixed_scenario_data_access import MixedTrafficScenarioDAO


def test_creating_scenarios_with_no_preregistered_users_should_not_be_listed_among_other_scenarios(
        flexcrash_test_app_with_a_scenario_template_and_given_users,
        mocker):
    """
    Case 1 at #267
        - User2 creates a new scenario with two drivers and no pre-registered users
        - User1 joins the scenario
        - User2 joins the scenario
        - User1 lists "Other Scenarios"
    The scenario should NOT be listed among the User1 other active scenarios
    """

    user_1_id = 10
    user_2_id = 11

    scenario_creator_user_id = user_2_id

    scenario_template_id = 1
    n_avs = 0
    n_users = 2
    scenario_duration_in_seconds = 0.5

    scenario_id = 1
    preregistered_users = []

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id, user_2_id],
        scenario_template_id)

    # Create the scenario
    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code < 300

    # User 1 Joins the scenario
    with flask_app.test_client() as test_client:
        user_data = {
            "user_id": user_1_id
        }
        response = test_client.post(url_for("api.scenarios.create_driver", scenario_id=scenario_id),
                                    data=user_data)
        assert response.status_code < 300

    # User 2 Joins the scenario
    with flask_app.test_client() as test_client:
        user_data = {
            "user_id": user_2_id
        }
        response = test_client.post(url_for("api.scenarios.create_driver", scenario_id=scenario_id),
                                    data=user_data)
        assert response.status_code < 300

    # Assert that listing other scenarios should be empty for user1 and user2
    scenario_dao = MixedTrafficScenarioDAO(flask_app.config)

    scenario_active_objects = scenario_dao.get_all_other_active_custom_scenarios(user_id=user_1_id)
    assert len(scenario_active_objects) == 0

    scenario_done_objects = scenario_dao.get_all_other_closed_custom_scenarios(user_id=user_1_id)
    assert len(scenario_done_objects) == 0


def test_creating_scenarios_with_no_preregistered_users_should_not_be_listed_among_other_scenarios(
        flexcrash_test_app_with_a_scenario_template_and_given_users,
        mocker):
    """
    Case 2 at #267
        - User2 creates a new scenario with two drivers and pre-registered User1
        - User2 joins the scenario
        - User1 lists "Other Scenarios"
    The scenario should NOT be listed among the User1 other active scenarios
    """

    user_1_id = 10
    user_2_id = 11

    scenario_creator_user_id = user_2_id

    scenario_template_id = 1
    n_avs = 0
    n_users = 2
    scenario_duration_in_seconds = 0.5

    scenario_id = 1
    preregistered_users = [user_1_id]

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id, user_2_id],
        scenario_template_id)

    # Create the scenario
    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code < 300

    # User 2 Joins the scenario
    with flask_app.test_client() as test_client:
        user_data = {
            "user_id": user_2_id
        }
        response = test_client.post(url_for("api.scenarios.create_driver", scenario_id=scenario_id),
                                    data=user_data)
        assert response.status_code < 300

    # Assert that listing other scenarios should be empty for user1 and user2
    scenario_dao = MixedTrafficScenarioDAO(flask_app.config)

    scenario_active_objects = scenario_dao.get_all_other_active_custom_scenarios(user_id=user_1_id)
    assert len(scenario_active_objects) == 0

    scenario_done_objects = scenario_dao.get_all_other_closed_custom_scenarios(user_id=user_1_id)
    assert len(scenario_done_objects) == 0




def test_creating_scenarios_with_preregistered_users_should_not_be_listed_among_other_scenarios(
        flexcrash_test_app_with_a_scenario_template_and_given_users,
        mocker):
    """
    Case 3 at #267
        - User2 creates a new scenario with two drivers and pre-registered users User1, User2
        - User1 lists "Other Scenarios"

    The scenario should NOT be listed among the User1 other active scenarios
    """

    user_1_id = 10
    user_2_id = 11

    scenario_creator_user_id = user_2_id

    scenario_template_id = 1
    n_avs = 0
    n_users = 2
    scenario_duration_in_seconds = 0.5

    scenario_id = 1
    preregistered_users = [user_1_id, user_2_id]

    scenario_data = generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users,
                                            scenario_duration_in_seconds, scenario_id, preregistered_users)

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users(
        [user_1_id, user_2_id],
        scenario_template_id)

    with flask_app.test_client() as test_client:
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code < 300

    # Assert that listing other scenarios should be empty for user1 and user2

    scenario_dao = MixedTrafficScenarioDAO(flask_app.config)

    scenario_active_objects = scenario_dao.get_all_other_active_custom_scenarios(user_id=user_1_id)
    assert len(scenario_active_objects) == 0

    scenario_done_objects = scenario_dao.get_all_other_closed_custom_scenarios(user_id=user_1_id)
    assert len(scenario_done_objects) == 0
