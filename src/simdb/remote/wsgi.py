import ssl
import sys

from .app import create_app

if "sphinx" not in sys.modules:
    from werkzeug.middleware.proxy_fix import ProxyFix

    # Do not create app when making docs as configuration file may not exist.
    app = create_app()
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_prefix=1)


def run(*, port=5000):
    # from werkzeug.middleware.profiler import ProfilerMiddleware
    # app.config['PROFILE'] = True
    # app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[50], sort_by=("cumtime",))
    config = app.simdb_config

    if config.get_option("server.ssl_enabled"):
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        context.load_cert_chain(
            certfile=config.get_option("server.ssl_cert_file"),
            keyfile=config.get_option("server.ssl_key_file"),
        )
        app.run(host="0.0.0.0", port=port, ssl_context=context)
    else:
        app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    run(port=5000)
