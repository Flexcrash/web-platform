import sqlite3
import logging as logger

from typing import List, Optional
# Enable this ONLY in unit testing
# logger = logging.getLogger('flexcrash.sub')


from model.mixed_traffic_scenario import MixedTrafficScenario, generate_embeddable_html_snippet
from controller.controller import MixedTrafficScenarioGenerator
from model.vehicle_state import VehicleState
from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate, TrainingScenarioTemplate, \
    generate_static_image
from model.user import User

from model.collision_checking import CollisionChecker

from commonroad_route_planner.route_planner import RoutePlanner

import glob
import os

from werkzeug.security import generate_password_hash, check_password_hash

# References
#   - https://stackoverflow.com/questions/2614984/sqlite-sqlalchemy-how-to-enforce-foreign-keys

CREATE_SCENARIO_TEMPLATE = """CREATE TABLE Scenario_Template(
                template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                xml TEXT NOT NULL
            ); 
            """

CREATE_USER_TABLE = """ CREATE TABLE User(
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
                );"""

CREATE_MIXED_TRAFFIC_SCENARIO_TABLE = """ CREATE TABLE Mixed_Traffic_Scenario(
            scenario_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            created_by INTEGER,
            max_players INTEGER,
            status TEXT,
            template_id INTEGER,
            duration INTEGER,
            
            CONSTRAINT fk_created_by
                FOREIGN KEY (created_by)
                REFERENCES User (user_id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
            
            CONSTRAINT fk_template_id
                FOREIGN KEY (template_id)
                REFERENCES Scenario_Template (template_id)
                ON UPDATE CASCADE
                ON DELETE CASCADE

            );
            """

CREATE_DRIVER_TABLE = """ CREATE TABLE Driver(
                user_id INTEGER,
                scenario_id INTEGER,
                goal_region Rectangle,
                
                PRIMARY KEY (user_id, scenario_id),

                CONSTRAINT fk_user_id
                    FOREIGN KEY (user_id)
                    REFERENCES User (user_id)
                    ON UPDATE CASCADE
                    ON DELETE CASCADE

                CONSTRAINT fk_scenario_id
                    FOREIGN KEY (scenario_id) 
                    REFERENCES Mixed_Traffic_Scenario (scenario_id) 
                    ON UPDATE CASCADE
                    ON DELETE CASCADE
                );
            """

# TODO Use vehicle state id as key is prone to error!
# Why is not timestamp and driver_id and scenario_id the PRIMARY KEY?
CREATE_VEHICLE_STATE_TABLE = vehicle_state = """CREATE TABLE Vehicle_State(
            vehicle_state_id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT,
            timestamp INTEGER,
            driver_id INTEGER,
            scenario_id INTEGER,
            position_x FLOAT,
            position_y FLOAT,
            rotation FLOAT,
            speed_ms FLOAT,
            acceleration_m2s FLOAT,
            
            CONSTRAINT fk_driver_id
                FOREIGN KEY (driver_id, scenario_id)
                REFERENCES Driver(user_id, scenario_id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
            );
            """

CREATE_TRAINING_SCENARIO_TEMPLATES = """CREATE TABLE Training_Scenario_Template(
                name PRIMARY KEY,
                description TEXT,
                based_on INTEGER,
                duration FLOAT,
                goal_region Rectangle,
                initial_ego_position_x FLOAT,
                initial_ego_position_y FLOAT,
                initial_ego_rotation FLOAT,
                initial_ego_speed_ms FLOAT,
                initial_ego_acceleration_m2s FLOAT,
                n_avs INTEGER,
                
                CONSTRAINT fk_based_on
                    FOREIGN KEY (based_on)
                    REFERENCES Scenario_Template (template_id)
                    ON UPDATE CASCADE
                    ON DELETE CASCADE
            ); 
            """

INSERT_USER = "INSERT INTO User VALUES(?, ?, ?, ?);"
INSERT_MIXED_TRAFFIC_SCENARIO = "INSERT INTO Mixed_Traffic_Scenario VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
INSERT_DRIVER = "INSERT INTO Driver VALUES (?, ?, ?)"
INSERT_SCENARIO_TEMPLATE = "INSERT INTO Scenario_Template VALUES (?, ?, ?, ?)"
INSERT_VEHICLE_STATE = "INSERT INTO Vehicle_State VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
INSERT_TRAINING_SCENARIO_TEMPLATE = "INSERT INTO Training_Scenario_Template VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"

UPDATE_MIXED_TRAFFIC_SCENARIO_STATUS = "UPDATE Mixed_Traffic_Scenario SET status = ?"
UPDATE_VEHICLE_STATE_STATUS = "UPDATE Vehicle_State SET status = ?"
UPDATE_VEHICLE_STATE = "UPDATE Vehicle_State SET status = ?, position_x = ?,  position_y = ?, rotation = ?, speed_ms = ?, acceleration_m2s = ?"
UPDATE_DRIVER = "UPDATE Driver SET goal_region = ?"

# Note: By keeping the order of attributes here, we can use tuple expansion to create Python objects
SELECT_USER = "SELECT user_id, username, email, password FROM User"
SELECT_MIXED_TRAFFIC_SCENARIO = "SELECT scenario_id, name, description, created_by, max_players, status, template_id, duration FROM Mixed_Traffic_Scenario"
SELECT_SCENARIO_TEMPLATE = "SELECT template_id, name, description, xml FROM Scenario_Template"
SELECT_VEHICLE_STATE = "SELECT vehicle_state_id, status, timestamp, driver_id, scenario_id, position_x, position_y, rotation, speed_ms, acceleration_m2s FROM Vehicle_State"
SELECT_TRAINING_SCENARIO_TEMPLATE = "SELECT name, description, based_on, duration, goal_region, initial_ego_position_x, initial_ego_position_y, initial_ego_rotation, initial_ego_speed_ms, initial_ego_acceleration_m2s, n_avs FROM Training_Scenario_Template"

COUNT_VEHICLE_STATES = "SELECT Count(*) FROM Vehicle_State"

DELETE_MIXED_TRAFFIC_SCENARIO = "DELETE FROM Mixed_Traffic_Scenario"


def hash_the_password(password):
    hashed_password = generate_password_hash(password)
    assert check_password_hash(hashed_password, password)
    return hashed_password


def create_where_statement_using_attributes(**kwargs):
    """
    Utility function to build a conjunction of attributes

    :param kwargs: a dictionary containing the attribute names and values
    :return:
    """
    # No parameters
    if kwargs is None or len(kwargs) == 0:
        return "", ()

    # Collect paramters
    parameter_names = []
    parameter_values = []
    for key, value in kwargs.items():
        if value is None:
            parameter_names.append("{} IS NULL ".format(key))
            # Note: no parameter_value is added here because we do not use ?
        elif type(value) == str and "|" in value:  # Cannot have None here only strings!
            # If nested OR A|B -> (A is ? OR A is ?)
            or_clauses = []
            for v in value.split("|"):
                or_clauses.append("{} = ? ".format(key))
                parameter_values.append(v if v is not None else "NULL")

            parameter_names.append("(" + "OR ".join(or_clauses) + ")")
        else:
            parameter_names.append("{} = ? ".format(key))
            parameter_values.append(value if value is not None else "NULL")

    # Build return values
    where_clause = " WHERE " + "AND ".join(parameter_names)
    params = tuple(parameter_values)

    return where_clause, params


def get_all_drivers(app_config, scenario_id=None):
    connection = sqlite3.connect(app_config["DATABASE_NAME"])
    try:
        cursor = connection.cursor()
        if scenario_id is not None:
            where_clause, where_values = create_where_statement_using_attributes(**{
                "scenario_id": scenario_id
            })
            cursor.execute(
                "SELECT * from Driver" + where_clause, where_values
            )
        else:
            cursor.execute("SELECT * from Driver")
        return cursor.fetchall()
    finally:
        connection.close()


