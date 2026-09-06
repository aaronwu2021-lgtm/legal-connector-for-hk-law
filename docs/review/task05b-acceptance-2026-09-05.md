# Task 05b acceptance — immutable exploratory run records

Recorded 2026-09-05 23:40 UTC. This is an engineering acceptance record, not a model evaluation or verification of any legal proposition.

## Changes and backup

The two original runners were copied before modification to `.git/codex-review/2026-09-05/task05b-before/`, with a source inventory. The original Exp3 runner SHA-256 was `28a840b10df6b005c5bcfe5517502c675a0465bb1d03c2c124f2cfe25381b3fb`; the original Exp4 runner was `cade5514979ba3407b38e00219534ee36af7a1d3406958878798bbcce87ddd6f`.

This batch adds `experiments/run_integrity.py` and `scripts/tests/test_run_integrity.py`, and replaces only the Exp3 and Exp4 `run.py` implementations with import-safe wrappers. The original system instructions remain unchanged. Their connector explanation now states the actual limitation: dated catalogue metadata is available; historical legal rule text is not modelled.

No original builder, runner, real model, or network API was executed. All target imports and build/run/blind calls used independent temporary copies with synthetic tasks, matter, local API source and data files. API responses and model completions were mocked. The test audit hook rejects network/process events and writes outside the temporary fixture; an explicit negative test confirms the guard. Original protected artefact hashes and modification times were unchanged across the test run.

## Observed verification

Command executed from the repository root:

```text
python -B -X utf8 -m unittest discover -s scripts/tests -p test_run_integrity.py -v
```

Result: **32/32 passed**, 1.821 seconds, exit 0. This includes:

- Import, help, unknown arguments and single-command build/run/blind dispatch through both copied wrappers.
- Current task payload shape (`timelines` and `checklist`), Exp4 module timeline requests, Exp4's dedicated output override and its earlier Exp3 override fallback.
- Year-only cutoffs normalized to December 31; exact-date cutoffs require an exact date for same-year authority records.
- Rejection of missing strict markers, different cutoffs, future records, future citation years, holdings, current rules, unknown prose fields and unversioned notes. Explanations from `historical_limitations` and `resolution` are replaced with fixed local text before appearing in prompts.
- Raw captured API response hashes, request URLs, strict markers and cutoff bindings. Malformed JSON, duplicate JSON keys, nonfinite numbers, invalid UTF-8 and responses over 4 MiB fail closed.
- Model ID/family declarations, unknown opaque parameters, exploratory readiness, and the fact that local source hashes do not attest to the code executed by a remote API or an already-running process.
- Cache rejection after task, matter, local API source, local data, prompt, model identity, variant or API configuration changes. A complete matching cache performs no API/model calls and changes no bytes or modification times.
- Refusal of old directories without manifests, partial answer/metadata pairs, missing answers, extra answers, tampered answers or metadata, incorrect timing, and old unbound verdict directories. No repair, overwrite, deletion or silent migration occurs.
- Changes to a shared matter file between tasks, or to a bound input while the model completion runs, cause rejection before accepting the affected answer.
- Full answer inventory required before blinding; exact answer bytes are preserved, including CRLF. Existing labels remain unchanged. Altered private mappings and blinded content fail validation.
- The judge-safe loader succeeds even when the private run manifest and private key are deliberately made unreadable JSON, demonstrating that it does not parse those files. Its public manifest is checked recursively for treatment-mapping keys.
- Mocked model failure and timeout messages do not disclose `MODEL_CMD` or command stderr, and accept no answer.

The separate 05c reviewer reported its expanded **26/26** temporary-copy tests passing after explicit empty payload inventories and matching parameter declarations were added to its synthetic fixtures. That is a separate suite, not included in the 32 above.

The older 100-file protected baseline was also checked after this batch: **98 unchanged; two intentional documentation differences**, `experiments/exp3-hk-matter/README.md` and `experiments/exp4-cfa/README.md`. The parent confirmed that both are separately backed-up 05c documentation changes. There were no generated data, task, matter, reader/checklist or original run changes. This report does not claim 100/100 baseline identity.

## Command interface

The existing single-step interface remains available for a newly chosen run directory:

```text
python experiments/exp3-hk-matter/run.py build
python experiments/exp3-hk-matter/run.py run
python experiments/exp3-hk-matter/run.py blind

python experiments/exp4-cfa/run.py build
python experiments/exp4-cfa/run.py run
python experiments/exp4-cfa/run.py blind
```

These are interface examples only; none was executed against original repository data during acceptance. `MODEL_ID` and `MODEL_FAMILY` are required before these stages. `MODEL_CMD` is required only when missing answers must actually be generated. Generator identity is explicitly `operator-declared`. Opaque command parameters and tokens are `not-recorded`.

