"""
Copyright (C) DeepLearning Financial Technologies Inc. - All Rights Reserved
Unauthorized copying, distribution, reproduction, publication, use of this file, via any medium is strictly prohibited
Proprietary and confidential
Written by Eric lee <e.lee@dessa.com>, 08 2019
"""

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


tracker_clients = _TrackerClientList()
del _TrackerClientList
