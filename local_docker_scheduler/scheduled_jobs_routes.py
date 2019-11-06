"""
Copyright (C) DeepLearning Financial Technologies Inc. - All Rights Reserved
Unauthorized copying, distribution, reproduction, publication, use of this file, via any medium is strictly prohibited
Proprietary and confidential
Written by Eric lee <e.lee@dessa.com>, 08 2019
"""

import docker_worker_pool
from local_docker_scheduler import get_app
from flask import jsonify, request, make_response
from .constants import _WORKING_DIR, _ARCHIVE_DIR
import logging

app = get_app()


def _check_for_parameter(parameter):
    try:
        return request.get_json().get(parameter)
    except:
        try:
            return request.args.get(parameter)
        except:
            print('no parameters passed')
    return None


@app.route('/scheduled_jobs', methods=['GET'])
def scheduled_jobs():
    full_list_of_scheduled_jobs = {job.name: _scheduled_job_response_entry(job) for job in app.apscheduler.get_jobs(jobstore='redis')}

    if _check_for_parameter('project'):
        project = _check_for_parameter('project')
        project_scheduled_jobs = {job: job_details for job, job_details in full_list_of_scheduled_jobs.items() if job_details['properties']['metadata']['project_name'] == project}
        return jsonify(project_scheduled_jobs)

    return jsonify(full_list_of_scheduled_jobs)


@app.route('/scheduled_jobs', methods=['POST'])
def create_scheduled_job():
    scheduled_job = request.json
    try:
        job_id = scheduled_job['job_id']
        spec = scheduled_job['spec']
        schedule = scheduled_job.get('schedule', {})
    except KeyError:
        return "Job must contain 'job_id', 'spec'", 400

    if not isinstance(schedule, dict) or job_id is None or not isinstance(spec, dict):
        return "Job must contain valid 'job_id', 'spec'", 400

    if not _job_directory_exists(job_id):
        return 'Cannot schedule a job that has no uploaded bundle', 409

    scheduled_job = {'job_id': job_id,
                        'spec': spec,
                        'schedule': schedule,
                        'metadata': scheduled_job.get('metadata', {}),
                        'gpu_spec': scheduled_job.get('gpu_spec', {})}

    try:
        docker_worker_pool.add_cron_worker(scheduled_job)
        if not schedule:
            worker = docker_worker_pool.cron_worker_by_job_id(job_id)
            job = worker.apscheduler_job
            job.pause()
            job.next_run_time = None
        return make_response(jsonify(job_id), 201)
    except ResourceWarning:
        return "Maximum number of scheduled jobs reached", 400


@app.route('/scheduled_jobs/<string:job_id>', methods=['DELETE'])
def delete_scheduled_job(job_id):
    try:
        docker_worker_pool.delete_cron_job(job_id)
        return make_response(jsonify({}), 204)
    except Exception as ex:
        return f'Scheduled job {job_id} not found', 404


@app.route('/scheduled_jobs/<string:job_id>', methods=['PUT'])
def update_scheduled_job_status(job_id):
    from datetime import datetime
    from tzlocal import get_localzone

    status = request.json.get('status')

    if status is None:
        return 'Missing status key', 400

    try:
        worker = docker_worker_pool.cron_worker_by_job_id(job_id)
        job = worker.apscheduler_job

        if status == 'paused':
            job.pause()
            job.next_run_time = None
            return make_response(jsonify({}), 204)
        elif status == 'active':
            now = datetime.now(get_localzone())
            next_fire_time = job.trigger.get_next_fire_time(None, now)
            job.next_run_time = next_fire_time
            resume_result = job.resume()
            if not resume_result:
                try:
                    logging.warning(f"Job ID {job_id} has expired. Cleaning up job...")
                    docker_worker_pool.delete_cron_job(job_id)
                    return "Cannot mark expired monitor as active. Job will be removed.", 400
                except Exception as ex:
                    logging.warning(str(ex))
                    return "Unable to process update for expired job", 400

            return make_response(jsonify({}), 204)
        else:
            return 'Invalid status', 400
    # TODO - Capture a a more specific error
    except:
        return f"Scheduled job {job_id} not found", 404


