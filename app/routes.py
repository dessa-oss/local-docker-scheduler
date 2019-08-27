from app import app, q, wp
from flask import abort, request


@app.route('/')
def show_home_page():
    return "Welcome to docker scheduler"

@app.route('/queued_jobs', methods=['GET', 'POST'])
def queued_jobs():
    if request.method == 'POST':
        q.append(request.json)
    return str(q)

@app.route('/queued_jobs/<int:position>', methods=['GET'])
def show_queued_job(position):
    return q[position]