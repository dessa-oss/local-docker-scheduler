#
# Copyright (C) DeepLearning Financial Technologies Inc. - All Rights Reserved
# Unauthorized copying, distribution, reproduction, publication, use of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Eric lee <e.lee@dessa.com>, 08 2019
#

FROM python:3.6-alpine

MAINTAINER Eric Kin Ho Lee version: 0.1

COPY ./requirements.txt /app/requirements.txt

RUN pip install --requirement /app/requirements.txt

COPY . /app/local-docker-scheduler/

WORKDIR /app/local-docker-scheduler

RUN mkdir /job_bundle_store_dir

VOLUME ["/root/.docker", "/var/run/docker.sock", "/app/local-docker-scheduler/tracker_client_plugins.yaml", "/app/local-docker-scheduler/database.config.yaml", "/archives", "/working_dir", "/job_bundle_store_dir"]

EXPOSE 5000

ENTRYPOINT ["python", "-m", "local_docker_scheduler", "-p 5000"]

#CMD ["-H", "0.0.0.0"]

#ENTRYPOINT gunicorn --workers=1 -b 0.0.0.0:5000 local_docker_scheduler:"get_app()"