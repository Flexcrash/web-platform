import uuid

from itertools import cycle

from flask import current_app, jsonify, session, redirect, url_for, render_template, make_response, request
from flask import Blueprint

from av.sampling_based_motion_plannner import get_motion_plannner_for

from persistence.data_access import MixedTrafficScenarioDAO, MixedTrafficScenarioTemplateDAO, UserDAO, VehicleStateDAO
from model.mixed_traffic_scenario import MixedTrafficScenarioSchema
from model.vehicle_state import VehicleStateSchema, VehicleState
from model.collision_checking import CollisionChecker

from model.trajectory import TrajectorySampler, TrajectorySchema

from av.sampling_based_motion_plannner import get_motion_plannner_for, create_motion_planner_for

# References:
#   - https://stackoverflow.com/questions/19686533/how-to-zip-two-differently-sized-lists-repeating-the-shorter-list

# This blueprint handles the requests to the API Scenario Endpoint
scenarios_api = Blueprint('scenarios', __name__, url_prefix='/scenarios')

# Marshmallow Integrationn
scenario_schema = MixedTrafficScenarioSchema()
scenarios_schema = MixedTrafficScenarioSchema(many=True)

vehicle_state_schema = VehicleStateSchema()
vehicle_states_schema = VehicleStateSchema(many=True)

# In theory is a trajectory Bundle?
trajectories_schema = TrajectorySchema(many=True)

# TODO Add authentication


def _check_scenario_completion(scenario):
    """ Check whether the scenario is over and update its status in the db"""
    if scenario.status == "WAITING":
        return

    vehicle_state_dao = VehicleStateDAO(current_app.config)
    # TODO This is an approximation, we should check all the states !
    # Get the state of all the vehicles
    last_scenario_state = vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario.scenario_id, scenario.duration)
    if all([vehicle_state.status == "ACTIVE" or vehicle_state.status == "CRASHED" or vehicle_state.status == "GOAL_REACHED" for vehicle_state in last_scenario_state]):
        current_app.logger.info("Scenario {} is over".format(scenario.scenario_id))
        mixed_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
        mixed_scenario_dao.close_scenario(scenario)


@scenarios_api.route("/", methods=["GET"])
def get_scenarios():
    """
    Return all the scenarios that matches the query parameters (args) and that the current users is allowed to see
    :return:
    """
    # Extracts the arguments from the URL, i.e., ?created_by=1&status="ACTIVE"
    args = request.args
    # The other fields of the MixedTrafficScenario class cannot be used as query parameters
    created_by = args.get("created_by")
    status = args.get("status")
    template_id = args.get("template_id")

    current_app.logger.debug("Query scenarios using {} scenarios ".format(args))

    scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    all_scenarios = scenario_dao.get_all_scenarios(created_by, status, template_id)
    return scenarios_schema.dump(all_scenarios)


@scenarios_api.route("/currently_playing", methods=["GET"])
def get_current_scenarios():
    """
    Return all the scenarios that matches the query parameters (args) and that the current users is allowed to see
    :return:
    """
    # Extracts the arguments from the URL, i.e., ?created_by=1&status="ACTIVE"
    args = request.args
    # The other fields of the MixedTrafficScenario class cannot be used as query parameters
    user_id = args.get("user_id")

    current_app.logger.debug("Query scenarios using {} scenarios ".format(args))

    scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    all_scenarios = scenario_dao.get_all_scenarios_where_user_is_driving(user_id)
    return scenarios_schema.dump(all_scenarios)


@scenarios_api.route("/<scenario_id>/", methods=["GET"])
def get_scenario_by_id(scenario_id):
    """
    Return the scenario with the given scenario_id or 404 if not exist and if the user is allowed to see it
    :return:
    """
    scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = scenario_dao.get_scenario_by_scenario_id(scenario_id)
    current_app.logger.debug("Found {} scenario ".format(scenario))
    return (scenario_schema.dump(scenario), 200) if scenario is not None else ("", 404)


