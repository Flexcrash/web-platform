import logging
logger = logging.getLogger('flexcrash.sub')

from typing import List

import numpy as np
from model.vehicle_state import VehicleState
from api.serialization import VehicleStateSchema
from marshmallow import Schema, fields, post_load

from commonroad_rp.parameter import TimeSampling, PositionSampling, VelocitySampling, VehModelParameters
from commonroad_rp.polynomial_trajectory import QuinticTrajectory, QuarticTrajectory
from commonroad_rp.trajectories import TrajectoryBundle, TrajectorySample, CartesianSample, CurviLinearSample
from commonroad_rp.cost_function import CostFunction
from commonroad_rp.utils import CoordinateSystem, interpolate_angle
from commonroad_route_planner.route_planner import RoutePlanner

from commonroad.scenario.trajectory import State
from commonroad.common.util import Interval
from commonroad.planning.goal import GoalRegion
from commonroad.planning.planning_problem import PlanningProblem

import math

_LOW_VEL_MODE = False

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
                #
                # cart_states['time_step'] = self.x_0.time_step + self._factor * i

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
                vehicle_state = VehicleState(
                    vehicle_state_id=vehicle_state_id,
                    status=status,
                    timestamp=timestamp,
                    user_id=user_id,
                    scenario_id=scenario_id,
                    position_x=position_x,
                    position_y=position_y,
                    rotation=rotation,
                    speed_ms=speed_ms,
                    acceleration_m2s=acceleration_m2s
                )
                planned_states.append(vehicle_state)

        return Trajectory(the_t, the_v, the_d, planned_states)

