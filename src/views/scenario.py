import uuid

from itertools import cycle

from flask import current_app, request
from flask import Blueprint

from typing import Tuple

from persistence.user_data_access import UserDAO

from model.user import User
from model.driver import Driver

from persistence.mixed_scenario_template_data_access import MixedTrafficScenarioTemplateDAO
from persistence.mixed_scenario_data_access import MixedTrafficScenarioDAO
from persistence.vehicle_state_data_access import VehicleStateDAO
from persistence.driver_data_access import DriverDAO

from model.vehicle_state import VehicleState, VehicleStatusEnum
from model.collision_checking import CollisionChecker
from model.trajectory import TrajectorySampler, TrajectorySchema
from model.mixed_traffic_scenario import MixedTrafficScenarioStatusEnum

from api.serialization import MixedTrafficScenarioSchema, VehicleStateSchema, DriverSchema

from background.scheduler import deploy_av_in_background, undeploy_av
from views.authentication import jwt_required, create_the_token
import json

# References:
#   - https://stackoverflow.com/questions/19686533/how-to-zip-two-differently-sized-lists-repeating-the-shorter-list

# This blueprint handles the requests to the API Scenario Endpoint
scenarios_api = Blueprint('scenarios', __name__, url_prefix='/scenarios')

# Marshmallow Integrationn
scenario_schema = MixedTrafficScenarioSchema()
scenarios_schema = MixedTrafficScenarioSchema(many=True)

vehicle_state_schema = VehicleStateSchema()
vehicle_states_schema = VehicleStateSchema(many=True)

driver_schema = DriverSchema()
drivers_schema = DriverSchema(many=True)

# In theory is a trajectory Bundle?
trajectory_schema = TrajectorySchema()
trajectories_schema = TrajectorySchema(many=True)

from background import scheduler

def _check_scenario_completion(scenario):
    """ Check whether the scenario is over and update its status in the db"""
    if scenario.status == MixedTrafficScenarioStatusEnum.WAITING:
        return

    mixed_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    vehicle_state_dao = VehicleStateDAO(current_app.config, mixed_scenario_dao)
    # TODO This is an approximation, we should check all the states !
    # Get the state of all the vehicles
    last_scenario_state = vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario.scenario_id, scenario.duration)
    if all([vehicle_state.status == VehicleStatusEnum.ACTIVE or vehicle_state.status == VehicleStatusEnum.CRASHED or vehicle_state.status == VehicleStatusEnum.GOAL_REACHED for vehicle_state in last_scenario_state]):
        current_app.logger.info("Scenario {} is over".format(scenario.scenario_id))
        mixed_scenario_dao.close_scenario(scenario)
        for driver in scenario.drivers:
            if driver.user.username.startswith("bot_"):
                undeploy_av(driver)

@scenarios_api.route("/", methods=["GET"])
@jwt_required()
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

# TODO Break the API
@scenarios_api.route("/currently_playing", methods=["GET"])
@jwt_required()
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
@jwt_required()
def get_scenario_by_id(scenario_id):
    """
    Return the scenario with the given scenario_id or 404 if not exist and if the user is allowed to see it
    :return:
    """
    scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = scenario_dao.get_scenario_by_scenario_id(scenario_id)
    current_app.logger.debug("Found {} scenario ".format(scenario))
    return (scenario_schema.dump(scenario), 200) if scenario is not None else ("", 404)


@scenarios_api.route("/get_vehicle_positions", methods=["POST"])
@jwt_required()
def get_vehicle_positions():

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

    scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario_dao.get_vehicle_positions()


