# When this code is used via a background threat we need to ensure no interaction is allowed
# This is automatically set in the flask app
import matplotlib
matplotlib.use('Agg')  # disable interactive view

from model.vehicle_state import VehicleStatusEnum
from model.mixed_traffic_scenario import MixedTrafficScenarioStatusEnum
import numpy as np
import os
import json

import mpld3

import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba

from frontend.mpld3_plugins import TrajectoryView, AllTrajectoriesView, ZoomEgoCarPlugin, ScenarioDragPlugin, NewScenarioDragPlugin

from commonroad.geometry.shape import Rectangle
from commonroad.planning.goal import GoalRegion
from commonroad.common.util import Interval

from commonroad.visualization.mp_renderer import MPRenderer

# TODO Move this to an util module
from matplotlib.cm import get_cmap
_name = "Accent"
_cmap = get_cmap(_name)  # type: matplotlib.colors.ListedColormap
# TODO Those must be HEX Strings?
# THIS HAS ONLY 8 COLORS!
vehicle_colors = _cmap.colors  # type: list

# This is the color of the current user vehicle
# _ego_vehicle_color = "#505D86"

# import necessary classes from different modules
from commonroad.scenario.obstacle import DynamicObstacle, ObstacleType
from commonroad.scenario.trajectory import Trajectory, State
from commonroad.prediction.prediction import TrajectoryPrediction

from shapely.geometry import Point
# Controls
# TODO: Is this the overall number or the number of each batch?
VISIBLE_TRAJECTORIES = 100

# TODO: Not safe for refactoring and redefinition, better use app.config
from configuration.config import VEHICLE_WIDTH, VEHICLE_LENGTH

from commonroad.scenario.scenario import Scenario
from commonroad.planning.planning_problem import PlanningProblemSet, PlanningProblem
from commonroad.common.file_writer import CommonRoadFileWriter, OverwriteExistingFile


def generate_commonroad_xml_file(output_file_path,
                                scenario, initial_states, goal_region_as_rectangles, scenario_states):
    # Export the scenario planning problems and the corresponding dynamic obstacles
    commonroad_scenario: Scenario
    commonroad_planning_problems: PlanningProblemSet

    commonroad_scenario, commonroad_planning_problems = scenario.as_commonroad_scenario_and_planning_problems(
        initial_states=initial_states,
        goal_region_as_rectangles=goal_region_as_rectangles)

    # CommonRoad Scenario MetaData
    author = scenario.owner.username
    affiliation = 'Flexcrash EU Project'
    source = ''
    tags = {}

    # Scenario Dynamic Obstacles
    # We follow this convention: DynamicObstacle's IDs are user.id + 2000
    for driver in scenario.drivers:
        dynamic_obstacle_shape = Rectangle(VEHICLE_LENGTH, VEHICLE_WIDTH)
        planning_problem: PlanningProblem
        planning_problem = commonroad_planning_problems[driver.user_id]

        # This might invalidate the Scenario but allows the users to decide which one to keep
        dynamic_obstacle_initial_state = planning_problem.initial_state

        # Since this is only a state, we might not need any state list
        # Note: The initial state does not belong to the prediction/trajectory
        dynamic_obstacle_states = [ state.as_commonroad_state() for state in scenario_states[driver.user_id][1:]]
        # The initial timestep of the trajectory is the timestep of the first state
        dynamic_obstacle_prediction = TrajectoryPrediction(
            Trajectory(dynamic_obstacle_states[0].time_step, dynamic_obstacle_states),
            dynamic_obstacle_shape)

        dynamic_obstacle_id = driver.user_id + 2000
        dynamic_obstacle_type = ObstacleType.CAR
        dynamic_obstacle = DynamicObstacle(dynamic_obstacle_id,
                                           dynamic_obstacle_type,
                                           dynamic_obstacle_shape,
                                           dynamic_obstacle_initial_state,
                                           dynamic_obstacle_prediction)

        commonroad_scenario.add_objects(dynamic_obstacle)

    # CommonRoad Planning Problem Set
    # We follow this convention: PlannningProblem's IDs are user.id + 3000
    planning_problem_list = list()
    for user_id, planning_problem in commonroad_planning_problems.items():
        # Planning problems ID are immutable!
        planning_problem._planning_problem_id = 3000 + int(user_id)
        planning_problem_list.append(planning_problem)
    planning_problem_set = PlanningProblemSet(planning_problem_list)

    fw = CommonRoadFileWriter(commonroad_scenario, planning_problem_set, author, affiliation, source, tags)
    fw.write_to_file(output_file_path, OverwriteExistingFile.ALWAYS)


