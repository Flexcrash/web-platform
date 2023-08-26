import json
import os

from flask_login import LoginManager, login_required, logout_user, login_user, current_user

from model.trajectory import TrajectorySampler, D_METER_MIN, D_METER_MAX, T_SEC_MIN, T_SEC_MAX, SAMPLING_LEVEL

from flask import Blueprint
from flask import current_app, redirect, url_for, render_template, request
from flask_login import LoginManager, login_required, logout_user, login_user
import werkzeug
from werkzeug.routing.exceptions import BuildError

from persistence.data_access import MixedTrafficScenarioDAO, UserDAO, VehicleStateDAO

# This blueprint handles the requests for the Web layer
web_layer = Blueprint('web', __name__, url_prefix='/')

# The login manager for the Web Part
login_manager = LoginManager()
login_manager.login_view = "web.login"

@login_manager.user_loader
def load_user(user_id):
    """ Returns a user object if exist or None otherwise"""
    user_dao = UserDAO(current_app.config)
    user = user_dao.get_user_by_user_id(user_id)
    if user: # Store this into DB?
        user.is_active = True
        user.is_authenticated = True
    return user


@web_layer.before_request
def log_request_info():
    # Reference: https://stackoverflow.com/questions/31637774/how-can-i-log-request-post-body-in-flask
    """ Log each and every request """
    current_app.logger.debug('Request: %s', request.url)


@web_layer.route('/', methods=["GET"])
@login_required
def index():
    return render_template("2_start_menu.html"), 200

@web_layer.route('/login_user', methods=['GET', 'POST'])
def login():

    if request.method == "GET":
        # Default to FALSE
        sign_up_enabled = current_app.config["SING_UP_DISABLED"] if "SING_UP_DISABLED" in current_app.config else False
        return render_template("1_login.html", sign_up_enabled=sign_up_enabled), 200
    else:
        # TODO Probably we could use the API to authenticate this user
        # Authenticate the user and generate a token
        email, password = request.form['log_email'], request.form['log_pass']
        user_dao = UserDAO(current_app.config)
        if user_dao.verify_password(email, password):
            user = user_dao.get_user_by_email(email)
            # TODO Handle this with DB. By default is False, so the user will be ignored
            user.is_active = True
            user.is_authenticated = True
            # Ensure Login-Flask knows about the user
            login_user(user)
            # This is to automatically redirect to the next page.
            # next = request.args.get('next')
            # is_safe_url should check if the url is safe for redirects.
            # See http://flask.pocoo.org/snippets/62/ for an example.
            # if not is_safe_url(next):
            #     return flask.abort(400)
            #
            # return flask.redirect(next or flask.url_for('index'))
            # return flask.render_template('login.html', form=form)
            # Show the Start menu page
            return redirect(url_for("web.index"))
        else:
            # Show the Login menu page (again)
            # TODO Add a message maybe
            return render_template("1_login.html", error="Invalid Credentials"), 401

@web_layer.route("/logout", methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for("web.index"))

@web_layer.route('/register_user', methods=['POST'])
def register():
    # We use the API to register the USER and we always return to the LOGIN page
    with current_app.test_client() as http_client:
        user_data = {
            "username": request.form["username"],
            "email": request.form["reg_email"],
            "password": request.form["reg_pass"]
        }
        response = http_client.post(url_for("api.users.create"), data = user_data)
        if response.status_code == 201:
            return render_template("1_login.html"), 200
        else:
            # TODO Improve the message
            return render_template("1_login.html", error="CANNOT REGISTER"), response.status_code

@web_layer.route('/navbar', methods=["GET"])
@login_required
def navbar():
    return render_template("nav.html")

@web_layer.route('/footer', methods=["GET"])
def footer():
    return render_template("footer.html")

