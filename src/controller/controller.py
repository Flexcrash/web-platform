import math
import random

import numpy as np

from typing import Tuple, List


from commonroad.geometry.shape import Rectangle, Polygon
from commonroad.scenario.lanelet import Lanelet
from shapely.geometry import LineString, Point
from shapely.ops import substring, nearest_points
from scipy.interpolate import splev, splprep
from numpy.ma import arange
from itertools import islice

from model.utils import direction_along_segment

def _pairs(lst):
    for i in range(1, len(lst)):
        yield lst[i - 1], lst[i]

def _triple(lst):
    for i in range(2, len(lst)):
        yield lst[i - 2], lst[i - 1], lst[i]


def _window(seq, n=2):
    """
    Returns a sliding window (of width n) over data from the iterable
       s -> (s0,s1,...s[n-1]), (s1,s2,...,sn), ...
    Taken from: https://stackoverflow.com/questions/6822725/rolling-or-sliding-window-iterator

    :param seq:
    :param n:
    :return:
    """

    it = iter(seq)
    result = tuple(islice(it, n))
    if len(result) == n:
        yield result
    for elem in it:
        result = result[1:] + (elem,)
        yield result


def _interpolate_and_resample_splines(sample_nodes, nodes_per_meter = 5, smoothness=0, k=3, rounding_precision=4):
    """ Interpolate a list of points as a spline (quadratic by default) and resample it with num_nodes"""

    # Compute lenght of the road
    road_lenght = LineString([(t[0], t[1]) for t in sample_nodes]).length

    num_nodes = nodes_per_meter  * int(road_lenght)

    old_x_vals = [t[0] for t in sample_nodes]
    old_y_vals = [t[1] for t in sample_nodes]
    # old_width_vals  = [t[3] for t in sample_nodes]

    assert len(sample_nodes) > 1, "Not enought point!"

    # Interpolate the old points
    if len(sample_nodes) == 2:
        pos_tck, pos_u = splprep([old_x_vals, old_y_vals], s=smoothness, k=1)
    elif len(sample_nodes) == 3:
        pos_tck, pos_u = splprep([old_x_vals, old_y_vals], s=smoothness, k=2)
    else:
        pos_tck, pos_u = splprep([old_x_vals, old_y_vals], s=smoothness, k=k)

    # Resample them
    step_size = 1 / num_nodes
    unew = arange(0, 1 + step_size, step_size)

    new_x_vals, new_y_vals = splev(unew, pos_tck)

    # Reduce floating point rounding errors otherwise these may cause problems with calculating parallel_offset
    return list(zip([round(v, rounding_precision) for v in new_x_vals],
                    [round(v, rounding_precision) for v in new_y_vals]))


def _identify_segment(road_nodes, goal_area_coords, length_before, length_after):

    nodes_per_meter = 2

    # Interpolate and resample, then take some point before and after the given point
    road_points = _interpolate_and_resample_splines(road_nodes, nodes_per_meter=nodes_per_meter)

    # Create a LineString out of the road_points
    road_line = LineString([(rp[0], rp[1]) for rp in road_points])

    goal_area_point = Point(*goal_area_coords)

    # Find the point in the interpolated points that is closes to the OOB position
    # https://stackoverflow.com/questions/24415806/coordinates-of-the-closest-points-of-two-geometries-in-shapely
    np = nearest_points(road_line, goal_area_point)[0]

    # https://gis.stackexchange.com/questions/84512/get-the-vertices-on-a-linestring-either-side-of-a-point
    before = None
    after = None

    road_coords = list(road_line.coords)
    for i, p in enumerate(road_coords):
        if Point(p).distance(np) < 1.0/nodes_per_meter:
            before = road_coords[0:i]
            before.append(np.coords[0])

            after = road_coords[i:]

    # Take the s meters 'before' the OBE or the entire segment otherwise
    distance = 0
    temp = []
    for p1, p2 in _window(reversed(before), 2):

        if len(temp) == 0:
            temp.append(p1)

        distance += LineString([p1, p2]).length

        if distance >= length_before:
            break
        else:
            temp.insert(0, p2)

    # segment_before = LineString(temp)

    distance = 0
    # temp = []
    for p1, p2 in _window(after, 2):

        if len(temp) == 0:
            temp.append(p1)

        distance += LineString([p1, p2]).length

        if distance >= length_after:
            break
        else:
            temp.append(p2)

    # segment_after = LineString(temp)
    segment = LineString(temp)
    return segment



