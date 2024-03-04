from flask_sqlalchemy import SQLAlchemy

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlite3 import Connection as SQLite3Connection


from persistence.utils import inject_where_statement_using_attributes

# https://stackoverflow.com/questions/2614984/sqlite-sqlalchemy-how-to-enforce-foreign-keys
# Make sure that if we use SQLite we enable ForeignKeys checking
@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, SQLite3Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

# From https://flask-sqlalchemy.palletsprojects.com/en/3.0.x/quickstart/
# Define the global handle for the database in the web app
db = SQLAlchemy()

# def reload(orm_entity):
#     from model.mixed_traffic_scenario import MixedTrafficScenario
#     from model.vehicle_state import VehicleState
#     from model.driver import Driver
#
#     if isinstance(orm_entity, MixedTrafficScenario):
#         orm_entity: MixedTrafficScenario
#         stmt = db.select(MixedTrafficScenario)
#         # Select the drivers in the scenarios without user_id
#         kwargs = {
#             MixedTrafficScenario.scenario_id.name: orm_entity.scenario_id
#         }
#         updated_stmt = inject_where_statement_using_attributes(stmt, MixedTrafficScenario, **kwargs)
#         return db.session.execute(updated_stmt).first()[0]
#     elif isinstance(orm_entity, VehicleState):
#         orm_entity: VehicleState
#         stmt = db.select(VehicleState)
#         # Select the drivers in the scenarios without user_id
#         kwargs = {
#             VehicleState.vehicle_state_id.name: orm_entity.vehicle_state_id
#         }
#         updated_stmt = inject_where_statement_using_attributes(stmt, VehicleState, **kwargs)
#         return db.session.execute(updated_stmt).first()[0]
#     elif isinstance(orm_entity, Driver):
#         orm_entity: Driver
#         stmt = db.select(Driver)
#         # Select the drivers in the scenarios without user_id
#         kwargs = {
#             Driver.driver_id.name: orm_entity.driver_id
#         }
#         updated_stmt = inject_where_statement_using_attributes(stmt, Driver, **kwargs)
#         return db.session.execute(updated_stmt).first()[0]
#     else:
#         raise AssertionError(f"Type {type(orm_entity).__name__} is not supported for reload")


def init_app(app):
    """
    Init this DB for the given flask_app
    """
    assert "SQLALCHEMY_DATABASE_URI" in app.config, "Cannot initialize Database: No SQLALCHEMY_DATABASE_URI value provided!"
    app.logger.debug("Initialize Database {}".format(app.config["SQLALCHEMY_DATABASE_URI"]))
    db.init_app(app)
    # NOTE: The db is created w.r.t. to the instance path of the flask app
    # Initialize the models here - Make sure we import all of them BEFORE calling db.create_all()
    from model.user import User
    from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate
    from model.mixed_traffic_scenario import MixedTrafficScenario
    from model.driver import Driver
    from model.vehicle_state import VehicleState
    from model.tokens import UserToken

    # Get ready to store Trajectories
    # TODO Why model contains CollisionChecking?

    with app.app_context():
        db.create_all()



