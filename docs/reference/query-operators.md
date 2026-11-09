# Query operators

`simdb simulation query` (local) and `simdb remote query` (remote) find
simulations by matching against their [metadata](manifest-format.md#metadata).
This page lists the available comparison operators. For worked examples, see
[Query simulations](../how-to/query-simulations.md).

## Constraint syntax

Each constraint has the form:

```
NAME=[modifier:]VALUE
```

- `NAME` is the metadata field to match. Nested fields use dotted names, for
  example `code.name`.
- `modifier` is one of the operators below. If omitted, equality (`eq`) is used.
- String comparisons are case-insensitive.
- Passing several constraints matches simulations that satisfy **all** of them
  (logical AND).

```bash
simdb simulation query code.name=SOLPS-ITER
simdb simulation query global_quantities.r0.value=gt:6 machine=ITER
simdb remote iter query machine=ITER
```

## Operators

These operators are available for both local and remote queries:

| Modifier | Meaning |
| --- | --- |
| `eq` | Equal to `VALUE` (the default when no modifier is given). |
| `ne` | Not equal to `VALUE`. |
| `in` | Field contains `VALUE` (substring match). |
| `ni` | Field does not contain `VALUE`. |
| `gt` | Greater than `VALUE`. |
| `ge` | Greater than or equal to `VALUE`. |
| `lt` | Less than `VALUE`. |
| `le` | Less than or equal to `VALUE`. |
| `exist` | The field exists, regardless of its value. Provide no value: `NAME=exist:`. |

### Range operators

These operators apply to a metadata value shaped as a range object with `min`
and `max` keys, for example `time: {min: 2.0, max: 8.5}`. The `a` prefix stands
for "any": the comparison succeeds if any value in the range satisfies it, which
is tested against the range's `max` (for `agt`/`age`) or `min` (for
`alt`/`ale`). They work for both local and remote queries.

| Modifier | Meaning |
| --- | --- |
| `agt` | The range's `max` is greater than `VALUE`. |
| `age` | The range's `max` is greater than or equal to `VALUE`. |
| `alt` | The range's `min` is less than `VALUE`. |
| `ale` | The range's `min` is less than or equal to `VALUE`. |

## Examples

```bash
# Exact match (eq is implied)
simdb simulation query responsible_name=j.smith

# Substring match, case-insensitive
simdb simulation query workflow.name=in:test

# Numeric comparison combined with an exact match
simdb simulation query global_quantities.r0.value=gt:6 machine=ITER

# Simulations that have a "sequence" metadata field at all
simdb simulation query sequence=exist:

# Range query: the time range's upper bound is above 5.0
simdb simulation query time=agt:5.0
```

Use `-m/--meta-data NAME` to add extra metadata columns to the output, and
`--uuid` to include the simulation UUID. See the [CLI reference](cli.md) for all
options.
