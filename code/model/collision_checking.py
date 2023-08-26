from typing import List, Tuple, Dict

# https://commonroad.in.tum.de/docs/commonroad-drivability-checker/sphinx/05_collision_checks_dynamic_obstacles.html
# commonroad_dc
import commonroad_dc.pycrcc as pycrcc
from commonroad_dc.collision.collision_detection.pycrcc_collision_dispatch import create_collision_checker, create_collision_object
from commonroad_dc.boundary import boundary
from commonroad_dc.collision.trajectory_queries import trajectory_queries
from commonroad_dc.pycrcc.Util import trajectory_enclosure_polygons_static

# Flexcrash platform
from model.mixed_traffic_scenario import MixedTrafficScenario
from model.user import User
from model.vehicle_state import VehicleState
from commonroad.geometry.shape import Rectangle

# Causes Circular import
# from persistence.data_access import VehicleStateDAO

from configuration.config import VEHICLE_WIDTH, VEHICLE_LENGTH

# TODO We do not really need a class for this, since there's no state here?
class CollisionChecker():

    def __init__(self, vehicle_state_dao):
        self.vehicle_state_dao = vehicle_state_dao

    def check_for_collisions(self, scenario: MixedTrafficScenario, timestamp: int) -> List[Tuple[User, VehicleState]]:
        """ Basic collision checking: get the state of not DONE/GOAL_REACHED vehicles at given time stamp, create a OBBRectangle object, check collisions """
        # No need to check collision over time or predicted occupancy set
        # TODO This will prob fail to check drivers that have GOAL_REACHED state

        # Fetch the states from the DB
        vehicles_state_at_timestamp = self.vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(
            scenario_id=scenario.scenario_id, timestamp=timestamp)

        # Sort states and driver by driver id, and then zip them to match
        sorted_vehicles_state = sorted(vehicles_state_at_timestamp, key=lambda vs : vs.user_id)
        sorted_drivers = sorted(scenario.drivers, key=lambda d: d.user_id)

        # Build the map such that all the sparse data are available at one place
        drivers_map = {}

        crashed_drivers_and_their_state = []
        # Make sure we consider only active drivers!
        for driver, vehicle_state in zip(sorted_drivers, sorted_vehicles_state):
            # Better safe than sorry!
            assert driver.user_id == vehicle_state.user_id, "Driver and VehicleState have different ids! "

            if vehicle_state.status == "GOAL_REACHED":
                continue

            drivers_map[driver.user_id] = {}
            drivers_map[driver.user_id]["driver"] = driver
            # Oriented rectangle with width/2, height/2, orientation, x-position , y-position
            # TODO What's width and height at this point?
            drivers_map[driver.user_id]["obstacle"] = pycrcc.RectOBB(VEHICLE_LENGTH/2, VEHICLE_WIDTH/2,
                                                                     vehicle_state.rotation,
                                                                     vehicle_state.position_x, vehicle_state.position_y)
            # TODO Is this really safe? Ideally, if something is already crashed, the cc should report CRASHED
            # TODO What about OFF_ROAD?
            drivers_map[driver.user_id]["state"] = vehicle_state

        def debug_plot():
            from commonroad.visualization.mp_renderer import MPRenderer
            rnd = MPRenderer(figsize=(10,10))
            for obstacle, color in zip([v["obstacle"] for v in drivers_map.values()], ["green", "red"]):
                obstacle.draw(rnd,  draw_params={'facecolor': color})
            rnd.render()

        # Now check all the possible combinations (note, this can be improved)
        done = []
        for v1_key, v1_dict in drivers_map.items():
            done.append(v1_key)
            for v2_key, v2_dict in [(k, v) for (k, v) in drivers_map.items() if k not in done]:
                if v1_dict["obstacle"].collide(v2_dict["obstacle"]):
                    crashed_drivers_and_their_state.append((v1_dict["driver"], v1_dict["state"]))
                    crashed_drivers_and_their_state.append((v2_dict["driver"], v2_dict["state"]))

        # Return the list of (driver, state) for reportedly CRASHED vehicles
        return crashed_drivers_and_their_state

    def check_goal_reached(self, vehicles_state_at_timestamp: Dict[int, VehicleState],
                           goal_region_as_rectangles: Dict[int, Rectangle]) -> List[int]:
        """
        Simply checks whether vehicles' BBox collides with the corresponding goal regions

        :param states:
        :param goal_region_as_rectangles:
        :return:
        """
        # TODO Note that here we use driver id and not user objects!!

        # Build the map such that all the sparse data are available at one place
        goal_reached_drivers = []

        # Assume the maps have the same entries!
        for driver_id in vehicles_state_at_timestamp.keys():

            vehicle_state = vehicles_state_at_timestamp[driver_id]
            goal_region_as_rectangle = goal_region_as_rectangles[driver_id]

            # Do they collide?

            state_rect = pycrcc.RectOBB(VEHICLE_LENGTH / 2, VEHICLE_WIDTH / 2,
                                        vehicle_state.rotation,
                                        vehicle_state.position_x, vehicle_state.position_y)

            goal_rect = pycrcc.RectOBB(goal_region_as_rectangle.length/2, goal_region_as_rectangle.width/2,
                                       goal_region_as_rectangle.orientation,
                                       goal_region_as_rectangle.center[0], goal_region_as_rectangle.center[1])

            if state_rect.collide(goal_rect):
                goal_reached_drivers.append(driver_id)

            def debug_plot():
                from commonroad.visualization.mp_renderer import MPRenderer
                rnd = MPRenderer(figsize=(10, 10))
                state_rect.draw(rnd, draw_params={'facecolor': "green"})
                goal_rect.draw(rnd, draw_params={'facecolor': "red"})
                rnd.render()

        return goal_reached_drivers