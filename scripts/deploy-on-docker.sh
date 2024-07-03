#!/bin/bash

PATH_OF_THI_SCRIPT=$(realpath $(dirname $0))
ROOT_OF_THE_PROJECT=$(dirname $PATH_OF_THI_SCRIPT)
DEPLOY_FOLDER=$(echo "$ROOT_OF_THE_PROJECT/deploy")

# Move to the deploy folder (secret files have relative path)
pushd $DEPLOY_FOLDER

docker-compose up

popd