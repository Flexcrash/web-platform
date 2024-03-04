import math
import numpy as np
import pytest

from visualization.mixed_traffic_scenario import generate_picture
from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.common.file_writer import CommonRoadFileWriter
from commonroad.scenario.scenario import State
from tests.utils import initial_full_state

from model.mixed_traffic_scenario import MixedTrafficScenario
from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate
from model.driver import Driver

from controller.controller import MixedTrafficScenarioGenerator

def test_visualize_vehicle(tmp_path, xml_scenario_template_as_file):


    output_folder = tmp_path
    commonroad_scenario, planning_problem_set = CommonRoadFileReader(filename=xml_scenario_template_as_file).open()
    mixed_traffic_scenario_duration = 5
    mixed_traffic_scenario_scenario_id = 1

    # 1 Driver - but 4 timestamps
    state_gen = initial_full_state(4)

    # Returns a namedtuple
    _scenario_state = [next(state_gen), next(state_gen), next(state_gen), next(state_gen)]

    user_id = 1
    scenario_state = []
    for t, s in enumerate(_scenario_state):
        scenario_state.append(s._replace(user_id=user_id, timestamp=t))

    focus_on_driver_user_id = None
    goal_region_as_rectangle = None

    # Generate the PNG
    render_png = True
    figsize = (16, 6)

    generate_picture(render_png, figsize,
                     output_folder, commonroad_scenario, mixed_traffic_scenario_duration,
                     mixed_traffic_scenario_scenario_id,
                     scenario_state,
                     focus_on_driver_user_id, goal_region_as_rectangle)

    pass


# Ensure the ORM and the rest is setup
@pytest.mark.skip("Manual test. Requires showing plots")
def test_visualize_vehicle_along_the_road(tmp_path, flexcrash_test_app, xml_scenario_template_as_file):

    # rotation_angle = 0.0
    # initial_position = (
    #     (569.1732 + 571.58942) * 0.5,
    #     (-698.71446 -696.18229) * 0.5
    # )

    rotation_angle = math.pi*0.5
    initial_position = (683, 556)

    rotation_angle = math.pi
    initial_position = (-556, 683)

    rotation_angle = math.pi *1.5
    initial_position = (-683+2.0, -556)

    output_file = tmp_path / "output.xml"

    # Generate and rotate the scenario
    commonroad_scenario, planning_problem_set = CommonRoadFileReader(xml_scenario_template_as_file).open()

    commonroad_scenario.translate_rotate(translation=np.array((0.0, 0.0)), angle=rotation_angle)

    CommonRoadFileWriter(commonroad_scenario, planning_problem_set,
                         author="Foo",
                         affiliation="Bar",
                         source="Bar",
                         tags=[]
                         ).write_to_file(output_file)

    # Now read the rotated one to check its' ok
    commonroad_scenario, _ = CommonRoadFileReader(output_file).open()
    # from commonroad.visualization.mp_renderer import MPRenderer
    # import matplotlib.pyplot as plt
    #
    # fig, ax = plt.subplots(figsize=(10,10))
    #
    # rnd = MPRenderer(ax=ax)
    # commonroad_scenario.draw(rnd)
    # rnd.render()
    # plt.show()
    # VISUALIZE TO SEE WHERE TO PUT THE INITIAL POSITION

    with open(output_file, "r") as rotated_template_file:
        xml_scenario_template = rotated_template_file.read()

    # The generator (is the class under test)
    scenario_template = MixedTrafficScenarioTemplate(
        template_id=1,
        name = "test",
        description = "",
        xml = xml_scenario_template
    )
    driver_1 = Driver(
        driver_id=1,
        user_id=1,
        scenario_id=1,
        # Fix this
        initial_position = initial_position,
        initial_speed = 1.0
    )

    mixed_traffic_scenario = MixedTrafficScenario(
        scenario_id = 1,
        name = "foo",
        description = "",
        created_by = 1,
        max_players = 1, n_avs=0, n_users=1,
        status = "ACTIVE",
        template_id = 1,
        scenario_template = scenario_template,
        duration = 1.0,
        drivers = [ driver_1 ]
    )

    goal_region_length = 10
    goal_region_width = 4
    dist_to_end = 10
    min_initial_speed, max_initial_speed = 1.0, 20.0
    mixed_traffic_scenario_dao = None

    generator = MixedTrafficScenarioGenerator(mixed_traffic_scenario, goal_region_length, goal_region_width, dist_to_end, min_initial_speed, max_initial_speed,
    mixed_traffic_scenario_dao)

    initial_states = generator.create_initial_states()
    initial_state = initial_states[1]
    commonroad_state = State(**{
        "time_step": 0,
        "position": np.array([initial_state[5], initial_state[6]]),
        "orientation": initial_state[7],
        "velocity": 10.0,
        "acceleration": 0.0,
        "yaw_rate": 0,
        "slip_angle": 0
    })

    # Visual inspection
    def _debug_plot():
        from commonroad.visualization.mp_renderer import MPRenderer
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10,10))
        rnd = MPRenderer(ax=ax)
        # self.lanelet_network.draw(rnd)
        commonroad_scenario.draw(rnd)
        commonroad_state.draw(rnd, draw_params={"state" : {"draw_arrow" : True}})
        rnd.render()
        plt.plot(initial_position[0], initial_position[1], "*", color="white", zorder=100)
        plt.show()

    _debug_plot()

    pass
    # TODO Validate manually - or try to use a planner to see whether the goal region is reachable or the direction is correct