# Experiment 3 — Hong Kong matter-file evaluation

This folder contains five synthetic matter tasks and 31 criteria. The current
maintenance work has not run a new model experiment or produced validated new
results. Answer keys still require independent source and proposition review.

The intended comparison concerns Hong Kong matter handling and the effect of a
historical cutoff. The two dates applied to the same matter are a paired design
feature, not independent experiments. The stored task definitions are the
review targets; their inclusion here does not certify the legal answer keys.

| Task | Cutoff | Criteria |
|---|---:|---:|
| HKM-01 | 2026-09-06 | 7 |
| HKM-02 | 2026-09-06 | 7 |
| HKM-03 | 2015-12-01 | 6 |
| HKM-04 | 2026-09-06 | 6 |
| HKM-05 | 2026-09-06 | 5 |

`tasks.json`, `matter/` and `reader_checklist.md` are generated artifacts.
`build_tasks.py`, `validate_tasks.py` and `build_reader_checklist.py` retain the
source definitions and review tooling. Execute normal builds only in an
isolated review copy; do not overwrite the historical task/checklist artifacts
while assessing compatibility. A catalogue match or existing verification label
is not independent confirmation of a rubric proposition.

Held-out tasks require `CONNECTOR_INCLUDE_HELDOUT=1` to be selected. Selection,
variant and exact task contents are frozen in the run manifest. For a deliberately
chosen alternate task file/matter directory, `EXP_TASKS` and `EXP_MATTER_DIR`
must be set before building and remain consistent for that run.

## Bound exploratory workflow

Run these commands from this experiment directory. Use a new output directory;
old `runs/` files without a manifest are retained as legacy artifacts and are
refused by the new tools. Do not edit old hashes or attach new metadata to old
answers to make them look current.

The examples use PowerShell. Set the generator ID and family before building;
they must still match when running or blinding. Commands are never stored.
IDs/families are operator declarations, not authenticated provider identities;
unknown model parameters and token counts remain explicitly unrecorded.

```powershell
$env:EXP3_RUNS_DIR = 'runs_review_01'
$env:MODEL_ID = '<actual generator and snapshot>'
$env:MODEL_FAMILY = '<actual generator family>'
python run.py build
```

`build` uses the local API (default `http://localhost:8899/api`, configurable
with `CONNECTOR_API`) and the task's `payload` specification. It freezes the
task snapshot, prompts, local source hashes and captured strict API responses.
It makes no model call. Integer `as_of` years mean December 31; exact ISO dates
are preserved in both the prompt and API request. Unversioned historical rule
text is withheld and gaps remain visible. The resulting intervention therefore
differs from the legacy prompt bundles and must not be mixed with them.

After choosing and authorizing an actual model command:

```powershell
$env:MODEL_CMD = '<command reading a prompt on stdin and writing an answer>'
python run.py run
python run.py blind
python judge.py --runs runs_review_01 --dry
```

`run` reuses an answer only when the prompt, task, model declaration and answer
metadata all agree. `blind` verifies the complete answer set and preserves an
existing valid label order. The private `blind_key.json` contains conditions;
`blind_manifest.json` does not. The judge loads only the latter, the frozen task
snapshot and the blinded answers, then its own bound review artifacts.

```powershell
$env:JUDGE_ID_A = '<actual judge A and snapshot>'
$env:JUDGE_FAMILY_A = '<judge A family>'
$env:JUDGE_CMD_A = '<judge A command>'
$env:JUDGE_ID_B = '<actual judge B and snapshot>'
$env:JUDGE_FAMILY_B = '<judge B family>'
$env:JUDGE_CMD_B = '<judge B command>'
python judge.py --runs runs_review_01
python score.py --runs runs_review_01 --json
python eval_card.py --runs runs_review_01 --output runs_review_01/eval_card_review_01.json
```

The two judge families must differ from each other and from the generator's
family. A single exploratory judge is supported with `JUDGE_CMD`, `JUDGE_ID`
and `JUDGE_FAMILY`; it supplies no independent dual-judge assurance. Every
verdict binds the exact answer, criterion, rubric, blind snapshot, judge prompt
and execution-time model declarations. Changing any of these cannot silently
reuse a file just because its label still exists.

## Reporting boundary

`score.py` reports paired descriptive counts and per-task/variant results.
`SPLIT`, `UNPARSEABLE`, process `ERROR`, and entirely missing verdicts are
separate unresolved states. They do not become `FAIL`. An existing verdict
missing a criterion, a duplicate identity, or a changed hash is rejected.
A complete descriptive report can exit successfully while
`formal_readiness` remains `false`; an incomplete score returns nonzero.

Criteria within one matter and repeated as-of variants are related observations.
No criterion-level significance test, confidence interval treating criteria as
independent samples, posterior comparison, or automatic calibration adjustment
is emitted. Task-all-pass counts are descriptive too. Independent answer-key
review, bound human calibration and approval of a formal analysis protocol
remain separate outstanding requirements.

The evaluation card reads its task path/hash, generator/judge declarations and
execution records from the bound artifacts. It does not reconstruct old model
identities from today's environment variables. Costs use only validated answer
metadata. Reports print JSON by default; `--output NEW_FILE` writes exclusively
and refuses an existing output file.

## Human calibration and invariance

`calibrate.py --runs runs_review_01` accepts only a `human_gold.json` object with
schema `doctrine-human-gold-v1`, the current `blind_manifest_sha256` and
`judging_sha256`, and an `entries` array. Each entry records `label`, `criterion`,
`answer_sha256`, `criterion_sha256`, `human` (`PASS` or `FAIL`), `reader`, and
`reviewed_utc`. An independent person supplies those grades; the tools do not
create or infer them. Legacy arrays with only labels and grades are rejected.
The output describes agreement among supplied, bound, binary pairs; unresolved
judge results are counted separately. It grants no automatic reporting gate.

For an invariance round, use a separate new output directory and
`CONNECTOR_VARIANT=inv`, then build/run/blind/judge that round with the same
frozen task definitions and model declarations. Compare explicitly:

```powershell
python invariance.py runs_review_01 runs_inv_review_01
```

The comparison requires the same selected task/condition/criterion matrix and
an explicit base-versus-invariance variant pairing. It refuses stale or partial
joins. Binary changes are descriptive surface sensitivity; unresolved states
are not counted as flips or failures.

## Offline software checks

From the repository root:

```powershell
python scripts/tests/test_review_results.py
```

These tests use temporary copies, synthetic answers and local callbacks. Passing
them establishes software behavior only; it does not run or validate a formal
legal experiment. Original task files, generated checklists and old run artifacts
are not rewritten by this maintenance workflow.