@scenarios_api.route("/create", methods=["POST"])
def create():
    """
    Create a new mixed traffic scenario from the provided data if they represent a VALID scenario
        - created_by the id of the user that owns this scenario - TODO Check this is the same user authenticated
        - n_users
        - n_avs
        - template id
        - [optional] a possibly empty list of users
        Validate the paremters:
            - created_by exists
            - template_id corresponds to an existing template
            - duration > 0 # mandatory
            - n_users >= 0 # expected number of users participating
            - n_avs >= 0
            - n_users + n_avs >= 1
            - check that len(optional users) <= n_users
            - possibly more...
    :return: API returns
        - 202 Accepted (but not finished) if the scenario is created but still waiting for people to join
        - 201 Created, i.e., ready to go if all the users/av are already present
        - 200 in case the scenario is over (it happens for the case only AVs)
    """
    # Make the form data a "Mutable" objbect
    data = dict(request.form)

    # Mandatory inputs - Make this an utility method
    assert "name" in data, "Missing name"
    assert "n_users" in data, "Missing n_users"
    assert "n_avs" in data, "Missing n_avs"
    assert "duration" in data, "Missing duration"
    assert "template_id" in data, "Missing template_id"
    assert "creator_user_id" in data, "Missing creator_user_id"

    n_users = int(data["n_users"])
    n_avs = int(data["n_avs"])
    duration_in_seconds = float(data["duration"])
    template_id = int(data["template_id"])
    creator_user_id = int(data["creator_user_id"])

    assert n_users >= 0
    assert n_avs >= 0
    assert n_users + n_avs >= 1
    assert duration_in_seconds > 0

    # If valid, update data =with the right type/values
    data["n_users"] = n_users
    data["n_avs"] = n_avs
    # Transform to steps - TODO Read the definition of the step size from somewhere...
    data["duration"] = int(duration_in_seconds / 0.1)

    mixed_traffic_scenario_template_dao = MixedTrafficScenarioTemplateDAO(current_app.config)
    scenario_template = mixed_traffic_scenario_template_dao.get_template_by_id(template_id)
    assert scenario_template is not None
    data["template"] = scenario_template

    user_dao = UserDAO(current_app.config)
    created_by = user_dao.get_user_by_user_id(creator_user_id)
    assert created_by is not None
    data["created_by"] = created_by


    # Optional Inputs
    description = data["description"] if "description" in data else None
    # TODO Consider changing the name in the form..
    # TODO This validation is not ROBUST
    preassigned_user_ids = set(data["users"].split(',') if "users" in data and len(data["users"]) > 0 else [])
    # Check the preassigned_users are OK
    preassigned_users = []
    for preassigned_user_id in preassigned_user_ids:
        preassigned_user = user_dao.get_user_by_user_id(preassigned_user_id)
        assert preassigned_user is not None, "Preassigned user is not valid"
        preassigned_users.append(preassigned_user)

    # Assert that we are not assigning more users than the available ones
    assert len(preassigned_user_ids) <= n_users
    data["users"] = preassigned_users

    # Ensure the optional inputs get a value
    data["scenario_id"] = int(data["scenario_id"]) if "scenario_id" in data else None
    data["description"] = description


    # TODO Create a DB Transaction! - AssertionErrors are reported ?
    scenario_dao = MixedTrafficScenarioDAO(current_app.config)

    # Create the new scenario and store it into the DB
    new_scenario = scenario_dao.create_new_scenario(data)

    ### This logic should be placed somewhere else?

    # Automatically register the n_avs users, if any
    for i in range(0, n_avs):
        # Generate a random BOT-User and add it to the scenario as integer
        user_id = uuid.uuid1().int
        user = user_dao.create_new_user({
            "username" : "bot_{}".format(user_id),
            "email" : "bot_{}".format(user_id) + "@flexcrash.eu",
            # Probably better some random number
            "password" : "bot_{}".format(user_id)
        })
        # Adding a user to a scenario might cause the scenario to START (ACTIVE STATE)
        # scenario_dao.add_user_to_scenario(user, new_scenario)
        _add_driver_to_scenario(new_scenario, user)

    # TODO Try to add the users provided as inputs. Since now we treat them as set
    #  repetitions should not be a problem
    for preassigned_user in preassigned_users:
        _add_driver_to_scenario(new_scenario, preassigned_user)

    # At this point we add all the AVs and

    # Trigger the evolution - Skip if already done!
    _trigger_avs(new_scenario, 0)
    # Check whether the scenario is over. This will change the scenario as well, so w
    _check_scenario_completion(new_scenario)

    # Return the latest version
    updated_scenario = scenario_dao.get_scenario_by_scenario_id(new_scenario.scenario_id)
    # Reload the scenario - Somehow there's no way to call the API directly... one should indeed the actual call!

    assert updated_scenario.status in ["WAITING", "ACTIVE", "DONE"]

    if updated_scenario.status == "ACTIVE":
        response_status_code = 201
    elif updated_scenario.status == "WAITING":
        response_status_code = 202
    else:
        # updated_scenario.status == "DONE":
        response_status_code = 200

    return scenario_schema.dump(updated_scenario), response_status_code


