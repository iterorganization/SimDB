# SimDB server maintenance guide

This guide describes the steps needed to set up and maintain a SimDB server as a production service. The first section details the general steps required to do this, followed by details on how this is done at ITER.

## Installing SimDB

First clone the master branch of SimDB:

```bash
git clone ssh://git@git.iter.org/imex/simdb.git
```

Next set up the virtual environment:

```bash
cd simdb
python3 -m venv venv
source venv/bin/activate
```

And install SimDB:

```bash
pip3 install -r requirements.txt
pip3 install .
```

You can test the SimDB installation by running:

```bash
simdb --version
```

## Running the server (using built-in http server)

Once simdb has been installed, before you can run the server you need to create the server configuration file. This file should be created in the application configuration directory which can be located by using:

```
dirname "$(simdb config path)"
```

For example on Linux this would be:

```
/home/$USER/.config/simdb
```

On macOS this would be:

```
/Users/$USER/Library/Application Support/simdb
```

In this directory you should create a file 'app.cfg' specifying the server configuration. This file must have permissions set to `0600` i.e. user read only.

Options for the server configuration are:

| Section    | Option                   | Required               | Description                                                                                                                                                              |
|------------|--------------------------|------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| database   | type                     | yes                    | Database type [sqlite, postgres].                                                                                                                                        |
| database   | file                     | yes (type=sqlite)      | Database file (for sqlite) - defaults to remote.db in the user data directory if not specified.                                                                          |
| database   | host                     | yes (type=postgres)    | Database host (for postgres).                                                                                                                                            |
| database   | port                     | yes (type=postgres)    | Database port (for postgres).                                                                                                                                            |
| database   | name                     | yes (type=postgres)    | Database name (for postgres).                                                                                                                                            |
| server     | upload_folder            | yes                    | Root directory where SimDB simulation files are stored.                                                                                                                  |
| server     | ssl_enabled              | no                     | Flag [True, False] to specify whether the debug server uses SSL - this should be set to False for production servers behind dedicated webserver. Defaults to False.      |
| server     | ssl_cert_file            | yes (ssl_enabled=True) | Path to SSL certificate file if ssl_enabled is True.                                                                                                                     |
| server     | ssl_key_file             | yes (ssl_enabled=True) | Path to SSL key file if ssl_enabled is True.                                                                                                                             |
| server     | admin_password           | yes                    | Password for admin superuser.                                                                                                                                            |
| server     | token_lifetime           | no                     | Number of days generated tokens are valid for - defaults to 30 days.                                                                                                     |
 | server     | ad_server                | yes                    | Active directory server used for user authentication.                                                                                                                    |
 | server     | ad_domain                | yes                    | Active directory domain used for user authentication.                                                                                                                    |
| flask      | flask_env                | no                     | Flask server environment [development, production] - defaults to production.                                                                                             |
| flask      | debug                    | no                     | Flag [True, Flase] to specify whether Flask server is run with debug mode enabled - defaults to True if flask_env='development', otherwise False.                        |
| flask      | testing                  | no                     | Flag [True, False] to specify whether exceptions are propagated rather than being handled by Flask's error handlers - defaults to False.                                 |
| flask      | secret_key               | yes                    | Secret key used to encrypt server messages including authentication tokens - should be at least 20 characters long.                                                      |
| flask      | swagger_ui_doc_expansion | no                     | Default state of the Swagger UI documentations [none, list, full].                                                                                                       | 
| validation | auto_validate            | no                     | Flag [True, False] to set whether the server should run validation on uploaded simulation automatically. Defaults to False.                                              |
| validation | error_on_fail            | no                     | Flag [True, False] to set whether simulations that fail validation should be rejected - auto_validate must be set to True if this flag is set to True. Defaults to False |
| email      | server                   | yes                    | SMTP server used to send emails from the SimDB server.                                                                                                                   |
| email      | port                     | yes                    | SMTP server port port.                                                                                                                                                   |
| email      | user                     | yes                    | SMTP server user to send emails from .                                                                                                                                   |
| email      | password                 | yes                    | SMTP server user password.                                                                                                                                               |

Example of app.cfg for SQLite:

```
[flask]
flask_env = development
debug = True
testing = True
secret_key = CHANGE_ME

[server]
upload_folder = /tmp/simdb/simulations
ssl_enabled = False
admin_password = admin

[database]
type = sqlite

[validation]
auto_validate = True
error_on_fail = True

[email]
server = smtp.email.com
port = 465
user = test@email.com
password = abc123
```

Example of app.cfg for PostgreSQL:

```
...

[database]
type = postgres
host = localhost
port = 5432

DB_TYPE = "postgres"
DB_HOST = "localhost"
DB_PORT = 5432
UPLOAD_FOLDER = "/tmp/simdb/simulations"
DEBUG = False
SSL_ENABLED = True

...
```

Once the server configuration has been created you should be able to run

```
simdb_server 
```
And see some console output such as:

