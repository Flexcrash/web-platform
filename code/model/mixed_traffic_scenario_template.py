import tempfile
import os
import numpy as np

from marshmallow import Schema, fields, post_load
import matplotlib.pyplot as plt

from model.vehicle_state import VehicleState
# from commonroad.scenario.scenario import Scenario
# from commonroad.scenario.obstacle import DynamicObstacle
# from commonroad.planning.planning_problem import PlanningProblem
from commonroad.visualization.mp_renderer import MPRenderer
from commonroad.common.file_reader import CommonRoadFileReader

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



class MixedTrafficScenarioTemplate:

    def __init__(self, template_id, name, description, xml):
        self.template_id = template_id
        self.name = name
        self.description = description
        # Those are Scenario Attributes
        # self.creator_id = creator_id
        # self.maxplayers = maxplayers
        self.xml = xml

    def get_file_name(self):
        return "{}.png".format(self.template_id)

    def as_commonroad_scenario(self):
        # TODO Find a workaround to avoid using temporary files
        # Note: we need this specific code to avoid issues in Windows
        filename = None
        with tempfile.NamedTemporaryFile("w", delete=False) as temp_filename:
            # file will not be deleted after exec, so we need to keep the name around and do it ourselves
            temp_filename.write(self.xml)
            # Also, on windows this file does not allowed to be read in the context manager
            filename = temp_filename.name

        try:
            commonroad_file_reader = CommonRoadFileReader(filename)
            commonroad_scenario, _ = commonroad_file_reader.open()
            return commonroad_scenario
        finally:
            if filename:
                os.remove(filename)


class TrainingScenarioTemplate():

    def __init__(self, name, description, based_on, duration, goal_region_as_rectangle,
                 initial_ego_position_x, initial_ego_position_y,
                 initial_ego_rotation,
                 initial_ego_speed_ms, initial_ego_acceleration_m2s,
                 n_avs):
        self.name = name
        self.description = description
        self.based_on = based_on
        self.duration = duration
        self.goal_region_as_rectangle = goal_region_as_rectangle
        self.initial_ego_position_x = initial_ego_position_x
        self.initial_ego_position_y = initial_ego_position_y
        self.initial_ego_rotation = initial_ego_rotation
        self.initial_ego_speed_ms = initial_ego_speed_ms
        self.initial_ego_acceleration_m2s = initial_ego_acceleration_m2s
        self.n_avs = n_avs

    def get_file_name(self):
        return "training_{}.png".format(self.name)

    def generate_scenario_data_for(self, trainee_id):
        initial_state_as_dict = {
            "position_x": self.initial_ego_position_x,
            "position_y": self.initial_ego_position_y,
            "rotation": self.initial_ego_rotation,
            "speed_ms": self.initial_ego_speed_ms,
            "acceleration_m2s": self.initial_ego_acceleration_m2s
        }
        goal_region_as_rectangle = self.goal_region_as_rectangle

        training_scenario_data_as_dict = {
            "template_id": self.based_on.template_id,
            "duration": self.duration,
            "creator_user_id": trainee_id,
            "name": f"training-on-{self.name}",
            # TODO Shouldn't be ALWAYS 1
            "n_users": 1,
            "n_avs": self.n_avs,
            "users": trainee_id
        }

        return training_scenario_data_as_dict, initial_state_as_dict, goal_region_as_rectangle


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


def generate_static_image(output_folder, scenario_template):

    initial_state = None
    goal_region_as_rectangle = None
    duration = None
    mixed_traffic_scenario_template = None

    # Training Scneario is just a template with initial state, duration, goal area
    if type(scenario_template) == TrainingScenarioTemplate:
        mixed_traffic_scenario_template = scenario_template.based_on
        # vehicle_state_id, status, timestamp, user_id, scenario_id, position_x, position_y, rotation, speed_ms, acceleration_m2s
        user_id = 0
        scenario_id = 0
        initial_state = VehicleState(None, None, 0, user_id, scenario_id,
                                     scenario_template.initial_ego_position_x,
                                     scenario_template.initial_ego_position_y,
                                     scenario_template.initial_ego_rotation,
                                     scenario_template.initial_ego_speed_ms,
                                     scenario_template.initial_ego_acceleration_m2s)
        goal_region_as_rectangle = scenario_template.goal_region_as_rectangle
        duration = scenario_template.duration
    else:
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


class MixedTrafficScenarioTemplateSchema(Schema):
    """ This class is used to serialize/validate Python objects using Marshmallow """

    template_id = fields.Integer()
    name = fields.String()
    description = fields.String()
    xml = fields.String(required=False, allow_none=True)

    @post_load
    def make_mixed_traffic_scenario_template(self, data, **kwargs):
        return MixedTrafficScenarioTemplate(**data)


class TrainingScenarioTemplateSchema(Schema):
    """ This class is used to serialize/validate Python objects using Marshmallow """

    name = fields.String()
    description = fields.String()
    based_on = fields.Nested(MixedTrafficScenarioTemplateSchema(exclude=["xml"]), required=True)
    duration = fields.Float()

    # For the moment do not report all the details!
    # goal_region_as_rectangle = None # Nested?
    # initial_ego_position_x, initial_ego_position_y,
    # initial_ego_rotation,
    # initial_ego_speed_ms, initial_ego_acceleration_m2s,
    # n_avs)

    # @post_load
    # def make_training_scenario_template(self, data, **kwargs):
    #     return MixedTrafficScenarioTemplate(**data)

