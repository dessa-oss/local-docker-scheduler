from local_docker_scheduler import app
from db import queue, running_jobs, completed_jobs, failed_jobs
from flask import jsonify, request, make_response
from time import time
from uuid import uuid4
import docker_worker_pool
import logging


@app.route('/')
def show_home_page():
    return "Welcome to docker scheduler"


@app.route('/queued_jobs', methods=['GET', 'POST'])
def queued_jobs():
    if request.method == 'POST':
        job_id = request.json.get('job_id', uuid4().hex)
        queue.append({'queued_time': time(),
                      'job_id': job_id,
                      'spec': request.json['spec']})
        return make_response(jsonify(job_id), 201)
    else:
        return jsonify({i: {**val, 'position': i} for i, val in enumerate(queue)})


@app.route('/queued_jobs/<int:position>', methods=['GET'])
def show_queued_job(position):
    return queue[position]


@app.route('/queued_jobs/<int:position>', methods=['DELETE'])
def delete_queued_job(position):
    del queue[position]
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
    docker_worker_pool.stop(job_id)
    return make_response(jsonify({}), 204)


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


@app.route('/running_jobs/<string:job_id>/log_path', methods=['GET'])
def show_log_path_running_jobs(job_id):
    worker = docker_worker_pool.worker_by_job_id(job_id)
    if worker is None:
        raise KeyError("Job id not found")
    return jsonify(worker.log_path())


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
    docker_worker_pool.kill(worker_id)
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
            "status": "running",
            "spec": running_jobs[job_id]['spec']
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
