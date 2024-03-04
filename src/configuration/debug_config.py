"""Flask default configuration."""
# See: https://hackersandslackers.com/configure-flask-applications/
import os

TESTING = True
DEBUG = True
RESET = True

FLASK_ENV = 'development'
# TODO Read the configuration from file or via some env variable instead?
SECRET_KEY = "Bogus"
DATABASE_NAME = 'debug_flexcrash.db'
# According to:https://stackoverflow.com/questions/29397002/creating-database-with-sqlalchemy-in-flask
# sqlite:///database.db is a relative path
MARIA_DB = False
SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_NAME}"
# The list of extensions allowed to be uploaded as scenario template
ALLOWED_EXTENSIONS = ['xml']
# Default configuration of the goal region = TODO Check Tobias' config !
GOAL_REGION_LENGTH = 3.0
GOAL_REGION_WIDTH = 2.0
GOAL_REGION_DIST_TO_END = 10.0
MIN_INIT_SPEED_M_S = 1.0 # Problems with 0 speed.
MAX_INIT_SPEED_M_S = 25.0 # Circa 90 Km/h - 36.0 # Circa 130 Km/h

# Location of the generated images visualizing the templates
# TEMPLATE_IMAGES_FOLDER = os.path.join("static", "debug_scenario_template_images")
IMAGES_FOLDER = "static"
TEMPLATE_IMAGES_FOLDER = os.path.join(IMAGES_FOLDER, "scenario_template_images")
SCENARIO_IMAGES_FOLDER = os.path.join(IMAGES_FOLDER, "scenario_images")

AVS_CACHE_FOLDER = "avs_cache"

# Scheduler configuration
SCHEDULER_API_ENABLED = True
SCHEDULER_EXECUTORS = {"default": {"type": "processpool", "max_workers": 4}}