@app.route('/scheduled_jobs/<string:job_id>', methods=['PATCH'])
def update_scheduled_job_schedule(job_id):
    from werkzeug.exceptions import BadRequest
    from docker_worker_pool import DockerWorker
    worker = docker_worker_pool.cron_worker_by_job_id(job_id)
    _cron_workers = docker_worker_pool.get_cron_workers()
    if not worker:
        logging.info('worker not found')
        return f'Scheduled job {job_id} not found', 404

    job = request.json
    new_schedule = job.get('schedule', {})
    if not new_schedule:
        return "Bad job schedule", 400
    try:
        _update_job(worker, new_schedule)
        return make_response(jsonify({}), 204)
    except BadRequest as e:
        logging.info(f'Cannot process schedule update: invalid schedule provided for job {job_id}')
        return f'Cannot process schedule update: invalid schedule provided for job {job_id}', 400
    except Exception as e:
        logging.info(f'Unable to process schedule update for job {job_id}')
        logging.info(str(e))
        return f'Unable to process schedule update for job {job_id}', 400


@app.route('/scheduled_jobs/<string:job_id>', methods=['GET'])
def scheduled_job(job_id):
    response = {job.name: _scheduled_job_response_entry(job) for job in app.apscheduler.get_jobs(jobstore='redis') if job.name == job_id}

    if response:
        return jsonify(response)
    return f'Scheduled job {job_id} not found', 404


def _scheduled_job_response_entry(job):

    status, next_three_runtimes = _get_status_and_next_three_runtimes(job)

    return {
        'next_run_time': next_three_runtimes,
        'schedule': _schedule_dict(job.trigger),
        'status': status,
        'properties': job.args[1]
    }

def _get_next_runtime(job, previous_runtime=None, now=None):
    from datetime import datetime
    from tzlocal import get_localzone
    if not now:
        now = datetime.now(get_localzone())

    return job.trigger.get_next_fire_time(previous_runtime, now)

def _get_status_and_next_three_runtimes(job):
    from datetime import timedelta

    next_run_datetime = job.next_run_time

    if next_run_datetime is None:
        status = 'paused'
        list_of_next_three_runtimes = [None, None, None]
    else:
        status = 'active'
        list_of_next_three_runtimes = []
        next_run_timestamp = _convert_datetime_to_timestamp(next_run_datetime)
        list_of_next_three_runtimes.append(next_run_timestamp)
        for _ in range(2):
            next_run_datetime = _get_next_runtime(job, next_run_datetime, next_run_datetime + timedelta(milliseconds=1))
            next_run_timestamp = _convert_datetime_to_timestamp(next_run_datetime)
            list_of_next_three_runtimes.append(next_run_timestamp)

    return status, list_of_next_three_runtimes

def _convert_datetime_to_timestamp(datetime_object):
    from datetime import datetime
    import math
    timestamp_float = datetime.timestamp(datetime_object)
    timestamp = math.floor(timestamp_float)
    return timestamp

def _job_directory_exists(job_id):
    import os

    if job_id in os.listdir(_WORKING_DIR):
        return True
    return False


def _schedule_dict(trigger):
    schedule_dates = {'start_date': trigger.start_date, 'end_date': trigger.end_date}
    schedule = {field.name: str(field) for field in trigger.fields}
    return {**schedule, **schedule_dates}


def _update_job(worker, new_schedule):
    from werkzeug.exceptions import BadRequest
    from docker_worker_pool import DockerWorker
    _cron_workers = docker_worker_pool.get_cron_workers()

    worker_index = int(worker.worker_id.split('_')[-1])
    old_scheduled_job = worker.apscheduler_job
    docker_worker_pool.delete_cron_worker(worker_index)

    try:
        scheduled_job = get_app().apscheduler.add_job(func=old_scheduled_job.func,
                                                        trigger='cron',
                                                        **new_schedule,
                                                        args=old_scheduled_job.args,
                                                        id=old_scheduled_job.id,
                                                        name=old_scheduled_job.name,
                                                        jobstore='redis')
    except TypeError as e:
        scheduled_job = _recreate_cron_worker(old_scheduled_job)
        raise BadRequest(e)
    except ValueError as e:
        scheduled_job = _recreate_cron_worker(old_scheduled_job)
        raise BadRequest(e)
    finally:
        _cron_workers[worker_index] = DockerWorker(old_scheduled_job.id, scheduled_job)

def _recreate_cron_worker(scheduled_job):
    from docker_worker_pool import DockerWorker

    schedule = _schedule_dict(scheduled_job.trigger)

    recreated_scheduled_job = get_app().apscheduler.add_job(func=scheduled_job.func,
                                                        trigger='cron',
                                                        **schedule,
                                                        args=scheduled_job.args,
                                                        id=scheduled_job.id,
                                                        name=scheduled_job.name,
                                                        jobstore='redis')
    return recreated_scheduled_job
