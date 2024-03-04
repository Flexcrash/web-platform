import matplotlib.pyplot as plt
import os

import numpy as np

from commonroad.visualization.mp_renderer import MPRenderer

from commonroad.geometry.shape import Rectangle

from commonroad.scenario.obstacle import DynamicObstacle, ObstacleType
from commonroad.scenario.trajectory import Trajectory, State
from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.planning.goal import GoalRegion
from commonroad.common.util import Interval

# Color Schema
from matplotlib.cm import get_cmap
_name = "Accent"
_cmap = get_cmap(_name)  # type: matplotlib.colors.ListedColormap
# TODO Those must be HEX Strings?
_vehicle_colors = _cmap.colors  # type: list
_default_vehicle_color = "#505D86"


def generate_static_image(output_folder, scenario_template):

    initial_state = None
    goal_region_as_rectangle = None
    duration = None
    mixed_traffic_scenario_template = None

    # Training Scneario is just a template with initial state, duration, goal area
    # if type(scenario_template) == TrainingScenarioTemplate:
    #     mixed_traffic_scenario_template = scenario_template.based_on
    #     # vehicle_state_id, status, timestamp, user_id, scenario_id, position_x, position_y, rotation, speed_ms, acceleration_m2s
    #     user_id = 0
    #     scenario_id = 0
    #     initial_state = VehicleState(None, None, 0, user_id, scenario_id,
    #                                  scenario_template.initial_ego_position_x,
    #                                  scenario_template.initial_ego_position_y,
    #                                  scenario_template.initial_ego_rotation,
    #                                  scenario_template.initial_ego_speed_ms,
    #                                  scenario_template.initial_ego_acceleration_m2s)
    #     goal_region_as_rectangle = scenario_template.goal_region_as_rectangle
    #     duration = scenario_template.duration
    # else:
    mixed_traffic_scenario_template = scenario_template

    commonroad_scenario = mixed_traffic_scenario_template.as_commonroad_scenario()

    fig, ax = plt.subplots(figsize=(12, 9))

    try:
        # The renderer uses the gca... I hope this does not break when used in flask...
        rnd = MPRenderer(ax=ax)

        commonroad_scenario.lanelet_network.draw(rnd)

        if initial_state:
            add_vehicle_as_rectangle(rnd, initial_state, _default_vehicle_color)
        if goal_region_as_rectangle:
            add_goal_area(rnd, goal_region_as_rectangle, duration, _default_vehicle_color)

        # Plot to the file system, assumes the folder exists
        plt_path = os.path.join(output_folder, scenario_template.get_file_name())
        rnd.render(show=False, filename=plt_path)

        # Return the path
        return plt_path
    finally:
        plt.close(fig)

def add_vehicle_as_rectangle(rnd, vehicle_state, facecolor):
    # Size of the rectangle representing the car.
    # TODO Link this to the app configuration
    dynamic_obstacle_shape = Rectangle(width=1.8, length=4.3)

    # The issue is that commonroad 2022.4 removes State and introduces InitialState so we downgraded
    dynamic_obstacle_initial_state = State(position=np.array([vehicle_state.position_x, vehicle_state.position_y]),
                                           velocity=vehicle_state.speed_ms,
                                           orientation=vehicle_state.rotation,
                                           time_step=vehicle_state.timestamp)
    # Since this is only a state, we might not need any state list
    dynamic_obstacle_prediction = TrajectoryPrediction(
        Trajectory(dynamic_obstacle_initial_state.time_step, [dynamic_obstacle_initial_state]),
        dynamic_obstacle_shape)

    dynamic_obstacle_id = vehicle_state.user_id
    dynamic_obstacle_type = ObstacleType.CAR
    dynamic_obstacle = DynamicObstacle(dynamic_obstacle_id,
                                       dynamic_obstacle_type,
                                       dynamic_obstacle_shape,
                                       dynamic_obstacle_initial_state,
                                       dynamic_obstacle_prediction)

    vehicle_data = {
        "vehicle_shape": {
            "occupancy": {
                "shape": {
                    "rectangle": {
                        "facecolor": facecolor,
                        "edgecolor": facecolor,
                        "zorder": 50,
                        "opacity": 1
                    }
                }
            }
        }
    }

    # The states are ordered by time_steps
    dynamic_obstacle.draw(rnd, draw_params={"time_begin": dynamic_obstacle.initial_state.time_step,
                                            "dynamic_obstacle": vehicle_data})


def add_goal_area(rnd, goal_region_as_rectangle, duration, facecolor):
    goal_state_list = [State(position=goal_region_as_rectangle, time_step=Interval(0, duration))]
    commonroad_goal_region = GoalRegion(goal_state_list)
    draw_params = {'goal_region':
                       {'shape':
                            {'rectangle':
                                 {'facecolor': facecolor,
                                  'opacity': 0.5}
                             }
                        }
                   }
    commonroad_goal_region.draw(rnd, draw_params=draw_params)
