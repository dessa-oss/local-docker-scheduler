import docker
import collections
import logging


class WorkerPool:
    label = 'atlas_job'

    class NoResourcesException(Exception):
        pass

    def __init__(self, max_workers):
        self.client = docker.from_env()
        self.max_workers = max_workers

    def _worker_available(self):
        return len(self.client.containers.list(filters={'label': WorkerPool.label})) < self.max_workers

    def start_job(self, job):
        current_job = dict(job)
        current_job['detach'] = True
        if 'labels' in current_job:
            if isinstance(current_job['labels'], collections.Mapping):
                current_job['labels'][WorkerPool.label] = ""
            else:
                current_job['labels'].append(WorkerPool.label)
        else:
            current_job['labels'] = [WorkerPool.label]

        if self._worker_available():
            self.client.containers.run(**current_job)
            logging.debug(current_job)
        else:
            raise self.NoResourcesException()
