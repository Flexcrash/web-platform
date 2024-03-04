def initial_state_and_goal_area_generator(n_drivers):
    """ This method assume the simple, one road, test scenario so the goal area is always at the same point """
    rotation = 2.33
    speed_md = 1.0
    acceleration_m2s = 0.0
    # The road has one lane and it's slope in xy is -1
    scenario_slope = -1.1
    distance_x = 5
    min_x, min_y = 557.32551, -684.4076
    #
    goal_area_x, goal_area_y = 529.628465, -651.5852025

    for idx in range(0, n_drivers):
        position_x = min_x - idx * distance_x
        position_y = min_y + (scenario_slope * - idx * distance_x)

        # This was the internal representation of the complete state, now we provide only x, y and speed
        # yield [None, "ACTIVE", 0, None, scenario_id, position_x, position_y, rotation, speed_md,
        #        acceleration_m2s]
        yield ((position_x, position_y), speed_md), (goal_area_x, goal_area_y)

from collections import namedtuple
MockedVehicleState = namedtuple('MockedVehicleState', ["timestamp", "status",
                                                       "position_x", "position_y", "rotation",
                                                       "speed_ms", "acceleration_m2s",
                                                       "user_id", "driver_id", "scenario_id"])

def initial_full_state(n_drivers):
    """ This method assume the simple, one road, test scenario so the goal area is always at the same point """
    rotation = 2.33
    speed_ms = 1.0
    acceleration_m2s = 0.0
    # The road has one lane and it's slope in xy is -1
    scenario_slope = -1.1
    distance_x = 5
    min_x, min_y = 557.32551, -684.4076

    scenario_id = None

    for idx in range(0, n_drivers):
        position_x = min_x - idx * distance_x
        position_y = min_y + (scenario_slope * - idx * distance_x)
        kwargs = {
            "timestamp": 0,
            "position_x":  position_x,
            "position_y":  position_y,
            "rotation":  rotation,
            "speed_ms":  speed_ms,
            "acceleration_m2s":  acceleration_m2s,
            "user_id":  idx,
            "driver_id":  idx,
            "scenario_id":  None,
            "status":  "ACTIVE"
        }
        # This was the internal representation of the complete state, now we provide only x, y and speed
        yield MockedVehicleState(**kwargs)

def generate_scenario_data(scenario_creator_user_id, scenario_template_id, n_avs, n_users, scenario_duration_in_seconds, scenario_id=None, preregistered_users=[]):

    state_gen = initial_state_and_goal_area_generator(n_avs + n_users)
    # Create the scenario using the API to trigger the AV
    scenario_data = {
        "template_id": scenario_template_id,
        "duration": scenario_duration_in_seconds,
        "creator_user_id": scenario_creator_user_id,
        "name": "test",
        "n_users": n_users,
        "n_avs": n_avs,
    }

    if scenario_id is not None:
        scenario_data["scenario_id"] = scenario_id

    scenario_data["users"] = ",".join([str(user_id) for user_id in preregistered_users])

    # Initial States and Goal Regions
    scenario_data["id_array"] = "[" + ",".join([f'"AV_{i}"' for i in range(1, n_avs + 1)] + [f'"UD_{i}"' for i in range(1, n_users + 1 - len(preregistered_users))] + [f'"U_{user_id}"' for user_id in preregistered_users]) + "]"

    # Add information for initial state and goal aread
    for i in range(1, n_avs + 1):
        initial_state, goal_area = next(state_gen)
        scenario_data[f"AV_{i}_x"] = initial_state[0][0]
        scenario_data[f"AV_{i}_y"] = initial_state[0][1]
        scenario_data[f"AV_{i}_speed"] = initial_state[1]
        scenario_data[f"AV_{i}_goal_x"] = goal_area[0]
        scenario_data[f"AV_{i}_goal_y"] = goal_area[1]

    for i in range(1, n_users + 1 - len(preregistered_users)):
        initial_state, goal_area = next(state_gen)
        scenario_data[f"UD_{i}_x"] = initial_state[0][0]
        scenario_data[f"UD_{i}_y"] = initial_state[0][1]
        scenario_data[f"UD_{i}_speed"] = initial_state[1]
        scenario_data[f"UD_{i}_goal_x"] = goal_area[0]
        scenario_data[f"UD_{i}_goal_y"] = goal_area[1]

    for user_id in preregistered_users:
        initial_state, goal_area = next(state_gen)
        scenario_data[f"U_{user_id}_x"] = initial_state[0][0]
        scenario_data[f"U_{user_id}_y"] = initial_state[0][1]
        scenario_data[f"U_{user_id}_speed"] = initial_state[1]
        scenario_data[f"U_{user_id}_goal_x"] = goal_area[0]
        scenario_data[f"U_{user_id}_goal_y"] = goal_area[1]

    return scenario_data