@scenarios_api.route("/delete/<scenario_id>", methods=["DELETE"])
def delete(scenario_id):
    scenario_dao = MixedTrafficScenarioDAO(current_app.config)

    scenario_dao.delete_scenario_by_id(scenario_id)

    return "", 200


def _evolve_scenario_for_av_from_current_state(scenario, driver, current_timestamp):
    """
    We check if the driver can plan any action or not FROM this timestamp (it might have planned its action
    or it might still need to wait for the others to plan their actions or the scenario might be already DONE)


    :param scenario:
    :param driver:
    :param timestamp:
    :return:
    """

    current_app.logger.info("Try to evolve AV {} FROM timestamp {}".format(driver.user_id, current_timestamp))

    scenario_dao = MixedTrafficScenarioDAO(current_app.config)

    # This one is possible ONLY after we close the scenario, and that code is not yet triggered
    updated_scenario_status = scenario_dao.get_scenario_state_at_timestamp(scenario.scenario_id, current_timestamp, propagate=True)
    if updated_scenario_status == "DONE" or updated_scenario_status == "WAITING":
        current_app.logger.info("Scenario not in an actionable state {}".format(updated_scenario_status))
        return
    else:
        current_app.logger.debug("Scenario in an actionable state {}".format(updated_scenario_status))


    # If this vehicle at this timestamp was already invoked, it planned a state, so at this timestamp it will be WAITING or DONE or CRASH or GOAL_Reached, but NOT PENDING
    vehicle_state_dao = VehicleStateDAO(current_app.config)

    state_of_driver_at_current_timestamp = vehicle_state_dao.get_vehicle_state_by_scenario_timestamp_driver(scenario, current_timestamp, driver)

    # At this step, the driver might be in ACTIVE state (it is ready to plan the next move)
    # If state is PENDING, we did not submit any move, but neither the others, so we do not have enough data to plan
    # If state is CRASHED, we cannot do anything
    # If state is GOAL_REACHED, we cannot do anything
    # If state is WAITING, we already planned this state (we should not do anything!)
    # TODO We assume that is t=1 is PENDING, also t>1 is PENDING!

    # # Make sure we propagate the triggering if the state is GOAL_REACHED or CRASHED
    # if state_of_driver_at_current_timestamp.status == "GOAL_REACHED":
    #     # TODO This seems the simplest implementation, just try the next timestamp. Ideally we could ff to the latest state
    #     # Ensures that if this is the last AV all the others wake up
    #     current_app.logger.info("Vehicle has reached state {} at timestamp {} ".format(state_of_driver_at_current_timestamp.status, current_timestamp))
    #     next_timestamp = current_timestamp + 1
    #
    #     if next_timestamp > scenario.duration:
    #         current_app.logger.info(">> Reached the end of the scenario at timestamp {} ".format(next_timestamp))
    #     else:
    #         current_app.logger.info(">> Retriggering all AVS from timestamp {} ".format(next_timestamp))
    #         _trigger_avs(scenario, next_timestamp)
    #     return

    # TODO What's the logic? We need to check whether we can use the state at current time stamp for planning. Basically, if this is the last planned state
    # If this is PENDING or WAITING, it means that we cannot use it for planning further moves
    # If this is CRASHED or GOAL_REACHED, there's nothign this driver can do
    # So the ONLY option is ACTIVE (at that time, it was active)
    if state_of_driver_at_current_timestamp.status != "ACTIVE":
        current_app.logger.debug(
            "Scenario evolution for Scenario {} and Driver {} at Timestamp {} cannot take place from STATE = {}".format(
                scenario.scenario_id, driver.user_id, current_timestamp, state_of_driver_at_current_timestamp.status
            ))
        return

    # At this point we consider only ACTIVE states, that can be used to plan future moves

    # Get a reference  of the motion planner corresponding to the bot user
    motion_planner = get_motion_plannner_for(driver)

    # The internal AV does not replan!
    if current_timestamp < motion_planner.last_planned_state:
        current_app.logger.debug(
            "AV {} already planned from at Timestamp {} in Scenario {}".format(
                driver.user_id, current_timestamp, scenario.scenario_id))
        return

    # How long in the future the planner will plan, e.g., how many states it will plan before the end
    # TODO For the moment this code does not work for AV Motion planners, so they must return only one state at a time
    final_timestamp = current_timestamp + motion_planner.planning_horizon
    planning_steps = motion_planner.planning_horizon
    # How many states before the end?
    if final_timestamp > scenario.duration:
        planning_steps = final_timestamp - scenario.duration -1
        if planning_steps == 0:
            current_app.logger.debug(
                "Scenario evolution for Scenario {} and BOT AV {} at Timestamp {} is over".format(
                    scenario.scenario_id, driver.user_id, final_timestamp
                ))
            return

        else:
            current_app.logger.debug(
                "Scenario evolution for Scenario {} and Driver {} at Timestamp {} can evolve only {} steps".format(
                    scenario.scenario_id, driver.username, final_timestamp, planning_steps
                ))

    # This is already taken care of in line 276
    # # If the current step is already planned, we need to skip this execution to avoid double planning

    # for step in range(1, planning_steps + 1):
    #     # Filter the states with matching timestamp
    #     timestamp = current_timestamp + step
    #     vehicle_state_to_compute = next((driver_state for driver_state in driver_states
    #                                      if driver_state.timestamp == timestamp), None)
    #     assert vehicle_state_to_compute is not None
    #     if vehicle_state_to_compute.status != "PENDING": # or vehicle_state_to_compute.status == "WAITING":
    #         current_app.logger.debug(
    #             "Scenario evolution for Scenario {} and Driver {} at Timestamp {} already took place".format(
    #                 scenario.scenario_id, driver.username, timestamp
    #             ))
    #         return

    # At this point we can plan at least planning_steps in the future

    # Retrieve the state of all the vehicles at the current_timestamp, the planner needs to know what the other vehicles are
    state_of_drivers_at_current_timestamp = vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario.scenario_id,
                                                                                              current_timestamp)
    # Invoke the planner so we can get the next states from the current_scenario_state.timestamp

    # Make sure we "hide" vehicles that already reached the goal from this planner!
    state_of_currently_in_game_drivers_at_current_timestamp = [s for s in state_of_drivers_at_current_timestamp if s.status != "GOAL_REACHED"]

    # Now try to plan the move
    planned_states = motion_planner.plan(state_of_currently_in_game_drivers_at_current_timestamp)

    # current_app.logger.info("AV {} planned {} states ".format(driver.user_id, len(planned_states)))

    # Take only the stated we can indeed make use of (including  duration)
    planned_states = planned_states[:planning_steps]

    # Sort by timestamp
    planned_states.sort(key=lambda s: s.time_step)

    # Retrieve all the states for this driver, we need to UPDATE them, not create new ones!
    driver_states = vehicle_state_dao.get_states_in_scenario_of_driver(scenario.scenario_id, driver.user_id)
    # Extract data from the returned states and update the vehicle states in the DB
    for planned_state in planned_states:

        # Retrieve the driver state corresponding to the planned one
        vehicle_state_to_update = next((driver_state for driver_state in driver_states if driver_state.timestamp == planned_state.time_step), None)

        # THIS BREAKS THE AUTOMATIC TRIGGERING OF AVs
        # if vehicle_state_to_update.status != "PENDING":
        #     current_app.logger.info(">>>>>>>    Try to updating state {} for Driver {} in Scenario {} from Timestamp {}".format(
        #         vehicle_state_to_update.status, driver.user_id, scenario.scenario_id, vehicle_state_to_update.timestamp
        #     ))
        # continue

        assert vehicle_state_to_update is not None
        assert vehicle_state_to_update.status == "PENDING", "Wrong status {} for vehicle_state_to_update for driver {}".format(
            vehicle_state_to_update.status, driver.user_id)

        vehicle_state_to_update.position_x = float(planned_state.position[0])
        vehicle_state_to_update.position_y = float(planned_state.position[1])
        vehicle_state_to_update.speed_ms = float(planned_state.velocity) # No idea why this is a tuple...
        vehicle_state_to_update.acceleration_m2s = float(planned_state.acceleration) # No idea why this is a tuple...
        vehicle_state_to_update.rotation = float(planned_state.orientation) # No idea why this is a tuple...

        # Do the DB update
        current_app.logger.info("Updating state for AV {} in Scenario {} from Timestamp {}".format(
            driver.user_id, scenario.scenario_id, vehicle_state_to_update.timestamp
        ))

        # This call will automatically update and render all the states, if necessary. For instance, if a car reaches GOAL, all the future states are GOAL_REACHED
        # Because we check that no future planned state can be in NOT PENDING, we need to skip the next states
        # TODO Make sure this is also true for CRASHED
        skip_remaining_planned_states = vehicle_state_dao.update_driver_state_in_scenario(scenario, driver, vehicle_state_to_update)

        # Make sure we store the last planned state!
        motion_planner.last_planned_state = vehicle_state_to_update.timestamp

        # Ensures that if this is the last AV all the others wake up
        current_app.logger.info(">> Retriggering all AVS from timestamp {} ".format(vehicle_state_to_update.timestamp))
        _trigger_avs(scenario, vehicle_state_to_update.timestamp)

        if skip_remaining_planned_states:
            current_app.logger.info("AV {} reached the GOAL".format(driver.user_id))
            break


