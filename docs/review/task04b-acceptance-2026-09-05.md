# Task 04b — historical acceptance record

Recorded 2026-09-05 23:00 UTC. This records the actual isolated 04b runs **before the subsequent 05a Experiment 4 readiness changes**. Do not overwrite this baseline when later implementation changes the result; append a separate dated report instead.

## Outcome

**`overall_ok: false`.** The engineering tests passed because they verified repeatability, safe failure and honest reporting. The data integrity check did not pass.

| Check | Observed result |
| --- | --- |
| Entrypoint safety | 61/61 tests passed: original 57 cases retained, plus four for `check_build.py` |
| Build / failure regression tests | 16/16 passed |
| Ordered core build | All seven stages succeeded in each disposable copy |
| JSON/MJS pairs | All five pairs semantically equal; original baseline pairs also equal |
| Tier bands | 77 balancing factors retained complete bands: registry 60, scored 17 |
| Same-copy second build | Final ten output files byte-identical to the first build |
| Fresh copies, `PYTHONHASHSEED=1` and `2` | Final output bytes identical to the first build and each other |
| Core semantic drift | None observed |
| Core serialization drift | Exactly two files: persuasive JSON and MJS; stable `stats.signals` key order |
| Provenance | Three explicit-field deficiencies, present in both baseline and rebuilt data |
| Original repository | Protected path/hash/mtime checks passed; historical 100-file SHA-256 baseline also 100/100 unchanged |

The executed acceptance commands were:

```text
python -B -m unittest discover -s scripts/tests -p "test_builder_entrypoints.py" -v
python -B -m unittest discover -s scripts/tests -p "test_build_reproducibility.py" -v
```

The first build-test run contained 15 passing tests. After adding the CLI failure-status regression and clarifying the experiment output inventory, the final run contained 16 passing tests. The CLI adapter reused the real isolated result and returned **1**, with JSON `overall_ok: false`; this was not treated as successful integrity.

## What changed

- Added `scripts/check_build.py` and `scripts/tests/test_build_reproducibility.py`; extended `scripts/tests/test_builder_entrypoints.py` without removing the original 57 cases.
- `_paths.py` completes both JSON serializations and UTF-8 encodings before opening an output. Non-JSON numeric constants are rejected. Publication still consists of separate writes and is **not a cross-file transaction**.
- `apply_tiers.py` prepares and validates both scored and registry, rejects absent tiers and existing regression weights, then serializes both before publication. The TIERS, T and NOTES source tables were checked unchanged by AST comparison.
- `build_persuasive.py` sorts only the signal keys. Case/edge order and source dates are retained.
- Experiment 2 output paths are anchored to the helper directory, with explicit UTF-8/LF. Its 21 original item definitions were checked unchanged by AST comparison, including historical answer keys.

All actual builders and validators ran in independent temporary copies, including the runs used for fault injection. Copies used current workspace source bytes and local snapshots, independent ordinary files, checked execution/output paths, an empty copied cwd, disabled bytecode/site startup, explicit hash seeds and a scrubbed Python environment. The child audit guard denied networking, subprocess launches and access to the original repository. Target and sibling dependency `__file__` values were checked inside the copy. No builder executed or imported from the original repository. No outputs were copied back.

## Provenance failures retained

The traversal covers **all explicit `verified` occurrences** across the five JSON datasets, including statutes, authority lists, timeline declarations and manual jurisdiction overlays. It does not deduplicate by case identity, infer undeclared verification levels, or borrow evidence from another occurrence. These are structural completeness checks, not findings that a legal proposition is true or that a source was substantively verified.

| Path in elements JSON | Failure |
| --- | --- |
| `$.jurisdictions.HK.statutes[1].pin` | Declares primary but has no explicit pin field; sections/source remain present and were not silently substituted |
| `$.jurisdictions.HK.statutes[2].pin` | Declares primary but has no explicit pin field; sections/source remain present and were not silently substituted |
| `$.jurisdictions.HK.cases[5].source` | Long Year Development declares quoted and has a pin, but lacks its own explicit source/src field; another occurrence's source was not borrowed |