class MixedTrafficScenarioGenerator:
    """
    TODO: This probably can be merged with MixedTrafficScenario
    This code is based on the work by Tobias Ziegler from Uni Passau
    """
#
    def __init__(self, mixed_traffic_scenario, goal_region_length, goal_region_width, dist_to_end, min_initial_speed, max_initial_speed,
                 mixed_traffic_scenario_dao):
        self.length = goal_region_length
        self.width = goal_region_width
        self.dist_to_end = dist_to_end
        self.min_initial_speed = min_initial_speed
        self.max_initial_speed = max_initial_speed

        # NOT USED ANYMORE?!
        self.mixed_traffic_scenario_dao = mixed_traffic_scenario_dao

        # Note: Does this count as a transaction because we are accessing the scenario_template, which is a relation?
        # db.session.begin(nested=False)
        commonroad_scenario = mixed_traffic_scenario.scenario_template.as_commonroad_scenario()
        # db.session.commit()

        # Extract the lanelet network
        self.lanelet_network = commonroad_scenario.lanelet_network
        self.drivers = mixed_traffic_scenario.drivers
        self.scenario_id = mixed_traffic_scenario.scenario_id

        self.mixed_traffic_scenario = mixed_traffic_scenario

    def generate_goal_region(self, goal_region_position: Tuple[float, float]) -> Rectangle:
        orientation, snapped_initial_state = self._get_road_rotation_at_target_position(goal_region_position)
        center = np.array(snapped_initial_state)
        return Rectangle(self.length, self.width, center, orientation)

    def generate_random_goal_region(self):

        # Select a random exit Lanelet
        lanelet = random.choice(self.lanelet_network.lanelets)
        full_lanelets = self._get_successor_lanelets(lanelet, self.lanelet_network)
        random_ll = random.choice(full_lanelets)
        # Build the corresponding Rectangle

        goal_area = self._get_possible_goal_for_lanelet(random_ll)

        return goal_area

    def generate_random_initial_state(self, driver, goal_region_as_rectangle):
        """
        Starting from the driver's goal_region this code finds a random initial state by navigating the lanelet network
        backwards

        :param driver:
        :param goal_region_as_rectangle:
        :return:
        """

        # ######
        # # # TODO: FORCE PREDICTABLE STATE - Use Mocking While Testing!
        # if driver.user_id % 2 == 0:
        #     # position_x = {float} 21.031278567377385
        #     # position_y = {float} 21.363057754887016
        #     # rotation = {float} -3.0878530931621313
        #     return (None, "ACTIVE", 0, driver.user_id, self.scenario_id,  21.031278567377385, 21.363057754887016, -3.0878530931621313, 1.0, 0.0)
        # else:
        #     # position_x = {float} 24.87260616671392
        #     # position_y = {float} 21.576690205635856
        #     # rotation = {float} -3.1466276344870137
        #     return (None, "ACTIVE", 0, driver.user_id, self.scenario_id, 28.87260616671392, 21.576690205635856, -3.1466276344870137, 1.0, 0.0)
        #
        # ####

        # This might be more than one, in this case, we keep ALL of them
        lanelet_ids = self.lanelet_network.find_lanelet_by_shape(goal_region_as_rectangle)

        # Reachable lanelets are the one on which the goal region is plus the ones preceeding it
        lanelet_queue = set([self.lanelet_network.find_lanelet_by_id(l) for l in lanelet_ids])
        considered_queues = set([])
        reacheable_lanelets = set([self.lanelet_network.find_lanelet_by_id(l) for l in lanelet_ids])

        #
        while len(lanelet_queue) > 0:
            lanelet = lanelet_queue.pop()

            # If we already considered this lanelet, we skip it
            if lanelet in considered_queues:
                continue
            else:
                considered_queues.add(lanelet)

            # Reachable lanelets are the one(s) that comes before this lanelet
            if len(lanelet.predecessor) > 0:
                [reacheable_lanelets.add(self.lanelet_network.find_lanelet_by_id(l)) for l in lanelet.predecessor]
                [lanelet_queue.add(self.lanelet_network.find_lanelet_by_id(l)) for l in lanelet.predecessor]

            # Reachable lanelets are also the ones that have the same direction and on the side of the lanelet
            if lanelet.adj_left and lanelet.adj_left_same_direction:
                reacheable_lanelets.add(self.lanelet_network.find_lanelet_by_id(lanelet.adj_left))
                lanelet_queue.add(self.lanelet_network.find_lanelet_by_id(lanelet.adj_left))
            if lanelet.adj_right and lanelet.adj_right_same_direction:
                reacheable_lanelets.add(self.lanelet_network.find_lanelet_by_id(lanelet.adj_right))
                lanelet_queue.add(self.lanelet_network.find_lanelet_by_id(lanelet.adj_right))

        # TODO: This must ensure that goal area for driver is reachebla and the placement is valid (no unavoidable collisions)

        # Select one of the lanelet that can reach the goal area
        tentative_lanelet = random.choice(list(reacheable_lanelets))
        # Select one of the lanelet's vertices as the initial position (note, we cannot use the last point)
        random_index = random.choice(range(len(tentative_lanelet.center_vertices) - 2))
        position = tentative_lanelet.center_vertices[random_index]

        # Ensure that the vehicle is rotated as the road segment
        next_point = tentative_lanelet.center_vertices[random_index + 1]
        rotation = self._get_orientation_by_coords((position[0], position[1]), (next_point[0], next_point[1]))

        # Randomly select the initial speed
        speed_ms = random.uniform(self.min_initial_speed, self.max_initial_speed)
        assert speed_ms > 0.0

        # TODO Not sure what to do about this one...
        # Randomly select the initial acceleration
        # acceleration_m2s = random.uniform(self.min_initial_speed, self.max_initial_speed)
        acceleration_m2s = 0.0

        # The data to put inside the VehicleState including the None/NULL vehicle_state_id
        # TODO Probably "ACTIVE", and "0 - timestamp" are not necessary here
        return (None, "ACTIVE", 0, driver.user_id, self.scenario_id, position[0], position[1], rotation, speed_ms, acceleration_m2s)

    def _get_road_rotation_at_target_position(self, target_position: Tuple[float, float]):
        lanelets_per_position: List[List[int]]
        lanelets_per_position = self.lanelet_network.find_lanelet_by_position([np.array(target_position)])

        assert len(lanelets_per_position) > 0, f"There's no lanelet in position {target_position}"
        assert len(lanelets_per_position[0]) > 0, f"There's no lanelet in position {target_position}"

        # Get the first lanelet if any
        lanelet_id = lanelets_per_position[0][0]
        lanelet = self.lanelet_network.find_lanelet_by_id(lanelet_id)

        # Interpolate and resample
        nodes_per_meter = 2
        road_points = _interpolate_and_resample_splines(lanelet.center_vertices, k=1, nodes_per_meter=nodes_per_meter)
        # Create a LineString out of the road_points
        road_line = LineString([(rp[0], rp[1]) for rp in road_points])
        goal_area_point = Point(*target_position)
        # Find the point in the interpolated points that is closes to the goal area point
        # https://stackoverflow.com/questions/24415806/coordinates-of-the-closest-points-of-two-geometries-in-shapely
        # This is "on" the line, but not one of the existing points!
        nearest_point = nearest_points(road_line, goal_area_point)[0]
        # Find an actual point among the road_line.coords
        orientation = None
        for reference, next_one in _pairs(list(road_line.coords)):

            reference = Point(reference)
            next_one = Point(next_one)

            if reference.distance(nearest_point) <= 1.0 / nodes_per_meter and reference.distance(nearest_point) < next_one.distance(nearest_point):

                def _debug_plot():
                    import matplotlib.pyplot as plt
                    from commonroad.visualization.mp_renderer import MPRenderer
                    rnd = MPRenderer(figsize=(10,10))
                    self.lanelet_network.draw(rnd)
                    rnd.render()

                    # plt.plot(*road_line.coords.xy, "-.")
                    plt.plot(*road_line.coords.xy, "o", zorder=100)
                    plt.plot(reference.x, reference.y, "o", color="black", zorder=100)
                    plt.plot(next_one.x, next_one.y, "o", color="red", zorder=100)

                    plt.plot(target_position[0], target_position[1], "*", color="orange", zorder=100)
                    plt.plot(nearest_point.x, nearest_point.y, "o", color="orange", zorder=100)

                    plt.gca().set_aspect("equal")
                    plt.show()

                # _debug_plot()

                orientation = direction_along_segment(nearest_point, next_one)

        assert orientation is not None

        return orientation, nearest_point

    def create_initial_states(self, snap_to_lanelet=True) -> dict[int, Tuple]:
        """

        :param snap_to_lanelet: True - use the center of the road; False - use actual initial state position
        :return:
        """
        initial_states = {}
        for driver in self.mixed_traffic_scenario.drivers:
            position_x, position_y = driver.initial_position

            rotation, snapped_initial_state = self._get_road_rotation_at_target_position(driver.initial_position)

            if snap_to_lanelet:
                position_x = snapped_initial_state.x
                position_y = snapped_initial_state.y

            # TODO Shall we also ask this as input to the user?
            acceleration_m2s = 0.0
            # TODO Validate with min/max speed?
            speed_ms = driver.initial_speed
            initial_states[driver.driver_id] = (None, "ACTIVE", 0, driver.user_id, self.scenario_id, position_x, position_y, rotation, speed_ms, acceleration_m2s)
        return initial_states

    def _get_possible_goal_for_lanelet(self, lanelet) -> Rectangle:
        reversed_center_vertices = LineString(lanelet.center_vertices[::-1])
        # Take the center of the lanelet at the given distance. TODO This can be selected also at random
        goal_center_vertices: LineString = self._cut(reversed_center_vertices, self.dist_to_end)[0]
        goal_center = goal_center_vertices.centroid

        # last_point is at index 0 because vertices were reversed previously
        last_point = goal_center_vertices.coords[0]
        orientation = self._get_orientation_by_coords((goal_center.x, goal_center.y), (last_point[0], last_point[1]))
        return Rectangle(self.length, self.width, np.array([goal_center.x, goal_center.y]), orientation)

    def _cut(self, line, distance):
        # cuts a line in two at distance from its starting point
        if distance <= 0.0 or distance >= line.length:
            return [line]
        coords = list(line.coords)
        for i, p in enumerate(coords):
            pd = line.project(Point(p))
            if pd == distance:
                return [
                    LineString(coords[:i + 1]),
                    LineString(coords[i:])]
            if pd > distance:
                cp = line.interpolate(distance)
                return [
                    LineString(coords[:i] + [(cp.x, cp.y)]),
                    LineString([(cp.x, cp.y)] + coords[i:])]

    def _get_orientation_by_coords(self, first_point, next_point):
        a_x, a_y = next_point
        b_x, b_y = first_point
        # compute orientation: https://stackoverflow.com/questions/42258637/how-to-know-the-angle-between-two-vectors
        return math.atan2(a_y - b_y, a_x - b_x)

    def _get_successor_lanelets(self, lanelet, ll_network):
        # TODO only need to check for remaining distance of the drivable area, do this with additional dist param
        full_lanelets = [lanelet]
        processed_ids = [lanelet.lanelet_id]
        while self._have_lanelets_successors(full_lanelets, processed_ids):
            new_full_lls = []
            for ll in full_lanelets:
                if len(ll.successor) == 0:
                    new_full_lls.append(ll)
                else:
                    for succ_id in ll.successor:
                        succ_ll = ll_network.find_lanelet_by_id(succ_id)
                        full_lanelet = Lanelet.merge_lanelets(ll, succ_ll)
                        new_full_lls.append(full_lanelet)
                        processed_ids.append(succ_ll.lanelet_id)

            full_lanelets = new_full_lls
        return full_lanelets

    def _have_lanelets_successors(self, lanelets, visited_ll_ids):
        have_successors = any(len(ll.successor) != 0 and any(
            ll_id not in visited_ll_ids for ll_id in ll.successor) for ll in lanelets)
        return have_successors
