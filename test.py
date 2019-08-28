from time import sleep
from docker_worker_pool import WorkerPool
from repositionable_queue import Queue

if __name__ == "__main__":
    worker_pool = WorkerPool(2)
    queue = Queue([])
    for i in range(10):
        queue.append(
            {'image': "5b117edd0b76",
             'command': "sleep 3",
             })

    while True:
        try:
            job = queue.pop()

            try:
                worker_pool.start_job(job)
                print("started job " + str(job))
            except WorkerPool.NoResourcesException:
                queue.append(job)
                print("could not start job " + str(job))
        except IndexError:
            pass

        sleep(1)
