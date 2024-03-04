import logging as logger

# Typing
from typing import List, Optional

import sqlalchemy.exc

from model.collision_checking import CollisionChecker
from model.vehicle_state import VehicleStatusEnum
# Enable this ONLY in unit testing
# logger = logging.getLogger('flexcrash.sub')

# Import the singleton db instance
from persistence.database import db
from background.scheduler import render_in_background

from persistence.utils import inject_where_statement_using_attributes

# DAOs - Do I really need them!? We probably should rely in getting the models as dep
from persistence.user_data_access import UserDAO
# from persistence.mixed_scenario_data_access import MixedTrafficScenarioDAO

from controller.controller import MixedTrafficScenarioGenerator

# from visualization.mixed_traffic_scenario import generate_embeddable_html_snippet
from model.mixed_traffic_scenario import MixedTrafficScenario
from model.vehicle_state import VehicleState
from model.driver import Driver

# INSERT_USER = "INSERT INTO User VALUES(?, ?, ?, ?);"
# INSERT_MIXED_TRAFFIC_SCENARIO = "INSERT INTO Mixed_Traffic_Scenario VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
# INSERT_DRIVER = "INSERT INTO Driver VALUES (?, ?, ?)"
# INSERT_SCENARIO_TEMPLATE = "INSERT INTO Scenario_Template VALUES (?, ?, ?, ?)"
# INSERT_VEHICLE_STATE = "INSERT INTO Vehicle_State VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
# INSERT_TRAINING_SCENARIO_TEMPLATE = "INSERT INTO Training_Scenario_Template VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
#
# UPDATE_MIXED_TRAFFIC_SCENARIO_STATUS = "UPDATE Mixed_Traffic_Scenario SET status = ?"
# UPDATE_VEHICLE_STATE_STATUS = "UPDATE Vehicle_State SET status = ?"
# UPDATE_VEHICLE_STATE = "UPDATE Vehicle_State SET status = ?, position_x = ?,  position_y = ?, rotation = ?, speed_ms = ?, acceleration_m2s = ?"
#
# UPDATE_DRIVER = "UPDATE Driver SET goal_region = ?"
#
# Note: By keeping the order of attributes here, we can use tuple expansion to create Python objects
# SELECT_USER = "SELECT user_id, username, email, password FROM User"
# SELECT_MIXED_TRAFFIC_SCENARIO = "SELECT scenario_id, name, description, created_by, max_players, status, template_id, duration FROM Mixed_Traffic_Scenario"
# SELECT_SCENARIO_TEMPLATE = "SELECT template_id, name, description, xml FROM Scenario_Template"
# SELECT_VEHICLE_STATE = "SELECT vehicle_state_id, status, timestamp, driver_id, scenario_id, position_x, position_y, rotation, speed_ms, acceleration_m2s FROM Vehicle_State"
# SELECT_TRAINING_SCENARIO_TEMPLATE = "SELECT name, description, based_on, duration, goal_region, initial_ego_position_x, initial_ego_position_y, initial_ego_rotation, initial_ego_speed_ms, initial_ego_acceleration_m2s, n_avs FROM Training_Scenario_Template"
#
# COUNT_VEHICLE_STATES = "SELECT Count(*) FROM Vehicle_State"
#
# DELETE_MIXED_TRAFFIC_SCENARIO = "DELETE FROM Mixed_Traffic_Scenario"


