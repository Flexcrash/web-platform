# Installation Instruction

## Prerequisite

The Flexcrash platform requires the following dependencies to be in place:

- SQLite3. See instructions at [https://www.sqlite.org/index.html](https://www.sqlite.org/index.html)
- Python 3.7.7. See instructions at [https://www.python.org/downloads/release/python-377/](https://www.python.org/downloads/release/python-377/)
- make. Optional

In the following, we assume that you can work with a terminal. 

The code was tested on a MacBook Pro, Dual-Core Intel Core i7@3,5 GHz, 	16 GB RAM, running Mac OS: Big Sur version 11.7.6. 

## Setup the python project

Check that you have the correct python version installed

```
$ python -V> Python 3.7.7
```

Go to the `code` folder and create a python virtual environment called `.venv` 

```
$ cd code
$ python -m venv .venv
```

Activate the virtual environment, upgrade `pip`, and install the required python packages.
> Note: the version numbers might be different than the ones shown in this document:

```
$. .venv/bin/activate
[.venv]$ pip install --upgrade pip
> Successfully installed pip-23.2.1

[.venv]$ pip install setuptools wheel --upgrade
> Successfully installed setuptools-68.0.0 wheel-0.41.2

[.venv]$ pip install -r requirements.txt
```

Install the `mpld3` library:

```
[.venv]$ pip install mpld3
```

Obtain the code for `commonroad_rp` from Dr. Gerald Wuersching and copy it under the folder `code`

## Configure the app
The Flexcrahs platform is a `flask` application; hence, it must be configured accordingly. Most of the configurations can be left as provided, but you **must** provide a secret key.

You can do so by editing the file `configuration/config.py`

Locate the line:

```
SECRET_KEY = <ADD YOUR SECRET KEY HERE>
```
And change the <ADD YOUR SECRET KEY HERE> with your key. The key must be a string, i.e., enclosed in `"` or `'`

## Start the app

The app comes with a `makefile`, to start the app locally type:

```
make run
...
. .venv/bin/activate && flask --app flexcrash run
 * Serving Flask app 'flexcrash'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit

```

Alternatively, you can activate the python virtual environment and start flask manually as follows:

```
. .venv/bin/activate
[.venv]$ flask --app flexcrash run
 * Serving Flask app 'flexcrash'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit

```

At this point the app should be up and running, and you can access it at the address `http://127.0.0.1:5000` or `http://localhost:5000` using your browser.

> Note: the code was tested only using Chrome.

## Stopping the app
To stop the app, press `CTRL+C` to kill the process or close the terminal in which the process is running.