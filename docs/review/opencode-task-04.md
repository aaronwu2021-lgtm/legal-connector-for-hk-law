# OpenCode task 04: safe builder entry points and isolated reproducibility checks

Execute only after Codex accepts the preceding task and explicitly dispatches this task. Codex directs and independently reviews; OpenCode implements using the selected Muse Spark 1.3 Free model. Read `CLAUDE.md`. Preserve the dirty working tree, accepted API changes, existing tests, audit probe and baseline. No paid fallback, network retrieval, commits, push or deployment.

This task is motivated by an observed failure: `python scripts/build_scored.py --help` actually regenerated the base scored artefacts and removed their subsequently applied weight bands. Codex restored the exact original JSON and MJS blobs. Do not repeat the command against the working repository to reproduce it.

## Scope and invariant

Allowed existing files: `scripts/_paths.py`, `scripts/build_elements.py`, `scripts/build_registry.py`, `scripts/build_scored.py`, `scripts/apply_tiers.py`, `scripts/build_maintenance.py`, `scripts/build_persuasive.py`, `scripts/check_persuasive.py`, and the `build_tasks.py`, `build_reader_checklist.py`, and `validate_tasks.py` entry points in experiments 3 and 4. Add `scripts/check_build.py` and standard-library tests under `scripts/tests/` as needed. The experiment 2 helper is a separate, explicitly deferred batch below.

Do not edit `data/`, generated `server/netlify/functions/_*.mjs`, experiment tasks, matter files, reader checklists, model outputs or verdicts in the working repository. Do not change legal text, authorities, verification levels, dates, case counts, tier assignments, experiment keys or validation exemptions to make a build pass. Source refactoring must preserve those objects and their existing values.

**During implementation and verification, never execute or import any builder from the working repository, including with `--help`. Every execution/import of a target entry point must use an independent temporary copy.** Reading source and parsing it with `ast.parse` is safe; executing its AST, importing it, `runpy.run_path`, or calling it with help is execution. The test runner itself may run from the repository only if all target execution is isolated as specified below.

## Findings from source inspection

The line numbers describe the audited version and may move during refactoring.

| Entry point | Current side effect |
|---|---|
| `build_elements.py:354` | Calls `emit('elements', DATA)` at module scope; also computes and prints summaries on import. |
| `build_registry.py:292` | Emits the untiered registry at module scope. |
| `build_scored.py:124` | Emits the base scored module at module scope; a later `apply_tiers.py` run supplies the published bands. |
| `apply_tiers.py:97-98` | Reads and rewrites both scored and registry at module scope. |
| `build_maintenance.py:5,81,185` | Reads elements/registry/scored and emits maintenance at module scope. |
| `build_persuasive.py:312` | Has a main guard but no argument parser: `--help` still runs the build. |
| `check_persuasive.py` | Reads, validates, prints and may call `sys.exit` at module scope. No output writes, but it is not a quiet importable checker. |
| Experiment 3/4 task and reader builders | Have main guards but no argument parser: `--help` runs writing code or crashes before completion. |
| Experiment 3 validator | Import is already guarded; `main()` treats the first argument as an input filename, including `--help`. |
| Experiment 4 validator | Import is already guarded; arguments are ignored. The current dataset/schema mismatch still causes `KeyError: judgment_file`. This task must not hide that failure. |

Actual dependencies: the core builders and `apply_tiers` import `_paths`; they do not import one another. `build_maintenance` reads the three generated inputs, while `apply_tiers` reads and transforms scored and registry. The persuasive builder reads four local source snapshots under `data/sources/uklr/`, independently of the core sequence. Each reader-checklist builder imports its sibling validator's `match` and `norm`; the experiment 3 reader reads elements plus tasks. The experiment 4 reader also assumes old task fields such as `case`, so it is not compatible with the current arbitration tasks. Keep that failure visible for the experiment repair task.

The sibling validators have the same module name, `validate_tasks`. Do not create new process-wide import ambiguity by running both readers through a shared cached import. Keep CLI execution in separate processes, or use an explicit sibling import identity if a shared process is needed. No consumer may import a builder merely to obtain a helper or constant that would trigger output generation.

## Implementation requirements

