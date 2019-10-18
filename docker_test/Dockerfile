FROM python:3.7.4-alpine

VOLUME /app 

WORKDIR /app

CMD . ./.env && ./ci_install_requirements.sh && ./setup_filesystem.sh && python -m unittest test -f

