from flask_caching import Cache

from simdb.config import Config

config = Config('../scripts/app.cfg')
config.load()
cache_options = {'CACHE_' + k.upper(): v for (k, v) in config.get_section('cache', [])}

cache = Cache(config=cache_options)
