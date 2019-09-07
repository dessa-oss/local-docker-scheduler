from local_docker_scheduler import app
from tracker_client_plugins import tracker_clients
import logging
import argparse
import sys
import yaml


def get_args():
    parser = argparse.ArgumentParser(description='Starts a local docker scheduler')
    parser.add_argument('-H', '--host', type=str, default="0.0.0.0", help='host to bind server (default: 0.0.0.0)')
    parser.add_argument('-p', '--port', type=int, default=5000, help='port to bind server (default: 5000)')
    parser.add_argument('-d', '--debug', action='store_true', help='starts server in debug mode')

    return parser.parse_args(sys.argv[1:])


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.DEBUG)

    args = get_args()

    # load tracker plugins
    try:
        with open('tracker_client_plugins.yaml', 'r') as f:
            tracker_dict = yaml.load(f)

        for plugin_name, kwargs in tracker_dict.items():
            tracker_clients.add(plugin_name, **kwargs)
    except FileNotFoundError:
        pass

    app.run(use_reloader=False, host=args.host, port=args.port, debug=args.debug)
