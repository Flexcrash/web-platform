from persistence.user_data_access import UserDAO
from persistence.mixed_scenario_template_data_access import MixedTrafficScenarioTemplateDAO
from persistence.mixed_scenario_data_access import MixedTrafficScenarioDAO
from persistence.driver_data_access import DriverDAO
from persistence.vehicle_state_data_access import VehicleStateDAO

from model.user import User
from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate
from model.mixed_traffic_scenario import MixedTrafficScenario
from model.driver import Driver
from model.vehicle_state import VehicleState

from commonroad.geometry.shape import Rectangle
import numpy as np


def drive_straight_scenario_generation():
    goal_region_as_rectangle = Rectangle(10.0, 4.0, np.array([56.004933068235665,14.764451734398548]), -0.13799792241859862)
    training_scenario_template_data = {
        "name": "drive_straight",
        "description": "Keep driving until you reach the goal area",
        "based_on": 3,  # template_id = 3
        "duration": 2.0,  # in seconds == 20 steps
        #
        "goal_region_as_rectangle": goal_region_as_rectangle,
        #
        "initial_ego_position_x": -5.60915,
        "initial_ego_position_y": 13.0146,
        "initial_ego_rotation": 0.201155139700799,
        "initial_ego_speed_ms": 18.2720660179498,
        "initial_ego_acceleration_m2s": 0.0,
        #
        "n_avs": 0,
    }

    return training_scenario_template_data


def switch_lane():
    """

    :param user_id:
    :return:
    """
    goal_region_as_rectangle = Rectangle(10.0, 4.0, np.array([55.40048306823568, 10.412701734398574]),-0.13799792241860429)

    training_scenario_template_data = {
        "name": "switch_lane",
        "description": "Start from the left-most lane, move to the next lane on the right, where the goal region is",
        "based_on": 4,  # template_id = 3
        "duration": 2.0,  # in seconds == 20 steps
        #
        "goal_region_as_rectangle": goal_region_as_rectangle,
        #
        "initial_ego_position_x": 18.19635,
        "initial_ego_position_y": 16.8056,
        "initial_ego_rotation": 0.0554936791189995,
        "initial_ego_speed_ms": 31.1655473324561,
        "initial_ego_acceleration_m2s": 0.0,
        #
        "n_avs": 0,
    }

    return training_scenario_template_data


def setup_testing_database(app):
    """
    Setup the testing database used for manual testing. NOTE: Silently capture errors!

    :param app:
    :return:
    """
    user_dao = UserDAO()
    try:
        user_dao.create_new_user({"user_id": 1, "username":"one", "email":"one@email", "password":"1234"})
        user_dao.create_new_user({"user_id": 2, "username": "two", "email": "two@email", "password": "1234"})
        user_dao.create_new_user({"user_id": 3, "username": "three", "email": "three@email", "password": "1234"})
    except:
        pass
    # Enforce Template_ID
    template_files = [(1, "./tests/scenario_templates/template_1.xml"),
                      (2, "./tests/scenario_templates/template_2.xml"),
                      (3, "./tests/scenario_templates/template_3.xml"),
                      (4, "./tests/scenario_templates/template_4.xml")]

    scenario_template_dao = MixedTrafficScenarioTemplateDAO(app.config)
    for (template_id, template_file) in template_files:
        with open(template_file, "r") as file:
            scenario_template_data = {"name": f"template_{template_id}",
                                      "xml": file.read(),
                                      "description": f"Testing Template {template_id}",
                                      "template_id": template_id
                                      }
        try:
            # We need to call this to enfore the creation of the image
            scenario_template_dao.create_new_template(scenario_template_data)
        except:
            pass

