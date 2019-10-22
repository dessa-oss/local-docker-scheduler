#!/bin/bash
source ../.env

docker build -t docker-test . && \
docker run --rm -v $(realpath ..):/app -v /var/run/docker.sock:/var/run/docker.sock -v /tmp/local_docker_scheduler:/tmp/local_docker_scheduler docker-test

# need to change this