`EXP3_RUNS_DIR` selects Exp3 output. `EXP4_RUNS_DIR` selects Exp4 output, with the earlier `EXP3_RUNS_DIR` fallback retained. `EXP_TASKS`, `EXP_MATTER_DIR`, `CONNECTOR_API`, `CONNECTOR_VARIANT` (`base` or `inv`) and `CONNECTOR_INCLUDE_HELDOUT=1` remain supported. Relative paths resolve from the experiment directory, independently of the caller's working directory.

An existing directory is reused only after its configuration, bound local sources, tasks, prompts and available downstream bindings validate. Otherwise a new output directory is required. Failed publication can leave a detectable incomplete new directory; subsequent commands refuse it rather than inventing missing metadata.

## Shared record and validation contract

- `manifest.json`, schema `doctrine-run-v1`: self hash; task snapshot hash and source path; task IDs; global variant and held-out configuration; generator declaration; readiness; local source hashes; captured API requests; and the exact task/condition/variant entry matrix. Entries bind rubric and prompt hashes plus answer/metadata locations. Raw API responses are saved under `payloads/` with both file and canonical decoded-JSON hashes.
- Each answer metadata file, schema `doctrine-answer-v1`, binds the manifest, entry/task/condition/variant, prompt and answer hashes, generator ID/family, identity basis, parameter declaration, UTC start/end and duration. Answers are accepted only as complete pairs with matching metadata.
- `blind_manifest.json`, schema `doctrine-blind-v1`: self hash, opaque originating manifest hash, task snapshot, generator/readiness declarations, complete answer count, and public labels binding task/rubric/blinded-file/answer hashes. It has no condition, variant, private entry ID or prompt/answer/metadata source paths. Blinded files contain only the task header followed by exact answer bytes.
- `blind_key.json`, schema `doctrine-blind-key-v1`: private one-to-one label mapping to entry/task/condition/variant/answer hash, bound to both manifests. Random labels are assigned once and never reshuffled on reuse.
- `load_manifest(run_dir, verify_current=False)` verifies the run snapshot and payload bindings. `verify_current=True` also checks the current original source paths.
- `validate_answers(run_dir, manifest=None, require_complete=True)` returns dictionaries containing `entry`, `meta` and `answer`, after checking bindings.
- `load_blind_manifest(run_dir)` reads only the public manifest, bound task snapshot and blinded files. It does not read the run manifest or private key.
- `canonical_bytes`, `object_hash`, `sha256_bytes`, `hash_file`, `safe_path` and `IntegrityError` form the remaining shared interface. Canonical JSON uses UTF-8, sorted keys, compact separators and rejects NaN/Infinity.

The 05c judge/score/evaluation-card implementation is a separate batch. This implementation does not edit those tools or interpret their verdicts.

## Limits preserved

All runs produced by this implementation remain **exploratory**, with **formal readiness false**, source verification not performed, independent reader sign-off not recorded and calibration not recorded. Current task sets and keys were not reclassified or legally validated.

The strict connector material is intentionally limited to dated metadata. Missing historical rule text is not replaced by current holdings or editorial summaries. Strict marker/cutoff and schema checks cannot authenticate a remote service; recorded URLs and response hashes support later inspection. Local code hashes describe only the local source snapshot. Model IDs and families are operator declarations, and an opaque model command's actual settings or provider identity cannot be inferred.

Hashes detect inconsistent records, not deliberate coordinated forgery. Filesystem publication is exclusive but is not a multi-file transaction, and there is no distributed lock. An interrupted or competing publication can leave a partial directory that requires a fresh run directory. Existing data is never automatically synchronized.

Withholding treatment metadata does not guarantee that a judge cannot infer treatment from the answer's wording. Answer text is preserved instead of being redacted. All currently public tasks remain public; the held-out flag alone does not create a new independent hidden evaluation set.

## Accepted source hashes

| File | SHA-256 |
| --- | --- |
| `experiments/run_integrity.py` | `56fe3d305296b964d59bb92fd85b8860f0dc6f7d57c0607c3d8f14cccc2bd4d1` |
| `experiments/exp3-hk-matter/run.py` | `d8d5f98dd990a554130503bd1ab6c79bc90aba31ee0d12b0244f97079446b9a4` |
| `experiments/exp4-cfa/run.py` | `9205efc0cc19136c6ea2d25a32976977fbc267fe4e392ca271d0e9d1451b7bf1` |
| `scripts/tests/test_run_integrity.py` | `88fb3420281960292057494d98fac94fe2df507ed0e48173a0a296ad4eb4c321` |