def _check_collisions(scenario, driver, scenario_state):
    # TODO: We have check collisions in two places, here and in data_access#1500. Why?!

    # Note there must be at least one state
    # TODO Why not simply timestamp as input?
    timestamp = scenario_state[0].timestamp
    #
    current_app.logger.info("Checking collision for scenario {} at timestamp {} ".format(scenario.scenario_id, timestamp))
    # Invoke the collision checker and if a state is CRASH it cannot be restored (must remain CRASH)
    vehicle_state_dao = VehicleStateDAO(current_app.config)

    collision_checker = CollisionChecker(vehicle_state_dao)
    crashed_drivers_with_states = collision_checker.check_for_collisions(scenario, timestamp)

    for crashed_driver, crash_state in crashed_drivers_with_states:
        # Update ONLY the states for this driver. This results in possibly checking the same collision multiple times
        if crashed_driver.user_id == driver.user_id:
            vehicle_state_dao.driver_crashed_at_timestamp_in_scenario(scenario, crashed_driver, crash_state)
            # Notify the crash happened
            return True

    # Notify the crash did not happened for this driver
    return False


def _check_and_activate_scenario(scenario):
    """
    Check whether we filled all the positions for the scenario and whether the scenario is valid:
        - no collision (TODO Near-collisions)
        - all reacheable goal area
    """

    if len(scenario.drivers) == scenario.max_players:
        # TODO Validity should be checked BEFORE, and Initial States and Goal Areas should be preallocated!
        current_app.logger.info("Scenario {} is ready to start".format(scenario.scenario_id))

        mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)

        # Activate the scenario computing the initial state for all drivers (so timestamp==0 implies status=="ACTIVE")
        mixed_traffic_scenario_dao.activate_scenario(scenario)
        # Make sure we activate the AVs at this point

        # Make sure we register all the planners - This is a bit awkward... but we cannot do it before now
        for driver in scenario.drivers:
            if "bot_" in driver.username:
                initial_state = mixed_traffic_scenario_dao.get_initial_state_for_driver_in_scenario(driver, scenario)
                goal_region_as_rectangle = mixed_traffic_scenario_dao.get_goal_region_for_driver_in_scenario(driver,
                                                                                                             scenario)
                create_motion_planner_for(scenario, driver, initial_state, goal_region_as_rectangle)

        # Triggers an AssertionError if not valid
        current_app.logger.info("Validating scenario {}".format(scenario.scenario_id))
        mixed_traffic_scenario_dao.validate(scenario)

        _trigger_avs(scenario, 0)


