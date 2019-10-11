"""
Copyright (C) DeepLearning Financial Technologies Inc. - All Rights Reserved
Unauthorized copying, distribution, reproduction, publication, use of this file, via any medium is strictly prohibited
Proprietary and confidential
Written by Eric lee <e.lee@dessa.com>, 08 2019
"""


import logging
import copy
import os
from time import time

import docker
from docker.types import LogConfig
from docker.errors import APIError

from db import queue, running_jobs, completed_jobs, failed_jobs, peek_lock, gpu_pool, RLock
from local_docker_scheduler import get_app
from tracker_client_plugins import tracker_clients


_workers = {}
_interval = 2
_cron_workers = {}
_max_cron_workers = 10

_WORKING_DIR = os.environ.get('WORKING_DIR', '/working_dir')


class DockerWorker:
    def __init__(self, worker_id, APSSchedulerJob):
        self._worker_id = worker_id
        self._APSSchedulerJob = APSSchedulerJob
        self._job = None
        self._container = None
        self._client = docker.from_env()
        self._lock = RLock()

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

    @property
    def apscheduler_job(self):
        return self._APSSchedulerJob

    @property
    def worker_id(self):
        return self._worker_id

    def run_job(self, job, gpu_ids=None, remove_working_dir=True):
        import subprocess
        self._job = job

        job = self.job
        job_id = job['job_id']

        running_jobs[job_id] = job

        job['spec']['detach'] = True

        lc = LogConfig(type=LogConfig.types.JSON, config={'max-size': '1g', 'labels': 'atlas_logging'})
        job['spec']['log_config'] = lc

        if len(job['spec']['image'].split(':')) < 2:
            job['spec']['image'] = job['spec']['image']+':latest'

        if gpu_ids:
            if len(gpu_ids) > 0:
                job['spec']['environment']["NVIDIA_VISIBLE_DEVICES"] = ",".join(gpu_ids)

        container = None
        try:
            job['start_time'] = time()
            self._container = self._client.containers.run(**job['spec'])
            container = self._container
            logging.info(f"[Worker {self._worker_id}] - Job {job_id} started")

        except Exception as e:
            logging.info(f"[Worker {self._worker_id}] - Job {job_id} failed to start " + str(e))
            job['logs'] = str(e)
            self.stop_job(timeout=0)
            return

        tracker_clients.running(job)

        try:
            return_code = container.wait()
            job['logs'] = container.logs()
            try:
                job['logs'] = job['logs'].decode()
            except (UnicodeDecodeError, AttributeError):
                pass
        except Exception as e:
            job['end_time'] = time()
            logging.info(f"[Worker {self._worker_id}] - Worker {self._worker_id} failed to reconnect to job {job_id}, killing job now")

            self.stop_job(timeout=0)
        else:
            job['end_time'] = time()
            job['return_code'] = return_code
            logging.info(f"[Worker {self._worker_id}] - Job {job_id} finished with return code {return_code}")

            if not return_code['StatusCode']:
                completed_jobs[job_id] = job
                tracker_clients.completed(job)
            else:
                failed_jobs[job_id] = job
                tracker_clients.failed(job)

            self._cleanup_job(container, job_id, remove_working_dir)

        finally:
            self._delete_running_job(job_id)
            if gpu_ids:
                self._unlock_gpus(gpu_ids)

    def _delete_running_job(self, job_id):
        with self._lock:
            self._job = None
            self._container = None
            if job_id in running_jobs:
                del running_jobs[job_id]

    def stop_job(self, reschedule=False, timeout=5):
        if self.job is None:
            return

        job = self.job
        job_id = job['job_id']
        with self._lock:
            if reschedule:
                try:
                    queue.insert(0, job['job_spec'])
                except (KeyError, TypeError):
                    pass

            if self._container:
                try:
                    self._container.stop(timeout=timeout)
                except Exception as e:
                    logging.error("Couldn't stop the container:")
                    logging.error(e)

            try:
                failed_jobs[job_id] = job
                tracker_clients.failed(job)
            except TypeError:
                pass

        self._delete_running_job(job_id)

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

    def _remove_job_from_queue_and_fail(self, error_message):
        self._job = self._poll_queue()
        self.job['logs'] = str(error_message)
        self.stop_job(timeout=0)

    def peek_queue(self):
        logging.debug(f"[Worker {self._worker_id}] - peeking")

        job = None
        gpu_ids_for_job = None
        peek_lock.acquire()
        try:
            peek_job = queue.peek()
            num_gpus = peek_job.get("gpu_spec", {}).get("num_gpus", 0)

            try:
                num_gpus = int(num_gpus)
            except ValueError:
                error_message = f"Foundations ERROR: Job '{peek_job['job_id']}' was given a value that could not be converted to an integer for GPUs usage ({num_gpus})"
                self._remove_job_from_queue_and_fail(error_message)
                raise ResourceWarning(error_message)

            if num_gpus > len(gpu_pool):
                error_message = f"Foundations ERROR: Job '{peek_job['job_id']}' expects to use more GPUs ({num_gpus}) than available ({len(gpu_pool)}), removing from the queue"
                self._remove_job_from_queue_and_fail(error_message)
                raise ResourceWarning(error_message)
            elif num_gpus >= 0:
                available_gpu_ids = self._get_available_gpus()
                if not self._gpu_availability_is_sufficient(num_gpus, len(available_gpu_ids)):
                    raise ResourceWarning(f"[Worker {self._worker_id}] - not enough GPUs available for job, waiting for free resources")
                gpu_ids_for_job = self._lock_gpus(num_gpus, available_gpu_ids)
            else:
                error_message = f"Foundations ERROR: Job '{peek_job['job_id']}' expects an invalid number of GPUs ({num_gpus})"
                self._remove_job_from_queue_and_fail(error_message)
                raise ResourceWarning(error_message)
        except IndexError:
            logging.info(f"[Worker {self._worker_id}] - no jobs in queue, no jobs started")
        except ResourceWarning as error:
            logging.info(error)
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

    @staticmethod
    def remove_working_directory(job_id):
        import os.path as path
        from shutil import rmtree
        try:
            rmtree(path.join(_WORKING_DIR, job_id))
        except FileNotFoundError:
            logging.error(f"Could not cleanup working directory for job {job_id}")
            logging.error(
                f"Please cleanup manually from ~/.foundations/local_docker_scheduler/work_dir/{job_id}")

    @staticmethod
    def _cleanup_job(container, job_id, remove_working_dir):
        try:
            logging.info("Removing container...")
            container.remove(v=True)
            logging.info("Container removed!")
        except APIError as ex:
            logging.error(f"Could not remove container {container.id}")
            logging.error(str(ex))

        if remove_working_dir:
            DockerWorker.remove_working_directory(job_id)

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


