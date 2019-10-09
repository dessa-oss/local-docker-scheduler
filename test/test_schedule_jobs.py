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

    def _generate_tarball(self, job_tar_source_dir):
        import os
        import shutil
        import tarfile
        import uuid

        cwd = os.getcwd()
        dir_suffix = str(uuid.uuid4())
        job_id = f'{job_tar_source_dir}-{dir_suffix}'
        temp_dir = f'/tmp/{job_id}'
        tar_file = f'/tmp/{job_id}.tgz'

        shutil.rmtree(temp_dir, ignore_errors=True)
        shutil.copytree(f'test/fixtures/jobs/{job_tar_source_dir}', temp_dir)

        os.chdir('/tmp')

        try:
            with tarfile.open(tar_file, 'w:gz') as tar:
                tar.add(job_id)

            return tar_file
        finally:
            os.chdir(cwd)
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _upload_job_bundle(self, job_tar_path):
        import requests

        with open(job_tar_path, 'rb') as tarball:
            request_payload = {
                'job_bundle': tarball
            }

            response = requests.post('http://localhost:5000/job_bundle', files=request_payload)
        
        return response

    def _create_job(self, job_tar_source_dir):
        import os.path as path
        
        job_tar_path = self._generate_tarball('fake_job')
        job_bundle_name = path.basename(job_tar_path)[:-4]
        
        self._upload_job_bundle(job_tar_path)
        
        return job_bundle_name

    def _schedule_job(self, job_payload):
        import requests
        return requests.post('http://localhost:5000/scheduled_jobs', json=job_payload)

    def _scheduled_jobs(self):
        import requests
        return requests.get('http://localhost:5000/scheduled_jobs')

    def _job_payload(self, job_bundle_name):
        import os

        cwd = os.getcwd()

        return {
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

    def _submit_and_schedule_job(self):
        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name)
        response = self._schedule_job(job_payload)
        return job_bundle_name, response

    def test_scheduled_job_runs_on_schedule(self):
        import os
        import time

        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name)

        response = self._schedule_job(job_payload)

        self.assertEqual(201, response.status_code)
        self.assertEqual(f'"{job_bundle_name}"\n', response.text)

        time.sleep(8)

        files_from_scheduled_job = os.listdir(f'archives_dir/{job_bundle_name}')
        self.assertIn(len(files_from_scheduled_job), [3, 4])

    def test_schedule_job_with_invalid_payload_gives_400(self):
        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name)

        job_payload.pop('job_id')
        job_payload.pop('spec')
        job_payload.pop('schedule')

        response = self._schedule_job(job_payload)

        self.assertEqual(400, response.status_code)
        self.assertEqual("Job must contain 'job_id', 'spec', 'schedule'", response.text)

    def test_schedule_job_with_valid_payload_structure_but_invalid_payload_contents_400(self):
        import time

        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name)

        job_payload['job_id'] = None
        job_payload['spec'] = None
        job_payload['schedule'] = None

        response = self._schedule_job(job_payload)

        self.assertEqual(400, response.status_code)
        self.assertEqual("Job must contain valid 'job_id', 'spec', 'schedule'", response.text)

    def test_schedule_job_with_valid_payload_structure_but_job_id_None_returns_400(self):
        import os
        import time

        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name)

        job_payload['job_id'] = None
        job_payload['spec'] = None

        response = self._schedule_job(job_payload)

        self.assertEqual(400, response.status_code)
        self.assertEqual("Job must contain valid 'job_id', 'spec', 'schedule'", response.text)

    def test_schedule_job_with_valid_payload_structure_but_spec_None_returns_400(self):
        import os
        import time

        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name)

        job_payload['spec'] = None

        response = self._schedule_job(job_payload)

        self.assertEqual(400, response.status_code)
        self.assertEqual("Job must contain valid 'job_id', 'spec', 'schedule'", response.text)

    def test_schedule_job_with_valid_payload_structure_but_schedule_empty_returns_400(self):
        import os
        import time

        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name)

        job_payload['schedule'] = {}

        response = self._schedule_job(job_payload)

        self.assertEqual(400, response.status_code)
        self.assertEqual("Invalid job schedule", response.text)

    def test_schedule_too_many_jobs_returns_400(self):
        for _ in range(10):
            job_bundle_name, response = self._submit_and_schedule_job()
            self.assertEqual(201, response.status_code)
            self.assertEqual(f'"{job_bundle_name}"\n', response.text)

        job_bundle_name, response = self._submit_and_schedule_job()
        self.assertEqual(400, response.status_code)
        self.assertEqual('Maximum number of scheduled jobs reached', response.text)

    def test_get_scheduled_jobs_returns_empty_dict_and_200_if_no_jobs_scheduled(self):
        response = self._scheduled_jobs()

        self.assertEqual(200, response.status_code)
        self.assertEqual({}, response.json())