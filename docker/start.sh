#!/bin/bash
source ../.env

docker run --rm \
    -v $(realpath ..):/app \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /tmp/local_docker_scheduler/working_dir:/tmp/local_docker_scheduler/working_dir \
    -v /tmp/local_docker_scheduler/archives_dir:/tmp/local_docker_scheduler/archives_dir \
    docker.shehanigans.net/local-docker-scheduler
