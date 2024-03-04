import os.path

import pytest

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

from sqlalchemy.exc import IntegrityError


def test_cannot_find_a_template(mixed_traffic_scenario_template_dao: MixedTrafficScenarioTemplateDAO):
    """
    GIVEN An empty database
    WHEN DAO looks for a non-existing template
    THEN DAO returns None
    """
    template_id = 1
    template = mixed_traffic_scenario_template_dao.get_template_by_id(template_id)
    assert template is None


def test_create_a_template_from_dict(mixed_traffic_scenario_template_dao: MixedTrafficScenarioTemplateDAO, xml_scenario_template: str):
    """
    GIVEN An empty database
    WHEN DAO creates a new template
    THEN DAO returns the template and the path where images are stored
    """
    name = "foo"
    description = "description"
    data = {
        "name" : name,
        "xml" : xml_scenario_template,
        "description" : description
    }
    template, image_path = mixed_traffic_scenario_template_dao.create_new_template(data)

    assert template.name == name
    assert template.description == description
    assert template.xml == xml_scenario_template
    assert os.path.exists(image_path)


def test_get_all_templates_returns_empty_list(mixed_traffic_scenario_template_dao: MixedTrafficScenarioTemplateDAO):
    """
    GIVEN An empty database
    WHEN DAO gets all the stored templates
    THEN DAO returns an empty list
    """
    assert len(mixed_traffic_scenario_template_dao.get_templates()) == 0


def test_get_all_templates_returns_the_single_user(mixed_traffic_scenario_template_dao: MixedTrafficScenarioTemplateDAO, xml_scenario_template: str):
    """
    GIVEN A database containing one template
    WHEN DAO gets all the stored templates
    THEN DAO returns a list of size 1
    """
    template = MixedTrafficScenarioTemplate(name="name", description="", xml=xml_scenario_template)
    mixed_traffic_scenario_template_dao.insert_and_get(template)

    assert len(mixed_traffic_scenario_template_dao.get_templates()) == 1


def test_get_template_by_template_id(mixed_traffic_scenario_template_dao: MixedTrafficScenarioTemplateDAO, xml_scenario_template: str):
    """
    GIVEN A database containing a template with template_id = 101
    WHEN DAO gets the template by id = 101
    THEN DAO returns the template with id = 101
    """
    template_id = 101
    template = MixedTrafficScenarioTemplate(template_id=template_id, name="name", description="", xml=xml_scenario_template)
    mixed_traffic_scenario_template_dao.insert_and_get(template)

    actual_template = mixed_traffic_scenario_template_dao.get_template_by_id(template_id)
    assert actual_template == template


def test_get_template_by_template_id_cannot_find(mixed_traffic_scenario_template_dao: MixedTrafficScenarioTemplateDAO, xml_scenario_template: str):
    """
    GIVEN A database containing a template with template_id = 101
    WHEN DAO gets the template by id = 101
    THEN DAO returns the template with id = 101
    """
    template_id = 101
    wrong_template_id = 1
    template = MixedTrafficScenarioTemplate(template_id=template_id, name="name", description="", xml=xml_scenario_template)
    mixed_traffic_scenario_template_dao.insert_and_get(template)

    actual_template = mixed_traffic_scenario_template_dao.get_template_by_id(wrong_template_id)
    assert actual_template is None


def test_dao_prevents_duplicates(mixed_traffic_scenario_template_dao: MixedTrafficScenarioTemplateDAO, xml_scenario_template: str):
    """
    GIVEN An empty database
    WHEN DAO inserts two templates with same template_id
    THEN the DB reject the new second one
    """
    template_id = 1
    template_1 = MixedTrafficScenarioTemplate(template_id=template_id, name="name", description="", xml=xml_scenario_template)
    mixed_traffic_scenario_template_dao.insert(template_1)

    template_2 = MixedTrafficScenarioTemplate(template_id=template_id, name="anothername", description="", xml=xml_scenario_template)

    with pytest.raises(IntegrityError):
        mixed_traffic_scenario_template_dao.insert(template_2)


def test_dao_prevents_empty_names(mixed_traffic_scenario_template_dao: MixedTrafficScenarioTemplateDAO, xml_scenario_template: str):
    """
    GIVEN An empty database
    WHEN DAO inserts a template without name
    THEN the DB reject the new second one
    """
    template_id = 1
    template_1 = MixedTrafficScenarioTemplate(template_id=template_id, description="", xml=xml_scenario_template)

    with pytest.raises(IntegrityError):
        mixed_traffic_scenario_template_dao.insert(template_1)


def test_dao_prevents_empty_xml(mixed_traffic_scenario_template_dao: MixedTrafficScenarioTemplateDAO):
    """
    GIVEN An empty database
    WHEN DAO inserts a template without name
    THEN the DB reject the new second one
    """
    template_id = 1
    template_1 = MixedTrafficScenarioTemplate(template_id=template_id, name="name", description="")

    with pytest.raises(IntegrityError):
        mixed_traffic_scenario_template_dao.insert(template_1)