def generate_embeddable_html_snippet(output_folder,
                                    commonroad_scenario, mixed_traffic_scenario_duration, mixed_traffic_scenario_scenario_id,
                                    scenario_state,
                                    focus_on_driver_user_id=None, goal_region_as_rectangle=None):

    # print(f"generate_embeddable_html_snippet: {output_folder}")

    try:
        # Generate the PNG
        render_png = True
        figsize = (16, 6)
        generate_picture(render_png, figsize,
                         output_folder, commonroad_scenario, mixed_traffic_scenario_duration, mixed_traffic_scenario_scenario_id,
                         scenario_state,
                         focus_on_driver_user_id, goal_region_as_rectangle)

        # # Generate the HTML
        render_png = False
        figsize = (8, 3)
        generate_picture(render_png, figsize,
                         output_folder, commonroad_scenario, mixed_traffic_scenario_duration, mixed_traffic_scenario_scenario_id,
                         scenario_state,
                         focus_on_driver_user_id, goal_region_as_rectangle)
    except Exception as e:
        print(f"Exception {e}")


def generate_picture(render_png, figsize, # Tuple(Number, Number)?
                     output_folder,
                     commonroad_scenario, mixed_traffic_scenario_duration, mixed_traffic_scenario_scenario_id,
                     scenario_state,
                     focus_on_driver_user_id=None, goal_region_as_rectangle=None):
    """
    Render the provided states of the given scenario, possibly focusing on the given driver.
    Focusing means that the driver's vehicle is highlighted while the others have the default color
    """

    # If focus on driver is active, so must be the goal region
    # Store the ego state in a temp var
    ego_state = None

    if focus_on_driver_user_id:
        for vehicle_index, vehicle_state in enumerate(sorted(scenario_state, key=lambda vs: vs.driver_id), start=0):
            if vehicle_state.user_id == focus_on_driver_user_id:
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

    try:

        # The renderer uses the gca... I hope this does not break when used in flask...
        rnd = MPRenderer(ax=ax)

        # commonroad_scenario = mixed_traffic_scenario.scenario_template.as_commonroad_scenario()

        # Plot the lanelets
        commonroad_scenario.draw(rnd)  # , draw_params={'time_begin': timestamps[0]}) # TODO What are the other paramters here?

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
        for vehicle_index, vehicle_state in enumerate(sorted(scenario_state, key=lambda vs: vs.driver_id), start=0):

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

            # Assign a color to each vehicle
            # TODO Ensure that when vehicles disappear, colors do not change!
            facecolor = vehicle_colors[vehicle_index]

            # Plot the Goal Region, use a different color to show focus
            if focus_on_driver_user_id and vehicle_state.user_id == focus_on_driver_user_id:
                # In this case, we also include the trajectory visualizer
                # facecolor = _ego_vehicle_color
                goal_state_list = [State(position=goal_region_as_rectangle, time_step=Interval(0, mixed_traffic_scenario_duration))]
                commonroad_goal_region = GoalRegion(goal_state_list)
                commonroad_goal_region.draw(rnd, draw_params={'goal_region': {'shape': {'rectangle': {'facecolor': facecolor, 'opacity': 0.5}}}})

            # Plot the Vehicle. Highlight CRASHED (bold line around them) and GOAL_REACHED (opacity 0.1)
            opacity = 1.0 if vehicle_state.status == VehicleStatusEnum.ACTIVE else 0.4
            linewidth = 1.0 if vehicle_state.status == VehicleStatusEnum.ACTIVE else 3.0

            edgecolor = "black"
            if vehicle_state.status == VehicleStatusEnum.CRASHED:
                edgecolor = "red"
            elif vehicle_state.status == VehicleStatusEnum.GOAL_REACHED:
                # https://stackoverflow.com/questions/34606601/how-can-i-set-different-opacity-of-edgecolor-and-facecolor-of-a-patch-in-matplot
                opacity = 0.1

            # Convert the colors to RGBA
            facecolor = to_rgba(facecolor, opacity)
            edgecolor = to_rgba(edgecolor, opacity)

            # Plot the vehicle icon
            vehicle_data = {
                "draw_icon": True,
                "vehicle_shape": {
                               "occupancy": {
                                   "shape": {
                                       "rectangle": {
                                           "facecolor": facecolor,
                                           "edgecolor": edgecolor,
                                           "linewidth": linewidth,
                                           "zorder": 50,
                                           "opacity": opacity # This takes no effect with icons, as icons as matplotlib patches
                                       }
                                   }
                               }
                           }
                       }
            # The states are ordered by time_steps
            dynamic_obstacle.draw(rnd, draw_params={"time_begin": dynamic_obstacle.initial_state.time_step,
                                                    "dynamic_obstacle": vehicle_data})

        file_name_prefix = \
            "scenario_{}_timestamp_{}".format(mixed_traffic_scenario_scenario_id, timestamp) if focus_on_driver_user_id is None else \
            "scenario_{}_timestamp_{}_driver_{}".format(mixed_traffic_scenario_scenario_id, timestamp, focus_on_driver_user_id)

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

            if focus_on_driver_user_id and vehicle_state.user_id == focus_on_driver_user_id:
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

            if focus_on_driver_user_id and vehicle_state.user_id != focus_on_driver_user_id:
                # Include the distance to the ego
                tooltip_content_string = tooltip_content_string + "<br>"
                distance_to_ego = round(Point(vehicle_state.position_x, vehicle_state.position_y).distance(Point(ego_state.position_x, ego_state.position_y)), 2)
                tooltip_content_string = tooltip_content_string + f"The vehicle is about {distance_to_ego} meters from you"


            # Prepare the plugins for rendering the trajectories
            if focus_on_driver_user_id and vehicle_state.user_id == focus_on_driver_user_id:
                # Now add the selected trajectory on top of everything
                x = [vehicle_state.position_x]
                y = [vehicle_state.position_y]

                # Note: Pay attention that ax.plot returns a tuple!
                reference_path_line, = ax.plot(x, y, linestyle='-', lw=4, alpha=0.3, color="green", zorder=49)
                trajectory_line,  = ax.plot(x, y, linestyle='-', lw=2, alpha=0.5, color="black", zorder=50)
                selected_line, = ax.plot(x, y, linestyle='-', lw=4, alpha=1, color="black", zorder=51)

                # Activate the plugin for this figure
                mpld3.plugins.connect(fig, TrajectoryView(trajectory_line, selected_line, reference_path_line))


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

        # <div id="control-tooltip" class="mpld3-tooltip" style="position: absolute; z-index: 100; visibility: visible; top: 304px; left: 288px;background-color:white;">
        #     <table><thead><tr><th colspan="2" class="text-center">Vehicle's Parameters</th></tr></thead>
        #
        #         <tbody><tr><th>Speed (Km/h)</th><td>    <input type="range" id="speed-selector" name="speed-selector" min="0" max="90"></td></tr>
        #         <tr><th>Color</th>    <td style="background-color:green" }=""></td></tr>
        #         <tr><th>Type</th><td><label>Human Driver</label><div class="form-check form-switch">
        #       <input class="form-check-input" type="checkbox" id="flexSwitchCheckDefault">
        #     <label>AV</label>
        # </div></td></tr>
        #             <tr><th>User</th><td>TDB - Show the user selector</td></tr>
        #     </tbody></table>
        #
        #     <a id="remove-btn" class="btn btn-info" role="button">Remove this driver</a><a class="btn btn-info" role="button">Cancel</a></div>

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

