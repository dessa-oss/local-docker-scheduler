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
from docker.errors import APIError

from db import queue, running_jobs, completed_jobs, failed_jobs, peek_lock, gpu_pool
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

    def run_job(self, job, gpu_ids=None):
        import subprocess
        self._job = job

        running_jobs[self.job['job_id']] = self.job

        self.job['spec']['detach'] = True

        lc = LogConfig(type=LogConfig.types.JSON, config={'max-size': '1g', 'labels': 'atlas_logging'})
        self.job['spec']['log_config'] = lc

        if len(self.job['spec']['image'].split(':')) < 2:
            self.job['spec']['image'] = self.job['spec']['image']+':latest'

        logging.info(f"*** {self.job['spec']}")
        if gpu_ids:
            if len(gpu_ids) > 0:
                self.job['spec']['environment']["NVIDIA_VISIBLE_DEVICES"] = ",".join(gpu_ids)

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

            self.cleanup_job()

        finally:
            del running_jobs[self.job['job_id']]
            if gpu_ids:
                self._unlock_gpus(gpu_ids)
            self._job = None
            self._container = None

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

        self.cleanup_job()
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

    def _get_available_gpus(self):
        return [key for key, value in gpu_pool.items() if value == "unlocked"]

    def _gpu_availability_is_sufficient(self, num_required, num_available):
        if num_required > num_available:
            return False
        return True

    def _lock_gpus(self, num_required, available_ids):
        locked_gpus = []
        for i in range(num_required):
            gpu_pool[available_ids[i]] = "locked"
            locked_gpus.append(available_ids[i])
        return locked_gpus

    def _unlock_gpus(self, ids_to_unlock):
        if ids_to_unlock:
            for gpu_id in ids_to_unlock:
                gpu_pool[gpu_id] = "unlocked"

    def peek_queue(self):
        logging.debug(f"[Worker {self._worker_id}] - peeking")

        job = None
        gpu_ids_for_job = None
        peek_lock.acquire()
        try:
            peek_job = queue.peek()
            logging.info(f"***Peek job: {peek_job}")
            num_gpus = peek_job.get("gpu_spec", {}).get("num_gpus", 0)
            logging.info(f"***Num GPUs: {num_gpus}")
            logging.info(f"***GPU pool: {gpu_pool}")
            if num_gpus > 0:
                available_gpu_ids = self._get_available_gpus()
                if not self._gpu_availability_is_sufficient(num_gpus, len(available_gpu_ids)):
                    raise ResourceWarning
                gpu_ids_for_job = self._lock_gpus(num_gpus, available_gpu_ids)
        except IndexError:
            logging.info(f"[Worker {self._worker_id}] - no jobs in queue, no jobs started")
        except ResourceWarning:
            logging.info(f"[Worker {self._worker_id}] - not enough GPUs available for job, waiting for free resources")
        else:
            job = self._poll_queue()
        finally:
            peek_lock.release()
            try:
                if job:
                    self.run_job(job, gpu_ids_for_job)
            finally:
                self._unlock_gpus(gpu_ids_for_job)

    def _poll_queue(self):
        logging.debug(f"[Worker {self._worker_id}] - polling")

        try:
            job = copy.deepcopy(queue.pop(0))
            return job
        except IndexError:
            logging.info(f"[Worker {self._worker_id}] - no jobs in queue, no jobs started") # change message
            return None

    def cleanup_job(self):
        from shutil import rmtree
        try:
            logging.info("Removing container...")
            self._container.remove(v=True)
            logging.info("Container removed!")
        except APIError as ex:
            logging.error(f"Could not remove container {self._container.id}")
            logging.error(str(ex))

        try:
            rmtree('/working_dir/'+self.job['job_id'])
        except FileNotFoundError:
            logging.error(f"Could not cleanup working directory for job {self.job['job_id']}")
            logging.error(
                f"Please cleanup manually from ~/.foundations/local_docker_scheduler/work_dir/{self.job['job_id']}")


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
    logging.info(f"**** {worker_id}")
    logging.info(f"**** {id(job)}")
    _workers[worker_id] = DockerWorker(worker_id, job)
    logging.info(f"**** {_workers}")
    logging.info(f"**** {get_app().apscheduler.get_jobs()}")
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


def delete_archive(job_id):
    from shutil import rmtree
    from uuid import UUID

    try:
        uuid_obj = UUID(job_id, version=4)
    except ValueError:
        logging.error("A valid job UUID was not provided")
        raise IndexError

    try:
        rmtree('/archives/archive/'+job_id)
        logging.info(f"Successfully deleted archive for Job {job_id}")
    except FileNotFoundError:
        logging.error(f"Could not delete archive for Job {job_id}")
        logging.error(f"Please delete archive manually from ~/.foundations/job_data/")
        raise IndexError


def worker_job(worker_id):
    _workers[worker_id].peek_queue()
