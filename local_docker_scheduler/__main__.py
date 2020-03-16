import logging
logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.DEBUG)

from local_docker_scheduler import get_app
import local_docker_scheduler.routes # so that the routes are loaded into the app
from db import gpu_pool
import argparse
import sys
import os

def get_args():
    parser = argparse.ArgumentParser(description='Starts a local docker scheduler')
    parser.add_argument('-H', '--host', type=str, default="0.0.0.0", help='host to bind server (default: 0.0.0.0)')
    parser.add_argument('-p', '--port', type=int, default=5000, help='port to bind server (default: 5000)')
    parser.add_argument('-d', '--debug', action='store_true', help='starts server in debug mode')

    return parser.parse_args(sys.argv[1:])


if __name__ == '__main__':
    args = get_args()

    if os.environ.get("CUDA_VISIBLE_DEVICES", None):
        gpu_pool.update({k: "unlocked" for k in os.environ["CUDA_VISIBLE_DEVICES"].split(",")})

    get_app().run(use_reloader=False, host=args.host, port=args.port, debug=args.debug, threaded=True)
