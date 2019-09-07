from flask import Flask
from flask_apscheduler import APScheduler
import atexit

app = Flask(__name__)

from local_docker_scheduler import routes
scheduler = APScheduler()

# it is also possible to enable the API directly
# scheduler.api_enabled = True
scheduler.init_app(app)
atexit.register(lambda: scheduler.shutdown(wait=False))

import docker_worker_pool
docker_worker_pool.add()

scheduler.start()