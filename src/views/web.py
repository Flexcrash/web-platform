import json
import os

from model.trajectory import TrajectorySampler, D_METER_MIN, D_METER_MAX, T_SEC_MIN, T_SEC_MAX

from model.mixed_traffic_scenario import MixedTrafficScenarioStatusEnum
from model.vehicle_state import VehicleStatusEnum

from flask import Blueprint
from flask import current_app, redirect, url_for, render_template, request, flash, session, get_flashed_messages, send_file

from persistence.user_data_access import UserDAO
from persistence.mixed_scenario_data_access import MixedTrafficScenarioDAO
from persistence.vehicle_state_data_access import VehicleStateDAO
from persistence.mixed_scenario_template_data_access import MixedTrafficScenarioTemplateDAO

from visualization.mixed_traffic_scenario import generate_drag_and_drop_html, generate_commonroad_xml_file, generate_scenario_designer

from background.scheduler import scheduler

from views.admin import admin_interface

# TODO Move this into an util module
from matplotlib.colors import rgb2hex
from visualization.mixed_traffic_scenario import vehicle_colors

# Import the login manager
from frontend.authentication import login_manager, login_required, current_user, login_user, logout_user


# This blueprint handles the requests for the Web layer
web_layer = Blueprint('web', __name__, url_prefix='/')
web_layer.register_blueprint(admin_interface)


# Cached User Tokens - TODO This can be probably improved, not sure it is safe
# user_id, jwt token
# TODO Not entirely sure what happens when this is deployed in uWSGI. I suspect that the cached elements are not shared among the instances
#   In that case, use Redis or some DB in memory(?) to store the cache.
cached_user_tokens = {}

# Nested blueprint to handle scenario related requests and token-based authentication


def is_safe_url(target):
    """ Validate the next parameter of the login form. It must be a local url"""
    return target.startswith("/") if target is not None else True


@login_manager.user_loader
def load_user(user_id: str):
    """ Returns a user object if exist or None otherwise. Do not automatically refresh the primary token """
    user_id = int(user_id)
    try:
        user_dao = UserDAO()
        user = user_dao.get_user_by_user_id(user_id)

        if user:
            token = user_dao.get_primary_token(user.user_id)

            if token:
                # Set the user as active and authenticated only if everything is fine
                user.is_active = True
                user.is_authenticated = True
                user.personal_jwt_token = token

                return user
            else:
                current_app.logger.warning(f"Cannot find primary token for user {user_id} in the DB.")
        else:
            current_app.logger.warning(f"Cannot find user {user_id} in the DB.")
    except:
        current_app.logger.exception(f"Error while loading user {user_id}")

    return None


@web_layer.before_request
def log_request_info():
    # Reference: https://stackoverflow.com/questions/31637774/how-can-i-log-request-post-body-in-flask
    """ Log each and every request """
    current_app.logger.debug("WEB Request: {} at {} ".format(request.method, request.url))
    current_app.logger.debug(f"SESSION: {session}")

@web_layer.errorhandler(AssertionError)
def assertion_error_handler(error):
    validation_msg = f"{error}"
    current_app.logger.debug(f"Web INVALID REQUEST: {validation_msg}")
    # return validation_msg, 422
    return render_template("errors/error.html", is_user_authenticated=current_user.is_authenticated), 422


@web_layer.errorhandler(Exception)
def special_exception_handler(exception):
    # Make sure that this is not an SQL Integrity Error before raising the 500
    if "IntegrityError" in type(exception).__name__:
        current_app.logger.debug("Web INVALID REQUEST Request: {}".format(exception))
        # Any violation of the DB rules is the result of a request that passed the initial validation (422)
        # return 'Forbidden Request', 403
        return render_template("errors/error.html", is_user_authenticated=current_user.is_authenticated)
    else:
        current_app.logger.exception("Unhandled exception: {}".format(exception))
        # return "Server Error", 500
        return render_template("errors/server_error.html", is_user_authenticated=current_user.is_authenticated), 500

# Does not work out of the box with flask-login
# @web_layer.app_errorhandler(403)
# def not_authorized(e):
#     return render_template('errors/not_authorized.html', is_user_authenticated=current_user.is_authenticated), 403

from background import scheduler
from visualization.mixed_traffic_scenario_template import generate_static_image

