import os

import pytest

from model.user import User
import numpy as np


def test_deserialize_vehicle_states():
    json_string = """[{"acceleration_m2s":null,"position_x":null,"position_y":null,"rotation":null,"scenario_id":1,"speed_ms":null,"status":"PENDING","timestamp":1,"user_id":2,"vehicle_state_id":10},
    {"acceleration_m2s":null,"position_x":null,"position_y":null,"rotation":null,"scenario_id":1,"speed_ms":null,"status":"PENDING","timestamp":2,"user_id":2,"vehicle_state_id":11},
    {"acceleration_m2s":null,"position_x":null,"position_y":null,"rotation":null,"scenario_id":1,"speed_ms":null,"status":"PENDING","timestamp":3,"user_id":2,"vehicle_state_id":12},
    {"acceleration_m2s":0.0,"position_x":610.3065999999999,"position_y":-768.156095,"rotation":-2.857257599723069,"scenario_id":1,"speed_ms":12.060355333235734,"status":"ACTIVE","timestamp":0,"user_id":2,"vehicle_state_id":20}]\n"""

    from model.vehicle_state import VehicleStateSchema
    import json
    schema = VehicleStateSchema(many=True)
    # We need to convert the string into a JSON object first !
    schema.load(json.loads(json_string))


def test_user_attributes():
    """
    GIVEN a User model
    WHEN a new User is created
    THEN check username, email, password, user_id are defined correctly
    """
    username = "foo"
    email = "foo@bar.com"
    password = "CLEAR"
    user_id = 1

    tuple = (user_id, username, email, password)
    user = User(*tuple)

    assert user.username == username
    assert user.email == email
    assert user.password == password
    assert user.user_id == user_id


def test_generate_scenario_template_image(tmp_path, xml_scenario_template):
    from configuration.config import TEMPLATE_IMAGES_FOLDER
    from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate, generate_static_image

    # Create a temporary directory to store the generated image
    temp_output_folder = tmp_path / TEMPLATE_IMAGES_FOLDER
    temp_output_folder.mkdir(parents=True)

    # Create a template
    template_id, name, description, xml = 1, "test", None, xml_scenario_template
    scenario_template = MixedTrafficScenarioTemplate(template_id, name, description, xml)
    generated_image_path = generate_static_image(temp_output_folder, scenario_template)

    # Assess that the file exists and has size greater than zero.
    assert os.path.getsize(generated_image_path) > 0

@pytest.mark.skip(reason="Manually define a suitable Goal Region")
def test_generate_scenario_image(tmp_path, xml_scenario_template, mixed_traffic_scenario_dao):
    from commonroad.geometry.shape import Rectangle

    # from configuration.config import SCENARIO_IMAGES_FOLDER
    from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate
    from model.mixed_traffic_scenario import MixedTrafficScenario, generate_embeddable_html_snippet
    from controller.controller import MixedTrafficScenarioGenerator
    from model.user import User
    from model.vehicle_state import VehicleState

    # Create a temporary directory to store the generated image
    temp_output_folder = tmp_path / "scenario_images"
    temp_output_folder.mkdir(parents=True)

    # Create a template
    template_id, name, description, xml = 1, "test", None, xml_scenario_template
    scenario_template = MixedTrafficScenarioTemplate(template_id, name, description, xml)

    # Create a scenario with one Driver
    user_id, username, email, password = 1, "Bar", "foo", "1234"
    user_1 = User(user_id, username, email, password)

    scenario_id, name, description, created_by, max_players = 1, "test", None, user_1, 1
    status, scenario_template, duration = "ACTIVE", scenario_template, 5

    focus_on_driver = user_1
    drivers = [user_1]

    scenario = MixedTrafficScenario(scenario_id, name, description, created_by, max_players,
                                    status, scenario_template, duration, drivers)



    mixed_traffic_scenario = scenario
    length = 5.0
    width = 3.0
    dist_to_end = 10.0  # m
    min_initial_speed = 0.1  # m/s
    max_initial_speed = 10.0  # m/s
    # Random one.
    goal_region_as_rectangle = Rectangle(10.0, 4.0, np.array([0.0, 0.0]))

    generator = MixedTrafficScenarioGenerator(mixed_traffic_scenario, length, width, dist_to_end, min_initial_speed, max_initial_speed, mixed_traffic_scenario_dao)
    vehicle_state = VehicleState(*generator.generate_random_initial_state(user_1, goal_region_as_rectangle))

    scenario_states = [ vehicle_state ]
    html_snippet = generate_embeddable_html_snippet(temp_output_folder, mixed_traffic_scenario, scenario_states, focus_on_driver)

    # Assess that the file exists and has size greater than zero.
    assert os.path.getsize(html_snippet) > 0




