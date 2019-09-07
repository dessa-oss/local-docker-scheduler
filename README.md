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
  - key1: value1
  - key2: value2
name_of_plugin2:
  - key1: value1
  ...
```
where `name_of_plugin` is the name of the Python subpackage inside the `tracker_client_plugins` package, and `key:value` pairs are arguments that will be fed into the plugin. Please see documentation for each plugin.