@web_layer.route('/setup_custom_scenario', methods=["GET"])
@login_required
def create_scen():
    # List all the existing templates to get their ID using the API
    with current_app.test_client() as http_client:
        response = http_client.get(url_for("api.templates.get_scenario_templates"))
        # Parse the respons into a JSON Object
        scenario_templates = json.loads(response.data)

    # Extract all the template IDs
    scenario_template_ids = [st["template_id"] for st in scenario_templates]

    # Create the relative file paths
    scenario_template_file_paths = [os.path.join(current_app.config["TEMPLATE_IMAGES_FOLDER"],".".join([str(st_id), "png"]))
                                    for st_id in scenario_template_ids]

    # Make relative file paths, relative to STATIC FOLDER
    # https://stackoverflow.com/questions/8693024/how-to-remove-a-path-prefix-in-python
    relative_path = 'static'

    scenario_template_rel_paths = [os.path.relpath(full_path, relative_path) for full_path in scenario_template_file_paths]

    # For the list of files pointing to the images of the scenarios
    # <img src="{{url_for('static', filename='folder/file.png')}}">
    scenario_template_image_urls = [url_for("static", filename=fname) for fname in scenario_template_rel_paths]

    user_dao = UserDAO(current_app.config)
    users_data = user_dao.get_all_users()
    users = {}
    for user in users_data:
        users[user.username] = user.user_id

    return render_template("3_custom_scenario_setup.html",
                           scenario_template_image_urls_and_ids = list(zip(scenario_template_image_urls, scenario_template_ids)), all_users=users)

@web_layer.route('/webcreate', methods=['POST'])
@login_required
def create():
    """ Create the scenario from the data in the form"""
    # TODO Is the creator also a player? if not, visualize the entire scenario, if yes, visualize only its part?
    with current_app.test_client() as test_client:
        # Create the scenario using the API. The form data should be the same
        response = test_client.post(url_for("api.scenarios.create"), data=request.form)

        if response.status_code == 200 or response.status_code == 201 or response.status_code == 202:
            # Retrieve the scenario from the response
            scenario_dto = json.loads(response.data)
            return redirect(url_for("web.scenario_overview", scenario_id=scenario_dto["scenario_id"]))
            # return redirect(url_for(render_scenario), scenario_dto=scenario_dto)
        else:
            # In any other case, there was an issue with the creation
            # STORE MESSAGES IN THE SESSION?, error = "Cannot create the scenario")
            return redirect(url_for("web.create_scen"))

@web_layer.route('/setup_training_scenario', methods=["GET"])
@login_required
def create_training_scen():
    # List all the existing training scenario templates to get their ID using the API
    with current_app.test_client() as http_client:
        response = http_client.get(url_for("api.training.get_scenario_templates"))
        # Parse the respons into a JSON Object
        training_scenario_templates = json.loads(response.data)

    # Extract all the template IDs
    training_scenario_template_names = [st["name"] for st in training_scenario_templates]

    # Create the relative file paths
    # TODO Use the TrainingTemplate.get_file_name()?
    training_scenario_template_file_paths = [os.path.join(current_app.config["TEMPLATE_IMAGES_FOLDER"],
                                                          ".".join(["training_" + training_template_name, "png"]))
                                    for training_template_name in training_scenario_template_names]

    # Make relative file paths, relative to STATIC FOLDER
    # https://stackoverflow.com/questions/8693024/how-to-remove-a-path-prefix-in-python
    relative_path = 'static'

    training_scenario_template_rel_paths = [os.path.relpath(full_path, relative_path) for full_path in training_scenario_template_file_paths]

    # For the list of files pointing to the images of the scenarios
    # <img src="{{url_for('static', filename='folder/file.png')}}">
    training_scenario_template_image_urls = [url_for("static", filename=fname) for fname in training_scenario_template_rel_paths]

    return render_template("3_training_scenario_setup.html",
                           training_scenario_template_image_urls_and_ids = list(zip(training_scenario_template_image_urls, training_scenario_template_names)))

@web_layer.route('/webcreatetraining', methods=['POST'])
@login_required
def crt_training():
    """ Create the training scenario from the data in the form"""
    with current_app.test_client() as test_client:
        training_scenario_data = {
            "training_scenario_name" : request.form["training_scenario_name"],
            "trainee_id" : current_user.user_id
        }

        response = test_client.post(url_for("api.training.create"), data=training_scenario_data)

        if response.status_code == 200 or response.status_code == 201 or response.status_code == 202:
            scenario_dto = json.loads(response.data)
            return redirect(url_for("web.scenario_overview", scenario_id=scenario_dto["scenario_id"]))
        else:
            return redirect(url_for("web.create_training_scen"))


