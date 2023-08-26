from typing import Dict, List

from model.mixed_traffic_scenario import MixedTrafficScenario

from commonroad.geometry.shape import Polygon, Rectangle, ShapeGroup
from commonroad.scenario.trajectory import State
import numpy as np
from numpy.core.numeric import full


from commonroad.planning.planning_problem import PlanningProblem, PlanningProblemSet
from commonroad.scenario.lanelet import Lanelet, LaneletNetwork, LaneletType
from commonroad.scenario.scenario import Scenario

from validation.config import ValidationConfig

from shapely.ops import nearest_points, split, snap, unary_union
from shapely.geometry import Point, LineString

import matplotlib.pyplot as plt

NODE_DISTANCE_TOLERANCE = 0.01  # this is in meters
ADJACENT_WAY_DISTANCE_TOLERANCE = 0.05


class ScenarioValidator:
    def __init__(self):
        self.config: ValidationConfig = ValidationConfig()

    def is_mixed_traffic_scenario_valid(
        self, mixed_traffic_scenario: MixedTrafficScenario
    ):
        # TODO Extract the CommonRoad scenario and the PlanninProblems and validate them
        # return self.is_scenario_valid(mixed_traffic_scenario.scenario, mixed_traffic_scenario.planning_problems_set)
        return True

    def is_scenario_valid(self, scenario: Scenario, problem_set: PlanningProblemSet):
        # TODO validation is not very robust as later during development many validation criteria were
        #  implemented inside the mutation operators
        if self.config.ignore_validation:
            return True
        is_lanelet_network_valid = self.validate_lanelets(scenario)
        is_planning_problem_valid = self.validate_planning_problems(
            scenario, problem_set
        )
        return is_lanelet_network_valid and is_planning_problem_valid

    def validate_lanelets(self, scenario: Scenario):
        lanelet_network: LaneletNetwork = scenario.lanelet_network
        lanelets: Dict[int, Lanelet] = lanelet_network.lanelets
        for lanelet in lanelets:
            if not self._validate_lanlet_basics(lanelet):
                return False
            # those next variables only contain the lanelet IDs
            predecessors: list = lanelet.predecessor
            successors: list = lanelet.successor
            left_lanelet = lanelet.adj_left
            right_lanelet = lanelet.adj_right
            if not self._validate_lanelets_orientation(
                lanelet, left_lanelet, right_lanelet
            ):
                print("Scenario not valid: Bad Lanelet Orientation")
                return False
        return True

    def validate_planning_problems(
        self, scenario: Scenario, problem_set: PlanningProblemSet
    ):
        lanelet_network: LaneletNetwork = scenario.lanelet_network
        planning_problems = list(problem_set.planning_problem_dict.values())
        for key, problem in problem_set.planning_problem_dict.items():
            if not self._validate_initial_state(problem):
                return False
        if not self._validate_init_distances(scenario, problem_set):
            return False
        if not self._validate_distance_to_goal(scenario, problem_set):
            return False
        return True

    @staticmethod
    def _validate_initial_state(problem: PlanningProblem):
        if problem.initial_state.velocity < 1:
            print("Scenario not valid: Initial velocity too low")
            return False

        goal_region = problem.goal
        # check if initial state is not in goal region
        for goal_state in goal_region.state_list:
            # when no position provided the goal most likely is to not crash until a certain time step
            if hasattr(goal_state, "position") and goal_state.position.contains_point(
                problem.initial_state.position
            ):
                print("Scenario not valid: Initial State inside of Goal Region")
                return False

        # TODO: check if planning problem has the same orientation as the lanelet it is on
        return True

    def _validate_init_distances(
        self, scenario: Scenario, problem_set: PlanningProblemSet
    ):
        lanelet_network: LaneletNetwork = scenario.lanelet_network
        lanelets: Dict[int, Lanelet] = lanelet_network.lanelets
        obstacle_states: Dict[int, State] = scenario.obstacle_states_at_time_step(0)
        planning_problems = list(problem_set.planning_problem_dict.values())
        for lanelet in lanelets:
            full_lanelets = get_successor_lanelets(lanelet, lanelet_network)
            for full_ll in full_lanelets:
                # collect planning problems on this lanelet
                pp_on_lanelet = dict()
                for pp in planning_problems:
                    if full_ll.polygon.contains_point(pp.initial_state.position):
                        pp_on_lanelet[pp.planning_problem_id] = pp.initial_state
                # collect obstacles on this lanelet
                obstacles_on_lanelet = dict()
                for obstacle_key, state in obstacle_states.items():
                    if full_ll.polygon.contains_point(state.position):
                        obstacles_on_lanelet[obstacle_key] = state
                if not self._is_distance_in_lane_kept(
                    full_ll, obstacles_on_lanelet, pp_on_lanelet
                ):
                    return False
        return True

    def _validate_distance_to_goal(
        self, scenario: Scenario, problem_set: PlanningProblemSet
    ):
        planning_problems = list(problem_set.planning_problem_dict.values())
        for pp in planning_problems:
            init_position = pp.initial_state.position
            goal = pp.goal
            # distance to goal is always valid when the goal area is a full lanelet
            if (
                goal.lanelets_of_goal_position is not None
                and len(goal.lanelets_of_goal_position.values()) > 0
            ):
                return True
            # skip planning problems that don't have an area goal
            # it is possible that goals only have a required time_step
            if not hasattr(goal.state_list[0], "position"):
                continue
            goal_state = goal.state_list[0]
            goal_area = goal_state.position
            line = LineString([goal_area.center, init_position])
            distance = line.length
            if distance < self.config.min_dist_goal:
                print(
                    "Scenario not valid: Minimum distance to Goal Region not fulfilled"
                )
                return False
        return True

    # TODO should this only be checked for planning problems or also dynamic obstacles?
    def _is_distance_in_lane_kept(
        self,
        lanelet: Lanelet,
        obstacles: Dict[int, State],
        planning_problems: Dict[int, State],
    ):
        # check if lanelet is empty
        if not obstacles and not planning_problems:
            return True

        # all_obstacles = {**obstacles, **planning_problems}
        all_obstacles = {**planning_problems}
        if len(all_obstacles.values()) < 2:
            return True
        for key, obstacle in all_obstacles.items():
            path = LineString(lanelet.center_vertices)
            obstacle_center = Point(obstacle.position[0], obstacle.position[1])
            distance_to_obstacle = path.project(obstacle_center)
            # get the closest point from obstacle_center to the road center line
            # obstacle_point_path = path.interpolate(distance_to_obstacle)
            split_paths = cut(path, distance_to_obstacle)
            # when path could not be split a car is not centered or way off lanelet and the scenario is invalid
            if len(split_paths) != 2:
                return False
            # TODO is obstacle.orientation relevant for selecting the correct split lanelet
            #  in theory lanelet direction should automatically solve this
            path = split_paths[1]
            distance = self.config.car_distance_formula(obstacle.velocity)
            path = cut(path, distance)[0]
            required_driving_area = path.buffer(1)
            # plt.clf()
            # plt.plot(obstacle.position[0], obstacle.position[1], "go")
            for other_key, other_obstacle in all_obstacles.items():
                if key == other_key:
                    continue
                # plt.plot(*split_paths[1].buffer(1).exterior.xy, color="blue")
                # plt.plot(*split_paths[0].buffer(1).exterior.xy, color="purple")
                # plt.plot(other_obstacle.position[0],
                #          other_obstacle.position[1], "ro")
                # plt.show()
                other_obstacle_center = Point(
                    other_obstacle.position[0], other_obstacle.position[1]
                )
                if required_driving_area.intersects(other_obstacle_center):
                    print(
                        "Scenario not valid: Distance to next object in lane too short"
                    )
                    return False
            # plt.clf()

        return True

    # adjacent lanelets share the middle line with each other as a boundary for the right/left lanelet
    # so we need to check if the left/right boundary are the same for each other
    def _validate_lanelets_orientation(self, lanelet, left_lanelet, right_lanelet):
        # not really needed since we are currently not mutating the lanelet network
        return True

    # validate same direction of neighbour lanelets
    def _validate_lanlet_basics(self, lanelet: Lanelet):
        if not self.config.validate_lanelet_type_and_direction:
            return True
        # check if lanelet has correct type
        if lanelet.lanelet_type.intersection(self.config.lanelet_types) == set():
            print("Scenario not valid: Wrong Lanelet Types")
            return False
        if self.config.lanelet_same_direction_only and (
            (
                lanelet.adj_right_same_direction is not None
                and not lanelet.adj_right_same_direction
            )
            or (
                lanelet.adj_left_same_direction is not None
                and not lanelet.adj_left_same_direction
            )
        ):
            print("Scenario not valid: Lanelets not all in same direction")
            return False

        return True

    # code taken from commonroad scenario designer
    def _find_adjacencies_of_coinciding_ways(
        self,
        lanelet: Lanelet,
        first_left_node: str,
        first_right_node: str,
        last_left_node: str,
        last_right_node: str,
    ):
        """Find adjacencies of a lanelet by checking if its vertices coincide with vertices of other lanelets.

        Set new adjacent left or right if it finds neighbors.

        Args:
          lanelet: Lanelet to check potential adjacencies for.
          first_left_node: Id of first left node of the lanelet relation in OSM.
          first_right_node: Id of first right node of the lanelet relation in OSM.
          last_left_node: Id of last left node of the lanelet relation in OSM.
          last_right_node: Id of last right node of the lanelet relation in OSM.

        """
        # first case: left adjacent, same direction
        if lanelet.adj_left is None:
            potential_left_front = self._find_lanelet_ids_of_suitable_nodes(
                self.first_right_pts, first_left_node
            )
            potential_left_back = self._find_lanelet_ids_of_suitable_nodes(
                self.last_right_pts, last_left_node
            )
            potential_left_same_direction = list(
                set(potential_left_front) & set(potential_left_back)
            )
            for lanelet_id in potential_left_same_direction:
                nb_lanelet = self.lanelet_network.find_lanelet_by_id(lanelet_id)
                if nb_lanelet is not None and _two_vertices_coincide(
                    lanelet.left_vertices, nb_lanelet.right_vertices
                ):
                    self.lanelet_network.set_adjacent_left(
                        lanelet, nb_lanelet.lanelet_id, True
                    )
                    break

        # second case: right adjacent, same direction
        if lanelet.adj_right is None:
            potential_right_front = self._find_lanelet_ids_of_suitable_nodes(
                self.first_left_pts, first_right_node
            )
            potential_right_back = self._find_lanelet_ids_of_suitable_nodes(
                self.last_left_pts, last_right_node
            )
            potential_right_same_direction = list(
                set(potential_right_front) & set(potential_right_back)
            )
            for lanelet_id in potential_right_same_direction:
                nb_lanelet = self.lanelet_network.find_lanelet_by_id(lanelet_id)
                if nb_lanelet is not None and _two_vertices_coincide(
                    lanelet.right_vertices, nb_lanelet.left_vertices
                ):
                    self.lanelet_network.set_adjacent_right(
                        lanelet, nb_lanelet.lanelet_id, True
                    )
                    break

        # third case: left adjacent, opposite direction
        if lanelet.adj_left is None:
            potential_left_front = self._find_lanelet_ids_of_suitable_nodes(
                self.last_left_pts, first_left_node
            )
            potential_left_back = self._find_lanelet_ids_of_suitable_nodes(
                self.first_left_pts, last_left_node
            )
            potential_left_other_direction = list(
                set(potential_left_front) & set(potential_left_back)
            )
            for lanelet_id in potential_left_other_direction:
                nb_lanelet = self.lanelet_network.find_lanelet_by_id(lanelet_id)
                # compare right vertice of nb_lanelet with left vertice of lanelet
                if nb_lanelet is not None and _two_vertices_coincide(
                    lanelet.left_vertices, nb_lanelet.left_vertices[::-1]
                ):
                    self.lanelet_network.set_adjacent_left(
                        lanelet, nb_lanelet.lanelet_id, False
                    )
                    break

        # fourth case: right adjacent, opposite direction
        if lanelet.adj_right is None:
            potential_right_front = self._find_lanelet_ids_of_suitable_nodes(
                self.last_right_pts, first_right_node
            )
            potential_right_back = self._find_lanelet_ids_of_suitable_nodes(
                self.first_right_pts, last_right_node
            )
            potential_right_other_direction = list(
                set(potential_right_front) & set(potential_right_back)
            )
            for lanelet_id in potential_right_other_direction:
                nb_lanelet = self.lanelet_network.find_lanelet_by_id(lanelet_id)
                if nb_lanelet is not None and self._two_vertices_coincide(
                    lanelet.right_vertices, nb_lanelet.right_vertices[::-1]
                ):
                    self.lanelet_network.set_adjacent_right(
                        lanelet, nb_lanelet.lanelet_id, True
                    )
                    break

    def _find_lanelet_ids_of_suitable_nodes(
        self, nodes_dict: dict, node_id: str
    ) -> List:
        """Find values of a dict where the keys are node ids.

        Return the entries if there is a value in the node_dict
        for the node_id, but also the values for nodes which are in
        the proximity of the node with the node_id.

        Args:
          nodes_dict: Dict which saves lanelet ids with node ids as keys.
          node_id: Id of node for which the other entries are searched for.
        Returns:
          List of lanelet ids which match the above-mentioned rules.
        """
        suitable_lanelet_ids = []
        suitable_lanelet_ids.extend(nodes_dict.get(node_id, []))
        for nd, lanelet_ids in nodes_dict.items():
            if self.node_distance(nd, node_id) < NODE_DISTANCE_TOLERANCE:
                suitable_lanelet_ids.extend(lanelet_ids)
        return suitable_lanelet_ids

    def node_distance(self, node_id1: str, node_id2: str) -> float:
        """Calculate distance of one node to other node in the projection.

        Args:
          node_id1: Id of first node.
          node_id2: id of second node.
        Returns:
          Distance in
        """
        node1 = self.osm.find_node_by_id(node_id1)
        node2 = self.osm.find_node_by_id(node_id2)
        vec1 = np.array(self.proj(float(node1.lon), float(node1.lat)))
        vec2 = np.array(self.proj(float(node2.lon), float(node2.lat)))
        return np.linalg.norm(vec1 - vec2)


