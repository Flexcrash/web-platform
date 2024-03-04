"""Flask default configuration."""
# See: https://hackersandslackers.com/configure-flask-applications/

import os

TESTING = False
DEBUG = False
FLASK_ENV = 'production'
# TODO Read the configuration from file or via some env variable instead?
SECRET_KEY = None  # "fl3xCr@shh"

DATABASE_NAME = 'Flexcrash'
# According to:https://stackoverflow.com/questions/29397002/creating-database-with-sqlalchemy-in-flask
# https://stackoverflow.com/questions/50309545/how-can-i-override-config-parameters-in-flask-config
# sqlite:///database.db is a relative path
# SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_NAME}.db"
MARIA_DB = True
# Default values
MARIA_DB_USER = 'Flexcrash'
MARIA_DB_PASSWORD = None
MARIA_DB_HOST = "127.0.0.1"
MARIA_DB_PORT = "3306"
SQLALCHEMY_DATABASE_URI = f'mariadb+mariadbconnector://{MARIA_DB_USER}:{MARIA_DB_PASSWORD}@{MARIA_DB_HOST}:{MARIA_DB_PORT}/{DATABASE_NAME}'
SQL_ALCHEMY_POOL_RECYCLE = 50
SQLALCHEMY_POOL_SIZE = 100
SQLALCHEMY_PRE_PING = True
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 100,
    'pool_recycle': 50,
    'pool_pre_ping': True
}

PORT = 80

# The list of extensions allowed to be uploaded as scenario template
ALLOWED_EXTENSIONS = ['xml']
# Default configuration of the goal region = TODO Check Tobias' config !
GOAL_REGION_LENGTH = 3.0
GOAL_REGION_WIDTH = 2.0
GOAL_REGION_DIST_TO_END = 10.0
MIN_INIT_SPEED_M_S = 1.0  # Problems with 0 speed.
MAX_INIT_SPEED_M_S = 25.0  # Circa 90 Km/h - 36.0 # Circa 130 Km/h
# Vehicle dimensions - width=1.8, length=4.3
VEHICLE_LENGTH = 4.3
VEHICLE_WIDTH = 1.8
# Location of the generated images visualizing the templates
# TODO Can we ensure the folders exists directly here?
IMAGES_FOLDER = "static"
TEMPLATE_IMAGES_FOLDER = os.path.join(IMAGES_FOLDER, "scenario_template_images")
SCENARIO_IMAGES_FOLDER = os.path.join(IMAGES_FOLDER, "scenario_images")

AVS_CACHE_FOLDER = "avs_cache"

# Scheduler configuration
SCHEDULER_API_ENABLED = True
# I cannot find a way to assign jobs to executors
SCHEDULER_EXECUTORS = {
    "rendering": {"type": "processpool", "max_workers": 4},
    "driving": {"type": "processpool", "max_workers": 4}
}

# VERSIONING INFORMATION - Note the tag_the_app.sh script will append REV to this file
MAJOR = 1
MINOR = 1
REV = "a18a7c4"
# This number can be obtained with the Linux/MacOS command date +%s
LAST_UPDATED_IN_SECONDS = "1703243473"

# JWT TOKEN EXPIRATION TIME
TOKEN_EXPIRATION_IN_SECONDS = 3600