def _add_driver_to_scenario(scenario, driver):
    """ Add the driver to the scenario and trigger the AV logic IF scenario becomes ACTIVE"""

    try:
        mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
        # This might fail, but the exception will be captured by the catch-all logic inside the API layer
        mixed_traffic_scenario_dao.add_user_to_scenario(driver, scenario)
        # Note we cannot generate the Planner until the scenario is active, otherwise, we do not have their initial states
    except Exception as e:
        # current_app.logger.exception("Error occured while creating new driver {} ".format(type(e).__name__))
        # Make sure that this is not an SQL Integrity Error, otherwise let it raises the 500
        assert "IntegrityError" not in type(e).__name__
        # Propagate the exception
        raise e

    _check_and_activate_scenario(scenario)


def _trigger_avs(scenario, current_state_timestamp):
    """
    Make sure we invoke all the AVS to (possibly) update their state from the current_state_timestamp
    :param scenario:
    :param current_state_timestamp:
    :return:
    """

    current_app.logger.info("--------- START Trigger AV timestamp: {} ----".format(current_state_timestamp))

    for driver in scenario.drivers:
        if "bot_" in driver.username:
            # current_app.logger.info("Scheduling BOT AV {} for Scenario {} from Timestamp {}".format(
            #     driver.user_id, scenario.scenario_id, current_state_timestamp
            # ))
            _evolve_scenario_for_av_from_current_state(scenario, driver, current_state_timestamp)
    current_app.logger.info("-------- END Trigger AV timestamp: {} ----".format(current_state_timestamp))

