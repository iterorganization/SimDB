# SimDB Installation Guide


# Installing simdb

Installing from source:


```
git clone ssh://git@git.iter.org/imex/simdb.git -b develop
pip3 install ./simdb
```


Installing directly from git:


```
pip3 install git+ssh://git@git.iter.org/imex/simdb.git@develop
```


You should then be able to run the command:


```
simdb --help
```


**Note:** If you get an error such as `command not found: simdb` then you may need to add the bin folder in your pip install location to your path.


# Running the server (using built-in http server)

Once simdb has been installed, before you can run the server you need to create the server configuration file. This file should be created in the application configuration directory which can be located by using:


```
python3 -c 'import appdirs; print(appdirs.user_config_dir("simdb"))'
```


For example on Linux this would be:


```
/home/$USER/.config/simdb
```


On macOS this would be:


```
/Users/$USER/Library/Application Support/simdb
```


In this directory you should create a file 'app.cfg' specifying the server configuration. Options for the server configuration are:


<table>
  <tr>
   <td><strong>Option</strong>
   </td>
   <td><strong>Description</strong>
   </td>
  </tr>
  <tr>
   <td>DB_TYPE
   </td>
   <td>The type of database the server will use. Current choices are "pgsql" and "sqlite".
   </td>
  </tr>
  <tr>
   <td>DB_HOST
   </td>
   <td>Used when using "pgsql" to specify the database host.
   </td>
  </tr>
  <tr>
   <td>DB_PORT
   </td>
   <td>Used when using "pgsql" to specify the database port.
   </td>
  </tr>
  <tr>
   <td>UPLOAD_FOLDER
   </td>
   <td>The root directory of the location simdb will store the uploaded simulation files.
   </td>
  </tr>
  <tr>
   <td>DEBUG
   </td>
   <td>True to run the server in debug mode, or False not to.
   </td>
  </tr>
  <tr>
   <td>SSL_ENABLED
   </td>
   <td>True to run the server using SSL encryption, or False to run with no encryption.
   </td>
  </tr>
</table>


Example of app.cfg for SQLite:


```
DB_TYPE = "sqlite"
UPLOAD_FOLDER = "/tmp/simdb/simulations"
DEBUG = True
SSL_ENABLED = False
```


Example of app.cfg for PostgreSQL:


```
DB_TYPE = "pgsql"
DB_HOST = "localhost"
DB_PORT = 5432
UPLOAD_FOLDER = "/tmp/simdb/simulations"
DEBUG = False
SSL_ENABLED = True
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


Follow the url in the output and you should see the returned JSON data:


```
{ urls: [ "http://0.0.0.0:5000/api/v0.1.1" ] }
```


## Using SSL

If you want to run using SSL encryption you will need to provide a server certificate and private key in the application configuration directory.

A way to generate these is using the openssl command:


```
openssl req -x509 -out server.crt -keyout server.key \
-newkey rsa:2048 -nodes -sha256 \
  	-subj '/CN=localhost' -extensions EXT -config <( \
printf "[dn]\nCN=localhost\n[req]\ndistinguished_name = dn\n[EXT]\nsubjectAltName=DNS:localhost\nkeyUsage=digitalSignature\nextendedKeyUsage=serverAuth")
```


However, you will want to use a valid signing authority in production.


# Running the server behind nginx & gunicorn

To run the server in production you should run it as wsgi service behind a dedicated web server. To run using nginx (as a load-balancer/proxy) and gunicorn (as the web server) we need to set up the services as follows.

**Note:** The instructions below assume you already have nginx and gunicorn installed.


## Set up gunicorn service

Copy the init.d script from `simdb/remote/simdb.initd` in the simdb install directory (i.e. `/usr/local/lib/python3.7/site-packages/simdb/remote`) as `/etc/init.d/simdb`.

You will need to modify the line `USER=simdb` to change to user to whichever user you wish to run the simdb as (the gunicorn service will run as root but the workers will run in user space).

Once you have copied and modified the init.d script you can start the gunicorn service using:


```
service simdb start
```


And check that it is running using:


```
service simdb status
```



## Set up nginx service

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

**Note:** If you do not have a proxy_params file in `/etc/nginx` you can use the following:


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


**Note:** check that the line "`include /etc/nginx/sites-enabled/*.conf;" `is defined in your `/etc/nginx/nginx.conf` script, if not you can add it inside the `http {}` section.

Now you can restart nginx using:


```
service nginx restart
```


You should now be able to check the simdb server is running by going to the http address defined in your nginx site (localhost:80 in the example above).
