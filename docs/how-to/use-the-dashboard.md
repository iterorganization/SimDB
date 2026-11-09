# Use the dashboard

Apart from using the SimDB CLI, a SimDB server can be explored via
[SimDB-Dashboard](https://github.com/iterorganization/SimDB-Dashboard) for browsing
simulation metadata in the browser.

## Open a simulation by UUID

Use this URL pattern:

```
https://<SERVER>/dashboard/uuid/<SIMULATION_UUID>
```

For example, on the ITER server with UUID
`abcdef12345678901234567890abcdef`:

```
https://simdb.iter.org/dashboard/uuid/abcdef12345678901234567890abcdef
```

## Search in the dashboard

Alternatively, enter a UUID or alias in the **Alias/UUID** search field on the
dashboard.

```{tip}
- Use the full 32-character UUID (without dashes) if that is how it is stored.
- If your deployment uses a different base path, adjust `<SERVER>` accordingly.
```

You can find a simulation's UUID from the CLI with
`simdb remote info SIM_ID` or by adding `--uuid` to a
[list or query](query-simulations.md).
