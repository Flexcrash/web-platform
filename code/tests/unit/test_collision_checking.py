
from model.collision_checking import CollisionChecker

from persistence.data_access import VehicleStateDAO
from model.vehicle_state import VehicleState
from model.mixed_traffic_scenario import MixedTrafficScenario
from model.user import User

import pytest

@pytest.fixture
def vehicles_states_and_drivers_generators():

    def generator(v1_position_x, v1_position_y, v1_rotation, v2_position_x, v2_position_y, v2_rotation):
        vehicles_states = []
        # Common Attributes
        timestamp = 1
        status = "ACTIVE"
        scenario_id = 1
        speed_ms = 0.0
        acceleration_m2s = 0.0

        v1_vehicle_state_id, v2_vehicle_state_id = 1, 2
        v1_user_id, v2_user_id = 1, 2



        vehicles_states.append(
            VehicleState(v1_vehicle_state_id, status, timestamp, v1_user_id, scenario_id, v1_position_x, v1_position_y,
                         v1_rotation, speed_ms, acceleration_m2s))
        # Vehicle state of V2
        vehicles_states.append(
            VehicleState(v2_vehicle_state_id, status, timestamp, v2_user_id, scenario_id, v2_position_x, v2_position_y,
                         v2_rotation, speed_ms, acceleration_m2s))

        drivers = []
        drivers.append(User(v1_user_id, "username", "email", "password"))
        drivers.append(User(v2_user_id, "username", "email", "password"))

        return vehicles_states, drivers

    return generator


def test_collisions_reported_for_two_overlapping_vehicles(mocker, vehicles_states_and_drivers_generators):

    # The vehicles exactly overlaps
    v1_position_x, v2_position_x = 0.0, 0.0
    v1_position_y, v2_position_y = 0.0, 0.0
    v1_rotation, v2_rotation = 0.0, 0.0

    vehicles_states, drivers = vehicles_states_and_drivers_generators(v1_position_x, v1_position_y, v1_rotation,
                                                             v2_position_x, v2_position_y, v2_rotation)

    # Configure the mocking such that the call to get_vehicle_states_by_scenario_id_at_timestamp returns the expected values
    mock_function = mocker.patch('persistence.data_access.VehicleStateDAO.get_vehicle_states_by_scenario_id_at_timestamp')
    mock_function.return_value = vehicles_states

    mock_app_config = {}
    mock_app_config["DATABASE_NAME"] = "Bogus"
    mock_app_config["SCENARIO_IMAGES_FOLDER"] = "Bogus"

    collision_checker = CollisionChecker(VehicleStateDAO(mock_app_config))

    scenario = MixedTrafficScenario(1, "name", "description", "created_by", 2, "ACTIVE",
                                    "scenario_template", 10, drivers)

    any_timestamp = 1
    crashed_drivers_with_states = collision_checker.check_for_collisions(scenario, any_timestamp)

    assert len(crashed_drivers_with_states) == 2
    assert drivers[0] in [d for (d,s) in crashed_drivers_with_states]
    assert drivers[1] in [d for (d, s) in crashed_drivers_with_states]


def test_collisions_reported_for_two_vehicles_rotated(mocker, vehicles_states_and_drivers_generators):

    # The vehicles exactly overlaps
    v1_position_x, v2_position_x = 0.0, 0.0
    v1_position_y, v2_position_y = 0.0, 0.0
    # Rotate the second vehicle by 90 deg
    import math
    v1_rotation, v2_rotation = 0.0, math.pi * 0.5

    vehicles_states, drivers = vehicles_states_and_drivers_generators(v1_position_x, v1_position_y, v1_rotation,
                                                             v2_position_x, v2_position_y, v2_rotation)

    # Configure the mocking such that the call to get_vehicle_states_by_scenario_id_at_timestamp returns the expected values
    mock_function = mocker.patch('persistence.data_access.VehicleStateDAO.get_vehicle_states_by_scenario_id_at_timestamp')
    mock_function.return_value = vehicles_states

    mock_app_config = {}
    mock_app_config["DATABASE_NAME"] = "Bogus"
    mock_app_config["SCENARIO_IMAGES_FOLDER"] = "Bogus"

    collision_checker = CollisionChecker(VehicleStateDAO(mock_app_config))

    scenario = MixedTrafficScenario(1, "name", "description", "created_by", 2, "ACTIVE",
                                    "scenario_template", 10, drivers)

    any_timestamp = 1
    crashed_drivers_with_states = collision_checker.check_for_collisions(scenario, any_timestamp)

    assert len(crashed_drivers_with_states) == 2
    assert drivers[0] in [d for (d,s) in crashed_drivers_with_states]
    assert drivers[1] in [d for (d, s) in crashed_drivers_with_states]


