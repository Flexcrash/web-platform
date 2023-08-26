import pytest
import random

from pathlib import Path
from flexcrash import create_app
from model.user import User

from configuration.config import MIN_INIT_SPEED_M_S, MAX_INIT_SPEED_M_S
from persistence.data_access import UserDAO, MixedTrafficScenarioDAO, MixedTrafficScenarioTemplateDAO, VehicleStateDAO
from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate


@pytest.fixture
def dummy_username():
    def func(name="UserName"):
        num = 0
        while True:
            num += 1
            yield f"{name}_{num}"

    return func


@pytest.fixture
def flexcrash_user_generator(dummy_username):
    """ Return a function that generates random users"""

    def func():
        user_id = 0
        dummy_name_generator = dummy_username()
        while True:
            user_id += 1
            username = next(dummy_name_generator)
            email = "{}@flexcrash.eu".format(username)
            password = "1234"

            user = User(user_id, username, email, password)
            user_data = {
                "user_id": user.user_id, # Only for testing purposes
                "username": user.username,
                "email": user.email,
                "password": user.password,
            }

            yield user, user_data

    # Return the actual generator not the function that generate the generator
    return func()


@pytest.fixture
def flexcrash_test_app(tmp_path):
    """
    Return a flexcrash app configured for testing with
    :param tmp_path:
    :return:
    """
    # Create a temporary configuration for the app with DATABASE_NAME
    temp_cfg_file = tmp_path / "flexcrash.cfg"
    temp_database_file = tmp_path / "database.db"
    # Create the temporary static folders
    temp_scenario_image_folder = tmp_path
    # Reference https://stackoverflow.com/questions/24877025/runtimeerror-working-outside-of-application-context-when-unit-testing-with-py
    configuration = """
DATABASE_NAME = '{}'
SERVER_NAME = 'localhost:5000'
TESTING = True
DEBUG = True
RESET = False
IMAGES_FOLDER = '{}'
TEMPLATE_IMAGES_FOLDER = '{}'
SCENARIO_IMAGES_FOLDER = '{}'
# Default configuration of the goal region = TODO Check Tobias' config !
GOAL_REGION_LENGTH = 10.0
GOAL_REGION_WIDTH = 4.0
GOAL_REGION_DIST_TO_END = 10.0
MIN_INIT_SPEED_M_S = 13.89 # Circa 50 Km/h
MAX_INIT_SPEED_M_S = 36.11 # Circa 130 Km/h
# Vehicle dimensions -
VEHICLE_LENGTH = 3.0
VEHICLE_WIDTH = 2.0
""".format(temp_database_file, temp_scenario_image_folder, temp_scenario_image_folder, temp_scenario_image_folder)

    temp_cfg_file.write_text(configuration)

    flask_app = create_app(temp_cfg_file)
    flask_app.app_context = flask_app.app_context()
    flask_app.app_context.push()

    # Disable login for flask-login
    flask_app.config["LOGIN_DISABLED"] = True

    return flask_app


@pytest.fixture(scope="module")
def xml_scenario_template():
    """
    Return the test xml template scenario. This scenario is made of 3 consecutive lanelets
    """
    return """<?xml version='1.0' encoding='UTF-8'?>
<commonRoad timeStepSize="0.1" commonRoadVersion="2020a" author="Alessio Gambi" benchmarkID="ABW_Test-1_1_T-1"> 
  <scenarioTags>
    <test/>
  </scenarioTags>
  <lanelet id="14724">
    <leftBound>
      <point>
        <x>570.72489</x>
        <y>-700.09255</y>
      </point>
      <point>
        <x>569.1732</x>
        <y>-698.71446</y>
      </point>
      <point>
        <x>563.34905</x>
        <y>-693.15506</y>
      </point>
    </leftBound>
    <rightBound>
       <point>
        <x>573.02386</x>
        <y>-697.45357</y>
      </point>
      <point>
        <x>571.58942</x>
        <y>-696.18229</y>
      </point>
      <point>
        <x>565.86524</x>
        <y>-690.7222</y>
      </point>
    </rightBound>
  <successor ref="14725"/>
  </lanelet>
  <lanelet id="14725">
    <leftBound>
      <point>
        <x>563.34905</x>
        <y>-693.15506</y>
      </point>
      <point>
        <x>556.03044</x>
        <y>-685.58459</y>
      </point>
      <point>
        <x>544.29534</x>
        <y>-672.67213</y>
      </point>
    </leftBound>
    <rightBound>
      <point>
        <x>565.86524</x>
        <y>-690.7222</y>
      </point>
      <point>
        <x>558.62058</x>
        <y>-683.23061</y>
      </point>
      <point>
        <x>546.86954</x>
        <y>-670.30074</y>
      </point>
    </rightBound>
	<predecessor ref="14724"/>
	<successor ref="14726"/>
  </lanelet>
  <lanelet id="14726">
    <leftBound>
      <point>
        <x>544.29534</x>
        <y>-672.67213</y>
      </point>
      <point>
        <x>521.29847</x>
        <y>-647.7089</y>
      </point>
    </leftBound>
    <rightBound>
      <point>
        <x>546.86954</x>
        <y>-670.30074</y>
      </point>
      <point>
        <x>523.88144</x>
        <y>-645.34669</y>
      </point>
    </rightBound>
	<predecessor ref="14725"/>
  </lanelet>
</commonRoad>
"""


