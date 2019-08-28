from flask import Flask
from flask_apscheduler import APScheduler

app = Flask(__name__)

from app import routes
scheduler = APScheduler()

# it is also possible to enable the API directly
# scheduler.api_enabled = True
scheduler.init_app(app)

import docker_worker_pool
docker_worker_pool.add()

scheduler.start()