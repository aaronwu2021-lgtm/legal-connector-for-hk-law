"""Exercise real builds and injected failures only in ordinary temporary copies."""
import importlib.util
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[2]


class BuildReproducibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Discovery imports no checker or builder. Even the checker helper module
        # is loaded from a copied file; its children have a separate audit guard.
        temporary = tempfile.TemporaryDirectory(prefix="doctrine-checker-test-")
        cls.addClassCleanup(temporary.cleanup)
        cls.loader_root = Path(temporary.name).resolve()
        if cls.loader_root.is_relative_to(REPO):
            raise AssertionError("temporary module copy is inside the original repository")
        copied = cls.loader_root / "scripts/check_build.py"
        copied.parent.mkdir(parents=True)
        copied.write_bytes((REPO / "scripts/check_build.py").read_bytes())
        spec = importlib.util.spec_from_file_location("copied_build_checker", copied)
        cls.checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.checker)
        if Path(cls.checker.__file__).resolve() != copied:
            raise AssertionError("checker was not loaded from the copy")
        cls.protected = cls.checker.protected_manifest(REPO)
        cls.addClassCleanup(cls.assert_original_unchanged)
        cls.inputs, missing = cls.checker.capture_inputs(REPO, experiments=True)
        if missing:
            raise AssertionError("test source inputs missing: " + repr(missing))
        cls.baseline = {p: (REPO / p).read_bytes() for p in cls.checker.OUTPUTS}
        # This is the sole full-build group: all four core runs and optional
        # experiments are orchestrated inside guarded, disposable copies.
        cls.report = cls.checker.check(REPO, experiments=True)
        core = cls.report["core"]
        evidence = {
            "input_sha256": cls.report["input_sha256"],
            "core_ok": core["ok"], "deterministic": core.get("deterministic"),
            "comparison": core.get("comparison"), "provenance": core.get("provenance"),
            "baseline": cls.report["baseline"],
            "bands": core.get("bands"),
            "hash_seed_ok": {k: v["ok"] for k, v in core.get("hash_seeds", {}).items()},
            "experiments": {g: {"ok": r["ok"], "comparison": r["comparison"],
                "failed_stages": [s for s in r["stages"] if s["returncode"]]}
                for g, r in cls.report["experiments"].items()},
            "overall_ok": cls.report["overall_ok"],
            "original_unchanged": cls.report["original_unchanged"],
        }
        print("BUILD_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True), flush=True)

    @classmethod
    def assert_original_unchanged(cls):
        if cls.checker.protected_manifest(REPO) != cls.protected:
            raise AssertionError("original protected artefacts changed")

    def copy_workspace(self, baselines=True):
        temporary = tempfile.TemporaryDirectory(prefix="doctrine-failure-test-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        self.checker.materialize(root, REPO, self.inputs)
        if baselines:
            for relative, blob in self.baseline.items():
                path = self.checker.require_copy(root / relative, root, REPO)
                path.write_bytes(blob)
        return root

    def inject(self, root, relative, old, new):
        path = self.checker.require_copy(root / relative, root, REPO)
        body = path.read_text(encoding="utf-8")
        self.assertEqual(body.count(old), 1)
        path.write_text(body.replace(old, new, 1), encoding="utf-8", newline="\n")

    def assert_stage_failure(self, root, script, message):
        result = self.checker.run_stage(root, REPO, script)
        self.assertNotEqual(result["returncode"], 0, result)
        self.assertIn(message, result["stderr"])
        self.assertNotIn("tiered factors:", result["stdout"])
        return result

    def test_ordered_core_pairs_bands_and_repeated_bytes(self):
        core = self.report["core"]
        self.assertTrue(core["ok"], core)
        self.assertEqual([s["script"] for s in core["stages"]], list(self.checker.CORE))
        self.assertEqual(len(core["pairs"]), 5)
        self.assertTrue(all(p["equal"] for p in core["pairs"].values()))
        self.assertTrue(core["bands"]["ok"], core["bands"])
        self.assertTrue(all(n > 0 for n in core["bands"]["counts"].values()))
        self.assertTrue(core["repeat"]["ok"])
        self.assertTrue(core["deterministic"])

    def test_fresh_hash_seed_copies_match(self):
        seeds = self.report["core"]["hash_seeds"]
        self.assertEqual(set(seeds), {"1", "2"})
        self.assertTrue(all(r["ok"] for r in seeds.values()))
        self.assertEqual(seeds["1"]["output_sha256"], seeds["2"]["output_sha256"])

    def test_real_provenance_gaps_are_closed_without_clearing_independent_review(self):
        provenance = self.report["core"]["provenance"]
        self.assertTrue(provenance["ok"], provenance)
        self.assertEqual(provenance["issues"], [])
        self.assertFalse(self.report["overall_ok"])
        self.assertTrue(self.report["original_unchanged"])
        self.assertTrue(self.report["baseline"]["provenance"]["ok"])

    def test_baseline_drift_has_separate_categories(self):
        compare = self.checker.compare_output
        self.assertEqual(compare(b'{"a":1}', b'{ "a": 1 }', 'x.json')["status"], "serialization_drift")
        changed = compare(b'{"a":1}', b'{"a":2}', 'x.json')
        self.assertEqual(changed["status"], "semantic_drift")
        self.assertEqual(changed["changed_paths"], ["$.a"])
        self.assertEqual(len(self.report["core"]["comparison"]), 10)
        for result in self.report["core"]["comparison"].values():
            self.assertIn("baseline_sha256", result)
            self.assertIn("built_sha256", result)

    def test_provenance_is_per_occurrence_without_borrowed_evidence(self):
        objects = {"synthetic": {"jurisdictions": {"HK": {"cases": [
            {"case": "Same case", "verified": "quoted", "pin": "[7]"},
            {"case": "Same case", "verified": "verified-quoted", "pin": "[7]", "src": "Quoting judgment [9]"},
            {"verified": "primary", "source": "Judgment"},
            {"verified": "verified-primary", "pin": "[2]"},
            {"verified": "quoted", "pin": "[3]", "source": {"note": "A quotation is mentioned"}},
            {"verified": "quoted", "pin": "[4]", "source": {"cite": "[2020] TEST 1"}},
            {"verified": "web"},
            {"case": "Same case", "eff": "Undeclared timeline event"},
        ]}}}}
        result = self.checker.provenance(objects)
        self.assertEqual(result["counts"]["synthetic"], 7)
        self.assertEqual({i["path"] for i in result["issues"]}, {
            "synthetic:$.jurisdictions.HK.cases[0].source",
            "synthetic:$.jurisdictions.HK.cases[2].pin",
            "synthetic:$.jurisdictions.HK.cases[4].source",
        })
        self.assertNotIn("source", objects["synthetic"]["jurisdictions"]["HK"]["cases"][0])

    def test_invalid_verification_and_non_json_constants_fail(self):
        for value in (42, None, "verified-maybe", "verified-verified-primary"):
            with self.subTest(value=value):
                result = self.checker.provenance({"synthetic": {"verified": value}})
                self.assertFalse(result["ok"])
                self.assertEqual(result["issues"][0]["issue"], "invalid_verification_level")
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.checker.parse_output(('{"v":' + value + '}').encode(), "x.json")
                with self.assertRaises(ValueError):
                    self.checker.parse_output(('export default {"v":' + value + '};').encode(), "x.mjs")

    def test_serialization_and_utf8_failures_preserve_both_outputs(self):
        for expression in ("object()", "float('nan')", "'\\ud800'"):
            with self.subTest(expression=expression):
                root = self.copy_workspace()
                self.inject(root, "scripts/build_scored.py", "    emit('scored', W, indent=1)",
                    "    W['injected_invalid'] = " + expression + "\n    emit('scored', W, indent=1)")
                before = self.checker.output_bytes(root)
                result = self.checker.run_stage(root, REPO, "scripts/build_scored.py")
                self.assertNotEqual(result["returncode"], 0, result)
                self.assertEqual(self.checker.output_bytes(root), before)

    def test_second_serialization_failure_preserves_first_output_too(self):
        root = self.copy_workspace()
        self.inject(root, "scripts/_paths.py", '    module = ("export default "',
            '    raise ValueError("injected second serialization failure")\n    module = ("export default "')
        before = self.checker.output_bytes(root)
        self.assert_stage_failure(root, "scripts/build_scored.py", "injected second serialization failure")
        self.assertEqual(self.checker.output_bytes(root), before)

    def test_second_publication_failure_remains_visible_and_pair_mismatches(self):
        root = self.copy_workspace()
        self.inject(root, "scripts/_paths.py", '    with open(mjs, "wb") as f:',
            '    raise OSError("injected second publication failure")\n    with open(mjs, "wb") as f:')
        before = self.checker.output_bytes(root)
        self.assert_stage_failure(root, "scripts/build_scored.py", "injected second publication failure")
        after = self.checker.output_bytes(root)
        self.assertNotEqual(after["data/scored.json"], before["data/scored.json"])
        for path in before:
            if path != "data/scored.json": self.assertEqual(after[path], before[path], path)
        pairs, _ = self.checker.inspect_pairs(root)
        self.assertFalse(pairs["scored"]["equal"])

    def test_missing_tier_in_second_dataset_publishes_neither(self):
        root = self.copy_workspace()
        path = root / "data/registry.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        stage = next(s for m in registry["modules"] for s in m["stages"] if s["test_type"] == "balancing")
        stage["factors"].append({"id": "INJECTED-NO-TIER", "weight": 0.1})
        path.write_text(json.dumps(registry), encoding="utf-8")
        before = self.checker.output_bytes(root)
        self.assert_stage_failure(root, "scripts/apply_tiers.py", "INJECTED-NO-TIER: missing tier")
        self.assertEqual(self.checker.output_bytes(root), before)

    def test_regression_weights_cannot_be_silently_overwritten(self):
        root = self.copy_workspace()
        path = root / "data/registry.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        stage = next(s for m in registry["modules"] for s in m["stages"] if s["test_type"] == "balancing")
        stage["factors"][0]["weight_source"] = "regression"
        path.write_text(json.dumps(registry), encoding="utf-8")
        before = self.checker.output_bytes(root)
        self.assert_stage_failure(root, "scripts/apply_tiers.py", "regression weights cannot be replaced")
        self.assertEqual(self.checker.output_bytes(root), before)

    def test_missing_persuasive_source_stops_group_without_replacing_outputs(self):
        root = self.copy_workspace()
        (root / "data/sources/uklr/llms-cases.txt").unlink()
        before = self.checker.output_bytes(root)
        result = self.checker.run_order(root, REPO, ("scripts/build_persuasive.py", "scripts/check_persuasive.py"))
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["stages"]), 1)
        self.assertIn("llms-cases.txt", result["stages"][0]["stderr"])
        self.assertEqual(self.checker.output_bytes(root), before)

    def test_original_execution_and_network_are_blocked(self):
        with self.assertRaises(ValueError):
            self.checker.run_stage(REPO, REPO, "scripts/build_scored.py")
        root = self.copy_workspace()
        self.inject(root, "scripts/build_scored.py", "    emit('scored', W, indent=1)",
                    "    import socket\n    socket.socket()\n    emit('scored', W, indent=1)")
        before = self.checker.output_bytes(root)
        self.assert_stage_failure(root, "scripts/build_scored.py", "network/process operation forbidden")
        self.assertEqual(self.checker.output_bytes(root), before)

    def test_exp2_absolute_path_from_empty_cwd_is_anchored_and_utf8(self):
        root = self.copy_workspace(baselines=False)
        result = self.checker.run_stage(root, REPO, "experiments/exp2-probe/build_probe.py")
        self.assertEqual(result["returncode"], 0, result)
        self.assertEqual(list((root / "empty-cwd").iterdir()), [])
        for name in ("probe.json", "probe_questions.json"):
            blob = (root / "experiments/exp2-probe" / name).read_bytes()
            self.assertNotIn(b"\r\n", blob)
            self.assertTrue(json.loads(blob.decode("utf-8"))["items"])

    def test_optional_experiments_report_real_archive_and_schema_results(self):
        groups = self.report["experiments"]
        self.assertTrue(groups["exp2-probe"]["ok"], groups["exp2-probe"])
        self.assertEqual(len(groups["exp2-probe"]["comparison"]), 2)
        exp4 = groups["exp4-cfa"]
        self.assertFalse(exp4["ok"])
        self.assertEqual(exp4["stages"][-1]["script"], "experiments/exp4-cfa/validate_tasks.py")
        self.assertNotEqual(exp4["stages"][-1]["returncode"], 0)
        # 05a replaced the historical KeyError with an honest full-readiness
        # report. Keep the old outcome in its frozen acceptance document.
        validation = exp4["stages"][-1]
        self.assertEqual(validation["stderr"], "")
        self.assertIn("Structure: valid", validation["stdout"])
        self.assertIn("Source verification: checked", validation["stdout"])
        self.assertIn("Independent reader sign-off: pending", validation["stdout"])
        self.assertIn("Proposition support: not verified", validation["stdout"])
        self.assertIn("Experiment readiness: incomplete", validation["stdout"])
        self.assertFalse(self.report["overall_ok"])

    def test_cli_returns_failure_for_real_integrity_report(self):
        # Exercise only the CLI/report adapter, reusing the real isolated result.
        # Re-running four full builds here would not test additional behavior.
        original_check = self.checker.check
        self.checker.check = lambda **kwargs: self.report
        try:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = self.checker.main(["--experiments", "--json"])
            self.assertEqual(code, 1)
            self.assertFalse(json.loads(output.getvalue())["overall_ok"])
        finally:
            self.checker.check = original_check


if __name__ == "__main__":
    unittest.main()
