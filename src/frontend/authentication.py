from flask_login import LoginManager, login_required, logout_user, login_user, current_user
# The login manager for the Web Frontend
login_manager = LoginManager()
login_manager.login_view = "web.login"
login_manager.login_message = "User needs to be logged in to view this page"
login_manager.login_message_category = "alert-warning"