class UserDAO:

    def __init__(self, app_config):
        """
        Initialize the DAO with the give database_name
        :param database_name:
        """
        self.database_name = app_config["DATABASE_NAME"]

    def create_new_user(self, data):
        user_id = data["user_id"] if "user_id" in data else None
        username = data["username"]
        email = data["email"]
        password = data["password"]

        user = User(user_id, username, email, password)
        return self.insert_and_get(user)

    def insert(self, user):
        """
        Try to insert a user into the database. Fails if a user with the same username is already there.
        :param user:
        :return:
        :raise: Exception
        """
        connection = sqlite3.connect(self.database_name)
        # Enable Foreing Keys Support
        connection.execute('PRAGMA foreign_keys = ON')
        cursor = connection.cursor()
        try:
            cursor.execute(INSERT_USER, (
                user.user_id,
                user.username,
                user.email,
                hash_the_password(user.password))
                           )
            connection.commit()
            # Retrieve the last inserted using this cursor. There might be a better way to do this...for instance, avoid using autoincrement/ids
            cursor.execute("SELECT last_insert_rowid() FROM User")
            # This returns a tuple
            return cursor.fetchone()[0]
        finally:
            connection.close()

    def insert_and_get(self, user):
        """
        Try to insert a user into the database and get the updated object in return.
        Fails if a user with the same username is already there.
        :param user:
        :return: the update user object
        :raise: Exception
        """
        user_id = self.insert(user)
        # If the list is empty, something wrong happened, we raise an exception
        return self._get_users_by_attributes(**{"user_id": user_id})[0]

    def _get_users_by_attributes(self, **kwargs) -> List[User]:
        """
        Return a collection of user objects matching the given attributes or an empty list
        :return:
        """

        where_clause, params_as_tuple = create_where_statement_using_attributes(**kwargs)

        connection = sqlite3.connect(self.database_name)
        try:
            cursor = connection.cursor()
            cursor.execute(SELECT_USER + where_clause, params_as_tuple)
            return [User(*tokens) for tokens in cursor.fetchall()]
        finally:
            connection.close()

    def get_all_users(self):
        kwargs = {}
        return self._get_users_by_attributes(**kwargs)

    def get_user_by_user_id(self, user_id: int) -> Optional[User]:
        kwargs = {"user_id": user_id}
        users = self._get_users_by_attributes(**kwargs)
        assert len(users) == 0 or len(users) == 1
        return users[0] if len(users) == 1 else None

    def get_user_by_username(self, username: str) -> Optional[User]:
        kwargs = {"username": username}
        users = self._get_users_by_attributes(**kwargs)
        assert len(users) == 0 or len(users) == 1
        return users[0] if len(users) == 1 else None

    def get_user_by_email(self, email):

        kwargs = {"email": email}
        users = self._get_users_by_attributes(**kwargs)
        assert len(users) == 0 or len(users) == 1
        return users[0] if len(users) == 1 else None

    # TODO: This is the duplicate of verify_password. Also why "email" when we have username and password?
    # def authenticate_user(self, email, password):
    #     """
    #     Return the user if the username and password match, None otherwise
    #     :param username:
    #     :param password:
    #     :return:
    #     """
    #     user = self.get_user_by_email(email)
    #     print("user",user)
    #     if user is None:
    #         return None
    #     if user.password == hash_the_password(password):
    #         return user
    #     return None

    def register_user(self, username, email, password):
        """
        Register a new user. Fails if the username is already taken.
        :param username:
        :param password:
        :return:
        """
        user = User(None, username, email, password)
        return self.insert_and_get(user)

    def get_all_users_driving_in_a_scenario(self, scenario_id):
        """
        Return a collection of users that are driving in the scenario
        :param scenario_id
        :return:
        """
        connection = sqlite3.connect(self.database_name)
        try:
            cursor = connection.cursor()
            cursor.execute("""
                        SELECT U.user_id, U.username, U.email, U.password 
                        FROM User as U INNER JOIN Driver as D 
                        ON U.user_id = D.user_id
                        WHERE D.scenario_id = ?""",
                           (scenario_id,)
                           )
            return [User(*tokens) for tokens in cursor.fetchall()]
        finally:
            connection.close()

    def verify_password(self, email_or_username, password):
        user_by_email = self.get_user_by_email(email_or_username)
        user_by_username = self.get_user_by_username(email_or_username)

        # TODO Only one of the two should match... or maybe the username is also the email?
        # assert (user_by_email and user_by_username is None) or (user_by_email is None and user_by_username)

        user = user_by_username if user_by_email is None else user_by_email

        if user is None:
            return False

        return check_password_hash(user.password, password)