@pytest.fixture
def xml_scenario_template_as_file(tmp_path, xml_scenario_template):
    # Create a temp scenario faile
    temp_scenario_template_file = tmp_path / "scenario_template.xml"
    temp_scenario_template_file.write_text(xml_scenario_template)

    return temp_scenario_template_file

@pytest.fixture(scope="module")
def script_loc(request):
    """
    Return the directory of the currently running test script
    """
    return Path(request.fspath).parent


@pytest.fixture
def flexcrash_test_app_with_a_scenario_template_and_given_users(flexcrash_test_app,
                                                              flexcrash_user_generator,
                                                              xml_scenario_template):
    def _method(users_id, scenario_template_id):
        # At this point the flexcrash_test_app is already setup with an empty db
        user_dao = UserDAO(flexcrash_test_app.config)

        for user_id in users_id:
            user, _ = next(flexcrash_user_generator)
            # enforce the given ID to make the tests predictatble
            user.user_id = user_id
            user_dao.insert(user)

        # Upload the XML for the Scenario XML
        mixed_traffic_scenario_template_dao = MixedTrafficScenarioTemplateDAO(flexcrash_test_app.config)
        mixed_traffic_scenario_template_dao.insert_and_get(
            MixedTrafficScenarioTemplate(scenario_template_id, "xml", "xml", xml_scenario_template))

        return flexcrash_test_app

    return _method


@pytest.fixture
def random_vehicle_state_data_at_times(xml_scenario_template):
    """
    Return a random Vehicle State with the given timestamp
    This MIGHT be later based on the scenario template
    """

    def _method(timestamps):
        states_data = {
            "timestamps": ",".join([str(timestamp) for timestamp in timestamps]),
            "positions_x": ",".join([str(value) for value in [random.uniform(-10,10) for _ in range(len(timestamps))]]),
            "positions_y": ",".join([str(value) for value in [random.uniform(-10,10) for _ in range(len(timestamps))]]),
            "rotations": ",".join([str(value) for value in [random.uniform(-360,+360) for _ in range(len(timestamps))]]),
            "speeds_ms": ",".join([str(value) for value in [random.uniform(MIN_INIT_SPEED_M_S, MAX_INIT_SPEED_M_S) for _ in range(len(timestamps))]]),
            "accelerations_m2s": ",".join([str(value) for value in [random.uniform(-1.0, +1.0) for _ in range(len(timestamps))]])
        }
        return states_data

    return _method


@pytest.fixture
def tmp_cfg(tmp_path):
    """
    Return an app configuration where the db is a temp file (tmp_path)

    :param tmp_path:
    :return:
    """
    temp_cfg_file = tmp_path / "flexcrash.cfg"
    temp_database_file = tmp_path / "database.db"
    if "WindowsPath" in type(temp_database_file).__name__:
        temp_database_file = str(temp_database_file).replace("\\", "\\\\")

    # Reference https://stackoverflow.com/questions/24877025/runtimeerror-working-outside-of-application-context-when-unit-testing-with-py
    configuration = """
DATABASE_NAME = '{}'
SERVER_NAME = 'localhost:5000'""".format(temp_database_file)

    temp_cfg_file.write_text(configuration)

    temp_cfg_file = str(temp_cfg_file)

    return temp_cfg_file


# TODO Creating an app to get a configuration objbect might be overkilling but I cannot find another way to get it
@pytest.fixture
def user_dao(flexcrash_test_app):
    return UserDAO(flexcrash_test_app.config)


@pytest.fixture
def mixed_traffic_scenario_dao(flexcrash_test_app):
    return MixedTrafficScenarioDAO(flexcrash_test_app.config)


@pytest.fixture
def mixed_traffic_scenario_template_dao(flexcrash_test_app):
    return MixedTrafficScenarioTemplateDAO(flexcrash_test_app.config)

@pytest.fixture
def vehicle_state_dao(flexcrash_test_app):
    return VehicleStateDAO(flexcrash_test_app.config)