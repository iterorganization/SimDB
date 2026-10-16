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
carries the result and `error_on_fail` can reject the upload. Uploads through the
v1.3 API (`simdb simulation push_local`) are validated by a
[background worker](run-celery-workers.md) after the ingestion has completed, so
the client does not wait for it and `error_on_fail` does not apply: the
simulation is kept whatever the outcome. The worker needs the same
`[validation]` and `[file_validation]` configuration as the server, and the
`imas-validator` extra installed when the IDS validator is enabled.

Either way the outcome is stored with the simulation: its status becomes
`passed` or `failed`, and the `validation_report` metadata holds the result of
every check, so it can be read back later with `simdb remote REMOTE info SIM_ID`
or from the simulation's metadata in the API.

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
rule_filter_ids = core_profiles
```

The rule filters select the rules to run. `rule_filter_ids` keeps only the
rules written for the given IDS, and a rule must match every listed value, so
`rule_filter_ids = core_profiles,equilibrium` runs only rules that cover both
IDSs. Generic rules that apply to every IDS are not selected by an IDS filter.
A filter that matches no rule makes the validation pass with zero tests, which
the stored report shows as `Number of tests carried out : 0`.

Validating a large dataset takes minutes: the validator loads every IDS and
evaluates the rules on each time slice.

See the
[file validation options](../../reference/server-configuration.md#file_validation)
for the full list, including custom rule directories and ruleset filters.