class MixedTrafficScenarioDAO:

    def __init__(self, app_config):
        """
        Initialize the DAO with the given app_config dictionary. Probably a better approach would be to inject directly a configured scenario generator
        """
        self.app_config = app_config
        # Override of configuration. Maybe it is better to redesign it?
        self.database_name = self.app_config["DATABASE_NAME"]
        self.images_folder = self.app_config["SCENARIO_IMAGES_FOLDER"]
        #
        self._goal_region_lenght = self.app_config["GOAL_REGION_LENGTH"]
        self._goal_region_width = self.app_config["GOAL_REGION_WIDTH"]
        self._min_distance_to_end = self.app_config["GOAL_REGION_DIST_TO_END"]
        self._min_init_speed_m_s = self.app_config["MIN_INIT_SPEED_M_S"]
        self._max_init_speed_m_s = self.app_config["MAX_INIT_SPEED_M_S"]

        self.vehicle_state_dao = VehicleStateDAO(app_config)

    def validate(self, scenario: MixedTrafficScenario):
        """
        Check that scenario is valid, trigger AssertionErrors otherwise

        :param scenario:
        :return:
        """
        # Check no collisions
        initial_timestamp = 0
        cc = CollisionChecker(self.vehicle_state_dao)
        # List[Tuple[User, VehicleState]]:
        crashed_vehicles = cc.check_for_collisions(scenario, initial_timestamp)
        # Assert no crashes, report list of crashed vehicles otherwise
        assert len(
            crashed_vehicles) == 0, "Scenario is not valid, the following vehicles are already CRASHED: {}".format(
            ",".join([str(cv[0].user_id) for cv in crashed_vehicles])
        )

        # Check all drivers can reach their goal ares. Note that this is an approximation that works on the following
        # assumptions:
        # - goal areas are ALWAYS AT THE END of lanelets
        # - initial states are ALWAYS INSIDE lanelets (but not necessarily at the end)

        initial_states_at_timestamp = self.vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(
            scenario.scenario_id, initial_timestamp)
        initial_states = {}
        goal_region_as_rectangles = {}

        user_dao = UserDAO(self.app_config)

        for initial_state in initial_states_at_timestamp:
            initial_states[initial_state.user_id] = initial_state
            driver = user_dao.get_user_by_user_id(initial_state.user_id)
            goal_region_as_rectangles[initial_state.user_id] = self.get_goal_region_for_driver_in_scenario(driver,
                                                                                                           scenario)

        scenario, planning_problems = scenario.as_commonroad_scenario_and_planning_problems(
            initial_states=initial_states,
            goal_region_as_rectangles=goal_region_as_rectangles)

        for driver_id, planning_problem in planning_problems.items():
            ## If this does not work, try setting the route_planner.planning_problem.goal.lanelets_of_goal_positions:
            route_planner = RoutePlanner(scenario, planning_problem, reach_goal_state=False)
            # RouteCandidateHolder
            try:
                route_planner.plan_routes().retrieve_first_route().reference_path
            except Exception as exec_info:
                # Cannot find any exception
                # TODO Link the userid?
                raise AssertionError("Cannot find route for {}".format(
                    driver_id
                ))

        driver_id_that_reached_the_goal = cc.check_goal_reached(
            vehicles_state_at_timestamp=initial_states,
            goal_region_as_rectangles=goal_region_as_rectangles)

        # Assert no crashes, report list of crashed vehicles otherwise
        assert len(driver_id_that_reached_the_goal) == 0, \
            "Scenario is not valid,the following vehicles are already at GOAL AREA: {}".format(
                ",".join([str(idx) for idx in driver_id_that_reached_the_goal])
            )

    def render(self, scenario):
        # We need to render the first state of the scenario as well
        # Rendering seems to generate something but the placement of the CAR as Dynamic Obstacle is COMPLETELY WRONG
        initial_state_timestamp = 0
        logger.debug("Rendering scenario state at timestamp {} for scenario {}".format(initial_state_timestamp,
                                                                                       scenario.scenario_id))
        # Get the states at that timestamp - We can avoid this query probably accessing all_initial_states
        # We need a Vehicle DAO here... probebly also to run the above query
        vehicle_state_dao = VehicleStateDAO(self.app_config)
        scenario_states = vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario.scenario_id,
                                                                                           initial_state_timestamp)

        # Generate a global view, including all the drivers
        generate_embeddable_html_snippet(self.images_folder, scenario, scenario_states)
        # Focus on each driver and render the state again
        for driver in scenario.drivers:
            logger.debug("Rendering states at timestamp {} in scenario {} for driver {}".format(initial_state_timestamp,
                                                                                                scenario.scenario_id,
                                                                                                driver.user_id))
            goal_region_as_rectangle = self.get_goal_region_for_driver_in_scenario(driver, scenario)
            generate_embeddable_html_snippet(self.images_folder, scenario, scenario_states,
                                             focus_on_driver=driver, goal_region_as_rectangle=goal_region_as_rectangle)

    def force_initial_state_for_driver_in_scenario(self, init_state_dict, user_id, scenario_id):
        self.vehicle_state_dao.update_initial_state_for_driver_in_scenario(init_state_dict, user_id, scenario_id)

    def force_goal_region_as_rectangle_for_driver_in_scenario(self, goal_region_as_rectangle, user_id, scenario_id):
        connection = sqlite3.connect(self.database_name, detect_types=sqlite3.PARSE_DECLTYPES)
        try:
            # Enable Foreing Keys Support
            connection.execute('PRAGMA foreign_keys = ON')

            where_clause, where_tuple = create_where_statement_using_attributes(**{
                "user_id": user_id,
                "scenario_id": scenario_id
            })
            cursor = connection.cursor()
            # NOTE THIS IS SQLITE SPECIFIC
            cursor.execute(UPDATE_DRIVER + where_clause, (goal_region_as_rectangle,) + where_tuple)
            # Assert the row was updated
            result = cursor.rowcount
            connection.commit()
            assert result == 1
        finally:
            connection.close()
        pass

    def _complete_scenarios(self, scenarios):
        """
        Make sure that the scenarios' complex attributes are filled up properly
        :param scenarios:
        :return:
        """

        # TODO Accessing this DAO here seems a bit wrong...
        mixed_traffic_scenario_template_dao = MixedTrafficScenarioTemplateDAO(self.app_config)
        for scenario in scenarios:
            scenario_template = mixed_traffic_scenario_template_dao.get_template_by_id(scenario.scenario_template)
            scenario.scenario_template = scenario_template

        user_dao = UserDAO(self.app_config)

        for scenario in scenarios:
            created_by = user_dao.get_user_by_user_id(scenario.created_by)
            scenario.created_by = created_by

            drivers = user_dao.get_all_users_driving_in_a_scenario(scenario.scenario_id)
            scenario.drivers = drivers

        return scenarios

    def _get_scenarios_by_attributes(self, **kwargs):
        """
        Return a collection of scenarios matching the given attributes or an empty collection otherwise
        :return:
        """

        where_clause, params_as_tuple = create_where_statement_using_attributes(**kwargs)

        connection = sqlite3.connect(self.database_name)
        try:
            cursor = connection.cursor()
            cursor.execute(SELECT_MIXED_TRAFFIC_SCENARIO + where_clause, params_as_tuple)
            scenarios = [MixedTrafficScenario(*tokens) for tokens in cursor.fetchall()]
        finally:
            connection.close()

        # At this point the scenarios are NOT complete. For instance, they do not have the template, the creator and
        # the drivers but only their IDs
        return self._complete_scenarios(scenarios)

    def get_scenario_by_scenario_id(self, scenario_id: int) -> MixedTrafficScenario:
        kwargs = {"scenario_id": scenario_id}
        scenarios = self._get_scenarios_by_attributes(**kwargs)
        assert len(scenarios) == 0 or len(scenarios) == 1
        return scenarios[0] if len(scenarios) == 1 else None

    def get_all_scenarios(self, created_by=None, status=None, template_id=None):
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

    def get_all_scenarios_created_by_user(self, user_id):
        """
        Return the list of the scenarios created by the given user. It can be an empty list.
        :param user_id:
        :return:
        """
        kwargs = {"created_by": user_id}
        return self._get_scenarios_by_attributes(**kwargs)

    def get_waiting_scenarios(self):
        kwargs = {"status": "WAITING"}
        return self._get_scenarios_by_attributes(**kwargs)

    def get_scenarios_to_join(self, user_id):
        try:
            connection = sqlite3.connect(self.database_name)
            cursor = connection.cursor()
            cursor.execute("""
                        SELECT DISTINCT M.scenario_id, M.name, M.description, M.created_by, M.max_players, M.status, M.template_id, M.duration 
                        FROM Mixed_Traffic_Scenario as M INNER JOIN Driver as D 
                        ON M.scenario_id = D.scenario_id
                        WHERE D.user_id != ? AND M.status = ?""",
                           (user_id, "WAITING")
                           )
            scenarios = [MixedTrafficScenario(*tokens) for tokens in cursor.fetchall()]
        finally:
            connection.close()

        return self._complete_scenarios(scenarios)

    def get_all_active_scenarios_where_user_is_driving(self, user_id):
        """
        Return a collection of scenarios in which the user_id is participating as driver
        :param user_id:
        :return:
        """
        connection = sqlite3.connect(self.database_name)
        try:
            cursor = connection.cursor()
            cursor.execute("""
                        SELECT M.scenario_id, M.name, M.description, M.created_by, M.max_players, M.status, M.template_id, M.duration 
                        FROM Mixed_Traffic_Scenario as M INNER JOIN Driver as D 
                        ON M.scenario_id = D.scenario_id
                        WHERE D.user_id = ? AND M.status = ?""",
                           (user_id, "ACTIVE")
                           )
            scenarios = [MixedTrafficScenario(*tokens) for tokens in cursor.fetchall()]
        finally:
            connection.close()

        return self._complete_scenarios(scenarios)

    def get_all_waiting_scenarios_where_user_is_not_driving(self, user_id) -> List[MixedTrafficScenario]:
        """
        Return all the scenarios in WAITING state for which the given user is NOT YET a DRIVER
        :param user_id:
        :return:
        """
        try:
            connection = sqlite3.connect(self.database_name)
            cursor = connection.cursor()
            cursor.execute("""
                        SELECT M.scenario_id, M.name, M.description, M.created_by, M.max_players, M.status, M.template_id, M.duration 
                        FROM Mixed_Traffic_Scenario as M
                        WHERE M.status = ? and M.scenario_id NOT IN (
                            SELECT D.scenario_id
                            FROM Driver as D 
                            WHERE D.user_id = ?)
                        """,
                           ("WAITING", user_id))
            scenarios = [MixedTrafficScenario(*tokens) for tokens in cursor.fetchall()]
        finally:
            connection.close()

        return self._complete_scenarios(scenarios)

    def get_all_waiting_scenarios_where_user_is_driving(self, user_id):

        try:
            connection = sqlite3.connect(self.database_name)
            cursor = connection.cursor()
            cursor.execute("""
                        SELECT M.scenario_id, M.name, M.description, M.created_by, M.max_players, M.status, M.template_id, M.duration 
                        FROM Mixed_Traffic_Scenario as M INNER JOIN Driver as D 
                        ON M.scenario_id = D.scenario_id
                        WHERE D.user_id = ? AND M.status = ?""",
                           (user_id, "WAITING")
                           )
            scenarios = [MixedTrafficScenario(*tokens) for tokens in cursor.fetchall()]
        finally:
            connection.close()

        return self._complete_scenarios(scenarios)

    def get_all_closed_scenarios_where_user_is_driving(self, user_id):

        try:
            connection = sqlite3.connect(self.database_name)
            cursor = connection.cursor()
            cursor.execute("""
                        SELECT M.scenario_id, M.name, M.description, M.created_by, M.max_players, M.status, M.template_id, M.duration 
                        FROM Mixed_Traffic_Scenario as M INNER JOIN Driver as D 
                        ON M.scenario_id = D.scenario_id
                        WHERE D.user_id = ? AND M.status = ?""",
                           (user_id, "DONE")
                           )
            scenarios = [MixedTrafficScenario(*tokens) for tokens in cursor.fetchall()]
        finally:
            connection.close()

        return self._complete_scenarios(scenarios)

    def get_all_active_custom_scenarios(self, user_id):

        try:
            connection = sqlite3.connect(self.database_name)
            cursor = connection.cursor()
            cursor.execute("""
                        SELECT M.scenario_id, M.name, M.description, M.created_by, M.max_players, M.status, M.template_id, M.duration 
                        FROM Mixed_Traffic_Scenario as M INNER JOIN User as U 
                        ON M.created_by = U.user_id
                        WHERE U.user_id = ? AND M.status = ?""",
                           (user_id, "ACTIVE")
                           )
            scenarios = [MixedTrafficScenario(*tokens) for tokens in cursor.fetchall()]
        finally:
            connection.close()

        return self._complete_scenarios(scenarios)

    def get_all_waiting_custom_scenarios(self, user_id):

        try:
            connection = sqlite3.connect(self.database_name)
            cursor = connection.cursor()
            cursor.execute("""
                        SELECT M.scenario_id, M.name, M.description, M.created_by, M.max_players, M.status, M.template_id, M.duration 
                        FROM Mixed_Traffic_Scenario as M INNER JOIN User as U 
                        ON M.created_by = U.user_id
                        WHERE U.user_id = ? AND M.status = ?""",
                           (user_id, "WAITING")
                           )
            scenarios = [MixedTrafficScenario(*tokens) for tokens in cursor.fetchall()]
        finally:
            connection.close()

        return self._complete_scenarios(scenarios)

    def get_all_closed_custom_scenarios(self, user_id):

        try:
            connection = sqlite3.connect(self.database_name)
            cursor = connection.cursor()
            cursor.execute("""
                        SELECT M.scenario_id, M.name, M.description, M.created_by, M.max_players, M.status, M.template_id, M.duration 
                        FROM Mixed_Traffic_Scenario as M INNER JOIN User as U
                        ON M.created_by = U.user_id
                        WHERE U.user_id = ? AND M.status = ?""",
                           (user_id, "DONE")
                           )
            scenarios = [MixedTrafficScenario(*tokens) for tokens in cursor.fetchall()]
        finally:
            connection.close()

        return self._complete_scenarios(scenarios)

    def get_all_other_active_custom_scenarios(self, user_id) -> List[MixedTrafficScenario]:
        """ Return all the active scenarios in which the user is NOT involved nor is the owner"""
        try:
            connection = sqlite3.connect(self.database_name)
            cursor = connection.cursor()
            # Return all the scenarios in which the user is NOT the owner
            cursor.execute("""
                              SELECT DISTINCT(M.scenario_id), M.name, M.description, M.created_by, M.max_players, M.status, M.template_id, M.duration 
                              FROM Mixed_Traffic_Scenario as M INNER JOIN Driver as D 
                                ON M.scenario_id = D.scenario_id
                              WHERE
                                M.created_by != ? AND D.user_id != ? AND M.status = ?""",
                           (user_id, user_id, "ACTIVE")
                           )
            scenarios = [MixedTrafficScenario(*tokens) for tokens in cursor.fetchall()]
            # The query returns an entry for each Driver, so there are duplicates. Let's removed them
            # TODO Update the query to return only DISTINCT
        finally:
            connection.close()

        return self._complete_scenarios(scenarios)

        return self._complete_scenarios(scenarios)

    def get_all_other_closed_custom_scenarios(self, user_id) -> List[MixedTrafficScenario]:
        """ Return all the closed scenarios in which the user is NOT involved nor is the owner """
        try:
            connection = sqlite3.connect(self.database_name)
            cursor = connection.cursor()
            # Return all the scenarios in which the user is NOT the owner
            cursor.execute("""
                              SELECT M.scenario_id, M.name, M.description, M.created_by, M.max_players, M.status, M.template_id, M.duration 
                              FROM Mixed_Traffic_Scenario as M INNER JOIN Driver as D 
                                ON M.scenario_id = D.scenario_id
                              WHERE
                                M.created_by != ? AND D.user_id != ? AND M.status = ?""",
                           (user_id, user_id, "DONE")
                           )
            scenarios = [MixedTrafficScenario(*tokens) for tokens in cursor.fetchall()]
        finally:
            connection.close()

        return self._complete_scenarios(scenarios)

    def add_user_to_scenario(self, user, scenario):
        """
        Register the user as a driver in the given scenario and define its goal region (a Rectangle object).
        The consistency checks of the database should prevent duplication (the same user cannot be added twice)
        and foreing key constraints (the table can contain only elements for user/scenarios that exist already).
        """

        mixed_traffic_scenario_generator = MixedTrafficScenarioGenerator(scenario,
                                                                         self._goal_region_lenght,
                                                                         self._goal_region_width,
                                                                         self._min_distance_to_end,
                                                                         self._min_init_speed_m_s,
                                                                         self._max_init_speed_m_s,
                                                                         # TODO Bad design!!
                                                                         self)

        # The Goal Region must be reachable from the Initial State of the User

        # Create a Rectangle corresponding to the goal region
        goal_region = mixed_traffic_scenario_generator.generate_random_goal_region()

        # Store everything to the Driver table
        connection = sqlite3.connect(self.database_name)
        try:
            # Enable Foreing Keys Support
            connection.execute('PRAGMA foreign_keys = ON')

            cursor = connection.cursor()
            cursor.execute(
                INSERT_DRIVER, (user.user_id, scenario.scenario_id, goal_region)
            )
            connection.commit()

            # Update also the object
            scenario.drivers.append(user)
        finally:
            connection.close()

    def _update_status(self, scenario, status):
        connection = sqlite3.connect(self.database_name)
        try:
            where_clause, params_as_tuple = create_where_statement_using_attributes(
                **{"scenario_id": scenario.scenario_id})

            # Enable Foreing Keys Support
            connection.execute('PRAGMA foreign_keys = ON')

            cursor = connection.cursor()
            cursor.execute(
                # Make sure we provide the tuple for the update and the tuple for the where
                UPDATE_MIXED_TRAFFIC_SCENARIO_STATUS + where_clause, (status,) + params_as_tuple
            )
            connection.commit()

            # At this point we need to sync the object
            scenario.status = status

        finally:
            connection.close()

    def compute_effective_duration(self, scenario: MixedTrafficScenario):
        """ Return the max timestamp for the states in a scenario. """

        connection = sqlite3.connect(self.database_name)
        try:
            # Enable Foreing Keys Support
            connection.execute('PRAGMA foreign_keys = ON')

            cursor = connection.cursor()
            cursor.execute(
                """SELECT MAX(timestamp)
                    FROM Vehicle_State
                    WHERE scenario_id = ?
                """, (scenario.scenario_id,)
            )

            # If the number of drivers is equal to the count, we need to delete all the states!
            tokens = cursor.fetchone()
            connection.commit()

            return int(tokens[0])

        finally:
            connection.close()

        pass

    def _cleanup(self, scenario: MixedTrafficScenario):
        """ Get the last state, i.e., the first with DONE and delete all the states in this scenarios and in
        the vehicles for which timestamp > Done.timestamp"""

        connection = sqlite3.connect(self.database_name)
        try:
            # Enable Foreing Keys Support
            connection.execute('PRAGMA foreign_keys = ON')

            cursor = connection.cursor()
            cursor.execute(
                """SELECT Count(*), MAX(timestamp)
                    FROM Vehicle_State
                    WHERE (driver_id, timestamp) IN (
	                    SELECT driver_id, MIN(timestamp) 
	                    FROM Vehicle_State
	                    WHERE scenario_id = ? and (status = "GOAL_REACHED" OR status = "CRASHED")
	                    GROUP BY driver_id
                    )
                """, (scenario.scenario_id,)
            )

            # If the number of drivers is equal to the count, we need to delete all the states!
            tokens = cursor.fetchone()
            if int(tokens[0]) == len(scenario.drivers): #and tokens[1] < scenario.duration:
                # It means that all are we might need to update
                scenario_stopped_at_timestamp = int(tokens[1])
                cursor.execute(
                    """
                        DELETE
                        FROM Vehicle_State
                        WHERE scenario_id = ? and timestamp > ?
                    """, (scenario.scenario_id, scenario_stopped_at_timestamp)
                )

            connection.commit()
        finally:
            connection.close()

    def close_scenario(self, scenario):
        """
        Change the status of the scenario to be DONE.
        Remove all the states that will not be computed anymore in case the scenario ends before

        :param scenario:
        :return:
        """

        # Update the scenario state - TODO We need proper transactions here!
        self._update_status(scenario, "DONE")
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

        # Update the scenario state
        self._update_status(scenario, "ACTIVE")

        # Preallocate the vehicle states
        all_states = []
        connection = sqlite3.connect(self.database_name)
        try:
            # Default values
            state_id = None  # SMELLS BAD user_id?
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
                    all_states.append((state_id, status, timestamp, driver.user_id, scenario.scenario_id, position_x,
                                       position_y, rotation, speed_ms, acceleration_m2s))

            # Enable Foreing Keys Support
            connection.execute('PRAGMA foreign_keys = ON')
            connection.executemany(INSERT_VEHICLE_STATE, all_states)
            connection.commit()
        finally:
            connection.close()

        # TODO Why we do redefine the GOAL AREA for those drivers?! We do not, we create the initial states

        # Define the initial state for all the drivers! TODO Use a Vehicle DAO for this?

        mixed_traffic_scenario_generator = MixedTrafficScenarioGenerator(scenario,
                                                                         self._goal_region_lenght,
                                                                         self._goal_region_width,
                                                                         self._min_distance_to_end,
                                                                         self._min_init_speed_m_s,
                                                                         self._max_init_speed_m_s,
                                                                         # TODO Bad design
                                                                         self)

        all_initial_states = mixed_traffic_scenario_generator.create_initial_states()

        connection = sqlite3.connect(self.database_name)
        try:
            # Enable Foreing Keys Support
            connection.execute('PRAGMA foreign_keys = ON')
            connection.executemany(INSERT_VEHICLE_STATE, all_initial_states)
            connection.commit()
        finally:
            connection.close()

        self.render(scenario)

    def insert_and_get(self, new_scenario):
        """
        Insert the new scenario in the database and return the (update) ojbect representing it
        :param new_scenario: (possibly without scenario_id)
        :return: new_scenario (with scenario_id)
        """
        new_scenario_id = self.insert(new_scenario)
        # If the list is empty, something wrong happened, we raise an exception
        return self._get_scenarios_by_attributes(**{"scenario_id": new_scenario_id})[0]

    def create_new_scenario(self, data):
        # If this part fails we must trigger a 422

        scenario_id = data["scenario_id"]
        name = data["name"]
        created_by = data["created_by"]
        template = data["template"]
        duration = data["duration"]
        n_users = int(data["n_users"])
        n_avs = int(data["n_avs"])

        max_players = n_users + n_avs

        # Optional
        description = data["description"]

        status = "WAITING"

        # Create the object for the new scenario
        # TODO Maybe we should store n avg and nn users instead of max_players?
        new_scenario = MixedTrafficScenario(scenario_id, name, description, created_by, max_players, status, template,
                                            duration)
        # Store the scenario in the DB and get the updated object
        return self.insert_and_get(new_scenario)

    def delete_scenario_by_id(self, scenario_id):
        try:
            connection = sqlite3.connect(self.database_name)

            # Enable Foreing Keys Support
            connection.execute('PRAGMA foreign_keys = ON')
            where_clause, where_tuple = create_where_statement_using_attributes(**{
                "scenario_id": scenario_id
            })
            cursor = connection.cursor()
            cursor.execute(DELETE_MIXED_TRAFFIC_SCENARIO + where_clause, where_tuple)
            connection.commit()
        finally:
            connection.close()

        # Try to remove the files - "scenario_<scenario_id>_*"
        for scenario_image_file in glob.glob(os.path.join(self.images_folder, 'scenario_{}_*'.format(scenario_id))):
            try:
                os.remove(scenario_image_file)
            except Exception as e:
                logger.warning("Cannot delete file {}. Error: {}".format(scenario_image_file, e))

    def insert(self, new_scenario):
        """
        Try to insert the new scenario in the database, fails if the scenario violates the DB Constrainnts
        Otherwise, the databse assigns a unique id to the scenario if not specified.

        How to handle the new_scenario.drivers? We assume new scenarios have never drivers, we add them later

        :param new_scenario:
        :return: the scenario_id of the just inserted scenario
        """
        connection = sqlite3.connect(self.database_name)
        try:
            # Enable Foreing Keys Support
            connection.execute('PRAGMA foreign_keys = ON')

            cursor = connection.cursor()
            # NOTE THIS IS SQLITE SPECIFIC
            cursor.execute(INSERT_MIXED_TRAFFIC_SCENARIO,
                           (
                               new_scenario.scenario_id,
                               new_scenario.name,
                               new_scenario.description,
                               new_scenario.created_by.user_id,
                               new_scenario.max_players,
                               new_scenario.status,
                               # This is a nested Object
                               new_scenario.scenario_template.template_id,
                               new_scenario.duration
                           )
                           )
            connection.commit()
            # Retrieve the last inserted using this cursor. There might be a better way to do this...for instance, avoid using autoincrement/ids
            cursor.execute("SELECT last_insert_rowid() FROM Mixed_Traffic_Scenario")
            # This returns a tuple
            return cursor.fetchone()[0]
        finally:
            connection.close()

    def get_goal_region_for_driver_in_scenario(self, driver, scenario):
        """
            Get the goal region assigned to the driver in the scenario
        """
        connection = sqlite3.connect(self.database_name, detect_types=sqlite3.PARSE_DECLTYPES)
        try:
            # Enable Foreing Keys Support
            connection.execute('PRAGMA foreign_keys = ON')

            where_clause, where_tuple = create_where_statement_using_attributes(**{
                "user_id": driver.user_id,
                "scenario_id": scenario.scenario_id
            })
            #                 goal_region Rectangle,
            cursor = connection.cursor()
            # NOTE THIS IS SQLITE SPECIFIC
            cursor.execute("SELECT goal_region FROM Driver " + where_clause, where_tuple)

            # This returns a tuple, so we need to extract the class from it. note since we have in place converters this should be a Rectangle object
            return cursor.fetchone()[0]
        finally:
            connection.close()

    def get_initial_state_for_driver_in_scenario(self, driver, scenario):
        vehicle_state_dao = VehicleStateDAO(self.app_config)
        initial_states = vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario.scenario_id, 0)
        return next((vs for vs in initial_states if vs.user_id == driver.user_id), None)

    # TODO This is not OK
    def get_scenario_state_at_timestamp(self, scenario_id, timestamp, propagate=True):
        # The scenario state is defined by the state of the drivers.
        # However, if not all the drivers are registered, the scenario is not yet READY!

        vehicle_state_dao = VehicleStateDAO(self.app_config)
        vehicle_states = vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario_id, timestamp)

        if len(vehicle_states) == 0 and propagate:
            # We need to wait for others to join, the scenario is not yet started
            return "WAITING"
        elif len(vehicle_states) == 0 and not propagate:
            return None

        # Compute the state of the scenario from the vehicle states if they exist
        active_states = [vs for vs in vehicle_states if vs.status == "ACTIVE"]
        crashed_states = [vs for vs in vehicle_states if vs.status == "CRASHED"]
        goal_reached_states = [vs for vs in vehicle_states if vs.status == "GOAL_REACHED"]

        if len(active_states) + len(crashed_states) + len(goal_reached_states) == len(vehicle_states):
            # This state is not actionable because either the vehicles are active or crashed/goal_reached
            if propagate:
                # If the following state exists and is active or does not exist then this state is DONE otherwise is ACTIVE
                next_state = self.get_scenario_state_at_timestamp(scenario_id, int(timestamp) + 1, propagate=False)
                if next_state == "ACTIVE" or next_state is None:
                    return "DONE"
            return "ACTIVE"

        # We are waiting some input? Should be this dependent on the current user state?
        return "PENDING"

    def get_initial_state_for_driver_in_scenario(self, driver, scenario):
        vehicle_state_dao = VehicleStateDAO(self.app_config)
        initial_states = vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario.scenario_id, 0)
        return next((vs for vs in initial_states if vs.user_id == driver.user_id), None)

    def is_driver_in_game(self, scenario: MixedTrafficScenario, driver):
        # A user not driving in this scenario is not in_game
        if driver.user_id not in [d.user_id for d in scenario.drivers]:
            return False
        # No user can be in_game if the scenario is not ACTIVE
        if scenario.status != "ACTIVE":
            return False

        # Scenario is ACTIVE, find when this is. This requires some weird computation, so we need to do it brute force
        for timestamp in range(0, scenario.duration+1):
            scenario_state = self.get_scenario_state_at_timestamp(scenario.scenario_id, timestamp)
            if scenario_state == "ACTIVE":
                driver_last_known_state = self.vehicle_state_dao.get_vehicle_state_by_scenario_timestamp_driver(scenario, timestamp, driver)
                return not (driver_last_known_state.status == "CRASHED" or driver_last_known_state.status == "GOAL_REACHED")

        # THIS SHOULD NEVER HAPPEN!
        assert False, f"Problem in is_driver_in_game for {driver.user_id} in scenario {scenario.scenario_id} "

