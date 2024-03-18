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

**Note:** If you plan to run the server with a PostgreSQL database you will also need to install the `psycopg2-binary` library.

You can test the SimDB installation by running:

```bash
simdb --version
```

## Running the server (using built-in http server)

**Note:** Running the SimDB server using the built-in http server is for testing/development only and should not be used in production. In production you should run the SimDB server behind a dedicated web-server such as NGinx (see the [Running the server behind nginx & gunicorn](#running-the-server-behind-nginx--gunicorn) section below).

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

| Section    | Option                   | Required               | Description                                                                                                                                                                                                                                        |
|------------|--------------------------|------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| database   | type                     | yes                    | Database type [sqlite, postgres].                                                                                                                                                                                                                  |
| database   | file                     | yes (type=sqlite)      | Database file (for sqlite) - defaults to remote.db in the user data directory if not specified.                                                                                                                                                    |
| database   | host                     | yes (type=postgres)    | Database host (for postgres).                                                                                                                                                                                                                      |
| database   | port                     | yes (type=postgres)    | Database port (for postgres).                                                                                                                                                                                                                      |
| database   | name                     | yes (type=postgres)    | Database name (for postgres).                                                                                                                                                                                                                      |
| server     | upload_folder            | yes                    | Root directory where SimDB simulation files are stored.                                                                                                                                                                                            |
| server     | ssl_enabled              | no                     | Flag [True, False] to specify whether the debug server uses SSL - this should be set to False for production servers behind dedicated webserver. Defaults to False.                                                                                |
| server     | ssl_cert_file            | yes (ssl_enabled=True) | Path to SSL certificate file if ssl_enabled is True.                                                                                                                                                                                               |
| server     | ssl_key_file             | yes (ssl_enabled=True) | Path to SSL key file if ssl_enabled is True.                                                                                                                                                                                                       |
| server     | admin_password           | yes                    | Password for admin superuser.                                                                                                                                                                                                                      |
| server     | token_lifetime           | no                     | Number of days generated tokens are valid for - defaults to 30 days.                                                                                                                                                                               |
| server     | imas_remote_host         | no                     | Host name to set on ingested IMAS URIs which will be used to fetch the data via the specified IMAS remote access server. I.e. imas:hdf5?path=foo becomes imas://<imas_remote_host>:<imas_remote_port>/uda?path=foo&backend=hdf5 on ingest.         |
| server     | imas_remote_port         | no                     | Port to set on ingested IMAS URIs on ingest. See imas_remote_host for more details.                                                                                                                                                                |
| flask      | flask_env                | no                     | Flask server environment [development, production] - defaults to production.                                                                                                                                                                       |
| flask      | debug                    | no                     | Flag [True, Flase] to specify whether Flask server is run with debug mode enabled - defaults to True if flask_env='development', otherwise False.                                                                                                  |
| flask      | testing                  | no                     | Flag [True, False] to specify whether exceptions are propagated rather than being handled by Flask's error handlers - defaults to False.                                                                                                           |
| flask      | secret_key               | yes                    | Secret key used to encrypt server messages including authentication tokens - should be at least 20 characters long.                                                                                                                                |
| flask      | swagger_ui_doc_expansion | no                     | Default state of the Swagger UI documentations [none, list, full].                                                                                                                                                                                 | 
| validation | auto_validate            | no                     | Flag [True, False] to set whether the server should run validation on uploaded simulation automatically. Defaults to False.                                                                                                                        |
| validation | error_on_fail            | no                     | Flag [True, False] to set whether simulations that fail validation should be rejected - auto_validate must be set to True if this flag is set to True. Defaults to False                                                                           |
| email      | server                   | yes                    | SMTP server used to send emails from the SimDB server.                                                                                                                                                                                             |
| email      | port                     | yes                    | SMTP server port port.                                                                                                                                                                                                                             |
| email      | user                     | yes                    | SMTP server user to send emails from .                                                                                                                                                                                                             |
| email      | password                 | yes                    | SMTP server user password.                                                                                                                                                                                                                         |

### Authentication options

| Section        | Option         | Required | Description                                                                                                                                                                                                                                        |
|----------------|----------------|----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| authentication | type           | yes      | Name of the authentication method used by the server to authenticate users - current options are [ActiveDirectory, LDAP, None]. See sections below for details of extra options required for the Active Directory and LDAP authentication options. |
| authentication | firewall_auth  | no       | Flag [True, False] to specify that the server is being run behind a firewall and that the authentication should be read from the firewall headers.                                                                                                 |
| authentication | firewall_user  | no       | Name of the firewall header to use for the user name. Required if firewall_auth is True.                                                                                                                                                           |
| authentication | firewall_email | no       | Name of the firewall header to use for the user's email. Required if firewall_auth is True.                                                                                                                                                        |

### Activate Directory authentication options

| Section        | Option    | Required | Description                                           |
|----------------|-----------|----------|-------------------------------------------------------|
| authentication | ad_server | yes      | Active directory server used for user authentication. |
| authentication | ad_domain | yes      | Active directory domain used for user authentication. |

### LDAP authentication options

| Section        | Option              | Required | Description                                                                                                                                                              |
|----------------|---------------------|----------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| authentication | ldap_server         | yes      | LDAP server URI.                                                                                                                                                         |
| authentication | ldap_bind           | yes      | Bind string - this can contain {username} which will be replaced by the username of the user attempting to authenticate, i.e. "uid={username},ou=Users,dc=eufus,dc=eu".  |
| authentication | ldap_query_user     | no       | Bind user used to run LDAP queries, i.e. "uid=f2bind,ou=Users,dc=eufus,dc=eu" - if not provided the queries are run as the authenticated user.                           |
| authentication | ldap_query_password | no       | Password corresponding to ldap_query_user. Only required if ldap_query_user is specified.                                                                                |
| authentication | ldap_query_base     | yes      | Base point to start the query from, i.e. "dc=eufus,dc=eu".                                                                                                               |
| authentication | ldap_query_filter   | yes      | Query filter used to find the user - this can contain {username} which will be replaced by the username of the user attempting to authenticate, i.e. "(uid={username})". |
| authentication | ldap_query_uid      | no       | Name of the user parameter in the LDAP search query - defaults to 'uid'.                                                                                                 |
| authentication | ldap_query_mail     | no       | Name of the email parameter in the LDAP search query - defaults to 'mail'.                                                                                               |

### Caching options

| Section | Option          | Required | Description                                                                                                                                                                                                             |
|---------|-----------------|----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| cache   | type            | no       | Type of caching to use. Options include NullCache (default), SimpleCache, FileSystemCache. SimpleCache is a memory based cache and FileSystemCache caches using files. Configuration options for these are given below. |
| cache   | dir             | no       | Directory to store cache. Used only for FileSystemCache.                                                                                                                                                                |
| cache   | default_timeout | no       | The default timeout that is used if no timeout is specified. Unit of time is seconds.                                                                                                                                   |
| cache   | threshold       | no       | The maximum number of items the cache will store before it starts deleting some. Used only for SimpleCache and FileSystemCache                                                                                          |

More caching options can be found in the [Flask-Caching documentation](https://flask-caching.readthedocs.io/en/latest/#built-in-cache-backends). You can convert the caching options for the library to SimDB configuration by removing the `CACHE_` prefix and converting to lowercase, i.e. `CACHE_ARGS` becomes `args` in the `[cache]` section.

### Role options

| Section | Option | Required | Description                                                    |
|---------|--------|----------|----------------------------------------------------------------|
| role    | users  | yes      | A comma separated list of the the users assigned to this role. |

Each role must be given a name in the section header, and whilst defining any roles is optional each `role` section must
have a `users` option.

For example:

```yaml
[role "admin"]
users = admin,user1,user2
```

Currently only the `admin` role is used in SimDB (this is the set of users able to perform CLI command in the `admin`
command subgroup).

### Example configuration files

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

Example of app.cfg for PostgreSQL (see [Setting up PostgreSQL database](setting_up_postgres.md)):

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

**Note:** If it fails to run with an error stating that it cannot bind to a port then you will need to see check whatever service is running on port 5000 and shut this down if possible. If you need to modify the port you will need to edit the `simdb_server` script (which you can locate using `which simdb_server`), changing the port number.

Follow the url in the output (you can do this using a browser or using curl, e.g. `curl http://0.0.0.0:5000`), and you should see the returned JSON data:

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

You will need to modify the line `USER=simdb` to change to user to whichever user you wish to run the simdb as (the gunicorn service will run as root but the workers will run in user space). You will also need to modify the line `DAEMON=/home/simdb/venv/bin/gunicorn` to change the path to point towards the gunicorn installed in your virtual environment - you can find this path by running `which gunicorn` whilst the virtual environment is active.

Once you have copied and modified the init.d script you can start the gunicorn service using:

```
service simdb start
```

And check that it is running using:

```
service simdb status
```

### Set up nginx service

Create a simdb.conf script in `/etc/nginx/conf.d/simdb.conf`

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
/etc/nginx/conf.d/simdb.conf
```

The `proxy_pass` line should point to the endpoint of the gunicorn service (set by the `BIND` variable in the init.d script).

**Note:** If you do not have a proxy_params file in `/etc/nginx` you can create one containing the following:

```
proxy_set_header Host $http_host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

**Note:** check that the line `include /etc/nginx/conf.d/*.conf;` is defined in your `/etc/nginx/nginx.conf` script, if not you can add it inside the `http {}` section.

Now you can restart nginx using:

```
service nginx restart
```

You should now be able to check the simdb server is running by going to the http address defined in your nginx site (localhost:80 in the example above).

#### Nginx Request Entity Size

You may need to increase the size of uploaded files that Nginx will accept. For SimDB this should be at least 100MB.

You can set this by changing the following option in your `/etc/nginx/nginx.conf` file:

```
client_max_body_size 100m;
```

### Using SSL with the Gunicorn/Nginx

In production, you should be using HTTPS not HTTP for the SimDB server. To do this with Nginx you can change the simdb.conf in the `/etc/nginx/sites-available` that you created in the previous section.

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