@web_layer.route('/scenarios/<scenario_id>', methods=['GET'])
@login_required
def scenario_overview(scenario_id):
    # Retrieve the scenario object
    scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = scenario_dao.get_scenario_by_scenario_id(scenario_id)

    scenario_state_dtos = []
    scenario_image_urls = []

    focus_on_driver = False

    # If the status is in WAITING, it means that we are waiting for people to join, there are no vehicle states
    # that can be visualized
    if scenario.status != "WAITING":
        # Is the current user also a driver? If not, unless the scenario is ready nobody can see it
        focus_on_driver = any([driver.user_id == current_user.user_id for driver in scenario.drivers])



        # The following rules control the creation of the links that enable submitting states
        # If no action was submitted -> PENDING -> Do not create any link
        # If an action (but not all submitted) -> WAITING -> Do not create any link
        # If all actions were submitted -> ACTIVE -> Create link to DYNAMIC page
        # If the following scenario state is ACTIVE or CRASH or GOAL_REACHED, the current one CANNOT BE -> DONE -> Create link to STATIC page

        # Collect all the status information and images

        # We need to refer to the scenario ACTUAL duration when it is in state DONE!
        visualized_duration = scenario.duration
        if scenario.status == "DONE":
            visualized_duration =  scenario_dao.compute_effective_duration(scenario)

        scenario_states = []
        for timestamp in range(0, visualized_duration + 1):
            scenario_states.append(scenario_dao.get_scenario_state_at_timestamp(scenario_id, timestamp))

        # # Update the Actionable Scenario States
        # for index in range(0, len(scenario_states) - 1):
        #     if scenario_states[index + 1] == "ACTIVE":
        #         scenario_states[index] = "DONE"
        # # If the last state is ACTIVEm, then it is also DONE
        # if scenario_states[-1] == "ACTIVE":
        #     scenario_states[-1] = "DONE"

        current_user_driver_state = None
        if focus_on_driver:
            # Retrieve the last known state of the current user driver in this scenario
            vehicle_state_dao = VehicleStateDAO(current_app.config)
            last_timestamp = None
            for timestamp in range(0, visualized_duration + 1):
                if scenario_states[timestamp] != "PENDING":
                    last_timestamp = timestamp
            assert last_timestamp is not None
            current_user_driver_state = [ vs for vs in vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario_id, last_timestamp) if vs.user_id == current_user.user_id][0]

        for timestamp in range(0, visualized_duration + 1):
            scenario_state_dtos.append({
                "timestamp": timestamp,
                "status": scenario_states[timestamp]}
            )

            if(scenario_states[timestamp] != "PENDING"):
                # Generate the right image urls for the each state
                scenario_image_urls.append(
                    url_for("static", filename=_generate_scenario_image_rel_paths_for(scenario_id, timestamp))
                )

    # Visualize the ENTIRE scenario
    return render_template("4_scenario_overview.html",
                           focus_on_driver=focus_on_driver,
                           current_user_driver_state=current_user_driver_state,
                           scenario=scenario, scenario_state_dtos=scenario_state_dtos, scenario_image_urls = scenario_image_urls)


@web_layer.route('/drive', methods=['POST'])
@login_required
def drive_state():

    assert "planned_states" in request.form
    assert len(request.form.get("planned_states")) > 0

    assert "initial_timestamp" in request.form
    initial_timestamp = request.form.get("initial_timestamp")

    assert "scenario_id" in request.form
    scenario_id = request.form.get("scenario_id")

    states_data_list = json.loads(request.form.get("planned_states"))
    # TODO Iterate over the list and extract all the data
    states_data = {
        "timestamps": ",".join([str(t) for t, _ in enumerate(states_data_list, start=int(initial_timestamp)+1)]),
        "positions_x": ",".join([str(s["position_x"]) for s in states_data_list]),
        "positions_y": ",".join([str(s["position_y"]) for s in states_data_list]),
        "rotations": ",".join([str(s["rotation"]) for s in states_data_list]),
        "speeds_ms": ",".join([str(s["speed_ms"]) for s in states_data_list]),
        "accelerations_m2s": ",".join([ str(s["acceleration_m2s"]) for s in states_data_list])
    }


    with current_app.test_client() as http_client:
        response = http_client.put(url_for("api.scenarios.update_vehicle_states",
                                           scenario_id=scenario_id,
                                           driver_id=current_user.user_id),
                                   data=states_data)

    if response.status_code >= 300:
        return "", 500
    else:
        return redirect(url_for("web.scenario_overview", scenario_id=scenario_id))


