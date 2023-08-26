from commonroad.scenario.lanelet import LaneletType


class ValidationConfig:

    # safety_time in seconds will be used to calculate safe distances to other ego cars
    def __init__(self, safety_time=2) -> None:
        # time in seconds for a safe distance between two cars
        self.safety_time = safety_time

    lanelet_types = {
        LaneletType.HIGHWAY,
        LaneletType.ACCESS_RAMP,
        LaneletType.EXIT_RAMP,
        LaneletType.URBAN,
    }
    # this validation is not needed when taking valid scenarios from the online dataset
    validate_lanelet_type_and_direction = False
    lanelet_same_direction_only = False

    def car_distance_formula(self, speed):
        return speed * self.safety_time

    min_dist_goal = 50
    retry_generation = 10000

    ignore_validation = False  # for debugging purposes
