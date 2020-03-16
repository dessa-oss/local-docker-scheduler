import math
import os
import time

current_time = math.floor(time.time())
job_id = os.environ['FOUNDATIONS_JOB_ID']

os.makedirs(f'/job/job_archive/{job_id}', exist_ok=True)

with open(f'/job/job_archive/{job_id}/timestamp-{current_time}', 'w') as timestamp_file:
    timestamp_file.write(str(current_time))