def generate_scenario_designer(scenario_template, scenario_data={}, max_players=8):
    """
    Generate the interactive visualization of the scenario with preloaded (hidden) max_player markers.
    Use scenario_data to position the markers and configure the initial values of the form

    TODO Ideally, the markers should be placed in the middle of the actual figure. This could be probably done
    with a plugin

    TODO Max player is 8 because the cmap has 8 entries!

    TODO Use different icons for User/AV
    :return:
    """
    fig, ax = plt.subplots(figsize=(8, 3))

    try:
        # Render the scenario template, i.e., the road layout, without showing it yet
        rnd = MPRenderer(ax=ax)
        scenario = scenario_template.as_commonroad_scenario()
        scenario.draw(rnd)
        rnd.render(show=False)

        # Generate the placeholder/markers - independently as they cannot be easily modified later!
        initial_state_points = []
        goal_area_points = []
        colors = []
        # Note: Since we stack the one on top of the other, they steal the mouseover, not we put them one beside the other.
        # Can try to reverse their generation, but keep their order in the final array, or move them one aside the other

        # Keep the limits for the map
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        bottom_left_corner = [xlim[0], ylim[0]]

        initial_state_data = []
        goal_area_data = []

        # Avoid stupid mistakes
        if scenario_data is None:
            scenario_data = {}

        # Initialize the scenario data with the default values or the existing ones
        for driver_index in range(0, max_players):
            color = vehicle_colors[ driver_index ]

            # Assume the driver is not visible
            scenario_data[f"{driver_index}_is_visible"] = False

            # Initial State for the driver
            if f"{driver_index}_x_is" not in scenario_data:
                scenario_data[f"{driver_index}_x_is"] = bottom_left_corner[0] + driver_index * 2.0
            else:
                scenario_data[f"{driver_index}_is_visible"] = True

            if f"{driver_index}_y_is" not in scenario_data:
                scenario_data[f"{driver_index}_y_is"] = bottom_left_corner[1]
            else:
                scenario_data[f"{driver_index}_is_visible"] = True

            if f"{driver_index}_v_is" not in scenario_data:
                scenario_data[f"{driver_index}_v_is"] = 45.0
            else:
                scenario_data[f"{driver_index}_is_visible"] = True

            if f"{driver_index}_typology" not in scenario_data:
                scenario_data[f"{driver_index}_typology"] = "human"
            else:
                scenario_data[f"{driver_index}_is_visible"] = True

            # Goal Area for the driver
            if f"{driver_index}_x_ga" not in scenario_data:
                scenario_data[f"{driver_index}_x_ga"] = bottom_left_corner[0] + driver_index * 2.0
            else:
                scenario_data[f"{driver_index}_is_visible"] = True

            if f"{driver_index}_y_ga" not in scenario_data:
                scenario_data[f"{driver_index}_y_ga"] = bottom_left_corner[1] -2.0
            else:
                scenario_data[f"{driver_index}_is_visible"] = True

            # At this point scenario data contains either the past values or the default ones
            # The scenario data also contains a flag to force the vehicle visibility

            # Plot the markers

            # Round marker - Initial State
            x_is = float(scenario_data[f"{driver_index}_x_is"])
            y_is = float(scenario_data[f"{driver_index}_y_is"])

            initial_state_points.append(ax.plot(x_is, y_is, 'o', color= color, mec='k', ms=15, mew=1, alpha=0.0, zorder=52)[0])

            # Squared marker
            x_ga = float(scenario_data[f"{driver_index}_x_ga"])
            y_ga = float(scenario_data[f"{driver_index}_y_ga"])

            goal_area_points.append(ax.plot(x_ga, y_ga, 's', color= color, mec='k', ms=15, mew=1, alpha=0.0, zorder=52)[0])

            # Remember the colors as well
            colors.append(color)

        # Isn't it better to pass the scenario data directly here?! So the plugin can setup whatever it likes?
        mpld3.plugins.connect(fig, NewScenarioDragPlugin(
            initial_state_points, goal_area_points, scenario_data, colors))

        html_snippet = mpld3.fig_to_html(fig)

    finally:
        plt.close(fig)

    return html_snippet

