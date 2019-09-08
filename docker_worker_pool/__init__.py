import docker
from docker.types import LogConfig
import collections
import logging
from db import queue, running_jobs, completed_jobs, failed_jobs
import copy
from time import time
from local_docker_scheduler import app
from tracker_client_plugins import tracker_clients


_workers = {}
_interval = 2


class DockerWorker:
    def __init__(self, worker_id, APSSchedulerJob):
        self._worker_id = worker_id
        self._APSSchedulerJob = APSSchedulerJob
        self._job_spec = None
        self._job_id = None
        self._container = None
        self._client = docker.from_env()

    @property
    def job_id(self):
        return self._job_id

    @property
    def job_spec(self):
        return self._job_spec

    def stop(self, reschedule):
        if reschedule and self._job_spec:
            queue.insert(0, self._job_spec)
        if self._container:
            self._container.stop()
        try:
            del running_jobs[self._job_id]
        except KeyError:
            pass
        self._job_spec = None
        self._job_id = None
        self._container = None

    def kill(self, reschedule):
        self.stop(reschedule)
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
    #
    # def log_path(self):
    #     if self._container is not None:
    #         api_client = docker.APIClient()
    #         return api_client.inspect_container(self._container.id)['LogPath']
    #     else:
    #         return None

    def container_id(self):
        if self._container is not None:
            return self._container.id
        else:
            return None

    def poll_queue(self):
        logging.debug(f"[Worker {self._worker_id}] - polling")

        try:
            job = copy.deepcopy(queue.pop(0))
            running_jobs[job['job_id']] = job
        except IndexError:
            logging.info(f"[Worker {self._worker_id}] - no jobs in queue, no jobs started")
            return

        lc = LogConfig(type=LogConfig.types.JSON, config={'max-size': '1g', 'labels': 'atlas_logging'})

        job['spec']['detach'] = True
        job['spec']['log_config'] = lc

        try:
            start_time = time()
            self._container = self._client.containers.run(**job['spec'])
            self._job_spec = job['spec']
            self._job_id = job['job_id']
            logging.info(f"[Worker {self._worker_id}] - Job {job['job_id']} started")
        except Exception as e:
            logging.info(f"[Worker {self._worker_id}] - Job {job['job_id']} failed to start " + str(e))
            job['logs'] = str(e)
            self._job_spec = None
            self._job_id = None
            self._container = None
            failed_jobs[job['job_id']] = job
            del running_jobs[job['job_id']]
            return

        job['start_time'] = start_time
        tracker_clients.running(job)

        try:
            return_code = self._container.wait()
            job['logs'] = self._container.logs()
            try:
                job['logs'] = job['logs'].decode()
            except (UnicodeDecodeError, AttributeError):
                pass
        except Exception as e:
            self._container.kill()
            end_time = time()
            logging.info(f"[Worker {self._worker_id}] - Worker {self._worker_id} failed to reconnect to job {job['job_id']}, killing job now")

            job['end_time'] = end_time
            failed_jobs[job['job_id']] = job
            tracker_clients.failed(job)
        else:
            end_time = time()
            logging.info(f"[Worker {self._worker_id}] - Job {job['job_id']} finished with return code {return_code}")

            job['end_time'] = end_time
            job['return_code'] = return_code
            if not return_code['StatusCode']:
                completed_jobs[job['job_id']] = job
                tracker_clients.completed(job)
            else:
                failed_jobs[job['job_id']] = job
                tracker_clients.failed(job)
        finally:
            del running_jobs[job['job_id']]
            self._job_spec = None
            self._job_id = None
            self._container = None


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
    _workers[worker_id] = DockerWorker(worker_id, job)
    return str(worker_id)


def kill(worker_id, reschedule=False):
    _workers[worker_id].kill(reschedule)
    del _workers[worker_id]


def worker_by_job_id(job_id):
    for worker_id, worker in _workers.items():
        if worker.job_id == job_id:
            return worker
    else:
        return None


def stop(job_id, reschedule=False):
    worker = worker_by_job_id(job_id)
    if worker is None:
        raise KeyError("Job id was not found")
    else:
        worker.stop(reschedule)


def worker_job(worker_id):
    _workers[worker_id].poll_queue()