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
openssl req -x509 -out server.crt -keyout server.key \
  -newkey rsa:2048 -nodes -sha256 \
  -subj '/CN=localhost' -extensions EXT -config <( \
   printf "[dn]\nCN=localhost\n[req]\ndistinguished_name = dn\n[EXT]\nsubjectAltName=DNS:localhost\nkeyUsage=digitalSignature\nextendedKeyUsage=serverAuth")
```
