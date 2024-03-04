from typing import Tuple

# Import the login manager
from frontend.authentication import login_manager, login_required, current_user

from persistence.user_data_access import UserDAO
from persistence.mixed_scenario_data_access import MixedTrafficScenarioDAO
from persistence.vehicle_state_data_access import VehicleStateDAO
from persistence.mixed_scenario_template_data_access import MixedTrafficScenarioTemplateDAO

from flask import current_app, request, url_for, render_template, redirect, flash
from flask import Blueprint

# This blueprint handles all the requests that require admin rights
admin_interface = Blueprint('admin', __name__, url_prefix='/admin')


@admin_interface.route('/', methods=["GET", "POST"])
@login_required
def admin_page():
    """ Shows the admin page """
    if not current_user.is_admin:
        # return "You are not authorized to see this page!", 403
        return render_template('errors/not_authorized.html', is_user_authenticated=current_user.is_authenticated), 403
    else:
        if request.method == "GET":
            # Render all the scenarios
            scenario_dao = MixedTrafficScenarioDAO(current_app.config)

            scenarios_dto = []
            all_scenarios = scenario_dao.get_all_scenarios()
            for scenario in all_scenarios:
                scenarios_dto.append([scenario.name, scenario.scenario_id])

            scenario_template_dao = MixedTrafficScenarioTemplateDAO(current_app.config)

            scenario_templates_dto = []
            all_scenario_templates = scenario_template_dao.get_all_templates()
            for scenario_template in all_scenario_templates:
                scenario_templates_dto.append([scenario_template.template_id, scenario_template.is_active])

            # TODO Why this has no parameters, but the other do?
            user_dao = UserDAO()

            user_dtos = []
            all_human_users = [ u for u in user_dao.get_all_users() if not u.username.startswith("bot_")]
            for human_user in all_human_users:
                user_dtos.append([human_user.user_id, human_user.username, human_user.is_admin])

            return render_template("admin.html",
                                scenario_template_dtos=scenario_templates_dto,
                                scenario_dtos=scenarios_dto,
                                user_dtos = user_dtos), 200

        elif request.method == "POST":

            if "scenario_template_id" in request.form:
                # Activate or deactivate the scenario template
                scenario_template_dao = MixedTrafficScenarioTemplateDAO(current_app.config)
                scenario_template_id = request.form['scenario_template_id']
                #
                if f"is_enabled_{scenario_template_id}" in request.form:
                    scenario_template_dao.enable_template(scenario_template_id)
                else:
                    scenario_template_dao.disable_template(scenario_template_id)

            if "user_id" in request.form:
                # Activate or deactivate the scenario template
                user_dao = UserDAO()
                user_id = int(request.form['user_id'])

                assert user_id != current_user.user_id, "You cannot alter your admin rights!"
                #
                if f"is_admin_{user_id}" in request.form:
                    user_dao.make_admin_user(user_id)
                else:
                    user_dao.make_regular_user(user_id)

            if "delete_scenario" in request.form:
                # Delete the selected scenario and redirect to adming page
                scenario_dao = MixedTrafficScenarioDAO(current_app.config)
                scenario_id = request.form['scenario_id']
                scenario_dao.delete_scenario_by_id(scenario_id)

            return redirect(url_for("web.admin.admin_page"))

@admin_interface.route('/register_user', methods=["GET", "POST"])
@login_required
def register_user():
    if not current_user.is_admin:
        # return "You are not authorized to see this page!", 403
        return render_template('errors/not_authorized.html',
                               is_user_authenticated=current_user.is_authenticated), 403


    if request.method == "GET":
        return render_template("register_user.html"), 200
    else:
        try:
            # Check mandatory fields are there (this is a double check as user might workaround the UI)
            assert "reg_username" in request.form, "Missing username"
            assert request.form["reg_username"], "Missing username"

            assert "reg_email" in request.form, "Missing email"
            assert request.form["reg_email"], "Missing email"

            assert "reg_pass" in request.form, "Missing password"
            assert request.form["reg_pass"], "Missing password"

            # Try to create the client using the User API
            with current_app.test_client() as http_client:
                user_data = {
                    "username": request.form["reg_username"],
                    "email": request.form["reg_email"],
                    "password": request.form["reg_pass"]
                }

                # The error message must be created by the API
                response = http_client.post(url_for("api.users.create"), data = user_data,
                                            headers={'Authorization': current_user.personal_jwt_token})

                if response.status_code < 300:
                    return redirect(url_for("web.admin.admin_page"))
                else:
                    flash(response.text, "error")
                    return render_template("register_user.html"), response.status_code


        except AssertionError as a_error:
            flash(f"Cannot create the user. {a_error.args[0]}", "error")
            return render_template("register_user.html"), 422