@scenarios_api.route("/create", methods=["POST"])
@jwt_required()
def create():
    """
    We create a number of entries one for each driver, then we associate the available drivers to the various users
    Drivers have initial state and goal region since the beginning

    :return: API returns
        - 201 Created, i.e., ready to go if all the users/av are already present
        - 202 Accepted (but not finished) if the scenario is created but still waiting for people to join
        - 200 in case the scenario is over (it happens for the case only AVs)
    """
    # Make the form data a "Mutable" objbect
    data = dict(request.form)

    # Mandatory inputs - Make this an utility method
    assert "name" in data, "Missing name"
    assert "duration" in data, "Missing duration"
    assert "scenario_template_id" in data, "Missing template_id"
    assert "creator_user_id" in data, "Missing creator_user_id"

    # Backward comnpatibility
    data["template_id"] = data["scenario_template_id"]
    # Extract the data about the users
    # assert "n_users" in data, "Missing n_users"
    # assert "n_avs" in data, "Missing n_avs"

    # assert "id_array" in data, "Missing id_array"
    # Extract drivers data
    drivers_data = {}
    # TODO Validate the fields directly while collecting them - or make it fail at DB!
    # for initial_speed_key in [ k for k in data.keys() if str(k).endswith("_speed")]:
    #     initial_speed_value = float(data[initial_speed_key])
    #     assert current_app.config["MIN_INIT_SPEED_M_S"] <= initial_speed_value <= current_app.config["MAX_INIT_SPEED_M_S"], \
    #         f"Initial speed {initial_speed_value} for driver {initial_speed_key.replace('_speed', '')} " \
    #         f"out of range [{current_app.config['MIN_INIT_SPEED_M_S']} - {current_app.config['MAX_INIT_SPEED_M_S']}]"
    #         assert initial_state is not None, "Missing initial state"
    #         assert goal_area is not None, "Missing goal area"

    for key, value in [ (k, v) for (k, v) in data.items() if k not in ["name", "duration", "description", "creator_user_id", "template_id", "scenario_template_id"]]:

        if key.endswith("_x_is"): # Initial State Position X
            driver_id = key.split("_")[0]
            driver_data = drivers_data[driver_id ] if driver_id  in drivers_data else {}
            driver_data["x_is"] = float(value)
            drivers_data[driver_id] = driver_data
        elif key.endswith("_y_is"): # Initial State Position Y
            driver_id = key.split("_")[0]
            driver_data = drivers_data[driver_id] if driver_id in drivers_data else {}
            driver_data["y_is"] = float(value)
            drivers_data[driver_id] = driver_data
        elif key.endswith("_v_is"): # Initial State Velocity - Km/h
            driver_id = key.split("_")[0]
            driver_data = drivers_data[driver_id] if driver_id in drivers_data else {}
            driver_data["v_is"] = float(value)
            drivers_data[driver_id] = driver_data
        elif key.endswith("_x_ga"): # Goal Area Position X
            driver_id = key.split("_")[0]
            driver_data = drivers_data[driver_id] if driver_id in drivers_data else {}
            driver_data["x_ga"] = float(value)
            drivers_data[driver_id] = driver_data
        elif key.endswith("_y_ga"): # Goal Area Position Y
            driver_id = key.split("_")[0]
            driver_data = drivers_data[driver_id] if driver_id in drivers_data else {}
            driver_data["y_ga"] = float(value)
            drivers_data[driver_id] = driver_data
        elif key.endswith("_typology"):
            driver_id = key.split("_")[0]
            driver_data = drivers_data[driver_id] if driver_id in drivers_data else {}
            driver_data["typology"] = value
            drivers_data[driver_id] = driver_data
        elif key.endswith("_user_id"):
            try:
                driver_id = key.split("_")[0]
                driver_data = drivers_data[driver_id] if driver_id in drivers_data else {}
                driver_data["user_id"] = int(value)
                drivers_data[driver_id] = driver_data
            except ValueError:
                assert value == "", f"Invalid value {value} for {key}"

    unregistered_users = [d for d in drivers_data.values() if d["typology"] == "human" and "user_id" not in d]
    preregistered_users = [d for d in drivers_data.values() if d["typology"] == "human" and "user_id" in d]
    avs = [d for d in drivers_data.values() if d["typology"] == "av"]

    n_users = len(unregistered_users) + len(preregistered_users)
    n_avs = len(avs)

    duration_in_seconds = float(data["duration"])
    template_id = int(data["template_id"])
    creator_user_id = int(data["creator_user_id"])

    # TODO Creator exists?

    assert n_users >= 0
    assert n_avs >= 0
    assert n_users + n_avs >= 1
    assert duration_in_seconds > 0

    data["n_users"] = n_users
    data["n_avs"] = n_avs

    # Transform to steps
    data["duration"] = int(duration_in_seconds / 0.1)
    data["template_id"] = template_id

    user_dao = UserDAO()

    data["created_by"] = int(creator_user_id)
    data["scenario_id"] = int(data["scenario_id"]) if "scenario_id" in data else None

    # Optional Inputs
    description = data["description"] if "description" in data else None
    data["description"] = description

    # TODO Create a DB Transaction! - AssertionErrors are reported ? Becasue there are commits here and there!
    scenario_dao = MixedTrafficScenarioDAO(current_app.config)

    # Create the new scenario and store it into the DB: this creates automatically the right amount of
    # drivers but they are not yet assigned to anyone. Additionally, drivers have no initial state or goal area

    # TODO Update this logic such that Drivers do not have nullable fields
    new_scenario = scenario_dao.create_new_scenario(data)

    # We have driver data at this point, automatically register the AVs, this will create "bot_" users

    for av in avs:
        # Generate a random BOT-User and add it to the scenario as integer
        user_id = uuid.uuid1().int
        user = user_dao.create_new_user({
            "username" : "bot_{}".format(user_id),
            "email" : "bot_{}".format(user_id) + "@fc",
            "password" : "bot_{}".format(user_id) # TODO Use random instead
        })

        initial_x = float(av["x_is"])
        initial_y = float(av["y_is"])
        # We get Km/h not m/s, but internally we need m/s
        initial_speed_m_s = float(av["v_is"]) / 3.6

        goal_x = float(av["x_ga"])
        goal_y = float(av["y_ga"])

        initial_state = ( (initial_x, initial_y), initial_speed_m_s )
        goal_area = (goal_x, goal_y)

        # Add the new user to a scenario and set its initial state and goal area at once
        driver = _add_driver_to_scenario(new_scenario, initial_state, goal_area, user=user)

        # Deploy the AV in background - We are adding an AV!
        deploy_av_in_background(driver, create_the_token(driver.user))

        # If the user was added and the deployment was ok; check whether the scenario can be activated
        # or we need to wait for additional drivers
        _check_and_activate_scenario(new_scenario)

    for user in preregistered_users:

        preassigned_user = user_dao.get_user_by_user_id(user["user_id"])
        assert preassigned_user is not None, "Preassigned user is not valid"

        initial_x = float(user["x_is"])
        initial_y = float(user["y_is"])
        initial_speed_m_s = float(user["v_is"]) / 3.6

        goal_x = float(user["x_ga"])
        goal_y = float(user["y_ga"])

        initial_state = ((initial_x, initial_y), initial_speed_m_s)
        goal_area = (goal_x, goal_y)

        # Adding a user to a scenario and setting its initial state and goal area at once
        # might cause the scenario to START (ACTIVE STATE)
        _add_driver_to_scenario(new_scenario, initial_state, goal_area, user=preassigned_user)
        # If the user was added and the deployment was ok; check whether the scenario can be activated
        # or we need to wait for additional drivers
        _check_and_activate_scenario(new_scenario)


    # Add the necessary drivers waiting for any user to play them
    for user in unregistered_users:
        initial_x = float(user["x_is"])
        initial_y = float(user["y_is"])
        initial_speed_m_s = float(user["v_is"]) / 3.6

        goal_x = float(user["x_ga"])
        goal_y = float(user["y_ga"])

        initial_state = ((initial_x, initial_y), initial_speed_m_s)
        goal_area = (goal_x, goal_y)

        _add_driver_to_scenario(new_scenario, initial_state, goal_area)

    # At this point we have all the information to tell whether the scenario is valid or not from a semantic point of view.
    # TODO:
    #
    #
    #  at this point the scenario is ALREADY in the database and since we do not have proper transactions,
    # we need to forcefully manually of the validation is wrong!
    try:
        scenario_dao.validate(new_scenario)
    except AssertionError as a_err:
        raise a_err
    except Exception as exc_info:
        import traceback
        import sys

        print(traceback.format_exc())
        # or
        print(sys.exc_info()[2])
        exc_info = str(exc_info)
        raise AssertionError(f"Cannot build the scenario {exc_info}")

    # Return the latest version - This should NOT be needed - Not sure how t
    updated_scenario = scenario_dao.get_scenario_by_scenario_id(new_scenario.scenario_id)
    # Reload the scenario - Somehow there's no way to call the API directly... one should indeed the actual call!

    # NOTE: We deployed AV in background, so the scenario cannot end instantaneously
    assert updated_scenario.status in [ MixedTrafficScenarioStatusEnum.WAITING, MixedTrafficScenarioStatusEnum.ACTIVE]

    if updated_scenario.status == MixedTrafficScenarioStatusEnum.ACTIVE:
        response_status_code = 201
    elif updated_scenario.status == MixedTrafficScenarioStatusEnum.WAITING:
        response_status_code = 202
    else:
        raise AssertionError(f"Scenario {updated_scenario.scenario_id} is in wrong state {updated_scenario.status}")

    return scenario_schema.dump(updated_scenario), response_status_code


