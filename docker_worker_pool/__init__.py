"""
Copyright (C) DeepLearning Financial Technologies Inc. - All Rights Reserved
Unauthorized copying, distribution, reproduction, publication, use of this file, via any medium is strictly prohibited
Proprietary and confidential
Written by Eric lee <e.lee@dessa.com>, 08 2019
"""


import logging
import copy
from time import time

import docker
from docker.types import LogConfig

from db import queue, running_jobs, completed_jobs, failed_jobs
from local_docker_scheduler import get_app
from tracker_client_plugins import tracker_clients


_workers = {}
_interval = 2

class DockerWorker:
    def __init__(self, worker_id, APSSchedulerJob):
        self._worker_id = worker_id
        self._APSSchedulerJob = APSSchedulerJob
        self._job = None
        self._container = None
        self._client = docker.from_env()

    @property
    def status(self):
        if self._job:
            if self._container:
                return "running"
            else:
                return "pending"
        else:
            return "pending"

    @property
    def job(self):
        return self._job

    def run_job(self, job):
        import subprocess
        self._job = job

        running_jobs[self.job['job_id']] = self.job

        self.job['spec']['detach'] = True

        lc = LogConfig(type=LogConfig.types.JSON, config={'max-size': '1g', 'labels': 'atlas_logging'})
        self.job['spec']['log_config'] = lc

        if len(self.job['spec']['image'].split(':')) < 2:
            self.job['spec']['image'] = self.job['spec']['image']+':latest'

        # if self.job['spec'].get('runtime') == 'nvidia':
        #     try:
        #         gpu_stats = subprocess.check_output(["nvidia-smi", "--format=csv",
        #                                              "--query-gpu=memory.used,memory.free"])
        #     except FileNotFoundError as fe:
        #         logging.error("NVIDIA container run-time not found")
        #         logging.info(f"[Worker {self._worker_id}] - Job {self.job['job_id']} failed to start " + str(fe))
        #         self.job['logs'] = "Error: NVIDIA container run-time not found"
        #         self.stop_job(timeout=0)
        #         return

        try:
            self.job['start_time'] = time()
            self._container = self._client.containers.run(**self.job['spec'])
            logging.info(f"[Worker {self._worker_id}] - Job {self.job['job_id']} started")

        except Exception as e:
            logging.info(f"[Worker {self._worker_id}] - Job {self.job['job_id']} failed to start " + str(e))
            self.job['logs'] = str(e)
            self.stop_job(timeout=0)
            return

        tracker_clients.running(self.job)

        try:
            return_code = self._container.wait()
            self.job['logs'] = self._container.logs()
            try:
                self.job['logs'] = self.job['logs'].decode()
            except (UnicodeDecodeError, AttributeError):
                pass
        except Exception as e:
            self.job['end_time'] = time()
            logging.info(f"[Worker {self._worker_id}] - Worker {self._worker_id} failed to reconnect to job {self.job['job_id']}, killing job now")

            self.stop_job(timeout=0)
        else:
            self.job['end_time'] = time()
            self.job['return_code'] = return_code
            logging.info(f"[Worker {self._worker_id}] - Job {self.job['job_id']} finished with return code {return_code}")

            if not return_code['StatusCode']:
                completed_jobs[self.job['job_id']] = self.job
                tracker_clients.completed(self.job)
            else:
                failed_jobs[self.job['job_id']] = self.job
                tracker_clients.failed(self.job)
        finally:
            del running_jobs[self.job['job_id']]
            self._job = None
            self._container = None
            self._container.cleanup()

    def stop_job(self, reschedule=False, timeout=5):
        if reschedule:
            try:
                queue.insert(0, self.job['job_spec'])
            except (KeyError, TypeError):
                pass

        if self._container:
            self._container.stop(timeout=timeout)

        try:
            del running_jobs[self.job['job_id']]
        except TypeError:
            pass

        try:
            failed_jobs[self.job['job_id']] = self.job
            tracker_clients.failed(self.job)
        except TypeError:
            pass

        self._job = None
        self._container = None

    def delete(self, reschedule):
        self.stop_job(reschedule)
        self._APSSchedulerJob.remove()

    def logs(self):
        if self._container is not None:
            logs = self._container.logs()

            try:
                logs = logs.decode()
            except (UnicodeDecodeError, AttributeError):
                pass

            return logs
        else:
            return None

    def container_id(self):
        if self._container is not None:
            return self._container.id
        else:
            return None

    def poll_queue(self):
        logging.debug(f"[Worker {self._worker_id}] - polling")

        try:
            job = copy.deepcopy(queue.pop(0))
            self.run_job(job)
        except IndexError:
            logging.info(f"[Worker {self._worker_id}] - no jobs in queue, no jobs started")

    def cleanup(self):
        try:
            self._container.remove()
        except docker.errors.APIError as ex:
            logging.error(f"Could not remove container {self._container.id}")
            logging.error(str(ex))


def add():
    try:
        worker_id = sorted(_workers)[-1] + 1
    except IndexError:
        worker_id = 0
    job = get_app().apscheduler.add_job(func=worker_job,
                                  trigger='interval',
                                  seconds=_interval,
                                  args=[worker_id],
                                  id=str(worker_id))
    _workers[worker_id] = DockerWorker(worker_id, job)
    return str(worker_id)


def delete_worker(worker_id, reschedule=False):
    _workers[worker_id].delete(reschedule)
    del _workers[worker_id]


def worker_by_job_id(job_id):
    for worker_id, worker in _workers.items():
        if worker.job is not None and worker.job['job_id'] == job_id:
            return worker
    else:
        return None


def stop_job(job_id, reschedule=False):
    worker = worker_by_job_id(job_id)
    if worker is None:
        raise KeyError("Job id was not found")
    else:
        worker.stop_job(reschedule)


def worker_job(worker_id):
    _workers[worker_id].poll_queue()