import flask
from flask import current_app, request
from flask import Blueprint
import os

from persistence.data_access import MixedTrafficScenarioTemplateDAO
from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate, MixedTrafficScenarioTemplateSchema


# This blueprint handles the requests to the API Scenario Templates Endpoint
scenario_templates_api = Blueprint('templates', __name__, url_prefix='/templates')

# Marshmallow Integration - Make sure we do not dump the large XML to the user everytime
scenario_template_schema = MixedTrafficScenarioTemplateSchema(exclude=['xml'])
scenario_templates_schema = MixedTrafficScenarioTemplateSchema(many=True, exclude=['xml'])

# References:
#   - https://flask.palletsprojects.com/en/2.2.x/patterns/fileuploads/
#   - https://stackoverflow.com/questions/20015550/read-file-data-without-saving-it-in-flask
#   - https://github.com/marshmallow-code/flask-marshmallow/issues/50
#   - https://github.com/marshmallow-code/marshmallow/issues/631


@scenario_templates_api.route("/", methods=["GET"])
def get_scenario_templates():
    """
    :return: All the existing scenario templates. None has XML attached
    """
    scenario_templates_dao = MixedTrafficScenarioTemplateDAO(current_app.config)
    all_scenario_templates = scenario_templates_dao.get_templates()
    return scenario_templates_schema.dump(all_scenario_templates)

# @scenario_templates_api.route("/images", methods=["GET", "POST"])
# def get_scenario_templates_png():
#
#     try:
#         templates = os.listdir('./debug_static/scenario_template_images')
#         print("templates", templates)
#     except FileNotFoundError:
#         templates = []
#
#     return templates

@scenario_templates_api.route("/<template_id>/xml", methods=["GET"])
def get_scenario_template_xml(template_id):
    """
    :return: The XML of an existing scenario template if the scenario template exists
    """
    scenario_templates_dao = MixedTrafficScenarioTemplateDAO(current_app.config)
    scenario_template = scenario_templates_dao.get_template_by_id(template_id)
    if scenario_template is None:
        return "Scenario Template Not Found", 404
    # Return the XML otherwise
    return scenario_template.xml, 200


def allowed_file(filename):
    """
    TODO Check whether the uploaded file has a valid extension. Probably, one needs to check whether this is a valid commonroad scenario
    :param filename:
    :return:
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]


@scenario_templates_api.route("/", methods=["POST"])
def create():
    """
    Get the name of the scenario template and the XML content (uploaded as file)
    Stores a new scenario template in the DB
    :return:
    """
    # request.form is an ImmutableDict so we need to create a mutable one to add the xml
    data = dict(request.form)

    # Mandatory Fields
    assert "name" in data, "Missing mandatory input name"
    # check if the post request has the file part
    assert 'file' in request.files, "Missing template file data = {} files = {}".format(request.data, request.files)

    # Optional Fields. We initialize them
    data["template_id"] = data["template_id"] if "template_id" in data else None
    data["description"] = data["description"] if "description" in data else None

    # If the user does not select a file, the browser submits an
    # empty file without a filename.
    file = request.files['file']

    assert file.filename != '', "Missing template file"

    assert file and allowed_file(file.filename), "Invalid file type"

    if file and allowed_file(file.filename):
        contents = file.read()
        data["xml"] = contents.decode("utf-8")

    scenario_templates_dao = MixedTrafficScenarioTemplateDAO(current_app.config)
    # Ignore the image file for the moment
    all_scenario_template, _ = scenario_templates_dao.create_new_template(data)
    return scenario_template_schema.dump(all_scenario_template), 201