@scenarios_api.route("/delete/<scenario_id>", methods=["DELETE"])
@jwt_required()
def delete(scenario_id):
    #TODO check that whoever is issuing this request can indeed to it
    scenario_dao = MixedTrafficScenarioDAO(current_app.config)

    scenario_to_delete = scenario_dao.get_scenario_by_scenario_id(scenario_id)

    for driver in scenario_to_delete.drivers:
        # Note that a driver might NOT have a user assigned to it (e.g., WAITING scenario)
        if driver.user and driver.user.username.startswith("bot_"):
            undeploy_av(driver)

    scenario_dao.delete_scenario_by_id(scenario_id)

    return "", 200


def _check_collisions(scenario, driver, scenario_state):
    # TODO: We have check collisions in two places, here and in data_access#1500. Why?!

    # Note there must be at least one state
    # TODO Why not simply timestamp as input?
    timestamp = scenario_state[0].timestamp
    #
    current_app.logger.info("Checking collision for scenario {} at timestamp {} ".format(scenario.scenario_id, timestamp))
    # Invoke the collision checker and if a state is CRASH it cannot be restored (must remain CRASH)
    mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    vehicle_state_dao = VehicleStateDAO(current_app.config,mixed_traffic_scenario_dao)

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
    active_drivers = [driver for driver in scenario.drivers if driver.user_id is not None]

    if len(active_drivers) == scenario.max_players:
        # TODO Validity should be checked BEFORE, and Initial States and Goal Areas should be preallocated!
        current_app.logger.info("Scenario {} is ready to start".format(scenario.scenario_id))

        mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)

        # Activate the scenario computing the initial state for all drivers (so timestamp==0 implies status=="ACTIVE")
        mixed_traffic_scenario_dao.activate_scenario(scenario)

        # Validation of the scenario must be done when the scenario is submitted the first time!
        # Triggers an AssertionError if not valid
        # current_app.logger.info("Validating scenario {}".format(scenario.scenario_id))
        # mixed_traffic_scenario_dao.validate(scenario)


