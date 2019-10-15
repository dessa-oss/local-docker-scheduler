"""
Copyright (C) DeepLearning Financial Technologies Inc. - All Rights Reserved
Unauthorized copying, distribution, reproduction, publication, use of this file, via any medium is strictly prohibited
Proprietary and confidential
Written by Eric lee <e.lee@dessa.com>, 08 2019
"""

import logging

_app = None


def get_app():
    import atexit
    import os

    import yaml
    from flask import Flask
    from flask_apscheduler import APScheduler
    from apscheduler.jobstores.redis import RedisJobStore
    from apscheduler.jobstores.memory import MemoryJobStore

    from tracker_client_plugins import tracker_clients
    import docker_worker_pool
    from docker_worker_pool import get_cron_workers, DockerWorker

    global _app
    if _app is not None:
        return _app

    _app = Flask(__name__)

    # load tracker plugins
    try:
        with open('tracker_client_plugins.yaml', 'r') as f:
            tracker_dict = yaml.load(f, Loader=yaml.FullLoader)

        for plugin_name, kwargs in tracker_dict.items():
            tracker_clients.add(plugin_name, **kwargs)
    except FileNotFoundError:
        pass

    job_stores = {
        'redis': RedisJobStore(host=tracker_dict['redis_tracker_client']['host'],
                               port=tracker_dict['redis_tracker_client']['port']),
        'default': MemoryJobStore()}

    _app.config['SCHEDULER_JOBSTORES'] = job_stores

    scheduler = APScheduler()

    # it is also possible to enable the API directly
    # scheduler.api_enabled = True
    scheduler.init_app(_app)
    atexit.register(lambda: scheduler.shutdown(wait=False))

    num_workers = int(os.environ.get("NUM_WORKERS", 1))
    for i in range(num_workers):
        docker_worker_pool.add()

    scheduler.start()

    loaded_scheduled_jobs = scheduler.get_jobs(jobstore='redis')
    _cron_workers = get_cron_workers()
    if loaded_scheduled_jobs:
        for cron_job in loaded_scheduled_jobs:
            cron_worker_index = docker_worker_pool.get_cron_worker_index(cron_job.id)
            _cron_workers[cron_worker_index] = DockerWorker(cron_job.id, cron_job)

    return _app
