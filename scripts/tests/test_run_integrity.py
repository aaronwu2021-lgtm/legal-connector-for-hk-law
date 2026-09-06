"""Offline 05b acceptance: execute only copied runners with synthetic inputs.

Target imports and calls run under an audit guard denying network/processes and
all writes outside the fixture. No repository builder, model, API, or original
experiment run is executed. Source files are copied as bytes, never imported.
"""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import urllib.request


REPO = Path(__file__).resolve().parents[2]
ACTIVE_ROOT = None
sys.dont_write_bytecode = True


def audit(event, args):
    if ACTIVE_ROOT is None:
        return
    if event.startswith(("socket.", "subprocess.")) or event in {"os.system", "os.posix_spawn", "os.spawn"}:
        raise AssertionError("network/process denied during target execution: " + event)
    paths = []
    if event == "open":
        path, mode, flags = args
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            paths = [path]
    elif event in {"os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.utime"}:
        paths = [args[0]]
    elif event in {"os.rename", "os.link", "os.symlink"}:
        paths = list(args[:2])
    for item in paths:
        if isinstance(item, int):
            raise AssertionError("descriptor mutation not allowed")
        if not Path(item).resolve().is_relative_to(ACTIVE_ROOT):
            raise AssertionError("write outside temporary fixture: " + str(item))


sys.addaudithook(audit)


def snapshot(root):
    return {str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
            for p in root.rglob("*") if p.is_file()}