@web_layer.app_errorhandler(404)
def page_not_found(e):

    # TODO Refactor this to use the API instead of directly accessing the DAOs

    # This solution does not work for 404: https://stackoverflow.com/questions/62067691/capture-request-headers-whenever-a-static-file-is-requested-in-flask-app
    # Extract the requested (not found) path
    path = request.path
    try:
        #
        # Some static files, like scenario images/interactive snippet and scenario template images, are
        # wiped out during reboot in production, but the data are in the database. As safety net, check and
        # recreate them if necessary
        # Extract file name and extension
        file_name = str(path).split("/")[-1]
        file_type = str(file_name).split(".")[-1]

        if current_app.config["TEMPLATE_IMAGES_FOLDER"] in path and file_type == 'png' and request.method == 'GET':
            # This is a request to an image representing a template.
            # Extract the template id form the file name and check if the template exists
            # NOTE: Having utility methods to do this will be more robust to changes in naming conventions
            scenario_template_id = file_name.replace(f".{file_type}", "")
            # This is a direct access to the DB. Consider whether a boolean call to an API is better
            mixed_traffic_scenario_template_dao = MixedTrafficScenarioTemplateDAO(current_app.config)
            scenario_template = mixed_traffic_scenario_template_dao.get_template_by_id(scenario_template_id)
            if scenario_template is not None:
                # Render the image in "synch" mode
                template_image_path = generate_static_image(current_app.config["TEMPLATE_IMAGES_FOLDER"], scenario_template)
                # Send the file
                return send_file(template_image_path)
        elif current_app.config["SCENARIO_IMAGES_FOLDER"] in path and file_type == 'png' and \
                (request.method == 'GET' or request.method == 'HEAD'): # We need to force also on HEAD but must limit head to the visible ones

            # This is a request to an resource representing a scenario

            # Note: if the request is HEAD that's the web page refresh mechanism in action

            # Extract the template id form the file name and check if the template exists
            # NOTE: Having utility methods to do this will be more robust to changes in naming conventions

            driver_id = None
            driver = None
            scenario_id = None
            time_stamp = None
            goal_region_as_rectangle = None

            # Parse the file name tokens:
            file_name_tokens = file_name.replace(f".{file_type}", "").split("_")
            scenario_id = int(file_name_tokens[1])
            time_stamp = int(file_name_tokens[3])

            # Focus on driver, needs probably the goal region as well
            if len(file_name_tokens) > 4:
                driver_id = int(file_name_tokens[5])

            # This is a direct access to the DB. Consider whether a boolean call to an API is better
            mixed_traffic_scenario_dao = MixedTrafficScenarioDAO(current_app.config)
            scenario = mixed_traffic_scenario_dao.get_scenario_by_scenario_id(scenario_id)
            if scenario is not None:
                # Retrieve the states to render
                scenario_states = mixed_traffic_scenario_dao.vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(
                    scenario.scenario_id, time_stamp)

                # Retrieve the driver and its goal_region
                for d in scenario.drivers:
                    # Driver ID or User ID?
                    if d.user_id == driver_id:
                        driver = d
                        goal_region_as_rectangle = mixed_traffic_scenario_dao.get_goal_region_for_driver_in_scenario(driver, scenario)
                        break

                # Render the image(s) in "synch" mode
                scheduler.render_in_background(current_app.config["SCENARIO_IMAGES_FOLDER"],
                                               scenario, scenario_states,
                                               focus_on_driver=driver,
                                               goal_region_as_rectangle = goal_region_as_rectangle,
                                               force_render_now = True)
                # TODO This does not really work !
                # Send the requested file
                file_path = os.path.join(f"{current_app.config['TEMPLATE_IMAGES_FOLDER']}", file_name)
                return send_file(file_path)
        elif current_app.config["SCENARIO_IMAGES_FOLDER"] in path and file_type == 'xml' and \
                (request.method == 'GET'):

            # Parse the file name tokens:
            file_name_tokens = file_name.replace(f".{file_type}", "").split("_")
            scenario_id = int(file_name_tokens[1])

            # TODO Move all the logic into an API call to return the XML file content everytime it is called
            #   so we will be able to export data also from not yet done scenarios
            #   Add options to filter out elements (e.g., planning problems, intervals, etc.)

            # Retrieve the Scenario Data and generate the XML File in the expected folder
            scenario_dao = MixedTrafficScenarioDAO(current_app.config)
            scenario = scenario_dao.get_scenario_by_scenario_id(scenario_id)
            assert scenario, f"Scenario {scenario_id} does not exist"
            assert MixedTrafficScenarioStatusEnum.DONE == scenario.status, f"Scenario {scenario_id} is in the wrong state"

            initial_states = {}
            goal_region_as_rectangles = {}
            scenario_states = {}
            #
            for driver in scenario.drivers:
                initial_states[driver.user_id] = scenario_dao.get_initial_state_for_driver_in_scenario(driver, scenario)
                goal_region_as_rectangles[driver.user_id] = scenario_dao.get_goal_region_for_driver_in_scenario(driver, scenario)
                scenario_states[driver.user_id] = scenario_dao.get_all_states_for_driver_in_scenario(driver, scenario)

            filename = _generate_scenario_xml_rel_paths_for(scenario_id)
            # TODO Get this from the configuration somehow?
            file_path = os.path.join("static", filename)

            # Render the scenario as commonroad xml file
            generate_commonroad_xml_file(file_path, scenario, initial_states, goal_region_as_rectangles, scenario_states)

            # Serve the file
            return send_file(file_path)

    except Exception as exc_info:
        # Rendering might fail for many reasons, in that case default to 404
        current_app.logger.warning(f"Error while serving 404 to {request.method} {request.path}")

    # http://localhost:5000/static/manual-testing/scenario_template_images/1.png
    return render_template('errors/page_not_found.html', is_user_authenticated=current_user.is_authenticated), 404


