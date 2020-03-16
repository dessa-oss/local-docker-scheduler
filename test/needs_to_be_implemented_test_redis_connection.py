import unittest

from db.redis_connection import RedisList


client = None
redis_container = None

def setUpModule():
    import docker
    global redis_container

    client = docker.from_env()
    redis_container = client.containers.run("redis:5-alpine",
                                            detach=True,
                                            port={8642: 6379})

def tearDown():
    global redis_container
    redis_container.remove()


class TestRedisList(unittest.TestCase):
    def setUp(self):

        self.data = {}

    def test_add_value(self):
        l = RedisList()

    def tearDown(self):
        pass