def _add_driver_to_scenario(scenario, initial_state, goal_area_position: Tuple[float, float], user: User = None) -> Driver:
    """ Add the driver to the scenario and trigger the AV logic IF scenario becomes ACTIVE"""

    try:
        assert initial_state is not None
        assert goal_area_position is not None

        mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
        # This might fail, but the exception will be captured by the catch-all logic inside the API layer
        # We should rollback everything at this point...

        if user is not None:
            # Assign the user to a driver
            driver = mixed_traffic_scenario_dao.add_user_to_scenario(user, scenario)
        else:
            # Take the next driver and force its initial state and goal ared
            driver = mixed_traffic_scenario_dao.get_waiting_driver(scenario)

        # Update that driver/user initial state
        mixed_traffic_scenario_dao.force_initial_state_for_driver_in_scenario(driver, initial_state)
        # Update the goal region
        # TODO this should fail if the goal region is NOT overlapping the road/reacheable from the initial state...
        mixed_traffic_scenario_dao.force_goal_region_as_rectangle_for_driver_in_scenario(driver, goal_area_position)

        return driver
    except Exception as e:
        # current_app.logger.exception("Error occured while creating new driver {} ".format(type(e).__name__))
        # Make sure that this is not an SQL Integrity Error, otherwise let it raises the 500
        assert "IntegrityError" not in type(e).__name__
        # Propagate the exception
        raise e

