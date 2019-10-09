import unittest

class TestScheduleJobs(unittest.TestCase):

    def setUp(self):
        import docker
        import os
        from subprocess import Popen
        import time

        client = docker.from_env()
        client.images.pull('python:3.6-alpine')

        os.makedirs('working_dir', exist_ok=True)
        os.makedirs('archives_dir', exist_ok=True)
        env = os.environ.copy()
        env['WORKING_DIR'] = 'working_dir'
        self._server_process = Popen(['python', '-m', 'local_docker_scheduler', '-p', '5000'], env=env)
        time.sleep(1)

    def tearDown(self):
        import shutil

        self._server_process.terminate()
        shutil.rmtree('archives_dir')
        shutil.rmtree('working_dir')

    def _upload_job_bundle(self, job_tar_name):
        import requests

        with open(f'test/fixtures/jobs/{job_tar_name}.tgz', 'rb') as tarball:
            request_payload = {
                'job_bundle': tarball
            }

            response = requests.post('http://localhost:5000/job_bundle', files=request_payload)
        
        return response

    def _schedule_job(self, job_payload):
        import requests
        return requests.post('http://localhost:5000/scheduled_jobs', json=job_payload)

    def test_scheduled_job_runs_on_schedule(self):
        import os
        import time

        job_bundle_name = 'fake_job'

        self._upload_job_bundle(job_bundle_name)

        cwd = os.getcwd()

        job_payload = {
            'job_id': job_bundle_name,
            'spec': {
                'image': 'python:3.6-alpine',
                'volumes': {
                    f'{cwd}/working_dir/{job_bundle_name}': {
                        'bind': '/job/job_source',
                        'mode': 'rw'
                    },
                    f'{cwd}/archives_dir/{job_bundle_name}': {
                        'bind': '/job/job_archive',
                        'mode': 'rw'
                    }
                },
                'working_dir': '/job/job_source',
                'environment': {
                    'JOB_ID': job_bundle_name,
                    'ENTRYPOINT': 'whatever_i_want.py'
                },
                'entrypoint': [
                    '/bin/sh',
                    '-c'
                ],
                'command': [
                    'python ${ENTRYPOINT} && chmod -R a+rw /job/job_archive'
                ]
            },
            'metadata': {'project_name': 'test', 'username': 'shaz'},
            'schedule': {
                'second': '*/2'
            }
        }

        response = self._schedule_job(job_payload)

        self.assertEqual(201, response.status_code)
        self.assertEqual(f'"{job_bundle_name}"\n', response.text)

        time.sleep(8)

        files_from_scheduled_job = os.listdir(f'archives_dir/{job_bundle_name}')
        self.assertIn(len(files_from_scheduled_job), [3, 4])

    def test_schedule_job_with_invalid_payload_gives_400(self):
        job_bundle_name = 'fake_job'

        self._upload_job_bundle(job_bundle_name)

        job_payload = {
            'metadata': {'project_name': 'test', 'username': 'shaz'},
        }

        response = self._schedule_job(job_payload)

        self.assertEqual(400, response.status_code)
        self.assertEqual("Job must contain 'job_id', 'spec', 'schedule'", response.text)

    def test_schedule_job_with_valid_payload_structure_but_invalid_payload_contents_400(self):
        import os
        import time

        job_bundle_name = 'fake_job'

        self._upload_job_bundle(job_bundle_name)

        cwd = os.getcwd()

        job_payload = {
            'job_id': None,
            'spec': None,
            'metadata': {'project_name': 'test', 'username': 'shaz'},
            'schedule': None
        }

        response = self._schedule_job(job_payload)

        self.assertEqual(400, response.status_code)
        self.assertEqual("Job must contain valid 'job_id', 'spec', 'schedule'", response.text)

    def test_schedule_job_with_valid_payload_structure_but_job_id_None_returns_400(self):
        import os
        import time

        job_bundle_name = 'fake_job'

        self._upload_job_bundle(job_bundle_name)

        cwd = os.getcwd()

        job_payload = {
            'job_id': None,
            'spec': None,
            'metadata': {'project_name': 'test', 'username': 'shaz'},
            'schedule': {
                'second': '*/2'
            }
        }

        response = self._schedule_job(job_payload)

        self.assertEqual(400, response.status_code)
        self.assertEqual("Job must contain valid 'job_id', 'spec', 'schedule'", response.text)

    def test_schedule_job_with_valid_payload_structure_but_spec_None_returns_400(self):
        import os
        import time

        job_bundle_name = 'fake_job'

        self._upload_job_bundle(job_bundle_name)

        cwd = os.getcwd()

        job_payload = {
            'job_id': 'fake_job',
            'spec': None,
            'metadata': {'project_name': 'test', 'username': 'shaz'},
            'schedule': {
                'second': '*/2'
            }
        }

        response = self._schedule_job(job_payload)

        self.assertEqual(400, response.status_code)
        self.assertEqual("Job must contain valid 'job_id', 'spec', 'schedule'", response.text)