@web_layer.route('/', methods=["GET"])
def landing_page():
    """
    Visualizes the landing page visible by everybody.
    TODO: The landing page contains the details to register to the platform
    """
    return render_template("0_landing_page.html"), 200


@web_layer.route('/home')
@login_required
def index():
    return render_template("2_start_menu.html"), 200

@web_layer.route('/login_user', methods=['GET', 'POST'])
def login():
    if request.method == "GET":
        # Default to FALSE
        sign_up_enabled = current_app.config["SING_UP_DISABLED"] if "SING_UP_DISABLED" in current_app.config else False
        return render_template("1_login.html", sign_up_enabled=sign_up_enabled, next=request.args.get('next')), 200
    else:
        # TODO Probably we could use the API to authenticate this user
        # Authenticate the user and generate a token
        email, password = request.form['log_email'], request.form['log_pass']

        next = request.form['next'] if "next" in request.form else None

        user_dao = UserDAO()
        if user_dao.verify_password(email, password):
            user = user_dao.get_user_by_email(email)
            # TODO Handle this with DB. By default is False, so the user will be ignored
            # Create a token for user
            try:
                # TODO Make sure that user can not have multiple tokens
                user_dao.generate_token(user.user_id, is_primary=True)
            except Exception as e:
                print(str(e))
            user.personal_jwt_token = user_dao.get_primary_token(user.user_id)
            user.is_active = True
            user.is_authenticated = True
            # Ensure Login-Flask knows about the user. With sessions and production setup, the remember parameter is needed.
            login_user(user, remember=True)
            # This is to automatically redirect to the next page.
            # is_safe_url should check if the url is safe for redirects.
            # See https://stackoverflow.com/questions/60532973/how-do-i-get-a-is-safe-url-function-to-use-with-flask-and-how-does-it-work
            if not is_safe_url(next):
                assert False, "Invalid page requested"
            else:
                return redirect(next or url_for('web.index'))
        else:
            # Note: Do not return a 401 or 403
            return render_template("1_login.html", error="Invalid Credentials")

@web_layer.route("/logout", methods=['GET', 'POST'])
@login_required
def logout():

    # Clean up cached token
    if current_user.user_id in cached_user_tokens:
        del cached_user_tokens[current_user.user_id]

    # TODO Add here the logout functionality of the AUTH API when ready. This will basically invalidate the token corresponding to this Web interactions
    # Clean up session and Web part using flask_login.logout_user
    logout_user()

    return redirect(url_for("web.landing_page"))

@web_layer.route('/interactive_scenario_designer', methods=["GET"])
@login_required
def scenario_designer():
    """
    Setup the interactive scenario page and cleanup the session data

    :return:
    """

    scenario_data = session.pop("scenario_data", {})

    # This page expects the following data from the session. If they are not there send back to scenario_overview
    if "creator_user_id" not in scenario_data:
        # Clean up other messages?
        flash("Invalid request. Please retry", "error")
        return redirect(url_for("web.create_scen"))

    creator_user_id = int(scenario_data["creator_user_id"])
    assert creator_user_id == current_user.user_id, "Invalid user !"

    if "scenario_template_id" not in scenario_data:
        flash("There was an error. Please select the scenario template again.", "error")
        return redirect(url_for("web.create_scen"))

    template_id = int(scenario_data["scenario_template_id"])
    mixed_traffic_scenario_template_dao = MixedTrafficScenarioTemplateDAO(current_app.config)
    scenario_template = mixed_traffic_scenario_template_dao.get_template_by_id(template_id, skip_active_check=True)
    assert scenario_template, f"Cannot find template {template_id}"

    html_snippet = generate_scenario_designer(scenario_template, scenario_data=scenario_data)

    return render_template("4_scenario_designer.html",
                           html_snippet=html_snippet,
                           creator_user_id=creator_user_id,
                           template_id=template_id)


@web_layer.route('/setup_custom_scenario', methods=["GET"])
@login_required
def create_scen():

    # Clean up any data about scenarios
    session.pop("scenario_data", {})

    # List all the existing templates to get their id and description using the API
    with current_app.test_client() as http_client:
        response = http_client.get(url_for("api.templates.get_scenario_templates"),
                                   headers={'Authorization': current_user.personal_jwt_token})
        if response.status_code == 401:
            return redirect(url_for("web.logout"))
        # Parse the respons into a JSON Object
        scenario_templates = json.loads(response.data)

    # Extract all the template Ids and description
    scenario_template_ids = [st["template_id"] for st in scenario_templates]
    scenario_template_descriptions = [st["description"] for st in scenario_templates]

    # Create the relative file paths
    scenario_template_file_paths = [
        os.path.join(current_app.config["TEMPLATE_IMAGES_FOLDER"], ".".join([str(st_id), "png"]))
        for st_id in scenario_template_ids]

    # Make relative file paths, relative to STATIC FOLDER
    # https://stackoverflow.com/questions/8693024/how-to-remove-a-path-prefix-in-python
    relative_path = 'static'

    scenario_template_rel_paths = [os.path.relpath(full_path, relative_path) for full_path in
                                   scenario_template_file_paths]

    # For the list of files pointing to the images of the scenarios: <img src="{{url_for('static', filename='folder/file.png')}}">
    scenario_template_image_urls = [url_for("static", filename=fname) for fname in scenario_template_rel_paths]

    # Visualize the page with all the templates
    return render_template("3_scenario_template_selection.html",
                           scenario_template_image_urls_and_ids=list(
                               zip(scenario_template_image_urls, scenario_template_ids, scenario_template_descriptions)))

