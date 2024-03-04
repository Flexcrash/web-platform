from typing import Tuple, List, Optional

import sqlalchemy.exc
import traceback

from model.driver import Driver
from model.user import User
from model.mixed_traffic_scenario import MixedTrafficScenario

from commonroad.geometry.shape import Rectangle

from persistence.database import db
from persistence.utils import inject_where_statement_using_attributes

# TODO This helps with testing the unit, however, if this class is used ONLY by ScenarioDAO, we can merge those methods there!
class DriverDAO():

    def __init__(self, app_config):
        self.app_config = app_config

    def _get_unassigned_driver_in_scenario(self, scenario: MixedTrafficScenario) -> Optional[Driver]:
        stmt = db.select(Driver)
        kwargs = {
            Driver.user_id.name: None, # TODO Is this correct?
            Driver.scenario_id.name: scenario.scenario_id,
        }
        updated_stmt = inject_where_statement_using_attributes(stmt, Driver, **kwargs)

        # Execute the statement and return the first driver. first() returns a tuple, so we need the first element
        # In case the scenario does not exist, we should raise an exception
        try:
            driver = db.session.execute(updated_stmt).first()[0]
            # Concretize the list as we expect that later
            return driver
        except Exception as e:
            # TODO Add a warning?
            return None

    def get_waiting_driver(self, scenario: MixedTrafficScenario) -> Driver:
        """
        Return the next driver waiting to be initialized

        :param scenario:
        :return:
        """
        stmt = db.select(Driver)
        # Select the drivers in the scenarios without user_id
        kwargs = {
            Driver.user_id.name: None,  # TODO Is this correct?
            Driver.scenario_id.name: scenario.scenario_id,
            # Make sure to return a driver that is not yet initialized!
            Driver.goal_region.name: None,
            Driver.initial_position.name: None,
            Driver.initial_speed.name: None
        }
        updated_stmt = inject_where_statement_using_attributes(stmt, Driver, **kwargs)

        # Execute the statement and return the first driver. first() returns a tuple, so we need the first element
        # In case the scenario does not exist, we should raise an exception
        try:
            driver = db.session.execute(updated_stmt).first()[0]
            # Concretize the list as we expect that later
            return driver
        except Exception as e:
            # TODO Add a warning?
            return None

    def get_driver_by_driver_id(self, driver_id: int) -> Optional[Driver]:
        stmt = db.select(Driver)
        # Select the drivers in the scenarios without user_id
        kwargs = {
            Driver.driver_id.name: driver_id,
        }
        updated_stmt = inject_where_statement_using_attributes(stmt, Driver, **kwargs)

        # Execute the statement and return the first driver. first() returns a tuple, so we need the first element
        try:
            driver = db.session.execute(updated_stmt).first()[0]
            # Concretize the list as we expect that later
            return driver
        except Exception as e:
            return None

    def get_driver_by_user_id(self, scenario_id, user_id) -> Optional[Driver]:
        stmt = db.select(Driver)
        # Select the drivers in the scenarios without user_id
        kwargs = {
            Driver.user_id.name: user_id,
            Driver.scenario_id.name: scenario_id
        }
        updated_stmt = inject_where_statement_using_attributes(stmt, Driver, **kwargs)

        # Execute the statement and return the first driver. first() returns a tuple, so we need the first element
        try:
            driver = db.session.execute(updated_stmt).first()[0]
            # Concretize the list as we expect that later
            return driver
        except Exception as e:
            #
            return None

    def get_all_drivers(self, app_config, scenario_id=None) -> List[Driver]:
        # connection = sqlite3.connect(app_config["DATABASE_NAME"])
        # try:
        #     cursor = connection.cursor()
        #     if scenario_id is not None:
        #         where_clause, where_values = inject_where_statement_using_attributes()
        #         cursor.execute(
        #             "SELECT * from Driver" + where_clause, where_values
        #         )
        #     else:
        #         cursor.execute("SELECT * from Driver")
        #     return cursor.fetchall()
        # finally:
        #     connection.close()

        stmt = db.select(Driver)

        if scenario_id is not None:
            kwargs = {
                    "scenario_id": scenario_id
            }
            updated_stmt = inject_where_statement_using_attributes(stmt, Driver, **kwargs)
        else:
            updated_stmt = stmt

        # Execute the statement
        drivers = db.session.execute(updated_stmt)
        # db.session.commit()
        # Concretize the list as we expect that later
        return list(drivers.scalars())


    def force_initial_state_for_driver_in_scenario(self, driver, initial_state) -> None:
        stmt = db.select(Driver)
        kwargs = {
            Driver.driver_id.name: driver.driver_id
        }
        updated_stmt = inject_where_statement_using_attributes(stmt, Driver, **kwargs)
        # db.session.begin(nested=False)
        _driver: Driver
        # first() return a tuple
        _driver = db.session.execute(updated_stmt).first()[0]
        # Update the model
        _driver.initial_position = initial_state[0]
        _driver.initial_speed = initial_state[1]
        # Commit NECESSARY?
        db.session.commit()

    def force_goal_region_as_rectangle_for_driver_in_scenario(self, driver, goal_region_as_rectangle) -> None:
        stmt = db.select(Driver)
        kwargs = {
            Driver.driver_id.name : driver.driver_id
        }
        updated_stmt = inject_where_statement_using_attributes(stmt, Driver, **kwargs)
        # db.session.begin(nested=False)
        _driver : Driver
        # first() return a tuple
        _driver = db.session.execute(updated_stmt).first()[0]
        # Update the model
        _driver.goal_region = goal_region_as_rectangle
        # Commit NECESSARY?
        db.session.commit()

    def _is_user_already_driving_in_scenario(self, user: User, scenario: MixedTrafficScenario) -> bool:
        return self.get_driver_by_user_id(scenario.scenario_id, user.user_id) is not None


    def unassign_driver_from_user(self, scenario: MixedTrafficScenario, user: User):
        driver = self.get_driver_by_user_id(scenario.scenario_id, user.user_id)

        if driver is not None:
            # Update the ORM
            driver.user_id = None
            # TODO Should we check again here before commit?
            # Commit the changes
            db.session.commit()

    def assign_driver_to_user(self, scenario: MixedTrafficScenario, user: User) -> Driver:
        """
        Assign the first available driver in the scenario to the given user. Make sure that the same user is not already assigned to another driver in this scenario!

        :param driver:
        :param user:
        :param goal_region:
        :return:
        """

        # TODO Check if this is already inside a transaction!
        assert not self._is_user_already_driving_in_scenario(user, scenario), "user already in scenario"

        driver = self._get_unassigned_driver_in_scenario(scenario)

        # This might happen either if the scenario is full or does not exist. Both cases, should never happen in a regular execution
        assert driver is not None, "There are not more unsassigned drivers"
        # Update the ORM
        driver.user_id = user.user_id
        # TODO Should we check again here before commit?
        # Commit the changes
        db.session.commit()

        return driver

    def add_driver_to_scenario(self, scenario: MixedTrafficScenario):
        """
        Create a new driver and link it to the scenario
        :param scenario:
        :param goal_region:
        :return:
        """
        try:
            # Why does this complain that a transaction is running when none is? Maybe the Rectangle thingy?
            # db.session.begin(nested=False)
            driver = Driver(scenario_id=scenario.scenario_id)
            db.session.add(driver)
            # TODO Not sure about this...
            db.session.commit()
            return driver
        except sqlalchemy.exc.IntegrityError as err:
            db.session.rollback()
            # print(traceback.format_exc())
            raise err

    def get_drivers_goal_region_from_scenario(self, driver: Driver, scenario: MixedTrafficScenario, nested=False) -> Optional[Rectangle]:
        try:
            stmt = db.select(Driver.goal_region)
            kwargs = {
                "user_id": driver.user_id,
                "scenario_id": scenario.scenario_id
            }
            updated_stmt = inject_where_statement_using_attributes(stmt, Driver, **kwargs)
            # TODO No results Exception?
            # db.session.begin(nested=nested) -> Why an existing transaction is running at this point?
            return db.session.execute(updated_stmt).scalar_one()
        except sqlalchemy.exc.IntegrityError as err:
            db.session.rollback()
            print(traceback.format_exc())

            return None

