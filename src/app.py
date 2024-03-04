# This file is needed to start the app under uWSGI, which requires the application to be stored in the `app` variable:
# https://stackoverflow.com/questions/13751277/how-can-i-use-an-app-factory-in-flask-wsgi-servers-and-why-might-it-be-unsafe

from flexcrash import create_app

app = create_app("configuration/config.py")

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=80, threaded=True)
