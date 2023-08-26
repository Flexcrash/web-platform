import logging
import time

import numpy as np
import tempfile
import os

import mpld3
import matplotlib.pyplot as plt

from typing import List, Optional

from marshmallow import Schema, fields, post_load

from model.user import UserSchema, User
from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplateSchema

from frontend.mpld3_plugins import TrajectoryView, AllTrajectoriesView, ZoomEgoCarPlugin

from commonroad.geometry.shape import Rectangle

from commonroad.visualization.mp_renderer import MPRenderer
from commonroad.common.file_reader import CommonRoadFileReader

from commonroad.planning.goal import GoalRegion
from commonroad.planning.planning_problem import PlanningProblem

from commonroad.common.util import Interval

from matplotlib.cm import get_cmap

_name = "Accent"
_cmap = get_cmap(_name)  # type: matplotlib.colors.ListedColormap
# TODO Those must be HEX Strings?
_vehicle_colors = _cmap.colors  # type: list
_default_vehicle_color = "#505D86"

# import necessary classes from different modules
from commonroad.scenario.obstacle import DynamicObstacle, ObstacleType
from commonroad.scenario.trajectory import Trajectory, State
from commonroad.prediction.prediction import TrajectoryPrediction

from shapely.geometry import Point
# Controls
# TODO: Is this the overall number or the number of each batch?
VISIBLE_TRAJECTORIES = 100

from configuration.config import VEHICLE_WIDTH, VEHICLE_LENGTH

# Here we need to have already all the states since the model cannot use DAO object !

def generate_embeddable_html_snippet(output_folder, mixed_traffic_scenario, scenario_state,
                                     focus_on_driver=None, goal_region_as_rectangle=None):
    # Generate the PNG
    render_png = True
    figsize = (16, 6)
    generate_picture(render_png, figsize,
                     output_folder, mixed_traffic_scenario, scenario_state,
                                     focus_on_driver, goal_region_as_rectangle)
    # Generate the HTML
    render_png = False
    figsize = (8, 3)
    generate_picture(render_png, figsize,
                     output_folder, mixed_traffic_scenario, scenario_state,
                     focus_on_driver, goal_region_as_rectangle)


