# Make sure to start the app without interactive matplot
# References:
#   - https://stackoverflow.com/questions/65068073/error-while-showing-matplotlib-figure-in-flask
#   - https://stackoverflow.com/questions/58320567/matplotlib-font-manager-debug-messages-in-log-file

import logging
from datetime import timedelta

import matplotlib
matplotlib.use('Agg')  # disable interactive view

# Monkey patch commonroad_rp.utils.interpolate_angle
def monkeypatch_commonroad_rp():
    import commonroad_rp.utils as utils_module
    original_function = utils_module.interpolate_angle
    # new function
    def patched_interpolate_angle(x: float, x1: float, x2: float, y1: float, y2:float) -> float:
        if x1 == x2:
            return original_function(x, x1, x2 + 0.001, y1, y2)
        else:
            return original_function(x, x1, x2, y1, y2)

    utils_module.interpolate_angle = patched_interpolate_angle

# Make sure we do monkey patch that module
monkeypatch_commonroad_rp()

import shutil
import os

import inflect
import datetime

# TODO Move this to an utility module?
# https://gist.github.com/thatalextaylor/7408395
def time_since(date_in_seconds: int, lang = inflect.engine()):

    if date_in_seconds is None:
        return "Last updated: Unknown"

    # Ensures this is an integer
    date_in_seconds = int(date_in_seconds)
    
    # Get the current date and time and convert the date and time to an integer using the timestamp() method
    timestamp = int(datetime.datetime.now().timestamp())
    seconds_passed = timestamp - date_in_seconds

    assert seconds_passed >= 0, "Cannot have a negative time here!"

    days, hours, minutes, seconds = 0, 0 ,0 ,0
    days, seconds = divmod(seconds_passed, 86400)
    if days <= 0:
        hours, seconds = divmod(seconds_passed, 3600)
        if hours <= 0:
            minutes, seconds = divmod(seconds_passed, 60)

    if days > 0 or hours > 0 or minutes > 0:
        seconds = 0

    measures = (
        (days, "day"),
        (hours, "hour"),
        (minutes, "minute"),
        (seconds, "second"),
    )

    message = lang.join([f"{count} {lang.plural(noun, count)}" for (count, noun) in measures if count])
    return f"Last updated {message} ago."

from flask import Flask

def upload_basic_templates(app):
    from persistence.database import db
    from persistence.mixed_scenario_template_data_access import MixedTrafficScenarioTemplateDAO

    with app.app_context():
        scenario_template_dao = MixedTrafficScenarioTemplateDAO(app.config)
        # TODO Upload LTAP, Intersections and similar cases automatically!

        # For manual testing and demonstration we use ONLY the simplest scenario template
        # template_files = ["./tests/scenario_templates/template_1.xml",
        #                     "./tests/scenario_templates/template_2.xml",
        #                     "./tests/scenario_templates/template_3.xml"]

        template_files = ["./tests/scenario_templates/template_3.xml"]

        for i, template_file in enumerate(template_files, start=1):
            with open(template_file, "r") as file:

                scenario_template_data = {"name": f"template_{i}",
                                            "xml": file.read(),
                                            "description": "A simple scenario template.",
                                            "template_id": i
                                            }
                try:
                    # We need to call this to enfore the creation of the image  
                    scenario_template_dao.create_new_template(scenario_template_data)
                except Exception as ex:
                    # import traceback
                    # print(traceback.format_exc())
                    db.session.rollback()


def create_default_admin_user(app):
    # Create the Default Admin User if specified in the environment
    admin_user_file = os.environ.get("ADMIN_USER_FILE", None)
    admin_email_file = os.environ.get("ADMIN_EMAIL_FILE", None)
    admin_password_file = os.environ.get("ADMIN_PASSWORD_FILE", None)

    if admin_user_file and admin_email_file and admin_password_file:
        
        from persistence.database import db
        from persistence.user_data_access import UserDAO

        admin_user = None
        admin_email = None
        admin_password = None

        with open(admin_user_file, "r") as f:
            admin_user = f.read().rstrip('\n')

        with open(admin_email_file, "r") as f:
            admin_email = f.read().rstrip('\n')

        with open(admin_password_file, "r") as f:
            admin_password = f.read().rstrip('\n')

        print(f"\n Creating Initial Admin User {admin_user} with Email {admin_email} \n")

        with app.app_context():
            # This might fail if the user already exists since we are concurrently inserting it
            # TODO One would check if another admin user exists, and do not create this one again
            try:
                user_dao = UserDAO()
                user_dao.create_new_user({"user_id": 1, "username": admin_user, "email": admin_email, "password": admin_password})
                user_dao.make_admin_user(1)
            except Exception as ex:
                # Note this one!
                db.session.rollback()