# Implements redirect-after-post
@web_layer.route("/select_template", methods=["POST"])
def select_template():
    """
    Make sure we initialize the session object here
    :return:
    """
    data = dict(request.form)

    assert "creator_user_id" in data, "Missing creator id"
    assert "scenario_template_id" in data, "Missing template id"

    creator_user_id = int(data["creator_user_id"])
    scenario_template_id = int(data["scenario_template_id"])

    # Store this into the session the partial data about the scenario
    session["scenario_data"] = {
        "creator_user_id": creator_user_id,
        "scenario_template_id": scenario_template_id
    }

    # Redirect to the scenario creator page
    return redirect(url_for("web.scenario_designer"))

def create_scen_old_logic():
    # List all the existing templates to get their ID using the API
    with current_app.test_client() as http_client:
        response = http_client.get(url_for("api.templates.get_scenario_templates"),
                                    headers={'Authorization': current_user.personal_jwt_token})
        if response.status_code == 401:
            return redirect(url_for("web.logout"))
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

    user_dao = UserDAO()
    users_data = user_dao.get_all_users()
    users = {}
    for user in users_data:
        users[user.username] = user.user_id

    print(session)
    #session["scenario_data"] = {}
    #session["scenario_data"]["user_data"] = {}
    #session["scenario_data"]["user_data"]["UD_1"] = {"x": 0, "y": 0, "player_type": "User", "initial_speed": 5,
    #                                                  "color": "b", "user_id": session['scenario_data']["creator_user_id"]}

    return render_template("3_custom_scenario_setup.html",
                           scenario_template_image_urls_and_ids = list(zip(scenario_template_image_urls, scenario_template_ids)), all_users=users)

@web_layer.route("/add_player", methods=["POST"])
def add_player():
    data = dict(request.form)
    print("DATA: ", data)

    # new_user
    player_type = data["player_type"]
    color = data["colorPicker"]
    initial_speed = data["initialSpeed"]

    scenario_data = session["scenario_data"]

    if player_type == "AV":
        scenario_data["n_avs"] = int(scenario_data["n_avs"]) + 1
    elif player_type == "User":
        new_user_id = data["newUserID"]
        n_users = int(scenario_data["n_users"])

        #reorder the x- and y-array so User and AV vehicles dont swap positions
        #if type(data["x_array"]) != list:
        #    x_array = data["x_array"][1:-1].split(",")
        #    y_array = data["y_array"][1:-1].split(",")
        #else:
        #    x_array = data["x_array"]
        #    y_array = data["y_array"]

        #if len(x_array) > n_users:
        #    x_val = x_array.pop()
        #    y_val = y_array.pop()
        #    x_array.insert(n_users, x_val)
        #    y_array.insert(n_users, y_val)

        scenario_data["n_users"] = n_users + 1
        scenario_data["users"].append(new_user_id)


    template_id = data["template_id"]
    mixed_traffic_scenario_template_dao = MixedTrafficScenarioTemplateDAO(current_app.config)
    scenario_template = mixed_traffic_scenario_template_dao.get_template_by_id(template_id)

    name = scenario_data["name"]
    duration = scenario_data["duration"]
    creator_user_id = scenario_data["creator_user_id"]
    n_users = int(scenario_data["n_users"])
    n_avs = int(scenario_data["n_avs"])
    users = scenario_data["users"]
    #users_list = users.split(",") if len(users) > 0 else []
    unassigned_users = n_users - len(users)
    vehicles = {"n_avs": n_avs, "unassigned_users": unassigned_users, "users_list": users}
    v_pos = None
    if "x_array" in data.keys():
        v_pos = {"x": data["x_array"], "y": data["y_array"]}

    #for user in scenario_data["user_data"].keys():
    #    x_array.append(scenario_data["user_data"][user]["initial_x"])
    #    y_array.append(scenario_data["user_data"][user]["initial_y"])
    #print("X & Y: ", x_array, y_array)

    vehicles_as_string = json.dumps(vehicles)
    html_snippet = generate_drag_and_drop_html(scenario_template, template_id, vehicles_as_string,
                                               vehicle_positions=v_pos)
    #print(session["scenario_data"])

    return render_template("4_vehicle_positions.html",
                           html_snippet=html_snippet, scenario_template=scenario_template,
                           name=name, duration=duration,
                           n_users=n_users,
                           creator_user_id=creator_user_id, template_id=template_id,
                           #
                           n_avs=n_avs,
                           unassigned_users=unassigned_users,
                           users_list=users)