# Rename this to JOIN
@jwt_required()
@scenarios_api.route("/<scenario_id>/drivers/<user_id>", methods=["DELETE"])
def delete_driver(scenario_id, user_id):
    """
    This is the LEAVE action, unbind driver and user for the scenario
    :return: 204
    """

    user_dao = UserDAO()
    user = user_dao.get_user_by_user_id(user_id)
    if user is None:
        return "User not found", 404

    # Does the scenario_id correspond to an existing scenario?
    mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = mixed_traffic_scenario_dao.get_scenario_by_scenario_id(scenario_id)
    if scenario is None:
        return "Scenario not found", 404


    # Note: We already set initial state and goal area, we simply link the user with a waiting driver in the scenario
    mixed_traffic_scenario_dao.remove_user_from_scenario(user, scenario)


    # If everything is ok, we return a 204 (accepted but no content)
    return "", 204

@scenarios_api.route("/<scenario_id>/drivers/", methods=["POST"])
@jwt_required()
def create_driver(scenario_id):
    """
    This is the JOIN action. The driver is there, but the user must be associated with it
    Not at this point, the initial_state and goal_area are already there.
    If the scenario becomes active, we need to rewamp all the AV/drivers associated with it!

    :return: 201
    """

    # Make the input data mutable
    data = dict(request.form)

    # Validate the input

    # Is the mandatory field there?
    assert "user_id" in data, "Missing user_id"
    user_id = int(data["user_id"])

    # Does the user_id correspond to an existing user?
    user_dao = UserDAO()
    user = user_dao.get_user_by_user_id(user_id)
    assert user is not None

    # Does the scenario_id correspond to an existing scenario?
    mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = mixed_traffic_scenario_dao.get_scenario_by_scenario_id(scenario_id)
    if scenario is None:
        return "Scenario not found", 404

    # Note: We already set initial state and goal area, we simply link the user with a waiting driver in the scenario
    mixed_traffic_scenario_dao.add_user_to_scenario(user, scenario)

    # Check whether the scenarios needs to be activated
    _check_and_activate_scenario(scenario)

    # Force a restart of all the jobs that
    if "SCHEDULER_API_ENABLED" in current_app.config and current_app.config["SCHEDULER_API_ENABLED"]:
        scheduler.rewamp_jobs(scenario=scenario)

    # If everything is ok, we return a 204 (accepted but no content)
    return "", 204


@scenarios_api.route("/<scenario_id>/drivers/<user_id>/", methods=["GET"])
@jwt_required()
def get_driver(scenario_id, user_id):
    scenario_id = int(scenario_id)
    user_id = int(user_id)

    # Does the scenario_id correspond to an existing scenario?
    mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = mixed_traffic_scenario_dao.get_scenario_by_scenario_id(scenario_id)

    if scenario is None:
        return "Scenario not found", 404
    try:
        driver = [d for d in scenario.drivers if d.user_id == user_id][0]
        return driver_schema.dump(driver)
    except IndexError as ie:
        return "User not driving in the scenario", 404


@scenarios_api.route("<scenario_id>/drivers/<user_id>/states/<timestamp>/", methods=["GET"])
@jwt_required()
def get_vehicle_state_at_timestamp(scenario_id: int, user_id: int, timestamp: int):
    scenario_id = int(scenario_id)
    user_id = int(user_id)
    # Does the scenario_id correspond to an existing scenario?
    mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = mixed_traffic_scenario_dao.get_scenario_by_scenario_id(scenario_id)
    if scenario is None:
        return "Scenario not found", 404
    # Does the scenario_id correspond to an existing scenario?
    user_dao = UserDAO()
    user = user_dao.get_user_by_user_id(user_id)
    if user is None:
        return "User not found", 404
    # Is the user associated to a driver in this scenario?
    try:
        driver = [d for d in scenario.drivers if d.user_id == user_id][0]
        assert driver.scenario_id == scenario_id, "Not a valid scenario"
    except IndexError as e_info:
        raise AssertionError(f"User {user_id} is not a driver in scenario {scenario_id}")
    # Get the state of the driver at given timestamp
    vehicle_state_dao = VehicleStateDAO(current_app.config, mixed_traffic_scenario_dao)
    vehicle_state = vehicle_state_dao.get_vehicle_state_by_scenario_timestamp_driver(scenario, timestamp, driver)
    if vehicle_state is None:
        return "State not found", 404
    else:
        return vehicle_state_schema.dump(vehicle_state)


