
export build_version=`python get_version.py | sed 's/+/_/g'`
registry=${NEXUS_DOCKER_REGISTRY:-us.gcr.io/dessa-atlas/foundations}


docker push "$registry/scheduler" \
  && echo "Successfully pushed scheduler to $registry repository"