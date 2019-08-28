from app import app
from db import queue, running_jobs, completed_jobs, failed_jobs
from flask import jsonify, request, make_response
from time import time
from uuid import uuid4
import docker_worker_pool


@app.route('/')
def show_home_page():
    return "Welcome to docker scheduler"


@app.route('/queued_jobs', methods=['GET', 'POST'])
def queued_jobs():
    if request.method == 'POST':
        job_id = uuid4().hex
        queue.append({'queued_time': time(),
                      'job_id': job_id,
                      'spec': request.json})
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


@app.route('/completed_jobs', methods=['GET'])
def show_completed_jobs():
    return jsonify({key: value for key, value in completed_jobs.items()})


@app.route('/failed_jobs', methods=['GET'])
def show_failed_jobs():
    return jsonify({key: value for key, value in failed_jobs.items()})

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