"""
Copyright (C) DeepLearning Financial Technologies Inc. - All Rights Reserved
Unauthorized copying, distribution, reproduction, publication, use of this file, via any medium is strictly prohibited
Proprietary and confidential
Written by Eric lee <e.lee@dessa.com>, 08 2019
"""


_app = None


def get_app(num_workers=1):
    import atexit

    import yaml
    from flask import Flask
    from flask_apscheduler import APScheduler

    from tracker_client_plugins import tracker_clients
    import docker_worker_pool
    from local_docker_scheduler import routes

    global _app
    if _app is not None:
        return _app

    _app = Flask(__name__)

    scheduler = APScheduler()

    # it is also possible to enable the API directly
    # scheduler.api_enabled = True
    scheduler.init_app(_app)
    atexit.register(lambda: scheduler.shutdown(wait=False))

    # load tracker plugins
    try:
        with open('tracker_client_plugins.yaml', 'r') as f:
            tracker_dict = yaml.load(f, Loader=yaml.FullLoader)

        for plugin_name, kwargs in tracker_dict.items():
            tracker_clients.add(plugin_name, **kwargs)
    except FileNotFoundError:
        pass

    for i in range(num_workers):
        docker_worker_pool.add()

    scheduler.start()

    return _app
