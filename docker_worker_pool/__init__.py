import docker
from docker.types import LogConfig
import collections
import logging
from db import queue, running_jobs, completed_jobs, failed_jobs
import copy
from time import time
from app import app


_workers = {}
_interval = 2


def add():
    try:
        worker_id = sorted(_workers)[-1] + 1
    except IndexError:
        worker_id = 0
    job = app.apscheduler.add_job(func=worker_job,
                                  trigger='interval',
                                  seconds=_interval,
                                  args=[worker_id],
                                  id=str(worker_id))
    _workers[worker_id] = job
    return str(worker_id)


def remove(worker_id):
    _workers[worker_id].remove()
    del _workers[worker_id]
    return


def worker_job(worker_id):
    logging.debug(f"[Worker {worker_id}] - pulling")
    label = "atlas_job"

    client = docker.from_env()

    lc = LogConfig(type=LogConfig.types.JSON, config={'max-size': '1g', 'labels': 'atlas_logging'})

    try:
        job = copy.deepcopy(queue.pop(0))
    except IndexError:
        logging.info(f"[Worker {worker_id}] - no jobs in queue, no jobs started")
        return

    job['spec']['detach'] = True
    job['spec']['log_config'] = lc
    if 'labels' in job['spec']:
        if isinstance(job['spec']['labels'], collections.Mapping):
            job['spec']['labels'][label] = ""
        else:
            job['spec']['labels'].append(label)
    else:
        job['spec']['labels'] = [label]

    try:
        start_time = time()
        container = client.containers.run(**job['spec'])
        logging.info(f"[Worker {worker_id}] - Job {job['job_id']} started")
    except Exception as e:
        logging.info(f"[Worker {worker_id}] - Job {job['job_id']} failed to start " + e)
        return

    job['start_time'] = start_time
    running_jobs[job['job_id']] = job

    try:
        return_code = container.wait()
        end_time = time()
    except Exception as e:
        logging.info(f"[Worker {worker_id}] - Worker {worker_id} failed to reconnect to job {job['job_id']}, killing job now")
        container.kill()
        end_time = time()

        job['end_time'] = end_time
        failed_jobs[job['job_id']] = job
    else:
        logging.info(f"[Worker {worker_id}] - Job {job['job_id']} finished with return code {return_code}")

        job['end_time'] = end_time
        job['return_code'] = return_code
        completed_jobs[job['job_id']] = job
    finally:
        del running_jobs[job['job_id']]
