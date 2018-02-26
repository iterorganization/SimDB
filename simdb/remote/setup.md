# Database Setup

Managing PostgreSQL

Creating the server:

```bash
pg_ctl init -D data/
sed -i.bak 's/#port = 5432/port = 7000/' data/postgresql.conf
mkdir logs
```

Starting the server:

```bash
pg_ctl start -D data/ -l logs/pgsql.log
```

Stopping the server:

```bash
pg_ctl stop -D data/
```

Creating the database

```bash
createdb -p 7000 simdb
```

Creating certificates:

```bash
openssl genrsa 1024 > server.key
chmod 400 server.key
openssl req -new -x509 -key server.key -subj "/C=GB/ST=OXON/O=UKAEA/OU=CCFE/CN=127.0.0.1" -reqexts SAN -extensions SAN -config <(cat /etc/ssl/openssl.cnf <(printf "[SAN]\nsubjectAltName=DNS:127.0.0.1,DNS:localhost")) -out server.crt

country name
state name
locality
organization
unit
common name
email

```