@scenarios_api.route("/<scenario_id>/drivers/", methods=["POST"])
def create_driver(scenario_id):
    """
    Create a new driver, i.e., add an existing user to the given scenario. Might fail if DB constraints are
    violated or user (returns 422) and scenario do not exist (404).
    :return: 201
    """

    # Make the input data mutable
    data = dict(request.form)

    # Validate the input

    # Is the mandatory field there?
    assert "user_id" in data, "Missing user_id"
    user_id = int(data["user_id"])

    # Does the user_id correspond to an existing user?
    user_dao = UserDAO(current_app.config)
    user = user_dao.get_user_by_user_id(user_id)
    assert user is not None

    # Does the scenario_id correspond to an existing scenario?
    mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = mixed_traffic_scenario_dao.get_scenario_by_scenario_id(scenario_id)
    if scenario is None:
        return "Scenario not found", 404

    _add_driver_to_scenario(scenario, user)

    # Check whether the scenario is over, but only if the sc
    _check_scenario_completion(scenario)

    # If everything is ok, we return a 204 (accepted but no content)
    return "", 204


@scenarios_api.route("/<scenario_id>/drivers/<driver_id>/states/", methods=["GET"])
def get_vehicle_states(scenario_id, driver_id):
    """
    Return all the states for the driver identified by driver_id in the scenario identified by scenario_id
    """

    # Validate the input

    # TODO Code duplication, pretty sure this can be solved with nesting of requests

    # Does the scenario_id correspond to an existing scenario?
    mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = mixed_traffic_scenario_dao.get_scenario_by_scenario_id(scenario_id)
    if scenario is None:
        return "Scenario not found", 404

    # Does the scenario_id correspond to an existing scenario?
    user_dao = UserDAO(current_app.config)
    driver = user_dao.get_user_by_user_id(driver_id)
    if driver is None:
        return "Driver not found", 404

    vehicle_state_dao = VehicleStateDAO(current_app.config)
    all_states = vehicle_state_dao.get_states_in_scenario_of_driver(scenario_id, driver_id)
    all_states.sort(key=lambda s: s.timestamp)
    return vehicle_states_schema.dump(all_states)