def _generate_scenario_image_rel_paths_for(scenario_id, timestamp):
    # TODO Access this using an API call instead, maybe from api.users ?
    scenario_dao = MixedTrafficScenarioDAO(current_app.config)

    scenario = scenario_dao.get_scenario_by_scenario_id(scenario_id)

    # TODO: Until we remove this one, the method stays in this module!
    #  Is the current user also a driver? If not, unless the scenario is ready nobody can see it
    focus_on_driver = any([driver.user_id == current_user.user_id for driver in scenario.drivers])

    # We are in a PAST STATE or in a CRASH STATE. We visualize a static view
    if focus_on_driver:
        static_image_file_name = "_".join(["scenario", str(scenario_id),
                                           "timestamp", str(timestamp),
                                           "driver", str(current_user.user_id)])
    else:
        # This is no driver, we can simply show the current state of the entire scenario as STATIC
        static_image_file_name = "_".join(["scenario", str(scenario_id),
                                           "timestamp", str(timestamp)])

    # Add extension
    scenario_image_file_path = os.path.join(current_app.config["SCENARIO_IMAGES_FOLDER"],
                                            ".".join([static_image_file_name, "png"]))

    # Make the path relative to STATIC FOLDER
    relative_path = 'static'
    return os.path.relpath(scenario_image_file_path, relative_path)

@web_layer.route('/state', methods=['GET'])
@login_required
def scenario_state_static():
    """
    Visualize the state of the scenario as static entity
    TODO Add input validation
    :return:
    """

    args = request.args
    scenario_id = args.get('scenario_id')
    timestamp = int(args.get('timestamp'))

    scenario_dao = MixedTrafficScenarioDAO(current_app.config)

    scenario = scenario_dao.get_scenario_by_scenario_id(scenario_id)

    # Ensure that this state can be visualized
    scenario_state_at_timestamp = scenario_dao.get_scenario_state_at_timestamp(scenario_id, timestamp)

    # Is the current user also a driver? If not, unless the scenario is ready nobody can see it
    focus_on_driver = any([driver.user_id == current_user.user_id for driver in scenario.drivers])

    # This should not create weird infinite loops
    if focus_on_driver:
        if scenario_state_at_timestamp == "ACTIVE":
            if scenario_dao.is_driver_in_game(scenario, current_user):
                # Visualize the dynamic page instead
                return redirect(url_for("web.scenario_state", scenario_id=scenario_id, timestamp=timestamp))
        elif scenario_state_at_timestamp != "DONE":
            return "", 401

    # Make sure the URL is the correct one, i.e., relative to STATIC folder
    rendered_state_url = url_for("static", filename=_generate_scenario_image_rel_paths_for(scenario_id, timestamp))

    if timestamp <= 0:
        prev_state_url = None
    else:
        prev_state_url = url_for("web.scenario_state_static", scenario_id=scenario_id, timestamp=timestamp-1)

    if timestamp < scenario.duration:
        # Check the next state if exists
        scenario_state_at_next_timestamp = scenario_dao.get_scenario_state_at_timestamp(scenario_id, timestamp+1)
        if scenario_state_at_next_timestamp == "DONE":
            next_state_url = url_for("web.scenario_state_static", scenario_id=scenario_id, timestamp=timestamp + 1)
        elif scenario_state_at_next_timestamp == "ACTIVE":
            next_state_url = url_for("web.scenario_state", scenario_id=scenario_id, timestamp=timestamp + 1)
        else:
            next_state_url = None
    else:
        # Otherwise there's no next state
        next_state_url = None

    # Add the link to the scenario_url=scenario_url,
    scenario_url = url_for("web.scenario_overview", scenario_id=scenario_id)

    # Fetch the info about each vechicle state:
    vehicle_state_dao = VehicleStateDAO(current_app.config)
    vehicle_states_at_timestamp = vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario_id=scenario_id,
                                                                                                   timestamp=timestamp)
    # Fetch data about the drivers and monkey path the objects passed to the renderingi nterface
    user_dao = UserDAO(current_app.config)
    for vehicle_state in vehicle_states_at_timestamp:
        user = user_dao.get_user_by_user_id(vehicle_state.user_id)
        # vehicle_state.username
        setattr(vehicle_state, "username", user.username)
        # vehicle_state.is_current_user
        setattr(vehicle_state, "is_current_user", user.user_id == current_user.user_id)

    # Render the template
    return render_template("6_view_scenario_state_static.html",
                           rendered_state_url=rendered_state_url,
                           scenario_url=scenario_url,
                           prev_state_url=prev_state_url,
                           next_state_url=next_state_url,
                           vehicle_states=vehicle_states_at_timestamp)


