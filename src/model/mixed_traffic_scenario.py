import enum
from sqlalchemy import Enum

from model.user import User
from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate

from commonroad.scenario.trajectory import Trajectory, State

from commonroad.planning.goal import GoalRegion
from commonroad.planning.planning_problem import PlanningProblem

from commonroad.common.util import Interval

# The global reference to the database
from persistence.database import db
# Make sure we can combine db-stored attributes with transient ones
# See: https://docs.sqlalchemy.org/en/13/orm/constructors.html


class MixedTrafficScenarioStatusEnum(str, enum.Enum):
    """ Represent the possible status of a Mixed Traffic Scenario as Enumeration """
    # Since we serialize the enum into JSON, we can make it inherit from str to avoid exceptions
    # https://stackoverflow.com/questions/70738783/json-serialize-python-enum-object
    PENDING = "PENDING"
    WAITING = "WAITING"
    ACTIVE = "ACTIVE"
    DONE = "DONE"


class MixedTrafficScenario(db.Model):

    __tablename__ = 'Mixed_Traffic_Scenario'

    scenario_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # TODO Is this really Nullable?
    name = db.Column(db.String(250), nullable=False)
    description = db.Column(db.String(250), nullable=True)

    # TODO Rename to owner_id - THIS IS MISSING IN THE SERIALIZED VERSION
    created_by = db.Column(db.Integer, db.ForeignKey(User.user_id, ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    # TODO - THIS IS MISSING IN THE SERIALIZED VERSION - A link maybe?
    owner = db.relationship('User', back_populates='owns', uselist=False)

    max_players = db.Column(db.Integer, nullable=False)
    n_users = db.Column(db.Integer, nullable=False)
    n_avs = db.Column(db.Integer, nullable=False)

    status = db.Column(Enum(MixedTrafficScenarioStatusEnum), nullable=False)

    # TODO - THIS IS MISSING IN THE SERIALIZED VERSION
    template_id = db.Column(db.Integer, db.ForeignKey(MixedTrafficScenarioTemplate.template_id, ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    # TODO - THIS IS MISSING IN THE SERIALIZED VERSION
    scenario_template = db.relationship("MixedTrafficScenarioTemplate", back_populates="define", uselist=False)

    duration = db.Column(db.Integer, nullable=False)

    # uselist=False means one-to-one
    # https://stackoverflow.com/questions/51246354/how-can-a-check-on-foreign-key-be-enforced-before-insert-a-new-value-in-flask-sq
    # Many-to-many: Read https://medium.com/@warrenzhang17/many-to-many-relationships-in-sqlalchemy-ba08f8e9ccf7#:~:text=SQLAlchemy%2C%20known%20to%20be%20a,of%20another%2C%20and%20vice%20versa.

    # Represents the drivers in a scenario
    # TODO - THIS IS MISSING IN THE SERIALIZED VERSION
    drivers = db.relationship('Driver', back_populates='scenario', uselist=True, lazy=True)

    def __eq__(self, other):
        if not isinstance(other, MixedTrafficScenario):
            # Trivially False
            return False

        # TODO What about the Status?
        return self.scenario_id == other.scenario_id and self.name == other.name and \
               self.description == other.description and \
               self.created_by == other.created_by and \
               self.max_players == other.max_players and self.status == other.status and \
               self.template_id == other.template_id and \
               self.duration == other.duration and \
               all(d1 == d2 for d1, d2 in zip(self.drivers, other.drivers))

    # TODO Ugly patch to allow passing the initial and goal area for the drivers
    def as_commonroad_scenario_and_planning_problems(self, initial_states= {}, goal_region_as_rectangles = {} ):
        # Create a CommonRoad scenario out of the static template
        commonroad_scenario = self.scenario_template.as_commonroad_scenario()

        # TODO Add the planning problems here for each driver
        planning_problems = {}
        for driver in self.drivers:
            # TODO Refactor to get it directly from the driver object. Driver objects are not used ATM
            commonroad_initial_state = initial_states[driver.driver_id].as_commonroad_state()
            goal_region_as_rectangle = goal_region_as_rectangles[driver.driver_id]
            goal_state_list = [
                State(position=goal_region_as_rectangle, time_step=Interval(0, self.duration))]
            commonroad_goal_region = GoalRegion(goal_state_list)
            # Use the User id as planning problem
            # NOTE: This will not work if the same user id is associated to multiple AVs in the same scenario!
            planning_problems[driver.driver_id] = PlanningProblem(driver.driver_id, commonroad_initial_state, commonroad_goal_region)

        return commonroad_scenario, planning_problems