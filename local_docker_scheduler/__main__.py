"""
Copyright (C) DeepLearning Financial Technologies Inc. - All Rights Reserved
Unauthorized copying, distribution, reproduction, publication, use of this file, via any medium is strictly prohibited
Proprietary and confidential
Written by Eric lee <e.lee@dessa.com>, 08 2019
"""

from local_docker_scheduler import get_app
import logging
import argparse
import sys


def get_args():
    parser = argparse.ArgumentParser(description='Starts a local docker scheduler')
    parser.add_argument('-H', '--host', type=str, default="0.0.0.0", help='host to bind server (default: 0.0.0.0)')
    parser.add_argument('-p', '--port', type=int, default=5000, help='port to bind server (default: 5000)')
    parser.add_argument('-d', '--debug', action='store_true', help='starts server in debug mode')

    return parser.parse_args(sys.argv[1:])


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.DEBUG)

    args = get_args()

    get_app(1).run(use_reloader=False, host=args.host, port=args.port, debug=args.debug, threaded=False)
