# TODO Deprecated? We do not really have a use case for it
import json

from flask import current_app, request, url_for
from flask import Blueprint


# from persistence.data_access import MixedTrafficScenarioDAO, UserDAO
from persistence.mixed_scenario_template_data_access import MixedTrafficScenarioTemplateDAO
from persistence.user_data_access import UserDAO

from model.mixed_traffic_scenario import MixedTrafficScenarioSchema
# from model.mixed_traffic_scenario_template import TrainingScenarioTemplateSchema

# Setup this Blueprint
training_scenarios_api = Blueprint('training', __name__, url_prefix='/training')

# Marshmallow Integrationn
scenario_schema = MixedTrafficScenarioSchema()
scenarios_schema = MixedTrafficScenarioSchema(many=True)

# Marshmallow Integration - Make sure we do not dump the large XML to the user everytime
training_scenario_template_schema = TrainingScenarioTemplateSchema()
training_scenario_templates_schema = TrainingScenarioTemplateSchema(many=True)


@training_scenarios_api.route("/", methods=["POST"])
def create():
    """
    Create a new mixed traffic scenario from one of the available preconfigured scenarios used for training
    and identified by a key (string).
    """
    data = dict(request.form)

    # Mandatory inputs - Make this an utility method
    assert "training_scenario_name" in data, "Missing training scenario name"
    assert "trainee_id" in data, "Missing trainee user ID"

    training_scenario_name = data["training_scenario_name"]

    training_scenario_dao = TrainingScenarioTemplateDAO(current_app.config)

    # This will raise an exception if there's no match
    training_template = next(tt for tt in training_scenario_dao.get_templates() if tt.name == training_scenario_name)

    trainee_id = int(data["trainee_id"])

    user_dao = UserDAO(current_app.config)
    trainee = user_dao.get_user_by_user_id(trainee_id)
    assert trainee, "Invalid trainee user ID"

    # Now invoke the factory to get all the necessary data
    training_scenario_data, init_state_dict, goal_region_as_rectangle = training_template.generate_scenario_data_for(trainee_id)
    #  https://stackoverflow.com/questions/33353192/flask-hangs-when-sending-a-post-request-to-itself
    with current_app.test_client() as http_client:
        response = http_client.post(url_for("api.scenarios.create"), data=training_scenario_data)
        # Assert that this scenario is ACTIVE (only one scenario)
        assert response.status_code == 201

    # Extract Scenario ID
    created_scenario_as_dict = json.loads(response.data.decode("utf-8"))
    scenario_id = created_scenario_as_dict["scenario_id"]
    #
    # # FORCE PUSH THE NEW INIT STATE AND GOAL_REGION
    scenario_dao = MixedTrafficScenarioDAO(current_app.config)
    #
    scenario_dao.force_initial_state_for_driver_in_scenario(init_state_dict, trainee_id, scenario_id)
    scenario_dao.force_goal_region_as_rectangle_for_driver_in_scenario(goal_region_as_rectangle, trainee_id, scenario_id)

    # Force reactivation
    updated_scenario = scenario_dao.get_scenario_by_scenario_id(scenario_id)
    scenario_dao.render(updated_scenario)

    return scenario_schema.dump(updated_scenario), 201

@training_scenarios_api.route("/", methods=["GET"])
def get_scenario_templates():
    """
    :return: All the existing training scenario templates. But do not attach the scenario template
    """
    training_scenario_templates_dao = TrainingScenarioTemplateDAO(current_app.config)
    all_training_scenario_templates = training_scenario_templates_dao.get_templates()
    return training_scenario_templates_schema.dump(all_training_scenario_templates)