import logging
from functools import wraps

from flask import request, Response
import requests

from db.redis_connection import RedisDict
import redis


import os
my_url = os.environ.get("SCHEDULER_HOST_URL", None)
redis_host = os.environ.get("REDIS_HOST", None)
redis_port = os.environ.get("REDIS_PORT", "")
routing_map = dict()


if my_url is None:
    logging.info("Self URL not specified; operating in local mode")
else:
    if redis_host is None:
        logging.info("Proxy routing map host not specified; operating in local mode")
    else:
        logging.info(f"Proxy routing map host found, connecting to {redis_host}:{redis_port}")

for key_type in ["job_id"]:
    if redis_host is None or my_url is None:
        routing_map[key_type] = dict()
    else:
        try:
            routing_map[key_type] = RedisDict(f"routing_map:{key_type}", redis_host, redis_port)
        except redis.ConnectionError:
            logging.warning("Cannot connect to proxy routing map host; operating in local mode")
            routing_map[key_type] = dict()


def _proxy(new_host_url):
    resp = requests.request(
        method=request.method,
        url=request.url.replace(request.host_url, new_host_url),
        headers={key: value for (key, value) in request.headers if key != 'Host'},
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=False)

    excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
    headers = [(name, value) for (name, value) in resp.raw.headers.items()
               if name.lower() not in excluded_headers]

    response = Response(resp.content, resp.status_code, headers)
    return response


def forward(key_type, parameter_name):
    def decorator(f):
        @wraps(f)
        def inside(*args, **kwargs):
            try:
                key = kwargs[parameter_name]
            except KeyError:
                logging.error(f"Invalid parameter_name {parameter_name} in decorator while attempting to look up routing")
                raise

            try:
                logging.info(f"Looking up routing with key_type, key = {key_type}, {key}")
                try:
                    cur_map = routing_map[key_type]
                except KeyError:
                    logging.error(f"Invalid key_type {key_type} in decorator while attempting to look up routing")
                    raise
                host_url = cur_map[key]
            except KeyError:
                logging.info(f"Cannot find {key_type}={key} in routing table; handling request locally")
                return f(*args, **kwargs)
            else:
                if host_url != my_url:
                    logging.info(f"Found {key_type}={key} in routing table; handling request at {host_url}")
                    return _proxy(host_url)
                else:
                    logging.info(f"Found {key_type}={key} in routing table; handling request locally")
                    return f(*args, **kwargs)
        return inside
    return decorator