def add_cron_worker(scheduled_job):
    try:
        cron_worker_index = sorted(_cron_workers)[-1] + 1
    except IndexError:
        cron_worker_index = 0

    worker_id = f'cron_{cron_worker_index}'

    if len(get_cron_workers()) == _max_cron_workers:
        raise ResourceWarning("Maximum number of scheduled jobs reached. Unable to process job")

    else:
        cron_job = get_app().apscheduler.add_job(func=cron_worker_job,
                                                 trigger='cron',
                                                 **scheduled_job['schedule'],
                                                 args=[cron_worker_index, scheduled_job],
                                                 id=worker_id,
                                                 name=scheduled_job['job_id'],
                                                 jobstore='redis')

        _cron_workers[cron_worker_index] = DockerWorker(worker_id, cron_job)
        return str(worker_id)

def get_cron_workers():
    return _cron_workers


def delete_worker(worker_id, reschedule=False):
    _workers[worker_id].delete(reschedule)
    del _workers[worker_id]

def delete_cron_worker(worker_id):
    _cron_workers[worker_id].delete(reschedule=False)
    del _cron_workers[worker_id]

def delete_cron_job(job_id):
    worker_name = cron_worker_by_job_id(job_id).worker_id
    worker_index = get_cron_worker_index(worker_name)
    delete_cron_worker(worker_index)
    remove_working_directory(job_id)

def get_cron_worker_index(worker_id):
    worker_index = int(worker_id.lstrip('cron_'))
    return worker_index

def worker_by_job_id(job_id):
    for worker_id, worker in _workers.items():
        if worker.job is not None and worker.job['job_id'] == job_id:
            return worker
    else:
        return None


def cron_worker_by_job_id(job_id):
    for worker_id, worker in _cron_workers.items():
        if worker.apscheduler_job.name == job_id:
            return worker
    else:
        return None


def remove_working_directory(job_id):
    return DockerWorker.remove_working_directory(job_id)


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

def cron_worker_job(cron_worker_index, scheduled_job):
    import copy
    from datetime import datetime

    now = datetime.now()
    timestamp = now.strftime('%Y%m%d_%H%M%S')

    old_job_id = scheduled_job['job_id']
    new_job_id = f'{old_job_id}_{timestamp}'

    _create_scheduled_run_directory(old_job_id, new_job_id)
    scheduled_job_run = _create_scheduled_run_job_spec(scheduled_job, new_job_id)

    _cron_workers[cron_worker_index].run_job(scheduled_job_run)

def _create_scheduled_run_directory(old_job_id, new_job_id):
    import os.path as path
    import shutil

    old_job_dir = path.join(_WORKING_DIR, old_job_id)
    new_job_dir = path.join(_WORKING_DIR, new_job_id)

    shutil.rmtree(new_job_dir, ignore_errors=True)
    shutil.copytree(old_job_dir, new_job_dir)

def _create_scheduled_run_job_spec(scheduled_job, new_job_id):
    scheduled_job_run = copy.deepcopy(scheduled_job)
    scheduled_job_run['job_id'] = new_job_id

    spec = scheduled_job_run['spec']
    spec['environment']['JOB_ID'] = new_job_id
    spec['volumes'] = _rewrite_volumes(spec['volumes'], new_job_id)

    return scheduled_job_run

def _rewrite_volumes(spec_volumes, new_job_id):
    import os.path as path

    new_volumes = {}

    for host_path, volume_information in spec_volumes.items():
        if volume_information['bind'] == '/job/job_source':
            host_path = path.join(path.dirname(host_path), new_job_id)

        new_volumes[host_path] = volume_information

    return new_volumes