# Experiment 4 — CFA arbitration evaluation

This folder contains three tasks and 13 criteria. The current maintenance work
has not run a new model experiment or produced validated new results. The
stored keys have passed local identity/date/phrase checks and remain pending
independent paragraph-level source and proposition review.

| Task | Exact cutoff | Criteria | Requested timeline |
|---|---:|---:|---|
| EXP4-CVD-22 | 2022-12-31 | 3 | ARBCH-12 |
| EXP4-CVD-26 | 2026-09-06 | 5 | ARBCH-12 |
| EXP4-ETON-26 | 2026-09-06 | 5 | NYC-V |

CVD-22 and CVD-26 share a matter file and form an as-of pair. Preserve that
pairing. The task's `payload` controls the connector material; the old local
harness's unrelated LRO/Milmo coverage-gap text is not used.

## Key review status

The current three-task schema records each judgment, determination and cited
version of Cap. 609 separately under `sources`, including its complete title,
citation, court or publisher, procedural/source nature, legal and availability
dates, official URL and local source-check file. Each criterion maps a
source-specific locator and its phrases to an exact citation through
`source_checks`. This prevents a phrase found in one source from mechanically
verifying a different source in the same task. Compiler provenance and local
matches remain declarations and mechanical checks; they do not replace an
independent reader's legal judgment.

The Eton criteria preserve the source layers: [2020] HKCFA 32 is the earlier
merits decision, [2024] HKCFI 1291 is the damages assessment, and [2026] HKCFA
30 is the later Appeal Committee determination that recaps those rulings. For
the 2020 and 2024 records, the judgment date is used as the recorded availability
proxy because the original upload date was not separately established; both
dates are well before the 2026-09-06 task cutoff.

In an isolated copy, the validator reports structure separately from source and
reader readiness:

```powershell
python validate_tasks.py --structure-only --json
python validate_tasks.py --json
python build_reader_checklist.py --output reader_checklist_pending.md
```

For the current data, the first command succeeds structurally; local identity,
date and phrase checks are complete. The second still exits nonzero because
independent proposition review remains pending.
The reader output retains all 13 criteria and leaves every human checkbox and
signature blank. A local phrase match, when source records are supplied, checks
text presence and recorded identity only; it does not establish paragraph-level
legal support. Rebuild the generated `tasks.json` and `reader_checklist.md`
whenever their builders change.

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
$env:EXP4_RUNS_DIR = 'runs_review_01'
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
