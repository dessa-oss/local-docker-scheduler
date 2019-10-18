docker build -t docker-test . && \
docker run -v $(realpath ..):/app -v /var/run/docker.sock:/var/run/docker.sock docker-test