@web_layer.route('/actionablestate', methods=['GET'])
@login_required
def scenario_state():
    """
    Visualize the interactive view of a scenario state
    :return:
    """
    ## TODO: There's api.scenarios.compute_trajectories_from_state(scenario_id, driver_id, timestamp)
    #   that apparently does the same thing, why not use that one?

    args = request.args
    scenario_id  = int(args.get('scenario_id'))
    timestamp = int(args.get('timestamp'))
    snap_to_road = args.get('relative') is None

    # Here some other parameters - We might handle them differently later
    t_sec_min = args.get('tmin', T_SEC_MIN)
    t_sec_max = args.get('tmax', T_SEC_MAX)
    d_meter_min = args.get('dmin', D_METER_MIN)
    d_meter_max = args.get('dmax', D_METER_MAX)

    # Speed is based on current speed at the moment

    scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = scenario_dao.get_scenario_by_scenario_id(scenario_id)

    # TODO This is NOT OK WE STILL HAVE TO CHECK IF THE TIMESTAMP IS THE LAST ONE!
    scenario_status_at_timestamp = scenario_dao.get_scenario_state_at_timestamp(scenario_id, timestamp)

    if scenario_status_at_timestamp == "PENDING":
        # PENDING STATES CANNOT BE VISUALIZED, because we need to input some actions in the previous ones (ACTIVE!)
        # The current user is NOT authorized to see the page
        return "", 401

    # Is the current user also a driver? If not, unless the scenario is ready nobody can see it
    focus_on_driver = any([driver.user_id == current_user.user_id for driver in scenario.drivers])

    # TODO Note: At the moment ACTIVE IS ATTACHED TO ALL, BUT API DOES NOT LET DO ANYTHING FOR THE WRONG STATE
    #   NOT RELIABLE
    if focus_on_driver and scenario_status_at_timestamp == "ACTIVE" and scenario_dao.is_driver_in_game(scenario, current_user):
        # In this case, we are ready to submit an action from the "last known" state
        # Read the HTML from the file
        interactive_image_file_name = "_".join(["scenario", str(scenario.scenario_id),
                                                "timestamp", str(timestamp),
                                                "driver", str(current_user.user_id)])
        # Add extension
        interactive_image_file_path = os.path.join(current_app.config["SCENARIO_IMAGES_FOLDER"],
                                                   ".".join([interactive_image_file_name, "embeddable.html"]))

        # Load the string
        with open(interactive_image_file_path, "r") as input_file:
            embeddable_html = input_file.read()

        # Get default parameters for trajectory visualization and generation - or read them from the URL or from the session ?
        vehicle_state_dao = VehicleStateDAO(current_app.config)

        current_state = next(vs for vs in vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario_id, timestamp)
                             if vs.user_id == current_user.user_id)

        initial_state = scenario_dao.get_initial_state_for_driver_in_scenario(current_user, scenario)
        goal_region_as_rectangle = scenario_dao.get_goal_region_for_driver_in_scenario(current_user, scenario)

        trajectory_sampler = TrajectorySampler(scenario, initial_state, goal_region_as_rectangle, snap_to_road)

        feasible_trajectories = trajectory_sampler.sample_trajectories(current_state,
                                               t_sec_min= t_sec_min, t_sec_max = t_sec_max,
                                               d_meter_min = d_meter_min, d_meter_max = d_meter_max)

        # Create the index v => d => t
        indexed_trajectories = {}

        v_samples = trajectory_sampler.get_sampled_v()
        d_samples = trajectory_sampler.get_sampled_d()
        t_samples = trajectory_sampler.get_sampled_t()

        # Note that many of those indices might be empty, so we need to filter them out!
        for v_index in range(0, len(v_samples)):
            indexed_trajectories[v_index] = {}
            for d_index in range(0, len(d_samples)):
                indexed_trajectories[v_index][d_index] = {}
                for t_index in range(0, len(t_samples)):
                    indexed_trajectories[v_index][d_index][t_index] = {}

        # Fill up the values
        for trajectory in feasible_trajectories:

            v_i = v_samples.index(trajectory.the_v)
            d_i = d_samples.index(trajectory.the_d)
            t_i = t_samples.index(trajectory.the_t)

            # We need something JSON serializable
            indexed_trajectories[v_i][d_i][t_i] = [{
                "timestamp": state.timestamp,
                "position_x": state.position_x,
                "position_y": state.position_y,
                "rotation": state.rotation,
                "speed_ms": state.speed_ms,
                "acceleration_m2s": state.acceleration_m2s} for state in trajectory.planned_states]

        # Render the template with the embedded HTML
        # References:
        #   - https://stackoverflow.com/questions/65318395/how-to-render-html-for-variables-in-flask-render-template

        # Provide the actual values of sampled dimensions and timestamp/time_step
        v = trajectory_sampler.get_sampled_v()
        d = trajectory_sampler.get_sampled_d()
        t = trajectory_sampler.get_sampled_t()
        h = [t_horizon * trajectory_sampler.dT for t_horizon in range(0, trajectory_sampler.N+1)]

        # Add the link to the previous state if any
        if int(timestamp) <= 0:
            prev_state_url = None
        else:
            prev_state_url = url_for("web.scenario_state_static", scenario_id=scenario_id, timestamp=int(timestamp) - 1)

        next_state_url = None # Trivally so

        # Add the link to the scenario_url=scenario_url,
        scenario_url = url_for("web.scenario_overview", scenario_id=scenario_id)

        return render_template("6_view_scenario_state_dynamic.html",
                               scenario_url=scenario_url,
                               prev_state_url=prev_state_url,
                               next_state_url=next_state_url,
                               embeddable_html=embeddable_html,
                               snap_to_road=snap_to_road,
                               trajectories = indexed_trajectories,
                               v_index = len(v) - 1,
                               d_index = len(d) - 1,
                               t_index = len(t) - 1,
                               # For the moment the horizon is as long as the trajectory sampler makes them
                               h_index = trajectory_sampler.N,
                               v = v,
                               d = d,
                               t = t,
                               h = h,
                               initial_timestamp=timestamp,
                               scenario_id=scenario_id)
    else:
        # If by chance someone ends up here, we show the scenario in the static form
        return redirect(url_for('web.scenario_state_static', scenario_id = scenario.scenario_id, timestamp=timestamp))

