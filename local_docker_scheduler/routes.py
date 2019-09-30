"""
Copyright (C) DeepLearning Financial Technologies Inc. - All Rights Reserved
Unauthorized copying, distribution, reproduction, publication, use of this file, via any medium is strictly prohibited
Proprietary and confidential
Written by Eric lee <e.lee@dessa.com>, 08 2019
"""

from local_docker_scheduler import get_app
from db import queue, running_jobs, completed_jobs, failed_jobs
from flask import jsonify, request, make_response
from time import time
from uuid import uuid4
import docker_worker_pool
import logging
from tracker_client_plugins import tracker_clients


app = get_app()

@app.route('/')
def show_home_page():
    return "Welcome to docker scheduler"


@app.route('/queued_jobs', methods=['GET', 'POST'])
def queued_jobs():
    if request.method == 'POST':
        job_id = request.json.get('job_id', str(uuid4()))
        queue.append({'queued_time': time(),
                      'job_id': job_id,
                      'spec': request.json['spec'],
                      'metadata': request.json.get('metadata', {}),
                      'cleanup_spec': request.json.get('cleanup_spec', {})})
        tracker_clients.queued(queue[-1])
        return make_response(jsonify(job_id), 201)
    else:
        return jsonify({i: {**val, 'position': i} for i, val in enumerate(queue)})


@app.route('/queued_jobs/<int:position>', methods=['GET'])
def show_queued_job(position):
    return queue[position]


@app.route('/queued_jobs/<int:position>', methods=['DELETE'])
def delete_queued_job(position):
    # need to make thread safe
    try:
        job = queue[position]
        del queue[position]
        tracker_clients.delete(job)
    except IndexError:
        return f"Bad queue position {position}", 404
    return make_response(jsonify({}), 204)


@app.route('/queued_jobs/<int:position>', methods=['PATCH'])
def reposition_queued_job(position):
    queue.reposition(position, request.json)
    return make_response(jsonify({}), 204)


@app.route('/running_jobs', methods=['GET'])
def show_running_jobs():
    return jsonify({key: value for key, value in running_jobs.items()})


@app.route('/running_jobs/<string:job_id>', methods=['DELETE'])
def delete_running_job(job_id):
    try:
        docker_worker_pool.stop_job(job_id)
    except IndexError:
        return f"Bad job id {job_id}", 404
    return make_response(jsonify({}), 204)


@app.route('/completed_jobs/<string:job_id>', methods=['DELETE'])
def delete_completed_job(job_id):
    return _delete_job(job_id)


def _delete_job(job_id):
    job = None
    try:
        if job_id in failed_jobs:
            job = failed_jobs[job_id]
            del failed_jobs[job_id]
        elif job_id in completed_jobs:
            job = completed_jobs[job_id]
            del completed_jobs[job_id]
        tracker_clients.delete(job)
        docker_worker_pool.delete_archive(job_id)

        return make_response(jsonify({}), 204)
    except IndexError:
        return f"Job {job_id} not found", 404


@app.route('/running_jobs/<string:job_id>/logs', methods=['GET'])
def show_logs_running_jobs(job_id):
    worker = docker_worker_pool.worker_by_job_id(job_id)
    if worker is None:
        raise KeyError("Job id not found")
    return jsonify(worker.logs())
#
#
# @app.route('/running_jobs/<string:job_id>/log_path', methods=['GET'])
# def show_log_path_running_jobs(job_id):
#     worker = docker_worker_pool.worker_by_job_id(job_id)
#     if worker is None:
#         raise KeyError("Job id not found")
#     return jsonify(worker.log_path())


@app.route('/running_jobs/<string:job_id>/container_id', methods=['GET'])
def show_container_id_running_jobs(job_id):
    worker = docker_worker_pool.worker_by_job_id(job_id)
    if worker is None:
        raise KeyError("Job id not found")
    return jsonify(worker.container_id())


@app.route('/completed_jobs', methods=['GET'])
def show_completed_jobs():
    result = {key: value for key, value in completed_jobs.items()}
    logging.info(request.args.get("sort"))
    if request.args.get("sort") is not None:
        reverse = {"asc": False, "desc": True}
        fields = [(field + ":asc").split(":")[0:2] for field in request.args.get("sort").split(",")]
        logging.debug(fields)
        for field in fields:
            try:
                result = sorted(result.items(), reverse=reverse[field[1]], key=lambda x: x[1][field[0]])
            except KeyError:
                return f"Bad sort request in {field}", 400
    return jsonify(result)


@app.route('/completed_jobs/<string:job_id>/logs', methods=['GET'])
def show_logs_completed_jobs(job_id):
    try:
        response = jsonify(completed_jobs[job_id]['logs'])
    except KeyError:
        return f"Bad job id {job_id}", 404
    return response


@app.route('/failed_jobs', methods=['GET'])
def show_failed_jobs():
    return jsonify({key: value for key, value in failed_jobs.items()})


@app.route('/failed_jobs/<string:job_id>/logs', methods=['GET'])
def show_logs_failed_jobs(job_id):
    return jsonify(failed_jobs[job_id]['logs'])


@app.route('/workers', methods=['GET', 'POST'])
def workers():
    if request.method == 'POST':
        worker_id = docker_worker_pool.add()
        return make_response(jsonify(worker_id), 201)
    else:
        workers_list = app.apscheduler.get_jobs()
        response = {}
        for worker in workers_list:
            response[worker.id] = {'id': worker.id,
                                   'max_instances': worker.max_instances,
                                   'name': worker.name,
                                   'pending': worker.pending
                                   }
        return jsonify(response)

@app.route('/workers/<int:worker_id>', methods=['DELETE'])
def delete_worker(worker_id):
    try:
        docker_worker_pool.delete_worker(worker_id)
    except IndexError:
        return f"Bad worker id {worker_id}", 404
    return make_response(jsonify({}), 204)

@app.route('/jobs/<string:job_id>', methods=['GET'])
def get_job(job_id):
    if job_id in failed_jobs:
        response = {
            "job_id": job_id,
            "logs": failed_jobs[job_id]['logs'],
            "status": "failed",
            "spec": failed_jobs[job_id]['spec']
        }
        return make_response(jsonify(response), 200)

    if job_id in completed_jobs:
        response = {
            "job_id": job_id,
            "logs": completed_jobs[job_id]['logs'],
            "status": "completed",
            "spec": completed_jobs[job_id]['spec']
        }
        return make_response(jsonify(response), 200)

    worker = docker_worker_pool.worker_by_job_id(job_id)
    if worker:
        response = {
            "job_id": job_id,
            "logs": worker.logs(),
            "status": worker.status,
            "spec": worker.job['spec']
        }
        return make_response(jsonify(response), 200)

    for job in queue:
        if job['job_id'] == job_id:
            response = {
                "job_id": job_id,
                "logs": "",
                "status": "queued",
                "spec": job['spec']
            }
            return make_response(jsonify(response), 200)

    return f"Bad job id {job_id}", 404