@scenarios_api.route("/<scenario_id>/drivers/<user_id>/states/", methods=["GET"])
@jwt_required()
def get_vehicle_states(scenario_id: int, user_id: int):
    """
    Return all the states for the driver identified by driver_id in the scenario identified by scenario_id
    """

    scenario_id = int(scenario_id)
    user_id = int(user_id)

    # Validate the input

    # TODO Code duplication, pretty sure this can be solved with nesting of requests

    # Does the scenario_id correspond to an existing scenario?
    mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = mixed_traffic_scenario_dao.get_scenario_by_scenario_id(scenario_id)
    if scenario is None:
        return "Scenario not found", 404

    # # Does the scenario_id correspond to an existing scenario?
    # user_dao = UserDAO()
    # user = user_dao.get_user_by_user_id(user_id)
    # if user is None:
    #     return "User not found", 404

    # This fails if the the user_id and scenario_id are wrong
    try:
        driver = [d for d in scenario.drivers if d.user_id == user_id ][0]
        assert driver.scenario_id == scenario_id, "Not a valid scenario"
    except IndexError as e_info:
        raise AssertionError(f"User {user_id} is not a driver in scenario {scenario_id}")

    vehicle_state_dao = VehicleStateDAO(current_app.config, mixed_traffic_scenario_dao)
    all_states = vehicle_state_dao.get_states_in_scenario_of_driver(scenario_id, driver.driver_id)
    all_states.sort(key=lambda s: s.timestamp)
    return vehicle_states_schema.dump(all_states)


@scenarios_api.route("/<scenario_id>/drivers/<user_id>/states/", methods=["PUT"])
@jwt_required(admin_only=False)
def update_vehicle_states(scenario_id: int, user_id: int):
    """
    Update the scenario states associated with the driver id.
    Return success-no-content (204) if the updates are accepted.

    If the states correspond to existing, but still modifiable states, all the (future) states are
    deleted to ensure no spurious states exist.

    TODO We should use transactions to be safe, but that would require a deep re-design
    """

    scenario_id = int(scenario_id)
    user_id = int(user_id)

    # Does the scenario_id correspond to an existing scenario?
    mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = mixed_traffic_scenario_dao.get_scenario_by_scenario_id(scenario_id)
    if scenario is None:
        return "Scenario not found", 404

    # Is this user also a driver in this scenario?
    driver = None
    try:

        driver = [d for d in scenario.drivers if d.user_id == user_id][0]
    except Exception:
        raise AssertionError(f"User {user_id} is not a driver in scenario {scenario.scenario_id}")

    assert driver.scenario_id == scenario_id, "Wrong scenario"

    # If the status is DONE the request is wrong
    assert scenario.status in [ MixedTrafficScenarioStatusEnum.WAITING, MixedTrafficScenarioStatusEnum.ACTIVE]

    # If the status is WAITING the request must be re-send in the future (too early)
    if scenario.status == MixedTrafficScenarioStatusEnum.WAITING:
        return "Scenario not yet started", 425

    # If the status is ACTIVE the request can go on

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
    planned_states = []
    for vehicle_state_data in zip(cycle([None]), cycle([VehicleStatusEnum.PENDING]), [int(x) for x in data["timestamps"].split(",")], # make sure those are integers
                                    cycle([driver.driver_id]), cycle([driver.user_id]), cycle([driver.scenario_id]),
                                  data["positions_x"].split(","), data["positions_y"].split(","),
                                  data["rotations"].split(","),
                                  data["speeds_ms"].split(","), data["accelerations_m2s"].split(",")):
        planned_states.append(
            VehicleState(
                vehicle_state_id=vehicle_state_data[0],
                status=vehicle_state_data[1],
                timestamp=vehicle_state_data[2],
                driver_id = vehicle_state_data[3],
                user_id=vehicle_state_data[4],
                scenario_id=vehicle_state_data[5],
                position_x=vehicle_state_data[6],
                position_y=vehicle_state_data[7],
                rotation=vehicle_state_data[8],
                speed_ms=vehicle_state_data[9],
                acceleration_m2s=vehicle_state_data[10]
            )
        )

    planned_states.sort(key=lambda s: s.timestamp)

    # If we are not updating any existing state, i.e., all the timestamp are beyond the end of the scenario,
    # the request is not valids
    assert planned_states[0].timestamp <= scenario.duration

    vehicle_state_dao = VehicleStateDAO(current_app.config, mixed_traffic_scenario_dao)

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
            if all(s.status == VehicleStatusEnum.ACTIVE or s.status == VehicleStatusEnum.CRASHED for s in scenario_state):
                if _check_collisions(scenario, driver, scenario_state):
                    # Do not try to update the other states, as they are already updated by the previous call
                    current_app.logger.info("> Do not try to update the other states, as they are already updated by the previous call")
                    break

            current_app.logger.info("Planned State for user {} at timestamp {}"
                                    .format(driver.user_id, planned_state.timestamp))
            #
            # Not necessary anymore, AVS are autonomous now
            # _trigger_avs(scenario, planned_state.timestamp)
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


