from db.repositionable_queue import Queue
from db.sqlite_dict_connection import connect
from .redis_connection import RedisDict, RedisList

# failed_jobs = connect('./failed_jobs.sqlite')
# completed_jobs = connect('./completed_jobs.sqlite')
# running_jobs = connect('./running_jobs.sqlite')
# queue = Queue()

failed_jobs = RedisDict("failed_jobs", "127.0.0.1", "6379")
completed_jobs = RedisDict("completed_jobs", "127.0.0.1", "6379")
running_jobs = RedisDict("running_jobs", "127.0.0.1", "6379")
queue = RedisList("queue", "127.0.0.1", "6379")