# Get the directory of the mkfile
# mkfile_path:=$(abspath $(lastword $(MAKEFILE_LIST)))
# current_dir:=$(notdir $(patsubst %/,%,$(dir $(mkfile_path))))
# Directory where the make file is
ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))


python_version_full := $(wordlist 2,4,$(subst ., ,$(shell python --version 2>&1)))
python_version_major := $(word 1,${python_version_full})
python_version_minor := $(word 2,${python_version_full})
python_version_patch := $(word 3,${python_version_full})

TARGET_PYTHON_VERSION=$(shell echo "3")


PIP=.venv/bin/pip
PYTHON=.venv/bin/python
ACTIVATE_VENV=. .venv/bin/activate

clean-prod:
	$(RM) flexcrash.db
	$(RM) static/scenario_template_images/*.*

clean-debug: 
	$(RM) debug_flexcrash.db
	$(RM) static/debug_scenario_template_images/*.*

clean-all: clean-prod clean-debug
	$(RM) -r __pycache__

.venv/bin/activate:
	python -m venv .venv

.setup: .venv/bin/activate requirements.txt
	$(PYTHON) -m pip install --upgrade pip 
	$(PIP) install wheel setuptools --upgrade
	$(PIP) install -r requirements.txt
	touch .setup

test: .venv/bin/activate .setup 
	$(ACTIVATE_VENV) && pytest tests 2>&1 | tee pytest.log

# TODO Use absolute paths?
debug: .venv/bin/activate .setup
	$(ACTIVATE_VENV) && export YOURAPPLICATION_SETTINGS=$(ROOT_DIR)/configuration/debug_config.py; flask --app flexcrash --debug run

manual-test: .venv/bin/activate .setup
	$(ACTIVATE_VENV) && export YOURAPPLICATION_SETTINGS=$(ROOT_DIR)/configuration/manual_testing_config.py; flask --app flexcrash --debug run


run : .venv/bin/activate .setup
	$(ACTIVATE_VENV) && flask --app flexcrash run