1. Add `main(argv=None)` and `if __name__ == '__main__': raise SystemExit(main())` entry points. Parse arguments with `argparse` before any input reads, output creation or build work. `--help` and `-h` return zero and usage text; an unsupported argument returns a nonzero usage error. These paths must not read required datasets just to display usage and must not create files or directories.
2. Move all filesystem reads, output writes, summaries and build invocation out of module scope. Preserve source objects and pure helpers. Imports must be quiet and must work even when generated outputs are absent. A pure `build()` or transformation helper may be introduced, but importing it must not call it. Repeated explicit calls must not accumulate mutations in global source dictionaries or counters; copy source objects where needed.
3. Preserve existing deliberate no-argument build commands. Do not silently redefine `build_scored.py` as a complete final build: it currently produces an intermediate base object. Document that only the complete ordered sequence is checked against published artefacts. Make the non-writing checker below the suggested verification command.
4. Keep all file paths anchored to the copied entry point's location, not the caller's working directory. Retain UTF-8 and LF output behavior already provided by `_paths.emit`. Do not reformat every source file or normalize unrelated generated files. Help and summary printing must work on Windows with bilingual text; tests set UTF-8 explicitly.
5. Validate complete outputs before publishing them. At minimum, serialize both JSON and MJS representations before opening either final path, and avoid truncating a final file if serialization fails. If using temporary sibling files and `os.replace`, state the limitation: two separate replacements are not a transaction across both files. The isolated checker must detect a pair mismatch. Do not claim whole-pipeline atomicity.
6. Do not hide a missing tier by emitting a stage labelled fully tiered. Compute/validate both scored and registry transformations before publishing either; report missing assignments as a nonzero build failure. Do not overwrite a future `regression` weight with a doctrinal tier: preserve it only if its existing representation is supported, otherwise fail explicitly before writing. No current weight values or assignments may be changed in this task.
7. Fix the identified byte-level nondeterminism in `build_persuasive.py`: its `stats.signals` dictionary iterates a set at the audited line 304. Use a stable ordering for that dictionary without changing values or arbitrary case/edge ordering. Do not replace fixed source dates with the current wall clock. Record unexpected reproducibility differences rather than regenerating the working repository to conceal them.
8. Add argument parsing to the experiment 3/4 builders and validators while preserving their current intended inputs and validation rules. Experiment 3's positional tasks-path argument must remain supported. Help must succeed without reading task data. An ordinary experiment 4 validation/build-check failure remains an error with useful context; it is not grounds for weakening the validator or editing the answer keys.
9. Validate verification provenance across every authority occurrence, including manually constructed jurisdiction-overlay case records, not only records created through `build_elements.A()`. Preserve the existing level vocabulary, require a pin for primary/quoted records and an explicit quoting source for quoted records, and report the precise data path for failures. An existing example is the HK overlay's Long Year Development record: it is quoted with a pin and note but no structured source, although another occurrence of the case has a source. Do not silently borrow another occurrence's provenance, add a source, downgrade the level or upgrade verification in this task. Report this as a pre-existing integrity failure requiring a separate source-record review. Counts must state their traversal scope; this occurrence audit alone does not establish that a differently scoped README total is wrong.

## Non-writing ordered build check

Implement `python -B scripts/check_build.py` as a non-writing check of the invoking repository. It must accept `--help` without copying or reading datasets. Its normal execution performs the work only inside a newly created independent temporary fixture, reports differences and returns a meaningful nonzero status for drift or failure. It must never repair, overwrite or copy results back into the source repository.

The fixture must contain copies of the current on-disk inputs, including uncommitted source snapshots needed by the persuasive builder. A `git archive HEAD` alone is insufficient because it omits current work and untracked inputs. Include only the required source/data/experiment paths; exclude `.git`, dependencies, caches and credentials. Do not use symlinks, junctions or hardlinks for fixtures. Reject reparse-point/symlink inputs or copy their ordinary file content under a checked policy; never traverse a link out of the intended input tree.

Before any target execution, resolve the fixture root, target script and expected output directories and assert that all targets are inside the fixture and outside the original repository. Use a new subprocess with `cwd` inside the fixture. Set `PYTHONDONTWRITEBYTECODE=1` or `-B` and `PYTHONUTF8=1`; remove any inherited `PYTHONPATH` that could select modules from the original repository. Import probes must explicitly add only the fixture's relevant script directory, and verify imported target modules' `__file__` paths are inside the fixture. No service or fetching script may be invoked.

Run this core sequence in the fixture, with each command completing successfully before the next:

1. `python -B scripts/build_elements.py`
2. `python -B scripts/build_registry.py`
3. `python -B scripts/build_scored.py`
4. `python -B scripts/apply_tiers.py`
5. `python -B scripts/build_maintenance.py`
6. `python -B scripts/build_persuasive.py`
7. `python -B scripts/check_persuasive.py`

Do not invoke `pull_uklr.py`, `collect_cfa_arb.py`, model runners, judges, local servers or deployment commands. Experiment task/checklist regeneration and validation are a separate check group so the known experiment 4 schema failure does not disguise the status of the core artefact build. If the optional experiment group is requested and fails, report failure; never silently skip it or return all-green.

