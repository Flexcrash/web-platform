import math
import random

import numpy as np
from commonroad.geometry.shape import Rectangle
from commonroad.scenario.lanelet import Lanelet
from shapely.geometry import LineString, Point


class MixedTrafficScenarioGenerator:
    """
    TODO: This probably can be merged with MixedTrafficScenario
    This code is based on the work by Tobias Ziegler from Uni Passau
    """
#
    def __init__(self, mixed_traffic_scenario, goal_region_length, goal_region_width, dist_to_end, min_initial_speed, max_initial_speed, mixed_traffic_scenario_dao):
        self.length = goal_region_length
        self.width = goal_region_width
        self.dist_to_end = dist_to_end
        self.min_initial_speed = min_initial_speed
        self.max_initial_speed = max_initial_speed
        self.mixed_traffic_scenario_dao = mixed_traffic_scenario_dao

        commonroad_scenario = mixed_traffic_scenario.scenario_template.as_commonroad_scenario()

        # Extract the lanelet network
        self.lanelet_network = commonroad_scenario.lanelet_network
        self.drivers = mixed_traffic_scenario.drivers
        self.scenario_id = mixed_traffic_scenario.scenario_id

        self.mixed_traffic_scenario = mixed_traffic_scenario

    def generate_random_goal_region(self):

        # Select a random exit Lanelet
        lanelet = random.choice(self.lanelet_network.lanelets)
        full_lanelets = self._get_successor_lanelets(lanelet, self.lanelet_network)
        random_ll = random.choice(full_lanelets)
        # Build the corresponding Rectangle

        #######
        # # TODO: FORCE PREDICTABLE STATE - Use Mocking While Testing!
        # random_ll = [ l for l in self.lanelet_network.lanelets if l.lanelet_id == 1002][0]
        # ########


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

    def create_initial_states(self):
        #
        # Create the initial states for each driver
        #  TODO Add validation of the scenario to ensure initial placement is correct!
        #         is_valid = validator.is_scenario_valid(new_scenario, new_problem_set)

        goal_regions_as_rectangles = [self.mixed_traffic_scenario_dao.get_goal_region_for_driver_in_scenario(driver, self.mixed_traffic_scenario) for driver in self.drivers]

        return [self.generate_random_initial_state(driver, goal_region) for driver, goal_region in zip(self.drivers, goal_regions_as_rectangles)]

    def _get_possible_goal_for_lanelet(self, lanelet):
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