def generate_drag_and_drop_html(scenario_template, template_id, vehicles, vehicle_positions=None):
    # Note: this should be done live, the others can be done using the scheduler

    # timestamp = scenario_state[0].timestamp
    fig, ax = plt.subplots(figsize=(8, 3))
    # (12, 9)

    items = ax.get_children()

    try:

        rnd = MPRenderer(ax=ax)
        scenario = scenario_template.as_commonroad_scenario()
        scenario.draw(rnd)

        # Render as PNG
        # plt_path = os.path.join(output_folder, "{}.png".format(template_id))
        # This might remove and recreate all the elements added so far, so we need a way to include the Trajectory as well!
        rnd.render(show=False) #, filename=plt_path)

        cars_x = []
        cars_y = []
        car_ids = []
        initial_state_tooltip_content = []
        goal_area_tooltip_content = []

        vehicles = json.loads(vehicles)

        if vehicles["unassigned_users"] > 0:
            for i in range(vehicles["unassigned_users"]):
                cars_x.append(0)
                cars_y.append(0)
                initial_state_tooltip_content.append(f"Initial state of Unassigned Driver {i+1}")
                goal_area_tooltip_content.append(f"Goal area of Unassigned Driver {i+1}")
                car_ids.append(f"UD_{i+1}")

        if vehicles["n_avs"] > 0:
            for i in range(vehicles["n_avs"]):
                cars_x.append(0)
                cars_y.append(0)
                initial_state_tooltip_content.append(f"Initial state of AV {i+1}")
                goal_area_tooltip_content.append(f"Goal area of AV {i+1}")
                car_ids.append(f"AV_{i+1}")

        if len(vehicles["users_list"]) > 0:
            for user in vehicles["users_list"]:
                cars_x.append(0)
                cars_y.append(0)
                initial_state_tooltip_content.append(f"Initial state of User ID: {user}")
                goal_area_tooltip_content.append(f"Goal area of User ID: {user}")
                car_ids.append(f"U_{user}")

        print("VPOS:", vehicle_positions)
        if vehicle_positions:
            print("SPLIT: ", vehicle_positions["x"][1:-1].split(","))
            veh_pos_x = vehicle_positions["x"][1:-1].split(",")
            veh_pos_y = vehicle_positions["y"][1:-1].split(",")
            for position in range(len(veh_pos_x)):
                if veh_pos_x[position] == '':
                    veh_pos_x[position] = 0
                    veh_pos_y[position] = 0
                cars_x[position] = float(veh_pos_x[position])
                cars_y[position] = float(veh_pos_y[position])


        css = """
              div.mpld3-tooltip {
                  color: white;  /* Set text color to black */
                  background-color: rgba(0, 0, 0, 0.8);  /* Set background color to transparent black */
                  border: none;  /* Remove border */
                  box-shadow: none;  /* Remove box shadow */
              }
          """
        # TODO Randomly place them instead on the road?
        # initial_state_point_colors = []
        # goal_area_point_colors = []
        # for c, _ in zip(_vehicle_colors, cars_x):
        #     initial_state_point_colors.append(c)
        #     goal_area_point_colors.append(c)
        #
        # # Round marker
        # initial_state_points = ax.plot(cars_x, cars_y, 'o', color=initial_state_point_colors, mec='k', ms=15, mew=1, alpha=.6, zorder=52)
        # # Squared marker
        # goal_area_points = ax.plot(cars_x, cars_y,'s', color=goal_area_point_colors, mec='k', ms=15, mew=1, alpha=.3, zorder=52)

        # Round marker
        initial_state_points = ax.plot(cars_x, cars_y, 'o', color="b", mec='k', ms=15, mew=1, alpha=.6, zorder=52)
        #TODO: initialize every point on its own
        # Squared marker
        goal_area_points = ax.plot(cars_x, cars_y,'s', color="g", mec='k', ms=15, mew=1, alpha=.3, zorder=52)

        mpld3.plugins.connect(fig, ScenarioDragPlugin(
            initial_state_points[0], goal_area_points[0],
            # TODO Not sure why we need x and y
            id_array=car_ids, x_array=cars_x, y_array=cars_y))

        # TODO  How can we attach the tooltip to goal area?
        initial_state_tooltip = mpld3.plugins.PointHTMLTooltip(initial_state_points[0], labels=initial_state_tooltip_content, css=css)
        goal_area_tooltip = mpld3.plugins.PointHTMLTooltip(goal_area_points[0], labels=goal_area_tooltip_content, css=css)
        # Can we?
        mpld3.plugins.connect(fig, initial_state_tooltip)
        mpld3.plugins.connect(fig, goal_area_tooltip)

        html_snippet = mpld3.fig_to_html(fig)

    finally:
        plt.close(fig)

    return html_snippet


