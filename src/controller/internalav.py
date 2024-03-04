import os.path
from copy import deepcopy
import logging


import requests
from typing import List, Optional

from exceptions.exceptions import StopMeException
from model.mixed_traffic_scenario import MixedTrafficScenarioStatusEnum
from model.vehicle_state import VehicleStatusEnum

# Make sure CR does not complain about overlapping IDs!
DYNAMIC_OBSTACLE_STARTING_ID = 10000

# TODO: Not refactoring safe!
GET_SCENARIO_BY_SCENARIO_ID = "/api/scenarios/{scenario_id}/"
GET_DRIVER_INITIAL_STATE = "/api/scenarios/{scenario_id}/drivers/{user_id}/states/0/"

GET_DRIVER_BY_SCENARIO_AND_USER_IDS = "/api/scenarios/{scenario_id}/drivers/{user_id}/"

# This is all the states at the vehicle
GET_VEHICLE_STATES = "/api/scenarios/{scenario_id}/drivers/{user_id}/states/"
# This is all the states at the timestamp
GET_VEHICLES_STATE_AT_TIMESTAMP = "/api/scenarios/{scenario_id}/states/{timestamp}/"

# We need to access the template from within the scenario, because templates might have been disabled in the meanwhile
GET_SCENARIO_TEMPLATE_BY_SCENARIO_ID = "/api/scenarios/{scenario_id}/template/xml/"

PUT_UPDATE_VEHICLES_STATES = "/api/scenarios/{scenario_id}/drivers/{user_id}/states/"

# Logging
FORMATTER = logging.Formatter("%(asctime)s — %(name)s — %(levelname)s — %(message)s")

from configuration.config import VEHICLE_LENGTH, VEHICLE_WIDTH


import json
from types import SimpleNamespace

from commonroad.geometry.shape import Rectangle

from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.common.file_writer import CommonRoadFileWriter

from commonroad.scenario.obstacle import DynamicObstacle, ObstacleType

from commonroad.scenario.scenario import State, Interval
from commonroad.planning.planning_problem import GoalRegion, PlanningProblem, PlanningProblemSet
from commonroad.prediction.prediction import Trajectory, TrajectoryPrediction
from commonroad_route_planner.route_planner import RoutePlanner

from commonroad_rp.reactive_planner import ReactivePlanner
from commonroad_rp.visualization import visualize_planning_result

from commonroad_rp.prediction import linear_prediction

from commonroad_dc.boundary.boundary import create_road_boundary_obstacle
from commonroad_dc.collision.collision_detection.pycrcc_collision_dispatch import create_collision_checker

import io

import numpy as np

# DEFAULT VALUES THAT WE WILL STORE IN SOME VARIABLE/FILE
delta_t = 0.1
# TODO Using replanning_frequency = 3 the AV goes back in time...
time_horizon = 2 # seconds

### TODO Make sure we handle 404, 401, etc.
# TODO How can we inject the token directly here without passing it as parameter?
def _do_get_request(the_request, auth_token, data=None):
    response = requests.get(the_request, data=data,
                        headers = {'Authorization': auth_token})

    if response.status_code > 400:
        raise StopMeException()

    return response

# def _do_post_request(the_request, auth_token, data=None):
#     return requests.post(the_request,
#                         data=data,
#                         headers={'Authorization': auth_token})

def _do_put_request(the_request, auth_token, data=None):
    return requests.put(the_request,
                        data=data,
                        headers = {'Authorization': auth_token})
#####


def as_commonroad_scenario(xml):
    with io.BytesIO(xml.encode('utf8')) as binary_file:
        with io.TextIOWrapper(binary_file, encoding='utf8') as file_obj:
            commonroad_file_reader = CommonRoadFileReader(file_obj)
            commonroad_scenario, _ = commonroad_file_reader.open()
            return commonroad_scenario


