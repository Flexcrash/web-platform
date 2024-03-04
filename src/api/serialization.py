# See https://flask-marshmallow.readthedocs.io/en/latest/
from flask_marshmallow import Marshmallow
from marshmallow import fields, ValidationError

from model.user import User
from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate
from model.mixed_traffic_scenario import MixedTrafficScenario
from model.vehicle_state import VehicleState
from model.driver import Driver

from commonroad.geometry.shape import Rectangle
import numpy as np

# Define the global handle for the serialization
ma = Marshmallow()

def init_app(app):
    """
    Init this DB for the given flask_app
    """
    app.logger.debug("Initialize Marshmallow")
    ma.init_app(app)

# TODO If the module becomes too big, split it in submodules
# TODO Additional configurations are available, including linking the resources.

class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = User
        include_fk = True


class MixedTrafficScenarioTemplateSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = MixedTrafficScenarioTemplate
        include_fk = True


class MixedTrafficScenarioSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = MixedTrafficScenario
        include_fk = True
        include_relationships = True
        load_instance = True
        # TODO owner and scenario_template are not loaded as object, but only with IDs
        # Maybe it's because they are marked as lazy? But also drivers are so...
    # Does not work, it might be an issue in the import inside the API
    # owner = Nested(UserSchema, many=False)
    # scenario_template = Nested(MixedTrafficScenarioTemplate, many=False)

    # operation = ma.Nested(OperationSchema, only=('key',))


class VehicleStateSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = VehicleState
        include_fk = True


class RectangleField(fields.Field):

    def _serialize(self, value, attr, obj, **kwargs):
        """
        Given a Rectangle return a string "length,width,center.x,center.y,orientation"
        """
        if value is None:
            return ""
        else:
            return ",".join([str(value.length), str(value.width),
                             str(value.center[0]), str(value.center[1]),
                             str(value.orientation)])

    def _deserialize(self, value, attr, data, **kwargs):
        """"
               Given a string "length,width,center.x,center.y,orientation" return a Rectangle
               """
        if value is None:
            return None

        if isinstance(value, bytes):
            value = value.decode('utf-8')

        length, width, center_x, center_y, orientation = [float(v) for v in value.split(",")]
        center = np.array([center_x, center_y])
        # center: np.ndarray = None,
        return Rectangle(length, width, center, orientation)


class DriverSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Driver
        include_fk = True

    goal_region = RectangleField()
