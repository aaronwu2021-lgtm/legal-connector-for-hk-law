"""Offline acceptance of copied Exp3/Exp4 judging and descriptive reporting.

Run manifests below are synthetic fixtures. No experiment runner, builder,
external model command, or service is executed by this suite.
"""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import urllib.request


REPO = Path(__file__).resolve().parents[2]
EXPERIMENTS = ("exp3-hk-matter", "exp4-cfa")
ENTRYPOINTS = ("judge.py", "score.py", "eval_card.py", "calibrate.py", "invariance.py")
HELPERS = ("run_integrity.py", "review_results.py")
JUDGES = [
    {"slot": "A", "id": "fixture-judge-a-v1", "family": "fixture-family-a"},
    {"slot": "B", "id": "fixture-judge-b-v1", "family": "fixture-family-b"},
]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def sealed(value, field):
    value = copy.deepcopy(value)
    value.pop(field, None)
    value[field] = sha(canonical(value))
    return value


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def manifest_files(root, include_python=False):
    return {
        path.relative_to(root).as_posix(): sha(path.read_bytes())
        for path in sorted(root.rglob("*")) if path.is_file()
        and "__pycache__" not in path.parts
        and (include_python or path.suffix not in {".py", ".pyc"})
    }


def fixture_document():
    return {"dataset": "synthetic-review-results", "version": "fixture-v1", "tasks": [
        {"id": "SYN-%d" % task, "as_of": 2020,
         "instruction": "Synthetic task %d only." % task, "files": ["matter.md"],
         "payload": {"checklist": False}, "held_out": False,
         "rubric": [{"id": "SYN-%d-%s" % (task, letter),
                     "criterion": "Synthetic criterion %s for task %d." % (letter, task),
                     "authority": "Synthetic Authority [2020] SYN 1", "pin": "[1]",
                     "discriminates_against": "A different synthetic statement.",
                     "drift_sensitive": False}
                    for letter in ("a", "b", "c")]}
        for task in (1, 2)
    ]}


def make_run(root, experiment="exp4-cfa", model=None, variant="base", task_ids=None):
    """Independently serialize the frozen 05b schemas, without invoking run.py."""
    run = root / experiment / ("synthetic-run" if variant == "base" else "synthetic-run-" + variant)
    run.mkdir(parents=True)
    document = fixture_document()
    source = root / "source-tasks.json"
    write_json(source, document)
    write_json(run / "tasks.snapshot.json", document)
    model = {"parameters": {"status": "not-recorded", "reason": "Synthetic fixture has no model invocation."},
             **(model or {"id": "fixture-generator-v1", "family": "fixture-generator-family"}),
             "identity_basis": "operator-declared"}
    readiness = {"run_kind": "exploratory", "formal_ready": False,
                 "independent_review": {"status": "not-recorded", "reader": None, "date": None},
                 "calibration": {"status": "not-recorded"}}
    entries = []
    selected_ids = task_ids if task_ids is not None else [task["id"] for task in document["tasks"]]
    for task in document["tasks"]:
        if task["id"] not in selected_ids:
            continue
        for condition in ("bare", "conn"):
            entry_id = task["id"] + "." + condition + "." + variant
            prompt_file = entry_id + ".prompt.txt"
            prompt = ("Synthetic prompt for " + entry_id + "\n").encode("utf-8")
            (run / prompt_file).write_bytes(prompt)
            entries.append({"entry_id": entry_id, "task_id": task["id"], "condition": condition,
                            "variant": variant, "as_of": "2020-12-31",
                            "rubric_sha256": sha(canonical(task["rubric"])),
                            "payload_request_ids": [],
                            "prompt_file": prompt_file, "prompt_sha256": sha(prompt),
                            "answer_file": entry_id + ".answer.md", "meta_file": entry_id + ".meta.json"})
    manifest = sealed({"schema_version": "doctrine-run-v1", "experiment": experiment,
                       "created_utc": "2026-09-05T00:00:00+00:00", "tasks_file": "tasks.snapshot.json",
                       "tasks_sha256": sha((run / "tasks.snapshot.json").read_bytes()),
                       "model": model, "readiness": readiness,
                       "task_ids": selected_ids, "variant": variant,
                       "inputs": [{"source_path": str(source), "sha256": sha(source.read_bytes())}],
                       "payload_requests": [],
                       "entries": entries}, "manifest_sha256")
    write_json(run / "manifest.json", manifest)
    blind_entries, key_entries = [], {}
    (run / "blinded").mkdir()
    for index, entry in enumerate(entries):
        answer = "Synthetic answer number %d for %s.\n" % (index, entry["task_id"])
        if variant == "inv":
            answer = "Alternative synthetic answer number %d for %s.\n" % (index, entry["task_id"])
        answer_hash = sha(answer.encode("utf-8"))
        (run / entry["answer_file"]).write_text(answer, encoding="utf-8", newline="\n")
        meta = {"schema_version": "doctrine-answer-v1", "manifest_sha256": manifest["manifest_sha256"],
                **{key: entry[key] for key in ("entry_id", "task_id", "condition", "variant", "prompt_sha256")},
                "answer_sha256": answer_hash, "model_id": model["id"], "model_family": model["family"],
                "identity_basis": "operator-declared",
                "parameters": copy.deepcopy(model["parameters"]),
                "started_utc": "2026-09-05T00:00:00+00:00", "ended_utc": "2026-09-05T00:00:01+00:00", "duration_s": 1.0}
        write_json(run / entry["meta_file"], meta)
        label = "OUT%02d" % index
        blinded_file = "blinded/" + label + ".md"
        body = ("<!-- task:%s -->\n" % entry["task_id"] + answer).encode("utf-8")
        (run / blinded_file).write_bytes(body)
        blind_entries.append({"label": label, "task_id": entry["task_id"], "rubric_sha256": entry["rubric_sha256"],
                              "blinded_file": blinded_file, "blinded_sha256": sha(body), "answer_sha256": answer_hash})
        key_entries[label] = {key: entry[key] for key in ("entry_id", "task_id", "condition", "variant")}
        key_entries[label]["answer_sha256"] = answer_hash
    blind = sealed({"schema_version": "doctrine-blind-v1", "manifest_sha256": manifest["manifest_sha256"],
                    "tasks_file": "tasks.snapshot.json", "tasks_sha256": manifest["tasks_sha256"],
                    "model": model, "readiness": readiness, "expected_answer_count": len(blind_entries),
                    "entries": blind_entries}, "blind_manifest_sha256")
    write_json(run / "blind_manifest.json", blind)
    write_json(run / "blind_key.json", {"schema_version": "doctrine-blind-key-v1",
               "manifest_sha256": manifest["manifest_sha256"], "blind_manifest_sha256": blind["blind_manifest_sha256"],
               "entries": key_entries})
    return run