class MixedTrafficScenarioTemplateDAO:

    def __init__(self, app_config):
        """
        Initialize the DAO with the give database_name and the folder where to store the images
        """
        self.database_name = app_config["DATABASE_NAME"]
        self.images_folder = app_config["TEMPLATE_IMAGES_FOLDER"]

    def create_new_template(self, data):
        # Mandatory
        name = data["name"]
        xml = data["xml"]
        # Optional
        template_id = data["template_id"] if "template_id" in data else None
        description = data["description"]

        new_template = MixedTrafficScenarioTemplate(template_id, name, description, xml)
        # Store the Template in the DB. Ensures it has a template_id, hence we return the updated object
        new_template = self.insert_and_get(new_template)

        # Store the Template on the FS
        template_image = generate_static_image(self.images_folder, new_template)

        # TODO Link the image to the scenario_template object?
        # If everything worked out, return the template
        return new_template, template_image

    def insert(self, template):
        """
               Try to insert the template scenario in the database, fails if the template scenario violates the DB Constraints
               Otherwise, the database assigns a unique id to the teamplte scenario unless specified.
               :param template: the template to store in the database
               :return: the template_id of the just inserted template scenario
               """
        connection = sqlite3.connect(self.database_name)
        try:
            # Enable Foreing Keys Support
            connection.execute('PRAGMA foreign_keys = ON')

            cursor = connection.cursor()
            cursor.execute(
                INSERT_SCENARIO_TEMPLATE,
                (template.template_id, template.name, template.description, template.xml,),
            )
            connection.commit()
            # Retrieve the last inserted using this cursor.
            # NOTE THIS IS SQLITE SPECIFIC
            cursor.execute("SELECT last_insert_rowid() FROM Scenario_Template")
            # This returns a tuple, but we need the template_id
            return cursor.fetchone()[0]
        finally:
            connection.close()

    def insert_and_get(self, template):
        """
        Try to insert a scenario template into the database and get the updated object in return.
        Fails if a scenario template has issues.
        :param template
        :return: the update scenario template object
        :raise: Exception
        """
        template_id = self.insert(template)
        # If the list is empty, something wrong happened, we raise an exception
        return self._get_templates_by_attributes(**{"template_id": template_id})[0]

    def _get_templates_by_attributes(self, **kwargs):
        """
        Return a collection of template scenarios matching the given attributes or an empty collection otherwise
        :return:
        """

        where_clause, params_as_tuple = create_where_statement_using_attributes(**kwargs)
        connection = sqlite3.connect(self.database_name)
        try:
            cursor = connection.cursor()
            cursor.execute(SELECT_SCENARIO_TEMPLATE + where_clause, params_as_tuple)
            return [MixedTrafficScenarioTemplate(*tokens) for tokens in cursor.fetchall()]
        finally:
            connection.close()

    def get_template_by_id(self, template_id):
        """
        Return the template with the given template_id if exists. None otherwise.
        :param template_id:
        :return:
        """

        kwargs = {"template_id": template_id}
        templates = self._get_templates_by_attributes(**kwargs)
        assert len(templates) == 0 or len(templates) == 1
        return templates[0] if len(templates) == 1 else None

    def get_templates(self):
        """
        Return the collection of all the scenario templates stored in the database. Otherwise an empty list
        :return:
        """
        kwargs = {}
        return self._get_templates_by_attributes(**kwargs)


