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

    def _delete_scheduled_job(self, job_id):
        import requests
        import time

        response = requests.delete(f'http://localhost:5000/scheduled_jobs/{job_id}')
        time.sleep(1)
        return response

    def _update_job_schedule(self, job_id, cron_schedule):
        import requests
        return requests.patch(f'http://localhost:5000/scheduled_jobs/{job_id}', json={'schedule': cron_schedule})

    def _pause_job(self, job_id):
        return self._put_to_job(job_id, 'paused')

    def _resume_job(self, job_id):
        return self._put_to_job(job_id, 'resumed')

    def _put_to_job(self, job_id, status):
        return self._put_to_job_with_payload(job_id, {'status': status})

    def _put_to_job_with_payload(self, job_id, payload):
        import requests
        return requests.put(f'http://localhost:5000/scheduled_jobs/{job_id}', json=payload)

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
                    f'{cwd}/archives_dir': {
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
        from glob import glob
        import time

        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name)

        response = self._schedule_job(job_payload)

        self.assertEqual(201, response.status_code)
        self.assertEqual(f'"{job_bundle_name}"\n', response.text)

        time.sleep(8)

        runs_from_scheduled_job = glob(f'archives_dir/{job_bundle_name}-*')
        submitted_job_dirs = glob(f'working_dir/{job_bundle_name}*')
        self.assertIn(len(runs_from_scheduled_job), [3, 4])
        self.assertIn(len(submitted_job_dirs), [1, 2])

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

    def test_get_scheduled_jobs_returns_dict_with_scheduled_jobs_if_any(self):
        import math
        import time

        now = math.floor(time.time())

        job_bundle_0, _ = self._submit_and_schedule_job()
        job_bundle_1, _ = self._submit_and_schedule_job()

        response = self._scheduled_jobs()
        response_json = response.json()

        expected_schedule = {
            'day': '*',
            'day_of_week': '*',
            'hour': '*',
            'minute': '*',
            'month': '*',
            'second': '*/2',
            'week': '*',
            'year': '*'
        }

        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(response_json))

        for job_bundle in [job_bundle_0, job_bundle_1]:
            self.assertEqual(expected_schedule, response_json[job_bundle]['schedule'])
            self.assertLessEqual(response_json[job_bundle]['next_run_time'] - now, 4)

    def test_schedule_job_with_no_bundle_gives_409_conflict(self):
        job_bundle_name = 'fake_job'
        
        job_payload = self._job_payload(job_bundle_name)
        response = self._schedule_job(job_payload)
        
        self.assertEqual(409, response.status_code)
        self.assertEqual('Cannot schedule a job that has no uploaded bundle', response.text)

    def test_delete_scheduled_job_that_does_not_exist_returns_404(self):
        job_bundle_name = 'fake_job'

        response = self._delete_scheduled_job(job_bundle_name)
        self.assertEqual(404, response.status_code)
        self.assertEqual(f'Scheduled job {job_bundle_name} not found', response.text)

    def test_delete_scheduled_job_removes_job_from_scheduled_jobs_endpoint(self):
        job_bundle_0, _ = self._submit_and_schedule_job()
        job_bundle_1, _ = self._submit_and_schedule_job()

        delete_response = self._delete_scheduled_job(job_bundle_0)

        get_scheduled_jobs_response = self._scheduled_jobs()
        get_scheduled_jobs_response_json = get_scheduled_jobs_response.json()

        self.assertEqual(204, delete_response.status_code)
        self.assertNotIn(job_bundle_0, get_scheduled_jobs_response_json)

    def test_delete_scheduled_job_removes_working_dir(self):
        import os

        job_bundle_name, _ = self._submit_and_schedule_job()
        self._delete_scheduled_job(job_bundle_name)
        self.assertNotIn(job_bundle_name, os.listdir('working_dir'))

    def test_delete_scheduled_job_stops_running_job(self):
        from glob import glob
        import time

        job_bundle_name, _ = self._submit_and_schedule_job()
        self._delete_scheduled_job(job_bundle_name)
        time.sleep(8)
        runs_from_scheduled_job = glob(f'archives_dir/{job_bundle_name}-*')
        self.assertIn(len(runs_from_scheduled_job), [0, 1])

    def test_update_job_schedule_for_nonexistent_job_returns_404(self):
        job_id = 'fake_job'

        response = self._update_job_schedule(job_id, {'seconds': '*/5'})
        self.assertEqual(404, response.status_code)
        self.assertEqual(f'Scheduled job {job_id} not found', response.text)

    def test_update_job_schedule_updates_schedule(self):
        from glob import glob
        import time

        new_schedule = {
            'second': '*/5'
        }

        job_bundle_name, _ = self._submit_and_schedule_job()
        response = self._update_job_schedule(job_bundle_name, new_schedule)

        time.sleep(10)
        runs_from_scheduled_job = glob(f'archives_dir/{job_bundle_name}-*')

        self.assertEqual(204, response.status_code)
        self.assertIn(len(runs_from_scheduled_job), [1, 2])

    def test_update_job_schedule_with_empty_schedule_returns_400(self):
        from glob import glob
        import time

        new_schedule = {}

        job_bundle_name, _ = self._submit_and_schedule_job()
        response = self._update_job_schedule(job_bundle_name, new_schedule)

        self.assertEqual(400, response.status_code)
        self.assertEqual('Bad job schedule', response.text)

    def test_pausing_nonexistent_job_returns_404(self):
        job_id = 'fake_job'

        response = self._pause_job(job_id)
        self.assertEqual(404, response.status_code)
        self.assertEqual(f'Scheduled job {job_id} not found', response.text)

    def test_updating_job_status_without_status_key_returns_400(self):
        job_id = 'fake_job'

        response = self._put_to_job_with_payload(job_id, {})
        self.assertEqual(400, response.status_code)
        self.assertEqual(f'Missing status key', response.text)

    def test_updating_job_with_invalid_status_returns_400(self):
        job_bundle_name, _ = self._submit_and_schedule_job()

        response = self._put_to_job(job_bundle_name, 'eating')
        self.assertEqual(400, response.status_code)
        self.assertEqual(f'Invalid status', response.text)

    def test_pause_job_pauses_future_job_executions(self):
        from glob import glob
        import time

        job_bundle_name, _ = self._submit_and_schedule_job()
        response = self._pause_job(job_bundle_name)

        time.sleep(7)
        runs_from_scheduled_job = glob(f'archives_dir/{job_bundle_name}-*')

        self.assertEqual(204, response.status_code)
        self.assertIn(len(runs_from_scheduled_job), [0, 1])

    def test_resume_job_resumes_job_executions(self):
        from glob import glob
        import time

        job_bundle_name, _ = self._submit_and_schedule_job()
        self._pause_job(job_bundle_name)

        time.sleep(7)

        response = self._resume_job(job_bundle_name)

        time.sleep(8)

        runs_from_scheduled_job = glob(f'archives_dir/{job_bundle_name}-*')

        self.assertEqual(204, response.status_code)
        self.assertIn(len(runs_from_scheduled_job), [3, 4, 5])