@scenarios_api.route("/<scenario_id>/drivers/<driver_id>/states/<timestamp>/trajectory", methods=["GET"])
# @jwt_required()
def get_trajectory(scenario_id, driver_id, timestamp):
    """ Return a single trajectory with the given sampling parameters + reference path"""

    assert "d" in request.args, "Missing lateral displacement parameter"
    assert "t" in request.args, "Missing time to reach the state parameter"
    assert "v" in request.args, "Missing speed parameter"
    assert "h" in request.args, "Missing planning horizon parameter"
    assert "s" in request.args, "Missing snap to road parameter"

    # Get the current state of the driver in the scenario at given timestamp
    # TODO This common logic might be refactored - START
    # Does the scenario_id correspond to an existing scenario?
    # here we want to get the value of user (i.e. ?user=some-value)
    t = float(request.args.get('t'))
    d = float(request.args.get('d'))
    v = float(request.args.get('v'))
    h = float(request.args.get('h'))
    snap_to_road = request.args.get("s") != "0"

    # Retrieve the scenario and all the elements needed to compute the trajectory given the sampling parameters
    mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = mixed_traffic_scenario_dao.get_scenario_by_scenario_id(scenario_id)

    if scenario is None:
        return "Scenario not found", 404

    # user_dao = UserDAO()
    # driver = user_dao.get_user_by_user_id(driver_id)
    driver_dao = DriverDAO(current_app.config)
    driver = driver_dao.get_driver_by_driver_id(driver_id)
    if driver is None:
        return "Driver not found", 404

    vehicle_state_dao = VehicleStateDAO(current_app.config, mixed_traffic_scenario_dao)

    scenario_state = vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario_id, timestamp)
    driver_state = next((state for state in scenario_state if state.user_id == driver.user_id), None)
    assert driver_state is not None, f"Cannot find Driver {driver_id} state at timestamp {timestamp}"

    # Check that state is still "workable", i.g., PENDING or WAITING
    # In theory this is not necessary, in nthe worse case we reject any update to it?
    # Probably better reutn a 403 NOT ALLOWED
    # Which status should be ACTIVE? Meaning that from THAT state you can move on
    assert driver_state.status == VehicleStatusEnum.ACTIVE

    mixed_traffic_scenario = scenario
    initial_state = mixed_traffic_scenario_dao.get_initial_state_for_driver_in_scenario(driver, scenario)
    goal_region_as_rectangle = mixed_traffic_scenario_dao.get_goal_region_for_driver_in_scenario(driver, scenario)

    # Extracts the arguments from the URL, i.e., ?created_by=1&status="ACTIVE"
    # args = request.args
    # Retrieve the N samples from the parameter h
    # TODO Might produce weird error for rounding?
    the_N = int(h / 0.1)

    trajectory_sampler = TrajectorySampler(mixed_traffic_scenario, initial_state, goal_region_as_rectangle,
                                           snap_to_road, the_N)

    # TODO: Make sure this gets dumped to JSON properly
    # [state["position_x"], state["position_y"]]
    the_reference_path = trajectory_sampler.get_reference_path()
    # Transform it into a valid json
    reference_path = [{"position_x": rp[0], "position_y": rp[1]} for rp in the_reference_path]
    try:
        # Sampler can result into a feasible trajectory or a non feasible one
        feasible_trajectories, infeasible_trajectories, infeasibility_reasons = trajectory_sampler.sample_trajectories(driver_state,
                                                                       t_sec_min=t, t_sec_max=t,
                                                                       d_meter_min=d, d_meter_max=d,
                                                                       v_meter_per_sec_min=v, v_meter_per_sec_max=v)
        # We want ONLY one trajectory
        assert len(feasible_trajectories) + len(infeasible_trajectories) == 1

        response_json = {}
        # The generated trajectory - We will visualize it not matter what
        response_json["trajectory"] = trajectory_schema.dump(feasible_trajectories[0]) if len(feasible_trajectories) == 1 \
            else trajectory_schema.dump(infeasible_trajectories[0])
        # Something about feasibility
        response_json["is_feasible"] = len(feasible_trajectories) == 1
        # Anything about the error
        response_json["infeasibility_reason"] = ""
        # https://fjp.at/posts/optimal-frenet/
        if len(infeasible_trajectories) == 1:
            # Translate the error message in human-understandable message
            # TODO Might be imprecise!

            # Kappa and KappaDot
            if "Kappa" in infeasibility_reasons[0]:
                response_json["infeasibility_reason"] = "you would turn too fast."
            elif "Acceleration" in infeasibility_reasons[0]:
                response_json["infeasibility_reason"] = "you could not accelerate that fast."
            elif "Velocity" in infeasibility_reasons[0]:
                response_json["infeasibility_reason"] = "moving backwards is not allowed."
            elif "Theta_dot" in infeasibility_reasons[0]:
                response_json["infeasibility_reason"] = "you would rotate too much."
            else:
                response_json["infeasibility_reason"] = "the parameters are wrong."

        # The reference path
        response_json["reference_path"] = reference_path
        # Set the response code
        code = 200 if len(feasible_trajectories) == 1 else 422

    except Exception as ex_info:
        # Produce an exceptional response
        response_json = {}
        # The trajectory is missing at this point
        response_json["trajectory"] = {}
        # Forcefully set the inputs
        response_json["trajectory"]["the_d"] = d
        response_json["trajectory"]["the_t"] = t
        response_json["trajectory"]["the_v"] = v
        #
        response_json["trajectory"]["planned_states"] = []
        #
        response_json["is_feasible"] = False
        response_json["infeasibility_reason"] = f"the provided parameters are wrong."
        # Mostly for debug, this is not visualized
        response_json["error_message"] = f"{ex_info.args}"
        #
        response_json["reference_path"] = reference_path
        # Make sure the code is an error
        code = 422

    # Send back the full JSON Object. We'll manage on the client to filter this out
    return json.dumps(response_json), code

    # # Simplify json we need to keep { sampling paramters + planned data as array of positions
    # simplified_json = {}
    # if response_json:
    #     simplified_json["the_d"] = response_json["the_d"]
    #     simplified_json["the_t"] = response_json["the_t"]
    #     simplified_json["the_v"] = response_json["the_v"]
    #     simplified_json["planned_states"] = [ [s["position_x"], s["position_y"]] for s in response_json["planned_states"]]
    # else:

    #
    # return simplified_json