@web_layer.route('/get-vehicle-positions', methods=['GET', 'POST'])
@login_required
def get_vehicle_positions(scenario_data=None):
    # Container for all the data about this scenario including metadata from the custom scenario page and data from
    # previous submissions of the form on this page
    scenario_data = None
    print("GVP: ", session)

    if request.method == 'GET':
        # We got the data from a previous failed request
        scenario_data = session.get('scenario_data', None)
        if scenario_data:
            session.pop('scenario_data')

        validation = session.get('validation', None)
        if validation:
            session.pop('validation')
            flash(validation, 'alert-danger')

    if request.method == 'POST':
        if scenario_data == None:
            # We got the data from the custom scenario selection page.
            scenario_data = request.form
            session['scenario_data'] = {}
            for k, v in scenario_data.items():
                session['scenario_data'][k] = v

            # creator_user_id = int(session['scenario_data']['creator_user_id'])
            # session['scenario_data']['users'] = [creator_user_id]
            # session['scenario_data']['user_data'] = {}
            # session['scenario_data']['user_data'][creator_user_id] = {'initial_x': 0, 'initial_y': 0, 'goal_x': 0, 'goal_y': 0, 'initial_speed': 5}
            # print("POST: ", session)
            # Keep the data around. Store the session
            session.modified = True
        else:
            scenario_data = scenario_data
            for k, v in scenario_data.items():
                session['scenario_data'][k] = v
            session.modified = True


    assert scenario_data is not None, "Invalid scenario data!"

    name = scenario_data["name"]
    duration = scenario_data["duration"]
    creator_user_id = scenario_data["creator_user_id"]
    template_id = scenario_data["template_id"]
    n_users = int(scenario_data["n_users"])
    n_avs = int(scenario_data["n_avs"])

    if len(scenario_data["users"]) == 0:
        users = [scenario_data['creator_user_id']]
        users_list = users
        session["scenario_data"]["users"] = users
    else:
        users = scenario_data["users"]
        users_list = users.split(",") if len(users) > 0 else []

    unassigned_users = n_users - len(users_list)
    vehicles = {"n_avs": n_avs, "unassigned_users": unassigned_users, "users_list": users_list}

    # scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    mixed_traffic_scenario_template_dao = MixedTrafficScenarioTemplateDAO(current_app.config)
    scenario_template = mixed_traffic_scenario_template_dao.get_template_by_id(template_id, skip_active_check=True)

    vehicles_as_string = json.dumps(vehicles)

    # TODO: if there are scenario_data, use them to initialize the positions of the drag_and_drop elements

    # output_folder, scenario_template, template_id, vehicles
    html_snippet = generate_drag_and_drop_html(scenario_template, template_id, vehicles_as_string)

    # scenario.drivers
    return render_template("4_vehicle_positions.html",
                           html_snippet=html_snippet, scenario_template=scenario_template,
                           name=name, duration=duration,
                           n_users=n_users,
                           creator_user_id=creator_user_id, template_id=template_id,
                           #
                           n_avs=n_avs,
                           unassigned_users=unassigned_users,
                           users_list=users_list)

@web_layer.route('/webcreate', methods=['POST'])
@login_required
def create():
    """
        Create the scenario from the data in the form.
        If the data is not valid, re-render the page and show an error message.
    """
    data = dict(request.form)
    with current_app.test_client() as test_client:
        # This call changes the current session object because we are issue another request to the app
        # The original session is visible outside the context manager
        response = test_client.post(url_for("api.scenarios.create"), data=request.form,
                                    headers={'Authorization': current_user.personal_jwt_token})

    if response.status_code == 200 or response.status_code == 201 or response.status_code == 202:
        # Retrieve the scenario from the response
        scenario_dto = json.loads(response.data)
        # NOTE: We assume at this point the scenario cannot be "DONE" so the export link is not necessary
        return redirect(url_for("web.scenario_overview", scenario_id=scenario_dto["scenario_id"]))
    else:
        # Setup the session data with the form.data so we do not lose data
        session["scenario_data"] = data
        # Notify the user that there was a problem with the scenario generation
        flash("The scenario cannot be created. Please retry", "error")
        # Redirect-after-post
        return redirect(url_for("web.scenario_designer"))

