import os.path
from typing import Tuple, List, Optional

import traceback

from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate

from visualization.mixed_traffic_scenario_template import generate_static_image

from persistence.database import db
from persistence.utils import inject_where_statement_using_attributes


class MixedTrafficScenarioTemplateDAO:

    def __init__(self, app_config):
        # TODO This is required here for rendering, remove it after refactoring since visualization logic doed not belong here
        self.images_folder = app_config["TEMPLATE_IMAGES_FOLDER"]

    # TODO Why returning also a str? Maybe this should be a method inside the template itself?
    def create_new_template(self, data: dict) -> Tuple[MixedTrafficScenarioTemplate, str]:
        # Mandatory
        name = data["name"]
        xml = data["xml"]
        # Optional
        template_id = data["template_id"] if "template_id" in data else None
        description = data["description"]

        new_template = MixedTrafficScenarioTemplate(template_id=template_id, name=name, description=description, xml=xml)
        template_image_path = None
        try:
            # Store the Template in the DB. Ensures it has a template_id, hence we return the updated object
            new_template = self.insert_and_get(new_template)

            # Store the Template on the FS
            template_image_path = generate_static_image(self.images_folder, new_template)

            # TODO Link the image to the scenario_template object?
            # If everything worked out, commit, and return the template
            db.session.commit()

            return new_template, template_image_path
        except Exception as ex:
            # Rollback in case of any problems
            db.session.rollback()
            if template_image_path is not None and os.path.exists(template_image_path):
                os.remove(template_image_path)
            print(traceback.format_exc())
            raise ex

    def disable_template(self, scenario_template_id: int) -> None:
        # TODO Better silently return nothing?
        assert scenario_template_id, "Missing Scenario Template ID"

        # Get the scenario_template object, disable it
        stmt = db.select(MixedTrafficScenarioTemplate)
        kwargs = {
            MixedTrafficScenarioTemplate.template_id.name: scenario_template_id
        }
        updated_stmt = inject_where_statement_using_attributes(stmt, MixedTrafficScenarioTemplate, **kwargs)

        scenario_template: MixedTrafficScenarioTemplate
        scenario_template = db.session.execute(updated_stmt).first()[0]
        scenario_template.is_active = False
        db.session.commit()

    def enable_template(self, scenario_template_id: int) -> None:

        # TODO Better silently return nothing?
        assert scenario_template_id, "Missing Scenario Template ID"

        # Get the scenario_template object, enable it
        stmt = db.select(MixedTrafficScenarioTemplate)
        kwargs = {
            MixedTrafficScenarioTemplate.template_id.name: scenario_template_id
        }
        updated_stmt = inject_where_statement_using_attributes(stmt, MixedTrafficScenarioTemplate, **kwargs)

        scenario_template: MixedTrafficScenarioTemplate
        scenario_template = db.session.execute(updated_stmt).first()[0]
        scenario_template.is_active = True
        db.session.commit()

    # TODO why we need to get back the template_id?
    # TODO We can get rid of this?
    def insert(self, template: MixedTrafficScenarioTemplate) -> int:
        """
               Try to insert the template scenario in the database, fails if the template scenario violates the DB Constraints
               Otherwise, the database assigns a unique id to the teamplte scenario unless specified.
               :param template: the template to store in the database
               :return: the template_id of the just inserted template scenario
               """
        return self.insert_and_get(template).template_id

    def insert_and_get(self, template: MixedTrafficScenarioTemplate, nested=False) -> MixedTrafficScenarioTemplate:
        """
        Try to insert a scenario template into the database and get the updated object in return.
        Fails if a scenario template has issues.
        """
        # TODO A session is already started at this point!
        # db.session.begin(nested=nested)
        db.session.add(template)
        db.session.commit()
        return template

    def _get_templates_by_attributes(self, **kwargs) -> List[MixedTrafficScenarioTemplate]:
        """
        Return a collection of template scenarios matching the given attributes or an empty collection otherwise
        :return:
        """
        # Create the basic SELECT for User
        stmt = db.select(MixedTrafficScenarioTemplate)

        # Add the necessary WHERE clauses
        updated_stmt = inject_where_statement_using_attributes(stmt, MixedTrafficScenarioTemplate, **kwargs)

        # Execute the statement
        scenario_templates = db.session.execute(updated_stmt)
        # TODO: do we need ? What if this is part of a larger transaction?
        db.session.commit()
        # Concretize the list as we expect that later
        return list(scenario_templates.scalars())

    def get_template_by_id(self, template_id: int, skip_active_check=False) -> Optional[MixedTrafficScenarioTemplate]:
        """
        Return the template with the given template_id if exists and is active. None otherwise.
        :param template_id:
        :return:
        """

        kwargs = {
            MixedTrafficScenarioTemplate.template_id.name: template_id
        }

        if not skip_active_check:
            kwargs[MixedTrafficScenarioTemplate.is_active.name] = True

        templates = self._get_templates_by_attributes(**kwargs)
        assert len(templates) == 0 or len(templates) == 1
        return templates[0] if len(templates) == 1 else None

    def get_templates(self) -> List[MixedTrafficScenarioTemplate]:
        """
        Return the collection of all the ACTIVE scenario templates stored in the database. Otherwise an empty list
        :return:
        """
        kwargs = {
            MixedTrafficScenarioTemplate.is_active.name: True
        }
        return self._get_templates_by_attributes(**kwargs)

    def get_all_templates(self) -> List[MixedTrafficScenarioTemplate]:
        """
        Return the collection of all the scenario templates stored in the database, including the one disabled.
        Note: this should be used only by ADMIN users
        :return:
        """
        kwargs = {}
        return self._get_templates_by_attributes(**kwargs)