Both baseline and rebuilt provenance reported the same three issues. Traversal counts were elements 58, registry 42, scored 9, maintenance 0 and persuasive 449: **558 explicit occurrences**. Normalized levels were primary 32, quoted 3, web 42 and unverified 481. This scope is not evidence that a differently scoped README count is wrong.

## Output comparison

Elements, registry, scored and maintenance each regenerated their JSON and MJS **byte-for-byte identically** to the original baseline: eight unchanged files.

| File | Original SHA-256 | Rebuilt SHA-256 | Classification |
| --- | --- | --- | --- |
| `data/persuasive.json` | `021331b9e40f2f4a20214dbd3b4b443fe3e57c303b334b45a9393604c9513ac6` | `aae100f0d040f5a6710b60b96c397e36df184e060e666f776a78120a7bb60184` | Serialization only |
| `server/netlify/functions/_persuasive.mjs` | `7af9f30930227758143d2be85b1bacf233b19971b035efff8177ea18f12b93c6` | `977172da44989ff023cf3b3398ec8176303c84058cd3aceebcae6a7219a294f8` | Serialization only |

The original two files remain unchanged. A stable new encoding was not used to reset the baseline automatically.

## Optional experimental groups — observed before 05a

| Group | Actual build/validation result | Comparison |
| --- | --- | --- |
| Experiment 2 | Helper completed in the copy | Both archived JSON files are semantically equal, with serialization differences only |
| Experiment 3 | Task builder, validator and reader builder all succeeded | Tasks, reader checklist and all 15 matter files are byte-identical to baseline |
| Experiment 4 | Task builder succeeded; validator failed; reader builder was not run after failure | Tasks are byte-identical; reader checklist has no regenerated output |

Experiment 2 archive hashes:

| File | Original SHA-256 | Rebuilt SHA-256 |
| --- | --- | --- |
| `probe.json` | `a3f2a1b81fad81df75cca86729189db939cb338788f13c717929c8567c21276b` | `f40d25f46ddba8533b0114bdd4e0d2d05ce088b5346906b218e7cb841a43d105` |
| `probe_questions.json` | `c26fe1f8e27dc579ca4419cc23c15e537860b2b8b0343771b603d9200d4eec9d` | `e8f5c773089b5a5b7158011251ded85a8145b805ed199f6eb845f763a03cc9ec` |

The **original, actually observed** Experiment 4 failure was exit code 1 in `experiments/exp4-cfa/validate_tasks.py`, line 59:

```text
blob = norm_text(open(os.path.join(ROOT, "matter", t["judgment_file"]),
                                                   ~^^^^^^^^^^^^^^^^^
KeyError: 'judgment_file'
```

This was the schema failure before 05a, not a later structured readiness report. Nothing in this record claims the Experiment 4 legal keys were checked, its checklist regenerated, or its evaluation run.

## Failure handling verified

The isolated regression suite confirmed that unserializable objects, NaN and invalid UTF-8 content leave both existing outputs intact; an injected failure in the second serialization also leaves both intact. Missing tiers in the second dataset and regression weight declarations publish neither scored nor registry. Missing persuasive source input stops its group before the checker stage without replacing outputs. A deliberate second publication failure returns nonzero and yields a detectable JSON/MJS mismatch while unrelated outputs stay unchanged: no transactional guarantee is claimed.

Synthetic manual overlays confirmed occurrence-specific missing-source detection, primary missing pins, rejection of empty/note-only source objects and invalid verification declarations. A socket creation attempt was blocked before networking. Executing an original repository builder path was rejected before child launch. An absolute copied Experiment 2 script run from a separate empty cwd produced UTF-8/LF files only beside that copied script.

## Captured build input SHA-256 values

These are the source/input hashes reported by the actual pre-05a run. They identify that run even if later working files change.

