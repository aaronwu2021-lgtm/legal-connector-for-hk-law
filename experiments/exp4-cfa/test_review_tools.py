"""Offline acceptance for Exp4 review helpers, executed only in temporary copies.

This module never imports run, judge, score, task builders, or a model client.
Only copied validator/reader helpers are loaded; original artefacts are checked
for byte preservation after the suite.
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


HERE = Path(__file__).resolve().parent
TOOL_NAMES = ("validate_tasks.py", "build_reader_checklist.py")


def artefact_manifest(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix not in {".py", ".pyc"}
        and "__pycache__" not in path.parts
    }


def load_copy(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def synthetic_document(year=2020):
    """A local string-matching fixture, never a real legal research assertion."""
    name = "Synthetic Alpha v Synthetic Beta"
    citation = "[%d] HKCFA 9" % year
    phrase = "This synthetic phrase checks only the presence of text."
    return {
        "dataset": "synthetic-review-fixture",
        "tasks": [{
            "id": "SYN-1", "as_of": year,
            "instruction": "Review this synthetic record without drawing a legal conclusion.",
            "files": ["matter.md"], "payload": {"timelines": ["SYN-T"], "checklist": False},
            "held_out": False,
            "sources": [{"case": name, "citation": citation, "court": "Synthetic Court",
                         "source_type": "synthetic fixture", "decision_date": "%d-01-01" % year,
                         "available_date": "%d-01-01" % year,
                         "official_url": "https://example.invalid/synthetic",
                         "source_file": "judgment.txt"}],
            "rubric": [{
                "id": "SYN-1-a", "criterion": "Reports the synthetic proposition.",
                "authority": name + " " + citation, "pin": "[1]",
                "discriminates_against": "Inventing another synthetic proposition.",
                "drift_sensitive": False, "polarity": "positive",
                "source_checks": [{"citation": citation, "locator": "[1]", "pin_phrases": [phrase]}],
            }],
        }],
    }


def judgment_for(document, phrase=True):
    task = document["tasks"][0]
    source = task["sources"][0]
    return "CASE NAME: " + source["case"] + " " + source["citation"] + "\n[1] " + (
        task["rubric"][0]["source_checks"][0]["pin_phrases"][0] if phrase else "An entirely different passage."
    ) + "\n"


class ReviewToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_manifest = artefact_manifest(HERE)
        cls.current = json.loads((HERE / "tasks.json").read_text(encoding="utf-8"))
        cls.source_bytes = {name: (HERE / name).read_bytes() for name in TOOL_NAMES}
        names = {name for task in cls.current["tasks"] for name in task["files"]}
        names.update(source["source_file"] for task in cls.current["tasks"] for source in task.get("sources", []))
        cls.current_matter = {name: (HERE / "matter" / name).read_bytes() for name in names}

    @classmethod
    def tearDownClass(cls):
        if artefact_manifest(HERE) != cls.original_manifest:
            raise AssertionError("original Exp4 artefacts changed during offline review-tool tests")

    @contextlib.contextmanager
    def tools(self, document=None, judgment=None, corrupt_tasks=False):
        document = copy.deepcopy(self.current if document is None else document)
        names = ("validate_tasks", "_exp4_reader_under_test")
        previous_modules = {name: sys.modules.get(name) for name in names}
        previous_path = sys.path[:]
        previous_bytecode = sys.dont_write_bytecode
        guards = []
        try:
            with tempfile.TemporaryDirectory(prefix="exp4-review-test-") as directory:
                root = Path(directory).resolve()
                self.assertFalse(root.is_relative_to(HERE))
                for name, blob in self.source_bytes.items():
                    (root / name).write_bytes(blob)
                (root / "matter").mkdir()
                for name, blob in self.current_matter.items():
                    path = root / "matter" / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(blob)
                (root / "matter" / "matter.md").write_text("Synthetic matter only.\n", encoding="utf-8")
                if judgment is not None:
                    (root / "matter" / "judgment.txt").write_text(judgment, encoding="utf-8")
                tasks_path = root / "tasks.json"
                tasks_path.write_text("{not-json" if corrupt_tasks else json.dumps(document, ensure_ascii=False), encoding="utf-8")
                before_import = artefact_manifest(root)
                sys.path.insert(0, str(root))
                sys.dont_write_bytecode = True
                with contextlib.ExitStack() as stack:
                    for target in (
                        "socket.socket", "socket.create_connection", "urllib.request.urlopen",
                        "subprocess.run", "subprocess.Popen", "os.system",
                    ):
                        guards.append(stack.enter_context(mock.patch(target, side_effect=AssertionError("External execution/network forbidden: " + target))))
                    stdout, stderr = io.StringIO(), io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        validator = load_copy("validate_tasks", root / "validate_tasks.py")
                        reader = load_copy("_exp4_reader_under_test", root / "build_reader_checklist.py")
                    self.assertEqual(stdout.getvalue(), "", "import must not run a report")
                    self.assertEqual(stderr.getvalue(), "", "import must not run a report")
                    self.assertEqual(artefact_manifest(root), before_import, "imports must not write artefacts")
                    self.assertEqual(Path(validator.__file__).resolve(), root / "validate_tasks.py")
                    self.assertEqual(Path(reader.__file__).resolve(), root / "build_reader_checklist.py")
                    yield root, validator, reader
                    self.assertTrue(all(not guard.called for guard in guards), "no external calls, even caught attempts")
        finally:
            sys.path[:] = previous_path
            sys.dont_write_bytecode = previous_bytecode
            for name, previous in previous_modules.items():
                if previous is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = previous

    def validate(self, document, judgment=None):
        with self.tools(document, judgment) as (root, validator, _reader):
            return validator.validate_document(document, matter_dir=root / "matter")

    def assert_pending(self, report):
        self.assertEqual(report["independent_review"]["status"], "pending")
        self.assertIs(report["ready_for_experiment"], False)

    def assert_structural_error(self, document, field=None):
        report = self.validate(document)
        self.assertIs(report["schema_valid"], False, report)
        self.assertTrue(report["structural_errors"], report)
        self.assert_pending(report)
        for issue in report["structural_errors"]:
            for key in ("code", "path", "message"):
                self.assertTrue(isinstance(issue.get(key), str) and issue[key].strip(), issue)
        if field:
            self.assertIn(field, json.dumps(report["structural_errors"]), report)

    @staticmethod
    def cli(module, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                status = module.main(argv)
            except SystemExit as error:
                status = error.code
        return 0 if status is None else status, stdout.getvalue(), stderr.getvalue()

    def test_current_three_tasks_thirteen_criteria_have_checked_local_sources_but_remain_pending(self):
        self.assertEqual(len(self.current["tasks"]), 3)
        self.assertEqual(sum(len(task["rubric"]) for task in self.current["tasks"]), 13)
        original = copy.deepcopy(self.current)
        report = self.validate(self.current)
        self.assertIs(report["schema_valid"], True, report)
        self.assertEqual(report["structural_errors"], [])
        self.assertEqual(report["source_verification"]["status"], "checked", report)
        self.assertEqual(report["source_verification"]["issues"], [])
        self.assert_pending(report)
        self.assertEqual(self.current, original)

    def test_missing_required_source_records_is_actionable_and_never_automatic_verification(self):
        document = synthetic_document()
        task = document["tasks"][0]
        task.pop("sources")
        report = self.validate(document)
        self.assertIs(report["schema_valid"], False, report)
        self.assertEqual(report["source_verification"]["status"], "incomplete")
        self.assert_pending(report)
        self.assertNotIn("verified-primary", json.dumps(report))

    def test_malformed_document_and_task_collection_are_actionable_errors(self):
        for document in (None, [], "text", 3, {}, {"tasks": None}, {"tasks": {}}, {"tasks": []}, {"tasks": [None]}):
            with self.subTest(document=document):
                self.assert_structural_error(document)

    def test_required_task_fields_reject_missing_and_wrong_types(self):
        invalid = {
            "id": [None, "", " ", 1], "instruction": [None, "", [], {}],
            "files": [None, [], "matter.md", [1], [""]],
            "payload": [None, [], "text"], "rubric": [None, [], {}, [None]],
        }
        for field, values in invalid.items():
            for value in ["__MISSING__", *values]:
                with self.subTest(field=field, value=value):
                    document = synthetic_document()
                    if value == "__MISSING__":
                        document["tasks"][0].pop(field)
                    else:
                        document["tasks"][0][field] = value
                    self.assert_structural_error(document, field)

    def test_cutoff_accepts_years_and_real_calendar_dates_and_rejects_invalid_types(self):
        for value in (2020, "2020", "2020-02-29"):
            document = synthetic_document()
            document["tasks"][0]["as_of"] = value
            report = self.validate(document)
            self.assertIs(report["schema_valid"], True, report)
        for value in (None, True, False, 2020.5, "", "2020-02-30", "2021-02-29", "20", [], {}):
            with self.subTest(value=value):
                document = synthetic_document()
                document["tasks"][0]["as_of"] = value
                self.assert_structural_error(document, "as_of")

    def test_required_criterion_fields_are_typed_and_nonblank(self):
        for field in ("id", "criterion", "authority", "pin", "discriminates_against"):
            for value in (None, "", " ", 1, [], {}):
                with self.subTest(field=field, value=value):
                    document = synthetic_document()
                    document["tasks"][0]["rubric"][0][field] = value
                    self.assert_structural_error(document, field)
            document = synthetic_document()
            document["tasks"][0]["rubric"][0].pop(field)
            self.assert_structural_error(document, field)
        for value in (None, 0, 1, "false", []):
            document = synthetic_document()
            document["tasks"][0]["rubric"][0]["drift_sensitive"] = value
            self.assert_structural_error(document, "drift_sensitive")

    def test_duplicate_task_and_criterion_ids_are_rejected_including_across_tasks(self):
        document = synthetic_document()
        document["tasks"].append(copy.deepcopy(document["tasks"][0]))
        self.assert_structural_error(document, "id")
        document["tasks"][1]["id"] = "SYN-2"
        self.assert_structural_error(document, "id")
        document = synthetic_document()
        document["tasks"][0]["rubric"].append(copy.deepcopy(document["tasks"][0]["rubric"][0]))
        self.assert_structural_error(document, "id")

    def test_source_records_checks_and_flags_are_validated(self):
        for field, value in (("held_out", "false"), ("sources", {}), ("sources", [])):
            document = synthetic_document()
            document["tasks"][0][field] = value
            self.assert_structural_error(document, field)
        for field, value in (("polarity", "guess"), ("polarity", None), ("source_checks", []), ("source_checks", {})):
            document = synthetic_document()
            document["tasks"][0]["rubric"][0][field] = value
            self.assert_structural_error(document, field)
        for value in ([], [""], "phrase"):
            document = synthetic_document()
            document["tasks"][0]["rubric"][0]["source_checks"][0]["pin_phrases"] = value
            self.assert_structural_error(document, "pin_phrases")
        for value in (None, "", " ", 1, []):
            document = synthetic_document()
            document["tasks"][0]["rubric"][0]["source_checks"][0]["locator"] = value
            self.assert_structural_error(document, "locator")

    def test_sources_use_one_strict_legal_date_and_separate_local_files(self):
        for change in ("both-dates", "no-date", "year-only", "duplicate-file"):
            with self.subTest(change=change):
                document = synthetic_document()
                source = document["tasks"][0]["sources"][0]
                if change == "both-dates":
                    source["version_date"] = source["decision_date"]
                elif change == "no-date":
                    source.pop("decision_date")
                elif change == "year-only":
                    source["decision_date"] = "2020"
                else:
                    second = copy.deepcopy(source)
                    second["citation"] = "[2020] HKCFA 10"
                    document["tasks"][0]["sources"].append(second)
                self.assert_structural_error(document)

    def test_legislation_source_with_version_date_is_checked_without_becoming_signoff(self):
        document = synthetic_document()
        task = document["tasks"][0]
        source = task["sources"][0]
        source.update({
            "case": "Synthetic Ordinance",
            "citation": "Cap. 999 ss. 1, 2",
            "court": "Synthetic publisher",
            "source_type": "synthetic legislation fixture",
            "version_date": "2020-01-01",
        })
        source.pop("decision_date")
        criterion = task["rubric"][0]
        criterion["authority"] = source["case"] + " " + source["citation"]
        criterion["source_checks"][0]["citation"] = source["citation"]
        text = ("INSTRUMENT: " + source["case"] + " " + source["citation"] + "\n"
                + criterion["source_checks"][0]["pin_phrases"][0] + "\n")
        report = self.validate(document, text)
        self.assertIs(report["schema_valid"], True, report)
        self.assertEqual(report["source_verification"]["status"], "checked", report)
        self.assert_pending(report)

    def test_legislation_commas_and_subsection_parentheses_cannot_collide(self):
        document = synthetic_document()
        task = document["tasks"][0]
        source = task["sources"][0]
        source.update({
            "case": "Synthetic Ordinance",
            "citation": "Cap. 999 ss. 1, 2",
            "court": "Synthetic publisher",
            "source_type": "synthetic legislation fixture",
            "version_date": "2020-01-01",
        })
        source.pop("decision_date")
        criterion = task["rubric"][0]
        criterion["authority"] = source["case"] + " " + source["citation"]
        criterion["source_checks"][0]["citation"] = source["citation"]
        correct_text = ("INSTRUMENT: " + source["case"] + " " + source["citation"] + "\n"
                        + criterion["source_checks"][0]["pin_phrases"][0] + "\n")
        wrong_citation = "Cap. 999 ss. 1(2)"

        cases = []
        wrong_check = copy.deepcopy(document)
        wrong_check["tasks"][0]["rubric"][0]["source_checks"][0]["citation"] = wrong_citation
        cases.append(("source check", wrong_check, correct_text))
        wrong_authority = copy.deepcopy(document)
        wrong_authority["tasks"][0]["rubric"][0]["authority"] = (
            source["case"] + " " + wrong_citation)
        cases.append(("authority", wrong_authority, correct_text))
        wrong_identity = correct_text.replace(source["citation"], wrong_citation)
        cases.append(("local identity", document, wrong_identity))

        for label, candidate, text in cases:
            with self.subTest(label=label):
                report = self.validate(candidate, text)
                self.assertIs(report["schema_valid"], True, report)
                self.assertEqual(report["source_verification"]["status"], "incomplete", report)
                self.assertTrue(report["source_verification"]["issues"], report)
                self.assert_pending(report)

    def test_exact_local_source_checks_remain_separate_from_independent_review(self):
        document = synthetic_document()
        original = copy.deepcopy(document)
        report = self.validate(document, judgment_for(document))
        self.assertIs(report["schema_valid"], True, report)
        self.assertEqual(report["source_verification"]["status"], "checked", report)
        self.assertEqual(report["source_verification"]["issues"], [])
        self.assert_pending(report)
        self.assertEqual(document, original)
        self.assertNotIn("verified-primary", json.dumps(report))

    def test_a_missing_judgment_or_nonmatching_phrase_remains_incomplete(self):
        document = synthetic_document()
        for judgment in (None, judgment_for(document, phrase=False)):
            report = self.validate(document, judgment)
            self.assertIs(report["schema_valid"], True, report)
            self.assertEqual(report["source_verification"]["status"], "incomplete")
            self.assertTrue(report["source_verification"]["issues"])
            self.assert_pending(report)

    def test_same_first_party_does_not_verify_a_conflicting_second_party(self):
        document = synthetic_document()
        judgment = judgment_for(document)
        document["tasks"][0]["rubric"][0]["authority"] = "Synthetic Alpha v Different Defendant [2020] HKCFA 9"
        report = self.validate(document, judgment)
        self.assertEqual(report["source_verification"]["status"], "incomplete", report)
        self.assert_pending(report)

    def test_extra_conflicting_citation_cannot_be_ignored_when_phrase_matches(self):
        document = synthetic_document()
        judgment = judgment_for(document)
        document["tasks"][0]["rubric"][0]["authority"] += "; [2020] HKCFA 999"
        report = self.validate(document, judgment)
        self.assertEqual(report["source_verification"]["status"], "incomplete", report)

    def test_declared_source_identity_must_appear_in_the_actual_local_text(self):
        document = synthetic_document()
        for judgment in (judgment_for(document).replace("Synthetic Beta", "Different Defendant"),
                         judgment_for(document).replace("Synthetic Beta", "Synthetic Beta Ltd"),
                         judgment_for(document).replace("[2020] HKCFA 9", "[2020] HKCFA 999")):
            report = self.validate(document, judgment)
            self.assertEqual(report["source_verification"]["status"], "incomplete", report)

    def test_unicode_party_identity_is_not_erased_by_normalization(self):
        document = synthetic_document()
        source = document["tasks"][0]["sources"][0]
        source["case"] = "Synthetic Alpha v 廈門新景地集團有限公司"
        document["tasks"][0]["rubric"][0]["authority"] = source["case"] + " " + source["citation"]
        judgment = judgment_for(document).replace("廈門新景地集團有限公司", "完全不同有限公司")
        report = self.validate(document, judgment)
        self.assertEqual(report["source_verification"]["status"], "incomplete", report)

    def test_phrase_from_one_source_cannot_verify_another_citation(self):
        document = synthetic_document()
        task = document["tasks"][0]
        second = copy.deepcopy(task["sources"][0])
        second["citation"] = "[2020] HKCFA 10"
        second["source_file"] = "second.txt"
        task["sources"].append(second)
        task["rubric"][0]["authority"] = second["case"] + " " + second["citation"]
        task["rubric"][0]["source_checks"][0]["citation"] = second["citation"]
        with self.tools(document, judgment_for(document)) as (root, validator, _reader):
            (root / "matter" / "second.txt").write_text(
                "CASE NAME: " + second["case"] + " " + second["citation"] + "\n[1] Different text.\n",
                encoding="utf-8",
            )
            report = validator.validate_document(document, matter_dir=root / "matter")
        self.assertEqual(report["source_verification"]["status"], "incomplete", report)

    def test_resolved_path_alias_cannot_reuse_one_file_for_two_sources(self):
        document = synthetic_document()
        task = document["tasks"][0]
        second = copy.deepcopy(task["sources"][0])
        second["citation"] = "[2020] HKCFA 10"
        second["source_file"] = "sub/../judgment.txt"
        task["sources"].append(second)
        report = self.validate(document, judgment_for(document))
        self.assertIs(report["schema_valid"], True, report)
        self.assertEqual(report["source_verification"]["status"], "incomplete", report)
        self.assertTrue(any(item["code"] == "source-file-reused"
                            for item in report["source_verification"]["issues"]), report)
        self.assert_pending(report)

    def test_hard_link_alias_cannot_reuse_one_file_for_two_sources(self):
        document = synthetic_document()
        task = document["tasks"][0]
        first = task["sources"][0]
        second = copy.deepcopy(first)
        second["citation"] = "[2020] HKCFA 10"
        second["source_file"] = "second.txt"
        task["sources"].append(second)
        phrase = task["rubric"][0]["source_checks"][0]["pin_phrases"][0]
        text = ("CASE NAME: " + first["case"] + " " + first["citation"] + "\n"
                "CASE NAME: " + second["case"] + " " + second["citation"] + "\n"
                "[1] " + phrase + "\n")
        with self.tools(document, text) as (root, validator, _reader):
            first_path = root / "matter" / "judgment.txt"
            second_path = root / "matter" / "second.txt"
            os.link(first_path, second_path)
            self.assertTrue(first_path.samefile(second_path))
            report = validator.validate_document(document, matter_dir=root / "matter")
        self.assertIs(report["schema_valid"], True, report)
        self.assertEqual(report["source_verification"]["status"], "incomplete", report)
        self.assertTrue(any(item["code"] == "source-file-reused"
                            for item in report["source_verification"]["issues"]), report)
        self.assert_pending(report)

    def test_distinct_source_paths_are_not_collapsed_by_punctuation(self):
        document = synthetic_document()
        task = document["tasks"][0]
        first = task["sources"][0]
        first["source_file"] = "a-b.txt"
        second = copy.deepcopy(first)
        second["citation"] = "[2020] HKCFA 10"
        second["source_file"] = "a_b.txt"
        task["sources"].append(second)
        phrase = task["rubric"][0]["source_checks"][0]["pin_phrases"][0]
        with self.tools(document) as (root, validator, _reader):
            for source in (first, second):
                (root / "matter" / source["source_file"]).write_text(
                    "CASE NAME: " + source["case"] + " " + source["citation"]
                    + "\n[1] " + phrase + "\n",
                    encoding="utf-8",
                )
            report = validator.validate_document(document, matter_dir=root / "matter")
        self.assertIs(report["schema_valid"], True, report)
        self.assertEqual(report["source_verification"]["status"], "checked", report)
        self.assertEqual(report["source_verification"]["issues"], [], report)
        self.assert_pending(report)

    def test_future_authority_requires_explicit_polarity_without_inference_from_prose(self):
        document = synthetic_document(2025)
        document["tasks"][0]["as_of"] = 2020
        judgment = judgment_for(document)
        criterion = document["tasks"][0]["rubric"][0]
        criterion["criterion"] = "Must NOT cite this later synthetic authority."
        positive = self.validate(document, judgment)
        self.assertIs(positive["schema_valid"], True, positive)
        self.assertEqual(positive["source_verification"]["status"], "incomplete", positive)
        criterion["polarity"] = "negative"
        negative = self.validate(document, judgment)
        self.assertIs(negative["schema_valid"], True, negative)
        self.assertEqual(negative["source_verification"]["status"], "checked", negative)
        criterion.pop("polarity")
        missing = self.validate(document, judgment)
        self.assertIs(missing["schema_valid"], True, missing)
        self.assertEqual(missing["source_verification"]["status"], "incomplete", missing)
        self.assertTrue(any("polarity" in issue["path"] for issue in missing["source_verification"]["issues"]), missing)
        for report in (positive, negative, missing):
            self.assert_pending(report)

    def test_reader_retains_all_original_criteria_files_payload_and_pending_signoff(self):
        original = copy.deepcopy(self.current)
        with self.tools() as (root, validator, reader):
            report = validator.validate_document(self.current, matter_dir=root / "matter")
            markdown = reader.build_checklist(self.current, report)
            self.assertIsInstance(markdown, str)
            self.assertTrue(markdown.strip())
            for task in self.current["tasks"]:
                self.assertIn(task["id"], markdown)
                self.assertIn(task["instruction"], markdown)
                for filename in task["files"]:
                    self.assertIn(filename, markdown)
                for key, value in task["payload"].items():
                    self.assertIn(key, markdown)
                    if isinstance(value, list):
                        for item in value:
                            self.assertIn(item, markdown)
                    elif isinstance(value, bool):
                        self.assertIn(str(value).lower(), markdown)
                for criterion in task["rubric"]:
                    for field in ("id", "criterion", "authority", "pin", "discriminates_against"):
                        self.assertIn(criterion[field], markdown, field)
            self.assertNotIn("[x]", markdown.lower(), "reader signoff must never be precompleted")
            self.assertTrue("pending" in markdown.lower() or "待" in markdown)
            self.assertEqual(self.current, original)

    def test_reader_does_not_promote_a_lexical_match_into_primary_or_completed_review(self):
        document = synthetic_document()
        with self.tools(document, judgment_for(document)) as (root, validator, reader):
            report = validator.validate_document(document, matter_dir=root / "matter")
            markdown = reader.build_checklist(document, report)
            self.assert_pending(report)
            self.assertNotIn("verified-primary", markdown)
            self.assertNotIn("[x]", markdown.lower())
            self.assertTrue("pending" in markdown.lower() or "待" in markdown)

    def test_import_help_and_unknown_arguments_do_not_read_tasks_or_write_outputs(self):
        with self.tools(corrupt_tasks=True) as (root, validator, reader):
            before = artefact_manifest(root)
            for module in (validator, reader):
                status, stdout, _ = self.cli(module, ["--help"])
                self.assertEqual(status, 0)
                self.assertIn("usage:", stdout.lower())
                status, _, _ = self.cli(module, ["--unknown-review-option"])
                self.assertNotEqual(status, 0)
            self.assertEqual(artefact_manifest(root), before)

    def test_validator_cli_distinguishes_structure_only_from_experiment_readiness(self):
        with self.tools() as (root, validator, _reader):
            args = ["--tasks", str(root / "tasks.json"), "--matter-dir", str(root / "matter"), "--json"]
            before = artefact_manifest(root)
            status, stdout, _ = self.cli(validator, args + ["--structure-only"])
            self.assertEqual(status, 0, stdout)
            report = json.loads(stdout)
            self.assertIs(report["schema_valid"], True)
            self.assertEqual(report["source_verification"]["status"], "checked", report)
            self.assert_pending(report)
            status, stdout, _ = self.cli(validator, args)
            self.assertNotEqual(status, 0, stdout)
            self.assert_pending(json.loads(stdout))
            self.assertEqual(artefact_manifest(root), before)

    def test_even_checked_sources_do_not_make_default_validation_ready(self):
        document = synthetic_document()
        with self.tools(document, judgment_for(document)) as (root, validator, _reader):
            status, stdout, _ = self.cli(validator, ["--tasks", str(root / "tasks.json"), "--matter-dir", str(root / "matter"), "--json"])
            self.assertNotEqual(status, 0)
            report = json.loads(stdout)
            self.assertEqual(report["source_verification"]["status"], "checked", report)
            self.assert_pending(report)

    def test_reader_cli_writes_only_requested_temporary_pending_output_in_utf8_lf(self):
        with self.tools() as (root, _validator, reader):
            output = root / "pending-review.md"
            before = artefact_manifest(root)
            status, stdout, stderr = self.cli(reader, ["--tasks", str(root / "tasks.json"), "--matter-dir", str(root / "matter"), "--output", str(output)])
            self.assertEqual(status, 0, stdout + stderr)
            self.assertTrue(output.is_file())
            blob = output.read_bytes()
            self.assertNotIn(b"\r", blob)
            self.assertTrue(blob.decode("utf-8").strip())
            after = artefact_manifest(root)
            after.pop("pending-review.md")
            self.assertEqual(after, before, "no default or unrelated output may be rewritten")

    def test_invalid_cli_input_is_nonzero_and_never_truncates_a_prior_checklist(self):
        for corrupt in (True, False):
            document = synthetic_document()
            document["tasks"][0]["rubric"][0]["id"] = ""
            with self.tools(document, corrupt_tasks=corrupt) as (root, validator, reader):
                output = root / "prior-review.md"
                output.write_text("Existing review must survive.\n", encoding="utf-8")
                before = artefact_manifest(root)
                base = ["--tasks", str(root / "tasks.json"), "--matter-dir", str(root / "matter")]
                for module, args in ((validator, base + ["--json", "--structure-only"]), (reader, base + ["--output", str(output)])):
                    status, _, _ = self.cli(module, args)
                    self.assertNotEqual(status, 0)
                self.assertEqual(artefact_manifest(root), before)


if __name__ == "__main__":
    unittest.main()
