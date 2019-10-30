import unittest
import uuid


class TestScheduleJobs(unittest.TestCase):

    random_string = str(uuid.uuid4())[:8]
    archives_dir_path = '/tmp/local_docker_scheduler/archives_dir'
    working_dir_path = '/tmp/local_docker_scheduler/working_dir'
    _server_process = None
    wait_time = 5

    @classmethod
    def setUpClass(cls):
        import docker
        import time

        client = docker.from_env()
        client.images.pull('python:3.6-alpine')

        cls.archives_dir_path = f'/tmp/local_docker_scheduler/archives_dir_{cls.random_string}'
        cls.working_dir_path = f'/tmp/local_docker_scheduler/working_dir_{cls.random_string}'

        cls._start_server()
        time.sleep(1)

    def setUp(self):
        import time
        redis = self.load_redis()
        redis.flushall()
        time.sleep(1)

    @classmethod
    def load_redis(cls):
        import yaml
        from redis import StrictRedis
        with open('database.config.yaml', 'r') as f:
            db_dict = yaml.load(f, Loader=yaml.FullLoader)

        conn_info = db_dict['running_jobs']['args']
        return StrictRedis(conn_info['host'], conn_info['port'], 0)

    @classmethod
    def tearDownClass(cls):
        cls._stop_server()

    def tearDown(self):
        import shutil
        import glob
        try:
            self._cleanup_jobs()
            archive_files = glob.glob(f'{self.archives_dir_path}/*')
            working_dir_files = glob.glob(f'{self.working_dir_path}/*')
            for f in archive_files + working_dir_files:
                shutil.rmtree(f)
        except Exception as e:
            print('Unable to delete jobs at the end of the test:', str(e))

    @classmethod
    def _start_server(cls):
        from subprocess import Popen
        import os

        env = os.environ
        env['WORKING_DIR'] = cls.working_dir_path
        env['ARCHIVE_DIR'] = cls.archives_dir_path
        env['NUM_WORKERS'] = '0'
        cls._server_process = Popen(['python', '-m', 'local_docker_scheduler', '-p', '5000'], env=env)

    @classmethod
    def _stop_server(cls):
        if cls._server_process:
            cls._server_process.terminate()
            cls._server_process.wait()

    def _generate_tarball(self, job_tar_source_dir, job_id_prefix=None):
        import os
        import os.path as path
        import shutil
        import tarfile
        import tempfile
        import uuid

        temp_dir_root = tempfile.mkdtemp()

        cwd = os.getcwd()
        dir_suffix = str(uuid.uuid4())
        if job_id_prefix:
            job_id = f'{job_id_prefix}-{job_tar_source_dir}-{dir_suffix}'
        else:
            job_id = f'{job_tar_source_dir}-{dir_suffix}'
        temp_dir = path.join(temp_dir_root, job_id)
        tar_file = path.join(temp_dir_root, f'{job_id}.tgz')

        shutil.rmtree(temp_dir_root, ignore_errors=True)
        shutil.copytree(path.join('test', 'fixtures', 'jobs', job_tar_source_dir), temp_dir)

        os.chdir(temp_dir_root)

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

    def _create_job(self, job_tar_source_dir, job_id_prefix=None):
        import os.path as path

        job_tar_path = self._generate_tarball('fake_job', job_id_prefix)
        job_bundle_name = path.basename(job_tar_path)[:-4]

        self._upload_job_bundle(job_tar_path)

        return job_bundle_name

    def _schedule_job(self, job_payload):
        import requests
        return requests.post('http://localhost:5000/scheduled_jobs', json=job_payload)

    @classmethod
    def _scheduled_jobs(cls):
        import requests
        return requests.get('http://localhost:5000/scheduled_jobs')

    def _scheduled_job(self, job_id):
        import requests
        return requests.get(f'http://localhost:5000/scheduled_jobs/{job_id}')

    @classmethod
    def _delete_scheduled_job(cls, job_id):
        import requests
        import time

        response = requests.delete(f'http://localhost:5000/scheduled_jobs/{job_id}')
        return response

    def _update_job_schedule(self, job_id, cron_schedule):
        import requests
        return requests.patch(f'http://localhost:5000/scheduled_jobs/{job_id}', json={'schedule': cron_schedule})

    def _pause_job(self, job_id):
        return self._put_to_job(job_id, 'paused')

    def _resume_job(self, job_id):
        return self._put_to_job(job_id, 'active')

    def _put_to_job(self, job_id, status):
        return self._put_to_job_with_payload(job_id, {'status': status})

    def _put_to_job_with_payload(self, job_id, payload):
        import requests
        return requests.put(f'http://localhost:5000/scheduled_jobs/{job_id}', json=payload)

    def _job_payload(self, job_bundle_name):
        host_working_dir = self.working_dir_path
        host_archive_dir = self.archives_dir_path

        return {
            'job_id': job_bundle_name,
            'spec': {
                'image': 'python:3.6-alpine',
                'volumes': {
                    f'{host_working_dir}/{job_bundle_name}': {
                        'bind': '/job',
                        'mode': 'rw'
                    },
                    f'{host_archive_dir}': {
                        'bind': '/job/job_archive',
                        'mode': 'rw'
                    }
                },
                'working_dir': '/job',
                'environment': {
                    'FOUNDATIONS_JOB_ID': job_bundle_name,
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
            },
            'gpu_spec': {}
        }

    def _submit_and_schedule_job(self, job_id_prefix=None):
        job_bundle_name = self._create_job('fake_job', job_id_prefix)
        job_payload = self._job_payload(job_bundle_name)
        response = self._schedule_job(job_payload)
        return job_bundle_name, response

    @classmethod
    def _cleanup_jobs(cls):
        failure_log = ''

        for job in cls._scheduled_jobs().json():
            try:
                response = cls._delete_scheduled_job(job)

                if response.status_code != 204:
                    failure_log += f'failed to cleanup {job}: {response.text}\n'
            except:
                pass
        if failure_log:
            raise AssertionError(failure_log)

    def test_scheduled_job_runs_on_schedule(self):
        from glob import glob
        import time

        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name)

        response = self._schedule_job(job_payload)
        job_info = self._scheduled_job(job_bundle_name)
        job_content = job_info.json()[job_bundle_name]

        self.assertEqual(201, response.status_code)
        self.assertEqual(f'"{job_bundle_name}"\n', response.text)
        self.assertEqual('active', job_content['status'])

        time.sleep(self.wait_time)

        runs_from_scheduled_job = glob(f'{self.archives_dir_path}/{job_bundle_name}_*')
        submitted_job_dirs = glob(f'{self.working_dir_path}/{job_bundle_name}*')
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
        self.assertEqual("Job must contain 'job_id', 'spec'", response.text)

    def test_schedule_job_with_valid_payload_structure_but_invalid_payload_contents_400(self):
        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name)

        job_payload['job_id'] = None
        job_payload['spec'] = None
        job_payload['schedule'] = None

        response = self._schedule_job(job_payload)

        self.assertEqual(400, response.status_code)
        self.assertEqual("Job must contain valid 'job_id', 'spec'", response.text)

    def test_schedule_job_with_valid_payload_structure_but_job_id_None_returns_400(self):
        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name)

        job_payload['job_id'] = None
        job_payload['spec'] = None

        response = self._schedule_job(job_payload)

        self.assertEqual(400, response.status_code)
        self.assertEqual("Job must contain valid 'job_id', 'spec'", response.text)

    def test_schedule_job_with_valid_payload_structure_but_spec_None_returns_400(self):
        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name)

        job_payload['spec'] = None

        response = self._schedule_job(job_payload)

        self.assertEqual(400, response.status_code)
        self.assertEqual("Job must contain valid 'job_id', 'spec'", response.text)

    def test_schedule_job_with_valid_payload_structure_but_schedule_empty_returns_201_with_paused_job(self):
        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name)

        job_payload['schedule'] = {}

        response = self._schedule_job(job_payload)
        job_info = self._scheduled_job(job_bundle_name)
        job_content = job_info.json()[job_bundle_name]

        self.assertEqual(201, response.status_code)
        self.assertEqual(f'"{job_bundle_name}"\n', response.text)
        self.assertIsNone(job_content['next_run_time'])
        self.assertEqual('paused', job_content['status'])

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
            'year': '*',
            'start_date': None,
            'end_date': None
        }

        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(response_json))

        for job_bundle in [job_bundle_0, job_bundle_1]:
            self.assertEqual(expected_schedule, response_json[job_bundle]['schedule'])
            self.assertLessEqual(response_json[job_bundle]['next_run_time'] - now, 9)

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
        self.assertNotIn(job_bundle_name, os.listdir(self.working_dir_path))

    def test_delete_scheduled_job_stops_running_job(self):
        from glob import glob
        job_bundle_name, _ = self._submit_and_schedule_job()
        self._delete_scheduled_job(job_bundle_name)
        runs_from_scheduled_job = glob(f'{self.archives_dir_path}/{job_bundle_name}_*')
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

        time.sleep(self.wait_time)
        runs_from_scheduled_job = glob(f'{self.archives_dir_path}/{job_bundle_name}_*')

        self.assertEqual(204, response.status_code)
        self.assertIn(len(runs_from_scheduled_job), [1, 2])

    def test_resuming_updated_job_runs_on_new_schedule(self):
        from glob import glob
        import time

        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name)
        job_payload['schedule'] = {}

        response = self._schedule_job(job_payload)
        time.sleep(self.wait_time)

        runs_from_scheduled_job = glob(f'{self.archives_dir_path}/{job_bundle_name}_*')

        self.assertEqual(201, response.status_code)
        self.assertEqual(0, len(runs_from_scheduled_job))

        new_schedule = {
            'second': '*/5'
        }

        update_response = self._update_job_schedule(job_bundle_name, new_schedule)
        resume_response = self._resume_job(job_bundle_name)
        time.sleep(7)

        runs_from_scheduled_job = glob(f'{self.archives_dir_path}/{job_bundle_name}_*')

        self.assertEqual(204, update_response.status_code)
        self.assertEqual(204, resume_response.status_code)
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
        runs_from_scheduled_job = glob(f'{self.archives_dir_path}/{job_bundle_name}_*')

        self.assertEqual(204, response.status_code)
        self.assertIn(len(runs_from_scheduled_job), [0, 1])

    def test_resume_job_resumes_job_executions(self):
        from glob import glob
        import time

        job_bundle_name, _ = self._submit_and_schedule_job()
        self._pause_job(job_bundle_name)
        time.sleep(self.wait_time)

        response = self._resume_job(job_bundle_name)
        time.sleep(self.wait_time)

        runs_from_scheduled_job = glob(f'{self.archives_dir_path}/{job_bundle_name}_*')

        self.assertEqual(204, response.status_code)
        self.assertIn(len(runs_from_scheduled_job), [3, 4, 5])

    def test_can_pause_job_twice(self):
        from glob import glob
        import time

        job_bundle_name, _ = self._submit_and_schedule_job()
        self._pause_job(job_bundle_name)
        pause_response = self._pause_job(job_bundle_name)

        self.assertEqual(204, pause_response.status_code)

        time.sleep(7)

        response = self._resume_job(job_bundle_name)

        time.sleep(8)

        runs_from_scheduled_job = glob(f'{self.archives_dir_path}/{job_bundle_name}_*')

        self.assertEqual(204, response.status_code)
        self.assertIn(len(runs_from_scheduled_job), [3, 4, 5])

    def test_can_resume_job_twice(self):
        from glob import glob
        import time

        job_bundle_name, _ = self._submit_and_schedule_job()
        self._pause_job(job_bundle_name)

        time.sleep(7)

        self._resume_job(job_bundle_name)
        response = self._resume_job(job_bundle_name)

        time.sleep(8)

        runs_from_scheduled_job = glob(f'{self.archives_dir_path}/{job_bundle_name}_*')

        self.assertEqual(204, response.status_code)
        self.assertIn(len(runs_from_scheduled_job), [3, 4, 5])

    def test_scheduled_jobs_have_status(self):
        job_bundle_0, _ = self._submit_and_schedule_job()
        self._pause_job(job_bundle_0)

        job_bundle_1, _ = self._submit_and_schedule_job()

        job_bundle_2, _ = self._submit_and_schedule_job()
        self._pause_job(job_bundle_2)
        self._resume_job(job_bundle_2)

        jobs_information = self._scheduled_jobs().json()

        self.assertEqual('paused', jobs_information[job_bundle_0]['status'])
        self.assertEqual('active', jobs_information[job_bundle_1]['status'])
        self.assertEqual('active', jobs_information[job_bundle_2]['status'])

    def test_scheduler_persists_scheduled_and_paused_jobs(self):
        from glob import glob
        import time
        
        job_bundle_0, _ = self._submit_and_schedule_job()
        self._pause_job(job_bundle_0)

        job_bundle_1, _ = self._submit_and_schedule_job()

        self._stop_server()
        time.sleep(2)
        self._start_server()

        time.sleep(5)

        runs_from_scheduled_job_0 = glob(f'{self.archives_dir_path}/{job_bundle_0}_*')
        runs_from_scheduled_job_1 = glob(f'{self.archives_dir_path}/{job_bundle_1}_*')

        self.assertIn(len(runs_from_scheduled_job_0), [0, 1])
        self.assertIn(len(runs_from_scheduled_job_1), [2, 3])

        jobs_information = self._scheduled_jobs().json()
        self.assertEqual('paused', jobs_information[job_bundle_0]['status'])
        self.assertEqual('active', jobs_information[job_bundle_1]['status'])

    def test_can_resume_paused_job_after_scheduler_restarts(self):
        from glob import glob
        import time

        job_bundle_0, _ = self._submit_and_schedule_job()
        self._pause_job(job_bundle_0)

        job_bundle_1, _ = self._submit_and_schedule_job()
        self._pause_job(job_bundle_1)

        self._stop_server()
        time.sleep(self.wait_time)
        self._start_server()
        time.sleep(self.wait_time)

        self._resume_job(job_bundle_0)
        self._resume_job(job_bundle_1)

        time.sleep(self.wait_time)

        runs_from_scheduled_job_0 = glob(f'{self.archives_dir_path}/{job_bundle_0}_*')
        self.assertIn(len(runs_from_scheduled_job_0), [2, 3])

        runs_from_scheduled_job_1 = glob(f'{self.archives_dir_path}/{job_bundle_1}_*')
        self.assertIn(len(runs_from_scheduled_job_1), [2, 3])

        jobs_information = self._scheduled_jobs().json()
        self.assertEqual('active', jobs_information[job_bundle_0]['status'])
        self.assertEqual('active', jobs_information[job_bundle_1]['status'])

    def test_can_delete_paused_job_after_restarting_scheduler(self):
        import time

        job_bundle_0, _ = self._submit_and_schedule_job()
        self._pause_job(job_bundle_0)

        job_bundle_1, _ = self._submit_and_schedule_job()

        self._stop_server()

        self._start_server()
        time.sleep(self.wait_time)

        response = self._delete_scheduled_job(job_bundle_0)
        self.assertEqual(204, response.status_code)

        jobs_information = self._scheduled_jobs().json()
        self.assertIn(job_bundle_1, jobs_information)

    def test_get_scheduled_job_on_nonexistent_job_returns_404(self):
        job_id = 'fake_job'

        response = self._scheduled_job(job_id)
        self.assertEqual(404, response.status_code)
        self.assertEqual(f'Scheduled job {job_id} not found', response.text)

    def test_get_scheduled_job_returns_correct_information(self):
        import math
        import time

        now = math.floor(time.time())

        job_bundle_0, _ = self._submit_and_schedule_job()
        job_bundle_1, _ = self._submit_and_schedule_job()
        self._pause_job(job_bundle_0)

        response_0 = self._scheduled_job(job_bundle_0)
        response_1 = self._scheduled_job(job_bundle_1)
        response_0_json = response_0.json()
        response_1_json = response_1.json()

        self.assertEqual(200, response_0.status_code)
        self.assertEqual(200, response_1.status_code)

        expected_schedule = {
            'day': '*',
            'day_of_week': '*',
            'hour': '*',
            'minute': '*',
            'month': '*',
            'second': '*/2',
            'week': '*',
            'year': '*',
            'start_date': None,
            'end_date': None
        }

        job_bundle_0_content = response_0_json[job_bundle_0]
        job_bundle_1_content = response_1_json[job_bundle_1]
        expected_properties_0 = self._job_payload(job_bundle_0)
        expected_properties_1 = self._job_payload(job_bundle_1)
        expected_properties_0.pop('schedule')
        expected_properties_1.pop('schedule')

        self.assertEqual([job_bundle_0], list(response_0_json.keys()))
        self.assertEqual(expected_schedule, job_bundle_0_content['schedule'])
        self.assertIsNone(job_bundle_0_content['next_run_time'])
        self.assertEqual('paused', job_bundle_0_content['status'])
        self.assertEqual(expected_properties_0, job_bundle_0_content['properties'])

        self.assertEqual([job_bundle_1], list(response_1_json.keys()))
        self.assertEqual(expected_schedule, job_bundle_1_content['schedule'])
        self.assertLessEqual(job_bundle_1_content['next_run_time'] - now, 9)
        self.assertEqual('active', job_bundle_1_content['status'])
        self.assertEqual(expected_properties_1, job_bundle_1_content['properties'])

    def test_scheduled_job_run_has_human_readable_timestamp(self):
        from glob import glob
        import time

        job_bundle_name, _ = self._submit_and_schedule_job()

        time.sleep(8)

        runs_from_scheduled_job = glob(f"{self.archives_dir_path}/{job_bundle_name}_{'[0-9]'*8}_{'[0-9]'*6}")
        self.assertIn(len(runs_from_scheduled_job), [3, 4])

    def _create_jobs_with_and_without_prefix(self, prefix):
        
        job_bundle_0, _ = self._submit_and_schedule_job()
        job_bundle_1, _ = self._submit_and_schedule_job()

        job_bundle_3, _ = self._submit_and_schedule_job(job_id_prefix=prefix)
        job_bundle_4, _ = self._submit_and_schedule_job(job_id_prefix=prefix)

    def test_filtered_get_scheduled_job_returns_correct_information(self):
        project_name = 'test_project'
        self._create_jobs_with_and_without_prefix(project_name)

        import requests
        response = requests.get(f'http://localhost:5000/scheduled_jobs?project={project_name}').json()
        job_ids = response.keys()
        has_project_name = True
        for job_id in job_ids:
            has_project_name = project_name in job_id and has_project_name

        self.assertTrue(has_project_name)

    def test_filtered_get_scheduled_job_returns_correct_information_when_submitted_in_the_body(self):
        project_name = 'test_project'
        self._create_jobs_with_and_without_prefix(project_name)

        import requests
        response = requests.get(f'http://localhost:5000/scheduled_jobs', params={'project': project_name}).json()
        
        job_ids = response.keys()
        has_project_name = True
        for job_id in job_ids:
            has_project_name = project_name in job_id and has_project_name

        self.assertTrue(has_project_name)
