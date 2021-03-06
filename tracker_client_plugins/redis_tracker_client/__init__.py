from tracker_client_plugins import TrackerClientBase
import redis
import time
import logging


class RedisTrackerClient(TrackerClientBase):
    # the following logic refactored to the server side (i.e. wrap Redis into a service) to ensure
    # data integrity/consistency and proper encapsulation

    # All tracking updates should update the following items:
    # SET project:<project_name>:jobs:(queued/running/completed?) job_id
    # SET projects:global:jobs:(queued/running/completed) job_id
    # key-value jobs:<job_id>:(state/project_name/user/create_time/start_time/completed_time)
    # Z   projects <time> <project_id>

    def __init__(self, host, port):
        self._host = host
        self._port = port
        self._rc = redis.StrictRedis(host=host, port=port)
        self._logger = logging.getLogger(__name__)
        try:
            self._rc.ping()
            self._logger.info(f"Connected to Redis tracker at {host}:{port}")
        except redis.exceptions.ConnectionError:
            self._logger.warning(f"Cannot connect to Redis tracker at {host}:{port}")

    @staticmethod
    def _set_project_job_status(p: redis.Redis.pipeline, job_id: str, project_name: str, status: str):
        if status == 'queued':
            p.sadd(f"project:{project_name}:jobs:queued", job_id)
            p.sadd(f"project:{project_name}:jobs:running", job_id)
        elif status == 'running':
            p.srem(f"project:{project_name}:jobs:queued", job_id)
            p.sadd(f"project:{project_name}:jobs:running", job_id)

    @staticmethod
    def _set_global_job_status(p: redis.Redis.pipeline, job_id: str, status: str):
        if status == 'queued':
            p.sadd(f"projects:global:jobs:queued", job_id)
        elif status == 'running':
            p.srem(f"projects:global:jobs:queued", job_id)
        # elif status in ['completed', 'failed']:
        #     p.sadd(f"projects:global:jobs:completed", job_id)

    @staticmethod
    def _kv_job(p: redis.Redis.pipeline, job_id: str, fields: dict):
        for field, value in fields.items():
            p.set(f"jobs:{job_id}:{field}", value)

    def _send_update(self, job: dict, status: str, relevant_time: dict, update_project_listing=False):
        job_id, project_name, username = job['job_id'], job['metadata']['project_name'], job['metadata']['username']
        self._logger.debug(f"Tracking start: Update job {job_id} to {status}")

        p = self._rc.pipeline()

        self._set_project_job_status(p, job_id, project_name, status)
        self._set_global_job_status(p, job_id, status)

        self._kv_job(p, job_id, {**{'state': status, 'project': project_name, 'user': username}, **relevant_time})

        if update_project_listing:
            if self.create_project(project_name, list(relevant_time.values())[0]):
                self._logger.debug(f"Created project {project_name}")

        try:
            p.execute()
        except redis.exceptions.ConnectionError:
            self._logger.warning(f"Cannot connect to Redis tracker at {self._host}:{self._port}")

        self._logger.debug(f"Tracking end: Update job {job_id} to {status}")

    def queued(self, job):
        self._send_update(job, "queued", {'creation_time': time.time()}, True)

    def running(self, job):
        self._send_update(job, "running", {'start_time': time.time()}, False)

    def completed(self, job):
        self._send_update(job, "completed", {'completed_time': time.time()}, False)

    def failed(self, job):
        self._send_update(job, "failed", {'completed_time': time.time()}, False)

    def delete(self, job):
        job_id, project_name = job['job_id'], job['metadata']['project_name']
        self._logger.debug(f"Tracking start: Deleting job {job_id}")

        p = self._rc.pipeline()

        states = ['queued', 'running', 'completed']
        project_keys = [f"project:{project_name}:jobs:{i}" for i in states]

        for key in project_keys:
            p.srem(key, job_id)

        global_keys = [f"projects:global:jobs:{i}" for i in states]

        for key in global_keys:
            p.srem(key, job_id)

        jobs_keys = ['project', 'state', 'parameters', 'completed_time', 'metrics', 'creation_time', 'user', 'input_parameters', 'start_time', 'user_artifact_metadata']
        jobs_keys = [f"jobs:{job_id}:{i}" for i in jobs_keys]

        p.delete(*jobs_keys)

        p.execute()

        self._logger.debug(f"Tracking end: Deleting job {job_id}")

    def create_project(self, project_name, project_creation_time=None):
        if not project_creation_time:
            project_creation_time = time.time()

        return self._rc.zadd("projects", {project_name: project_creation_time}, nx=True)

    def track_scheduled_job_run(self, job, run):
        project_name = job['metadata']['project_name']
        monitor_name = job['metadata']['monitor_name']
        self._logger.debug(f'Tracking run {run} for job {job["job_id"]} in project {project_name}')
        self._rc.sadd(f'projects:{project_name}:monitors:{monitor_name}:jobs', run)