@web_layer.route('/render_scenario/<scenario_id>', methods=["GET", "POST"])
@login_required
def render_scenario():
    # xml = test_client.post(url_for("api.scenarios.create"))
    return render_template("4_current_simulation.html")


@web_layer.route('/created_by_you', methods=["GET"])
@login_required
def created_by_you():
    scenarios_active = []
    scenarios_waiting = []
    scenarios_done = []

    scenario_dao = MixedTrafficScenarioDAO(current_app.config)

    scenario_active_objects = scenario_dao.get_all_active_custom_scenarios(user_id=current_user.user_id)
    for scenario in scenario_active_objects:
        scenarios_active.append([scenario.name, scenario.scenario_id])

    scenario_waiting_objects = scenario_dao.get_all_waiting_custom_scenarios(
        user_id=current_user.user_id)
    for scenario in scenario_waiting_objects:
        scenarios_waiting.append([scenario.name, scenario.scenario_id])

    scenario_done_objects = scenario_dao.get_all_closed_custom_scenarios(user_id=current_user.user_id)
    for scenario in scenario_done_objects:
        scenarios_done.append([scenario.name, scenario.scenario_id])

    return render_template("3_created_by_you.html", scenarios_active=scenarios_active, scenarios_waiting=scenarios_waiting, scenarios_done=scenarios_done)