def generate_picture(render_png: bool, figsize, # Tuple(Number, Number)?
                     output_folder, mixed_traffic_scenario, scenario_state,
                                     focus_on_driver=None, goal_region_as_rectangle=None):
    """
    Render the provided states of the given scenario, possibly focusing on the given driver.
    Focusing means that the driver's vehicle is highlighted while the others have the default color

    :param output_folder:
    :param mixed_traffic_scenario:
    :param scenario_state: the list of vehicle states of the scenario at the given timestamp
    :param focus_on_driver:
    :return:
    """

    # If focus on driver is active, so must be the goal region
    # Store the ego state in a temp var
    ego_state = None

    if focus_on_driver:
        for vehicle_index, vehicle_state in enumerate(sorted(scenario_state, key=lambda vs: vs.user_id), start=0):
            if vehicle_state.user_id == focus_on_driver.user_id:
                ego_state = vehicle_state
                break

        assert goal_region_as_rectangle

    # There MUST be at least one vehicle in the scenario. All of them have the same timestamp
    timestamp = scenario_state[0].timestamp

    # Now plot the thing. We need to create an external figure to link it to mpld3
    # TODO A lot of this code can be improved by caching partial results and objects
    # ca 16:9
    # Somehow this changes the outer box but not the inner one?
    fig, ax = plt.subplots(figsize=figsize)

    items = ax.get_children()

    try:

        # The renderer uses the gca... I hope this does not break when used in flask...
        rnd = MPRenderer(ax=ax)

        scenario = mixed_traffic_scenario.scenario_template.as_commonroad_scenario()

        # Plot the lanelets
        scenario.draw(rnd)  # , draw_params={'time_begin': timestamps[0]}) # TODO What are the other paramters here?

        # Size of the rectangle representing the car.
        # dynamic_obstacle_shape = Rectangle(width=1.8, length=4.3)
        # TODO Not sure what's the issue here... it seems that at some point vehicles are rotated by 90?
        dynamic_obstacle_shape = Rectangle(VEHICLE_LENGTH, VEHICLE_WIDTH)

        tooltip_content = []

        # Generate the for each driver
        # for scenario_state in scenario_states: -> Possible extension to visualize more than one timestamp at the time.
        # SORT BY USER_ID to assign colors
        # DO NOT RENDER GOAL_REACHED
        # TODO Render CRASH differently !
        for vehicle_index, vehicle_state in enumerate(sorted(scenario_state, key=lambda vs: vs.user_id), start=0):

            # # AH! Vy
            # if vehicle_state.status == "GOAL_REACHED":
            #     logging.debug("Driver {} has reched the goal. Do not visualize it".format(vehicle_state.user_id))
            #     continue
            # The issue is that commonroad 2022.4 removes State and introduces InitialState so we downgraded to 2022.1
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

            # Default color for vehicles
            facecolor = _default_vehicle_color

            # Plot the Goal Region, use a different color to show focus
            if focus_on_driver and vehicle_state.user_id == focus_on_driver.user_id:
                # In this case, we also include the trajectory visualizer
                facecolor = _vehicle_colors[vehicle_index]

                goal_state_list = [State(position=goal_region_as_rectangle, time_step=Interval(0,mixed_traffic_scenario.duration))]
                commonroad_goal_region = GoalRegion(goal_state_list)
                commonroad_goal_region.draw(rnd, draw_params={'goal_region': {'shape': {'rectangle': {'facecolor': facecolor, 'opacity': 0.5}}}})

            # Plot the Vehicle. Highlight CRASHED (bold line around them) and GOAL_REACHED (opacity 0.1)
            opacity = 1.0 if vehicle_state.status == "ACTIVE" else 0.4
            linewidth = 1.0 if vehicle_state.status == "ACTIVE" else 3.0

            edgecolor = facecolor
            if vehicle_state.status == "CRASHED":
                edgecolor = "red"
            elif vehicle_state.status == "GOAL_REACHED":
                edgecolor = "black"

            vehicle_data = {"vehicle_shape": {
                               "occupancy": {
                                   "shape": {
                                       "rectangle": {
                                           "facecolor": facecolor,
                                           "edgecolor": edgecolor,
                                           "linewidth": linewidth,
                                           "zorder": 50,
                                           "opacity": opacity
                                       }
                                   }
                               }
                           }
                       }
            # The states are ordered by time_steps
            dynamic_obstacle.draw(rnd, draw_params={"time_begin": dynamic_obstacle.initial_state.time_step,
                                                    "dynamic_obstacle": vehicle_data})

        file_name_prefix = \
            "scenario_{}_timestamp_{}".format(mixed_traffic_scenario.scenario_id, timestamp) if focus_on_driver is None else \
            "scenario_{}_timestamp_{}_driver_{}".format(mixed_traffic_scenario.scenario_id, timestamp, focus_on_driver.user_id)

        # Render the as PNG
        if render_png:
            plt_path = os.path.join(output_folder, "{}.png".format(file_name_prefix))
            # This might remove and recreate all the elements added so far, so we need a way to include the Trajectory as well!
            rnd.render(show=False, filename=plt_path)
            #
            return

        # Enabling the Tooltip Plugin
        rnd.render(show=False)

        cars_x = []
        cars_y = []

        for vehicle_index, vehicle_state in enumerate(sorted(scenario_state, key=lambda vs: vs.user_id), start=0):

            cars_x.append(vehicle_state.position_x)
            cars_y.append(vehicle_state.position_y)

            if focus_on_driver and vehicle_state.user_id == focus_on_driver.user_id:
                if vehicle_state.acceleration_m2s > 0.0:
                    acc_string = "Your vehicle is <b>accelerating</b>"
                elif vehicle_state.acceleration_m2s < 0.0:
                    acc_string = "Your vehicle is <b>braking</b>"
                else:
                    acc_string = "Your vehicle <b>maintains</b> its speed"
            else:
                # This is HTML code!
                if vehicle_state.acceleration_m2s > 0.0:
                    acc_string = "The vehicle is <b>accelerating</b>"
                elif vehicle_state.acceleration_m2s < 0.0:
                    acc_string = "The vehicle is <b>braking</b>"
                else:
                    acc_string = "The vehicle <b>maintains</b> its speed"

            tooltip_content_string = f"User ID: {vehicle_state.user_id}<br>" \
                                     f"Speed: {round(vehicle_state.speed_ms * 3.6, 2)}<br>" \
                                     f"{acc_string}"

            if focus_on_driver and vehicle_state.user_id != focus_on_driver.user_id:
                # Include the distance to the ego
                tooltip_content_string = tooltip_content_string + "<br>"
                distance_to_ego = round(Point(vehicle_state.position_x, vehicle_state.position_y).distance(Point(ego_state.position_x, ego_state.position_y)), 2)
                tooltip_content_string = tooltip_content_string + f"The vehicle is about {distance_to_ego} meters from you"


            # Prepare the plugins for rendering the trajectories
            if focus_on_driver and vehicle_state.user_id == focus_on_driver.user_id:
                # Now add the selected trajectory on top of everything
                x = [vehicle_state.position_x]
                y = [vehicle_state.position_y]
                # We use two lines that represent the ENTIRE trajectory and the one SELECTED by the user
                trajectory_line,  = ax.plot(x, y, linestyle='-', lw=2, alpha=0.5, color="black", zorder=50)
                selected_line, = ax.plot(x, y, linestyle='-', lw=4, alpha=1, color="black", zorder=51)
                # Activate the plugin for this figure
                mpld3.plugins.connect(fig, TrajectoryView(trajectory_line, selected_line))
                # Now add all the trajectories that can be chosen from
                # ATM mpld3 requires to pre-allocate all the objects in a figure which might be altered later
                visible_trajectory_placeholders = []
                for i in range(0, VISIBLE_TRAJECTORIES):
                    # Make sure they are rendered below the selected trajectory
                    visible_trajectory_line, = ax.plot(x, y, linestyle='--', lw=2, alpha=0.2, color="blue", zorder=49)
                    visible_trajectory_placeholders.append(visible_trajectory_line)

                mpld3.plugins.connect(fig, AllTrajectoriesView(visible_trajectory_placeholders))

                # Register the EgoCarZoom Plugin
                mpld3.plugins.connect(fig, ZoomEgoCarPlugin(x, y))

            # TODO Compute Euclidean distance to the ego vehicle if any?
            tooltip_content.append(tooltip_content_string)

        css = """
            div.mpld3-tooltip {
                color: white;  /* Set text color to black */
                background-color: rgba(0, 0, 0, 0.8);  /* Set background color to transparent black */
                border: none;  /* Remove border */
                box-shadow: none;  /* Remove box shadow */
            }
        """

        # tooltip_mask = [True] * len(tooltip_content)  # Enable tooltips for all cars tooltip_hover=tooltip_mask
        # points = coordinates of all cars objects. make them transparent
        points = ax.plot(cars_x, cars_y, 'o', color='b',
                 mec='k', ms=15, mew=1, alpha=0, zorder=52)

        tooltip = mpld3.plugins.PointHTMLTooltip(points[0], labels=tooltip_content, css=css)
        mpld3.plugins.connect(fig, tooltip)

        # Render as embeddable HTML snippet
        plt_path = os.path.join(output_folder, "{}.embeddable.html".format(file_name_prefix))

        # TODO Maybe there's something to plot directly to file?
        theString = mpld3.fig_to_html(fig, template_type="simple")
        with open(plt_path, "w") as output_file:
            output_file.write( theString)

        return plt_path
    finally:
        plt.close(fig)


