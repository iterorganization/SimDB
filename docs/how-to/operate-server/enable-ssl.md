# Enable SSL

A production SimDB server must serve over HTTPS. There are two ways to enable
SSL, depending on how you run the server.

**For container deployments**, the sister project
[SimDB-Dashboard](https://github.com/iterorganization/SimDB-Dashboard) provides
a complete nginx configuration, including TLS, that proxies `/scenarios/api` to
the SimDB backend. This is the recommended approach for modern deployments.

## Option A: TLS at Nginx

When [running behind Nginx and Gunicorn](run-behind-nginx-gunicorn.md), let
Nginx terminate TLS. Change `/etc/nginx/conf.d/simdb.conf` to listen on 443 and
redirect HTTP to HTTPS:

```nginx
server {
    listen 443 ssl;
    server_name localhost;   # or the server's address

    ssl_protocols TLSv1.1 TLSv1.2;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDH+AESGCM:ECDH+AES256:ECDH+AES128:DH+3DES:!ADH:!AECDH:!MD5;

    ssl_certificate     /etc/pki/nginx/server.crt;
    ssl_certificate_key /etc/pki/nginx/private/server.key;

    location /scenarios/api {
        # Typical proxy params
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Inform simdb backend to add this prefix in their responses
        proxy_set_header X-Forwarded-Prefix /scenarios/api;

        proxy_pass http://unix:/var/run/simdb.sock;
    }
}

server {
    if ($host = localhost) {   # or the server's address
        return 301 https://$host$request_uri;
    }
    server_name localhost;
    listen 80;
    return 404;
}
```

Point `ssl_certificate` and `ssl_certificate_key` at a certificate and key
issued by a valid signing authority.

## Option B: TLS at the built-in server

For the built-in development server, set the SSL options in `app.cfg`:

```ini
[server]
ssl_enabled = True
ssl_cert_file = /path/to/server.crt
ssl_key_file = /path/to/server.key
```

## Generating a self-signed certificate (testing only)

For local testing you can generate a self-signed certificate. Use a real signing
authority in production.

```bash
openssl req -x509 -out server.crt -keyout server.key \
  -newkey rsa:2048 -nodes -sha256 \
  -subj '/CN=localhost' -extensions EXT -config <( \
  printf "[dn]\nCN=localhost\n[req]\ndistinguished_name = dn\n[EXT]\nsubjectAltName=DNS:localhost\nkeyUsage=digitalSignature\nextendedKeyUsage=serverAuth")
```
