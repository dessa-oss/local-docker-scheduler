#!/bin/bash
source ../.env

echo $HOST_WORK_DIR
docker build -t docker-test . && \
docker run --rm -v $(realpath ..):/app -v /var/run/docker.sock:/var/run/docker.sock -v $HOST_WORK_DIR:/app/working_dir -v $HOST_ARCHIVES_DIR:/app/archives_dir docker-test