# Get current state
def get_current_state(protocol, host, port, scenario_id, user_id, auth_token, logger) -> Optional[State]:
    response = _do_get_request(f"{protocol}://{host}:{port}{GET_VEHICLE_STATES.format(scenario_id=scenario_id, user_id=user_id)}", auth_token)

    vehicle_states: List
    vehicle_states = json.loads(response.text, object_hook=lambda d: SimpleNamespace(**d))
    vehicle_states.sort(key=lambda vs: vs.timestamp)
    # Process them in pairs looking for the pattern t=N, state=ACTIVE, t=N+1, state=PENDING
    # TODO Crashed? TODO Goal Reached? -> Undeploy AV!
    for before, after in zip(vehicle_states[:], vehicle_states[1:]):
        if before.status == "ACTIVE" and after.status == "PENDING":
            logger.info(f"Background AV {user_id} in Scenario {scenario_id}. Found an actionable state at {before.timestamp}")
            planning_from_timestamp = before.timestamp
            return before

    logger.warn(f"Cannot found an actionable state for user {user_id} in scenario {scenario_id}. Stop.")
    # Note: Do not trigger stop me at this point otherwise the driver will die. Instead, we want it to be rescheduled
    #   by the background scheduler
    return None


def _extend_ref_path_by(ref_path, step, times):
    """
    The planner uses the ref path to project its position. At the edges of the network, the path is not there anymore,
    and the planner fails. So we extend it in both directions!
    """

    x = [p[0] for p in ref_path]
    y = [p[1] for p in ref_path]

    # TODO There is surely a better way
    # Starting at xe1,  ye1, extend it by X points at distance "step" following the direction defined by xs, ys and xe, ye
    # Take last two points
    xs1, ys1 = x[-2], y[-2]
    xe1, ye1 = x[-1], y[-1]

    if xe1 == xs1:
        # Direction:
        if ye1 > ys1:
            # up
            extension = np.array([[xe1, ye1 + i * step] for i in range(0, times+1)])
        else:
            # down - assuming y grews up
            extension = np.array([[xe1, ye1 - i * step] for i in range(0, times+1)])
        pass
    else:
        # Slope
        m1 = (ye1 - ys1) / (xe1 - xs1)
        # Direction:
        if xe1 > xs1:
            # right
            extension = np.array([[xe1 + i * step, ye1 + (i * step) * m1] for i in range(0, times+1)])
        else:
            # left
            extension = np.array([[xe1 - i * step, ye1 - (i * step) * m1] for i in range(0, times+1)])
    xext = x + [p[0] for p in extension]
    yext = y + [p[1] for p in extension]
    return np.array([[px, py] for px, py in zip(xext, yext)])


