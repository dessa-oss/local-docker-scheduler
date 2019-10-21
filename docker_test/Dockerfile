FROM docker.shehanigans.net/foundations-ci-tester

VOLUME /app 

WORKDIR /app

CMD . ./.env && ./ci_install_requirements.sh && ./setup_filesystem.sh && python3 -m unittest test -f -v

