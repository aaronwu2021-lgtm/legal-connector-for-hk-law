# Task 05c — bound review and descriptive reporting acceptance

Date: 2026-09-05. Status: offline software acceptance passed; no new model experiment was run and no formal result is claimed.

## Scope and preserved artifacts

The changed implementation is `experiments/review_results.py`, plus the five thin entrypoints `judge.py`, `score.py`, `eval_card.py`, `calibrate.py` and `invariance.py` in each of `experiments/exp3-hk-matter/` and `experiments/exp4-cfa/`. Both experiment READMEs now document the actual CLI and reporting limits. `scripts/tests/test_review_results.py` is a new independent acceptance suite.

All ten old entrypoint files and both old READMEs were copied byte-for-byte before editing to `.git/codex-review/2026-09-05/task05c-before/experiments/<experiment>/`. The shared `run_integrity.py` and run/build/blind implementation belong to task 05b and were not edited by this task. The root README belongs to the root agent and was not edited here.

Existing task JSON, matter files, generated reader checklists, run prompts, answers, verdicts and other generated data were preserved. README changes are intentional documentation changes. The only follow-up outside 05c was restoring Exp4 reader's `match_case` import alias for the existing 04a import contract; it still points to the strict complete-authority matcher and does not restore prefix matching.

## Result identity

- Judge uses the condition-free `blind_manifest.json`, frozen task snapshot and blinded answer files. It does not open `manifest.json`, `blind_key.json`, raw answer paths or prompt files to decide a verdict.
- `judging_manifest.json` fixes the blind/task hashes, prompt version/hash and execution-time judge ID/family declarations. These declarations are explicitly operator-declared.
- Each verdict binds label, task, answer, blinded text, rubric, criterion, judge prompt and judge configuration hashes. It records each individual judge result and checks the combined result against those records.
- Cached files are reused only after all identities and criterion coverage agree. An old label, changed model, extra/missing criterion, changed task/rubric, changed prompt, or changed blinded answer cannot silently acquire a new meaning.
- Scoring additionally joins each private key entry to its exact source manifest entry and validated answer metadata. It rejects duplicate task/condition/variant identities and incomplete selected matrices rather than taking an intersection or overwriting a dictionary entry.
- Evaluation cards read frozen task paths/hashes, model declarations, answer timing and metadata hashes from the run artifacts. Current environment model IDs cannot rewrite historical identity. Relative run-directory environment overrides use the same experiment-directory anchoring as task 05b.

## Report semantics

Reports contain paired descriptive counts and per-task/variant results. Related criteria and repeated as-of variants are not treated as independent observations. Inferential significance, posterior-comparison and automatic calibration-adjustment branches were removed from the reporting path; there is no result selected because its sample size can achieve a threshold.

`SPLIT`, `UNPARSEABLE`, process `ERROR` and wholly missing verdict files have separate unresolved counts. They are not `FAIL` and do not become binary wins/losses. A present verdict missing a criterion is a malformed artifact and is rejected.

Every current report has `formal_readiness: false`. Complete descriptive data do not substitute for independent answer-key review, bound human calibration, authenticated model identity, or approval of a formal analysis protocol.

Calibration accepts only bound `doctrine-human-gold-v1` input, including answer/criterion hashes, judging/blind hashes, reader and actual UTC review date. It reports agreement over supplied valid binary pairs, separately counting unresolved judge results. Legacy label-only lists are refused. The mathematical `kappa` helper remains importable for compatibility but grants no reporting gate and is not emitted as an automatic formal conclusion.

Invariance requires the same frozen task/rubric snapshot, model declarations and exact selected matrix in an explicit base/invariance pairing. It records both rounds' manifest, blind, judging and verdict-set bindings. Only matched binary results contribute to descriptive flips; missing or unresolved outcomes remain separate.

## Offline acceptance

The independent suite was authored by the `scoring_tests` agent and then run again by the implementing agent after the final run-directory compatibility patch:

```text
python scripts/tests/test_review_results.py
Ran 26 tests
OK
```

All helper and entrypoint execution used disposable temporary copies and synthetic run artifacts. Network, model-command and subprocess launch paths were guarded and not invoked. Original experiment artifacts were compared by path/hash during the tests.

The suite covers:

1. Correctly bound judgments, exact-cache reuse, and separate binary/unresolved states.
2. Rehashed stale verdict fields, swapped answer/task identity, changed rubric or prompt/model declarations, duplicate tasks/variants/criteria, deleted criteria, and changed blinded contents.
3. Judge read isolation from conditions and private keys; import, help, unknown-argument and dry-run behavior across all ten wrappers.
4. Evaluation cards ignoring poisoned current environment identity/task settings, plus cost and metadata-hash provenance.
5. Legacy unbound run, gold-label and invariance rejection.
6. Positive calibration: 12 supplied bound labels produce 11 binary pairs, 10 agreements and one excluded split; invalid/duplicate human bindings and invalid review timestamps reject.
7. Positive invariance: 12 matched binary pairs produce four pass-to-fail and four fail-to-pass changes; changed model, wrong variant, selected-task mismatch or missing answer pairs reject. Missing complete verdicts remain unresolved rather than being counted as flips.

The Exp4 compatibility import alias also passed its 21 task-05a tests and the four targeted 04a import/help/short-help/unknown-option checks. These are separate from the 26 result-integrity tests above.

## Remaining limits

Hashes detect content inconsistency, not intentional forgery. Model IDs/families describe what the operator declared at execution; opaque commands do not authenticate a provider or disclose unknown parameters. Human grades remain human-supplied declarations and no legal proposition was independently checked in this task.

No archived unbound experiment output was migrated or rescored. The strict historical connector payload now withholds unversioned rule text; this changes the intervention relative to old prompt bundles. New exploratory runs need fresh directories, and their keys still need independent source/proposition review before formal use.

## Recorded source fingerprints

- `experiments/review_results.py`: `152eb1f7c8f68fc3406ebf7c44e0bbadd27306b6d9d669944fa8885550e17824`
- `scripts/tests/test_review_results.py`: `7a9b496651b904e6f1cf517c019c054b571d00e123ecf3d419b57f26c5e2ca5c`
