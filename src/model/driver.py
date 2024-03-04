# This class represent a User driving in a Scenario. We need it to streamline ORM
from model.user import User
from model.mixed_traffic_scenario import MixedTrafficScenario
from persistence.custom_types import RectangleType, PositionType
from persistence.database import db


# CREATE_DRIVER_TABLE = """ CREATE TABLE Driver(
#                 user_id INTEGER,
#                 scenario_id INTEGER,
#                 goal_region Rectangle,
#
#                 PRIMARY KEY (user_id, scenario_id),
#
#                 CONSTRAINT fk_user_id
#                     FOREIGN KEY (user_id)
#                     REFERENCES User (user_id)
#                     ON UPDATE CASCADE
#                     ON DELETE CASCADE
#
#                 CONSTRAINT fk_scenario_id
#                     FOREIGN KEY (scenario_id)
#                     REFERENCES Mixed_Traffic_Scenario (scenario_id)
#                     ON UPDATE CASCADE
#                     ON DELETE CASCADE
#                 );
#             """
class Driver(db.Model):

    __tablename__ = 'Driver'

    # This enables to create drivers without associating any user to them
    driver_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # This could be null waiting for the users to join
    user_id = db.Column(db.Integer, db.ForeignKey(User.user_id, ondelete="CASCADE", onupdate="CASCADE"), primary_key=False, nullable=True)
    # This could not be null, because there are no drivers without a scenario
    scenario_id = db.Column(db.Integer, db.ForeignKey(MixedTrafficScenario.scenario_id, ondelete="CASCADE", onupdate="CASCADE"), primary_key=False, nullable=False)

    # Not sure how to call this part of the relation
    user = db.relationship('User', back_populates='drives', uselist=False)
    # Represents the scenarios in which drivers drive
    scenario = db.relationship('MixedTrafficScenario', back_populates='drivers', uselist=False)

    # Note this is not the GOAL region, but only the position of its center.
    goal_region = db.Column(RectangleType, nullable=True)
    initial_position = db.Column(PositionType, nullable=True)
    initial_speed = db.Column(db.Float, nullable=True)


