import unittest

class TestSubmitJobBundle(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import os
        from subprocess import Popen
        import time

        os.makedirs('working_dir', exist_ok=True)
        env = os.environ.copy()
        env['WORKING_DIR'] = 'working_dir'
        cls._server_process = Popen(['python', '-m', 'local_docker_scheduler', '-p', '5000'], env=env)
        time.sleep(3)

    @classmethod
    def tearDownClass(cls):
        import shutil

        cls._server_process.terminate()
        shutil.rmtree('working_dir')

    def setUp(self):
        self._job_id = None

    @property
    def job_id(self):
        import uuid

        if self._job_id is None:
            self._job_id = str(uuid.uuid4())

        return self._job_id

    def _generate_tarball(self):
        import os
        import os.path as path
        import shutil
        import tarfile

        os.makedirs(self.job_id)

        try:
            file_0_path = path.join(self.job_id, 'file_0')
            file_1_path = path.join(self.job_id, 'file_1')
            tar_path = f'{self.job_id}.tgz'

            with open(file_0_path, 'w') as file_0:
                file_0.write('hello world')

            with open(file_1_path, 'w') as file_1:
                file_1.write('goodbye world')

            with tarfile.open(tar_path, 'w:gz') as tar:
                tar.add(self.job_id)

            return tar_path
        finally:
            shutil.rmtree(self.job_id)

    def test_can_upload_and_untar_bundle_via_rest_api(self):
        import os
        import requests

        tarball_location = self._generate_tarball()

        with open(tarball_location, 'rb') as tarball:
            request_payload = {
                'job_bundle': tarball
            }

            response = requests.post('http://localhost:5000/job_bundle', files=request_payload)
        
        os.remove(tarball_location)

        self.assertEqual(200, response.status_code)
        self.assertEqual('Job bundle uploaded', response.text)

        with open(f'working_dir/{self.job_id}/file_0', 'r') as file_0:
            self.assertEqual('hello world', file_0.read())

        with open(f'working_dir/{self.job_id}/file_1', 'r') as file_1:
            self.assertEqual('goodbye world', file_1.read())