def create_app(config_filename=None):
    # As describe here: https://flask.palletsprojects.com/en/2.2.x/logging/ we need to setup logging before the app is
    # created unless we are fine with the default logging configuration
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # Register additional functions that can be invoked directly form the templates
    app.jinja_env.globals.update(time_since=time_since)

    # Make sure annoying messages are gone
    logging.getLogger('matplotlib').setLevel(logging.WARNING)

    # Set the logger to DEBUG is the app is in launch in debug mode
    if app.debug:
        app.logger.setLevel(logging.DEBUG)

    # Reference: https://flask.palletsprojects.com/en/2.2.x/config/
    # Configure the application with default values from config.py inside the configuration package
    app.config.from_object('configuration.config')

    # Load any provided configuration if availble.
    # NOTE: This will override default values
    # TODO: What happens to new keys? and old, but not modified ones?
    if config_filename is not None:
        # Load the conf from file
        assert app.config.from_pyfile(config_filename)

    # TODO Probably better to rename this variable to something else!
    # If the YOURAPPLICATION_SETTINGS points to a (python config) file, overwrite the values
    # References:
    #   - https://flask.palletsprojects.com/en/2.2.x/config/
    app.config.from_envvar('YOURAPPLICATION_SETTINGS', silent=True)

    if not app.config["SECRET_KEY"]:
        print("SECRET_KEY is missing. Read it from ENV")
        pass_file = os.environ.get("SECRET_KEY_FILE", None)
        if pass_file:
            with open(pass_file, "r") as f:
                app.config.update({"SECRET_KEY": f.read().rstrip('\n')})

    assert app.config["SECRET_KEY"], "SECRET_KEY is missing. Cannot start the application"

    # Session configuration. Ideally, we should use something on the server to store big sessions. However, in production
    # using uWSGI with multiple processes breaks the session mechanism. So the only working solution, so far, is to rely on the
    # basic SessionCookie mechanism
    # app.config.update(SESSION_COOKIE_SAMESITE="None", SESSION_COOKIE_SECURE=True)
    #
    # if "SESSION_TYPE" not in app.config:
    #     app.config["SESSION_TYPE"] = 'filesystem'
    # app.config['SESSION_PERMANENT'] = True
    # app.config['SESSION_TYPE'] = 'filesystem'
    # app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=5)
    # app.config['SESSION_FILE_THRESHOLD'] = 20
    #
    # app.logger.info(f"Managing sessions using {app.config['SESSION_TYPE']}")
    #
    # session = Session()
    # session.init_app(app)
    # Not sure this makes a difference
    # CORS(app, supports_credentials=True)

    if app.config["MARIA_DB"]:
        # When using MARIA DB under uWSGI, a powerful machine will start concurrently the DB initializations
        # Those initialization do not use CREATE TABLE IF DOES NOT EXIST statements, so they fail
        # Adding a delay should help giving the first time to set stuff up from within the app
        from time import sleep
        sleep(10)
        app.logger.info("Configuring Maria DB")
        # To enable fine-tuning, especially for Docker, we might need to update single entries using EnvVariables
        for conf_key in ["MARIA_DB_PASSWORD", "MARIA_DB_HOST", "MARIA_DB_PORT", "MARIA_DB_USER"]:
            app.config.update({conf_key: os.environ.get(conf_key, app.config[conf_key])})
        # Sometimes the PASSWORD are passed via secret files that must contain ONLY the value (terminated with \n)
        pass_file = os.environ.get("MARIA_DB_PASSWORD_FILE", None)
        if pass_file:
            with open(pass_file, "r") as f:
                app.config.update({"MARIA_DB_PASSWORD": f.read().rstrip('\n')})

        # Refresh the DATABASE URI
        app.config["SQLALCHEMY_DATABASE_URI"]=f'mariadb+mariadbconnector://{app.config["MARIA_DB_USER"]}:{app.config["MARIA_DB_PASSWORD"]}@{app.config["MARIA_DB_HOST"]}:{app.config["MARIA_DB_PORT"]}/{app.config["DATABASE_NAME"]}'

    # Patch to create a temporary databased to manual e2e testing
    if app.config["TESTING"] and app.config["RESET"]:
        # TODO This should reset whatever DB is there
        # If the SQLIte test database exists, wipe it out!
        sqlite_db_file = os.path.join(app.instance_path, app.config["DATABASE_NAME"])
        if os.path.exists(sqlite_db_file):
            app.logger.info("Testing database {} exist. Remove it.".format(sqlite_db_file))
            os.remove(sqlite_db_file)
        # TODO why this is not inside the instance instead?
        # If the image folder exists, we wipe it out
        if os.path.exists(app.config["IMAGES_FOLDER"]):
            shutil.rmtree(app.config["IMAGES_FOLDER"], ignore_errors=True)
        if "AVS_CACHE_FOLDER" in app.config and os.path.exists(app.config["AVS_CACHE_FOLDER"]):
            shutil.rmtree(app.config["AVS_CACHE_FOLDER"], ignore_errors=True)

    # Configure the Database - Note this must be done BEFORE marshmallow
    from persistence import database
    database.init_app(app)

    # Configure MarshMallow
    from api import serialization
    serialization.init_app(app)

    # Configure the Background scheduler (multiprocess)
    if "SCHEDULER_API_ENABLED" in app.config and app.config["SCHEDULER_API_ENABLED"]:
        from background import scheduler
        scheduler.init_app(app)
        # This is kept separated from init for readability
        scheduler.rewamp_jobs()

    else:
        app.logger.debug("Scheduler not configured")
    # Register the BluePrints
    # References:
    #   - https://flask.palletsprojects.com/en/2.2.x/blueprints/
    from views.web import web_layer
    app.register_blueprint(web_layer)

    from views.api import api_layer
    app.register_blueprint(api_layer)

    # Ensures all the image folders exist
    image_path = app.config["IMAGES_FOLDER"]
    if not os.path.exists(image_path):
        os.makedirs(image_path, exist_ok=True)  # , mode=0o777)
    image_path = app.config["TEMPLATE_IMAGES_FOLDER"]
    if not os.path.exists(image_path):
        os.makedirs(image_path, exist_ok=True)  # , mode=0o777)
    image_path = app.config["SCENARIO_IMAGES_FOLDER"]
    if not os.path.exists(image_path):
        os.makedirs(image_path, exist_ok=True)  # , mode=0o777)

    # Manage sessions
    # app.config.update(SESSION_COOKIE_SAMESITE="None", SESSION_COOKIE_SECURE=True)

    create_default_admin_user(app)
    
    upload_basic_templates(app)

    # Patch to create a temporary databased to manual e2e testing
    if app.config["TESTING"] and app.config["RESET"]:

        print("\n Creating Testing Environment with Users and Templates \n")
        # At this point the db is already configured
        from persistence.database import db
        from persistence.user_data_access import UserDAO
        from persistence.mixed_scenario_template_data_access import MixedTrafficScenarioTemplateDAO

        with app.app_context():
            user_dao = UserDAO()
            scenario_template_dao = MixedTrafficScenarioTemplateDAO(app.config)
            # scenario_dao = MixedTrafficScenarioDAO(app.config)

            try:
                user_dao.create_new_user({"user_id": 1, "username": "one", "email": "one@email", "password": "1234"})
                user_dao.make_admin_user(1)
                user_dao.create_new_user({"user_id": 2, "username": "two", "email": "two@email", "password": "1234"})
                user_dao.create_new_user({"user_id": 3, "username": "three", "email": "three@email", "password": "1234"})
            except Exception as ex:
                import traceback
                print(traceback.format_exc())
                # Note this one!
                db.session.rollback()

            # TODO Upload LTAP, Intersections and similar cases automatically!
            # For manual testing and demonstration we use ONLY the simplest scenario template
            template_files = ["./tests/scenario_templates/template_1.xml",
                              "./tests/scenario_templates/template_2.xml",
                              "./tests/scenario_templates/template_3.xml"]

            # template_files = ["./tests/scenario_templates/template_3.xml"]

            for i, template_file in enumerate(template_files, start=1):
                with open(template_file, "r") as file:

                    scenario_template_data = {"name": f"template_{i}",
                                              "xml": file.read(),
                                              "description": "",
                                              "template_id": i
                                              }
                try:
                    # We need to call this to enfore the creation of the image
                    scenario_template_dao.create_new_template(scenario_template_data)
                except Exception as ex:
                    import traceback
                    print(traceback.format_exc())
                    db.session.rollback()

    # Import the login manager and link it to the app
    # TODO There might be a similar need for API authentication?
    from views.web import login_manager
    login_manager.init_app(app)


    # Extract version metadata
    major = app.config['MAJOR'] if 'MAJOR' in app.config else None
    minor = app.config['MINOR'] if 'MINOR' in app.config else None
    revision = app.config['REV'] if 'REV' in app.config else None
    # Seconds. Convert it to Date if not None

    last_updated_in_seconds = app.config['LAST_UPDATED_IN_SECONDS'] if 'LAST_UPDATED_IN_SECONDS' in app.config else None
    time_since_last_updated = time_since(last_updated_in_seconds)

    # Printout the Current Version of the CODE
    print("")
    print(f"Running Version {major}.{minor}.{revision}. {time_since_last_updated}")
    print("")

    return app