For each of elements, registry, scored, maintenance and persuasive, verify that `data/<name>.json` equals the data encoded in `server/netlify/functions/_<name>.mjs`. Parse the known `export default <JSON>;` representation as JSON without executing the application handler. Compare the final outputs with the corresponding snapshot of the original repository. Report semantic drift separately from serialization-only drift; either is visible, never automatically accepted. Run the complete sequence a second time and require identical final output bytes.

## Exact offline acceptance tests

Add `scripts/tests/test_build_safety.py` (or an equally small standard-library test module). It must never import a target builder at test-module scope. The following are requirements for the test implementation, not permission to run original target scripts.

- **Fixture isolation:** before launching any child, assert real resolved paths meet the constraints above. Snapshot hashes and path inventories of the original protected outputs before and after the suite and require equality. All output mutation belongs to the fixture. Enable a child-process network-denial guard for the targets so an accidental added fetch fails the test.
- **Help matrix:** for every in-scope builder/checker/validator, launch both `--help` and `-h` in a fresh fixture with generated datasets absent. Require exit 0, nonempty usage text, unchanged file bytes, unchanged output mtimes and no new files/directories. The absence of inputs ensures argument parsing happens before reads. A help command that regenerates identical bytes still fails because the mtime changes.
- **Unknown argument matrix:** launch each target with `--definitely-unsupported-option`; require a usage error, nonzero exit and the same no-write/no-new-path assertions. Do not mistake an attempted open of that string as a successful argument parser.
- **Import matrix:** in separate fresh subprocesses, import each target from its copied path with bytecode generation disabled. Require no output-file reads, writes, stdout, stderr or `SystemExit`. A standard-library audit hook or carefully scoped I/O guard may reject accesses to fixture `data/` and output paths while allowing Python to read source files. Test the readers with their sibling validators available. No original module path may enter `sys.modules` for a target dependency.
- **CWD independence:** in a fixture with required inputs, run a deliberate builder from a separate empty directory using its absolute copied script path. All generated output must land under the fixture, and the unrelated working directory must remain empty. Compare the result with running the same copied script from the fixture root.
- **Ordered final output:** run the complete core sequence, check all JSON/MJS pairs, confirm balancing factors retain their existing bands after tier application, and then rebuild. Final bytes must be identical. Do not compare intermediate scored/registry output with final published data before `apply_tiers`.
- **Hash-seed variation:** repeat the full build in two fresh fixtures using `PYTHONHASHSEED=1` and `PYTHONHASHSEED=2`. Require equal final bytes, especially persuasive `stats.signals`. Compare values and preservation of verification/source/pin fields with the pre-refactor source baseline.
- **Failure behavior:** in fixtures only, simulate a serialization failure, a missing tier and a missing persuasive source snapshot. Require nonzero failure, no false success and no unrelated output replacement. Check that an induced second-output write failure is reported and detectable as a pair inconsistency; do not claim an impossible multi-file transaction guarantee.
- **Validator behavior:** require experiment 3 help to preserve its positional-input contract and ordinary validation outcomes. Require experiment 4 help to succeed, while an ordinary validation against the known incompatible schema remains a visible failure. Do not turn that failure into an expected success of the optional experiment build group.
- **All-occurrence provenance:** use synthetic fixture records to verify that an unpinned primary record and a quoted overlay record without a source are both reported, even when a matching case elsewhere has complete provenance. Apply the same traversal to the rebuilt data and report any pre-existing violation separately from deterministic-build and JSON/MJS-pair results. The check must not repair the data or declare all integrity checks successful when this violation remains.

Once the isolation checks are implemented and reviewed, the only repository-level test command needed is:

```text
python -B -m unittest discover -s scripts/tests -p "test_build_safety.py" -v
```

This command runs the test harness; the harness must route every target builder/import/help/build execution to temporary copies. Report the exact tested entry-point list, original-output hash comparison, pair comparisons, repeat-build result, hash-seed comparison and any pre-existing drift or experiment failure. Leave the working repository's generated data unchanged and stop for Codex review.

## Deferred experiment 2 helper batch

`experiments/exp2-probe/build_probe.py:131-141` is also unsafe: it writes `probe.json` and `probe_questions.json` at module scope, relative to the caller's CWD, without explicit UTF-8. This helper produces the original experiment keys, including superseded keys retained for the research record. Do not regenerate or revise those historical artefacts as part of task 04.

A separately dispatched batch should add its main guard and argument parser, anchor paths to the helper directory and explicitly specify UTF-8/LF. Preserve the original probe definitions and their archival role; do not replace the keys with corrected law. Extend the same isolated help/import/CWD tests and compare original archival payloads in temporary copies. Until that batch is accepted, clearly list this helper as still unsafe; do not describe the entire repository as universally safe to execute with `--help`.
