# Database Setup

Managing PostgreSQL

```bash
pg_ctl init -D data/
pg_ctl start -D data/ -l logs/pgsql.log
pg_ctl stop -D data/
```

Creating the database

```bash
createdb simdb
```
