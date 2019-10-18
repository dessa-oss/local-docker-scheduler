#!/bin/sh

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