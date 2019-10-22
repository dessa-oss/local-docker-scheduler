FROM docker.shehanigans.net/foundations-ci-tester

VOLUME /app 

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt
RUN ./setup_filesystem.sh

CMD python3 -m local_docker_scheduler -p 5000

