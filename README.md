# local-docker-scheduler

## How to run

`python -m local-docker-scheduler -H host -p port [-d]`

where `host:port` is where the REST API will bind to, and -d starts the service in debug mode

## How to build Docker image

`docker build -f Dockerfile -t <name>:<tag> .`

## Tracker client plugins configuration

Place a `tracker_client_plugins.yaml` in the project folder will make the scheduler load the designated plugins at start.  
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