def json_write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class RunIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Read-only snapshot includes existing runs and non-Python artefacts.
        paths = list((REPO / "data").rglob("*"))
        paths += list((REPO / "experiments/exp3-hk-matter").rglob("*"))
        paths += list((REPO / "experiments/exp4-cfa").rglob("*"))
        paths += list((REPO / "server/netlify/functions").glob("_*.mjs"))
        cls.protected = {p: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                         for p in paths if p.is_file() and p.suffix not in {".py", ".pyc"}}

    @classmethod
    def tearDownClass(cls):
        changed = [str(p) for p, old in cls.protected.items()
                   if not p.is_file() or (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns) != old]
        if changed:
            raise AssertionError("original artefacts changed: " + str(changed))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="doctrine-05b-")
        self.root = Path(self.temp.name).resolve()
        self.here = self.root / "experiments/exp3-hk-matter"
        self.here.mkdir(parents=True)
        self.here4 = self.root / "experiments/exp4-cfa"
        self.here4.mkdir()
        for relative in ("experiments/run_integrity.py", "experiments/exp3-hk-matter/run.py", "experiments/exp4-cfa/run.py"):
            shutil.copyfile(REPO / relative, self.root / relative)
        (self.root / "server/netlify/functions").mkdir(parents=True)
        (self.root / "server/netlify/functions/api.mjs").write_text("// synthetic API source snapshot\n", encoding="utf-8")
        (self.root / "data").mkdir()
        (self.root / "data/catalogue.json").write_text('{"synthetic":true}\n', encoding="utf-8")
        (self.here / "matter").mkdir()
        (self.here / "matter/base.md").write_text("Synthetic matter only.\n", encoding="utf-8")
        (self.here / "matter/inv.md").write_text("Synthetic alternate matter.\n", encoding="utf-8")
        self.tasks = {"tasks": [{"id": "T1", "as_of": 2022, "instruction": "Discuss the synthetic matter.",
            "files": ["base.md"], "files_inv": ["inv.md"], "payload": {"timelines": ["TL"], "checklist": True},
            "rubric": [{"id": "T1-a", "criterion": "Synthetic criterion", "pin": "[1]"}]}]}
        json_write(self.here / "tasks.json", self.tasks)
        self.env = mock.patch.dict(os.environ, {"MODEL_ID": "synthetic-model", "MODEL_FAMILY": "SYNTHETIC",
            "EXP3_RUNS_DIR": str(self.here / "runs"), "EXP4_RUNS_DIR": str(self.here4 / "runs"),
            "EXP_TASKS": str(self.here / "tasks.json"), "EXP_MATTER_DIR": str(self.here / "matter"),
            "CONNECTOR_VARIANT": "base", "CONNECTOR_INCLUDE_HELDOUT": "0",
            "CONNECTOR_API": "http://fixture.invalid/api", "MODEL_CMD": "DO-NOT-EXECUTE-secret"}, clear=False)
        self.env.start()
        self.out = self.here / "runs"
        self.old_path = list(sys.path)
        self.old_module = sys.modules.pop("run_integrity", None)
        self.api_calls = []
        with self.guarded():
            spec = importlib.util.spec_from_file_location("run_integrity", self.root / "experiments/run_integrity.py")
            self.target = importlib.util.module_from_spec(spec)
            sys.modules["run_integrity"] = self.target
            spec.loader.exec_module(self.target)

    def tearDown(self):
        self.env.stop()
        sys.path[:] = self.old_path
        sys.modules.pop("run_integrity", None)
        if self.old_module is not None:
            sys.modules["run_integrity"] = self.old_module
        self.temp.cleanup()

    @contextlib.contextmanager
    def guarded(self):
        global ACTIVE_ROOT
        previous = ACTIVE_ROOT
        ACTIVE_ROOT = self.root
        try:
            with mock.patch.object(urllib.request, "urlopen", side_effect=AssertionError("real API denied")), \
                    mock.patch.object(subprocess, "run", side_effect=AssertionError("real model/process denied")), \
                    contextlib.redirect_stdout(io.StringIO()):
                yield
        finally:
            ACTIVE_ROOT = previous

    def call(self, fn, *args, **kwargs):
        with self.guarded():
            return fn(*args, **kwargs)

    def response(self, url):
        self.api_calls.append(url)
        cutoff = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["as_of"][0]
        common = {"as_of": cutoff, "historical_mode": "strict", "historical_rule_status": "historical-rule-not-modelled",
                  "historical_limitations": {"rule_text": "Current text withheld", "excluded_counts": {"after-cutoff": 1}}}
        authority = {"case": "Synthetic case", "cite": "[2021] HKCFA 1", "year": 2021,
            "pin": "[1]", "verified": "verified-primary", "proposition_check": "not-performed"}
        if "/checklist?" in url:
            return {**common, "elements": [{"element": "E1", "sub_test": "E1a", "backbone_authority": [authority]}],
                    "defences_to_anticipate": [{"id": "D1", "en": "Synthetic", "authority": [authority]}]}
        return {**common, "id": "TL", "events": [{"j": "HK", "y": 2021, "case": "Synthetic case"}],
                "standing_rules": [{"jurisdiction": "HK", "since": 2021, "case": "Synthetic case"}],
                "latest_rules": [], "resolution": "This explanation is locally replaced."}

    def build(self, getter=None):
        return self.call(self.target.build_run, self.here, "exp3-hk-matter", "SYSTEM", "STRICT METADATA", getter=getter or self.response)

    def answer(self, completion=None):
        return self.call(self.target.run_answers, self.here, "exp3-hk-matter", completion=completion or (lambda prompt: "Synthetic answer: " + self.target.sha256_bytes(prompt.encode())[:8] + "\r\n"))

    def blind(self):
        return self.call(self.target.blind_run, self.here, "exp3-hk-matter")

    def rewrite_manifest(self, manifest):
        manifest["manifest_sha256"] = self.target.object_hash({k: v for k, v in manifest.items() if k != "manifest_sha256"})
        json_write(self.out / "manifest.json", manifest)

    def test_import_and_help_unknown_are_read_only_for_both_copied_wrappers(self):
        before = snapshot(self.root)
        for n, here in enumerate((self.here, self.here4)):
            with self.guarded():
                spec = importlib.util.spec_from_file_location("fixture_runner_" + str(n), here / "run.py")
                wrapper = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(wrapper)
                self.assertEqual(wrapper.HERE, here)
                for argv, exit_code in ((["--help"], 0), (["bad-command"], 2), (["build", "--unknown"], 2)):
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                        wrapper.main(argv)
                    self.assertEqual(caught.exception.code, exit_code)
        self.assertEqual(snapshot(self.root), before)

    def test_guard_denies_process_network_and_outside_writes(self):
        with self.guarded():
            for action in (lambda: socket.socket(), lambda: subprocess.run(["NO"]),
                           lambda: (self.root.parent / "outside-denied-05b").write_text("no")):
                with self.assertRaises(AssertionError): action()

    def test_single_command_cli_dispatch_build_run_blind_for_both_wrappers(self):
        for n, here in enumerate((self.here, self.here4)):
            with self.subTest(experiment=here.name), self.guarded():
                spec = importlib.util.spec_from_file_location("fixture_cli_" + str(n), here / "run.py")
                wrapper = importlib.util.module_from_spec(spec); spec.loader.exec_module(wrapper)
                with mock.patch.object(self.target, "api_get", self.response), \
                        mock.patch.object(self.target, "complete_command", lambda _: "Synthetic CLI answer"):
                    for command in ("build", "run", "blind"):
                        self.assertEqual(wrapper.main([command]), 0)
                self.assertTrue((here / "runs/blind_manifest.json").is_file())

    def test_opaque_model_failure_hides_command_stderr_and_records_no_result(self):
        self.build()
        with self.guarded():
            for result in (subprocess.CompletedProcess("secret", 7, "", "CREDENTIAL SECRET"),
                           subprocess.TimeoutExpired("CREDENTIAL SECRET", 300)):
                fake = mock.Mock(side_effect=result) if isinstance(result, Exception) else mock.Mock(return_value=result)
                with mock.patch.object(subprocess, "run", fake), self.assertRaises(self.target.IntegrityError) as caught:
                    self.target.run_answers(self.here, "exp3-hk-matter")
                self.assertNotIn("SECRET", str(caught.exception))
                self.assertNotIn("DO-NOT-EXECUTE", str(caught.exception))
                self.assertEqual(list(self.out.glob("*.answer.md")), [])

    def test_api_adapter_rejects_oversize_and_non_json_without_network(self):
        class Response:
            def __init__(self, blob): self.blob = blob
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return self.blob[:limit]
        with self.guarded():
            for blob in (b"X" * (4 * 1024 * 1024 + 1), b"<html>failure</html>", b'{}\xff', b'{"a":NaN}', b'{"a":1,"a":2}'):
                with self.subTest(length=len(blob)), mock.patch.object(urllib.request, "urlopen", return_value=Response(blob)), self.assertRaises(self.target.IntegrityError):
                    self.target.api_get("http://fixture.invalid/api")

    def test_build_current_payload_schema_year_end_and_honest_declarations(self):
        manifest = self.build()
        self.assertEqual(len(manifest["entries"]), 2)
        self.assertEqual(len(self.api_calls), 2)
        self.assertTrue(all("as_of=2022-12-31" in url for url in self.api_calls))
        self.assertFalse(manifest["readiness"]["formal_ready"])
        self.assertEqual(manifest["readiness"]["run_kind"], "exploratory")
        self.assertEqual(manifest["model"]["identity_basis"], "operator-declared")
        self.assertEqual(manifest["model"]["parameters"]["status"], "not-recorded")
        self.assertIn("not an attestation", manifest["input_identity_basis"])
        bare, conn = [(self.out / e["prompt_file"]).read_text(encoding="utf-8") for e in manifest["entries"]]
        self.assertNotIn("Synthetic criterion", conn)
        self.assertNotIn("CONNECTOR MATERIAL", bare)
        self.assertIn("authority", conn)
        self.assertIn("Historical legal rules are not modelled", conn)
        self.assertNotIn("This explanation is locally replaced", conn)
        self.assertNotIn("DO-NOT-EXECUTE-secret", (self.out / "manifest.json").read_text())
        for req in manifest["payload_requests"]:
            raw = self.target.read_json(self.out / req["response_file"])
            self.assertEqual(req["response_sha256"], self.target.object_hash(raw))

    def test_full_pipeline_resume_is_read_only_and_preserves_exact_answer_bytes(self):
        self.build(); self.answer(); blind = self.blind()
        before = snapshot(self.root)
        self.build(getter=lambda _: self.fail("existing build fetched API"))
        self.answer(completion=lambda _: self.fail("existing answer called model"))
        self.assertEqual(self.blind(), blind)
        self.assertEqual(snapshot(self.root), before)
        for public in blind["entries"]:
            blob = (self.out / public["blinded_file"]).read_bytes().split(b"\n", 1)[1]
            self.assertTrue(blob.endswith(b"\r\n"))
            self.assertEqual(self.target.sha256_bytes(blob), public["answer_sha256"])

    def test_model_identity_required_before_creating_any_directory(self):
        with mock.patch.dict(os.environ, {"MODEL_ID": ""}):
            with self.assertRaises(self.target.IntegrityError): self.build()
        self.assertFalse(self.out.exists())

    def test_exp4_payload_and_own_output_override(self):
        self.tasks["tasks"][0]["payload"] = {"timelines": ["ARBCH-12"], "checklist": False}
        json_write(self.here / "tasks.json", self.tasks)
        manifest = self.call(self.target.build_run, self.here4, "exp4-cfa", "SYSTEM", "STRICT", getter=self.response)
        self.assertEqual(manifest["experiment"], "exp4-cfa")
        self.assertTrue((self.here4 / "runs/manifest.json").is_file())
        self.assertFalse(self.out.exists())
        self.assertEqual(len(self.api_calls), 1)
        self.assertIn("/timeline/ARBCH-12?", self.api_calls[0])

    def test_exp4_old_output_override_fallback(self):
        with mock.patch.dict(os.environ, {"EXP4_RUNS_DIR": ""}):
            self.call(self.target.build_run, self.here4, "exp4-cfa", "SYSTEM", "STRICT", getter=self.response)
        self.assertTrue((self.out / "manifest.json").is_file())

    def test_inverted_run_identity_and_matter_fallback_are_explicit(self):
        for inverted_file in (True, False):
            with self.subTest(inverted_file=inverted_file):
                if not inverted_file: self.tasks["tasks"][0].pop("files_inv")
                json_write(self.here / "tasks.json", self.tasks)
                with mock.patch.dict(os.environ, {"CONNECTOR_VARIANT": "inv", "EXP3_RUNS_DIR": str(self.here / ("inv-" + str(inverted_file)))}):
                    manifest = self.build()
                for entry in manifest["entries"]:
                    self.assertEqual(entry["variant"], "inv")
                    self.assertEqual(entry["matter_variant"], "inv" if inverted_file else "base")
                    self.assertTrue(entry["entry_id"].endswith(".inv"))

    def test_heldout_selection_is_bound_to_matrix_and_config(self):
        extra = copy.deepcopy(self.tasks["tasks"][0]); extra.update(id="T2", held_out=True)
        self.tasks["tasks"].append(extra); json_write(self.here / "tasks.json", self.tasks)
        self.assertEqual(self.build()["task_ids"], ["T1"])
        with mock.patch.dict(os.environ, {"CONNECTOR_INCLUDE_HELDOUT": "1"}):
            with self.assertRaises(self.target.IntegrityError): self.build()

    def test_historical_missing_mode_wrong_cutoff_and_future_body_rejected_before_writes(self):
        for mutation in (lambda r: r.pop("historical_mode"), lambda r: r.update(as_of="2023-12-31"),
                         lambda r: r.update(holding="Future conclusion"), lambda r: r.update(rule="Undated current rule")):
            def getter(url):
                value = self.response(url); mutation(value); return value
            with self.subTest(mutation=mutation), self.assertRaises(self.target.IntegrityError): self.build(getter)
            self.assertFalse(self.out.exists())

    def test_future_nested_authority_and_unversioned_note_rejected(self):
        for extra in ({"events": [{"y": 2023, "case": "Future"}]}, {"note": "Unsupported prose"},
                      {"events": [{"case": "Future [2023] HKCFA 1"}]}):
            response = {"as_of": "2022-12-31", "historical_mode": "strict", "historical_rule_status": "historical-rule-not-modelled", **extra}
            with self.subTest(extra=extra), self.assertRaises(self.target.IntegrityError):
                self.call(self.target.strict_payload, response, 2022)

    def test_precise_cutoff_requires_same_year_exact_date(self):
        response = {"as_of": "2022-06-30", "historical_mode": "strict", "historical_rule_status": "historical-rule-not-modelled",
                    "events": [{"y": 2022, "case": "Synthetic"}]}
        with self.assertRaises(self.target.IntegrityError): self.call(self.target.strict_payload, response, "2022-06-30")
        response["events"][0]["decision_date"] = "2022-06-01"
        self.call(self.target.strict_payload, response, "2022-06-30")
        response["events"][0]["decision_date"] = "2022-07-01"
        with self.assertRaises(self.target.IntegrityError): self.call(self.target.strict_payload, response, "2022-06-30")

    def test_local_fixed_explanation_replaces_all_unversioned_limitations(self):
        response = self.response("http://fixture.invalid/checklist?as_of=2022-12-31")
        response["historical_limitations"] = {"holding": "FUTURE SECRET FROM 2026"}
        projected = self.call(self.target.strict_payload, response, 2022)
        self.assertNotIn("FUTURE SECRET", json.dumps(projected))

    def test_old_nonmanifest_directory_is_unchanged(self):
        self.out.mkdir(); (self.out / "old.answer.md").write_text("Existing unbound result")
        before = snapshot(self.root)
        for operation in (self.build, self.answer, self.blind):
            with self.assertRaises(self.target.IntegrityError): operation()
        self.assertEqual(snapshot(self.root), before)

    def test_input_changes_block_reuse_and_never_rewrite(self):
        self.build()
        for source in (self.here / "tasks.json", self.here / "matter/base.md", self.root / "server/netlify/functions/api.mjs", self.root / "data/catalogue.json"):
            blob = source.read_bytes(); source.write_bytes(blob + b"\n")
            before = snapshot(self.out)
            with self.subTest(source=source), self.assertRaises(self.target.IntegrityError): self.build()
            self.assertEqual(snapshot(self.out), before)
            source.write_bytes(blob)

    def test_config_identity_changes_block_answer_cache(self):
        self.build(); self.answer()
        for key, value in (("MODEL_ID", "other-model"), ("MODEL_FAMILY", "other-family"), ("CONNECTOR_VARIANT", "inv"), ("CONNECTOR_API", "http://other.invalid/api")):
            with self.subTest(key=key), mock.patch.dict(os.environ, {key: value}), self.assertRaises(self.target.IntegrityError): self.answer()

    def test_source_change_during_model_call_rejects_answer_before_save(self):
        self.build()
        def mutate(prompt):
            (self.here / "matter/base.md").write_text("Changed during model call")
            return "ANSWER"
        with self.assertRaises(self.target.IntegrityError): self.answer(mutate)
        self.assertEqual(list(self.out.glob("*.answer.md")), [])

    def test_shared_matter_change_between_tasks_is_rejected_before_publication(self):
        extra = copy.deepcopy(self.tasks["tasks"][0]); extra["id"] = "T2"
        self.tasks["tasks"].append(extra); json_write(self.here / "tasks.json", self.tasks)
        def getter(url):
            response = self.response(url)
            (self.here / "matter/base.md").write_text("Changed between tasks")
            return response
        with self.assertRaises(self.target.IntegrityError): self.build(getter)
        self.assertFalse(self.out.exists())

    def test_prompt_tamper_blocks_model_and_build(self):
        manifest = self.build()
        (self.out / manifest["entries"][0]["prompt_file"]).write_text("Changed prompt")
        for operation in (self.build, lambda: self.answer(lambda _: self.fail("model reached"))):
            with self.assertRaises(self.target.IntegrityError): operation()

    def test_incomplete_answer_pair_is_not_overwritten_or_repaired(self):
        manifest = self.build()
        (self.out / manifest["entries"][0]["answer_file"]).write_text("Legacy answer only")
        before = snapshot(self.out)
        with self.assertRaises(self.target.IntegrityError): self.answer()
        with self.assertRaises(self.target.IntegrityError): self.blind()
        self.assertEqual(snapshot(self.out), before)

    def test_blind_requires_all_expected_answers_and_rejects_extra(self):
        self.build()
        with self.assertRaises(self.target.IntegrityError): self.blind()
        self.answer(); (self.out / "unexpected.answer.md").write_text("Unbound")
        with self.assertRaises(self.target.IntegrityError): self.blind()
        self.assertFalse((self.out / "blind_manifest.json").exists())

    def test_answer_content_and_metadata_bindings_are_checked(self):
        manifest = self.build(); self.answer()
        entry = manifest["entries"][0]
        meta_path = self.out / entry["meta_file"]
        original = self.target.read_json(meta_path)
        for field, changed in (("model_id", "other"), ("model_family", "other"), ("variant", "inv"),
                ("condition", "conn"), ("manifest_sha256", "0" * 64), ("prompt_sha256", "0" * 64),
                ("identity_basis", "provider-attested"), ("parameters", {"temperature": 0}),
                ("started_utc", "2000-01-01T00:00:00Z"), ("duration_s", -1)):
            bad = copy.deepcopy(original); bad[field] = changed; json_write(meta_path, bad)
            with self.subTest(field=field), self.assertRaises(self.target.IntegrityError):
                self.call(self.target.validate_answers, self.out)
        json_write(meta_path, original)
        (self.out / entry["answer_file"]).write_text("Tampered content")
        with self.assertRaises(self.target.IntegrityError): self.blind()

    def test_empty_model_response_is_never_accepted(self):
        self.build()
        for response in ("", "  ", None):
            with self.subTest(response=response), self.assertRaises(self.target.IntegrityError): self.answer(lambda _: response)
        self.assertEqual(list(self.out.glob("*.answer.md")), [])

    def test_payload_response_tamper_and_reference_mismatch_fail(self):
        manifest = self.build()
        raw_path = self.out / manifest["payload_requests"][0]["response_file"]
        raw = raw_path.read_bytes(); raw_path.write_bytes(raw + b" ")
        with self.assertRaises(self.target.IntegrityError): self.call(self.target.load_manifest, self.out)
        raw_path.write_bytes(raw)
        manifest["entries"][0]["payload_request_ids"] = [manifest["payload_requests"][0]["request_id"]]
        self.rewrite_manifest(manifest)
        with self.assertRaises(self.target.IntegrityError): self.call(self.target.load_manifest, self.out)

    def test_declared_matrix_and_safe_paths_are_checked(self):
        manifest = self.build()
        manifest["task_ids"] = ["T1", "MISSING"]
        self.rewrite_manifest(manifest)
        with self.assertRaises(self.target.IntegrityError): self.call(self.target.load_manifest, self.out)
        for value in ("../escape", self.root / "absolute", ".", None):
            with self.subTest(path=value), self.assertRaises(self.target.IntegrityError):
                self.call(self.target.safe_path, self.out, value)

    def test_judge_safe_loader_does_not_read_private_manifest_or_key(self):
        self.build(); self.answer(); blind = self.blind()
        (self.out / "manifest.json").write_text("PRIVATE CANNOT PARSE")
        (self.out / "blind_key.json").write_text("PRIVATE CANNOT PARSE")
        self.assertEqual(self.call(self.target.load_blind_manifest, self.out), blind)
        forbidden = {"condition", "variant", "entry_id", "prompt_file", "answer_file", "meta_file"}
        def walk(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden & set(value))
                for child in value.values(): walk(child)
            elif isinstance(value, list):
                for child in value: walk(child)
        walk(blind)

    def test_private_key_swap_and_public_content_tamper_rejected_without_relabeling(self):
        self.build(); self.answer(); blind = self.blind()
        key_path = self.out / "blind_key.json"
        original = self.target.read_json(key_path)
        swapped = copy.deepcopy(original)
        a, b = swapped["entries"]
        swapped["entries"][a], swapped["entries"][b] = swapped["entries"][b], swapped["entries"][a]
        json_write(key_path, swapped); before = snapshot(self.out)
        with self.assertRaises(self.target.IntegrityError): self.blind()
        self.assertEqual(snapshot(self.out), before)
        json_write(key_path, original)
        (self.out / blind["entries"][0]["blinded_file"]).write_text("Changed blinded answer")
        with self.assertRaises(self.target.IntegrityError): self.blind()

    def test_legacy_verdict_directory_blocks_build_run_blind_reuse(self):
        self.build(); self.answer(); (self.out / "verdicts").mkdir()
        (self.out / "verdicts/OUT00.json").write_text("{}")
        before = snapshot(self.out)
        for operation in (self.build, self.answer, self.blind):
            with self.assertRaises(self.target.IntegrityError): operation()
        self.assertEqual(snapshot(self.out), before)

    def test_json_and_calendar_inputs_fail_closed(self):
        for value in (True, 99, "2022-02-30", "2022-1-1", "2022-12-31junk"):
            with self.subTest(value=value), self.assertRaises(self.target.IntegrityError):
                self.call(self.target.normalize_as_of, value)
        for source in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
            path = self.root / "invalid.json"; path.write_text(source)
            with self.subTest(source=source), self.assertRaises(self.target.IntegrityError): self.call(self.target.read_json, path)


if __name__ == "__main__":
    unittest.main()
