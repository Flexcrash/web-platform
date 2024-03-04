import math

import numpy as np
import matplotlib.pyplot as plt
from model.trajectory import TrajectorySampler
from model.mixed_traffic_scenario import MixedTrafficScenario
from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate
from persistence.user_data_access import UserDAO
from persistence.mixed_scenario_template_data_access import MixedTrafficScenarioTemplateDAO
from persistence.mixed_scenario_data_access import MixedTrafficScenarioDAO
from persistence.driver_data_access import DriverDAO
from persistence.vehicle_state_data_access import VehicleStateDAO

from model.user import User
from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate
from model.mixed_traffic_scenario import MixedTrafficScenario
from model.driver import Driver
from model.vehicle_state import VehicleState


from commonroad.visualization.mp_renderer import MPRenderer

def plot(state: VehicleState, ref_path, trajectories, color):
    plt.plot(state.position_x, state.position_y, "o", markersize=5, color="yellow", zorder=101)
    plt.plot([x[0] for x in ref_path], [x[1] for x in ref_path], "-", color=color, zorder=100)

    for t in trajectories:
        plt.plot([s.position_x for s in t.planned_states],
             [s.position_y for s in t.planned_states], "--", alpha=0.2, color=color, zorder=102)

def initial_state_generator(n_drivers, scenario_id):
    # Make sure that the vehicle is rotated, so linear and snaptoroad are different
    rotation = 2.33 + math.pi * 0.1

    speed_md = 10.0
    # If this is wrong, the car cannot really move as freely as one can expect
    acceleration_m2s = 3.0
    # The road has one lane and it's slope in xy is -1
    scenario_slope = -1.1
    distance_x = 5
    min_x, min_y = 557.32551, -684.4076
    for idx in range(0, n_drivers):
        position_x = min_x - idx * distance_x
        position_y = min_y + (scenario_slope * - idx * distance_x)

        yield [None, "ACTIVE", 0, None, scenario_id, position_x, position_y, rotation, speed_md,
               acceleration_m2s]

def generate_goal_area():
    from commonroad.geometry.shape import Rectangle
    import numpy as np

    orientation = 2.33
    min_x, min_y = 557.32551, -684.4076
    scenario_slope = -1.1
    distance_x = 3
    position_x = min_x - distance_x
    position_y = min_y + (scenario_slope * - distance_x)

    return Rectangle(4.0, 4.0, np.array([position_x, position_y]), orientation)



def test_plot_and_check(xml_scenario_template):
    user_id = 1
    username = "1"
    email="foo"
    password ="bar"

    user = User(user_id=user_id, username=username, email=email, password=password)

    scenario_id = 1
    name = "foo"
    description =""

    created_by = user
    max_players = 1
    status = "ACTIVE"

    template_id = 1
    template_name = "foo"
    template_description = ""
    scenario_template = MixedTrafficScenarioTemplate(
        template_id=template_id,
        name=template_name,
        description=template_description,
        xml=xml_scenario_template)

    duration = 1.0
    drivers = [Driver(user_id=user_id, scenario_id=scenario_id)]

    mixed_traffic_scenario = MixedTrafficScenario(
        scenario_id=scenario_id,
        name=name, description=description, created_by=created_by, max_players=max_players, status=status, scenario_template=scenario_template,
        duration=duration, drivers=drivers
    )

    state_gen = initial_state_generator(len(drivers), scenario_id)
    initial_state_array = next(state_gen)
    initial_state_array[3] = user.user_id

    # vehicle_state_id, status, timestamp, user_id, scenario_id, position_x, position_y, rotation, speed_ms, acceleration_m2s
    initial_state_dict = {
        "vehicle_state_id": initial_state_array[0],
        "status": initial_state_array[1],
        "timestamp": initial_state_array[2],
        "user_id": initial_state_array[3],
        "scenario_id": initial_state_array[4],
        "position_x": initial_state_array[5],
        "position_y": initial_state_array[6],
        "rotation": initial_state_array[7],
        "speed_ms": initial_state_array[8],
        "acceleration_m2s": initial_state_array[9]
    }
    initial_state = VehicleState(**initial_state_dict)

    goal_region_as_rectangle = generate_goal_area()

    rnd = MPRenderer(figsize=(10,5))
    mixed_traffic_scenario.scenario_template.as_commonroad_scenario().draw(rnd)


    ####
    from commonroad.geometry.shape import Rectangle
    from configuration.config import VEHICLE_WIDTH, VEHICLE_LENGTH
    dynamic_obstacle_shape = Rectangle(VEHICLE_LENGTH, VEHICLE_WIDTH)
    from commonroad.scenario.obstacle import DynamicObstacle, ObstacleType
    from commonroad.prediction.prediction import TrajectoryPrediction, Trajectory
    dynamic_obstacle_initial_state = initial_state.as_commonroad_state()
    # State(position=np.array([initial_state.position_x, initial_state.position_y]),
    #                                        velocity=initial_state.speed_ms,
    #                                        orientation=initial_state.rotation,
    #                                        time_step=initial_state.timestamp)

    # Since this is only a state, we might not need any state list
    dynamic_obstacle_prediction = TrajectoryPrediction(
        Trajectory(dynamic_obstacle_initial_state.time_step, [dynamic_obstacle_initial_state]),
        dynamic_obstacle_shape)

    dynamic_obstacle_id = initial_state.user_id
    dynamic_obstacle_type = ObstacleType.CAR
    dynamic_obstacle = DynamicObstacle(dynamic_obstacle_id,
                                       dynamic_obstacle_type,
                                       dynamic_obstacle_shape,
                                       dynamic_obstacle_initial_state,
                                       dynamic_obstacle_prediction)


    vehicle_data = {"vehicle_shape": {
        "occupancy": {
            "shape": {
                "rectangle": {
                    "facecolor": "blue",
                    "edgecolor": "blue",
                    "linewidth": 1.0,
                    "zorder": 50,
                    "opacity": 1.0
                    }
                }
            }
        }
    }

    # The states are ordered by time_steps
    dynamic_obstacle.draw(rnd, draw_params={"time_begin": dynamic_obstacle.initial_state.time_step,
                                            "dynamic_obstacle": vehicle_data})
    rnd.render()

    snap_to_road = True
    sampler = TrajectorySampler(mixed_traffic_scenario, initial_state, goal_region_as_rectangle, snap_to_road)
    trajectories = sampler.sample_trajectories(initial_state)
    ref_path = sampler._ref_path
    plot(initial_state, ref_path, trajectories, color="green")


    snap_to_road = False
    linear_sampler = TrajectorySampler(mixed_traffic_scenario, initial_state, goal_region_as_rectangle, snap_to_road)
    linear_trajectories = linear_sampler.sample_trajectories(initial_state)
    linear_ref_path = linear_sampler._ref_path
    plot(initial_state, linear_ref_path, linear_trajectories, color="black")


    plt.show()
    ##
    # plot(current_position, road_snap_ref_path)