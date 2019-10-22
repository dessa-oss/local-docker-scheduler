all: build test

.PHONY: build
build:
	. ./.env
	cp requirements.txt docker/requirements.txt
	docker build -t docker-test docker/
	rm docker/requirements.txt

test:
	docker run --rm -v $(realpath ..):/app \
		-v /var/run/docker.sock:/var/run/docker.sock \
		-v /tmp/local_docker_scheduler/:/tmp/local_docker_scheduler \
		docker-test
