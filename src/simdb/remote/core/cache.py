from flask_caching import Cache
from flask import request

from simdb.config import Config

config = Config('app.cfg')
config.load()
cache_options = {'CACHE_' + k.upper(): v for (k, v) in config.get_section('cache', [])}

cache = Cache(config=cache_options)


def cache_key(*args, **kwargs):
    headers = []
    for key in request.headers.keys():
        if 'simdb-' in key.lower():
            headers.append('{}:{}'.format(key.lower(), request.headers.get(key, 0)))
    return request.url + '?' + '&'.join(headers)
