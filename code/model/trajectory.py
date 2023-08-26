import logging
logger = logging.getLogger('flexcrash.sub')

from typing import List

import numpy as np
from model.vehicle_state import VehicleState, VehicleStateSchema
from marshmallow import Schema, fields, post_load

import tempfile

from commonroad_route_planner.route_planner import RoutePlanner

from commonroad.scenario.lanelet import Lanelet

from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.scenario.trajectory import State
from commonroad.common.util import Interval
from commonroad.planning.goal import GoalRegion
from commonroad.planning.planning_problem import PlanningProblem

import math

class Trajectory():

    def __init__(self, the_t, the_v, the_d, planned_states):
        self.the_t = the_t
        self.the_v = the_v
        self.the_d = the_d

        self.planned_states = planned_states

    @staticmethod
    def from_trajectory_sample(trajectory_sample):
        planned_states = list()

        the_t = trajectory_sample.the_t
        the_v = trajectory_sample.the_v
        the_d = trajectory_sample.the_d

        # Iterate over the cartesian rep of the trajectory
        for i in range(len(trajectory_sample.cartesian.x)):
                # create Vehicle State
                vehicle_state_id = None
                status = None
                timestamp = None #starting_timestamp + i
                user_id = None
                scenario_id = None
                position_x, position_y = trajectory_sample.cartesian.x[i], trajectory_sample.cartesian.y[i]
                rotation = trajectory_sample.cartesian.theta[i]
                speed_ms = trajectory_sample.cartesian.v[i]
                acceleration_m2s = trajectory_sample.cartesian.a[i]
                yaw_rate = trajectory_sample.cartesian.kappa[i]
                # Not sure we should pass VehicleStates at this point...
                vehicle_state = VehicleState(vehicle_state_id, status, timestamp, user_id, scenario_id, position_x, position_y, rotation, speed_ms, acceleration_m2s)
                planned_states.append(vehicle_state)

        return Trajectory(the_t, the_v, the_d, planned_states)


class TrajectorySchema(Schema):
    the_t = fields.Integer(required=False)
    the_v = fields.Float(required=False)
    the_d = fields.Float(required=False)
    # TODO We can probably omit many info here and keep only position?
    planned_states = fields.List(fields.Nested(VehicleStateSchema()))

    @post_load
    def make_trajectory(self, data, **kwargs):
        return TrajectorySchema(**data)


class ConstantCostFunction(CostFunction):
    def evaluate(self, trajectory, parameters: []):
        return 1.0


# Controls how much time it takes to the car to achieve the final state.
# The logic is that after achieving the target state, it keeps that (if possible)
# This is somewhat arbitary, but do not go below 0.1
T_SEC_MIN = 0.3
# This cannot go over planning horizon otherwise the vehicle will be teleported
T_SEC_MAX = 1.9

# Controls how much the car is allowed to move laterally left/right
D_METER_MIN = -2.0
D_METER_MAX = +2.0

# 1 m/s = 3.6 km/h
V_METER_PER_SEC_MIN = 0.0
V_METER_PER_SEC_MAX = 25.0 # 25 m/s = 90 km/h

# Controls how many samples we generate between min/max over the three dimensions
SAMPLING_LEVEL = 2
DISABLE_FEASIBILITY = False

def extend_ref_path_by(ref_path, step, times):
    x = [p[0] for p in ref_path]
    y = [p[1] for p in ref_path]

    # TODO There is surely a better way
    # Starting at xe1,  ye1, extend it by X points at distance 1 following the direction defined by xs, ys and xe, ye
    # Take last two points
    xs1, ys1 = x[-2], y[-2]
    xe1, ye1 = x[-1], y[-1]

    if xe1 == xs1:
        # Direction:
        if ye1 > ys1:
            # up
            extension = np.array([[xe1, ye1 + i * step] for i in range(0, times+1)])
        else:
            # down - assuming y grews up
            extension = np.array([[xe1, ye1 - i * step] for i in range(0, times+1)])
        pass
    else:
        # Slope
        m1 = (ye1 - ys1) / (xe1 - xs1)
        # Direction:
        if xe1 > xs1:
            # right
            extension = np.array([[xe1 + i * step, ye1 + (i * step) * m1] for i in range(0, times+1)])
        else:
            # left
            extension = np.array([[xe1 - i * step, ye1 - (i * step) * m1] for i in range(0, times+1)])
    xext = x + [p[0] for p in extension]
    yext = y + [p[1] for p in extension]
    return np.array([[px, py] for px, py in zip(xext, yext)])


class TrajectorySampler():
    """
    Wraps and extends the closed-source samplers from TUM
    """

    def __init__(self):
        raise NotImplementedError("This code is not available.")

    def sample_trajectories(self, current_state,
                            t_sec_min=T_SEC_MIN, t_sec_max=T_SEC_MAX,
                            # Those are LEFT and RIGHT
                            d_meter_min = D_METER_MIN, d_meter_max = D_METER_MAX,
                            #
                            v_meter_per_sec_min=V_METER_PER_SEC_MIN, v_meter_per_sec_max=V_METER_PER_SEC_MAX) -> List[Trajectory]:

        raise NotImplementedError("This code is not available.")