class TrainingScenarioTemplateDAO:

    def __init__(self, app_config):
        """
        Initialize the DAO with the give database_name and the folder where to store the images
        """
        self.app_config = app_config
        self.database_name = app_config["DATABASE_NAME"]
        self.images_folder = app_config["TEMPLATE_IMAGES_FOLDER"]

    def create_new_template(self, data):
        # Mandatory

        name = data["name"]

        template_dao = MixedTrafficScenarioTemplateDAO(self.app_config)
        based_on = template_dao.get_template_by_id(data["based_on"])

        duration = data["duration"]

        goal_region_as_rectangle = data["goal_region_as_rectangle"]

        initial_ego_position_x = data["initial_ego_position_x"]
        initial_ego_position_y = data["initial_ego_position_y"]
        initial_ego_rotation = data["initial_ego_rotation"]
        initial_ego_speed_ms = data["initial_ego_speed_ms"]
        initial_ego_acceleration_m2s = data["initial_ego_acceleration_m2s"]

        n_avs = data["n_avs"]

        # Optional
        description = data["description"] if "description" in data else None

        new_training_template = TrainingScenarioTemplate(name, description, based_on, duration,
                                                         goal_region_as_rectangle,
                                                         initial_ego_position_x, initial_ego_position_y,
                                                         initial_ego_rotation, initial_ego_speed_ms,
                                                         initial_ego_acceleration_m2s,
                                                         n_avs)
        self.insert(new_training_template)

        # Store the Template on the FS
        # TODO Use the type for setting the name of the files!
        training_template_image = generate_static_image(self.images_folder, new_training_template)

        # TODO Link the image to the scenario_template object?
        # If everything worked out, return the template
        return new_training_template, training_template_image

    def insert(self, training_template):
        """
           Try to insert the training template scenario in the database, fails if the template scenario violates the DB Constraints
           :param training_template: the template to store in the database
           :return: the template_id of the just inserted template scenario
        """
        connection = sqlite3.connect(self.database_name, detect_types=sqlite3.PARSE_DECLTYPES)
        try:
            # Enable Foreing Keys Support
            connection.execute('PRAGMA foreign_keys = ON')

            cursor = connection.cursor()
            cursor.execute(
                INSERT_TRAINING_SCENARIO_TEMPLATE,
                (training_template.name,
                 training_template.description,
                 # Note this one
                 training_template.based_on.template_id,
                 training_template.duration,
                 #
                 training_template.goal_region_as_rectangle,
                 #
                 training_template.initial_ego_position_x, training_template.initial_ego_position_y,
                 training_template.initial_ego_rotation, training_template.initial_ego_speed_ms,
                 training_template.initial_ego_acceleration_m2s,
                 training_template.n_avs)
            )
            connection.commit()
            # Retrieve the last inserted using this cursor.
            # NOTE THIS IS SQLITE SPECIFIC
            cursor.execute("SELECT last_insert_rowid() FROM Scenario_Template")
            # This returns a tuple, but we need the template_id
            return cursor.fetchone()[0]
        finally:
            connection.close()

    def _get_training_templates_by_attributes(self, **kwargs):
        """
        Return a collection of TrainingScenarioTemplates
        :return:
        """
        where_clause, params_as_tuple = create_where_statement_using_attributes(**kwargs)
        connection = sqlite3.connect(self.database_name)
        try:
            cursor = connection.cursor()
            cursor.execute(SELECT_TRAINING_SCENARIO_TEMPLATE + where_clause, params_as_tuple)
            # based_on is an integer now
            training_templates = [TrainingScenarioTemplate(*tokens) for tokens in cursor.fetchall()]
        finally:
            connection.close()
        # Make sure that the MixedTrafficTemplates are there!
        template_dao = MixedTrafficScenarioTemplateDAO(self.app_config)

        for training_template in training_templates:
            # Get the Template
            training_template.based_on = template_dao.get_template_by_id(training_template.based_on)

        return training_templates

    def get_templates(self):
        kwargs = {}
        return self._get_training_templates_by_attributes(**kwargs)


