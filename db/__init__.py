# from db.repositionable_queue import Queue
# from db.sqlite_dict_connection import connect
# from .redis_connection import RedisDict, RedisList

# failed_jobs = connect('./failed_jobs.sqlite')
# completed_jobs = connect('./completed_jobs.sqlite')
# running_jobs = connect('./running_jobs.sqlite')
# queue = Queue()
#
# failed_jobs = RedisDict("failed_jobs", "127.0.0.1", "6379")
# completed_jobs = RedisDict("completed_jobs", "127.0.0.1", "6379")
# running_jobs = RedisDict("running_jobs", "127.0.0.1", "6379")
# queue = RedisList("queue", "127.0.0.1", "6379")

from importlib import import_module
import yaml


def _db_class(t):
    name = t.rsplit('.', 1)
    return getattr(import_module('.'.join([__name__, name[0]])), name[1])


with open('database.config.yaml', 'r') as f:
    database_dict = yaml.load(f)

failed_jobs = _db_class(database_dict['failed_jobs']['type'])(**database_dict['failed_jobs']['args'])
completed_jobs = _db_class(database_dict['completed_jobs']['type'])(**database_dict['completed_jobs']['args'])
running_jobs = _db_class(database_dict['running_jobs']['type'])(**database_dict['running_jobs']['args'])
queue = _db_class(database_dict['queue']['type'])(**database_dict['queue']['args'])