class VehicleStateDAO:

    # TODO A lot of circular deps here...
    def __init__(self, app_config, scenario_dao):
        self.app_config = app_config
        # self.database_name = app_config["DATABASE_NAME"]
        self.images_folder = app_config["SCENARIO_IMAGES_FOLDER"]
        #
        self.collision_checker = CollisionChecker(self)
        self.user_dao = UserDAO()
        self.scenario_dao = scenario_dao
        #
        self._goal_region_lenght = app_config["GOAL_REGION_LENGTH"]
        self._goal_region_width = app_config["GOAL_REGION_WIDTH"]
        self._min_distance_to_end = app_config["GOAL_REGION_DIST_TO_END"]
        self._min_init_speed_m_s = app_config["MIN_INIT_SPEED_M_S"]
        self._max_init_speed_m_s = app_config["MAX_INIT_SPEED_M_S"]

    def delete_state_from_scenario_at_timestamp(self, scenario:MixedTrafficScenario, scenario_stopped_at_timestamp:int):
        stmt = db.delete(VehicleState).\
            where(VehicleState.scenario_id == scenario.scenario_id).\
            where(VehicleState.timestamp > scenario_stopped_at_timestamp)

        db.session.execute(stmt)
        db.session.commit()
        # cursor.execute(
        #     """
        #         DELETE
        #         FROM Vehicle_State
        #         WHERE scenario_id = ? and timestamp > ?
        #     """, (scenario.scenario_id, scenario_stopped_at_timestamp)
        # )

    # TODO Probably better to use Objects
    def update_initial_state_for_driver_in_scenario(self, init_state_dict, driver_id: int, scenario_id: int) -> None:
        logger.info('FORCE UPDATING INITIAL STATE for driver {} in scenario {}'.format(driver_id, scenario_id))
        stmt = db.select(VehicleState)
        kwargs = {
            "scenario_id": scenario_id,
            "user_id": driver_id,
            # Force this to be the initial state
            "timestamp": 0,
            # Note: by design this state already exists, we need to force-update it
            "status": "ACTIVE"
        }
        updated_stmt = inject_where_statement_using_attributes(stmt, VehicleState,**kwargs)
        db.session.begin(nested=False)
        # Get the driver, if any
        initial_state: VehicleState
        initial_state = db.session.execute(stmt).scalar_one()
        # Set the fields in the driver
        initial_state.status = "ACTIVE"
        initial_state.position_x, initial_state.position_y = init_state_dict["position_x"], init_state_dict["position_y"]
        initial_state.rotation = init_state_dict["rotation"]
        initial_state.speed_ms = init_state_dict["speed_ms"]
        initial_state.acceleration_m2s = init_state_dict["acceleration_m2s"]
        # Commit the changes
        db.session.commit()

    def insert(self, vehicle_state: VehicleState):
        # """
        # Try to insert the vehicle state in the database. Fails if any DB constraints are missed or the user is not a
        # driver in this scenario. We need an explicit constraints here because we introduced the DriverID Primary Key
        # :param vehicle_state:
        # :return:
        # """
        try:
            # Check whether the data inside the vehicle states are consistent
            assert vehicle_state.driver_id == self.scenario_dao.driver_dao.get_driver_by_user_id(vehicle_state.scenario_id, vehicle_state.user_id)
            db.session.add(vehicle_state)
            db.session.commit()
        except AssertionError as err:
            db.session.rollback()
            raise err
        except sqlalchemy.exc.IntegrityError as err:
            # Is this even possible now?
            db.session.rollback()
            raise err

    def _get_vehicle_state_by_attributes(self, nested=False, **kwargs) -> List[VehicleState]:
        """
        Return a collection of vehicle states matching the given attributes or an empty collection otherwise
        """
        # db.session.begin(nested=nested) -> TODO Somehow the transaction is already running!
        stmt = db.select(VehicleState)
        update_stmt = inject_where_statement_using_attributes(stmt, VehicleState, **kwargs)

        vehicle_states = db.session.execute(update_stmt)
        # db.session.commit()
        return list(vehicle_states.scalars())

    def get_vehicle_state_by_vehicle_state_id(self, vehicle_state_id, nested=False) -> Optional[VehicleState]:
        """
        Return the vehicle state with the given id if it exists. None otherwise
        :param vehicle_state_id:
        :return:
        """
        kwargs = {"vehicle_state_id": vehicle_state_id}
        vehicle_states = self._get_vehicle_state_by_attributes(nested=nested, **kwargs)
        assert len(vehicle_states) == 0 or len(vehicle_states) == 1
        return vehicle_states[0] if len(vehicle_states) == 1 else None

    def get_vehicle_states_by_scenario_id(self, scenario_id) -> List[VehicleState]:
        """
        Return all the states associated to the same scenario
        :param scenario_id:
        :return:
        """
        kwargs = {"scenario_id": scenario_id}
        return self._get_vehicle_state_by_attributes(**kwargs)

    def get_vehicle_states_by_scenario_id_at_timestamp(self, scenario_id, timestamp, nested=False) -> List[VehicleState]:
        """
        Return all the states associated to the given scenario at the given timestamp

        :param scenario_id:
        :param timestamp:
        :return:
        """
        kwargs = {
            "scenario_id": scenario_id,
            "timestamp": timestamp
        }
        return self._get_vehicle_state_by_attributes(nested=nested, **kwargs)

    def get_vehicle_state_by_scenario_timestamp_driver(self, scenario: MixedTrafficScenario, timestamp: int, driver: Driver) -> Optional[VehicleState]:
        """
             Return all the states associated to the given scenario at the given timestamp for the given driver
             """
        kwargs = {
            "scenario_id": scenario.scenario_id,
            "timestamp": timestamp,
            "driver_id": driver.driver_id
        }
        # TODO Here we should check that only one state is indeed returned from the DB
        query_result = self._get_vehicle_state_by_attributes(**kwargs)
        return query_result[0] if len(query_result) == 1 else None

    # TODO: REFACTOR: Make those parameters scenario and driver instead of their ID
    def get_states_in_scenario_of_driver(self, scenario_id: int , driver_id: int) -> List[VehicleState]:
        """
        Return all the vehicles states for the given driver in the given scenario
        :param driver_id:
        :param scenario_id:
        :return:
        """
        kwargs = {
            "driver_id": driver_id,
            "scenario_id": scenario_id
        }
        return self._get_vehicle_state_by_attributes(**kwargs)

    def propagate_state_for_driver_in_scenario(self, scenario: MixedTrafficScenario,
                                               driver: Driver,
                                               state_to_propagate: VehicleState, nested=False) -> None:
        """
        Propagate the given state for this driver until scenario.duration
        """
        logger.info("===> Propagating state {} for driver {} from timestamp {} to timestamp {} in scenario {}".format(
            state_to_propagate.status, driver.user_id, state_to_propagate.timestamp, scenario.duration,
            scenario.scenario_id)
        )
        # We need to exclude the current state, since its already set, and we need to include the duration + 1 since
        # timestamps are 1-indexed
        timestamps_to_update = list(range(state_to_propagate.timestamp, scenario.duration + 1))
        update_vals = {
            VehicleState.status.name: state_to_propagate.status,
            VehicleState.position_x.name: state_to_propagate.position_x,
            VehicleState.position_y.name: state_to_propagate.position_y,
            VehicleState.rotation.name: state_to_propagate.rotation,
            VehicleState.speed_ms.name: state_to_propagate.speed_ms,
            VehicleState.acceleration_m2s.name: state_to_propagate.acceleration_m2s
        }
        stmt = db.update(VehicleState).values(**update_vals)
        # stmt = db.session.get(VehicleState)
        # Enable Foreing Keys Support
        kwargs = {
            "scenario_id": scenario.scenario_id,
            "user_id": driver.user_id,
            # Update the state with the given timestamp (unique for each driver/scenario)
            "timestamp": "|".join([str(t) for t in timestamps_to_update])
        }
        update_stmt = inject_where_statement_using_attributes(stmt, VehicleState, **kwargs)
        db.session.begin(nested=nested)
        db.session.execute(update_stmt)
        # for vehicle_state in db.session.execute(update_stmt):
        #     vehicle_state.status = state_to_propagate.status
        #     vehicle_state.position_x = state_to_propagate.position_x
        #     vehicle_state.position_y = state_to_propagate.position_y
        #     vehicle_state.rotation = state_to_propagate.rotation
        #     vehicle_state.speed_ms = state_to_propagate.speed_ms
        #     vehicle_state.acceleration_m2s = state_to_propagate.acceleration_m2s
        #
        db.session.commit()

    def update_driver_state_in_scenario(self, scenario: MixedTrafficScenario, driver: Driver, state: VehicleState):
        """
        Try to update the states of the given user in the given scenario. Ensures that if for THIS state
         all drivers have submitted their actions, THIS state becomes ACTIVE. In this case, we can trigger
         the AV. NOTE: The assumption is that the (internal) AV computes states faster than regular users,
         this might change in the future. In case the state is ALREADY crashed, do not do anything

         TODO state.timestamp might be wrong?!
         # TODO CHECK IF STATE (CRASHED, GOAL_REACHED) IS ALREADY SET, and SKIP!

        :param scenario:
        :param driver:
        :param state:
        """

        logger.info('Updating state at timestamp {} for driver {} in scenario {}'.format(state.timestamp,
                                                                                         driver.user_id,
                                                                                         scenario.scenario_id))
        # TODO Fix the transactions
        # db.session.begin(nested=False)

        update_vals = {
            # TODO Before this was WAITING
            VehicleState.status.name: VehicleStatusEnum.WAITING,
            VehicleState.position_x.name: state.position_x,
            VehicleState.position_y.name: state.position_y,
            VehicleState.rotation.name: state.rotation,
            VehicleState.speed_ms.name: state.speed_ms,
            VehicleState.acceleration_m2s.name: state.acceleration_m2s
        }
        stmt = db.update(VehicleState).values(**update_vals)
        kwargs = {
            "scenario_id": scenario.scenario_id,
            "user_id": driver.user_id,
            # Update the state with the given timestamp (unique for each driver/scenario)
            "timestamp": state.timestamp,
            # We can only update states that are PENDING or WAITING. We cannot update ACTIVE or CRASH states
            # Can we deal with this using enums?
            # "status": "PENDING|WAITING"
            "status": f"{VehicleStatusEnum.PENDING}|{VehicleStatusEnum.WAITING}"
        }
        update_stmt = inject_where_statement_using_attributes(stmt, VehicleState, **kwargs)
        result = db.session.execute(update_stmt)
        # TODO Count how many were updated

        if result.rowcount == 0:
            # Make sure the state was indeed actionable
            the_state = self._get_vehicle_state_by_attributes(
                nested=True,
                **{
                    "scenario_id": scenario.scenario_id,
                    "user_id": driver.user_id,
                    "timestamp": state.timestamp
                }
            )[0]

            # TODO CRASH or CRASHED?
            if the_state.status == "GOAL_REACHED" or the_state.status == "CRASHED":
                logger.info(
                    'State at timestamp {} for driver {} in scenario {} is already {}'.format(
                        state.timestamp, driver.user_id, scenario.scenario_id, the_state.status))
            else:
                db.session.rollback()
                logger.error(
                    'Cannot update state at timestamp {} for driver {} in '
                    'scenario {}.'.format(state.timestamp, driver.user_id,
                                          scenario.scenario_id))  # , the_state.status))
                raise AssertionError("Cannot update vehicle state {}".format(state.vehicle_state_id))

        # This makes WAITING states into ACTIVE states at the same timestamp
        self._synchronize_scenario_states(scenario, state.timestamp, nested=True)

        # This makes ACTIVE states into CRASHED at this time stamp - it stores into the DB at timestamp
        # Does not return an UPDATED version of the states
        state_of_vehicles_that_collided = self._vehicles_that_collided(scenario, state.timestamp, nested=True)

        # This makes ACTIVE states into GOAL_REACHED at this time stamp - it stores into the DB at timestamp
        state_of_vehicles_that_reached_goal = self._vehicles_that_reached_goal(scenario, state.timestamp, nested=True)

        # Plot all the graphics (MIGHT TAKE SOME TIME if many players!)
        # This also queries the DB to get the latest state
        self._render_scenario_state(scenario, state.timestamp)

        # At this point we need to "propagate" the state of GOAL_REACHED and CRASH states if any!
        # At timestamp t is stored already in the DB
        timestamp = state.timestamp + 1

        if timestamp <= scenario.duration:
            for state_of_vehicle in state_of_vehicles_that_collided:
                # Select the Driver who is in the Propagable state
                driver_to_update = self.user_dao.get_user_by_user_id(state_of_vehicle.user_id, nested=True)
                # Propagate its states
                self.propagate_state_for_driver_in_scenario(scenario, driver_to_update, state_of_vehicle, nested=True)

            for state_of_vehicle in state_of_vehicles_that_reached_goal:
                # Select the Driver who is in the Propagable state
                driver_to_update = self.user_dao.get_user_by_user_id(state_of_vehicle.user_id, nested=True)
                # Propagate its states
                self.propagate_state_for_driver_in_scenario(scenario, driver_to_update, state_of_vehicle, nested=True)

        db.session.commit()
        # At this point we should return whether the called shall skip the planned steps!
        return driver.user_id in [s.user_id for s in
                                  state_of_vehicles_that_reached_goal + state_of_vehicles_that_collided]

    def driver_crashed_at_timestamp_in_scenario(self, scenario, driver, vehicle_state_at_timestamp):
        """
        Set the status of all the vehicle states after timestamp (inclusive of timestamp)
        that belong to the driver in the scenario as CRASHED and copy over all the attributes (beside timestamp!)

        :param scenario:
        :param driver:
        :param timestamp:
        :return:
        """
        timestamp = vehicle_state_at_timestamp.timestamp

        logger.info('Driver {} Crashed at timestamp {} in scenario {}'.format(driver.user_id, timestamp,
                                                                              scenario.scenario_id))
        timestamps = "|".join(
            str(t) for t in range(timestamp, scenario.duration + 1))  # Include the last timestamp at duration

        stmt = db.update(VehicleState).values(**{
            VehicleState.status.name: "CRASHED"
        })
        kwargs = {
            "scenario_id": scenario.scenario_id,
            "user_id": driver.user_id,
            # Update the state any of the given timestamps (unique for each driver/scenario)
            "timestamp": timestamps
        }
        updated_stmt = inject_where_statement_using_attributes(stmt, VehicleState, **kwargs)
        result = db.session.execute(updated_stmt).rowcount
        if result == 0:
            logger.error(
                'Cannot set Crash state at timestamp {} for driver {} in scenario {}'.format(timestamp,
                                                                                             driver.user_id,
                                                                                             scenario.scenario_id))
            db.session.rollback()
            raise AssertionError("Cannot update driver state {}".format(driver.user_id))

        db.session.commit()

    def _render_scenario_state(self, scenario, timestamp, nested=False):
        # Check if we need to render this timestamp
        # db.session.begin(nested=nested)
        # Get the stored states which include ACTIVE, GOAL_REACHED, and CRASHED
        vehicles_states_at_timestamp = self.get_vehicle_states_by_scenario_id_at_timestamp(scenario.scenario_id,
                                                                                           timestamp, nested)
        # Check that all the states are NOT actionable
        if all(s.status == "ACTIVE" or s.status == "GOAL_REACHED" or s.status == "CRASHED" for s in
               vehicles_states_at_timestamp):
            # We can render the scenario at this timestamp (for all the drivers)
            logger.debug(
                "Rendering scenario state at timestamp {} for scenario {}".format(timestamp, scenario.scenario_id))
            # Generate a global view, including all the drivers
            render_in_background(self.images_folder, scenario, vehicles_states_at_timestamp)

            # Focus on each driver and render the state again
            for driver in scenario.drivers:
                # TODO I do not like this nesting of DAOs but cannot do anything about it now
                goal_region_as_rectangle = self.scenario_dao.get_goal_region_for_driver_in_scenario(driver, scenario, nested)

                logger.debug("Rendering states at timestamp {} in scenario {} for driver {}".format(timestamp,
                                                                                                    scenario.scenario_id,
                                                                                                    driver.user_id))
                render_in_background(self.images_folder, scenario, vehicles_states_at_timestamp,
                                                 focus_on_driver=driver,
                                                 goal_region_as_rectangle=goal_region_as_rectangle)

        db.session.commit()

    def _vehicles_that_collided(self, scenario, timestamp, nested=False) -> List[VehicleState]:
        """
        Collision checking is possible only if ALL the vehicles submitted the trajectory

        :param scenario:
        :param timestamp:
        :return:
        """

        db.session.begin(nested=nested)

        state_of_vehicles_that_collided = list()


        vehicles_states_at_timestamp = self.get_vehicle_states_by_scenario_id_at_timestamp(scenario.scenario_id,
                                                                                           timestamp, nested=nested)
        for driver_state in vehicles_states_at_timestamp:
            # If the state is PENDING, there's no data to use for checking whether the goal is reached.
            if driver_state.status == "PENDING":
                logger.info(
                    "Driver {} has NOT YET SENT ITS PLANNED STATES at timestamp {}. "
                    "We skip collision checking ".format(driver_state.user_id, timestamp))
                db.session.commit()
                return state_of_vehicles_that_collided

        # At this point we can effectively check the collisions of ALL the vehicles, are return the one that collided
        # Those are not MODEL Objects because we call scalar?
        crashed_drivers_with_states = self.collision_checker.check_for_collisions(scenario, timestamp, nested=nested)

        for driver, driver_state in crashed_drivers_with_states:
            logger.info("Driver {} has crashed at timestamp {} ".format(driver.user_id, timestamp))

            # Get the actual state here
            stmt = db.select(VehicleState)
            kwargs = {
                "user_id": driver.user_id,
                "scenario_id": scenario.scenario_id,
                "timestamp": timestamp,
            }
            updated_stmt = inject_where_statement_using_attributes(stmt, VehicleState, **kwargs)

            # Update the model object
            # Note First() return a tuple
            vehicle_state = db.session.execute(updated_stmt).first()[0]
            #
            vehicle_state.status = "CRASHED"

            state_of_vehicles_that_collided.append(vehicle_state)

            # stmt = db.session.get(VehicleState)
            # result = 0
            # for vehicle_state in db.session.execute(updated_stmt):
            #     vehicle_state.status = "CRASHED"
            #     result = result + 1
            # db.session.commit()


            # result = db.session.execute(updated_stmt).rowcount
            # if result != 1:
            #     err_msg = 'Cannot set the state of driver as CRASHED at timestamp {} in scenario {}'.format(timestamp, scenario.scenario_id)
            #     logger.error(err_msg)
            #     db.session.rollback()
            #     raise AssertionError(err_msg)

        # Refresh the states from the DB
        # refreshed_states = []
        # for vehicle_state in state_of_vehicles_that_collided:
        #     refreshed_states.append(self.get_vehicle_state_by_vehicle_state_id(vehicle_state.vehicle_state_id, nested=nested))

        db.session.commit()

        # return refreshed_states
        return state_of_vehicles_that_collided

    def _vehicles_that_reached_goal(self, scenario, timestamp, nested=False) -> List[VehicleState]:
        # TODO: Why not simply checking that the goal region and the rectangle of the car (or its center) collided?!

        # Update the database and mark as GOAL_REACHED the vehicle states that reached the goal in this step
        state_of_vehicles_that_reached_goal = list()

        db.session.begin(nested=nested)

        vehicles_states_at_timestamp = self.get_vehicle_states_by_scenario_id_at_timestamp(scenario.scenario_id,
                                                                                           timestamp, nested=nested)
        # Skip the check if there are not enough data
        if any([driver_state.status == "PENDING" for driver_state in vehicles_states_at_timestamp]):
            logger.info("Pending states at timestamp {}. Skip goal checking ".format(timestamp))
            db.session.commit()
            return state_of_vehicles_that_reached_goal

        initial_states = {}
        goal_region_as_rectangles = {}

        for driver in scenario.drivers:
            initial_states[driver.driver_id] = self.scenario_dao.get_initial_state_for_driver_in_scenario(driver, scenario, nested=nested)
            goal_region_as_rectangles[driver.driver_id] = self.scenario_dao.get_goal_region_for_driver_in_scenario(driver,
                                                                                                            scenario, nested=nested)

        commonroad_scenario, planning_problems_as_dictionary = scenario.as_commonroad_scenario_and_planning_problems(
            initial_states=initial_states, goal_region_as_rectangles=goal_region_as_rectangles)

        for driver_state in vehicles_states_at_timestamp:

            if driver_state.status == "CRASHED" or driver_state.status == "GOAL_REACHED":
                # Do not check drivers that cannot move or already reached the goal
                continue
            # TODO: Can this be WAITING?
            assert driver_state.status != "PENDING"

            # TODO: Note that this mechanism for checking whether a goal is reached is NOT the same as the validation
            # The validation code is stricter as it does not allow ANY overlap between vehicles and goal areas, while
            # here, the goal is computed based on states and other conditions (speed, time, etc.)
            #
            if planning_problems_as_dictionary[driver_state.driver_id].goal.is_reached(
                    driver_state.as_commonroad_state()):
                logger.info(
                    ">> Driver {} driving for user {} has reached its goal state at timestamp {} ".format(driver_state.driver_id, driver.user_id, timestamp))

                stmt = db.select(VehicleState)
                # stmt = db.session.get(VehicleState)
                kwargs = {
                    "user_id": driver_state.user_id,
                    "scenario_id": scenario.scenario_id,
                    "timestamp": timestamp,
                }
                updated_stmt = inject_where_statement_using_attributes(stmt, VehicleState, **kwargs)

                vehicle_state = db.session.execute(updated_stmt).first()[0]
                vehicle_state.status = "GOAL_REACHED"

                state_of_vehicles_that_reached_goal.append(driver_state)

                # result = 0
                # for vehicle_state in db.session.execute(updated_stmt):
                #     vehicle_state.status = "GOAL_REACHED"
                #     result = result + 1
                # db.session.commit()

                # result = db.session.execute(updated_stmt).rowcount
                # if result != 1:
                #     err_msg = 'Cannot set the state of driver as GOAL_REACHED at timestamp {} in scenario {}'.format(
                #             timestamp, scenario.scenario_id)
                #     logger.error(err_msg)
                #     db.session.rollback()
                #     raise AssertionError(err_msg)
            else:
                logger.info(
                    "Driver {} has NOT reached its goal state at timestamp {} ".format(driver_state.user_id,
                                                                                       timestamp))

        # # Refresh the states from the DB
        # refreshed_states = []
        # for vehicle_state in state_of_vehicles_that_reached_goal:
        #     refreshed_states.append(self.get_vehicle_state_by_vehicle_state_id(vehicle_state.vehicle_state_id, nested=nested))

        db.session.commit()
        return state_of_vehicles_that_reached_goal

    def _synchronize_scenario_states(self, scenario, timestamp, nested=False):
        #
        # At this point, we need to check whether all the drivers have provided an action for this timestamp
        # and update all the states at once, making all the WAITING states ACTIVE
        #
        db.session.begin(nested=nested)

        # "SELECT Count(*) FROM Vehicle_State"
        stmt = db.select(VehicleState)
        kwargs = {
            "scenario_id": scenario.scenario_id,
            "timestamp": timestamp,
            "status": "WAITING"
        }
        updated_stmt = inject_where_statement_using_attributes(stmt, VehicleState, **kwargs)
        # number = session.query(func.count(table.id).label('number').first().number
        # TODO Very Inefficient but do not know how to do it otherwise
        #
        waiting_result = len(list(db.session.execute(updated_stmt).scalars()))
        stmt = db.select(VehicleState)
        kwargs = {
            "scenario_id": scenario.scenario_id,
            "timestamp": timestamp,
            "status": "GOAL_REACHED|CRASHED"
        }
        updated_stmt = inject_where_statement_using_attributes(stmt, VehicleState, **kwargs)
        goal_reached_and_crashed_result = len(list(db.session.execute(updated_stmt).scalars()))

        # If all have sent their action, update all the scenario states at timestamp to be ACTIVE or CRASHED or GOAL_REACHED, but not WAITING
        if waiting_result + goal_reached_and_crashed_result == len(scenario.drivers):
            # Select all the states of the scenario at the given timestamp
            stmt = db.update(VehicleState).values(**{
                VehicleState.status.name: "ACTIVE"
            })
            kwargs = {
                "scenario_id": scenario.scenario_id,
                "timestamp": timestamp,
                # We can update to ACTIVE only the one in WAITING state, the other must remain GOAL_REACHED and CRASHED
                "status": "WAITING"
            }

            # # We need first to get the objects from the DB
            # stmt = db.select(VehicleState)
            updated_stmt = inject_where_statement_using_attributes(stmt, VehicleState, **kwargs)
            # # Then we need to update them... one by one
            # result = 0
            # for vehicle_state in db.session.execute(updated_stmt):
            #     vehicle_state.status = "ACTIVE"
            #     result = result + 1
            #
            # # Finally try to commit everyting
            # db.session.commit()

            result = db.session.execute(updated_stmt).rowcount

            if result != waiting_result:
                logger.error(
                    'Got {} updates instead of {}'.format(result, waiting_result))
                logger.error(
                    'Cannot activate states at timestamp {} in scenario {} for WAITING states'.format(timestamp,
                                                                                                     scenario.scenario_id))
                db.session.rollback()
                raise AssertionError(
                    'Cannot activate states at timestamp {} in scenario {}'.format(timestamp, scenario.scenario_id))
            else:
                logger.info("******* Activating states at timestamp {} in scenario {} ******* ".format(timestamp,
                                                                                                       scenario.scenario_id))
        else:
            logger.info(
                "******* Cannot activating states at timestamp {} in scenario {} MISSING {} ******* ".format(
                    timestamp,
                    scenario.scenario_id,
                    (len(scenario.drivers) - waiting_result - goal_reached_and_crashed_result))
            )

        db.session.commit()

    def reset_state_for_driver_in_scenario_at_timestamp(self, driver: Driver, scenario: MixedTrafficScenario, timestamp: int):

        update_vals = {
            VehicleState.status.name: "PENDING",
            VehicleState.position_x.name: None,
            VehicleState.position_y.name: None,
            VehicleState.rotation.name: None,
            VehicleState.speed_ms.name: None,
            VehicleState.acceleration_m2s.name: None
        }
        stmt = db.update(VehicleState).values(**update_vals)
        # stmt = db.session.get(VehicleState)
        kwargs = {
            "scenario_id": scenario.scenario_id,
            "driver_id": driver.driver_id,
            # Update the state with the given timestamp (unique for each driver/scenario)
            "timestamp": timestamp,
            # We can only update states that are PENDING or WAITING. We cannot update ACTIVE or CRASH states
            "status": "PENDING|WAITING"
        }
        updated_stmt = inject_where_statement_using_attributes(stmt, VehicleState, **kwargs)
        # TODO: This can be done in bulk
        logger.debug('Resetting state at timestamp {} for driver {} in scenario {}'.format(timestamp,
                                                                                           driver.user_id,
                                                                                           scenario.scenario_id))
        # result = 0
        # for vehicle_state in db.session.execute(updated_stmt):
        #     vehicle_state.status = "PENDING"
        #     vehicle_state.position_x = None
        #     vehicle_state.position_y = None
        #     vehicle_state.rotation = None
        #     vehicle_state.speed_ms = None
        #     vehicle_state.acceleration_m2s = None
        #     result = result + 1
        # db.session.commit()

        result = db.session.execute(updated_stmt).rowcount
        if result == 0:
            # Make sure the state was indeed actionable
            the_state = self._get_vehicle_state_by_attributes(nested=True, **{
                "scenario_id": scenario.scenario_id,
                "driver_id": driver.driver_id,
                "timestamp": timestamp
            })[0]

            if the_state.status == "GOAL_REACHED" or the_state.status == "CRASHED":
                logger.debug(
                    'State at timestamp {} for driver {} in scenario {} is already {}'.format(
                        timestamp, driver.user_id, scenario.scenario_id, the_state.status))
            else:
                error_msg = 'Cannot RESET state at timestamp {} for driver {} in ' \
                            'scenario {}.'.format(timestamp, driver.user_id, scenario.scenario_id)
                logger.warning(error_msg)
                db.session.rollback()
                raise AssertionError(error_msg)

    def get_max_timestamp_in_scenario(self, scenario: MixedTrafficScenario) -> Optional[int]:

        from sqlalchemy.sql.expression import func
        stmt = db.select(func.max(VehicleState.timestamp))
        kwargs = {
            "scenario_id" : scenario.scenario_id
        }
        updated_stmt = inject_where_statement_using_attributes(stmt, VehicleState, **kwargs)
        max_timestamp = db.session.execute(updated_stmt).scalar()
        return max_timestamp

    def initialize_scenario_states(self, scenario: MixedTrafficScenario, nested=False) -> None:
        """ At this point, all the info about drivers, initial state position and speed, and goal area position are available.
        We need to transform those into actual State and Rectangles """
        # Preallocate the vehicle states
        db.session.begin(nested=nested)

        # # Generate Drivers INITIAL states and RECTANGLES
        # # TODO Why we do redefine the GOAL AREA for those drivers?! We do not, we create the initial states
        # # Define the initial state for all the drivers! TODO Use a Vehicle DAO for this?
        mixed_traffic_scenario_generator = MixedTrafficScenarioGenerator(scenario,
                                                                         self._goal_region_lenght,
                                                                         self._goal_region_width,
                                                                         self._min_distance_to_end,
                                                                         self._min_init_speed_m_s,
                                                                         self._max_init_speed_m_s,
                                                                         # TODO Bad design
                                                                         self.scenario_dao)
        # Read them from the Driver Table!
        all_initial_states = mixed_traffic_scenario_generator.create_initial_states()

        # Does this work? At this point there might not even be a vehicle state!
        # self.vehicle_state_dao.update_initial_state_for_driver_in_scenario(init_state_dict, user_id, scenario_id)

        for driver_id in all_initial_states.keys():
            state_id, status, timestamp, user_id, scenario_id, position_x, position_y, rotation, speed_ms, acceleration_m2s = all_initial_states[driver_id]
            vehicle_state = VehicleState(status=status, timestamp=timestamp, user_id=user_id,
                                         driver_id=driver_id,
                                         scenario_id=scenario_id,
                                         position_x=position_x, position_y=position_y,
                                         rotation=rotation, speed_ms=speed_ms, acceleration_m2s=acceleration_m2s)
            db.session.add(vehicle_state)

        # Initialize all the other states. We need bulk update here!

        position_x = None
        position_y = None
        rotation = None
        speed_ms = None
        acceleration_m2s = None
        status = "PENDING"
        # Preallocate the vehicle states
        for driver in scenario.drivers:
            # Note: we start from timestamp 1 not 0, 0 is the initial state and will be filled later
            for timestamp in range(1, scenario.duration + 1):
                vehicle_state = VehicleState(status=status, timestamp=timestamp, driver_id = driver.driver_id,
                                             user_id=driver.user_id,
                                             scenario_id=scenario.scenario_id,
                                             position_x=position_x, position_y=position_y,
                                             rotation=rotation, speed_ms=speed_ms, acceleration_m2s=acceleration_m2s)
                db.session.add(vehicle_state)

        db.session.commit()