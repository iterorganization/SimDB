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
  `error_on_fail` enabled, simulations uploaded through the v1.2 API that fail
  are rejected. Uploads through the v1.3 API are validated by a background
  worker after the ingestion has completed, and are kept whatever the outcome
  (see [Push and pull](../how-to/push-pull.md#push-on-a-shared-file-system)).

The outcome is reflected in the simulation's
[status](concepts.md#status-and-lifecycle), and the result of every check is
stored in its `validation_report` metadata so it can be read back later.

### The validation report

`validation_report` is a structured value, so a client can show how many tests
passed or which rule failed without parsing text. Every level carries `passed`
and `tests` (`total`, `passed`, `failed`):

```json
{
  "passed": false,
  "error": null,
  "tests": {"total": 89559, "passed": 69383, "failed": 20176},
  "metadata": {"passed": true, "error": null},
  "files": [
    {
      "uri": "imas:hdf5?path=/data/simdb/simulations/.../run",
      "passed": false,
      "error": null,
      "tests": {"total": 89559, "passed": 69383, "failed": 20176},
      "ids": [
        {
          "name": "core_profiles",
          "occurrence": 0,
          "passed": false,
          "tests": {"total": 89559, "passed": 69383, "failed": 20176},
          "rules": [
            {
              "name": "generic/core_profiles.py:validate_zeff",
              "passed": false,
              "tests": {"total": 59736, "passed": 40520, "failed": 19216},
              "message": "Effective charge zeff not consistent with ion square charge and density",
              "failed_nodes": 159216,
              "sample_nodes": ["profiles_1d[0]/zeff", "profiles_1d[1]/zeff"]
            }
          ]
        }
      ]
    }
  ]
}
```

- The top-level `error` is set, and nothing else is filled in, when the
  validation could not run at all: for example the file validator is not
  installed on the worker or the configuration names an unknown one. The
  simulation is marked failed in that case too, but its watchers are not
  emailed, since this is a problem for the operator rather than for them.
- `metadata.error` holds the schema violations when the metadata check failed.
- A file the validator could not open at all has `error` set and no `ids`.
- A rule is evaluated once per node or time slice it covers, so it has test
  counts of its own; it `passed` only if every evaluation passed. `message` is
  the reason of the first failure, `failed_nodes` how many nodes the failures
  affect and `sample_nodes` a few of them.
- Rules that did not run, because a rule filter excluded them, are not listed.

`simdb remote info` prints the report as nested metadata, and the email sent
to watchers on a failure renders it as text.

