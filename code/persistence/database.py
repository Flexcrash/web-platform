import os
import sqlite3
import numpy as np

from persistence.data_access import CREATE_USER_TABLE
from persistence.data_access import CREATE_MIXED_TRAFFIC_SCENARIO_TABLE
from persistence.data_access import CREATE_VEHICLE_STATE_TABLE
from persistence.data_access import CREATE_DRIVER_TABLE
from persistence.data_access import CREATE_SCENARIO_TEMPLATE

from persistence.data_access import CREATE_TRAINING_SCENARIO_TEMPLATES

from commonroad.geometry.shape import Rectangle


def init_app(app):
    """
    Init this DB for the given flask_app
    :param app: the flask_app
    """
    app.logger.debug("Initialize Database {}".format(app.config["DATABASE_NAME"]))
    # Since we open a new connection every time, it is enough to store the database name and initialize the file here
    # TODO This can be replaced with a simple functionn
    Database(app.config["DATABASE_NAME"])


def rectangle_to_str(rectangle_as_object):
    """
        Given a Rectangle return a string "length,width,center.x,center.y,orientation"
    :param rectangle_as_object:
    :return:
    """
    return ",".join([str(rectangle_as_object.length), str(rectangle_as_object.width),
                     str(rectangle_as_object.center[0]), str(rectangle_as_object.center[1]),
                     str(rectangle_as_object.orientation)])


def str_to_rectangle(rectangle_as_bytestr):
    """
    Given a string b"length,width,center.x,center.y,orientation" return a Rectangle
    :param rectangle_as_bytestr:
    :return:
    """
    length, width, center_x, center_y, orientation = [float(v) for v in rectangle_as_bytestr.decode('utf-8').split(",")]
    center = np.array([center_x, center_y])
    # center: np.ndarray = None,
    return Rectangle(length, width, center, orientation)


# TODO This is not a class wrapping db access, this is a class wrapping a call to create a DB...
class Database:

    def __init__(self, database_name):
        self.database_name = database_name
        self.initialize()

    def initialize(self):
        # Register to the DB the converters to serialized/deserialize objects to columns - Note those cannot be easily put in WHERE clauses!
        sqlite3.register_adapter(Rectangle, rectangle_to_str)
        sqlite3.register_converter("rectangle", str_to_rectangle)

        if not os.path.exists(self.database_name):
            try:
                # TODO Replace with logging
                print("Create Database")
                connection = sqlite3.connect(self.database_name)
                # Enable Foreing Keys Support
                connection.execute('PRAGMA foreign_keys = ON')
                # Create the Tables
                cursor = connection.cursor()
                cursor.execute(CREATE_USER_TABLE)
                cursor.execute(CREATE_SCENARIO_TEMPLATE)
                # This one logically depends on the ones above
                cursor.execute(CREATE_MIXED_TRAFFIC_SCENARIO_TABLE)
                # This one logically depends on the ones above
                cursor.execute(CREATE_DRIVER_TABLE)
                # This one logically depends on the ones above
                cursor.execute(CREATE_VEHICLE_STATE_TABLE)
                # This one logically depends on the ones above
                cursor.execute(CREATE_TRAINING_SCENARIO_TEMPLATES)

                connection.commit()
            finally:
                connection.close()


