from flexcrash import create_app

import pytest

from persistence.user_data_access import UserDAO
from persistence.mixed_scenario_template_data_access import MixedTrafficScenarioTemplateDAO
from persistence.mixed_scenario_data_access import MixedTrafficScenarioDAO
from persistence.driver_data_access import DriverDAO
from persistence.vehicle_state_data_access import VehicleStateDAO

from model.user import User
from model.mixed_traffic_scenario_template import MixedTrafficScenarioTemplate
from model.mixed_traffic_scenario import MixedTrafficScenario
from model.driver import Driver
from model.vehicle_state import VehicleState

@pytest.mark.skip(reason="Broken")
def test_home_page(tmp_cfg):
    """
    GIVEN the flexcrash application configured for testing (in memory database) and the user is not authenticated
    WHEN the '/' page is requested (GET)
    THEN check that the response is valid 200
    """
    flask_app = create_app(tmp_cfg)

    with flask_app.test_client() as test_client:
        response = test_client.get('/')
        assert response.status_code == 200
        # TODO Add assertions
        # assert b"Welcome to the" in response.data
        # assert b"Flask User Management Example!" in response.data
        # assert b"Need an account?" in response.data
        # assert b"Existing user?" in response.data

@pytest.mark.skip(reason="Broken")
def test_sign_up(tmp_cfg):
    # TODO Implement Me
    """
    GIVEN the flexcrash application configured for testing (in memory database) and the user is not authenticated
    WHEN the SIGN UP form is submitted (POST) with a new user's data
    THEN check that the response is a valid redirect to "/"
    """


    flask_app = create_app(tmp_cfg)
    flask_app.app_context = flask_app.app_context()
    flask_app.app_context.push() 
    

    macaron = User(username="Macaron",email="macaron@email.com",password="pizza_con_pinaplo")

    #send a post request to the sign up page
    request_data = {
        "username": macaron.username,
        "reg_email": macaron.email,
        "reg_pass": macaron.password    
        
        
    }
    flask_app.test_client().post('/register_user', data=request_data)
    response = flask_app.test_client().get('/')
    
    #check if the respose is a valid redirect to "/"
    assert response.status_code == 200

@pytest.mark.skip(reason="Broken")
def test_login(tmp_cfg):
    # TODO Implement Me
    """
    GIVEN the flexcrash application configured for testing (in memory database) and the user is not authenticated
    WHEN the LOGIN UP form is submitted (POST) with data about existing user
    THEN check that the response is a valid redirect to "/"
    """
    flask_app = create_app(tmp_cfg)
    flask_app.app_context = flask_app.app_context()
    flask_app.app_context.push()


    #1. Create a user
    macaron = User(username="Macaron",email="macaron@email.com",password="pizza_con_pinaplo")

    #2. make userDao
    userdao = UserDAO()
    userdao.insert(macaron)

    #3.send a post request to the sign up page
    request_data = {
        "username": macaron.username,
        "reg_email": macaron.email,
        "reg_pass": macaron.password    
        
        
    }
    
    flask_app.test_client().post('/login_user', data=request_data)
    #4. check if the respose is a valid redirect to "/"
    

    response = flask_app.test_client().get('/')
    assert response.status_code == 200
    

def test_logout():
    """
    GIVEN the flexcrash application configured for testing (in memory database) and the user is authenticated
    WHEN the LOGOUT form is submitted (POST)
    THEN check that the response is a valid redirect to "/"
    """
    pass