import numpy as np
import enum

from sqlalchemy import Enum

from commonroad.scenario.trajectory import State

from model.driver import Driver
from model.user import User
from model.mixed_traffic_scenario import MixedTrafficScenario

from persistence.database import db


class VehicleStatusEnum(str, enum.Enum):
    """ Represent the possible status of a vehicle state as Enumeration """
    # Since we serialize the enum into JSON, we can make it inherit from str to avoid exceptions
    # https://stackoverflow.com/questions/70738783/json-serialize-python-enum-object
    PENDING = "PENDING" # JUST INITIALIZED, NOTHING SUBMITTED SO FAR
    WAITING = "WAITING" # SUBMITTED BUT STILL CAN BE CHANGED
    ACTIVE = "ACTIVE" # SUBMITTED AND CANNOT BE CHANGED (NOMINAL CASE)
    CRASHED = "CRASHED"  # SUBMITTED AND CANNOT BE CHANGED (CRASH CASE - AUTOMATICALLY ENFORCED)
    GOAL_REACHED = "GOAL_REACHED" # SUBMITTED AND CANNOT BE CHANGED (END CASE - AUTOMATICALLY ENFORCED)


class VehicleState(db.Model):
    """
    A Vehicle state is an immutable object that represents the "physical" state of a vehicle in a simulator.
    TODO Check Common RoadStates
    """
    class Object:
        """ Internal Object class. To avoid messing around with other object classes """
        pass

    __tablename__ = 'Vehicle_State'

    vehicle_state_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # https://stackoverflow.com/questions/2676133/best-way-to-do-enum-in-sqlalchemy
    status = db.Column(Enum(VehicleStatusEnum))
    timestamp = db.Column(db.Integer, nullable=False, unique=False)

    # Why is this necessary?
    driver_id = db.Column(db.Integer,  db.ForeignKey(Driver.driver_id, ondelete="CASCADE", onupdate="CASCADE"), primary_key=False, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey(User.user_id, ondelete="CASCADE", onupdate="CASCADE"), primary_key=False, nullable=False)
    scenario_id = db.Column(db.Integer, db.ForeignKey(MixedTrafficScenario.scenario_id, ondelete="CASCADE", onupdate="CASCADE"), primary_key=False, nullable=False)
    # To apply table-level constraint objects such as ForeignKeyConstraint to a table defined using Declarative,
    # use the __table_args__ attribute, described at Table Configuration.
    # __table_args__ = (
    #     # onupdate="CASCADE", ondelete="CASCADE"?
    #     db.ForeignKeyConstraint(["user_id", "scenario_id"], [Driver.user_id, Driver.scenario_id], ondelete="CASCADE", onupdate="CASCADE"), # Note this must be tuple!
    # )
    position_x = db.Column(db.Float, nullable=True, unique=False)
    position_y = db.Column(db.Float, nullable=True, unique=False)
    rotation = db.Column(db.Float, nullable=True, unique=False)
    speed_ms = db.Column(db.Float, nullable=True, unique=False)
    acceleration_m2s = db.Column(db.Float, nullable=True, unique=False)

    # This is not backed up by a "single" ForeignKey?
    # driver = db.relationship("User", back_populates="driver", uselist="False")
    # TODO Add backref to Scenario

    def as_commonroad_state(self):
        """
        :return: a copy of this object as an object compatible with CommonRoad basic State object
        Note: STATE is only available in Commonroad 2022.2 !
        """
        return State(**{
            "time_step": self.timestamp,
            "position": np.array([self.position_x, self.position_y]),
            "orientation": self.rotation,
            "velocity": self.speed_ms,
            "acceleration": self.acceleration_m2s,
            "yaw_rate": 0,
            "slip_angle": 0
        })

    def as_plain_state(self):
        """
        Returns a "serializable" version of this object to be passed to the background image rendering process
        :return: a copy of this object as an object compatible with CommonRoad basic state
        """
        plain_state = VehicleState.Object()
        setattr(plain_state, "timestamp", self.timestamp)
        setattr(plain_state, "position_x", self.position_x)
        setattr(plain_state, "position_y", self.position_y)
        setattr(plain_state, "rotation", self.rotation)
        setattr(plain_state, "speed_ms", self.speed_ms)
        setattr(plain_state, "acceleration_m2s", self.acceleration_m2s)
        setattr(plain_state, "user_id", self.user_id)
        setattr(plain_state, "driver_id", self.driver_id)
        setattr(plain_state, "scenario_id", self.scenario_id)
        setattr(plain_state, "status", self.status)

        return plain_state