@web_layer.route('/scenarios/<scenario_id>', methods=['GET', 'POST'])
@login_required
def scenario_overview(scenario_id):

    # Retrieve the scenario object
    scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = scenario_dao.get_scenario_by_scenario_id(scenario_id)

    # TODO: Handle better 404 here
    if scenario is None:
        # This does not work, i.e., does not triggere the decorator: return "Scenario does not exist", 404
        return render_template('errors/page_not_found.html', is_user_authenticated=current_user.is_authenticated), 404

    # assert scenario is not None, "Scenario does not exist"

    scenario_state_dtos = []
    scenario_image_urls = []

    # If the status is in WAITING, it means that we are waiting for people to join, there are no vehicle states
    # that can be visualized
    current_user_driver_state = None

    current_user_is_driving = any([driver.user_id == current_user.user_id for driver in scenario.drivers])

    if scenario.status != MixedTrafficScenarioStatusEnum.WAITING:
        # Is the current user also a driver? If not, unless the scenario is ready nobody can see it
        # focus_on_driver = any([driver.user_id == current_user.user_id for driver in scenario.drivers])

        # The following rules control the creation of the links that enable submitting states
        # If no action was submitted -> PENDING -> Do not create any link
        # If an action (but not all submitted) -> WAITING -> Do not create any link
        # If all actions were submitted -> ACTIVE -> Create link to DYNAMIC page
        # If the following scenario state is ACTIVE or CRASH or GOAL_REACHED, the current one CANNOT BE -> DONE -> Create link to STATIC page

        # Collect all the status information and images

        # We need to refer to the scenario ACTUAL duration when it is in state DONE!
        visualized_duration = scenario.duration
        if scenario.status == MixedTrafficScenarioStatusEnum.DONE:
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

        if current_user_is_driving:
            # Retrieve the last known state of the current user driver in this scenario
            vehicle_state_dao = VehicleStateDAO(current_app.config, scenario_dao)
            last_timestamp = None
            for timestamp in range(0, visualized_duration + 1):
                if scenario_states[timestamp] != VehicleStatusEnum.PENDING:
                    last_timestamp = timestamp
            assert last_timestamp is not None
            current_user_driver_state = [ vs for vs in vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario_id, last_timestamp) if vs.user_id == current_user.user_id][0]

        for timestamp in range(0, visualized_duration + 1):
            scenario_state_dtos.append({
                "timestamp": timestamp,
                "status": scenario_states[timestamp]}
            )

            if(scenario_states[timestamp] != VehicleStatusEnum.PENDING):
                # Generate the right image urls for the each state
                scenario_image_urls.append(
                    url_for("static", filename=_generate_scenario_image_rel_paths_for(scenario_id, timestamp))
                )
    how_many_active_user_drivers = sum(1 for d in scenario.drivers if d.user is not None and not d.user.username.startswith("bot_"))
    how_many_active_avs_drivers = sum(1 for d in scenario.drivers if d.user is not None and d.user.username.startswith("bot_"))

    # Include colors and sort them
    # Sort in place if any

    scenario.drivers.sort(key=lambda d: d.driver_id)

    for driver_index, driver in enumerate(scenario.drivers, start=0):
        setattr(driver, "color", rgb2hex(vehicle_colors[driver_index]))

    download_file_url = None
    if scenario.status == MixedTrafficScenarioStatusEnum.DONE:
        download_file_url = url_for("static", filename=_generate_scenario_xml_rel_paths_for(scenario_id))


    # Visualize the ENTIRE scenario
    return render_template("4_scenario_overview.html",
                           current_user_is_driving=current_user_is_driving,
                           how_many_users_missing = scenario.n_users - how_many_active_user_drivers,
                           how_many_av_missing = scenario.n_avs - how_many_active_avs_drivers,
                           current_user_driver_state=current_user_driver_state,
                           scenario=scenario,
                           scenario_state_dtos=scenario_state_dtos,
                           scenario_image_urls = scenario_image_urls,
                           download_file_url=download_file_url)


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
                                           user_id=current_user.user_id),
                                   data=states_data,
                                   headers={'Authorization': current_user.personal_jwt_token})

    if response.status_code >= 300:
        return "", 500
    else:
        return redirect(url_for("web.scenario_overview", scenario_id=scenario_id))

