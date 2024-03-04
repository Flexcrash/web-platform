import pytest
from flask import url_for

from persistence.vehicle_state_data_access import VehicleStateDAO
from persistence.mixed_scenario_data_access import MixedTrafficScenarioDAO
from tests.utils import generate_scenario_data

@pytest.mark.skip("We have no way to simulate or wait for the scenario to be automatically completed")
def test_get_max_duration(flexcrash_test_app_with_a_scenario_template_and_given_users):
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
        # At this point, the scenario should be ACTIVE
        assert response.status_code == 201

    scenario_dao = MixedTrafficScenarioDAO(flask_app.config)
    mixed_traffic_scenario = scenario_dao.get_scenario_by_scenario_id(scenario_id)

    dao = VehicleStateDAO(flask_app.config, scenario_dao)

    max_timestamp = dao.get_max_timestamp_in_scenario(mixed_traffic_scenario)

    assert max_timestamp == 5

