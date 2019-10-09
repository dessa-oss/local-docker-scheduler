import math
import time

current_time = math.floor(time.time())

with open(f'/job/job_archive/timestamp-{current_time}', 'w') as timestamp_file:
    timestamp_file.write(str(current_time))