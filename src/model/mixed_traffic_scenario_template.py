import tempfile
import os
import io

# This is to convert this class to a CommonRoad object. TODO Move it to anntoher package
from commonroad.common.file_reader import CommonRoadFileReader

# Import the "singleton" db object for creating the model
from persistence.database import db

class MixedTrafficScenarioTemplate(db.Model):

    __tablename__ = 'Mixed_Traffic_Scenario_Template'

    template_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(250), nullable=False)
    description = db.Column(db.String(250), nullable=True)
    # TODO Not sure this is ok
    xml = db.Column(db.Text, nullable=False)

    # Is this Template Active?
    is_active = db.Column(db.Boolean, unique=False, default=True)

    #     parent = relationship("Parent", back_populates="children")
    # This template (1) defined (many) scenarios. One scenario is defined by one template
    # so this is a "one-to-many" relation, so we need use_list=True?
    define = db.relationship("MixedTrafficScenario", back_populates="scenario_template", uselist=True)

    def get_file_name(self):
        return "{}.png".format(self.template_id)

    def __eq__(self, other):
        if not isinstance(other, MixedTrafficScenarioTemplate):
            return False

        return self.template_id == other.template_id and \
               self.name == other.name and \
               self.description == other.description and \
               self.xml == other.xml

    def as_commonroad_scenario(self):
        # TODO Find a workaround to avoid using temporary files
        # Note: we need this specific code to avoid issues in Windows
        with io.BytesIO(self.xml.encode('utf8')) as binary_file:
            with io.TextIOWrapper(binary_file, encoding='utf8') as file_obj:
                commonroad_file_reader = CommonRoadFileReader(file_obj)
                commonroad_scenario, _ = commonroad_file_reader.open()
                return commonroad_scenario