class VehicleStateDAO:

    def __init__(self, app_config):
        self.app_config = app_config
        self.database_name = app_config["DATABASE_NAME"]
        self.images_folder = app_config["SCENARIO_IMAGES_FOLDER"]
        #
        self.collision_checker = CollisionChecker(self)

    def update_initial_state_for_driver_in_scenario(self, init_state_dict, user_id, scenario_id):
        connection = sqlite3.connect(self.database_name)
        try:
            connection.execute('PRAGMA foreign_keys = ON')
            cursor = connection.cursor()

            logger.info('FORCE UPDATING INITIAL STATE for driver {} in scenario {}'.format(user_id, scenario_id))

            # Enable Foreing Keys Support
            where_clause, where_params = create_where_statement_using_attributes(**{
                "scenario_id": scenario_id,
                "driver_id": user_id,
                # Force this to be the initial state
                "timestamp": 0,
                # Note: by design this state already exists, we need to force-update it
                "status": "ACTIVE"
            })

            # Since we express at least one state update, that status becomes PENDING -> WAITING ( or WAITING->WAITING)
            cursor.execute(
                UPDATE_VEHICLE_STATE + where_clause,
                ("ACTIVE", init_state_dict["position_x"], init_state_dict["position_y"],
                 init_state_dict["rotation"], init_state_dict["speed_ms"],
                 init_state_dict["acceleration_m2s"]) + where_params,
            )
            result = cursor.rowcount
            connection.commit()
            assert result == 1
        finally:
            connection.close()

    # vehicle_state_id, timestamp, user_id, scenario_id, position_x, position_y, rotation, speed_ms, acceleration_m2s
    def insert(self, vehicle_state):
        """
        Try to insert the vehicle state in the database. Fails if any DB constraints are missed or the user is not a
        driver in this scenario. We need an explicit constraints here
        :param vehicle_state:
        :return:
        """
        connection = sqlite3.connect(self.database_name)
        try:
            # Enable Foreing Keys Support
            connection.execute('PRAGMA foreign_keys = ON')
            cursor = connection.cursor()
            cursor.execute(
                INSERT_VEHICLE_STATE,
                (vehicle_state.vehicle_state_id, vehicle_state.status, vehicle_state.timestamp, vehicle_state.user_id,
                 vehicle_state.scenario_id,
                 vehicle_state.position_x, vehicle_state.position_y, vehicle_state.rotation, vehicle_state.speed_ms,
                 vehicle_state.acceleration_m2s),
            )
            connection.commit()
        finally:
            connection.close()

    def _get_vehicle_state_by_attributes(self, **kwargs) -> List[VehicleState]:
        """
        Return a collection of vehicle states matching the given attributes or an empty collection otherwise
        :return:
        """

        where_clause, params_as_tuple = create_where_statement_using_attributes(**kwargs)
        connection = sqlite3.connect(self.database_name)
        try:
            cursor = connection.cursor()
            cursor.execute(SELECT_VEHICLE_STATE + where_clause, params_as_tuple)
            return [VehicleState(*tokens) for tokens in cursor.fetchall()]
        finally:
            connection.close()

    def get_vehicle_state_by_vehicle_state_id(self, vehicle_state_id):
        """
        Return the vehicle state with the given id if it exists. None otherwise
        :param vehicle_state_id:
        :return:
        """
        kwargs = {"vehicle_state_id": vehicle_state_id}
        vehicle_states = self._get_vehicle_state_by_attributes(**kwargs)
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

    def get_vehicle_states_by_scenario_id_at_timestamp(self, scenario_id, timestamp) -> List[VehicleState]:
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
        return self._get_vehicle_state_by_attributes(**kwargs)

    def get_vehicle_state_by_scenario_timestamp_driver(self, scenario, timestamp, driver):
        """
             Return all the states associated to the given scenario at the given timestamp for the given driver
             """
        kwargs = {
            "scenario_id": scenario.scenario_id,
            "timestamp": timestamp,
            "driver_id": driver.user_id
        }
        # TODO Here we should check that only one state is indeed returned from the DB
        query_result = self._get_vehicle_state_by_attributes(**kwargs)
        return query_result[0] if len(query_result) == 1 else None

    def get_states_in_scenario_of_driver(self, scenario_id, driver_id):
        """
        Return all the vehicles states for a given user in a given scenario
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
                                               driver: User,
                                               state_to_propagate: VehicleState):
        """
        Propagate the given state for this driver until scenario.duration
        """

        connection = sqlite3.connect(self.database_name)
        try:
            connection.execute('PRAGMA foreign_keys = ON')
            cursor = connection.cursor()
            logger.info("===> Propagating state {} for driver {} from timestamp {} to {} in scenario {}".format(
                state_to_propagate.status, driver.user_id, state_to_propagate.timestamp, scenario.duration,
                scenario.scenario_id)
            )

            # We need to exclude the current state, since its already set, and we need to include the duration + 1 since
            # timestamps are 1-indexed
            timestamps_to_update = list(range(state_to_propagate.timestamp, scenario.duration + 1))

            # Enable Foreing Keys Support
            where_clause, where_params = create_where_statement_using_attributes(**{
                "scenario_id": scenario.scenario_id,
                "driver_id": driver.user_id,
                # Update the state with the given timestamp (unique for each driver/scenario)
                "timestamp": "|".join([str(t) for t in timestamps_to_update])
                # We do not check what's there, we FORCEFULLY update the status
            })

            # Since we express at least one state update, that status becomes PENDING -> WAITING ( or WAITING->WAITING)
            # Keep all the other attributes, tho!
            cursor.execute(
                UPDATE_VEHICLE_STATE + where_clause,
                (state_to_propagate.status,
                 state_to_propagate.position_x, state_to_propagate.position_y,
                 state_to_propagate.rotation,
                 state_to_propagate.speed_ms,
                 state_to_propagate.acceleration_m2s) + where_params,
            )
            # We assume that if there are no errors, the update was OK
            # If NO row is updated it means we are trying to update an ACTIVE (error) or CRASH (cornercase) state
            result = cursor.rowcount
            connection.commit()
        finally:
            # connection.rollback()
            connection.close()

    def update_driver_state_in_scenario(self, scenario, driver, state):
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
        connection = sqlite3.connect(self.database_name)
        try:
            connection.execute('PRAGMA foreign_keys = ON')
            cursor = connection.cursor()

            logger.info('Updating state at timestamp {} for driver {} in scenario {}'.format(state.timestamp,
                                                                                             driver.user_id,
                                                                                             scenario.scenario_id))
            # Enable Foreing Keys Support
            where_clause, where_params = create_where_statement_using_attributes(**{
                "scenario_id": scenario.scenario_id,
                "driver_id": driver.user_id,
                # Update the state with the given timestamp (unique for each driver/scenario)
                "timestamp": state.timestamp,
                # We can only update states that are PENDING or WAITING. We cannot update ACTIVE or CRASH states
                "status": "PENDING|WAITING"
            })

            # Since we express at least one state update, that status becomes PENDING -> WAITING ( or WAITING->WAITING)
            cursor.execute(
                UPDATE_VEHICLE_STATE + where_clause,
                ("WAITING", state.position_x, state.position_y, state.rotation, state.speed_ms,
                 state.acceleration_m2s) + where_params,
            )

            # If NO row is updated it means we are trying to update an ACTIVE (error) or CRASH (cornercase) state
            result = cursor.rowcount
            connection.commit()
        finally:
            # connection.rollback()
            connection.close()

        if result == 0:
            # Make sure the state was indeed actionable
            the_state = self._get_vehicle_state_by_attributes(**{
                "scenario_id": scenario.scenario_id,
                "driver_id": driver.user_id,
                "timestamp": state.timestamp
            })[0]

            # TODO CRASH or CRASHED?
            if the_state.status == "GOAL_REACHED" or the_state.status == "CRASHED":
                logger.info(
                    'State at timestamp {} for driver {} in scenario {} is already {}'.format(
                        state.timestamp, driver.user_id, scenario.scenario_id, the_state.status))
            else:
                logger.error(
                    'Cannot update state at timestamp {} for driver {} in '
                    'scenario {}.'.format(state.timestamp, driver.user_id,
                                          scenario.scenario_id))  # , the_state.status))
                raise sqlite3.IntegrityError("Cannot update vehicle state {}".format(state.vehicle_state_id))

        # This makes WAITING states into ACTIVE states at the same timestamp
        self._synchronize_scenario_states(scenario, state.timestamp)

        # This makes ACTIVE states into CRASHED at this time stamp - it stores into the DB at timestamp
        # Does not return an UPDATED version of the states
        state_of_vehicles_that_collided = self._vehicles_that_collided(scenario, state.timestamp)

        # This makes ACTIVE states into GOAL_REACHED at this time stamp - it stores into the DB at timestamp
        state_of_vehicles_that_reached_goal = self._vehicles_that_reached_goal(scenario, state.timestamp)

        # Plot all the graphics (MIGHT TAKE SOME TIME if many players!)
        # This also queries the DB to get the latest state
        self._render_scenario_state(scenario, state.timestamp)

        # At this point we need to "propagate" the state of GOAL_REACHED and CRASH states if any!
        # At timestamp t is stored already in the DB
        timestamp = state.timestamp + 1

        if timestamp <= scenario.duration:
            user_dao = UserDAO(self.app_config)
            for state_of_vehicle in state_of_vehicles_that_collided:
                # Select the Driver who is in the Propagable state
                driver_to_update = user_dao.get_user_by_user_id(state_of_vehicle.user_id)
                # Propagate its states
                self.propagate_state_for_driver_in_scenario(scenario, driver_to_update, state_of_vehicle)

            for state_of_vehicle in state_of_vehicles_that_reached_goal:
                # Select the Driver who is in the Propagable state
                driver_to_update = user_dao.get_user_by_user_id(state_of_vehicle.user_id)
                # Propagate its states
                self.propagate_state_for_driver_in_scenario(scenario, driver_to_update, state_of_vehicle)

        # At this point we should return whether the called shall skip the planned steps!
        return driver.user_id in [s.user_id for s in
                                  state_of_vehicles_that_reached_goal + state_of_vehicles_that_collided]

    def driver_crashed_at_timestamp_in_scenario(self, scenario, driver, vehicle_state_at_timestamp):
        """
        Set the status of all the vehicle states after timestamp (inclusive of timestamp)
        that belong to the driver in the scenario as CRASH and copy over all the attributes (beside timestamp!)

        :param scenario:
        :param driver:
        :param timestamp:
        :return:
        """
        try:
            connection = sqlite3.connect(self.database_name)
            connection.execute('PRAGMA foreign_keys = ON')
            cursor = connection.cursor()

            timestamp = vehicle_state_at_timestamp.timestamp

            logger.info('Driver {} Crashed at timestamp {} in scenario {}'.format(driver.user_id, timestamp,
                                                                                  scenario.scenario_id))
            timestamps = "|".join(
                str(t) for t in range(timestamp, scenario.duration + 1))  # Include the last timestamp at duration
            # Enable Foreing Keys Support
            where_clause, where_params = create_where_statement_using_attributes(**{
                "scenario_id": scenario.scenario_id,
                "driver_id": driver.user_id,
                # Update the state any of the given timestamps (unique for each driver/scenario)
                "timestamp": timestamps
            })

            # Since we express at least one state update, that status becomes PENDING -> WAITING
            cursor.execute(
                UPDATE_VEHICLE_STATE + where_clause,
                ("CRASH",
                 # The CRASHED state attributes, remains the same for all the crashed states
                 vehicle_state_at_timestamp.position_x,
                 vehicle_state_at_timestamp.position_y,
                 vehicle_state_at_timestamp.rotation,
                 vehicle_state_at_timestamp.speed_ms,
                 vehicle_state_at_timestamp.acceleration_m2s
                 ) + where_params,
            )

            # If NO row is updated it means that none of the mandatory conditions matched
            result = cursor.rowcount
            if result == 0:
                logger.error(
                    'Cannot set Crash state at timestamp {} for driver {} in scenario {}'.format(timestamp,
                                                                                                 driver.user_id,
                                                                                                 scenario.scenario_id))
                raise sqlite3.IntegrityError("Cannot update driver state {}".format(driver.user_id))

            connection.commit()
        finally:
            connection.close()

    def _render_scenario_state(self, scenario, timestamp):
        # Check if we need to render this timestamp

        # Get the stored states which include ACTIVE, GOAL_REACHED, and CRASHED
        vehicles_states_at_timestamp = self.get_vehicle_states_by_scenario_id_at_timestamp(scenario.scenario_id,
                                                                                           timestamp)
        # Check that all the states are NOT actionable
        if all(s.status == "ACTIVE" or s.status == "GOAL_REACHED" or s.status == "CRASHED" for s in
               vehicles_states_at_timestamp):
            # We can render the scenario at this timestamp (for all the drivers)
            logger.debug(
                "Rendering scenario state at timestamp {} for scenario {}".format(timestamp, scenario.scenario_id))
            # Generate a global view, including all the drivers
            generate_embeddable_html_snippet(self.images_folder, scenario, vehicles_states_at_timestamp)
            # Focus on each driver and render the state again
            for driver in scenario.drivers:
                # TODO I do not like this nesting of DAOs but cannot do anything about it now
                scenario_dao = MixedTrafficScenarioDAO(self.app_config)
                goal_region_as_rectangle = scenario_dao.get_goal_region_for_driver_in_scenario(driver, scenario)

                logger.debug("Rendering states at timestamp {} in scenario {} for driver {}".format(timestamp,
                                                                                                    scenario.scenario_id,
                                                                                                    driver.user_id))
                generate_embeddable_html_snippet(self.images_folder, scenario, vehicles_states_at_timestamp,
                                                 focus_on_driver=driver,
                                                 goal_region_as_rectangle=goal_region_as_rectangle)

    def _vehicles_that_collided(self, scenario, timestamp) -> List[VehicleState]:
        """
        Collision checking is possible only if ALL the vehicles submitted the trajectory

        :param scenario:
        :param timestamp:
        :return:
        """
        state_of_vehicles_that_collided = list()

        vehicles_states_at_timestamp = self.get_vehicle_states_by_scenario_id_at_timestamp(scenario.scenario_id,
                                                                                           timestamp)
        for driver_state in vehicles_states_at_timestamp:
            # If the state is PENDING, there's no data to use for checking whether the goal is reached.
            if driver_state.status == "PENDING":
                logger.info(
                    "Driver {} has NOT YET SENT ITS PLANNED STATES at timestamp {}. "
                    "We skip collision checking ".format(driver_state.user_id, timestamp))
                return state_of_vehicles_that_collided

        # At this point we can effectively check the collisions of ALL the vehicles, are return the one that collided

        crashed_drivers_with_states = self.collision_checker.check_for_collisions(scenario, timestamp)

        for driver, driver_state in crashed_drivers_with_states:
            logger.info("Driver {} has crashed at timestamp {} ".format(driver.user_id, timestamp))
            state_of_vehicles_that_collided.append(driver_state)
            try:
                # TODO We might update at once all the future states of this driver
                connection = sqlite3.connect(self.database_name)
                connection.execute('PRAGMA foreign_keys = ON')
                cursor = connection.cursor()
                where_clause, where_params = create_where_statement_using_attributes(**{
                    "driver_id": driver_state.user_id,
                    "scenario_id": scenario.scenario_id,
                    "timestamp": timestamp,
                })

                cursor.execute(
                    UPDATE_VEHICLE_STATE_STATUS + where_clause,
                    ("CRASHED",) + where_params,
                )
                result = cursor.rowcount
                if result != 1:
                    err_msg = 'Cannot set the state of driver as CRASHED at timestamp {} in scenario {}'.format(
                        timestamp, scenario.scenario_id)
                    logger.error(err_msg)
                    raise sqlite3.IntegrityError(err_msg)

                connection.commit()
            finally:
                connection.close()

        # Refresh the states from the DB
        refreshed_states = []
        for vehicle_state in state_of_vehicles_that_collided:
            refreshed_states.append(self.get_vehicle_state_by_vehicle_state_id(vehicle_state.vehicle_state_id))

        return refreshed_states

    def _vehicles_that_reached_goal(self, scenario, timestamp) -> List[VehicleState]:
        # TODO: Why not simply checking that the goal region and the rectangle of the car (or its center) collided?!

        # Update the database and mark as GOAL_REACHED the vehicle states that reached the goal in this step
        state_of_vehicles_that_reached_goal = list()

        vehicles_states_at_timestamp = self.get_vehicle_states_by_scenario_id_at_timestamp(scenario.scenario_id,
                                                                                           timestamp)
        # Skip the check if there are not enough data
        if any([driver_state.status == "PENDING" for driver_state in vehicles_states_at_timestamp]):
            logger.info("Pending states at timestamp {}. Skip goal checking ".format(timestamp))
            return state_of_vehicles_that_reached_goal

        scenario_dao = MixedTrafficScenarioDAO(self.app_config)

        initial_states = {}
        goal_region_as_rectangles = {}

        for driver in scenario.drivers:
            initial_states[driver.user_id] = scenario_dao.get_initial_state_for_driver_in_scenario(driver, scenario)
            goal_region_as_rectangles[driver.user_id] = scenario_dao.get_goal_region_for_driver_in_scenario(driver,
                                                                                                            scenario)

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
            if planning_problems_as_dictionary[driver_state.user_id].goal.is_reached(
                    driver_state.as_commonroad_state()):
                logger.info(
                    ">> Driver {} has reached its goal state at timestamp {} ".format(driver_state.user_id, timestamp))
                state_of_vehicles_that_reached_goal.append(driver_state)
                try:
                    # We do not update at once all the future states of this driver, because we need to possibly
                    # take into account the other drivers state !
                    connection = sqlite3.connect(self.database_name)
                    connection.execute('PRAGMA foreign_keys = ON')
                    cursor = connection.cursor()
                    where_clause, where_params = create_where_statement_using_attributes(**{
                        "driver_id": driver_state.user_id,
                        "scenario_id": scenario.scenario_id,
                        "timestamp": timestamp,
                    })

                    cursor.execute(
                        UPDATE_VEHICLE_STATE_STATUS + where_clause,
                        ("GOAL_REACHED",) + where_params,
                    )
                    result = cursor.rowcount
                    if result != 1:
                        err_msg = 'Cannot set the state of driver as GOAL_REACHED at timestamp {} in scenario {}'.format(
                            timestamp, scenario.scenario_id)
                        logger.error(err_msg)
                        raise sqlite3.IntegrityError(err_msg)

                    connection.commit()
                finally:
                    connection.close()
            else:
                logger.info(
                    "Driver {} has NOT reached its goal state at timestamp {} ".format(driver_state.user_id,
                                                                                       timestamp))

        # Refresh the states from the DB
        refreshed_states = []
        for vehicle_state in state_of_vehicles_that_reached_goal:
            refreshed_states.append(self.get_vehicle_state_by_vehicle_state_id(vehicle_state.vehicle_state_id))

        return refreshed_states

    def _synchronize_scenario_states(self, scenario, timestamp):
        #
        # At this point, we need to check whether all the drivers have provided an action for this timestamp
        # and update all the states at once, making all the WAITING states ACTIVE
        #
        try:
            connection = sqlite3.connect(self.database_name)
            connection.execute('PRAGMA foreign_keys = ON')
            cursor = connection.cursor()

            # Count how many states are WAITING for SCENARIO  at TIMESTAMP
            where_clause, where_params = create_where_statement_using_attributes(**{
                "scenario_id": scenario.scenario_id,
                "timestamp": timestamp,
                "status": "WAITING"
            })
            cursor.execute(COUNT_VEHICLE_STATES + where_clause, where_params)

            waiting_result = int(cursor.fetchone()[0])

            where_clause, where_params = create_where_statement_using_attributes(**{
                "scenario_id": scenario.scenario_id,
                "timestamp": timestamp,
                "status": "GOAL_REACHED|CRASHED"
            })
            cursor.execute(COUNT_VEHICLE_STATES + where_clause, where_params)
            goal_reached_and_crashed_result = int(cursor.fetchone()[0])

            # If all have sent their action, update all the scenario states at timestamp to be ACTIVE or CRASHED or GOAL_REACHED, but not WAITING
            if waiting_result + goal_reached_and_crashed_result == len(scenario.drivers):
                # Select all the states of the scenario at the given timestamp
                where_clause, where_params = create_where_statement_using_attributes(**{
                    "scenario_id": scenario.scenario_id,
                    "timestamp": timestamp,
                    # We can update to ACTIVE only the one in WAITING state, the other must remain GOAL_REACHED and CRASHED
                    "status": "WAITING"
                })
                # As first step activate all the vehicle states at this timestamp; later,
                # we check for collisions and goal reached
                cursor.execute(
                    UPDATE_VEHICLE_STATE_STATUS + where_clause,
                    ("ACTIVE",) + where_params,
                )
                result = cursor.rowcount
                if result != waiting_result:
                    logger.error(
                        'Got {} updates instead of {}'.format(result, waiting_result))
                    logger.error(
                        'Cannot activate states at timestamp {} in scenario {} for WAITING states'.format(timestamp,
                                                                                                          scenario.scenario_id))
                    raise sqlite3.IntegrityError(
                        'Cannot activate states at timestamp {} in scenario {}'.format(timestamp, scenario.scenario_id))
                else:
                    logger.info("******* Activating states at timestamp {} in scenario {} ******* ".format(timestamp,
                                                                                                           scenario.scenario_id))
            else:
                logger.info(
                    "******* Cannot activating states at timestamp {} in scenario {} MISSING {} ******* ".format(
                        timestamp,
                        scenario.scenario_id,
                        (len(scenario.drivers) - waiting_result - goal_reached_and_crashed_result)))
            connection.commit()
        finally:
            connection.close()

    def reset_state_for_driver_in_scenario_at_timestamp(self, driver, scenario, timestamp):
        # TODO: This can be done in bulk
        try:
            connection = sqlite3.connect(self.database_name)
            connection.execute('PRAGMA foreign_keys = ON')
            cursor = connection.cursor()

            logger.debug('Resetting state at timestamp {} for driver {} in scenario {}'.format(timestamp,
                                                                                               driver.user_id,
                                                                                               scenario.scenario_id))
            # Enable Foreing Keys Support
            where_clause, where_params = create_where_statement_using_attributes(**{
                "scenario_id": scenario.scenario_id,
                "driver_id": driver.user_id,
                # Update the state with the given timestamp (unique for each driver/scenario)
                "timestamp": timestamp,
                # We can only update states that are PENDING or WAITING. We cannot update ACTIVE or CRASH states
                "status": "PENDING|WAITING"
            })

            # Since we express at least one state update, that status becomes PENDING -> WAITING ( or WAITING->WAITING)
            position_x = None
            position_y = None
            rotation = None
            speed_ms = None
            acceleration_m2s = None
            status = "PENDING"
            # status = ?, position_x = ?,  position_y = ?, rotation = ?, speed_ms = ?, acceleration_m2s = ?"
            cursor.execute(
                UPDATE_VEHICLE_STATE + where_clause,
                (status, position_x, position_y, rotation, speed_ms, acceleration_m2s) + where_params,
            )

            # If NO row is updated it means we are trying to update an ACTIVE (error) or CRASH|GOAL_REACHED (cornercase) state
            result = cursor.rowcount
            connection.commit()
        finally:
            # connection.rollback()
            connection.close()

        if result == 0:
            # Make sure the state was indeed actionable
            the_state = self._get_vehicle_state_by_attributes(**{
                "scenario_id": scenario.scenario_id,
                "driver_id": driver.user_id,
                "timestamp": timestamp
            })[0]

            if the_state.status == "GOAL_REACHED" or the_state.status == "CRASH":
                logger.debug(
                    'State at timestamp {} for driver {} in scenario {} is already {}'.format(
                        timestamp, driver.user_id, scenario.scenario_id, the_state.status))
            else:
                error_msg = 'Cannot RESET state at timestamp {} for driver {} in ' \
                            'scenario {}.'.format(timestamp, driver.user_id,
                                                  scenario.scenario_id);
                logger.warning(error_msg);
                raise sqlite3.IntegrityError(error_msg)