def create_motion_or_get_planner_for(driver_cache_dir, driver_id, scenario, user_id, auth_token,
                                     replanning_frequency, cost_function_parameters,
                                     protocol, host, port, logger):

    if not os.path.exists(driver_cache_dir):

        os.makedirs(driver_cache_dir)
        # Store the configuration values
        with open(os.path.join(driver_cache_dir, "configuration.json"), "w") as configuration_json_file:
            configuration = {}
            configuration["replanning_frequency"] = replanning_frequency
            configuration["cost_function_parameters"] = cost_function_parameters
            configuration["auth_token"] = auth_token

            json.dump(configuration,configuration_json_file, indent=8)

        # 3. Define the CommonRoad Scenario and CommonRoad PlanningProblem for the Planner

        # Get the lanelets network XML, aka the template used for this scenario
        response = _do_get_request(f"{protocol}://{host}:{port}{GET_SCENARIO_TEMPLATE_BY_SCENARIO_ID.format(scenario_id=scenario.scenario_id)}", auth_token)

        template_xml = response.text
        base_commonroad_scenario = as_commonroad_scenario(template_xml)

        # Get the Driver Goal Region
        response = _do_get_request(f"{protocol}://{host}:{port}{GET_DRIVER_BY_SCENARIO_AND_USER_IDS.format(scenario_id=scenario.scenario_id, user_id=user_id)}",
                                       auth_token)
        driver = json.loads(response.text, object_hook=lambda d: SimpleNamespace(**d))
        length, width, center_x, center_y, orientation = [float(v) for v in driver.goal_region.split(",")]
        center = np.array([center_x, center_y])
        goal_region_as_rectangle = Rectangle(length, width, center, orientation)
        goal_state_list = [State(position=goal_region_as_rectangle, time_step=Interval(0, scenario.duration))]
        commonroad_goal_region = GoalRegion(goal_state_list)

        # Get the Driver Initial State
        response = _do_get_request(f"{protocol}://{host}:{port}{GET_DRIVER_INITIAL_STATE.format(scenario_id=scenario.scenario_id, user_id=user_id)}",
                                       auth_token)
        initial_state = json.loads(response.text, object_hook=lambda d: SimpleNamespace(**d))
        commonroad_initial_state = State(**{
            "time_step": 0,
            "position": np.array([initial_state.position_x, initial_state.position_y]),
            "velocity": initial_state.speed_ms,
            "orientation": initial_state.rotation,
            "yaw_rate": 0,
            "slip_angle": 0
        })
        #
        commonroad_planning_problem = PlanningProblem(driver_id, commonroad_initial_state, commonroad_goal_region)
        commonroad_planning_problem_set = PlanningProblemSet([commonroad_planning_problem])
        CommonRoadFileWriter(
            base_commonroad_scenario,
            commonroad_planning_problem_set,
            author=f"Flexcrash User: {scenario.created_by}",
            affiliation="Flexcrash",
            source="Flexcrash-Platform"
        ).write_to_file(os.path.join(driver_cache_dir,"scenario.xml"), overwrite_existing_file=True, check_validity=True)

        # Compute and store the Reference Route
        # This defines the Reference Trajectory for the planner... and causes a lot of troubles at the edges, so we extend the ref path
        route_planner = RoutePlanner(base_commonroad_scenario, commonroad_planning_problem, log_to_console=True)
        # Planner must start on a road
        assert len(route_planner.id_lanelets_start) > 0, "Cannot plan a route outside the road"
        initial_id = route_planner.id_lanelets_start[0]
        initial_lanelet = route_planner.scenario.lanelet_network.find_lanelet_by_id(initial_id)
        # TODO Use commonroad_initial_state
        try:
            # get reference path
            follow_initial_lanelet = False
            if follow_initial_lanelet is True and len(base_commonroad_scenario.lanelet_network.intersections) == 0:
                # follow initial lanelet
                ref_path = initial_lanelet.center_vertices
            else:
                # custom reference path
                ref_path = route_planner.plan_routes().retrieve_first_route().reference_path
        except Exception as exec:
            logger.error(f"Original planner cannot find a ref path {exec}")
            raise exec

        assert ref_path is not None, "Cannot find a reference path!"

        # Extend the reference path to avoid wrong behaviour at the limit.
        # For the moment just linearly using the last two points of the existing ref_path
        ref_path = _extend_ref_path_by(ref_path, step=5, times=100)
        # Store the reference_path to file
        # Save the array to a binary file
        np.save(os.path.join(driver_cache_dir, "reference_path.npy"), ref_path)

    # Load the planner configuration from the files
    with open(os.path.join(driver_cache_dir, "configuration.json"), "r") as configuration_json_file:
        configuration = json.loads(configuration_json_file.read())

    reference_path = np.load(os.path.join(driver_cache_dir, "reference_path.npy" ))
    base_commonroad_scenario, commonoroad_planning_problem_set = CommonRoadFileReader(os.path.join(driver_cache_dir, "scenario.xml")).open()
    commonroad_planning_problem = commonoroad_planning_problem_set.find_planning_problem_by_id(driver_id)

    # Setup the planner with those elements
    # Initialize our custom TUM's Reactive Planner
    planner = ReactivePlanner(dt=delta_t, t_h=time_horizon, N=int(time_horizon / delta_t),
                              rf=configuration["replanning_frequency"],
                              # TODO Compute the desired velocity from the ref planner
                              v_desired=commonroad_planning_problem.initial_state.velocity,
                              cost_parameters=configuration["cost_function_parameters"],
                              logger=logger)

    planner.set_d_sampling_parameters(-10, 10)
    planner.set_t_sampling_parameters(0.5, planner.dT, planner.horizon)
    # Set this a mix/max speed from app configuration
    planner.set_v_sampling_parameters(0.1, 25.0)

    # Configure the planner to follow the reference path
    planner.set_reference_path(reference_path)

    # Create the collision checkers for the original scenario. In this scenario,

    # we know every position of Dynamic and Static Obstacles with PREDEFINED trajectories
    road_collision_checker_original_scenario = create_collision_checker(base_commonroad_scenario)
    road_boundary_obstacle_original_scenario, road_boundary_sg_rectangles_original_scenario = create_road_boundary_obstacle(base_commonroad_scenario, open_lane_ends=False)  # Note this option!!
    road_collision_checker_original_scenario.add_collision_object(road_boundary_sg_rectangles_original_scenario)


    # Return a configured planner
    return base_commonroad_scenario, commonroad_planning_problem, planner, road_collision_checker_original_scenario

