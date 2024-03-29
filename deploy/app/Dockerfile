FROM tiangolo/uwsgi-nginx:python3.10

# Based on the example: https://github.com/tiangolo/uwsgi-nginx-flask-docker/blob/master/docker-images/python3.10.dockerfile
LABEL maintainer="Alessio Gambi <alessiogambi@gmail.com>"

# Install Drivability Checker v2022.1 from source

# Install Dependencies
RUN apt-get update && \
	apt-get install -y build-essential cmake git wget unzip libboost-dev libboost-thread-dev libboost-test-dev libboost-filesystem-dev libeigen3-dev libomp-dev

# Build from source
RUN git clone https://gitlab.lrz.de/tum-cps/commonroad-drivability-checker.git

WORKDIR commonroad-drivability-checker

RUN git checkout v2022.1 && \
	git submodule update --init

# Patch the dependencies
RUN sed -i -e 's|scipy==1.6.0|scipy==1.9.3|' requirements.txt && \
	python -m pip install --upgrade pip && \
	pip install wheel setuptools --upgrade && \
	pip install -r requirements.txt && \
	pip install triangle

RUN BUILD_JOBS=8 python setup.py build && \
	pip install .


# Install the new MariaDB connector
# RUN wget https://r.mariadb.com/downloads/mariadb_repo_setup && \
# 	echo "935944a2ab2b2a48a47f68711b43ad2d698c97f1c3a7d074b34058060c2ad21b  mariadb_repo_setup" | sha256sum -c - && \
# 	chmod +x mariadb_repo_setup && \
# 	./mariadb_repo_setup --mariadb-server-version="mariadb-10.6"

# Disable the sha checksum check
RUN wget https://r.mariadb.com/downloads/mariadb_repo_setup && \
	chmod +x mariadb_repo_setup && \
	./mariadb_repo_setup --mariadb-server-version="mariadb-10.6"

RUN apt-get install -y libmariadb3 libmariadb-dev mariadb-client

# Prepare the APP

# Install the APP's python requirements
COPY requirements.txt /tmp/requirements.txt

RUN python -m pip install --upgrade pip && \
	pip install -r /tmp/requirements.txt

# PATCH supervisord --- Since we DO NOT user threads but processes, this might not be needed afterall
RUN sed -i -e 's|\(command=/usr/local/bin/uwsgi .*\)|\1 --enable-threads|' /etc/supervisor/conf.d/supervisord.conf


# URL under which static (not modified by Python) files will be requested
# They will be served by Nginx directly, without being handled by uWSGI
# Make sure that nginx does not steal static files that might be (re)generated by the app after fixing #304
ENV STATIC_URL /static/global
# Absolute path in where the static files wil be
ENV STATIC_PATH /app/static/global

# If STATIC_INDEX is 1, serve / with /static/index.html directly (or the static URL configured)
# ENV STATIC_INDEX 1
ENV STATIC_INDEX 0

# Add flexcrash app
COPY ./src /app
WORKDIR /app

# Make sure there are no left over from development env
RUN rm -rfv ./static/manual-testing ./static/scenario_template_images static/scenario_images && \
	rm -rfv avs_cache && \
	mkdir avs_cache

# Make /app/* available to be imported by Python globally to better support several use cases like Alembic migrations.
ENV PYTHONPATH=/app

# Move the base entrypoint to reuse it
RUN mv /entrypoint.sh /uwsgi-nginx-entrypoint.sh
# Copy the entrypoint that will generate Nginx additional configs
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

# Run the start script provided by the parent image tiangolo/uwsgi-nginx.
# It will check for an /app/prestart.sh script (e.g. for migrations)
# And then will start Supervisor, which in turn will start Nginx and uWSGI
CMD ["/start.sh"]