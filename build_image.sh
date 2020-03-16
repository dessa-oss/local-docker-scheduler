#!/bin/bash

export build_version=`python get_version.py | sed 's/+/_/g'`
registry=${NEXUS_DOCKER_REGISTRY:-us.gcr.io/dessa-atlas/foundations}


docker build --network=host -t "$registry/scheduler:$build_version" . \
  && docker tag "$registry/scheduler:$build_version" "$registry/scheduler:latest" \
  && echo "Successfully built scheduler for $registry repository"