def to_common_road_state(vehicle_state):
    return State(**{
        "time_step": vehicle_state.timestamp,
        "position": np.array([vehicle_state.position_x, vehicle_state.position_y]),
        "velocity": vehicle_state.speed_ms,
        "acceleration": vehicle_state.acceleration_m2s,
        "orientation": vehicle_state.rotation,
        "yaw_rate": 0,
        "slip_angle": 0
    })


def to_predicted_common_road_state(vehicle_state):
    return State(**{
        "time_step": vehicle_state.timestamp,
        "position": np.array([vehicle_state.position_x, vehicle_state.position_y]),
        "velocity": vehicle_state.speed_ms,
        "orientation": vehicle_state.rotation
    })


def _augment_scenarios_with_past_driver_data_safety_buffer_and_prediction(
        ego_vehicle_commonroad_scenario, original_commonroad_scenario,
        driver_id, scenario, user_id, auth_token,
        protocol, host,
                                                              port, planning_from_timestamp,
                                                              predict_with: callable, lookahead_limit: int,
                                                              lookback_limit, safety_buffer):
    # Get the stat of all the drivers in the past "lookback_limit" timestamp, create Dynamic obstacles with them
    # Note: the scenario object here is NOT a MixedTrafficScenario, but only a deserialized dictionary obtained using the API

    # Accumulate the states of all the drivers that are NOT the ego_vehicles (AV)
    all_drivers_states = {}
    # Note: we need +1 to include planning_from_timestamp
    for timestamp in range(max(planning_from_timestamp-lookback_limit, 0), planning_from_timestamp+1):
        response = _do_get_request(
            f"{protocol}://{host}:{port}{GET_VEHICLES_STATE_AT_TIMESTAMP.format(scenario_id=scenario.scenario_id, timestamp=timestamp)}",
            auth_token)
        vehicle_states: List
        vehicle_states = json.loads(response.text, object_hook=lambda d: SimpleNamespace(**d))

        for vehicle_state in [npc_state for npc_state in vehicle_states if npc_state.user_id != user_id]:
            if vehicle_state.user_id not in all_drivers_states:
                all_drivers_states[vehicle_state.user_id] = []

            all_drivers_states[vehicle_state.user_id].append(vehicle_state)

    # At this point we have all the past states of all the users that are NOT the ego_vehicle.

    # We can build a DynamicObstacle for each of them by predicting their future states and applying the safety buffer

    for the_user_id in all_drivers_states:
        past_vehicle_states = all_drivers_states[the_user_id]
        obstacle_shape = Rectangle(VEHICLE_LENGTH, VEHICLE_WIDTH)

        # Add the safety buffer around the DynamicObstacle
        obstacle_shape_with_safety_buffer = Rectangle(VEHICLE_LENGTH + 2.0 * safety_buffer,
                                                      VEHICLE_WIDTH + 2.0 * safety_buffer)
        # Predict the DynamicObstacle's future states using "predict_with". We predict "lookahead_limit" future states
        # We consider the entire trajectory here, the past, the current, and the future states
        # Past states: [to_predicted_common_road_state(past_vehicle_state) for past_vehicle_state in past_vehicle_states] + \
        predicted_state_list = [commonroad_vehicle_state for commonroad_vehicle_state in predict_with(past_vehicle_states, lookahead_limit)]

        assert predicted_state_list[0].time_step == past_vehicle_states[-1].timestamp + 1

        initial_state = to_common_road_state(past_vehicle_states[-1])

        if len(predicted_state_list) > 0:
            # state_list[0].time_step=1 != self.initial_time_step=2
            # The new trajectory - prediction starts at the timestamp of its first element
            # The beginning of this trajectory is the timestemp of the initial state
            trajectory = Trajectory(predicted_state_list[0].time_step, predicted_state_list)
            prediction = TrajectoryPrediction(trajectory, obstacle_shape_with_safety_buffer)
        else:
            prediction = None

        # Note we use the_user_id but probably we should use the_driver_id corresponding to this DO vehicles' driver_id
        # Configure the ego_vehicle_commonroad_scenario
        dynamic_obstacle_with_safety_buffer_and_predictions = DynamicObstacle(DYNAMIC_OBSTACLE_STARTING_ID + the_user_id,
                                                                              ObstacleType.CAR, obstacle_shape_with_safety_buffer,
                                                                              initial_state, prediction)
        ego_vehicle_commonroad_scenario.add_objects(dynamic_obstacle_with_safety_buffer_and_predictions)

        # Configure the original_commonroad_scenario, no predictions, no safety buffer
        dynamic_obstacle = DynamicObstacle(DYNAMIC_OBSTACLE_STARTING_ID + the_user_id, ObstacleType.CAR, obstacle_shape,
                                                                              initial_state, None)
        original_commonroad_scenario.add_objects(dynamic_obstacle)


