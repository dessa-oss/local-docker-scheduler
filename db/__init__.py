"""
Copyright (C) DeepLearning Financial Technologies Inc. - All Rights Reserved
Unauthorized copying, distribution, reproduction, publication, use of this file, via any medium is strictly prohibited
Proprietary and confidential
Written by Eric lee <e.lee@dessa.com>, 08 2019
"""


from importlib import import_module
from threading import RLock
import yaml


def _db_class(t):
    name = t.rsplit('.', 1)
    return getattr(import_module('.'.join([__name__, name[0]])), name[1])


with open('database.config.yaml', 'r') as f:
    database_dict = yaml.load(f, Loader=yaml.FullLoader)

peek_lock = RLock()

failed_jobs = _db_class(database_dict['failed_jobs']['type'])(**database_dict['failed_jobs']['args'])
completed_jobs = _db_class(database_dict['completed_jobs']['type'])(**database_dict['completed_jobs']['args'])
running_jobs = _db_class(database_dict['running_jobs']['type'])(**database_dict['running_jobs']['args'])
queue = _db_class(database_dict['queue']['type'])(**database_dict['queue']['args'])
gpu_pool = {}  # TODO: This is currently thread safe based on the implementation of the pewk queue and where it is being used, but NOT thread safe if anyone else touched it directly