```text
data/sources/uklr/llms-cases.txt 996f1ee2b25e7bd3ce4b1ef51ace6b96f1c052b172d8b6f1a9ec5aa97150825a
data/sources/uklr/uklr-official-links.json cd114b959f484694b45317dae27f8201a83ced6e48c01b26b72f407c8e7f0111
data/sources/uklr/uklr-related-links.json b2443444b5b6ae30116f242612444a7741f6546c34d20056500b6afa1bf9a926
data/sources/uklr/uklr-treatment-slim.json 656e89585640446f1d42a3c4ab99c5c8730ab95fd58ce353da00a64bd27b4e56
experiments/exp2-probe/build_probe.py 73a3fdc3ce0fe20d4a3fb0f8fa2b3ef77a0ee08f0c49495795d700a09c2a0550
experiments/exp3-hk-matter/build_reader_checklist.py 5a777b4a0b450c90762dfffbdd63ed7c3f01ca1b81caf919b5de5396e535cafc
experiments/exp3-hk-matter/build_tasks.py 481dc0df3d0628fbffa99b09dbd220420b7508fc3730bc98efb7d7c926de84e9
experiments/exp3-hk-matter/validate_tasks.py 5c1954c8c912b6f8786952f3a5b8eaa5dacddca265683be9b8c9d1bde18d6168
experiments/exp4-cfa/build_reader_checklist.py 282ff48e2ac25cca01c76b9260da5229103a037c0ef44df55ea013f64e5fa0dc
experiments/exp4-cfa/build_tasks.py 0adfddf72bae35cecc6880ac95325bdfd60c113756184f1ca976c8d775713c01
experiments/exp4-cfa/matter/CFA-02-judgment.txt b91bb0228cbd4380695729353a3f521b72f6744c6b617896f1658f26f8630ce9
experiments/exp4-cfa/matter/CFA02-ca-summary.md 23c457e2afb81ac4f7f6ee5940d504cca5414714b82e6ad65742788621d39225
experiments/exp4-cfa/matter/CFA02-chronology.md ceb8ef270a04a23b461531ef65a292696d0aa77edc56e10023f1214c27899879
experiments/exp4-cfa/matter/CFA02-instructions.md bf7c46d99ed9c1437ce1023433557db5b0dbee88629518f34a20fc065a156ea3
experiments/exp4-cfa/matter/CVD-matter.md 1137081ace451f4edc0a266d0c35d22adb14de1d3d2e682414a33014441da308
experiments/exp4-cfa/matter/ETON-matter.md 62f3398ff286c02cb07a3b22dfc72345d4e7f5dc61ab5ce6ee2e45b5f53a371e
experiments/exp4-cfa/validate_tasks.py e996431ab8b92577b79baf72fb99926d79c1340541b31e77134a2b504ff4cc29
scripts/_paths.py 288e1f07e6f7353f631536cfdc65ec422c6c159f99f09a60bc30a07072b33907
scripts/apply_tiers.py 7118e796d7479788c3a268d66bd01691d37c4a0d174ad4933f257cd76abe0a80
scripts/build_elements.py 3c0863b18e3140d951228bf146202238889e926f0234c53fa3bdaf97905aaf91
scripts/build_maintenance.py 4da194e5b4c8cbfee93eb10087e7e56768f39a82424333517a49b4d0ad53af18
scripts/build_persuasive.py 6268278051eefe8f0714e657d69a6e30ff79e064d5dc89c2f1caa1520e2ba144
scripts/build_registry.py 9c87fbee08da1c28572d3bb4a037b860e19d9b72220c02a1cc486f757fff0fcb
scripts/build_scored.py 16f3cd3f650c0c23cdcc6479b74aed391d62ab3b62ebb20086854b0f69f28e7e
scripts/check_persuasive.py eab4a66a8f781d47118b898f8ee13d096ea540b66c186156da07dd8792814d1c
```

The earlier protected baseline remains `.git/codex-review/2026-09-05/task04a-before/protected-hashes.json`; all its 100 recorded hashes were independently rechecked unchanged at the end of this batch.