class MixedTrafficScenario:

    def __init__(self, scenario_id, name, description, created_by, max_players, status, scenario_template, duration,
                 drivers: List[User] = []):
        # Static attributes
        self.scenario_id = scenario_id
        self.name = name
        self.description = description

        self.duration = duration

        self.created_by = created_by # User
        self.max_players = max_players
        self.status = status

        self.scenario_template = scenario_template # MixedScenarioTemplate

        # Dynamic attributes - TODO Which one do we really need?
        # Currently registered players
        self.drivers: List[User] = [] + drivers
        # Not sure why need this
        # This can be either the list of states (state_id) ordered by timestamp and organized around the drivers
        # self.vehicle_states = []
        # CommonRoad Scenario. We need those?
        # self.scenario = None
        # self.planning_problems_set = None

    def __eq__(self, other):
        if not isinstance(other, MixedTrafficScenario):
            # Trivially False
            return False

        return self.scenario_id == other.scenario_id and self.name == other.name and \
               self.description == other.description and self.created_by.user_id == other.created_by.user_id and \
               self.max_players == other.max_players and self.status == other.status and \
               self.scenario_template.template_id == other.scenario_template.template_id and \
               self.duration == other.duration and self.drivers == other.drivers

    # TODO Ugly patch to allow passing the initial and goal area for the drivers
    def as_commonroad_scenario_and_planning_problems(self, initial_states= {}, goal_region_as_rectangles = {} ):
        # Create a CommonRoad scenario out of the static template
        commonroad_scenario = self.scenario_template.as_commonroad_scenario()

        # TODO Add the planning problems here for each driver
        planning_problems = {}
        for driver in self.drivers:
            # TODO Refactor to get it directly from the driver object. Driver objects are not used ATM
            commonroad_initial_state = initial_states[driver.user_id].as_commonroad_state()
            goal_region_as_rectangle = goal_region_as_rectangles[driver.user_id]
            goal_state_list = [
                State(position=goal_region_as_rectangle, time_step=Interval(0, self.duration))]
            commonroad_goal_region = GoalRegion(goal_state_list)
            planning_problems[driver.user_id] = PlanningProblem(self.scenario_id, commonroad_initial_state, commonroad_goal_region)

        return commonroad_scenario, planning_problems


class MixedTrafficScenarioSchema(Schema):
    """ This class is used to serialize/validate Python objects using Marshmallow """
    scenario_id = fields.Integer(required=True)
    name = fields.String(required=True)
    description = fields.String(allow_none=True)
    created_by = fields.Nested(UserSchema(exclude=["password"]), required=True)
    scenario_template = fields.Nested(MixedTrafficScenarioTemplateSchema(exclude=["xml"]), required=True)
    status = fields.String(required=True)
    duration = fields.Integer(required=True)
    # TODO: not sure whether max player or n_users + n_avs is better here
    max_players = fields.Integer()
    # This is optional
    drivers = fields.List(fields.Nested(UserSchema(exclude=["password"])), required=False, exclude=["password"])

    @post_load
    def make_mixed_traffic_scenario(self, data, **kwargs):
        return MixedTrafficScenario(**data)


