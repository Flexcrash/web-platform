from flexcrash import create_app

if __name__ == "__main__":
    app = create_app("configuration/manual_testing_config.py")
    app.run(threaded=True)