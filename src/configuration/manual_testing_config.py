"""Flask default configuration."""
# See: https://hackersandslackers.com/configure-flask-applications/
import os

TESTING = True

DEBUG = True
RESET = False # Cause to wipe the DB on restart during debug/testing

# This is really bad design, but cannot find a way to find my own port!
PORT=5000

FLASK_ENV = 'development'
# TODO Read the configuration from file or via some env variable instead?
SECRET_KEY = "Bogus"
DATABASE_NAME = 'manual-testing.db'
# According to:https://stackoverflow.com/questions/29397002/creating-database-with-sqlalchemy-in-flask
# sqlite:///database.db is a relative path
MARIA_DB = False
SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_NAME}"
# The list of extensions allowed to be uploaded as scenario template
ALLOWED_EXTENSIONS = ['xml']
# Default configuration of the goal region = TODO Check Tobias' config !
GOAL_REGION_LENGTH = 10.0
GOAL_REGION_WIDTH = 4.0
GOAL_REGION_DIST_TO_END = 10.0
# MIN_INIT_SPEED_M_S = 13.89 # Circa 50 Km/h
# MAX_INIT_SPEED_M_S = 36.11 # Circa 130 Km/h
MIN_INIT_SPEED_M_S = 1.0 # Problems with 0 speed.
MAX_INIT_SPEED_M_S = 25.0 # Circa 90 Km/h - 36.0 # Circa 130 Km/h
# Vehicle dimensions - width=1.8, length=4.3
VEHICLE_LENGTH = 4.3
VEHICLE_WIDTH = 1.8
# Location of the generated images visualizing the templates
# All static files must be placed under static and their URL generated with url_for
IMAGES_FOLDER = os.path.join("static", "manual-testing")
TEMPLATE_IMAGES_FOLDER = os.path.join(IMAGES_FOLDER, "scenario_template_images")
SCENARIO_IMAGES_FOLDER = os.path.join(IMAGES_FOLDER, "scenario_images")

AVS_CACHE_FOLDER = "avs_cache"
# TODO: This smells bad!
# IMAGES_FOLDER = os.path.join(AVS_CACHE_FOLDER, "manual-testing")

# Scheduler configuration
SCHEDULER_API_ENABLED = True
SCHEDULER_EXECUTORS = {
    "rendering": {"type": "processpool", "max_workers": 4},
    "driving": {"type": "processpool", "max_workers": 4}
}