@scenarios_api.route("/<scenario_id>/states/<timestamp>/", methods=["GET"])
@jwt_required()
def get_scenario_state_at_timestamp(scenario_id: int, timestamp: int):
    scenario_id = int(scenario_id)
    timestamp = int(timestamp)

    mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = mixed_traffic_scenario_dao.get_scenario_by_scenario_id(scenario_id)
    if scenario is None:
        return "Scenario not found", 404

    vehicle_state_dao = VehicleStateDAO(current_app.config, mixed_traffic_scenario_dao)
    all_states = vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario_id, timestamp)
    all_states.sort(key=lambda s: s.timestamp)
    return vehicle_states_schema.dump(all_states)


@scenarios_api.route("<scenario_id>/template/xml/", methods=["GET"])
@jwt_required()
def get_scenario_template_xml(scenario_id: int):
    scenario_id = int(scenario_id)

    mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = mixed_traffic_scenario_dao.get_scenario_by_scenario_id(scenario_id)
    if scenario is None:
        return "Scenario not found", 404

    mixed_traffic_scenario_template_dao = MixedTrafficScenarioTemplateDAO(current_app.config)

    # Get the template used in this scenario even if it has been disabled
    scenario_template = mixed_traffic_scenario_template_dao.get_template_by_id(scenario.template_id, skip_active_check=True)

    # Return the XML
    return scenario_template.xml, 200
