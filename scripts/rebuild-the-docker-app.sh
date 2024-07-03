#!/bin/bash

PATH_OF_THI_SCRIPT=$(realpath $(dirname $0))
ROOT_OF_THE_PROJECT=$(dirname $PATH_OF_THI_SCRIPT)
DEPLOY_FOLDER=$(echo "$ROOT_OF_THE_PROJECT/deploy")

# Fail on error
set -e

# Make sure we are on main
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "main" ]]; then
  echo "Aborting script. Wrong branch: expected main got ${BRANCH}";
  exit 1;
fi

# Make sure we are at the latest commit
# TODO Check if it worked
git pull --all

# Get current revision and branch
REV=$(git rev-parse --short HEAD)

# Get the current time in seconds
THE_TIME=$(date +%s)

# Enter the script dir
pushd $PATH_OF_THI_SCRIPT

#### Update config.py to include the current version of the app and the last time it was updated by overwriting the corresponding variables
echo "" >> ../src/configuration/config.py
echo "REV=\"${REV}\"" >> ../src/configuration/config.py
echo "LAST_UPDATED_IN_SECONDS=\"${THE_TIME}\"" >> ../src/configuration/config.py

# Come back to original folder
popd

#### Build the flexcrash-app Docker image

# Go to the root of the project
pushd $ROOT_OF_THE_PROJECT

# Invoke Docker Build from here because it needs access to scripts and src folders
docker build -f deploy/app/Dockerfile -t flexcrash-app:${REV} .

# Come back
popd

#### Update the docker compose file to point to the current version of the flexcrash-app. We do not use latest because it's a smell

# Go to deploy folder
pushd $DEPLOY_FOLDER

# Make sure docker-compose has the latest version of the flexcrash-app image
sed -i .bkp -e "s|image: flexcrash-app:\(.*\)|image: flexcrash-app:${REV}|" docker-compose.yml 

# Come back
popd