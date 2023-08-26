import pytest
from flask import url_for
import json
import matplotlib.pyplot as plt
import numpy as np

from commonroad.visualization.mp_renderer import MPRenderer
from commonroad.scenario.trajectory import Trajectory, State

@pytest.mark.skip(reason="Cannot use plt.show()")
def test_smoke_test(flexcrash_test_app_with_a_scenario_template_and_given_users):
    # Create the app with the factory method
    scenario_creator_user_id = 1
    scenario_template_id = 1

    n_users = 1
    n_avs = 0
    duration = 10  # Keep it short

    flask_app = flexcrash_test_app_with_a_scenario_template_and_given_users([scenario_creator_user_id],
                                                                            scenario_template_id)

    with flask_app.test_client() as test_client:
        # Create the scenario using the API to trigger the AV
        scenario_id = 1
        scenario_data = {
            "scenario_id": scenario_id,  # enforce this to make the test predictable
            "template_id": scenario_template_id,
            "duration": duration,
            "creator_user_id": scenario_creator_user_id,
            "name": "short-test",
            "n_users": n_users,
            "n_avs": n_avs
        }
        response = test_client.post(url_for("api.scenarios.create"), data=scenario_data)
        assert response.status_code == 202

        # Register the user as driver. This activate the scenario
        driver_data = {
            "user_id": scenario_creator_user_id
        }

        # TODO Make this predictable by forcing an initial state and goal area for all the participants

        response = test_client.post(url_for("api.scenarios.create_driver", scenario_id=scenario_id),
                                    data=driver_data)
        assert response.status_code == 204

        # Now we can sample the trajectories
        response = test_client.get(url_for("api.scenarios.compute_trajectories_from_state",
                                           scenario_id=scenario_id, driver_id=scenario_creator_user_id, timestamp=0))

        assert response.status_code == 200

        data_as_json_object = json.loads(response.data)

        # This should be somewhere
        initial_time_step = 0
        state_list = []
        # fig, ax = plt.subplots(1, 1)
        # ax.axis("equal")
        for trajectory in data_as_json_object:
            x = []
            y = []
            for i, p_state in enumerate(trajectory["planned_states"]):
                x.append(p_state["position_x"])
                y.append(p_state["position_y"])
                # data = {
                #     'position': np.array([p_state["position_x"], p_state["position_y"]]),
                #     'orientation': p_state["rotation"],
                #     'velocity': p_state["speed_ms"],
                #     'yaw_rate': 0.0,
                #     'acceleration': p_state["acceleration_m2s"],
                #     'time_step': i #p_state["timestamp"] # NONE
                # }
                # state_list.append(State(**data))
            # trajectory = Trajectory(initial_time_step, state_list)
            #

            plt.plot(x, y, "-", zorder=20)
            plt.scatter(x, y, s=2, zorder=21)
        # rnd = MPRenderer()
        # # Create A trajectory
        # trajectory.draw(rnd)
        plt.show()