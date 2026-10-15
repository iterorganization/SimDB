# Configure validation

A server can validate simulations automatically when they are uploaded:
checksums, a metadata schema, and optionally the contents of data files. For the
concepts, see [Validation](../../explanation/validation.md).

## Validate uploads automatically

In `app.cfg`:

```ini
[validation]
auto_validate = True
error_on_fail = True
```

- `auto_validate` runs validation (including any file validation) on every
  upload.
- `error_on_fail` rejects simulations that fail. It requires `auto_validate`.

Uploads through the v1.2 API are validated inside the request, so the response
carries the result. Uploads through the v1.3 API (`simdb simulation push_local`)
are validated by a [background worker](run-celery-workers.md) once the files
have been copied: the ingestion passes through the `VALIDATING` state, and a
failure is recorded with the simulation and reported by the status endpoint.
With `error_on_fail` the ingestion then ends in the `VALIDATION_FAILED` state
and the simulation can be deleted; without it the simulation is ingested with a
failed validation status. The worker needs the same `[validation]` and
`[file_validation]` configuration as the server, and the `imas-validator` extra
installed when the IDS validator is enabled.

## Require metadata

Create `validation-schema.yaml` in the same directory as `app.cfg`, using
[Cerberus](https://docs.python-cerberus.org/) rules:

```yaml
description:
  required: true
  type: string
machine:
  required: true
  type: string
```

Clients can read the active schema with `simdb remote SERVER schema` and check
against it with `simdb simulation validate`.

## Validate file contents (IDS validator)

To check the contents of IMAS data files, enable a file validator. The
`ids_validator` requires the `imas-validator`
[extra](../../getting-started/installation.md#optional-extras).

```ini
[file_validation]
type = ids_validator
bundled_ruleset = True
apply_generic = True
rule_filter_ids = summary,equilibrium
```

See the
[file validation options](../../reference/server-configuration.md#file_validation)
for the full list, including custom rule directories and ruleset filters.
