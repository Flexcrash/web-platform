import numpy as np
from marshmallow import Schema, fields, post_load

from commonroad.scenario.trajectory import State

class VehicleState:
    """
    A Vehicle state is an immutable object that represents the "physical" state of a vehicle in a simulator.
    TODO Check Common RoadStates
    """

    def __init__(self, vehicle_state_id, status, timestamp, user_id, scenario_id, position_x, position_y, rotation, speed_ms, acceleration_m2s):
        self.vehicle_state_id = vehicle_state_id
        self.status = status
        self.timestamp = timestamp
        # Should this be driver_id ?
        self.user_id = user_id
        self.scenario_id = scenario_id
        self.position_x = position_x
        self.position_y = position_y
        self.rotation = rotation
        self.speed_ms= speed_ms
        self.acceleration_m2s= acceleration_m2s

    def as_commonroad_state(self):
        return State(**{
            "time_step": self.timestamp,
            "position": np.array([self.position_x, self.position_y]),
            "orientation": self.rotation,
            "velocity": self.speed_ms,
            "acceleration": self.acceleration_m2s,
            "yaw_rate": 0,
            "slip_angle": 0
        })


class VehicleStateSchema(Schema):
    """ This class is used to serialize/validate Python objects using Marshmallow """
    vehicle_state_id = fields.Integer(required=False)
    status = fields.String(required=True)
    timestamp = fields.Integer(required=True)
    user_id = fields.Integer(required=True)
    scenario_id = fields.Integer(required=True)
    # Those are optional because might not be available since beginning
    position_x = fields.Float(required=False, allow_none=True)
    position_y = fields.Float(required=False, allow_none=True)
    rotation = fields.Float(required=False, allow_none=True)
    speed_ms = fields.Float(required=False, allow_none=True)
    acceleration_m2s = fields.Float(required=False, allow_none=True)

    @post_load
    # TODO Prob we need to rename this method
    def make_user(self, data, **kwargs):
        return VehicleState(**data)
