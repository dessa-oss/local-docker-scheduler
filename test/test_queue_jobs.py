import unittest
import uuid


class TestQueueJobs(unittest.TestCase):
    random_string = str(uuid.uuid4())[:8]
    _server_process = None
    wait_time = 7

    @classmethod
    def setUpClass(cls):
        import docker
        import time
        import os

        client = docker.from_env()
        client.images.pull('python:3.6-alpine')

        cls.archives_dir_path = f'/tmp/local_docker_scheduler/archives_dir_{cls.random_string}'
        cls.working_dir_path = f'/tmp/local_docker_scheduler/working_dir_{cls.random_string}'
        cls.job_bundle_store_dir_path = f'/tmp/local_docker_scheduler/job_bundle_store_dir_{cls.random_string}'

        os.makedirs(cls.archives_dir_path)
        os.makedirs(cls.working_dir_path)
        os.makedirs(cls.job_bundle_store_dir_path)

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
            job_bundle_dir_files = glob.glob(f'{self.job_bundle_store_dir_path}/*')
            for f in archive_files + working_dir_files + job_bundle_dir_files:
                shutil.rmtree(f)
        except Exception as e:
            print('Unable to delete jobs at the end of the test:', str(e))

    @classmethod
    def _start_server(cls):
        from subprocess import Popen
        import os
        import yaml
        with open('database.config.yaml', 'r') as f:
            db_dict = yaml.load(f, Loader=yaml.FullLoader)

        conn_info = db_dict['running_jobs']['args']
        env = os.environ
        env['WORKING_DIR'] = cls.working_dir_path
        env['ARCHIVE_DIR'] = cls.archives_dir_path
        env['JOB_BUNDLE_STORE_DIR'] = cls.job_bundle_store_dir_path
        env['NUM_WORKERS'] = '1'
        env['REDIS_HOST'] = conn_info['host']
        env['REDIS_PORT'] = str(conn_info['port'])
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

    def _queue_job(self, job_payload):
        import requests
        return requests.post('http://localhost:5000/queued_jobs', json=job_payload)

    @classmethod
    def _queued_jobs(cls):
        import requests
        return requests.get('http://localhost:5000/queued_jobs')

    def _queued_job(self, job_id):
        import requests
        return requests.get(f'http://localhost:5000/queued_jobs/{job_id}')

    def _completed_jobs(self):
        import requests
        return requests.get('http://localhost:5000/completed_jobs')

    def _failed_jobs(self):
        import requests
        return requests.get(f'http://localhost:5000/failed_jobs')

    def _running_jobs(self):
        import requests
        return requests.get(f'http://localhost:5000/running_jobs')

    def _jobs(self, job_id):
        import requests
        return requests.get(f'http://localhost:5000/jobs/{job_id}')

    @classmethod
    def _delete_queued_job(cls, job_id):
        import requests
        response = requests.delete(f'http://localhost:5000/queued_jobs/{job_id}')
        return response

    def _job_payload(self, job_bundle_name, fail=False, sleep_in_seconds=0):
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
                    'ENTRYPOINT': 'whatever_i_want.py',
                    'SECONDS': f'{sleep_in_seconds}'
                },
                'entrypoint': [
                    '/bin/sh' + ("NOSUCHCOMMAND" if fail else ""),
                    '-c'
                ],
                'command': [
                    'python ${ENTRYPOINT} && chmod -R a+rw /job/job_archive && sleep ${SECONDS}'
                ]
            },
            'metadata': {'project_name': 'test', 'username': 'shaz'},
            'gpu_spec': {}
        }

    def _submit_and_queue_job(self, job_id_prefix=None):
        job_bundle_name = self._create_job('fake_job', job_id_prefix)
        job_payload = self._job_payload(job_bundle_name)
        response = self._queue_job(job_payload)
        return job_bundle_name, response

    @classmethod
    def _cleanup_jobs(cls):
        failure_log = ''

        for job in cls._queued_jobs().json():
            try:
                response = cls._delete_queued_job(job)

                if response.status_code != 204:
                    failure_log += f'failed to cleanup {job}: {response.text}\n'
            except:
                pass
        if failure_log:
            raise AssertionError(failure_log)

    def test_queuing_job_with_proper_payload_and_bundle_gives_201(self):
        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name)

        response = self._queue_job(job_payload)

        self.assertEqual(201, response.status_code)
        self.assertEqual(f'"{job_bundle_name}"\n', response.text)

    def test_queuing_job_with_improper_payload_and_proper_bundle_gives_400(self):
        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name)

        job_payload.pop('spec')

        response = self._queue_job(job_payload)

        self.assertEqual(400, response.status_code)

    def test_queuing_job_with_no_payload_and_proper_bundle_gives_400(self):
        self._create_job('fake_job')

        response = self._queue_job({})

        self.assertEqual(400, response.status_code)

    def test_queuing_job_with_proper_payload_and_improper_bundle_gives_400(self):
        job_payload = self._job_payload('123')

        response = self._queue_job(job_payload)

        self.assertEqual(400, response.status_code)

    def test_queued_job_has_completed(self):
        import time

        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name)

        self._queue_job(job_payload)

        time.sleep(self.wait_time)

        response = self._completed_jobs()
        self.assertEqual(200, response.status_code)
        self.assertIn(job_bundle_name, [job_id for job_id in response.json()])

        response = self._failed_jobs()
        self.assertEqual(200, response.status_code)
        self.assertNotIn(job_bundle_name, [job_id for job_id in response.json()])

        response = self._running_jobs()
        self.assertEqual(200, response.status_code)
        self.assertNotIn(job_bundle_name, [job_id for job_id in response.json()])

        response = self._queued_jobs()
        self.assertEqual(200, response.status_code)
        self.assertNotIn(job_bundle_name, [value['job_id'] for job_pos, value in response.json().items()])

        response = self._jobs(job_bundle_name)
        self.assertEqual(200, response.status_code)
        self.assertEqual(response.json()['status'], 'completed')

    def test_queued_job_has_failed(self):
        import time

        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name, fail=True)

        self._queue_job(job_payload)

        time.sleep(self.wait_time)

        response = self._completed_jobs()
        self.assertEqual(200, response.status_code)
        self.assertNotIn(job_bundle_name, [job_id for job_id in response.json()])

        response = self._failed_jobs()
        self.assertEqual(200, response.status_code)
        self.assertIn(job_bundle_name, [job_id for job_id in response.json()])

        response = self._running_jobs()
        self.assertEqual(200, response.status_code)
        self.assertNotIn(job_bundle_name, [job_id for job_id in response.json()])

        response = self._queued_jobs()
        self.assertEqual(200, response.status_code)
        self.assertNotIn(job_bundle_name, [value['job_id'] for job_pos, value in response.json().items()])

        response = self._jobs(job_bundle_name)
        self.assertEqual(200, response.status_code)
        self.assertEqual(response.json()['status'], 'failed')

    def test_running_job_status(self):
        import time

        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name, sleep_in_seconds=5)

        self._queue_job(job_payload)

        time.sleep(5)

        response = self._completed_jobs()
        self.assertEqual(200, response.status_code)
        self.assertNotIn(job_bundle_name, [job_id for job_id in response.json()])

        response = self._failed_jobs()
        self.assertEqual(200, response.status_code)
        self.assertNotIn(job_bundle_name, [job_id for job_id in response.json()])

        response = self._running_jobs()
        self.assertEqual(200, response.status_code)
        self.assertIn(job_bundle_name, [job_id for job_id in response.json()])

        response = self._queued_jobs()
        self.assertEqual(200, response.status_code)
        self.assertNotIn(job_bundle_name, [value['job_id'] for job_pos, value in response.json().items()])

        response = self._jobs(job_bundle_name)
        self.assertEqual(200, response.status_code)
        self.assertEqual(response.json()['status'], 'running')

    def test_queued_job_status_while_no_more_workers(self):
        job_bundle_name = self._create_job('fake_job')
        job_payload = self._job_payload(job_bundle_name, sleep_in_seconds=5)

        self._queue_job(job_payload)

        job_bundle_name2 = self._create_job('fake_job')
        job_payload2 = self._job_payload(job_bundle_name2, sleep_in_seconds=5)

        self._queue_job(job_payload2)

        response = self._completed_jobs()
        self.assertEqual(200, response.status_code)
        self.assertNotIn(job_bundle_name2, [job_id for job_id in response.json()])

        response = self._failed_jobs()
        self.assertEqual(200, response.status_code)
        self.assertNotIn(job_bundle_name2, [job_id for job_id in response.json()])

        response = self._running_jobs()
        self.assertEqual(200, response.status_code)
        self.assertNotIn(job_bundle_name2, [job_id for job_id in response.json()])

        response = self._queued_jobs()
        self.assertEqual(200, response.status_code)
        self.assertIn(job_bundle_name2, [value['job_id'] for job_pos, value in response.json().items()])

        response = self._jobs(job_bundle_name2)
        self.assertEqual(200, response.status_code)
        self.assertEqual(response.json()['status'], 'queued')

    def _restart_server(self):
        import time
        self._stop_server()
        time.sleep(self.wait_time)

        self._start_server()
        time.sleep(self.wait_time)
