import logging as logger
import glob
import os
import traceback

# Typing
from typing import List, Optional, Tuple

import sqlalchemy.exc
from sqlalchemy import or_

from model.user import User
from model.mixed_traffic_scenario import MixedTrafficScenario, MixedTrafficScenarioStatusEnum
from model.collision_checking import CollisionChecker
from model.driver import Driver
from model.vehicle_state import VehicleStatusEnum, VehicleState
#
# from commonroad.geometry.shape import Rectangle
# # Enable this ONLY in unit testing
# # logger = logging.getLogger('flexcrash.sub')

# Import the singleton db instance
from persistence.database import db
from background.scheduler import render_in_background

from persistence.utils import inject_where_statement_using_attributes
# DAOs
from persistence.user_data_access import UserDAO
from persistence.driver_data_access import DriverDAO
from persistence.vehicle_state_data_access import VehicleStateDAO

# from visualization.mixed_traffic_scenario import generate_embeddable_html_snippet, generate_picture

from commonroad_route_planner.route_planner import RoutePlanner
from controller.controller import MixedTrafficScenarioGenerator


class MixedTrafficScenarioDAO:

    def __init__(self, app_config):
        """
        Initialize the DAO with the given app_config dictionary. Probably a better approach would be to inject directly a configured scenario generator
        """
        self.app_config = app_config
        # Override of configuration. Maybe it is better to redesign it?
        # self.database_name = self.app_config["DATABASE_NAME"]
        self.images_folder = self.app_config["SCENARIO_IMAGES_FOLDER"]
        #
        self._goal_region_lenght = self.app_config["GOAL_REGION_LENGTH"]
        self._goal_region_width = self.app_config["GOAL_REGION_WIDTH"]
        self._min_distance_to_end = self.app_config["GOAL_REGION_DIST_TO_END"]
        self._min_init_speed_m_s = self.app_config["MIN_INIT_SPEED_M_S"]
        self._max_init_speed_m_s = self.app_config["MAX_INIT_SPEED_M_S"]

        # Break circular dep... why we have that?
        self.vehicle_state_dao = VehicleStateDAO(app_config, self)
        self.user_dao = UserDAO()
        self.driver_dao = DriverDAO(app_config)

    def validate(self, scenario: MixedTrafficScenario):
        """
        Check that scenario is valid, trigger AssertionErrors otherwise

        :param scenario:
        :return:
        """
        # Check no collisions
        initial_timestamp = 0
        cc = CollisionChecker(self.vehicle_state_dao)

        # Read them from the Driver Table!
        initial_states = {}
        goal_region_as_rectangles = {}

        mixed_traffic_scenario_generator = MixedTrafficScenarioGenerator(scenario,
                                                                         self._goal_region_lenght,
                                                                         self._goal_region_width,
                                                                         self._min_distance_to_end,
                                                                         self._min_init_speed_m_s,
                                                                         self._max_init_speed_m_s,
                                                                         # TODO Bad design
                                                                         self)
        for driver in scenario.drivers:
            rotation, snapped_initial_state = mixed_traffic_scenario_generator._get_road_rotation_at_target_position(
                driver.initial_position)
            # At this point, there might not yet been users assigned to the driver!
            initial_states[driver.driver_id] = VehicleState(
                vehicle_state_id=None,
                status=VehicleStatusEnum.PENDING,
                timestamp=0,
                driver_id=driver.driver_id,
                user_id=None,
                scenario_id=scenario.scenario_id,
                position_x=snapped_initial_state.x,
                position_y=snapped_initial_state.y,
                # TODO We need this one !
                rotation=rotation,
                #
                speed_ms=driver.initial_speed,
                acceleration_m2s=None)
            # TODO Is this a goal region as "Rectangle" ?!
            goal_region_as_rectangles[driver.driver_id] = driver.goal_region

        crashed_vehicles = cc.check_initial_states_for_collisions(initial_states)
        # Assert no crashes, report list of crashed vehicles otherwise
        assert len(crashed_vehicles) == 0, \
            "Scenario is not valid: " \
            "The following drivers have already collided: {}".format(",".join([str(cv[0]) for cv in crashed_vehicles]))

        commonroad_scenario, planning_problems = scenario.as_commonroad_scenario_and_planning_problems(
            initial_states=initial_states,
            goal_region_as_rectangles=goal_region_as_rectangles)

        for driver_id, planning_problem in planning_problems.items():
            ## If this does not work, try setting the route_planner.planning_problem.goal.lanelets_of_goal_positions:
            route_planner = RoutePlanner(commonroad_scenario, planning_problem, reach_goal_state=False)
            # RouteCandidateHolder
            # TODO collect the issues for ALL the drivers that have problems!
            try:
                route_planner.plan_routes().retrieve_first_route().reference_path
            except Exception as exec_info:
                # TODO: We need to inject at some point the index
                raise AssertionError("Scenario is not valid: "
                                     "Driver{} cannot find route {}".format(driver_id)
                    # [d.driver_id for d in scenario.drivers].index(driver_id))
                )

        driver_id_that_reached_the_goal = cc.check_goal_reached(
            vehicles_state_at_timestamp=initial_states,
            goal_region_as_rectangles=goal_region_as_rectangles)

        # Assert no vehicles are already in the goal area
        assert len(driver_id_that_reached_the_goal) == 0, \
            "Scenario is not valid: the following driver(s) have already reached their goal area: {}".format(
                ",".join([str(idx) for idx in driver_id_that_reached_the_goal])
            )

    # TODO Move this to visualization
    def render(self, scenario, nested=False):
        # We need to render the first state of the scenario as well
        # Rendering seems to generate something but the placement of the CAR as Dynamic Obstacle is COMPLETELY WRONG
        initial_state_timestamp = 0
        logger.debug("Rendering scenario state at timestamp {} for scenario {}".format(initial_state_timestamp,
                                                                                       scenario.scenario_id))
        # Get the states at that timestamp - We can avoid this query probably accessing all_initial_states
        # We need a Vehicle DAO here... probebly also to run the above query

        # TODO Load the entire object with all the joined deps at once!
        scenario_states = self.vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario.scenario_id,
                                                                                           initial_state_timestamp,
                                                                                                nested=nested)
        render_in_background(self.images_folder, scenario, scenario_states)

        # Focus on each driver and render the state again
        for driver in scenario.drivers:
            logger.debug("Rendering states at timestamp {} in scenario {} for driver {}".format(initial_state_timestamp,
                                                                                                scenario.scenario_id,
                                                                                                driver.user_id))
            # TODO Is this necessary?!
            goal_region_as_rectangle = self.get_goal_region_for_driver_in_scenario(driver, scenario, nested=nested)

            render_in_background(self.images_folder, scenario, scenario_states, focus_on_driver=driver, goal_region_as_rectangle=goal_region_as_rectangle)

    def get_waiting_driver(self, scenario):
        return self.driver_dao.get_waiting_driver(scenario)

    # TODO Move to DriverDAO
    def force_initial_state_for_driver_in_scenario(self, driver, initial_state):
        self.driver_dao.force_initial_state_for_driver_in_scenario(driver, initial_state)

    # TODO Move to DriverDAO or include the ScenarioReference so the goal region can be computed
    # Why this requires to store the goal region using the generator? Because it must compute the rectangle using the road orientation
    def force_goal_region_as_rectangle_for_driver_in_scenario(self, driver, goal_region_position: Tuple[float, float]):
        generator = MixedTrafficScenarioGenerator(
            driver.scenario, self._goal_region_lenght, self._goal_region_width, self._min_distance_to_end, self._min_init_speed_m_s,
            self._max_init_speed_m_s, self)

        goal_region_as_rectangle = generator.generate_goal_region(goal_region_position)

        self.driver_dao.force_goal_region_as_rectangle_for_driver_in_scenario(driver, goal_region_as_rectangle)

    def _get_scenarios_by_attributes(self, **kwargs) -> List[MixedTrafficScenario]:
        """
        Return a collection of scenarios matching the given attributes or an empty collection otherwise
        :return:
        """

        # Create the basic SELECT for User
        stmt = db.select(MixedTrafficScenario)

        # Add the necessary WHERE clauses
        updated_stmt = inject_where_statement_using_attributes(stmt, MixedTrafficScenario, **kwargs)

        # Execute the statement
        # TODO Check that those are indeed evaluated using drivers and such!
        scenarios = db.session.execute(updated_stmt)
        db.session.commit()
        # Concretize the list as we expect that later
        return list(scenarios.scalars())

    def get_scenario_by_scenario_id(self, scenario_id: int) -> Optional[MixedTrafficScenario]:
        kwargs = {"scenario_id": scenario_id}
        scenarios = self._get_scenarios_by_attributes(**kwargs)
        assert len(scenarios) == 0 or len(scenarios) == 1
        return scenarios[0] if len(scenarios) == 1 else None

    # TODO Created by might be replaced by an owner object?
    def get_all_scenarios(self, created_by: int = None, status: str = None, template_id: int = None) -> List[MixedTrafficScenario]:
        """
        Return the list of all the existing scenarios matching the given attributes
        :return:
        """
        kwargs = {}
        if created_by is not None:
            kwargs["created_by"] = created_by
        if status is not None:
            kwargs["status"] = status
        if template_id is not None:
            kwargs["template_id"] = template_id

        return self._get_scenarios_by_attributes(**kwargs)

    # TODO Pass an object instead of an int?
    def get_all_scenarios_created_by_user(self, user_id: int) -> List[MixedTrafficScenario]:
        """
        Return the list of the scenarios created by the given user. It can be an empty list.
        :param user_id:
        :return:
        """
        kwargs = {"created_by": user_id}
        return self._get_scenarios_by_attributes(**kwargs)

    def get_waiting_scenarios(self) -> List[MixedTrafficScenario]:
        kwargs = {"status": MixedTrafficScenarioStatusEnum.WAITING}
        return self._get_scenarios_by_attributes(**kwargs)

    def get_scenarios_to_join(self, user_id: int) -> List[MixedTrafficScenario]:
        # TODO This seems to be exactly the same as: get_all_waiting_scenarios_where_user_is_not_driving
        # SUB: SELECT ALL THE SCENARIOS IN WAITING STATE WHERE THE USER "IS" DRIVING
        subquery = db.session.query(MixedTrafficScenario.scenario_id)\
            .join(Driver, MixedTrafficScenario.scenario_id == Driver.scenario_id)\
            .where(MixedTrafficScenario.status == MixedTrafficScenarioStatusEnum.WAITING) \
            .where(Driver.user_id == user_id)\
            .subquery()

        # SELECT ALL THE SCENARIOS IN WAITING THAT ARE NOT THOSE WHERE THE USER IS DRIVING
        stmt = db.session.query(MixedTrafficScenario)\
            .where(MixedTrafficScenario.status == MixedTrafficScenarioStatusEnum.WAITING).\
            filter(MixedTrafficScenario.scenario_id.notin_(subquery))

        scenarios = db.session.execute(stmt)

        # Concretize the list as we expect that later
        return list(scenarios.scalars())

    def get_all_active_scenarios_where_user_is_driving(self, user_id):
        """
        Return a collection of scenarios in which the user_id is participating as driver
        :param user_id:
        :return:
        """
        # Create the basic SELECT for User .join(friendships, users.id==friendships.user_id)\
        # https://www.geeksforgeeks.org/returning-distinct-rows-in-sqlalchemy-with-sqlite/
        # query = db.select([db.distinct(EMPLOYEES.c.emp_address)])
        stmt = db.select(MixedTrafficScenario) \
            .join(Driver, MixedTrafficScenario.scenario_id == Driver.scenario_id) \
            .where(Driver.user_id == user_id).where(MixedTrafficScenario.status == MixedTrafficScenarioStatusEnum.ACTIVE)

        scenarios = db.session.execute(stmt)
        db.session.commit()
        # Concretize the list as we expect that later
        return list(scenarios.scalars())

    def get_all_waiting_scenarios_where_user_is_not_driving(self, user_id) -> List[MixedTrafficScenario]:
        # TODO Check if this is indeed the case
        return self.get_scenarios_to_join(user_id)

    def get_all_waiting_scenarios_where_user_is_driving(self, user_id):
        stmt = db.select(MixedTrafficScenario) \
            .join(Driver, MixedTrafficScenario.scenario_id == Driver.scenario_id) \
            .where(Driver.user_id == user_id).where(MixedTrafficScenario.status == MixedTrafficScenarioStatusEnum.WAITING)

        scenarios = db.session.execute(stmt)
        db.session.commit()
        return list(scenarios.scalars())

    def get_all_closed_scenarios_where_user_is_driving(self, user_id):
        stmt = db.select(MixedTrafficScenario) \
            .join(Driver, MixedTrafficScenario.scenario_id == Driver.scenario_id) \
            .where(Driver.user_id == user_id).where(MixedTrafficScenario.status == MixedTrafficScenarioStatusEnum.DONE)

        # scenarios = db.session.execute(stmt).distinct()
        scenarios = db.session.execute(stmt)
        db.session.commit()
        # Concretize the list as we expect that later
        return list(scenarios.scalars())

    # TODO What are CUSTOM scenarios?
    def get_all_active_custom_scenarios(self, user_id):
        stmt = db.select(MixedTrafficScenario) \
            .join(User, MixedTrafficScenario.created_by == User.user_id) \
            .where(User.user_id == user_id).where(MixedTrafficScenario.status == MixedTrafficScenarioStatusEnum.ACTIVE)

        # scenarios = db.session.execute(stmt).distinct()
        scenarios = db.session.execute(stmt)
        db.session.commit()
        # Concretize the list as we expect that later
        return list(scenarios.scalars())

    # TODO What are CUSTOM?
    def get_all_waiting_custom_scenarios(self, user_id):
        stmt = db.select(MixedTrafficScenario) \
            .join(User, MixedTrafficScenario.created_by == User.user_id) \
            .where(User.user_id == user_id).where(MixedTrafficScenario.status == MixedTrafficScenarioStatusEnum.WAITING)

        # scenarios = db.session.execute(stmt).distinct()
        scenarios = db.session.execute(stmt)
        db.session.commit()
        # Concretize the list as we expect that later
        return list(scenarios.scalars())

    # TODO What are CUSTOM?
    def get_all_closed_custom_scenarios(self, user_id):
        stmt = db.select(MixedTrafficScenario) \
            .join(User, MixedTrafficScenario.created_by == User.user_id) \
            .where(User.user_id == user_id).where(MixedTrafficScenario.status == MixedTrafficScenarioStatusEnum.DONE)

        # scenarios = db.session.execute(stmt).distinct()
        scenarios = db.session.execute(stmt)
        db.session.commit()
        # Concretize the list as we expect that later
        return list(scenarios.scalars())

    def get_all_other_active_custom_scenarios(self, user_id) -> List[MixedTrafficScenario]:
        """ Return all the active scenarios in which the user is NOT involved nor is the owner"""
        # SUB: SELECT ALL THE ACTIVE SCENARIOS WHERE THE USER "IS" DRIVING OR OWNER
        subquery = db.session.query(MixedTrafficScenario.scenario_id) \
            .join(Driver, MixedTrafficScenario.scenario_id == Driver.scenario_id) \
            .where(MixedTrafficScenario.status == MixedTrafficScenarioStatusEnum.ACTIVE) \
            .where(or_(Driver.user_id == user_id, MixedTrafficScenario.created_by == user_id)) \
            .subquery()

        # SELECT ALL THE ACTIVE SCENARIOS NOT IN SUBS
        stmt = db.session.query(MixedTrafficScenario)\
            .where(MixedTrafficScenario.status == MixedTrafficScenarioStatusEnum.ACTIVE) \
            .filter(MixedTrafficScenario.scenario_id.notin_(subquery))

        # scenarios = db.session.execute(stmt).distinct()
        scenarios = db.session.execute(stmt)
        db.session.commit()
        # Concretize the list as we expect that later
        return list(scenarios.scalars())

    def get_all_other_closed_custom_scenarios(self, user_id) -> List[MixedTrafficScenario]:
        # """ Return all the closed scenarios in which the user is NOT involved nor is the owner """
        stmt = db.select(MixedTrafficScenario) \
            .join(Driver, MixedTrafficScenario.scenario_id == Driver.scenario_id) \
            .where(MixedTrafficScenario.created_by != user_id) \
            .where(Driver.user_id != user_id).where(MixedTrafficScenario.status == MixedTrafficScenarioStatusEnum.DONE)

        # scenarios = db.session.execute(stmt).distinct()
        scenarios = db.session.execute(stmt)
        db.session.commit()
        # Concretize the list as we expect that later
        return list(scenarios.scalars())

    def add_user_to_scenario(self, user: User, scenario: MixedTrafficScenario) -> Driver:
        # Connenct
        return self.driver_dao.assign_driver_to_user(scenario, user)

    def remove_user_from_scenario(self, user: User, scenario: MixedTrafficScenario):
        # Disconnect
        return self.driver_dao.unassign_driver_from_user(scenario, user)

    def _update_status(self, scenario, status, nested=False):
        # According to the documentation:
        # https://flask-sqlalchemy.palletsprojects.com/en/3.0.x/queries/
        # To update data, modify attributes on the model objects, and commit
        # db.session.begin(nested)
        scenario.status = status
        # TODO Does it trigger if nested = False?
        db.session.commit()

        # connection = sqlite3.connect(self.database_name)
        # try:
        #     where_clause, params_as_tuple = inject_where_statement_using_attributes(
        #         **{"scenario_id": scenario.scenario_id})
        #
        #     # Enable Foreing Keys Support
        #     connection.execute('PRAGMA foreign_keys = ON')
        #
        #     cursor = connection.cursor()
        #     cursor.execute(
        #         # Make sure we provide the tuple for the update and the tuple for the where
        #         UPDATE_MIXED_TRAFFIC_SCENARIO_STATUS + where_clause, (status,) + params_as_tuple
        #     )
        #     connection.commit()
        #
        #     # At this point we need to sync the object
        #     scenario.status = status
        # finally:
        #     connection.close()

    def compute_effective_duration(self, scenario: MixedTrafficScenario):
        """ Return the max timestamp for the states in a scenario. """
        return self.vehicle_state_dao.get_max_timestamp_in_scenario(scenario)

    # TODO This one uses VehicleDAO
    def _cleanup(self, scenario: MixedTrafficScenario):
        """ Get the last state, i.e., the first with DONE and delete all the states in this scenarios and in
        the vehicles for which timestamp > Done.timestamp"""
        # TODO This requires a nested transaction

        # connection = sqlite3.connect(self.database_name)
        # try:
        #     # Enable Foreing Keys Support
        #     connection.execute('PRAGMA foreign_keys = ON')
            # cursor = connection.cursor()
            # cursor.execute(
        # TODO Move this one in VehicleStateDAO!
        from sqlalchemy.sql import text
        stmt = text(f"""
        SELECT Count(*), MAX(timestamp)
        FROM Vehicle_State
        WHERE (user_id, timestamp) IN (
	        SELECT user_id, MIN(timestamp)
	        FROM Vehicle_State
	        WHERE scenario_id = {scenario.scenario_id} and (status = "GOAL_REACHED" OR status = "CRASHED")
	        GROUP BY user_id 
	    )""")

        # from sqlalchemy import func, or_, tuple_
        # from model.vehicle_state import VehicleState
        # THIS ONE MISSES the GROUP BY! Fix it in the next refactoring
        # subquery = db.session.query(VehicleState.user_id, func.min(VehicleState.timestamp))\
        #     .where(VehicleState.scenario_id == scenario.scenario_id) \
        #     .where(or_(VehicleState.status == "GOAL_REACHED", VehicleState.status == "CRASHED")) \
        #     .subquery()
        #
        # stmt = db.session.query(func.count(VehicleState.scenario_id), func.max(VehicleState.timestamp)).where(
        #     tuple_(VehicleState.user_id, VehicleState.timestamp).in_(subquery)
        # )

        tokens = db.session.execute(stmt).first()
        # If the number of drivers is equal to the count, we need to delete all the states!
        if int(tokens[0]) == len(scenario.drivers): #and tokens[1] < scenario.duration:
            # It means that all are we might need to update

            scenario_stopped_at_timestamp = int(tokens[1])
            self.vehicle_state_dao.delete_state_from_scenario_at_timestamp(scenario, scenario_stopped_at_timestamp)
            # cursor.execute(
            #     """
            #         DELETE
            #         FROM Vehicle_State
            #         WHERE scenario_id = ? and timestamp > ?
            #     """, (scenario.scenario_id, scenario_stopped_at_timestamp)
            # )
            db.session.commit()
        else:
            # In this branch, there's no states to delete.
            pass

    def close_scenario(self, scenario):
        """
        Change the status of the scenario to be DONE.
        Remove all the states that will not be computed anymore in case the scenario ends before

        :param scenario:
        :return:
        """

        # Update the scenario state - TODO We need proper transactions here!
        self._update_status(scenario, MixedTrafficScenarioStatusEnum.DONE)
        # Make sure that if the scenario ended before its max duration, we remove all the future states after its completion
        self._cleanup(scenario)

    def activate_scenario(self, scenario):
        # TODO This might be unsafe. Use a transaction
        # TODO: https://stackoverflow.com/questions/36783579/sqlite3-python-how-to-do-an-efficient-bulk-update
        """
        Change the status of the scenario to be active and preallocate the states for all the drivers.
        Define the initial states and schedule the execution of registered AVs

        :param scenario:
        :return:
        """
        try:
            # Then probably use nested == true in the other methods
            # Why at this point there a running transaction?
            # db.session.begin(nested=False)
            # Update the scenario state - mark this as running transaction
            self._update_status(scenario, MixedTrafficScenarioStatusEnum.ACTIVE, nested=True)

            # TODO Why not simply setting driver states and call commit?
            self.vehicle_state_dao.initialize_scenario_states(scenario, nested=True)

            # If everything, including rendering is ok, then commit the transaction
            self.render(scenario, nested=True)

            db.session.commit()
        except Exception as ex:
            db.session.rollback()
            # TODO Clean up the image folder
            raise ex

    # TODO Probably can be merged to insert
    def insert_and_get(self, new_scenario, nested=False):
        """
        Insert the new scenario in the database and return the (update) object representing it
        """
        try:
            # Try to insert the scenario
            db.session.add(new_scenario)
            db.session.commit()
        except sqlalchemy.exc.IntegrityError as err:
            db.session.rollback()
            raise err

        try:
            # At this point the scenario must have a scenario_id, we try to add the drivers
            for _ in range(0, new_scenario.max_players):
                # Empty goal area and initial state - At this point the new_scenario did not get a valid id
                # so we cannot add drivers to it...
                self.driver_dao.add_driver_to_scenario(new_scenario)
            # TODO Check if the scenario has indeed the driver objects associated to it
            db.session.commit()
            return new_scenario
        except sqlalchemy.exc.IntegrityError as err:
            db.session.rollback()
            # Make sure we remove the scenarios as well
            db.session.delete(new_scenario)
            print(traceback.format_exc())
            raise err

    def create_new_scenario(self, data: dict):
        # If this part fails we must trigger a 422
        # TODO How the key is there?!
        scenario_id = data["scenario_id"] if "scenario_id" in data else None

        name = data["name"]
        created_by = data["created_by"]
        # Template ID?
        # TODO Update the FORM!
        template_id = data["template_id"]
        duration = data["duration"]

        n_users = int(data["n_users"])
        n_avs = int(data["n_avs"])

        # Derived attribute. Do we really need this?
        max_players = n_users + n_avs

        description = data["description"] if "description" in data else None

        status = MixedTrafficScenarioStatusEnum.WAITING

        # Create the object for the new scenario
        # TODO Maybe we should store n avg and nn users instead of max_players?
        # TODO: Not that at this point there are not (yet) drivers
        # A transaction might be already started here!
        new_scenario = MixedTrafficScenario(scenario_id=scenario_id, name=name, description=description,
                                            created_by=created_by,
                                            max_players=max_players, n_avs=n_avs, n_users=n_users,
                                            status=status, template_id=template_id,
                                            duration=duration)
        # Store the scenario in the DB and get the updated object
        return self.insert_and_get(new_scenario)

    def delete_scenario_by_id(self, scenario_id):

        # Try to remove the files - "scenario_<scenario_id>_*"
        # NOTE: If we cannot remove the files, it should not be a big deal - besides taking space
        for scenario_image_file in glob.glob(os.path.join(self.images_folder, 'scenario_{}_*'.format(scenario_id))):
            try:
                os.remove(scenario_image_file)
            except Exception as e:
                logger.warning("Cannot delete file {}. Error: {}".format(scenario_image_file, e))

        try:
            # Get the ORM object and not the scalar() version of it
            stmt = db.delete(MixedTrafficScenario).where(MixedTrafficScenario.scenario_id == scenario_id)
            db.session.execute(stmt)
            db.session.commit()
            # connection = sqlite3.connect(self.database_name)
            #
            # # Enable Foreing Keys Support
            # connection.execute('PRAGMA foreign_keys = ON')
            # where_clause, where_tuple = inject_where_statement_using_attributes(**{
            #     "scenario_id": scenario_id
            # })
            # cursor = connection.cursor()
            # cursor.execute(DELETE_MIXED_TRAFFIC_SCENARIO + where_clause, where_tuple)
            # connection.commit()
        except Exception as ex:
            # ADD CASCADE ON DRIVER AND CHECK WITH PRAGMA ON in SQLITE3 CONSOLE IF IT DOES NOT WORK
            # connection.close()
            # This probably is automatically done if commit fails
            db.session.rollback()
            raise ex

    def insert(self, new_scenario):
        """
        Try to insert the new scenario in the database, fails if the scenario violates the DB Constrainnts
        Otherwise, the databse assigns a unique id to the scenario if not specified.

        How to handle the new_scenario.drivers? We assume new scenarios have never drivers, we add them later

        :param new_scenario:
        :return: the scenario_id of the just inserted scenario
        """
        # connection = sqlite3.connect(self.database_name)
        # try:
        #     # Enable Foreing Keys Support
        #     connection.execute('PRAGMA foreign_keys = ON')
        #
        #     cursor = connection.cursor()
        #     # NOTE THIS IS SQLITE SPECIFIC
        #     cursor.execute(INSERT_MIXED_TRAFFIC_SCENARIO,
        #                    (
        #                        new_scenario.scenario_id,
        #                        new_scenario.name,
        #                        new_scenario.description,
        #                        new_scenario.created_by.user_id,
        #                        new_scenario.max_players,
        #                        new_scenario.status,
        #                        # This is a nested Object
        #                        new_scenario.scenario_template.template_id,
        #                        new_scenario.duration
        #                    )
        #                    )
        #     connection.commit()
        #     # Retrieve the last inserted using this cursor. There might be a better way to do this...for instance, avoid using autoincrement/ids
        #     cursor.execute("SELECT last_insert_rowid() FROM Mixed_Traffic_Scenario")
        #     # This returns a tuple
        #     return cursor.fetchone()[0]
        # finally:
        #     connection.close()
        self.insert_and_get(new_scenario)

    # Move this to DriverDAO
    def get_goal_region_for_driver_in_scenario(self, driver, scenario, nested=False):
        """
            Get the goal region assigned to the driver in the scenario
        """
        return self.driver_dao.get_drivers_goal_region_from_scenario(driver, scenario, nested=nested)

    # Move this to DriverDAO
    def get_all_states_for_driver_in_scenario(self, driver, scenario, nested=False):
        """
            Get all the recorded states of this driver in this scenario
        """
        # TODO: REFACTOR: Make those parameters scenario and driver instead of their ID
        return self.vehicle_state_dao.get_states_in_scenario_of_driver(scenario.scenario_id, driver.driver_id)

    # Move this to DriverDAO
    def get_initial_state_for_driver_in_scenario(self, driver, scenario, nested=False):
        # TODO Probably this should be a more focuse query with .first() return
        initial_states = self.vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario.scenario_id, 0, nested=nested)
        return next((vs for vs in initial_states if vs.user_id == driver.user_id), None)

    # TODO This is Really complex. We should either store the status in the scenario table or compute it with a QUERY
    #   Or maybe some FSM
    def get_scenario_state_at_timestamp(self, scenario_id, timestamp, propagate=True) -> Optional[MixedTrafficScenarioStatusEnum]:
        """
        Compute the state of the scenario from the state of the vehicles therein
        """

        # The scenario state is defined by the state of the drivers.
        # However, if not all the drivers are registered, the scenario is not yet READY!

        vehicle_states = self.vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario_id, timestamp)

        if len(vehicle_states) == 0 and propagate:
            # We need to wait for others to join, the scenario is not yet started
            return MixedTrafficScenarioStatusEnum.WAITING
        elif len(vehicle_states) == 0 and not propagate:
            # TODO Is this OPTIONAL or WRONG?
            return None

        # Compute the state of the scenario from the vehicle states if they exist
        active_states = [vs for vs in vehicle_states if vs.status == VehicleStatusEnum.ACTIVE]
        crashed_states = [vs for vs in vehicle_states if vs.status == VehicleStatusEnum.CRASHED]
        goal_reached_states = [vs for vs in vehicle_states if vs.status == VehicleStatusEnum.GOAL_REACHED]

        if len(active_states) + len(crashed_states) + len(goal_reached_states) == len(vehicle_states):
            # This state is not actionable because either the vehicles are active or crashed/goal_reached
            if propagate:
                # If the following state exists and is active or does not exist then this state is DONE otherwise is ACTIVE
                next_state = self.get_scenario_state_at_timestamp(scenario_id, int(timestamp) + 1, propagate=False)
                if next_state == VehicleStatusEnum.ACTIVE or next_state is None:
                    return MixedTrafficScenarioStatusEnum.DONE
            return MixedTrafficScenarioStatusEnum.ACTIVE

        # We are waiting some input? Should be this dependent on the current user state?
        return MixedTrafficScenarioStatusEnum.PENDING


    # TODO Move this into Mixedscenario ADT. Assuming the model is syncronized with the DB
    def is_driver_in_game(self, _scenario: MixedTrafficScenario, user: User):
        # A user not driving in this scenario is not in_game
        scenario = self.get_scenario_by_scenario_id(_scenario.scenario_id)
        if user.user_id not in [d.user_id for d in scenario.drivers]:
            return False

        driver = [d for d in scenario.drivers if d.user_id == user.user_id][0]

        # No user can be in_game if the scenario is not ACTIVE
        if scenario.status != MixedTrafficScenarioStatusEnum.ACTIVE:
            return False

        # Scenario is ACTIVE, find when this is. This requires some weird computation, so we need to do it brute force
        # TODO This loop makes a lot of queries... maybe we can get all states at once
        for timestamp in range(0, scenario.duration+1):
            scenario_state = self.get_scenario_state_at_timestamp(scenario.scenario_id, timestamp)
            if scenario_state == MixedTrafficScenarioStatusEnum.ACTIVE:
                driver_last_known_state = self.vehicle_state_dao.get_vehicle_state_by_scenario_timestamp_driver(scenario, timestamp, driver)
                return not (driver_last_known_state.status == VehicleStatusEnum.CRASHED or driver_last_known_state.status == VehicleStatusEnum.GOAL_REACHED)

        # THIS SHOULD NEVER HAPPEN!
        assert False, f"Problem in is_driver_in_game for {driver.user_id} in scenario {scenario.scenario_id} "