def test_collisions_reported_for_two_partially_overlapping_vehicles(mocker, vehicles_states_and_drivers_generators):

    # The vehicles overlaps
    from configuration.config import VEHICLE_WIDTH, VEHICLE_LENGTH
    v1_position_x, v2_position_x = 0.0, 0.0 + VEHICLE_LENGTH * 0.5
    v1_position_y, v2_position_y = 0.0, 0.0 + VEHICLE_WIDTH * 0.5
    v1_rotation, v2_rotation = 0.0, 0.0

    vehicles_states, drivers = vehicles_states_and_drivers_generators(v1_position_x, v1_position_y, v1_rotation,
                                                             v2_position_x, v2_position_y, v2_rotation)

    # Configure the mocking such that the call to get_vehicle_states_by_scenario_id_at_timestamp returns the expected values
    mock_function = mocker.patch('persistence.data_access.VehicleStateDAO.get_vehicle_states_by_scenario_id_at_timestamp')
    mock_function.return_value = vehicles_states

    mock_app_config = {}
    mock_app_config["DATABASE_NAME"] = "Bogus"
    mock_app_config["SCENARIO_IMAGES_FOLDER"] = "Bogus"

    collision_checker = CollisionChecker(VehicleStateDAO(mock_app_config))

    scenario = MixedTrafficScenario(1, "name", "description", "created_by", 2, "ACTIVE",
                                    "scenario_template", 10, drivers)

    any_timestamp = 1
    crashed_drivers_with_states = collision_checker.check_for_collisions(scenario, any_timestamp)

    assert len(crashed_drivers_with_states) == 2
    assert drivers[0] in [d for (d,s) in crashed_drivers_with_states]
    assert drivers[1] in [d for (d, s) in crashed_drivers_with_states]

def test_shold_collide_but_it_does_not(mocker, vehicles_states_and_drivers_generators):

    # Those values are taken from a failed system test. The Rectangles indeed DO NOT overlap !
    # <collision::RectangleOBB r_x=1.000000 r_y=1.500000 center_x=21.031279 center_y=21.363058>
    # acceleration_m2s = {float} -3.557849871647718e-15
    # position_x = {float} 21.031278567377385
    # position_y = {float} 21.363057754887016
    # rotation = {float} -3.0878530931621313
    # scenario_id = {int} 4
    # speed_ms = {float} 0.0
    # status = {str} 'ACTIVE'
    # timestamp = {int} 6
    # user_id = {int} 1
    # vehicle_state_id = {int} 612
    #
    #
    # <collision::RectangleOBB r_x=1.000000 r_y=1.500000 center_x=24.872606 center_y=21.576690>
    # acceleration_m2s = {float} -1.092187810754453e-13
    # position_x = {float} 24.87260616671392
    # position_y = {float} 21.576690205635856
    # rotation = {float} -3.1466276344870137
    # scenario_id = {int} 4
    # speed_ms = {float} 12.499999999999938
    # status = {str} 'ACTIVE'
    # timestamp = {int} 6
    # user_id = {int} 2
    # vehicle_state_id = {int} 711

    # THOSE ARE OVERLAPPING BUT CC REPORTS THEY ARE NOT!
    v1_position_x, v2_position_x = 21.031278567377385, 24.87260616671392
    v1_position_y, v2_position_y = 21.363057754887016, 21.576690205635856
    v1_rotation, v2_rotation = -3.0878530931621313, -3.1466276344870137

    vehicles_states, drivers = vehicles_states_and_drivers_generators(v1_position_x, v1_position_y, v1_rotation,
                                                             v2_position_x, v2_position_y, v2_rotation)

    # Configure the mocking such that the call to get_vehicle_states_by_scenario_id_at_timestamp returns the expected values
    mock_function = mocker.patch('persistence.data_access.VehicleStateDAO.get_vehicle_states_by_scenario_id_at_timestamp')
    mock_function.return_value = vehicles_states

    mock_app_config = {}
    mock_app_config["DATABASE_NAME"] = "Bogus"
    mock_app_config["SCENARIO_IMAGES_FOLDER"] = "Bogus"

    collision_checker = CollisionChecker(VehicleStateDAO(mock_app_config))

    scenario = MixedTrafficScenario(1, "name", "description", "created_by", 2, "ACTIVE",
                                    "scenario_template", 10, drivers)

    any_timestamp = 1
    crashed_drivers_with_states = collision_checker.check_for_collisions(scenario, any_timestamp)

    assert len(crashed_drivers_with_states) == 2


def test_collisions_is_not_reported_for_two_nonoverlapping_vehicles(mocker, vehicles_states_and_drivers_generators):

    # The vehicles do not overlap
    from configuration.config import VEHICLE_WIDTH, VEHICLE_LENGTH
    v1_position_x, v2_position_x = 0.0, 0.0 + 2 * VEHICLE_WIDTH
    v1_position_y, v2_position_y = 0.0, 0.0 + 2 * VEHICLE_LENGTH
    v1_rotation, v2_rotation = 0.0, 0.0

    vehicles_states, drivers = vehicles_states_and_drivers_generators(v1_position_x, v1_position_y, v1_rotation,
                                                             v2_position_x, v2_position_y, v2_rotation)

    # Configure the mocking such that the call to get_vehicle_states_by_scenario_id_at_timestamp returns the expected values
    mock_function = mocker.patch('persistence.data_access.VehicleStateDAO.get_vehicle_states_by_scenario_id_at_timestamp')
    mock_function.return_value = vehicles_states

    mock_app_config = {}
    mock_app_config["DATABASE_NAME"] = "Bogus"
    mock_app_config["SCENARIO_IMAGES_FOLDER"] = "Bogus"

    collision_checker = CollisionChecker(VehicleStateDAO(mock_app_config))

    scenario = MixedTrafficScenario(1, "name", "description", "created_by", 2, "ACTIVE",
                                    "scenario_template", 10, drivers)

    any_timestamp = 1
    crashed_drivers_with_states = collision_checker.check_for_collisions(scenario, any_timestamp)

    assert len(crashed_drivers_with_states) == 0