@web_layer.route('/you_are_in', methods=["GET", "POST"])
@login_required
def you_are_in():
    scenarios_active = []
    scenarios_waiting = []
    scenarios_done = []

    scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario_active_objects = scenario_dao.get_all_active_scenarios_where_user_is_driving(user_id=current_user.user_id)
    for scenario in scenario_active_objects:
        scenarios_active.append([scenario.name, scenario.scenario_id])

    scenario_waiting_objects = scenario_dao.get_all_waiting_scenarios_where_user_is_driving(user_id=current_user.user_id)
    for scenario in scenario_waiting_objects:
        scenarios_waiting.append([scenario.name, scenario.scenario_id])

    scenario_done_objects = scenario_dao.get_all_closed_scenarios_where_user_is_driving(user_id=current_user.user_id)
    for scenario in scenario_done_objects:
        scenarios_done.append([scenario.name, scenario.scenario_id])

    return render_template("3_you_are_in.html", scenarios_active=scenarios_active, scenarios_waiting=scenarios_waiting, scenarios_done=scenarios_done)

@web_layer.route('/other_scenarios', methods=["GET"])
@login_required
def other_scenarios():
    """
    This page will show all the scenarios that are not in the other categories (created by you, waiting)
    TODO Sort by date
    TODO Can become quite big with use, will likely need pagination OR a search functionality
    :return:
    """
    scenarios_active = []
    scenarios_done = []

    scenario_dao = MixedTrafficScenarioDAO(current_app.config)

    scenario_active_objects = scenario_dao.get_all_other_active_custom_scenarios(user_id=current_user.user_id)
    for scenario in scenario_active_objects:
        scenarios_active.append([scenario.name, scenario.scenario_id])

    scenario_done_objects = scenario_dao.get_all_other_closed_custom_scenarios(user_id=current_user.user_id)
    for scenario in scenario_done_objects:
        scenarios_done.append([scenario.name, scenario.scenario_id])

    return render_template("3_other_scenarios.html",
                           scenarios_active=scenarios_active, scenarios_done=scenarios_done)



@web_layer.route('/delete_scenario', methods=["POST"])
@login_required
def delete_scenario_created_by_you():
    scenario_id = request.form["scenario_id"]
    # TODO Is the current user the owner of the scenario?
    scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = scenario_dao.get_scenario_by_scenario_id(scenario_id)
    assert scenario.created_by.user_id == current_user.user_id

    # Use the API to delete this scenario
    with current_app.test_client() as http_client:
        response = http_client.delete(url_for("api.scenarios.delete", scenario_id=scenario_id))
        # If the response is OK show the created_byb_you page, otherwise we bubble up the error
        assert response.status_code == 200
        return redirect(url_for("web.created_by_you"))

@web_layer.route('/join_scenario', methods=["GET", "POST"])
@login_required
def join_scenario():
    if request.method == "GET":
        """
        Visualize the scenarios that the current user can join. Those are scenarios with WAITING state in which the
        current user is not yet involve as driver. Scenarios are divided between those owned by current user and the others
        """
        yours_scenarios = []
        others_scenarios = []

        scenario_dao = MixedTrafficScenarioDAO(current_app.config)

        joinable_scenario_objects = scenario_dao.get_all_waiting_scenarios_where_user_is_not_driving(current_user.user_id)

        for scenario in joinable_scenario_objects:
            if scenario.created_by.user_id == current_user.user_id:
                yours_scenarios.append([scenario.name, scenario.scenario_id])
            else:
                others_scenarios.append([scenario.name, scenario.scenario_id])

        return render_template("3_join_scenario.html", yours_scenarios=yours_scenarios, others_scenarios=others_scenarios)

    elif request.method == "POST":

        scenario_id = request.form["scenario_id"]

        with current_app.test_client() as http_client:
            user_data = {
                "user_id": current_user.user_id
            }
            response = http_client.post(url_for("api.scenarios.create_driver", scenario_id=scenario_id), data=user_data)
            # registered as driver
            # Note: We cannot redirect (301) and also specify a response code (200, 400)
            if response.status_code == 204:
                return redirect(url_for("web.scenario_overview", scenario_id=scenario_id))
            else:
                return redirect(url_for("web.join_scenario"))
    else:
        return "Not allowed!", 405