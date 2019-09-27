import unittest
import threading
import logging
from werkzeug.serving import make_server
from local_docker_scheduler import get_app
import requests

log = logging.getLogger(__name__)
server = None
port = 8642
host = '127.0.0.1'


class ServerThread(threading.Thread):

    def __init__(self, app):
        threading.Thread.__init__(self)
        self.srv = make_server(host, port, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        log.info('starting server')
        self.srv.serve_forever()

    def shutdown(self):
        self.srv.shutdown()


def start_server():
    global server
    app = get_app(1)
    server = ServerThread(app)
    server.start()
    log.info('server started')


def stop_server():
    global server
    server.shutdown()


def setUpModule():
    start_server()


def tearDownModule():
    stop_server()


class TestBasicRoutes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        'called once, before any tests'
        pass

    @classmethod
    def tearDownClass(cls):
        'called once, after all tests, if setUpClass successful'
        pass

    def setUp(self):
        'called multiple times, before every test method'
        pass

    def tearDown(self):
        'called multiple times, after every test method'
        pass

    def test_get_empty_queued_jobs(self):
        'Getting an empty queued job list'
        response = requests.get(f"http://{host}:{port}/queued_jobs")
        self.assertEqual(response.json(), {})
        self.assertEqual(response.status_code, 200)

    def test_get_empty_completed_jobs(self):
        'Getting an empty completed job list'
        response = requests.get(f"http://{host}:{port}/completed_jobs")
        self.assertEqual(response.json(), {})
        self.assertEqual(response.status_code, 200)

    def test_get_empty_running_jobs(self):
        'Getting an empty running job list'
        response = requests.get(f"http://{host}:{port}/running_jobs")
        self.assertEqual(response.json(), {})
        self.assertEqual(response.status_code, 200)

    def test_get_empty_failed_jobs(self):
        'Getting an empty failed job list'
        response = requests.get(f"http://{host}:{port}/failed_jobs")
        self.assertEqual(response.json(), {})
        self.assertEqual(response.status_code, 200)

    def test_get_bad_job(self):
        'Retrieving a non-existing job'
        response = requests.get(f"http://{host}:{port}/queued_jobs/not-a-job")
        self.assertEqual(response.status_code, 404)

    def test_submit_job_no_json(self):
        'Submitting an ill-formed job'

        response = requests.post(f"http://{host}:{port}/queued_jobs")
        self.assertEqual(response.status_code, 400)

    def test_submit_job_bad_json(self):
        'Submitting an ill-formed job'
        response = requests.post(f"http://{host}:{port}/queued_jobs",
                                 json={})
        self.assertEqual(response.status_code, 400)