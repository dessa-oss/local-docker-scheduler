# local-docker-scheduler

## How to run

`python -m local-docker-scheduler -H host -p port [-d]`

where `host:port` is where the REST API will bind to, and -d starts the service in debug mode

If using docker to run, you will need to mount the following volumes:

```
-v <docker socket>:/var/run/docker.sock
-v <docker configuration>:/root/.docker
-v <path to tracker_client_plugins.config.yaml>:/app/local-docker-scheduler/tracker_client_plugins.yaml
-v <path to database.config.yaml>:/app/local-docker-scheduler/database.config.yaml
```

Please see sections below on details on configuration files

## How to build Docker image

`docker build -f Dockerfile -t <name>:<tag> .`

## Tracker client plugins configuration

Placing a `tracker_client_plugins.yaml` in the project directory will make the scheduler load the designated plugins at start.  
Format of the yaml file should be:
```
name_of_plugin1:
  key1: value1
  key2: value2
name_of_plugin2:
  key1: value1
  ...
```
where `name_of_plugin` is the name of the Python subpackage inside the `tracker_client_plugins` package, and `key:value` pairs are arguments that will be fed into the plugin. Please see documentation for each plugin.

Example:
```
redis_tracker_client:
  host: "127.0.0.1"
  port: 6379
```

## Database configuration

The database configuration allows the scheduler to use different backend implementations to store states and results of the jobs. Currently, queued, running, failed, and completed jobs can support different backends.

A `database.config.yaml` must be present in the project directory. The structure needs to look like:

```
queue:
  type: <name_of_plugin>
  arg:
    key1: value1
    key2: value2
    ...
failed_jobs:
  type: <name_of_plugin>
  arg:
    key1: value1
    key2: value2
    ...
completed_jobs:
  type: <name_of_plugin>
  arg:
    key1: value1
    key2: value2
    ...
running_jobs:
  type: <name_of_plugin>
  arg:
    key1: value1
    key2: value2
    ...
```
where `<name_of_plugin>` is a dot separated path to the relevant backend. It is a callable and the scheduler will provide it with the arguments as keyword arguments at start up. An example would look like:

```
queue:
  type: redis_connection.RedisList
  args:
    key: queue
    host: foundations-redis
    port: 6379
failed_jobs:
  type: redis_connection.RedisDict
  args:
    key: failed_jobs
    host: foundations-redis
    port: 6379
completed_jobs:
  type: redis_connection.RedisDict
  args:
    key: completed_jobs
    host: foundations-redis
    port: 6379
running_jobs:
  type: redis_connection.RedisDict
  args:
    key: running_jobs
    host: foundations-redis
    port: 6379
```

For the redis_connection objects, the host and port are used to connect to a Redis server, while the key is the redis key used to store the related data.

## Foundations submission configuration

The following is the configuration file you will need in your $FOUNDATIONS_HOME/config/submission directory in order for the Foundations SDK to know how to use this scheduler.

```
job_deployment_env: local_docker_scheduler_plugin

job_results_root: <path to store finished jobs>
working_dir_root: <temporary directory where jobs are stored for execution by workers>
scheduler_url: <the host and port from the How to run section above>
container_config_root: <config/ folder containing submission and execution subfolders: configuration files mounted for the worker container>

cache_config:
  end_point: /cache_end_point
```