# TODO Move this to serialization.serialization when Trajectory becomes an ORM
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
T_SEC_MIN = 0.1
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
    """ Wraps and extends the closed-source samplers from TUM """
    # TODO This could probably be a static method or something... I do not think it will be reused ever

    def __init__(self, mixed_traffic_scenario, initial_state: State, goal_region_as_rectangle, snap_to_road: bool, N: int = 20):

        # TODO Sampling T control how long it takes the vehicle to move to a distance d at the given speed
        # TODO So t = 0 means that it will shift to the left/right
        # TODO So t = 1.0 means that it will take one second to shift to the left/right
        # Note when d = 0 it should not matter... but I suspect that the points will be moved infront!
        # We can probably constraint how much left/right in how much time
        self._sampling_t = None
        self.sampled_t = None

        self._sampling_d = None
        self.sampled_d = None
        self.snap_to_road = snap_to_road

        self._sampling_v = None
        self.sampled_v = None

        self.constraints = VehModelParameters()

        self.commonroad_scenario = mixed_traffic_scenario.scenario_template.as_commonroad_scenario()

        self.dT = 0.1 # TODO Where is this defined?

        self.n_samples = 5 # Fixed for the moment

        self.N = N #20 # Max length of trajectory
        self.horizon = self.dT * self.N

        # Compute the reference path from the given initial state. This can be the current state.

        commonroad_initial_state = State(**{
            "time_step": initial_state.timestamp,
            "position": np.array([initial_state.position_x, initial_state.position_y]),
            "velocity": initial_state.speed_ms,
            "orientation": initial_state.rotation,
            "yaw_rate": 0,
            "slip_angle": 0
        })

        goal_state_list = [
            State(position=goal_region_as_rectangle, time_step=Interval(initial_state.timestamp,
                                                                        mixed_traffic_scenario.duration))]

        commonroad_goal_region = GoalRegion(goal_state_list)
        self.commonroad_planning_problem = PlanningProblem(mixed_traffic_scenario.scenario_id,
                                                           commonroad_initial_state,
                                                           commonroad_goal_region)
        if self.snap_to_road:
            # The trajectories will try to follow the road
            # Configure the Route Planner
            # initialize route planner
            # TODO Here we use the altered = self.commonroad_scenario
            route_planner = RoutePlanner(self.commonroad_scenario, self.commonroad_planning_problem)
            # TODO No idea what's this... This is to avoid that the planner stars on a multiple lanelet situation
            assert len(route_planner.id_lanelets_start) == 1
            initial_id = route_planner.id_lanelets_start[0]
            initial_lanelet = route_planner.scenario.lanelet_network.find_lanelet_by_id(initial_id)

            # TODO Sometimes this is broken?
            # get reference path
            follow_initial_lanelet = True
            if follow_initial_lanelet is True and len(self.commonroad_scenario.lanelet_network.intersections) == 0:
                # follow initial lanelet
                self._ref_path = initial_lanelet.center_vertices
            else:
                # custom reference path
                self._ref_path = route_planner.plan_routes().retrieve_first_route().reference_path


            step, times = 0.1, 400
            # In some cases the ref path is too short, so we need to extend it to ensure that trajectories can be computed
            # Ideally we should follow the curvature... but for the moment just interpolate the last 2 points or somethign

            # TODO CHECK THIS ONE !!!
            self._ref_path = extend_ref_path_by(self._ref_path, step, times)

        else:
            # The trajectories will be computed from the current vehicles rotation
            # Create a linear ref path from the current state x_0
            xs = [commonroad_initial_state.position[0] + distance * math.cos(commonroad_initial_state.orientation) for distance in range(-20, 100, 5)]
            ys = [commonroad_initial_state.position[1] + distance * math.sin(commonroad_initial_state.orientation) for distance in range(-20, 100, 5)]
            linear_reference_path = np.array([[px, py] for px, py in zip(xs, ys)])
            self._ref_path = linear_reference_path

        # The ref path is nothing more than a sequence of points
        self._co: CoordinateSystem = CoordinateSystem(self._ref_path)

    def get_reference_path(self):
        return self._ref_path

    def get_sampled_t(self):
        return self.sampled_t

    def get_sampled_v(self):
        return self.sampled_v

    def get_sampled_d(self):
        return self.sampled_d

    def _generate_feasible_trajectories(self, x_0_lon, x_0_lat, samp_level):
        """
        Code Taken from the Reactive Planner from TUM

        Plans trajectory samples that try to reach a certain velocity and samples in this domain.
        Sample in time (duration) and velocity domain. Initial state is given. Longitudinal end state (s) is sampled.
        Lateral end state (d) is always set to 0

        :param x_0_lon: np.array([s, s_dot, s_ddot])
        :param x_0_lat: np.array([d, d_dot, d_ddot])

        :param samp_level: index of the sampling parameter set to use

        :return: trajectory bundle with all sample trajectories.

        NOTE: Here, no collision or feasibility check is done!
        """

        # Set the sampled intervals here
        self.sampled_t = sorted(list(self._sampling_t.to_range(samp_level)))
        self.sampled_v = sorted(list(self._sampling_v.to_range(samp_level)))

        # TODO Why is it necessary to include the current state lat value? as an alternative to 0?
        # if self.snap_to_road:
        #     # I suspect that with d=0 we need to use the x_0_lat[0] trick...
        #     self.sampled_d = sorted(list(self._sampling_d.to_range(samp_level).union({x_0_lat[0]})))
        # else:

        # Otherwise, we can simply go with it?
        self.sampled_d = sorted(list(self._sampling_d.to_range(samp_level)))

        trajectories = list()
        for v in self.sampled_v:

            # Longitudinal sampling for all possible velocities
            for t in self.sampled_t:

                # end_state_lon = np.array([t * v + x_0_lon[0], v, 0.0])
                # trajectory_long = QuinticTrajectory(tau_0=0, delta_tau=t, x_0=np.array(x_0_lon), x_d=end_state_lon)
                trajectory_long = QuarticTrajectory(tau_0=0, delta_tau=t, x_0=np.array(x_0_lon), x_d=np.array([v, 0]))

                # Sample lateral end states (add x_0_lat to sampled states)
                if trajectory_long.coeffs is not None:
                    # AHHHHH ! This one is different?! Sampling + UNION ?
                    for d in self.sampled_d:
                        end_state_lat = np.array([d, 0.0, 0.0])

                        # TODO No idea what's this!
                        # SWITCHING TO POSITION DOMAIN FOR LATERAL TRAJECTORY PLANNING
                        if _LOW_VEL_MODE:
                            s_lon_goal = trajectory_long.evaluate_state_at_tau(t)[0] - x_0_lon[0]
                            if s_lon_goal <= 0:
                                s_lon_goal = t
                            trajectory_lat = QuinticTrajectory(tau_0=0, delta_tau=s_lon_goal, x_0=np.array(x_0_lat),
                                                               x_d=end_state_lat)

                        # Switch to sampling over t for high velocities
                        else:
                            trajectory_lat = QuinticTrajectory(tau_0=0, delta_tau=t, x_0=np.array(x_0_lat),
                                                               x_d=end_state_lat)
                        if trajectory_lat.coeffs is not None:
                            # We do not have any cost parameter
                            trajectory_sample = TrajectorySample(self.horizon, self.dT, trajectory_long, trajectory_lat, [])

                            # TODO Dirty trick!
                            setattr(trajectory_sample, "the_v", v)
                            setattr(trajectory_sample, "the_t", t)
                            setattr(trajectory_sample, "the_d", d)

                            trajectories.append(trajectory_sample)

        # perform pre-check and order trajectories according their cost
        trajectory_bundle = TrajectoryBundle(trajectories, cost_function=ConstantCostFunction())
        total_count = len(trajectory_bundle._trajectory_bundle)
        logger.debug('{} trajectories sampled'.format(total_count))

        # This transform the trajectory object into a sequence of states -
        # TODO ACCEPT ALL OF THEM FOR THE MOMENT WE NEED TO LET THE USER DO WHATEVER THEY WANT
        #
        feasible_trajectories, non_feasible_trajectories, infeasibility_reasons = self.check_kinematics(trajectory_bundle, accept_all=DISABLE_FEASIBILITY)

        total_count = len(feasible_trajectories)
        logger.debug('{} feasible trajectories'.format(total_count))

        return feasible_trajectories, non_feasible_trajectories, infeasibility_reasons

    def check_kinematics(self, trajectory_bundle: TrajectoryBundle, accept_all=False):
        """
        Checks the kinematics of given trajectories in a bundle and computes the cartesian trajectory information
        Faster function: Lazy evaluation, only kinematically feasible trajectories are evaluated

        :param trajectory_bundle: The trajectory bundle to check
        :return: The list of trajectories which are kinematically feasible
        """
        feasible_trajectories = list()
        infeasible_trajectories = list()
        infeasibility_reasons = list()

        for tr_index, trajectory in enumerate(trajectory_bundle.trajectories):

            feasible = True

            try:
                # create time array and precompute time interval information
                t = np.arange(0, np.round(trajectory.trajectory_long.delta_tau + self.dT, 5), self.dT)
                t2 = np.square(t)
                t3 = t2 * t
                t4 = np.square(t2)
                t5 = t4 * t

                # Why do we care about the 4th power of time? space, velocity, acceralation, jerk, ??

                # compute position, velocity, acceleration from trajectory sample
                s = trajectory.trajectory_long.calc_position(t, t2, t3, t4, t5)  # lon pos
                # Speed goes down, why?
                s_velocity = trajectory.trajectory_long.calc_velocity(t, t2, t3, t4)  # lon velocity
                # Acceleration is not constant... why? The methods are not explained...
                s_acceleration = trajectory.trajectory_long.calc_acceleration(t, t2, t3)  # lon acceleration

                # At low speeds, we have to sample the lateral motion over the travelled distance rather than time.
                if not _LOW_VEL_MODE:
                    d = trajectory.trajectory_lat.calc_position(t, t2, t3, t4, t5)  # lat pos
                    d_velocity = trajectory.trajectory_lat.calc_velocity(t, t2, t3, t4)  # lat velocity
                    d_acceleration = trajectory.trajectory_lat.calc_acceleration(t, t2, t3)  # lat acceleration

                else:
                    # compute normalized travelled distance for low velocity mode of lateral planning
                    s1 = s - s[0]
                    s2 = np.square(s1)
                    s3 = s2 * s1
                    s4 = np.square(s2)
                    s5 = s4 * s1

                    d = trajectory.trajectory_lat.calc_position(s1, s2, s3, s4, s5)  # lat pos
                    # in LOW_VEL_MODE d_velocity is actually d' (see Diss. Moritz Werling  p.124)
                    d_velocity = trajectory.trajectory_lat.calc_velocity(s1, s2, s3, s4)  # lat velocity
                    d_acceleration = trajectory.trajectory_lat.calc_acceleration(s1, s2, s3)  # lat acceleration

                # Compute cartesian information of trajectory
                s_length = len(s)
                x = np.zeros(s_length)
                y = np.zeros(s_length)
                theta_gl = np.zeros(s_length)
                theta_cl = np.zeros(s_length)
                v = np.zeros(s_length)
                a = np.zeros(s_length)
                kappa_gl = np.zeros(s_length)
                kappa_cl = np.zeros(s_length)

                oopd = False # Out of Projection Domain

                for i in range(0, s_length):
                    # compute Global position from the coordinate system defined by the reference path. Not sure what is s and d, maybe longitudinal and lateral/latitudinal positions?
                    pos: np.ndarray = self._co.convert_to_cartesian_coords(s[i], d[i])

                    if pos is not None:
                        x[i] = pos[0]
                        y[i] = pos[1]
                    else:
                        feasible = False
                        oopd = True
                        # TODO What's this? When this triggers we cannot generate the Cartesian Trajectory
                        # This happens when the ref path is shorter than the plannable trajectory
                        logger.info("Out of projection domain")
                        break

                    # compute orientations - what dp is supposed to be?
                    if not _LOW_VEL_MODE:
                        if s_velocity[i] > 0.001:
                            dp = d_velocity[i] / s_velocity[i]
                        else:
                            if d_velocity[i] > 0.001:
                                dp = None
                            else:
                                dp = 0.
                        ddot = d_acceleration[i] - dp * s_acceleration[i]
                        # What dpp is supposed to be?
                        if s_velocity[i] > 0.001:
                            dpp = ddot / (s_velocity[i] ** 2)
                        else:
                            if np.abs(ddot) > 0.00003:
                                # TODO When this happens everything crashes.
                                # THIS CONDITION IS TRIGGERED BY SOME SPECIFIC INITIAL STATE, WHICH IS RANDOM AT THE MOMENT
                                dpp = None
                            else:
                                dpp = 0.
                    else:
                        dp = d_velocity[i]
                        dpp = d_acceleration[i]

                    # At this point dpp might not have been initialized?

                    s_idx = np.argmin(np.abs(self._co.ref_pos() - s[i]))
                    if self._co.ref_pos()[s_idx] < s[i]:
                        s_idx += 1

                    if s_idx + 1 >= len(self._co.ref_pos()):
                        feasible = False
                        break

                    s_lambda = (self._co.ref_pos()[s_idx] - s[i]) / (
                            self._co.ref_pos()[s_idx + 1] - self._co.ref_pos()[s_idx])

                    # add cl and gl orientation
                    if s_velocity[i] > 0.005:
                        if _LOW_VEL_MODE:
                            theta_cl[i] = np.arctan2(dp, 1.0)
                        else:
                            theta_cl[i] = np.arctan2(d_velocity[i], s_velocity[i])
                        theta_gl[i] = theta_cl[i] + interpolate_angle(
                            s[i],
                            self._co.ref_pos()[s_idx],
                            self._co.ref_pos()[s_idx + 1],
                            self._co.ref_theta()[s_idx],
                            self._co.ref_theta()[s_idx + 1]
                        )
                        if theta_gl[i] < -np.pi:
                            theta_gl[i] += 2 * np.pi
                        if theta_gl[i] > np.pi:
                            theta_gl[i] -= 2 * np.pi
                        # theta_gl[i] = theta_cl[i] + (
                        #         self._co.ref_theta()[s_idx + 1] - self._co.ref_theta()[s_idx]) * s_lambda + \
                        #               self._co.ref_theta()[s_idx]

                    else:
                        # theta_cl.append(np.interp(s[i], self._co.ref_pos(), self._co.ref_theta()))
                        # theta_cl[i] = (self._co.ref_theta()[s_idx + 1] - self._co.ref_theta()[s_idx]) * s_lambda + \
                        #               self._co.ref_theta()[s_idx]
                        theta_cl[i] = interpolate_angle(
                            s[i],
                            self._co.ref_pos()[s_idx],
                            self._co.ref_pos()[s_idx + 1],
                            self._co.ref_theta()[s_idx],
                            self._co.ref_theta()[s_idx + 1]
                        )
                        if theta_cl[i] < -np.pi:
                            theta_cl[i] += 2 * np.pi
                        if theta_cl[i] > np.pi:
                            theta_cl[i] -= 2 * np.pi
                        theta_gl[i] = theta_cl[i]

                    # Compute curvature of reference at current position
                    k_r = (self._co.ref_curv()[s_idx + 1] - self._co.ref_curv()[s_idx]) * s_lambda + \
                          self._co.ref_curv()[
                              s_idx]
                    k_r_d = (self._co.ref_curv_d()[s_idx + 1] - self._co.ref_curv_d()[s_idx]) * s_lambda + \
                            self._co.ref_curv_d()[s_idx]

                    # compute global curvature based on appendix A of Moritz Werling's PhD thesis ... well sadly this is written in German!
                    # TODO What happens if dpp is None?
                    oneKrD = (1 - k_r * d[i])
                    cosTheta = np.cos(theta_cl[i])
                    tanTheta = np.tan(theta_cl[i])
                    kappa_gl[i] = (dpp + k_r * dp * tanTheta) * cosTheta * (cosTheta / oneKrD) ** 2 + (
                            cosTheta / oneKrD) * k_r
                    kappa_cl[i] = kappa_gl[i] - k_r

                    # velocity
                    v[i] = s_velocity[i] * (oneKrD / (np.cos(theta_cl[i])))

                    # compute acceleration
                    a[i] = s_acceleration[i] * oneKrD / cosTheta + ((s_velocity[i] ** 2) / cosTheta) * (
                            oneKrD * tanTheta * (kappa_gl[i] * oneKrD / cosTheta - k_r) - (
                            k_r_d * d[i] + k_r * d_velocity[i]))

                    # check kinematics to already discard infeasible trajectories
                    infeasibility_reason = None
                    if abs(kappa_gl[i] > self.constraints.kappa_max):
                        infeasibility_reason = f"Rejected trajectory for Kappa {kappa_gl[i]} at step {i}"
                        feasible = False
                        break
                    if abs((kappa_gl[i] - kappa_gl[i - 1]) / self.dT if i > 0 else 0.) > self.constraints.kappa_dot_max:
                        infeasibility_reason = f"Rejected trajectory for KappaDOT {abs((kappa_gl[i] - kappa_gl[i - 1]) / self.dT if i > 0 else 0.)} between step {i - 1} and {i}"
                        feasible = False
                        break
                    if abs(a[i]) > self.constraints.a_max:
                        infeasibility_reason = f"Rejected trajectory for Acceleration {a[i]} at step {i}"
                        feasible = False
                        break
                    if abs(v[i]) < -0.01:
                        infeasibility_reason = f"Rejected trajectory for Velocity {v[i]} at step {i}"
                        feasible = False
                        break

                    # de-normalization
                    theta_gl = np.unwrap(theta_gl)

                    if abs((theta_gl[i - 1] - theta_gl[i]) / self.dT if i > 0 else 0.) > self.constraints.theta_dot_max:
                        infeasibility_reason =f"Rejected trajectory for Theta_dot {(theta_gl[i - 1] - theta_gl[i]) / self.dT if i > 0 else 0.} between step {i - 1} and {i}"
                        feasible = False
                        break

                if oopd:
                    # Do not show the one Out of Projection Domain!
                    continue

                # store Cartesian trajectory
                trajectory.cartesian = CartesianSample(x, y, theta_gl, v, a, kappa_gl,
                                                       np.append([0], np.diff(kappa_gl)))
                # store Curvilinear trajectory
                trajectory.curvilinear = CurviLinearSample(s, d, theta_gl, ss=s_velocity, sss=s_acceleration,
                                                           dd=d_velocity,
                                                           ddd=d_acceleration)

                # check if trajectories planning horizon is shorter than expected and extend if necessary
                # if self.horizon > trajectory.trajectory_long.delta_tau:
                # NOT SURE WHY THIS HAPPENS? FEW SAMPLING POINTS?
                if self.N + 1 > len(trajectory.cartesian.x):
                    trajectory.enlarge(self.N + 1 - len(trajectory.cartesian.x), self.dT)
                elif self.N + 1 < len(trajectory.cartesian.x):
                    trajectory.reduce(len(trajectory.cartesian.x) - (self.N + 1))

                if self.N + 1 == len(trajectory.cartesian.x) == len(trajectory.cartesian.y) == len(trajectory.cartesian.theta):
                    if feasible:
                        feasible_trajectories.append(trajectory)
                    else:
                        infeasible_trajectories.append(trajectory)
                        infeasibility_reasons.append(infeasibility_reason)
                        logger.debug(f"infeasibility_reason= {infeasibility_reason}" )
                else:
                    logger.warning("Error in generating the Cartesian Trajectory {} - {} - {}. Skip trajectory!".format(
                        trajectory.the_v, trajectory.the_d, trajectory.the_t
                    ))
                    infeasible_trajectories.append(trajectory)
                    infeasibility_reasons.append("Cannot generate the Cartesian Trajectory")

            except Exception as ex_info:
                infeasible_trajectories.append(trajectory)
                infeasibility_reasons.append(f"Error {ex_info.args}")
                logger.error("Failed to handle trajectory ! {}".format(tr_index))

        logger.debug(
            '<ReactivePlanner>: Kinematic check of %s trajectories done' % len(trajectory_bundle.trajectories))

        return feasible_trajectories, infeasible_trajectories, infeasibility_reasons

    def _compute_initial_states(self, x_0: State) -> (np.ndarray, np.ndarray):
        """
        Computes the initial states for the polynomial planner based on a CommonRoad state

        TODO Sometimes this fail because we cannot convert to curvilinear coordinates the initial/current state.
        Possible causes are:
            - The vehicle is too close to the end of the road/goal region
                -> solution: ensure that there's at least some minimum distance to goal/end of the road

        :param x_0: The CommonRoad state object representing the initial state of the vehicle
        :return: A tuple containing the initial longitudinal and lateral states (lon,lat)
        """

        # compute curvilinear position
        try:
            s, d = self._co.convert_to_curvilinear_coords(x_0.position[0], x_0.position[1])
        except ValueError:
            logger.exception('<Reactive_planner>: Value Error for curvilinear transformation')
            # TODO What's this?
            tmp = np.array([x_0.position])
            logger.info(x_0.position)
            # logger.info(self._co._reference[0])
            # logger.info(self._co._reference[-1])
            if self._co._reference[0][0] > x_0.position[0]:
                reference_path = np.concatenate((tmp, self._co._reference), axis=0)
            else:
                reference_path = np.concatenate((self._co._reference, tmp), axis=0)
            # self.set_reference_path(reference_path)
            s, d = self._co.convert_to_curvilinear_coords(x_0.position[0], x_0.position[1])

        # compute orientation in curvilinear coordinate frame
        ref_theta = np.unwrap(self._co.ref_theta())
        theta_cl = x_0.orientation - np.interp(s, self._co.ref_pos(), ref_theta)

        # compute curvatures
        kr = np.interp(s, self._co.ref_pos(), self._co.ref_curv())
        kr_d = np.interp(s, self._co.ref_pos(), self._co.ref_curv_d())

        # compute d prime and d prime prime -> derivation after arc length
        d_p = (1 - kr * d) * np.tan(theta_cl)
        d_pp = -(kr_d * d + kr * d_p) * np.tan(theta_cl) + ((1 - kr * d) / (np.cos(theta_cl) ** 2)) * (
                x_0.yaw_rate * (1 - kr * d) / np.cos(theta_cl) - kr)

        # compute s dot and s dot dot -> derivation after time
        s_d = x_0.velocity * np.cos(theta_cl) / (1 - kr * d)
        if s_d < 0:
            raise Exception(
                "Initial state or reference incorrect! Curvilinear velocity is negative which indicates that the "
                "ego vehicle is not driving in the same direction as specified by the reference")

        try:
            s_dd = x_0.acceleration

            s_dd -= (s_d ** 2 / np.cos(theta_cl)) * (
                    (1 - kr * d) * np.tan(theta_cl) * (x_0.yaw_rate * (1 - kr * d) / (np.cos(theta_cl)) - kr) -
                    (kr_d * d + kr * d_p))
            s_dd /= ((1 - kr * d) / (np.cos(theta_cl)))
        except Exception as e:
            print("AH")

        d_d = x_0.velocity * np.sin(theta_cl)
        d_dd = s_dd * d_p + s_d ** 2 * d_pp

        x_0_lon = [s, s_d, s_dd]
        x_0_lat = [d, d_d, d_dd]


        logger.debug("Starting planning trajectories with: \n#################")
        logger.debug(f'Initial state for planning is {x_0}')
        logger.debug(f'Initial x_0 lon = {x_0_lon}')
        logger.debug(f'Initial x_0 lat = {x_0_lat}')
        logger.debug("#################")

        return x_0_lon, x_0_lat

    def sample_trajectories(self, current_state,
                            t_sec_min=T_SEC_MIN, t_sec_max=T_SEC_MAX,
                            # Those are LEFT and RIGHT
                            d_meter_min = D_METER_MIN, d_meter_max = D_METER_MAX,
                            #
                            v_meter_per_sec_min=V_METER_PER_SEC_MIN, v_meter_per_sec_max=V_METER_PER_SEC_MAX) -> List[Trajectory]:
        """ feasible_trajectory, non_feasible_trajectory, infeasibility_reason """
        # TODO Use horizon here and compute n steps given dT
        assert t_sec_min >= T_SEC_MIN and t_sec_max < self.horizon

        t_range = (t_sec_min, t_sec_max)
        d_range = (d_meter_min, d_meter_max)
        v_range = (v_meter_per_sec_min, v_meter_per_sec_max)
        # v_range = (current_state.speed_ms - 2.0, current_state.speed_ms + 2.0)

        # TODO Not sure what t samples is used for... I guess from the current time onwards?
        # Probably we should move them into create_bundle!
        self._sampling_t = TimeSampling(t_range[0], t_range[1], self.n_samples, self.dT)
        # low: float, up: float, n_samples: int
        self._sampling_d = PositionSampling(d_range[0], d_range[1], self.n_samples)
        # low: float, up: float, n_samples: int):
        self._sampling_v = VelocitySampling(v_range[0], v_range[1], self.n_samples)

        # Translate current_state in x_0_lon and x_0_lat
        x_0 = State(**{
            "time_step": current_state.timestamp,
            "position": np.array([current_state.position_x, current_state.position_y]),
            "velocity": current_state.speed_ms,
            "orientation": current_state.rotation,
            "acceleration": current_state.acceleration_m2s,
            "yaw_rate": 0,
            "slip_angle": 0
        })

        x_0_lon, x_0_lat = self._compute_initial_states(x_0)


        # plan trajectory bundle - We replaced the ref path at beginning
        feasible_trajectories, non_feasible_trajectories, infeasibility_reasons = self._generate_feasible_trajectories(x_0_lon, x_0_lat, samp_level=SAMPLING_LEVEL)

        # Convert the TrajectorySamples to a list of Trajectories and return them
        return \
            [Trajectory.from_trajectory_sample(t) for t in feasible_trajectories],\
            [Trajectory.from_trajectory_sample(t) for t in non_feasible_trajectories],\
            infeasibility_reasons


