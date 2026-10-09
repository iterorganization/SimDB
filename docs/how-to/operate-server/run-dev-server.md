# Run a development server

SimDB ships a built-in HTTP server for testing and development.

```{warning}
The built-in server is for testing and development only. For production, run
behind a dedicated web server: see
[Run behind Nginx and Gunicorn](run-behind-nginx-gunicorn.md).
```

## Prerequisites

- SimDB [installed with the server extra](install-server.md).
- An `app.cfg` in the application configuration directory (see
  [Install a server](install-server.md)).

## Start it

```bash
simdb_server
```

The server starts on port 5000. Check it by opening
<http://localhost:5000> in a browser, or:

```bash
curl http://0.0.0.0:5000
```

which returns the available API URLs as JSON.

## Interactive API docs

Each API version publishes Swagger UI documentation, for example
<http://localhost:5000/v1.2/docs>. See the
[REST API reference](../../reference/rest-api.md).

## Troubleshooting the port

If the server cannot bind to port 5000, another service is using it. Stop that
service, or change the `server.port` setting in your SimDB configuration. See
also [Troubleshooting](../../troubleshooting.md).
