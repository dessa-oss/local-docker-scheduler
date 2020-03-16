from abc import ABC, abstractmethod
from importlib import import_module
class TrackerClientBase(ABC):
    @abstractmethod
    def queued(self, job):
        pass

    @abstractmethod
    def running(self, job):
        pass

    @abstractmethod
    def completed(self, job):
        pass

    @abstractmethod
    def failed(self, job):
        pass

    @abstractmethod
    def delete(self, job):
        pass

    @abstractmethod
    def create_project(self, job):
        pass

    @abstractmethod
    def track_scheduled_job_run(self, job, run):
        pass

class _TrackerClientList(TrackerClientBase):
    def __init__(self):
        self._clients = []

    def queued(self, job):
        return [client.queued(job) for client in self._clients]

    def running(self, job):
        return [client.running(job) for client in self._clients]

    def completed(self, job):
        return [client.completed(job) for client in self._clients]

    def failed(self, job):
        return [client.failed(job) for client in self._clients]

    def delete(self, job):
        return [client.delete(job) for client in self._clients]

    def add(self, name, *args, **kwargs):
        camel_name = ''.join(x.capitalize() or '_' for x in name.split('_'))
        self._clients.append(getattr(import_module('.'.join([__name__, name])), camel_name)(*args, **kwargs))

    def create_project(self, job):
        return [client.create_project(job) for client in self._clients]

    def track_scheduled_job_run(self, job, run):
        return [client.track_scheduled_job_run(job, run) for client in self._clients]


tracker_clients = _TrackerClientList()
del _TrackerClientList
