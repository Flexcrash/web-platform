"""Flask default configuration."""
# See: https://hackersandslackers.com/configure-flask-applications/

import os

TESTING = False
DEBUG = False
FLASK_ENV = 'development'
# TODO Read the configuration from file or via some env variable instead?
SECRET_KEY = None
DATABASE_NAME = 'flexcrash.db'
# The list of extensions allowed to be uploaded as scenario template
ALLOWED_EXTENSIONS = ['xml']
# Default configuration of the goal region = TODO Check Tobias' config !
GOAL_REGION_LENGTH = 3.0
GOAL_REGION_WIDTH = 2.0
GOAL_REGION_DIST_TO_END = 10.0
MIN_INIT_SPEED_M_S = 0.1 # Problems with 0 speed.
MAX_INIT_SPEED_M_S = 25.0 # Circa 90 Km/h - 36.0 # Circa 130 Km/h
# Vehicle dimensions - width=1.8, length=4.3
VEHICLE_LENGTH = 4.3
VEHICLE_WIDTH = 1.8
# Location of the generated images visualizing the templates
# TODO Can we ensure the folders exist directly here?
IMAGES_FOLDER = "static"
TEMPLATE_IMAGES_FOLDER = os.path.join(IMAGES_FOLDER, "scenario_template_images")
SCENARIO_IMAGES_FOLDER = os.path.join(IMAGES_FOLDER, "scenario_images")
