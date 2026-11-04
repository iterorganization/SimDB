# Run behind Nginx and Gunicorn

In production, run the SimDB server as a WSGI service behind a dedicated web
server. This guide uses Gunicorn as the WSGI server and Nginx as the
proxy/load-balancer. It assumes Nginx and Gunicorn are already installed.

**For container deployments**, the sister project
[SimDB-Dashboard](https://github.com/iterorganization/SimDB-Dashboard) provides
a complete nginx configuration that proxies `/scenarios/api` to the SimDB
backend. This is the recommended approach for modern deployments.

## Set up Nginx (bare-metal)

Create `/etc/nginx/conf.d/simdb.conf`, for example:

```nginx
server {
    listen 80;
    server_name localhost;   # or the server's address

    location /scenarios/api {
        # Typical proxy params
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Inform simdb backend to add this prefix in their responses
        proxy_set_header X-Forwarded-Prefix /scenarios/api;

        proxy_pass http://unix:/var/run/simdb.sock;
        # For TCP proxy instead (e.g., if gunicorn binds to 0.0.0.0:5000):
        # proxy_pass http://localhost:5000;
    }
}
```

Make sure `/etc/nginx/nginx.conf` includes `/etc/nginx/conf.d/*.conf` inside its
`http {}` block, then reload your nginx service.

## Allow large uploads

Simulation uploads can be large. Raise the body-size limit (at least 100 MB) in
`/etc/nginx/nginx.conf`:

```nginx
client_max_body_size 100m;
```

## Enable HTTPS

For production, terminate TLS at Nginx. See [Enable SSL](enable-ssl.md).
