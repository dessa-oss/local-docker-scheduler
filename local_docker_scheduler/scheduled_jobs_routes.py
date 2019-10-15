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

app = get_app()

@app.route('/scheduled_jobs', methods=['GET', 'POST'])
def scheduled_jobs():
    if request.method == 'POST':
        scheduled_job = request.json
        try:
            job_id = scheduled_job['job_id']
            spec = scheduled_job['spec']
            schedule = scheduled_job['schedule']
        except KeyError:
            return "Job must contain 'job_id', 'spec', 'schedule'", 400

        if not isinstance(schedule, dict) or job_id is None or not isinstance(spec, dict):
            return "Job must contain valid 'job_id', 'spec', 'schedule'", 400
        
        if len(schedule.items()) == 0:
            return "Invalid job schedule", 400

        if not _job_directory_exists(job_id):
            return 'Cannot schedule a job that has no uploaded bundle', 409

        scheduled_job = {'job_id': job_id,
                            'spec': spec,
                            'schedule': schedule,
                            'metadata': scheduled_job.get('metadata', {}),
                            'gpu_spec': scheduled_job.get('gpu_spec', {})}

        try:
            docker_worker_pool.add_cron_worker(scheduled_job)
            return make_response(jsonify(job_id), 201)
        except ResourceWarning:
            return "Maximum number of scheduled jobs reached", 400
    else:
        current_scheduled_jobs = docker_worker_pool.get_cron_workers()
        return jsonify({worker.apscheduler_job.name: _scheduled_job_response_entry(worker) for worker in current_scheduled_jobs.values()})

@app.route('/scheduled_jobs/<string:job_id>', methods=['DELETE'])
def delete_scheduled_job(job_id):
    try:
        docker_worker_pool.delete_cron_job(job_id)
        return make_response(jsonify({}), 204)
    except Exception as ex:
        return f'Scheduled job {job_id} not found', 404

@app.route('/scheduled_jobs/<string:job_id>/', methods=['PUT'])
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
            job.resume()
            return make_response(jsonify({}), 204)
        else:
            return 'Invalid status', 400
    # TODO - Capture a a more specific error
    except:
        return f"Scheduled job {job_id} not found", 404

@app.route('/scheduled_jobs/<string:job_id>', methods=['PATCH'])
def update_scheduled_job_schedule(job_id):
    worker = docker_worker_pool.cron_worker_by_job_id(job_id)
    job = request.json
    new_schedule = job.get('schedule', {})
    if not new_schedule:
        return "Bad job schedule", 400
    try:
        worker.apscheduler_job.reschedule('cron', **new_schedule)
        return make_response(jsonify({}), 204)
    # TODO - Capture a a more specific error
    except:
        return f'Scheduled job {job_id} not found', 404

@app.route('/scheduled_jobs/<string:job_id>', methods=['GET'])
def scheduled_job(job_id):
    current_scheduled_jobs = docker_worker_pool.get_cron_workers()
    response = {worker.apscheduler_job.name: _scheduled_job_response_entry(worker) for worker in current_scheduled_jobs.values() if worker.apscheduler_job.name == job_id}

    if response:
        return jsonify(response)
    return f'Scheduled job {job_id} not found', 404

def _scheduled_job_response_entry(worker):
    from datetime import datetime
    import math

    next_run_datetime = worker.apscheduler_job.next_run_time

    if next_run_datetime is None:
        status = 'paused'
        next_run_timestamp = None
    else:
        status = 'active'
        next_run_timestamp_float = datetime.timestamp(next_run_datetime)
        next_run_timestamp = math.floor(next_run_timestamp_float)

    return {
        'next_run_time': next_run_timestamp,
        'schedule': _schedule_dict(worker.apscheduler_job.trigger),
        'status': status
    }

def _job_directory_exists(job_id):
    import os

    if job_id in os.listdir(_WORKING_DIR):
        return True
    return False

def _schedule_dict(trigger):
    return {field.name: str(field) for field in trigger.fields}
