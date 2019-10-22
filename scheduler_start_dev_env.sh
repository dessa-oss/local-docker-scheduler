#!/bin/bash

if [[ -z "${LOCAL_DOCKER_SCHEDULER_HOST}" ]]
then
    echo "please set LOCAL_DOCKER_SCHEDULER_HOST"
    exit 1
fi

if [[ -z "${FOUNDATIONS_HOME}" ]]
then
    echo "please set FOUNDATIONS_HOME"
    exit 1
fi

if [ "$1" = "rebuild" ]; then
    docker build -t local-docker-scheduler:latest .
fi


canonical_home=$(cd ${FOUNDATIONS_HOME} && pwd)

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


archives_dir=${canonical_home}/job_data
working_dir=${canonical_home}/config/local_docker_scheduler/work_dir

mkdir -p ${archives_dir} ${working_dir}

create_network_if_not_exists () {
    if [[ -z "$(docker network ls --filter name=foundations-orbit --format \"{{.ID}}\")" ]]; then
        echo 'Creating foundations-orbit docker network'
        docker network create -d bridge foundations-orbit
    fi
}

get_redis_container_image () {
    docker ps --format "{{.Image}}" | grep -E '^redis:?.*$' | head -n1
}

create_redis_if_not_exists () {
    if [[ -z "$(get_redis_container_image)" ]]; then
        echo "Creating redis."
        docker run -d \
            --restart always \
            --name foundations-redis \
            -p 6379:6379 \
            redis:5 \
            > /dev/null
        echo 'Redis continer successfully started and attached to the network'
        if [[ $? -ne 0 ]]; then
            echo "Failed to start redis."
            exit 1
        fi
    fi
}

create_network_if_not_exists
create_redis_if_not_exists

redis_container_image=$(get_redis_container_image)
redis_container_name=$(docker ps -f ancestor=${redis_container_image} --format "{{.Names}}" | head -n1)

echo 'Attemtping to connect the redis server $redis_container_name to the network foundations-orbit'
docker network connect foundations-orbit ${redis_container_name} --alias redis >> /dev/null

echo 'Attempting to create docker for local-docker-scheduler'
docker run --rm -d --name local-docker-scheduler \
    -p 5000:5000 \
    -e NUM_WORKERS=0 \
    --network foundations-orbit \
    -v ${archives_dir}:/archives \
    -v ${working_dir}:/working_dir \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v ${HOME}/.docker:/root/.docker \
    -v $(pwd -P)/tracker_client_plugins.yaml:/app/local-docker-scheduler/tracker_client_plugins.yaml \
    -v $(pwd -P)/database.config.yaml:/app/local-docker-scheduler/database.config.yaml \
    local-docker-scheduler

if [[ $? -ne 0 ]]; then
    echo "Failed to start local-docker-scheduler."
    exit 1
fi