def get_successor_lanelets(
    lanelet: Lanelet, ll_network: LaneletNetwork
) -> List[Lanelet]:
    # TODO only need to check for remaining distance of the drivable area, do this with additional dist param
    full_lanelets = [lanelet]
    processed_ids = [lanelet.lanelet_id]
    while _have_lanelets_successors(full_lanelets, processed_ids):
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


def _have_lanelets_successors(lanelets: List[Lanelet], visited_ll_ids: List[int]):
    have_successors = any(
        len(ll.successor) != 0
        and any(ll_id not in visited_ll_ids for ll_id in ll.successor)
        for ll in lanelets
    )
    return have_successors


def cut(line: LineString, distance: float):
    # cuts a line in two at distance from its starting point
    if distance <= 0.0 or distance >= line.length:
        return [line]
    coords = list(line.coords)
    for i, p in enumerate(coords):
        pd = line.project(Point(p))
        if pd == distance:
            return [LineString(coords[: i + 1]), LineString(coords[i:])]
        if pd > distance:
            cp = line.interpolate(distance)
            return [
                LineString(coords[:i] + [(cp.x, cp.y)]),
                LineString([(cp.x, cp.y)] + coords[i:]),
            ]


def _two_vertices_coincide(
    vertices1: List[np.ndarray], vertices2: List[np.ndarray]
) -> bool:
    """Check if two vertices coincide and describe the same trajectory.

    For each vertice of vertices2 the minimal distance to the trajectory
    described by vertices1 is calculated. If this distance crosses a certain
    threshold, the vertices are deemed to be different.

    Args:
    vertices1: List of vertices which describe first trajectory.
    vertices2: List of vertices which describe second trajectory.

    Returns:
    True if the vertices coincide, else False.
    """
    segments = np.diff(vertices1, axis=0)

    for vert in vertices2:
        distances = np.empty([len(vertices1) + 1])
        distances[0] = np.linalg.norm(vert - vertices1[0])
        distances[-1] = np.linalg.norm(vert - vertices1[-1])
        for i, diff in enumerate(segments):
            distances[i + 1] = np.abs(
                np.cross(diff, vertices1[i] - vert)
            ) / np.linalg.norm(diff)
        if np.min(distances) > ADJACENT_WAY_DISTANCE_TOLERANCE:
            return False

    return True