@scenarios_api.route("/<scenario_id>/drivers/<driver_id>/states/", methods=["PUT"])
def update_vehicle_states(scenario_id, driver_id):
    """
    Update the scenario states associated with the driver id. This might trigger the various AV
    Return success-no-content (204) if the updates are accepted.

    If the states correspond to existing, but still modifiable states, all the (future) states are
    deleted to ensure no spurious states exist.

    TODO We should use transactions to be safe, but that would require a deep re-design
    """

    # Validate the input: TODO Code duplication, pretty sure this can be solved with nesting of blueprints

    # Does the scenario_id correspond to an existing scenario?
    mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = mixed_traffic_scenario_dao.get_scenario_by_scenario_id(scenario_id)
    if scenario is None:
        return "Scenario not found", 404

    # Does the user_id correspond to an existing user?
    user_dao = UserDAO(current_app.config)
    driver = user_dao.get_user_by_user_id(driver_id)
    # Is this user also a driver in this scenario?
    assert driver in scenario.drivers, "Not a driver in the scenario"

    # If the status is "DONE" the request is wrong
    assert scenario.status in ["WAITING", "ACTIVE"]

    # If the status is "WAITING" the request must be re-send in the future (too early)
    if scenario.status == "WAITING":
        return "Scenario not yet started", 425

    # If the status is "ACTIVE" the request can go on

    # Make the input data mutable
    data = dict(request.form)

    # Validate inputs. Note the plural: each driver can submit one or more states (as part of a trajectory)
    # TODO Should we use the latest PENDING state as first timestamp?
    # Mandatory inputs must be there
    assert "timestamps" in data
    assert "positions_x" in data
    assert "positions_y" in data
    assert "rotations" in data
    assert "speeds_ms" in data
    # TODO Not sure about the accelerations
    assert "accelerations_m2s" in data

    # Create the local objects
    # vehicle_state_id, status, timestamp, user_id, scenario_id, position_x, position_y, rotation, speed_ms, acceleration_m2s
    planned_states = [VehicleState(*vs) for vs in zip(cycle([None]), cycle(["PENDING"]),
                                                      [int(x) for x in data["timestamps"].split(",")], # make sure those are integers
                                                      cycle([driver_id]), cycle([scenario_id]), data["positions_x"].split(","), data["positions_y"].split(","),
                                 data["rotations"].split(","), data["speeds_ms"].split(","), data["accelerations_m2s"].split(","))]
    planned_states.sort(key=lambda s: s.timestamp)

    # If we are not updating any existing state, i.e., all the timestamp are beyond the end of the scenario,
    # the request is not valids
    assert planned_states[0].timestamp <= scenario.duration

    vehicle_state_dao = VehicleStateDAO(current_app.config)

    # To update many states, we update one state after the other in the context of the same request, unless those are ACTIVE or CRASH
    skip_reset = False
    for planned_state in planned_states:

        # TODO Not sure this  is the best, but if we go over board, we silently capture the error (but do not fail)
        if planned_state.timestamp <= scenario.duration:

            # This update the scenario state to WAITING or ACTIVE, but if it is CRASH or GOAL_REACHED do not do anything...
            skip_remaining_planned_states = vehicle_state_dao.update_driver_state_in_scenario(scenario, driver, planned_state)

            if skip_remaining_planned_states:
                current_app.logger.info("Driver {} is Done. Skip all the remaining planned states".format(driver.user_id))
                skip_reset = True
                break

            # Refresh the scenario state
            scenario_state = vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario.scenario_id,
                                                                                              planned_state.timestamp)

            # At this point we need to check for ALREADY HAPPENED collisions
            # Is the state ready for checking? all ACTIVE or CRASH
            # NOT SURE why we check collisions ONE BY ONE...
            if all(s.status == "ACTIVE" or s.status == "CRASHED" for s in scenario_state):
                if _check_collisions(scenario, driver, scenario_state):
                    # Do not try to update the other states, as they are already updated by the previous call
                    current_app.logger.info("> Do not try to update the other states, as they are already updated by the previous call")
                    break

            current_app.logger.info("Planned State for user {} at timestamp {}"
                                    .format(driver.user_id, planned_state.timestamp))
            _trigger_avs(scenario, planned_state.timestamp)
        else:
            current_app.logger.info("Planned State for user {} at timestamp {} is over duration {}. "
                                    "Ignore it".format(driver.user_id, planned_state.timestamp, scenario.duration))

    # Delete any future state to ensure nothing spurious remains from previous planning if any planning took place.
    # Reset should be skipped for CRASH and GOAL_REACHED
    if not skip_reset:
        timestamp_to_delete = planned_states[-1].timestamp + 1
        while timestamp_to_delete <= scenario.duration:
            current_app.logger.info("Resetting State for user {} at timestamp {}"
                                    .format(driver.user_id, timestamp_to_delete))
            # TODO Make this updates in bulk
            vehicle_state_dao.reset_state_for_driver_in_scenario_at_timestamp(driver, scenario, timestamp_to_delete)
            timestamp_to_delete = timestamp_to_delete + 1

    # Check whether the scenario is over
    _check_scenario_completion(scenario)

    # We do not return anything here!
    return "", 204

