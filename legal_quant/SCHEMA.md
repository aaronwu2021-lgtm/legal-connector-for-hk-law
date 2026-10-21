# Declarative model contract, version 1

`models.json` is the single source of mathematical definitions for the Python
package and the JavaScript API. Neither runtime accepts a user-supplied formula.
`sources.json` records the provenance and verification level of referenced
materials. A source's presence does not establish that its rule applies in Hong
Kong or to a particular case.

## Catalogue

The root contains `schema_version: "1"` and a `models` array. Each model has:

- Identity: `id`, `version` (a string), `title`, `category`, `output_kind`.
- Purpose: `question`, `formula_summary`, `legal_status`.
- Classification: `analysis_layer` (`legal_standard` or `supporting_analysis`)
  and `formula_authority`. `judicial_heuristic` identifies reasoning explicitly
  found in a judgment (the model may include stated extensions);
  `legal_test_formalisation` identifies a project model of an actual legal test.
  Supporting tools retain a separate classification. None of these labels
  certifies jurisdictional applicability or a binding numerical threshold.
- Boundaries: `assumptions`, `limitations`, `required_legal_findings`.
- Provenance: `source_ids`, resolved against the source ledger.
- Computation: `fields`, `constraints`, and ordered `outputs`.
- Demonstration: `example_inputs`, `example_basis: "hypothetical"`.

Categories distinguish `legal_standard`, `amount`, `evidence`, `decision`, `balancing`, `market`
and `policy`. These are not elements of a common legal score and must not be
summed into one.

## Inputs

All declared fields are required. Unknown fields are rejected, including inside
object arrays. Missing values, `null`, numeric strings, Boolean values and
nonfinite numbers are never silently converted to zero or to a valid number.

Each field has `id`, `label`, `description`, `unit`, and `type`. Supported types
are `number`, `integer`, `string`, `number_array` and `object_array`.

- Numeric bounds: `min`, `max`, `exclusiveMinimum`, `exclusiveMaximum`.
- Numeric allowed grades: `enum`.
- Array bounds: `minItems`, `maxItems`; the runtime ceiling is 256 entries.
- `number_array` applies its numeric bounds to each element.
- `object_array.items` is an array of child field definitions.
- Integers must be within JavaScript's safe integer range.
- Strings must be nonempty after trimming and at most 2,000 characters.

Numeric calculations use ordinary binary floating-point arithmetic; preserve
unrounded results for reproducibility and round only for display. They are not
an arbitrary-precision accounting system. Python converts numbers, including
JSON integer inputs, to binary64 for each operation to match JavaScript's
numeric semantics. Integer-typed input fields still require safe integers.

The Hand model calculates avoided loss using the algebraically equivalent
`NpL(eₚ+eₗ−eₚeₗ)` form. This preserves very small reductions that could disappear
if two very large, nearly equal expected-loss amounts were subtracted.

## Expression tree

JSON scalars are literals. Lists recursively evaluate their elements.
Expressions have one of the following shapes:

```json
{"var": "input.prior"}
{"var": "out.denominator"}
{"var": "item.amount"}
{"var": "item"}
{"var": "index"}
{"op": "mul", "args": [2, {"var": "input.prior"}]}
{"op": "map", "items": {"var": "input.cashflows"}, "value": {"var": "item.amount"}}
{"op": "if", "condition": true, "then": 1, "else": 0}
```

Variable paths resolve only present own keys. They cannot access code, built-in
objects, methods, the filesystem or the network. `item` and zero-based `index`
exist inside `map`. Referencing an output that has not yet been calculated is an
error.

Operators:

| Operator | Inputs | Result |
|---|---|---|
| `add`, `mul` | One or more numbers | Sum or product |
| `sub`, `div`, `pow` | Two numbers | Difference, quotient, power |
| `abs` | One number | Absolute value |
| `min`, `max` | One numeric array, or one or more numbers | Extreme value |
| `sum` | One numeric array | Sequential sum; empty array sums to zero |
| `argmin` | One nonempty numeric array | All minimum indices, preserving ties |
| `eq`, `ne` | Two primitive values | Strict scalar equality or inequality |
| `lt`, `le`, `gt`, `ge` | Two numbers | Boolean comparison |
| `and`, `or` | One or more Booleans | Boolean result |
| `at` | Array and valid nonnegative integer index | Existing element |
| `map` | `items` array expression and `value` expression | Result array |
| `if` | Boolean `condition`, `then`, `else` | Only the selected branch evaluates |

Division by zero, invalid array indices and nonfinite intermediate results
raise errors. There is no `eval` operation. `and` and `or` evaluate their
arguments eagerly; use `if` to guard a potentially invalid branch.

## Evaluation order

1. Resolve `model_id` and require the declared model version.
2. Validate every input field and normalize context.
3. Evaluate constraints against inputs. Each must return Boolean `true`.
4. Evaluate outputs in declaration order, exposing prior outputs under `out`.
5. Return the inputs, results, calculation trace and legal boundaries.

Constraints may refer to `input` and nested array items, never `out`. Each
constraint is `{ "expression": <Boolean tree>, "message": <explanation> }`.
Each output has `id`, `label`, `unit`, human-readable `formula` and executable
`expression`.

## Context and evidence

Default context is:

```json
{
  "jurisdiction": "HK",
  "as_of": null,
  "input_basis": "hypothetical",
  "sources": {},
  "applicability": "unreviewed"
}
```

`as_of` is a valid `YYYY-MM-DD` context tag or `null`. It does **not** ask the
calculator to retrieve or certify the law in force on that date.
`jurisdiction` records the intended jurisdiction; choosing `HK` does not turn
foreign or theoretical material into Hong Kong authority.

`input_basis` may instead be `case_data`. In that mode each top-level input must
have a nonempty source note in `sources`, keyed by the input field ID. For an
array input the source note should identify the underlying schedule and how
each row was derived. Source notes are user statements, not machine-verified
evidence. Unknown source keys are rejected; source notes have a 4,000-character
limit.

`applicability: "externally_assessed"` records an external assessment assertion.
It is never a certificate issued by the engine. No setting changes
`legal_conclusion: null`.

## Request and response

CLI and REST requests require `model_id`, `model_version` and `inputs`.
`context` is optional; when present it must be an object. Unknown request fields
are rejected. The Python library additionally permits omitted/default context
through its normal `None` default.

The response contains:

```text
model_id, model_version, category, output_kind,
analysis_layer, formula_authority,
context, inputs, source_ids, legal_status,
results: { output_id: value },
steps: [{ id, label, unit, formula, value }],
assumptions, limitations, required_legal_findings,
legal_conclusion: null,
applicability_status: context.applicability
```

The input snapshot and ordered trace make the file reproducible against the
same model version. Changing a mathematical definition or its assumptions
requires an explicit model version change and review of both runtimes.

## Commands

Run from the repository root; Python 3.10 or later is required:

```text
python -m legal_quant list
python -m legal_quant show hand
python -m legal_quant example hand --output request.json
python -m legal_quant evaluate --input request.json --output result.json
python -m unittest discover -s legal_quant/tests -v
```

`evaluate --input -` reads a request from standard input. The CLI returns status
`0` on success and `2` on invalid input or a file error. It rejects nonstandard
JSON `NaN`/`Infinity` and duplicate object keys.

REST and quantitative MCP calls also reject duplicate object keys. Their JSON
request size is limited to 128 KiB; the CLI permits up to 2,000,000 characters.
These transport limits are separate from the common model field constraints.