```
 * Serving Flask app "simdb.remote.app" (lazy loading)
 * Environment: production
   WARNING: This is a development server. Do not use it in a production deployment.
   Use a production WSGI server instead.
 * Debug mode: on
 * Running on http://0.0.0.0:5000/ (Press CTRL+C to quit)
```

Follow the url in the output, and you should see the returned JSON data:

```
{ urls: [ "http://0.0.0.0:5000/api/v0.1.1" ] }
```

This is running the Flask's internal webserver and should only be used for development or testing. For production the server should be run behind a dedicated webserver and load balancer, see below for details for how to do this using Gunicorn and Nginx.

## Using SSL

If you want to run using SSL encryption you will need to provide a server certificate and private key in the application configuration directory.

A way to generate these, is using the openssl command:

```
openssl req -x509 -out server.crt -keyout server.key \
-newkey rsa:2048 -nodes -sha256 \
  	-subj '/CN=localhost' -extensions EXT -config <( \
printf "[dn]\nCN=localhost\n[req]\ndistinguished_name = dn\n[EXT]\nsubjectAltName=DNS:localhost\nkeyUsage=digitalSignature\nextendedKeyUsage=serverAuth")
```

However, you will want to use a valid signing authority in production.

## Running the server behind nginx & gunicorn

To run the server in production you should run it as wsgi service behind a dedicated web server. To run using nginx (as a load-balancer/proxy) and gunicorn (as the web server) we need to set up the services as follows.

**Note:** The instructions below assume you already have nginx and gunicorn installed.

### Set up gunicorn service

Copy the init.d script from `src/simdb/remote/scripts/simdb.initd` in the simdb install directory (i.e. `/usr/local/lib/python3.7/site-packages/simdb/remote`) as `/etc/init.d/simdb`.

You will need to modify the line `USER=simdb` to change to user to whichever user you wish to run the simdb as (the gunicorn service will run as root but the workers will run in user space).

Once you have copied and modified the init.d script you can start the gunicorn service using:

```
service simdb start
```

And check that it is running using:

```
service simdb status
```

### Set up nginx service

Create a simdb.conf script in `/etc/nginx/sites-available/simdb.conf`

```
server {
    listen 80;
    server_name localhost; # or the address of the server you are running

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/run/simdb.sock;
    }
}
```

Alternatively, copy the script provided as `simdb/remote/simdb.nginx` (in the simdb installation directory, i.e. `/usr/local/lib/python3.7/site-packages/simdb/remote`) to:

```
/etc/nginx/sites-available/simdb.conf
```

The `proxy_pass` line should point to the endpoint of the gunicorn service (set by the `BIND` variable in the init.d script).

**Note:** If you do not have a proxy_params file in `/etc/nginx` you can create one containing the following:

```
proxy_set_header Host $http_host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

Now sim-link the script into `/etc/nginx/sites-enabled`:

```
simdb.conf -> /etc/nginx/sites-available/simdb.conf
```

**Note:** check that the line `include /etc/nginx/sites-enabled/*.conf;` is defined in your `/etc/nginx/nginx.conf` script, if not you can add it inside the `http {}` section.

Now you can restart nginx using:

```
service nginx restart
```

You should now be able to check the simdb server is running by going to the http address defined in your nginx site (localhost:80 in the example above).

### Using SSL with the Gunicorn/Nginx

In production, you should be using HTTPS not HTTPS for the SimDB server. To do this with Nginx you can change the simdb.conf in the `/etc/nginx/sites-available` that you created in the previous section.

Change this to be:

```
server {
    listen 443 ssl;
    server_name localhost; # or the address of the server you are running

    # Use only TLS
    ssl_protocols TLSv1.1 TLSv1.2;
    
    # Tell client which ciphers are available
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDH+AESGCM:ECDH+AES256:ECDH+AES128:DH+3DES:!ADH:!AECDH:!MD5;

    # Certificates
    ssl_certificate     /etc/pki/nginx/server.crt;
    ssl_certificate_key /etc/pki/nginx/private/server.key;

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/run/simdb.sock;
    }
}

server {
    # Redirect HTTP traffic to HTTPS
    if ($host = localhost) { # or the address of the server you are running
        return 301 https://$host$request_uri;
    }
    
    server_name localhost; # or the address of the server you are running
    listen 80;
    
    return 404;
}
```

The `ssl_certificate` and `ssl_certificate_key` should be set to point to the SSL certificate and key that you have generated using a valid signing authority for the server.

## Setting up PostgreSQL database

For the production server you should be using a production DBMS. To use PostgreSQL as the DBMS you can use the following instructions.

First, install PostgreSQL:

```bash
sudo yum -y install postgresql-server postgresql-contrib
```

Next, initialise the database:

```bash
postgresql-setup initdb
```

You then need to connect to the database as the `postgres` user. You can do this using:

```bash
sudo -u postgres psql
```

And run the following:

```sql
CREATE DATABASE simdb;
CREATE ROLE simdb;
ALTER DATABASE simdb OWNER TO simdb;
ALTER ROLE "simdb" WITH LOGIN; 
```

This is assuming your webserver is running as user `simdb`. If not, you should change the role name above to match whichever user you are running the server under.