FROM python:3.6-alpine

MAINTAINER Eric Kin Ho Lee version: 0.1

COPY ./requirements.txt /app/requirements.txt

RUN pip install --requirement /app/requirements.txt

COPY . /app/local-docker-scheduler/

WORKDIR /app/local-docker-scheduler

VOLUME ["/root/.docker", "/var/run/docker.sock"]

CMD python docker_scheduler.py