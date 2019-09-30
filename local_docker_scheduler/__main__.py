"""
Copyright (C) DeepLearning Financial Technologies Inc. - All Rights Reserved
Unauthorized copying, distribution, reproduction, publication, use of this file, via any medium is strictly prohibited
Proprietary and confidential
Written by Eric lee <e.lee@dessa.com>, 08 2019
"""

from local_docker_scheduler import get_app
from db import gpu_pool
import logging
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
    logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.DEBUG)

    args = get_args()

    logging.info(f"***ENV: {os.environ}")
    if os.environ.get("CUDA_VISIBLE_DEVICES", None):
        logging.info(f"*** GPU_POOL 1: {gpu_pool}")
        gpu_pool["0"] = "unlocked"
        gpu_pool["1"] = "unlocked"
        gpu_pool["2"] = "unlocked"
        gpu_pool["3"] = "unlocked"
        # gpu_pool = {k: "unlocked" for k in os.environ["CUDA_VISIBLE_DEVICES"].split(",")}
        logging.info(f"*** GPU_POOL 2: {gpu_pool}")

    num_workers = os.environ.get("NUM_WORKERS", 1)
    logging.info(f"*** GPU_POOL 3: {gpu_pool}")

    get_app(num_workers).run(use_reloader=False, host=args.host, port=args.port, debug=args.debug, threaded=False)