def get_scenario(protocol, host, port, scenario_id, user_id, auth_token, logger):
    # Try to get the resorse of trigger a StopMeException()
    response = _do_get_request(
        f"{protocol}://{host}:{port}{GET_SCENARIO_BY_SCENARIO_ID.format(scenario_id=scenario_id)}",
        auth_token)

    # At this point, the scenario exists
    scenario = json.loads(response.text, object_hook=lambda d: SimpleNamespace(**d))

    if scenario.status == MixedTrafficScenarioStatusEnum.WAITING or scenario.status == MixedTrafficScenarioStatusEnum.DONE:
        logger.info(f"Background AV {user_id} in Scenario {scenario_id}. Scenario is {scenario.status}. Stop.")
        # Note: We do not reschedule the job, so it naturally stops
        raise StopMeException()

    return scenario


def drive(driver_id, user_id, scenario_id,
          auth_token,
          cache_dir,
          lookback_limit=10, # TODO: Not really sure about this one...
          lookahead_limit=20,  # Mow many future states to predict
          safety_buffer = 0.0, # Force a minimum distance between ego and the other vehicles
          replanning_frequency=1,
          predict_with=linear_prediction,
          cost_function_parameters=[[5], [5, 50, 100], [0.25, 20], [0.25, 5]],
          protocol="http", host="localhost", port=5000):

    # This function is invoked automatically and repeatedly by the Scheduler until the StopMeException is raised.

    # Create a custom logger, configure it, and share it with all the dependent functions. Not ideal
    driver_logger = logging.getLogger(f"Driver {user_id}.{driver_id}")
    # Set Logging Level
    driver_logger.setLevel(logging.DEBUG)
    # Do not propagate to parent logger
    driver_logger.propagate = False

    # The logger is a singleton, but its handlers are not.
    if len(driver_logger.handlers) < 1:
        # Create Stream Handler - INFO
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(FORMATTER)
        console_handler.setLevel(logging.WARNING)
        driver_logger.addHandler(console_handler)

    driver_logger.warning(f"Triggered. Connecting on {host}:{port}.")

    try:

        # 1. Get scenario state or fail with a StopMeException.
        scenario = get_scenario(protocol, host, port, scenario_id, user_id, auth_token, driver_logger)

        # At this point, the scenario is assumed to exist. We can ensure the cache directory exist and instantiate
        # the objects

        driver_cache_dir = os.path.join(cache_dir, f"av_user_id_{user_id}_driver_{driver_id}")


        # Scenario without any vehicle
        base_commonroad_scenario, commonroad_planning_problem, motion_planner, road_collision_checker = \
            create_motion_or_get_planner_for(driver_cache_dir, driver_id, scenario, user_id, auth_token,
                                             replanning_frequency, cost_function_parameters, protocol, host, port,
                                             driver_logger)

        driver_logger.warning(f"Logging to {driver_cache_dir}")
        # The logger is a singleton, but its handlers are not.
        if len(driver_logger.handlers) < 2:
            # This ensures the directories are created so we can create the file handler
            # We need to ensure that logging information goes to the correct file
            # File Handler - DEBUG
            file_handler = logging.FileHandler(os.path.join(driver_cache_dir, "output.log"))
            file_handler.setFormatter(FORMATTER)
            file_handler.setLevel(logging.DEBUG)
            driver_logger.addHandler(file_handler)

        # 2. Get current/last action submitted by THIS AV/Planner or fail with a StopMeException
        current_state = get_current_state(protocol, host, port, scenario_id, user_id, auth_token, driver_logger)

        if current_state is None:
            # Wait for the next round
            return

        planning_from_timestamp = current_state.timestamp

        # Inject the other vehicles inside the scenario.
        # TODO: This is what the export function does to some extent

        # Alter the scenario by including the other drivers as Dynamic Obstacles

        # This represents what the ego_vehicle sees, including safety buffers and predictions
        actual_scenario = deepcopy(base_commonroad_scenario)

        # This represents what the scenario really is
        original_scenario = deepcopy(base_commonroad_scenario)

        # Retrieve all the data about the other drivers and add them to the scenario
        # Maybe split this into:
        # retrieve the data,
        # apply the safety buffer,
        # make the prediction,
        # create the dynamic obstacle
        # create the collision checker
        # Predict the future trajectories of the various obstacles


        # Include all the info about NPC
        # Not currently logged
        _augment_scenarios_with_past_driver_data_safety_buffer_and_prediction(
            actual_scenario, original_scenario, driver_id, scenario, user_id, auth_token,
                                                protocol, host, port,
                                                planning_from_timestamp,
                                                predict_with, lookahead_limit,
                                                lookback_limit, safety_buffer)

        # Create the updated collision checker
        collision_checker_scenario = create_collision_checker(actual_scenario)
        road_boundary_obstacle, road_boundary_sg_triangles = create_road_boundary_obstacle(actual_scenario)
        collision_checker_scenario.add_collision_object(road_boundary_sg_triangles)

        x_0: State
        x_0 = to_common_road_state(current_state)

        # This is maintaining the current velocity, but we can use something else...
        # set desired velocity - TODO Read this from the reference path maybe?
        current_velocity = x_0.velocity
        motion_planner.set_desired_velocity(current_velocity)

        # What's X_CL ? Previously computed states?
        # Plan trajectory using the just configured collision_checker. This will set the emergency flag if necessary
        optimal = motion_planner.plan(x_0, collision_checker_scenario, draw_traj_set=False) # cl_states=x_cl,

        # if the planner fails to find an optimal trajectory -> terminate. At this point, planner has switched to emergency mode
        if optimal is None:
            optimal = motion_planner.emergency_plan(x_0, collision_checker_scenario, draw_traj_set=True) # cl_states=x_cl,

            # What we do now?! Retry to job is useless, but cannot find any thing else.
            # TODO Maybe go straight?
            assert optimal is not None, "The planner cannot find ANY trajectory!"

        # comp_time_end = time.time()

        # Correct orientation angle
        new_state_list = motion_planner.shift_orientation(optimal[0])

        # Decide how many states to driver based on the replanning frequency parameter. Once we store them, AV will not replan them
        planned_states = []
        for idx, planned_state in enumerate(new_state_list.state_list[1:1+replanning_frequency], start=1):
            planned_state.time_step = planning_from_timestamp + idx
            # Make sure we do not go reverse!
            if planned_state.velocity < 0.0:
                driver_logger.warning(f"Detected negative speed for {user_id} in scenario {scenario_id}")

                planned_state.velocity = 0.0
                planned_state.acceleration = 0.0

            planned_states.append(planned_state)

        # # Visualize Planning using the "transformed" scenarios to represent the ego-vehicle POV
        # # but include also the predictions and the actual trajectory of the NPC
        visualize_planning_result(scenario=actual_scenario, # This one has the safety buffer active
                                  original_scenario=original_scenario, # This one is the original one must also contain the data about NPC.
                                  planning_problem=commonroad_planning_problem,
                                  ego=motion_planner.convert_cr_trajectory_to_object(optimal[0]), # Create CommonRoad Obstacle for the ego Vehicle
                                  pos=np.asarray([state.position for state in new_state_list.state_list]),  # Get positions of optimal trajectory
                                  # Visualize Ground Truth = 0, no future vision
                                  perfect_knowledge_limit = 0,
                                  # traj_set=sampled_trajectory_bundle,
                                  # feasible_traj=feasible_trajectories,
                                  ref_path=motion_planner._original_co._reference,
                                  emergency_ref_path=motion_planner._emergency_mode_co._reference if motion_planner._emergency_mode_co is not None else None,
                                  timestep=planning_from_timestamp,
                                  save_path=driver_cache_dir)

        states_data = {
            "timestamps": ",".join([str(s.time_step) for s in planned_states]),
            "positions_x": ",".join([str(s.position[0]) for s in planned_states]),
            "positions_y": ",".join([str(s.position[1]) for s in planned_states]),
            "rotations": ",".join([str(s.orientation) for s in planned_states]),
            "speeds_ms": ",".join([str(s.velocity) for s in planned_states]),
            "accelerations_m2s": ",".join([str(s.acceleration) for s in planned_states])
        }

        response = _do_put_request(
            f"{protocol}://{host}:{port}{PUT_UPDATE_VEHICLES_STATES.format(scenario_id=scenario_id, user_id=user_id)}",
            auth_token,
            data=states_data)

        assert response.status_code == 204, f"Failed to update the states. Reason: {response.text}"
    except StopMeException as stop_me:
        driver_logger.warning(f"Execution is over!")
        raise stop_me
    except Exception as e_inf:
        driver_logger.error(f"Exception raised {e_inf}")
        raise StopMeException()



if __name__ == "__main__":
    import matplotlib
    matplotlib.use('Agg')  # disable interactive view

    user_id = 1
    scenario_id = 8
    driver_id = 15
    cache_dir = "./tmp/cache_dir"

    #
    replanning_frequency = 1

    for i in range(0, 20):
        drive(driver_id, user_id, scenario_id, cache_dir, replanning_frequency=replanning_frequency)