def make_human_gold(run, overrides=None):
    """Create human labels against recorded answer and criterion identities."""
    blind = read_json(run / "blind_manifest.json")
    judging = read_json(run / "judging_manifest.json")
    tasks = {task["id"]: task for task in read_json(run / "tasks.snapshot.json")["tasks"]}
    entries = []
    for entry in blind["entries"]:
        for criterion in tasks[entry["task_id"]]["rubric"]:
            entries.append({"label": entry["label"], "criterion": criterion["id"],
                            "answer_sha256": entry["answer_sha256"], "criterion_sha256": sha(canonical(criterion)),
                            "human": (overrides or {}).get((entry["label"], criterion["id"]), "PASS"),
                            "reader": "Synthetic independent reader", "reviewed_utc": "2026-09-05T00:00:02+00:00"})
    gold = {"schema_version": "doctrine-human-gold-v1", "blind_manifest_sha256": blind["blind_manifest_sha256"],
            "judging_sha256": judging["judging_sha256"], "entries": entries}
    write_json(run / "human_gold.json", gold)
    return gold


class ReviewResultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protected = {name: manifest_files(REPO / "experiments" / name) for name in EXPERIMENTS}
        paths = ["experiments/" + name for name in HELPERS]
        paths += ["experiments/" + group + "/" + name for group in EXPERIMENTS for name in ENTRYPOINTS]
        cls.sources = {relative: (REPO / relative).read_bytes() for relative in paths}

    @classmethod
    def tearDownClass(cls):
        actual = {name: manifest_files(REPO / "experiments" / name) for name in EXPERIMENTS}
        if actual != cls.protected:
            raise AssertionError("original experiment artefacts changed")

    @contextlib.contextmanager
    def copied(self):
        module_names = ["run_integrity", "review_results"]
        old_modules = {name: sys.modules.get(name) for name in module_names}
        old_path, old_bytecode = sys.path[:], sys.dont_write_bytecode
        try:
            with tempfile.TemporaryDirectory(prefix="review-results-test-") as directory:
                root = Path(directory).resolve()
                self.assertFalse(root.is_relative_to(REPO))
                for relative, blob in self.sources.items():
                    target = root / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(blob)
                sys.path.insert(0, str(root / "experiments"))
                sys.dont_write_bytecode = True
                with contextlib.ExitStack() as stack:
                    guards = [stack.enter_context(mock.patch(name, side_effect=AssertionError("No external execution/network: " + name)))
                              for name in ("socket.socket", "socket.create_connection", "urllib.request.urlopen", "subprocess.run", "subprocess.Popen", "os.system")]
                    before = manifest_files(root, True)
                    directories = {path.relative_to(root) for path in root.rglob("*") if path.is_dir()}
                    stdout, stderr = io.StringIO(), io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        loaded = {}
                        for name in module_names:
                            path = root / "experiments" / (name + ".py")
                            spec = importlib.util.spec_from_file_location(name, path)
                            module = importlib.util.module_from_spec(spec)
                            sys.modules[name] = module
                            spec.loader.exec_module(module)
                            loaded[name] = module
                    self.assertEqual(stdout.getvalue() + stderr.getvalue(), "")
                    self.assertEqual(manifest_files(root, True), before)
                    self.assertEqual({path.relative_to(root) for path in root.rglob("*") if path.is_dir()}, directories)
                    yield root, loaded["review_results"], loaded["run_integrity"]
                    self.assertTrue(all(not guard.called for guard in guards), "no attempted external call may be swallowed")
        finally:
            sys.path[:] = old_path
            sys.dont_write_bytecode = old_bytecode
            for name, value in old_modules.items():
                if value is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value

    @staticmethod
    def all_pass(prompt, judge):
        return json.dumps({"verdict": "PASS", "reason": "Synthetic local judgment only."})

    def populate(self, results, run, complete=None):
        calls = []
        callback = complete or self.all_pass
        def complete_tracked(prompt, judge):
            calls.append((prompt, copy.deepcopy(judge)))
            return callback(prompt, judge)
        results.judge_run(run, judges=copy.deepcopy(JUDGES), complete=complete_tracked)
        expected_criteria = 3 * len(read_json(run / "blind_manifest.json")["entries"])
        self.assertEqual(len(calls), 2 * expected_criteria, "two judges independently check every selected fixture criterion")
        return calls

    def assert_no_inference(self, value):
        forbidden = {"p_value", "pvalue", "mcnemar", "mcnemar_p", "mid_p", "ppi", "ppi_rectified", "posterior", "primary_result"}
        if isinstance(value, dict):
            for key, child in value.items():
                self.assertNotIn(key.lower(), forbidden)
                self.assert_no_inference(child)
        elif isinstance(value, list):
            for child in value:
                self.assert_no_inference(child)

    @staticmethod
    def mutate_json(path, mutate, self_hash=None):
        value = read_json(path)
        mutate(value)
        write_json(path, sealed(value, self_hash) if self_hash else value)

    @staticmethod
    def cli(module, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                status = module.main(args)
            except SystemExit as error:
                status = error.code
        return 0 if status is None else status, stdout.getvalue(), stderr.getvalue()

    def load_entrypoint(self, root, group, name):
        path = root / "experiments" / group / (name + ".py")
        spec = importlib.util.spec_from_file_location("copied_" + group.replace("-", "_") + "_" + name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(Path(module.__file__).resolve(), path)
        return module

    def test_complete_binary_data_remains_descriptive_and_not_formally_ready(self):
        with self.copied() as (root, results, _integrity):
            run = make_run(root)
            self.populate(results, run)
            report = results.score_run(run)
            self.assertEqual(report["status"], "complete", report)
            self.assertIs(report["formal_readiness"], False)
            for condition in ("bare", "conn"):
                self.assertEqual(report["counts_by_condition"][condition]["PASS"], 6)
                self.assertEqual(report["counts_by_condition"][condition]["FAIL"], 0)
                costs = report["costs_by_condition"][condition]
                self.assertEqual(costs["answers"], 2)
                self.assertEqual(costs["duration_s"], 2.0)
                indexes = (0, 2) if condition == "bare" else (1, 3)
                self.assertEqual(costs["answer_chars"],
                                 sum(len("Synthetic answer number %d for SYN-%d.\n" % (index, index // 2 + 1)) for index in indexes))
            self.assertEqual(len(report["execution_records"]), 4)
            for record in report["execution_records"]:
                self.assertEqual(record["duration_s"], 1.0)
                self.assertEqual(record["model_id"], "fixture-generator-v1")
                self.assertEqual(record["meta_sha256"], sha((run / record["meta_file"]).read_bytes()))
            self.assertEqual(sum(report["unresolved_counts"].values()), 0)
            self.assertEqual(report["paired_counts"]["both_pass"], 6)
            self.assertEqual(len(report["task_results"]), 2)
            self.assert_no_inference(report)

    def test_fully_bound_verdict_cache_reuses_only_matching_records(self):
        with self.copied() as (root, results, _integrity):
            run = make_run(root)
            self.populate(results, run)
            before = manifest_files(run)
            results.judge_run(run, judges=copy.deepcopy(JUDGES), complete=lambda *_: self.fail("matching cache unexpectedly called judge"))
            self.assertEqual(manifest_files(run), before)

    def test_rehashed_wrong_verdict_bindings_are_rejected(self):
        fields = ("label", "task_id", "rubric_sha256", "blinded_sha256", "answer_sha256",
                  "blind_manifest_sha256", "judging_sha256", "judge_prompt_sha256")
        for field in fields:
            with self.subTest(field=field), self.copied() as (root, results, integrity):
                run = make_run(root)
                self.populate(results, run)
                path = run / "verdicts" / "OUT00.json"
                self.mutate_json(path, lambda record: record.__setitem__(field, "wrong-binding"), "verdict_sha256")
                with self.assertRaises(integrity.IntegrityError):
                    results.score_run(run)

    def test_missing_duplicate_extra_or_rehashed_changed_criterion_is_rejected(self):
        changes = [
            lambda record: record["verdicts"].pop(),
            lambda record: record["verdicts"].append(copy.deepcopy(record["verdicts"][0])),
            lambda record: record["verdicts"][0].__setitem__("criterion", "OTHER-CRITERION"),
            lambda record: record["verdicts"][0].__setitem__("criterion_sha256", "0" * 64),
        ]
        for change in changes:
            with self.subTest(change=change), self.copied() as (root, results, integrity):
                run = make_run(root)
                self.populate(results, run)
                self.mutate_json(run / "verdicts" / "OUT00.json", change, "verdict_sha256")
                with self.assertRaises(integrity.IntegrityError):
                    results.score_run(run)

    def test_changed_judge_configuration_cannot_reuse_previous_verdicts(self):
        for field, value in (("id", "different-judge-version"), ("family", "different-judge-family")):
            with self.subTest(field=field), self.copied() as (root, results, integrity):
                run = make_run(root)
                self.populate(results, run)
                changed = copy.deepcopy(JUDGES)
                changed[0][field] = value
                before = manifest_files(run)
                with self.assertRaises(integrity.IntegrityError):
                    results.judge_run(run, judges=changed, complete=lambda *_: self.fail("stale cache invoked judge"))
                self.assertEqual(manifest_files(run), before)

    def test_changed_rubric_blinded_answer_or_run_model_is_refused(self):
        for change in ("rubric", "answer", "model"):
            with self.subTest(change=change), self.copied() as (root, results, integrity):
                run = make_run(root)
                self.populate(results, run)
                if change == "rubric":
                    self.mutate_json(run / "tasks.snapshot.json", lambda document: document["tasks"][0]["rubric"][0].__setitem__("criterion", "Changed wording with the same id."))
                elif change == "answer":
                    with (run / "blinded" / "OUT00.md").open("a", encoding="utf-8") as stream:
                        stream.write("Changed answer after judgment.\n")
                else:
                    self.mutate_json(run / "manifest.json", lambda manifest: manifest["model"].__setitem__("id", "changed-generator"), "manifest_sha256")
                with self.assertRaises(integrity.IntegrityError):
                    results.score_run(run)

    def test_a_changed_prompt_template_cannot_reuse_cached_judgments(self):
        with self.copied() as (root, results, integrity):
            run = make_run(root)
            self.populate(results, run)
            before = manifest_files(run)
            with mock.patch.object(results, "PROMPT_HASH", sha(b"Changed synthetic judge prompt.")):
                with self.assertRaises(integrity.IntegrityError):
                    results.judge_run(run, judges=copy.deepcopy(JUDGES),
                                      complete=lambda *_: self.fail("changed prompt invoked judge"))
                with self.assertRaises(integrity.IntegrityError):
                    results.score_run(run)
            self.assertEqual(manifest_files(run), before)

    def test_duplicate_tasks_in_an_internally_hashed_snapshot_are_refused(self):
        with self.copied() as (root, results, integrity):
            run = make_run(root)
            self.mutate_json(run / "tasks.snapshot.json",
                             lambda document: document["tasks"].append(copy.deepcopy(document["tasks"][0])))
            self.mutate_json(run / "blind_manifest.json",
                             lambda manifest: manifest.__setitem__("tasks_sha256", sha((run / "tasks.snapshot.json").read_bytes())),
                             "blind_manifest_sha256")
            before = manifest_files(run)
            with self.assertRaises(integrity.IntegrityError):
                results.judge_run(run, dry=True)
            self.assertEqual(manifest_files(run), before)

    def test_duplicate_task_condition_variant_in_key_is_refused(self):
        with self.copied() as (root, results, integrity):
            run = make_run(root)
            self.populate(results, run)
            self.mutate_json(run / "blind_key.json", lambda key: key["entries"].__setitem__("OUT01", copy.deepcopy(key["entries"]["OUT00"])))
            with self.assertRaises(integrity.IntegrityError):
                results.score_run(run)

    def test_an_old_unbound_verdict_is_not_silently_accepted(self):
        with self.copied() as (root, results, integrity):
            run = make_run(root)
            self.populate(results, run)
            write_json(run / "verdicts" / "OUT00.json", {"label": "OUT00", "task": "SYN-1", "judges": ["A", "B"],
                       "prompt_version": "v1", "verdicts": [{"criterion": "SYN-1-a", "verdict": "PASS"}]})
            with self.assertRaises(integrity.IntegrityError):
                results.score_run(run)

    def test_a_missing_whole_verdict_is_missing_not_a_failure(self):
        with self.copied() as (root, results, _integrity):
            run = make_run(root)
            self.populate(results, run)
            (run / "verdicts" / "OUT00.json").unlink()
            report = results.score_run(run)
            self.assertEqual(report["status"], "incomplete", report)
            self.assertEqual(report["unresolved_counts"]["MISSING"], 3)
            self.assertEqual(report["counts_by_condition"]["bare"]["MISSING"], 3)
            self.assertEqual(report["counts_by_condition"]["bare"]["FAIL"], 0)
            self.assertIs(report["formal_readiness"], False)

    def test_split_unparseable_and_error_are_separate_from_fail(self):
        for outcome in ("SPLIT", "UNPARSEABLE", "ERROR"):
            with self.subTest(outcome=outcome), self.copied() as (root, results, _integrity):
                run = make_run(root)
                def response(prompt, judge):
                    if judge["slot"] == "A":
                        return self.all_pass(prompt, judge)
                    if outcome == "ERROR":
                        raise RuntimeError("Synthetic callback failure.")
                    if outcome == "UNPARSEABLE":
                        return "No JSON object in this synthetic response."
                    return json.dumps({"verdict": "FAIL", "reason": "Synthetic disagreement."})
                self.populate(results, run, response)
                report = results.score_run(run)
                self.assertEqual(report["status"], "incomplete", report)
                self.assertEqual(report["unresolved_counts"][outcome], 12)
                for condition in ("bare", "conn"):
                    self.assertEqual(report["counts_by_condition"][condition][outcome], 6)
                    self.assertEqual(report["counts_by_condition"][condition]["FAIL"], 0)
                self.assert_no_inference(report)

    def test_old_runs_without_manifest_are_refused(self):
        with self.copied() as (root, results, integrity):
            run = root / "old-run"
            (run / "blinded").mkdir(parents=True)
            (run / "blinded" / "OUT00.md").write_text("<!-- task:SYN-1 -->\nOld answer", encoding="utf-8")
            write_json(run / "blind_key.json", {"OUT00": {"task": "SYN-1", "condition": "bare"}})
            for function in (results.score_run, results.evaluation_card):
                with self.assertRaises(integrity.IntegrityError):
                    function(run)
            with self.assertRaises(integrity.IntegrityError):
                results.judge_run(run, dry=True)

    def test_legacy_list_shaped_human_gold_cannot_create_a_calibration_result(self):
        with self.copied() as (root, results, integrity):
            run = make_run(root)
            self.populate(results, run)
            write_json(run / "human_gold.json", [{"label": "OUT00", "criterion": "SYN-1-a", "human": "PASS"}])
            before = manifest_files(root, True)
            with self.assertRaises(integrity.IntegrityError):
                results.calibration_run(run)
            self.assertEqual(manifest_files(root, True), before)

    def test_bound_calibration_reports_binary_agreement_and_excludes_split(self):
        with self.copied() as (root, results, _integrity):
            run = make_run(root)
            def response(prompt, judge):
                split = (judge["slot"] == "B" and "Synthetic criterion c for task 1." in prompt
                         and "Synthetic answer number 0 for SYN-1." in prompt)
                return json.dumps({"verdict": "FAIL" if split else "PASS", "reason": "Synthetic calibration response."})
            self.populate(results, run, response)
            make_human_gold(run, {("OUT00", "SYN-1-b"): "FAIL"})
            before = manifest_files(root, True)
            report = results.calibration_run(run)
            self.assertEqual(report["binary_pairs"], 11)
            self.assertEqual(report["matching_binary_pairs"], 10)
            self.assertEqual(report["unresolved_pairs"], 1)
            self.assertAlmostEqual(report["raw_agreement"], 10 / 11)
            self.assertEqual(report["human_gold_sha256"], sha((run / "human_gold.json").read_bytes()))
            self.assertIs(report["formal_readiness"], False)
            self.assert_no_inference(report)
            for group in EXPERIMENTS:
                module = self.load_entrypoint(root, group, "calibrate")
                status, stdout, stderr = self.cli(module, ["--runs", str(run), "--json"])
                self.assertEqual(status, 0, stdout + stderr)
                self.assertEqual(json.loads(stdout), report)
            self.assertEqual(manifest_files(root, True), before)

    def test_bound_human_gold_rejects_duplicate_or_changed_identity_and_invalid_review_dates(self):
        changes = {
            "duplicate": lambda gold: gold["entries"].append(copy.deepcopy(gold["entries"][0])),
            "unknown-label": lambda gold: gold["entries"][0].__setitem__("label", "OUT999"),
            "wrong-answer": lambda gold: gold["entries"][0].__setitem__("answer_sha256", "0" * 64),
            "changed-criterion": lambda gold: gold["entries"][0].__setitem__("criterion_sha256", "0" * 64),
            "missing-reader": lambda gold: gold["entries"][0].__setitem__("reader", " "),
            "malformed-date": lambda gold: gold["entries"][0].__setitem__("reviewed_utc", "not-a-date"),
            "naive-date": lambda gold: gold["entries"][0].__setitem__("reviewed_utc", "2026-09-05T00:00:02"),
            "non-utc-date": lambda gold: gold["entries"][0].__setitem__("reviewed_utc", "2026-09-05T00:00:02+01:00"),
        }
        for label, change in changes.items():
            with self.subTest(change=label), self.copied() as (root, results, integrity):
                run = make_run(root)
                self.populate(results, run)
                make_human_gold(run)
                self.mutate_json(run / "human_gold.json", change)
                before = manifest_files(root, True)
                with self.assertRaises(integrity.IntegrityError):
                    results.calibration_run(run)
                self.assertEqual(manifest_files(root, True), before)

    def test_bound_base_and_invariance_rounds_report_descriptive_flips(self):
        with self.copied() as (root, results, _integrity):
            base, variant = make_run(root), make_run(root, variant="inv")
            def response(prompt, judge):
                alternative = "Alternative synthetic answer" in prompt
                state = "PASS"
                if "Synthetic criterion a" in prompt:
                    state = "FAIL" if alternative else "PASS"
                elif "Synthetic criterion b" in prompt:
                    state = "PASS" if alternative else "FAIL"
                return json.dumps({"verdict": state, "reason": "Synthetic variant response."})
            self.populate(results, base, response)
            self.populate(results, variant, response)
            before = manifest_files(root, True)
            report = results.invariance_run(base, variant)
            self.assertEqual(report["matched_binary_pairs"], 12)
            self.assertEqual(report["unresolved_pairs"], 0)
            self.assertEqual(report["pass_to_fail"], 4)
            self.assertEqual(report["fail_to_pass"], 4)
            self.assertIs(report["formal_readiness"], False)
            self.assert_no_inference(report)
            self.assertEqual(report["base_manifest_sha256"], read_json(base / "manifest.json")["manifest_sha256"])
            self.assertEqual(report["variant_manifest_sha256"], read_json(variant / "manifest.json")["manifest_sha256"])
            for group in EXPERIMENTS:
                module = self.load_entrypoint(root, group, "invariance")
                status, stdout, stderr = self.cli(module, [str(base), str(variant), "--json"])
                self.assertEqual(status, 0, stdout + stderr)
                self.assertEqual(json.loads(stdout), report)
            self.assertEqual(manifest_files(root, True), before)

    def test_invariance_excludes_missing_verdicts_from_binary_flips(self):
        with self.copied() as (root, results, _integrity):
            base, variant = make_run(root), make_run(root, variant="inv")
            self.populate(results, base)
            self.populate(results, variant, lambda *_: json.dumps({"verdict": "FAIL", "reason": "Synthetic difference."}))
            (variant / "verdicts" / "OUT00.json").unlink()
            report = results.invariance_run(base, variant)
            self.assertEqual(report["matched_binary_pairs"], 9)
            self.assertEqual(report["unresolved_pairs"], 3)
            self.assertEqual(report["pass_to_fail"], 9)
            self.assertEqual(report["fail_to_pass"], 0)
            self.assertIs(report["formal_readiness"], False)

    def test_invariance_refuses_different_selected_tasks_missing_answers_models_or_wrong_variant(self):
        for mismatch in ("selected-tasks", "missing-answer", "model", "wrong-variant"):
            with self.subTest(mismatch=mismatch), self.copied() as (root, results, integrity):
                base = make_run(root)
                self.populate(results, base)
                if mismatch == "wrong-variant":
                    variant = base
                else:
                    kwargs = {"variant": "inv"}
                    if mismatch == "selected-tasks":
                        kwargs["task_ids"] = ["SYN-1"]
                    elif mismatch == "model":
                        kwargs["model"] = {"id": "different-generator", "family": "different-generator-family"}
                    variant = make_run(root, **kwargs)
                    self.populate(results, variant)
                    if mismatch == "missing-answer":
                        entry = read_json(variant / "manifest.json")["entries"][-1]
                        (variant / entry["answer_file"]).unlink()
                        (variant / entry["meta_file"]).unlink()
                before = manifest_files(root, True)
                with self.assertRaises(integrity.IntegrityError):
                    results.invariance_run(base, variant)
                self.assertEqual(manifest_files(root, True), before)

    def test_legacy_unbound_invariance_rounds_are_refused(self):
        with self.copied() as (root, results, integrity):
            base, variant = root / "old-base", root / "old-inv"
            for directory in (base, variant):
                (directory / "verdicts").mkdir(parents=True)
                write_json(directory / "blind_key.json", {"OUT00": {"task": "SYN-1", "condition": "bare"}})
                write_json(directory / "verdicts" / "OUT00.json",
                           {"label": "OUT00", "verdicts": [{"criterion": "SYN-1-a", "verdict": "PASS"}]})
            before = manifest_files(root, True)
            with self.assertRaises(integrity.IntegrityError):
                results.invariance_run(base, variant)
            self.assertEqual(manifest_files(root, True), before)

    def test_judge_reads_no_condition_key_or_unblinded_source_files(self):
        with self.copied() as (root, results, _integrity):
            run = make_run(root)
            original_open = open
            reads = []
            def tracked_open(file, mode="r", *args, **kwargs):
                if isinstance(file, (str, bytes, os.PathLike)):
                    path = Path(os.fsdecode(file)).resolve()
                    if "r" in mode or "+" in mode:
                        reads.append(path)
                        self.assertNotIn(path.name, ("manifest.json", "blind_key.json"))
                        self.assertFalse(path.name.endswith((".answer.md", ".meta.json", ".prompt.txt")), path)
                return original_open(file, mode, *args, **kwargs)
            with mock.patch("builtins.open", tracked_open), mock.patch("io.open", tracked_open):
                calls = self.populate(results, run)
            self.assertTrue(reads)
            for prompt, judge in calls:
                self.assertNotIn("CONDITION", prompt.upper())
                self.assertNotIn("bare", prompt.lower())
                self.assertNotIn("conn", prompt.lower())
                self.assertNotIn("command", judge)

    def test_dry_run_without_judges_creates_no_directories_or_records(self):
        with self.copied() as (root, results, _integrity):
            run = make_run(root)
            before = manifest_files(root, True)
            directories = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_dir())
            results.judge_run(run, dry=True)
            self.assertEqual(manifest_files(root, True), before)
            self.assertEqual(sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_dir()), directories)

    def test_eval_card_uses_manifest_models_and_task_snapshot_ignoring_environment(self):
        with self.copied() as (root, results, _integrity):
            run = make_run(root)
            self.populate(results, run)
            expected = results.evaluation_card(run)
            environment = {"MODEL_ID": "POISONED-ENV-GENERATOR", "JUDGE_ID_A": "POISONED-ENV-JUDGE-A",
                           "JUDGE_ID_B": "POISONED-ENV-JUDGE-B", "EXP_TASKS": str(root / "does-not-exist.json"),
                           "MODEL_CMD": "SECRET-COMMAND-MUST-NOT-APPEAR", "JUDGE_CMD_A": "ANOTHER-SECRET-COMMAND"}
            with mock.patch.dict(os.environ, environment):
                actual = results.evaluation_card(run)
            for field in ("models", "dataset"):
                self.assertEqual(actual[field], expected[field])
            text = json.dumps(actual)
            for value in environment.values():
                self.assertNotIn(value, text)
            self.assertIn("fixture-generator-v1", text)
            self.assertIn("fixture-judge-a-v1", text)
            self.assertIn("synthetic-review-results", text)
            self.assertIs(actual["formal_readiness"], False)
            self.assert_no_inference(actual)

    def test_unrecorded_generator_identity_cannot_be_filled_from_current_environment(self):
        with self.copied() as (root, results, integrity):
            run = make_run(root, model={"id": "UNRECORDED", "family": "UNRECORDED"})
            with mock.patch.dict(os.environ, {"MODEL_ID": "POISONED-LATE-MODEL"}):
                try:
                    card = results.evaluation_card(run)
                except integrity.IntegrityError:
                    return
            self.assertIs(card["formal_readiness"], False)
            self.assertNotIn("POISONED-LATE-MODEL", json.dumps(card))

    def test_all_ten_entrypoints_import_help_and_unknown_flags_are_side_effect_free(self):
        with self.copied() as (root, _results, _integrity):
            before = manifest_files(root, True)
            directories = {path.relative_to(root) for path in root.rglob("*") if path.is_dir()}
            for group in EXPERIMENTS:
                for filename in ENTRYPOINTS:
                    name = Path(filename).stem
                    with self.subTest(group=group, name=name):
                        stdout, stderr = io.StringIO(), io.StringIO()
                        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                            module = self.load_entrypoint(root, group, name)
                        self.assertEqual(stdout.getvalue() + stderr.getvalue(), "")
                        status, stdout, _ = self.cli(module, ["--help"])
                        self.assertEqual(status, 0)
                        self.assertIn("usage:", stdout.lower())
                        status, _, _ = self.cli(module, ["--unknown-offline-test-flag"])
                        self.assertNotEqual(status, 0)
            self.assertEqual(manifest_files(root, True), before)
            self.assertEqual({path.relative_to(root) for path in root.rglob("*") if path.is_dir()}, directories)

    def test_copied_cli_dry_score_and_card_keep_outputs_explicit_and_descriptive(self):
        with self.copied() as (root, results, _integrity):
            for group in EXPERIMENTS:
                run = make_run(root, experiment=group)
                judge = self.load_entrypoint(root, group, "judge")
                before = manifest_files(root, True)
                status, stdout, stderr = self.cli(judge, ["--runs", str(run), "--dry"])
                self.assertEqual(status, 0, stdout + stderr)
                self.assertEqual(manifest_files(root, True), before)
                self.populate(results, run)
                score = self.load_entrypoint(root, group, "score")
                status, stdout, stderr = self.cli(score, ["--runs", str(run), "--json"])
                self.assertEqual(status, 0, stdout + stderr)
                report = json.loads(stdout)
                self.assertIs(report["formal_readiness"], False)
                self.assert_no_inference(report)
                self.assertNotRegex(stdout, r"PRIMARY criteria|PPI-rectified|McNemar|p=0\.")
                card = self.load_entrypoint(root, group, "eval_card")
                before = manifest_files(root, True)
                status, stdout, stderr = self.cli(card, ["--runs", str(run)])
                self.assertEqual(status, 0, stdout + stderr)
                self.assertEqual(manifest_files(root, True), before, "default card invocation prints only")
                output = root / (group + "-card.json")
                status, stdout, stderr = self.cli(card, ["--runs", str(run), "--output", str(output)])
                self.assertEqual(status, 0, stdout + stderr)
                self.assertIs(read_json(output)["formal_readiness"], False)


if __name__ == "__main__":
    unittest.main()
