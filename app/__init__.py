from flask import Flask
from docker_worker_pool import WorkerPool
from repositionable_queue import Queue


app = Flask(__name__)

wp = WorkerPool(2)
q = Queue()

from app import routes
