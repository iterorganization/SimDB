# Setting up a PostgreSQL database

This section will give some guidance to setting up a PostgreSQL server for SimDB. If
PostgreSQL is already set up and running on the machine this section can be skipped
and the connection details set in the SimDB configuration file. This is not intended 
to be an exhaustive guide to PostgreSQL (more details can be found on the [PostgreSQL website](https://www.postgresql.org/)).

## Installing PostgreSQL

PostgreSQL should be installed from an available system package. This should install
the database and create the default data directory (/var/lib/pgsql/data on CentOS 
Linux). The PostgreSQL service should then be started and enabled on the system 
(`system postgres start` and `system postgres enable` on Linux).

## Connecting to PostgreSQL

The SimDB server will need to be able to connect to the database. You can test this connection using:

```python
import psycopg2
psycopg2.connect("postgresql://simdb@<HOST>:<PORT>")
```

replacing `<HOST>` with the PostgreSQL hostname and `<PORT>` with the PostgreSQL port, e.g. `"postgresql://simdb@localhost:5432"`.

If you have issue connecting to a localhost database then you may need to check your `pg_hba.conf` in the PostgreSQL data folder and check the connection setting is set to `trust` rather than `ident`.