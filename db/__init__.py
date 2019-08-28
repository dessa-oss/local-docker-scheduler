from repositionable_queue import Queue
from db.sqlite_dict_connection import connect


failed_jobs = connect('./failed_jobs.sqlite')
completed_jobs = connect('./completed_jobs.sqlite')
running_jobs = connect('./running_jobs.sqlite')
queue = Queue()