def _generate_scenario_xml_rel_paths_for(scenario_id):
    # Generate the link to the XML file that correspond to this scenario.

    scenario_xml_file_name = "_".join(["scenario", str(scenario_id)])

    # Add extension
    scenario_xml_file_path = os.path.join(current_app.config["SCENARIO_IMAGES_FOLDER"],
                                        ".".join([scenario_xml_file_name, "xml"]))

    # Make the path relative to STATIC FOLDER
    # TODO This probably should be
    relative_path = 'static'
    return os.path.relpath(scenario_xml_file_path, relative_path)

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
        if scenario_state_at_timestamp == MixedTrafficScenarioStatusEnum.ACTIVE:
            if scenario_dao.is_driver_in_game(scenario, current_user):
                # Visualize the dynamic page instead
                return redirect(url_for("web.scenario_state", scenario_id=scenario_id, timestamp=timestamp))
        elif scenario_state_at_timestamp != MixedTrafficScenarioStatusEnum.DONE:
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
        if scenario_state_at_next_timestamp == MixedTrafficScenarioStatusEnum.DONE:
            next_state_url = url_for("web.scenario_state_static", scenario_id=scenario_id, timestamp=timestamp + 1)
        elif scenario_state_at_next_timestamp == MixedTrafficScenarioStatusEnum.ACTIVE:
            next_state_url = url_for("web.scenario_state", scenario_id=scenario_id, timestamp=timestamp + 1)
        else:
            next_state_url = None
    else:
        # Otherwise there's no next state
        next_state_url = None

    # Add the link to the scenario_url=scenario_url,
    scenario_url = url_for("web.scenario_overview", scenario_id=scenario_id)

    # Fetch the info about each vechicle state:
    vehicle_state_dao = VehicleStateDAO(current_app.config, scenario_dao)
    vehicle_states_at_timestamp = vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario_id=scenario_id,
                                                                                                   timestamp=timestamp)
    # Fetch data about the drivers and monkey path the objects passed to the renderingi nterface
    user_dao = UserDAO()
    # Force the colors!
    current_user_index = None
    # Sort the states:
    sorted_vehicle_states = sorted(vehicle_states_at_timestamp, key=lambda vs: vs.driver_id)
    for vehicle_index, vehicle_state in enumerate(sorted_vehicle_states, start=0):
        user = user_dao.get_user_by_user_id(vehicle_state.user_id)
        setattr(vehicle_state, "color", rgb2hex(vehicle_colors[vehicle_index]))
        # vehicle_state.username
        setattr(vehicle_state, "username", user.username)
        # vehicle_state.is_current_user
        setattr(vehicle_state, "is_current_user", user.user_id == current_user.user_id)

    if current_user_index:
        # Make sure that the current user is always on top
        sorted_vehicle_states.insert(0, sorted_vehicle_states.pop(current_user_index))

    # Render the template
    return render_template("6_view_scenario_state_static.html",
                           rendered_state_url=rendered_state_url,
                           scenario_url=scenario_url,
                           prev_state_url=prev_state_url,
                           next_state_url=next_state_url,
                           vehicle_states=sorted_vehicle_states)


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
    t_sec_max = args.get('tmax', T_SEC_MAX) # TODO This should depend on the h/p
    d_meter_min = args.get('dmin', D_METER_MIN)
    d_meter_max = args.get('dmax', D_METER_MAX)

    # Speed is based on current speed at the moment

    scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = scenario_dao.get_scenario_by_scenario_id(scenario_id)

    # TODO This is NOT OK WE STILL HAVE TO CHECK IF THE TIMESTAMP IS THE LAST ONE!
    scenario_status_at_timestamp = scenario_dao.get_scenario_state_at_timestamp(scenario_id, timestamp)

    if scenario_status_at_timestamp == MixedTrafficScenarioStatusEnum.PENDING:
        # PENDING STATES CANNOT BE VISUALIZED, because we need to input some actions in the previous ones (ACTIVE!)
        # The current user is NOT authorized to see the page
        return "", 401

    # Is the current user also a driver? If not, unless the scenario is ready nobody can see it
    focus_on_driver = any([driver.user_id == current_user.user_id for driver in scenario.drivers])


    # TODO Note: At the moment ACTIVE IS ATTACHED TO ALL, BUT API DOES NOT LET DO ANYTHING FOR THE WRONG STATE
    #   NOT RELIABLE
    if focus_on_driver and scenario_status_at_timestamp == MixedTrafficScenarioStatusEnum.ACTIVE and scenario_dao.is_driver_in_game(scenario, current_user):
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
        vehicle_state_dao = VehicleStateDAO(current_app.config, scenario_dao)

        current_state = next(vs for vs in vehicle_state_dao.get_vehicle_states_by_scenario_id_at_timestamp(scenario_id, timestamp)
                             if vs.user_id == current_user.user_id)

        return render_template("6_view_scenario_state_dynamic_2.html",
                               initial_timestamp=timestamp,
                               scenario_id=scenario_id,
                               driver_id=current_state.driver_id,
                               embeddable_html=embeddable_html,
                               # Just round this to Km/h
                               current_speed_km_h=int(current_state.speed_ms * 3.6),
                               host_url=request.host_url,
                               v=current_state.speed_ms,
                               d=0.0, # No lateral displacement
                               t=2.0, # Not sure what's the min value, it depends on the speed,but definitively above 1.0
                               h=5.0, # Plan for 5.0 sec, after this the planner does not really work fine?!
                               p=2.0, # Drive for 2.0 sec
                               # Default Values - What are those?
                               initial_drive_for=2.0,
                               initial_plan_for_sec=5.0,
                               #
                               initial_action_speed="maintain your speed", # v
                               initial_action_lat="staying on course", # d
                               initial_action_time= "", # h
                               snap_to_road=snap_to_road,
                               initial_action_snap_to_road = "following the road" if snap_to_road else "driving free")

        # initial_state = scenario_dao.get_initial_state_for_driver_in_scenario(current_user, scenario)
        # goal_region_as_rectangle = scenario_dao.get_goal_region_for_driver_in_scenario(current_user, scenario)
        #
        # trajectory_sampler = TrajectorySampler(scenario, initial_state, goal_region_as_rectangle, snap_to_road)
        #
        # feasible_trajectories = trajectory_sampler.sample_trajectories(current_state,
        #                                        t_sec_min= t_sec_min, t_sec_max = t_sec_max,
        #                                        d_meter_min = d_meter_min, d_meter_max = d_meter_max)

        # Create the index v => d => t
        # indexed_trajectories = {}
        #
        # v_samples = trajectory_sampler.get_sampled_v()
        # d_samples = trajectory_sampler.get_sampled_d()
        # t_samples = trajectory_sampler.get_sampled_t()
        #
        # # Note that many of those indices might be empty, so we need to filter them out!
        # for v_index in range(0, len(v_samples)):
        #     indexed_trajectories[v_index] = {}
        #     for d_index in range(0, len(d_samples)):
        #         indexed_trajectories[v_index][d_index] = {}
        #         for t_index in range(0, len(t_samples)):
        #             indexed_trajectories[v_index][d_index][t_index] = {}
        #
        # # Fill up the values
        # for trajectory in feasible_trajectories:
        #
        #     v_i = v_samples.index(trajectory.the_v)
        #     d_i = d_samples.index(trajectory.the_d)
        #     t_i = t_samples.index(trajectory.the_t)
        #
        #     # We need something JSON serializable
        #     indexed_trajectories[v_i][d_i][t_i] = [{
        #         "timestamp": state.timestamp,
        #         "position_x": state.position_x,
        #         "position_y": state.position_y,
        #         "rotation": state.rotation,
        #         "speed_ms": state.speed_ms,
        #         "acceleration_m2s": state.acceleration_m2s} for state in trajectory.planned_states]
        #
        # # Render the template with the embedded HTML
        # # References:
        # #   - https://stackoverflow.com/questions/65318395/how-to-render-html-for-variables-in-flask-render-template
        #
        # # Provide the actual values of sampled dimensions and timestamp/time_step
        # v = trajectory_sampler.get_sampled_v()
        # d = trajectory_sampler.get_sampled_d()
        # t = trajectory_sampler.get_sampled_t()
        # h = [t_horizon * trajectory_sampler.dT for t_horizon in range(0, trajectory_sampler.N+1)]

        # # Add the link to the previous state if any
        # if int(timestamp) <= 0:
        #     prev_state_url = None
        # else:
        #     prev_state_url = url_for("web.scenario_state_static", scenario_id=scenario_id, timestamp=int(timestamp) - 1)
        #
        # next_state_url = None # Trivally so

        # Add the link to the scenario_url=scenario_url,
        # scenario_url = url_for("web.scenario_overview", scenario_id=scenario_id)
        # OLD TEMPLATE
        # return render_template("6_view_scenario_state_dynamic.html",
        #                        scenario_url=scenario_url,
        #                        prev_state_url=prev_state_url,
        #                        next_state_url=next_state_url,
        #                        embeddable_html=embeddable_html,
        #                        snap_to_road=snap_to_road,
        #                        trajectories = indexed_trajectories,
        #                        v_index = len(v) - 1,
        #                        d_index = len(d) - 1,
        #                        t_index = len(t) - 1,
        #                        # For the moment the horizon is as long as the trajectory sampler makes them
        #                        h_index = trajectory_sampler.N,
        #                        v = v,
        #                        d = d,
        #                        t = t,
        #                        h = h,
        #                        initial_timestamp=timestamp,
        #                        scenario_id=scenario_id)
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
    try:
        scenario_id = int(request.form["scenario_id"])
    except Exception:
        return AssertionError("Invalid scenario id")

    # Is the current user the owner of the scenario the one asking to remove the scenario?
    # TODO Can we move this to the API?
    scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    scenario = scenario_dao.get_scenario_by_scenario_id(scenario_id)
    # TODO This should return 403!
    assert scenario.created_by == current_user.user_id, "The user cannot perform this action"

    # Use the API to delete this scenario
    with current_app.test_client() as http_client:
        response = http_client.delete(url_for("api.scenarios.delete", scenario_id=scenario_id),
                                    headers={'Authorization': current_user.personal_jwt_token})
        # If the response is OK show the created_byb_you page, otherwise we bubble up the error
        assert response.status_code == 200

    return redirect(url_for("web.created_by_you"))

@web_layer.route('/leave_scenario', methods=["POST"])
@login_required
def leave_scenario():
    scenario_id = request.form["scenario_id"]

    with current_app.test_client() as http_client:
        # TODO Refactor into api.scenarios.driver
        response = http_client.delete(url_for("api.scenarios.delete_driver", scenario_id=scenario_id, user_id=current_user.user_id),
                                    headers={'Authorization': current_user.personal_jwt_token})
        # if response.status_code == 204:
    return redirect(url_for("web.scenario_overview", scenario_id=scenario_id))


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
            if scenario.created_by == current_user.user_id:
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
            response = http_client.post(url_for("api.scenarios.create_driver", scenario_id=scenario_id), data=user_data,
                                    headers={'Authorization': current_user.personal_jwt_token})


        # registered as driver
        # Note: We cannot redirect (301) and also specify a response code (200, 400)
        if response.status_code == 204:
            return redirect(url_for("web.scenario_overview", scenario_id=scenario_id))
        else:
            return redirect(url_for("web.join_scenario"))
    else:
        return "Not allowed!", 405