# @scenarios_api.route("/vehicle_states/<vehicle_state_id>", methods=["GET"])
@scenarios_api.route("/<scenario_id>/drivers/<driver_id>/states/<timestamp>/trajectories", methods=["GET"])
def compute_trajectories_from_state(scenario_id, driver_id, timestamp, snap_to_road):

    # Get the current state of the driver in the scenario at given timestamp
    # TODO This common logic might be refactored - START
    # Does the scenario_id correspond to an existing scenario?
    mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = mixed_traffic_scenario_dao.get_scenario_by_scenario_id(scenario_id)

    if scenario is None:
        return "Scenario not found", 404

    user_dao = UserDAO(current_app.config)
    driver = user_dao.get_user_by_user_id(driver_id)
    if driver is None:
        return "Driver not found", 404

    vehicle_state_dao = VehicleStateDAO(current_app.config)

    scenario_state = vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario_id, timestamp)
    driver_state = next((state for state in scenario_state if state.user_id == driver.user_id), None)
    assert driver_state is not None, f"Cannot find Driver {driver_id} state at timestamp {timestamp}"

    # Check that state is still "workable", i.g., PENDING or WAITING
    # In theory this is not necessary, in nthe worse case we reject any update to it?
    # Probably better reutn a 403 NOT ALLOWED
    # Which status should be ACTIVE? Meaning that from THAT state you can move on
    assert driver_state.status == "ACTIVE" # or driver_state.status == "PENDING"

    mixed_traffic_scenario = scenario
    initial_state = mixed_traffic_scenario_dao.get_initial_state_for_driver_in_scenario(driver, scenario)
    goal_region_as_rectangle = mixed_traffic_scenario_dao.get_goal_region_for_driver_in_scenario(driver, scenario)

    # Extracts the arguments from the URL, i.e., ?created_by=1&status="ACTIVE"
    # args = request.args

    trajectory_sampler = TrajectorySampler(mixed_traffic_scenario, initial_state, goal_region_as_rectangle, snap_to_road)
    feasible_trajectories = trajectory_sampler.sample_trajectories(driver_state)

    return trajectories_schema.dump(feasible_trajectories)