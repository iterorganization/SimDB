# Validation

Validation is how SimDB and a server decide whether a simulation is complete,
intact, and acceptable. There are three independent layers. For the commands,
see [Validate a simulation](../how-to/validate-a-simulation.md); for the server
settings, see [Configure validation](../how-to/operate-server/configure-validation.md).

## Integrity (checksums)

When a simulation is ingested, SimDB records a checksum for every input and
output: a SHA-1 hash for ordinary files, and a content hash derived from the
IMAS data for IMAS entries. During push and validation these checksums are
recomputed and compared. A mismatch means the data changed since it was
catalogued (or a file is missing), and the simulation will not validate.

This is the most common cause of validation failure: one of the data sources is
absent, or something changed after ingestion.

## Metadata schema

A server can require specific metadata through a `validation-schema.yaml` file,
expressed as [Cerberus](https://docs.python-cerberus.org/) rules. For example, a
server might require a string `description` field. Different servers can have
different rules, so a simulation that is valid for one server may not be valid
for another.

Inspect a server's schema with:

```bash
simdb remote SERVER schema
```

and check a local simulation against it before pushing with:

```bash
simdb simulation validate SERVER SIM_ID
```

Failing to provide a server's mandatory metadata is the second common cause of
validation failure.

## File-content validation

Optionally, a server can inspect the *contents* of data files with a file
validator. The validator currently available is the **IDS validator** (the
`imas-validator` package), which applies rulesets to IMAS data, for example
checking that mandatory IDS quantities are populated and values fall within
expected ranges.

File validation is configured server-side under `[file_validation]` (see
[Server configuration](../reference/server-configuration.md#file_validation))
and runs when the server is set to validate uploads automatically.

## When validation runs

- **On the client**, on demand, with `simdb simulation validate`. This runs
  integrity and metadata checks against the target server's rules before you
  push, so you can fix problems early.
- **On the server**, when `auto_validate` is enabled, uploaded simulations are
  validated automatically (including any configured file validation). With
  `error_on_fail` enabled, simulations that fail are rejected. For uploads
  through the v1.3 API this happens in a background worker after the files
  have been copied, and the failure reason is reported through the ingestion
  status (see [Push and pull](../how-to/push-pull.md#push-on-a-shared-file-system)).

The outcome is reflected in the simulation's
[status](concepts.md#status-and-lifecycle).
