#!/bin/bash

if [[ -z "${LOCAL_DOCKER_SCHEDULER_HOST}" ]]
then
    echo "please set LOCAL_DOCKER_SCHEDULER_HOST"
    exit 1
fi

cat > database.config.yaml << EOF
queue:
  type: redis_connection.RedisList
  args:
    key: queue
    host: "${LOCAL_DOCKER_SCHEDULER_HOST}"
    port: 6379
failed_jobs:
  type: redis_connection.RedisDict
  args:
    key: failed_jobs
    host: "${LOCAL_DOCKER_SCHEDULER_HOST}"
    port: 6379
completed_jobs:
  type: redis_connection.RedisDict
  args:
    key: completed_jobs
    host: "${LOCAL_DOCKER_SCHEDULER_HOST}"
    port: 6379
running_jobs:
  type: redis_connection.RedisDict
  args:
    key: running_jobs
    host: "${LOCAL_DOCKER_SCHEDULER_HOST}"
    port: 6379
EOF

cat > tracker_client_plugins.yaml << EOF
redis_tracker_client:
  host: "${LOCAL_DOCKER_SCHEDULER_HOST}"
  port: 6379
EOF

mkdir -p /tmp/archives /tmp/working_dir

docker run --rm -d --name local-docker-scheduler \
    -p 5000:5000 \
    -v /tmp/archives:/archives \
    -v /tmp/working_dir:/working_dir \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v ${HOME}/.docker:/root/.docker \
    -v $(pwd -P)/tracker_client_plugins.yaml:/app/local-docker-scheduler/tracker_client_plugins.yaml \
    -v $(pwd -P)/database.config.yaml:/app/local-docker-scheduler/database.config.yaml \
    local-docker-scheduler