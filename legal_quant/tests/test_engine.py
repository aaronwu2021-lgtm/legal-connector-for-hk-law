"""Semantic checks for model outputs, boundaries and evidence provenance."""

from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

from legal_quant import evaluate, get_model, list_models
from legal_quant.__main__ import main
from legal_quant.engine import _evaluate_expression, _validate_inputs


REMOVED_MODELS = {
    "alexy", "bayes", "deterrence", "coase", "settlement", "cover_damages",
    "present_value", "counterfactual_damage", "hhi", "alarp", "interim_injunction",
    "procedural_safeguards", "necessity", "penalty_proportionality",
}


class ModelCalculations(unittest.TestCase):
    def inputs(self, name, **updates):
        return {**get_model(name)["example_inputs"], **updates}

    def calculate(self, name, **updates):
        return evaluate(name, self.inputs(name, **updates))["results"]

    def test_all_examples_have_traces_and_no_legal_conclusion(self):
        models = list_models()
        self.assertEqual(len(models), 4)
        self.assertEqual({model["id"] for model in models}, {"hand", "alarp_probability", "reasonable_mitigation", "loss_of_chance"})
        for model in models:
            with self.subTest(model=model["id"]):
                response = evaluate(model["id"], model["example_inputs"])
                self.assertEqual(response["model_version"], "1")
                self.assertIsNone(response["legal_conclusion"])
                self.assertEqual(response["applicability_status"], "unreviewed")
                self.assertEqual(response["context"]["input_basis"], "hypothetical")
                self.assertIsNone(response["context"]["as_of"])
                self.assertEqual({step["id"]: step["value"] for step in response["steps"]}, response["results"])
                self.assertTrue(response["required_legal_findings"])
                json.dumps(response, allow_nan=False)

    def test_removed_models_are_unavailable_not_just_hidden(self):
        for name in REMOVED_MODELS:
            with self.subTest(model=name):
                with self.assertRaises(ValueError):
                    get_model(name)
                with self.assertRaises(ValueError):
                    evaluate(name, {})

    def test_hand_uses_avoided_not_entire_expected_loss(self):
        actual = self.calculate("hand")
        self.assertEqual(actual["expected_before"], 832000)
        self.assertEqual(actual["expected_after"], 332800)
        self.assertEqual(actual["avoided_expected_loss"], 499200)
        self.assertEqual(actual["net_benefit"], 379200)
        no_effect = self.calculate("hand", prob_reduction=0, severity_reduction=0)
        self.assertEqual(no_effect["net_benefit"], -120000)
        self.assertFalse(no_effect["economically_favourable"])

    def test_hand_full_severity_effect_and_equality(self):
        actual = self.calculate("hand", prob_reduction=0, severity_reduction=1, annual_B=832000)
        self.assertEqual(actual["expected_after"], 0)
        self.assertEqual(actual["net_benefit"], 0)
        self.assertFalse(actual["economically_favourable"])

    def test_hand_tiny_reduction_preserves_small_avoided_loss(self):
        actual = self.calculate("hand", N=1e9, p=0.1, L=1e9, annual_B=0,
                                prob_reduction=1e-18, severity_reduction=0)
        self.assertAlmostEqual(actual["avoided_expected_loss"], 0.1)
        self.assertTrue(actual["economically_favourable"])
        # At this scale the two displayed expected losses round to the same
        # binary64 value; subtracting them would incorrectly erase the benefit.
        self.assertEqual(actual["expected_before"], actual["expected_after"])
        severity = self.calculate("hand", N=1e9, p=0.1, L=1e9, annual_B=0,
                                  prob_reduction=0, severity_reduction=1e-18)
        self.assertAlmostEqual(severity["avoided_expected_loss"], 0.1)

    def test_loss_of_chance_values_probability_change(self):
        self.assertAlmostEqual(self.calculate("loss_of_chance")["chance_value"], 300000)
        self.assertEqual(self.calculate("loss_of_chance", probability_after=0.4)["chance_value"], 0)

    def test_money_scaling_preserves_hand_preference(self):
        base = self.calculate("hand")
        scaled = self.calculate("hand", L=208000, annual_B=240000)
        self.assertEqual(scaled["net_benefit"], 2 * base["net_benefit"])
        self.assertEqual(scaled["economically_favourable"], base["economically_favourable"])


class InputAndProvenance(unittest.TestCase):
    def inputs(self, name, **updates):
        return {**get_model(name)["example_inputs"], **updates}

    def test_unknown_model_and_version_rejected(self):
        for model, version in [("fake", "1"), ("hand", "2"), ("hand", 1)]:
            with self.subTest(model=model, version=version), self.assertRaises(ValueError):
                evaluate(model, self.inputs("hand"), model_version=version)

    def test_missing_unknown_and_bool_input_rejected(self):
        missing = self.inputs("hand")
        del missing["p"]
        bad = [missing, self.inputs("hand", formula="execute()"),
               self.inputs("hand", p=True), self.inputs("hand", p="0.1"), []]
        for inputs in bad:
            with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                evaluate("hand", inputs)

    def test_nonfinite_numbers_rejected(self):
        for number in [math.inf, -math.inf, math.nan, 10 ** 1000]:
            with self.subTest(number=str(number)[:25]), self.assertRaises(ValueError):
                evaluate("alarp_probability", self.inputs("alarp_probability", precaution_cost=number))

    def test_overflowing_intermediate_results_rejected(self):
        with self.assertRaises(ValueError):
            evaluate("hand", self.inputs("hand", N=1e308, p=1, L=1e308))

    def test_invalid_probability_ranges(self):
        for probability in [-0.001, 1.001]:
            with self.subTest(probability=probability), self.assertRaises(ValueError):
                evaluate("alarp_probability", self.inputs("alarp_probability", probability_before=probability))

    def test_nested_schema_validation_remains_available_for_generic_engine(self):
        # Synthetic schema, not an extra published legal model.
        fields = [{"id": "rows", "type": "object_array", "items": [
            {"id": "label", "type": "string"},
            {"id": "index", "type": "integer", "min": 0},
            {"id": "probability", "type": "number", "min": 0, "max": 1},
        ]}]
        row = {"label": "Synthetic", "index": 1, "probability": 0.5}
        _validate_inputs({"rows": [row]}, fields)
        for rows in [[], [dict(row, extra=1)], [{"label": "Synthetic", "index": 1}],
                     [dict(row, probability=True)], [dict(row, index=0.5)],
                     [dict(row, index=-1)], [dict(row, index=2 ** 53)],
                     [dict(row, label=" ")], [row] * 257]:
            with self.subTest(rows=rows[:1]), self.assertRaises(ValueError):
                _validate_inputs({"rows": rows}, fields)
        numeric = [{"id": "values", "type": "number_array", "min": 0, "max": 1}]
        for values in [[], [True], [-0.01], [1.01], [0] * 257]:
            with self.subTest(values=values[:2]), self.assertRaises(ValueError):
                _validate_inputs({"values": values}, numeric)

    def test_case_data_require_sources_for_every_top_level_input(self):
        for context in [
            {"input_basis": "case_data"},
            {"input_basis": "case_data", "sources": {"probability_before": "专家报告"}},
            {"input_basis": "case_data", "sources": {"probability_before": "专家报告", "precaution_cost": " "}},
        ]:
            with self.subTest(context=context), self.assertRaises(ValueError):
                evaluate("alarp_probability", self.inputs("alarp_probability"), context)
        context = {"input_basis": "case_data", "sources": {
            key: "Synthetic expert assumption, page 2" for key in self.inputs("alarp_probability")},
                   "jurisdiction": "HK", "as_of": "2026-10-24", "applicability": "externally_assessed"}
        result = evaluate("alarp_probability", self.inputs("alarp_probability"), context)
        self.assertEqual(result["context"], context)
        self.assertEqual(result["applicability_status"], "externally_assessed")
        self.assertIsNone(result["legal_conclusion"])

    def test_context_dates_values_and_unknown_sources(self):
        invalid = [
            {"as_of": "2025-02-29"}, {"as_of": "2026-2-1"}, {"as_of": "0000-01-01"},
            {"as_of": True}, {"jurisdiction": " "}, {"input_basis": "verified"},
            {"applicability": "automatically_approved"}, {"extra": "x"},
            {"sources": {"fake": "document"}}, {"sources": {"probability_before": None}},
        ]
        for context in invalid:
            with self.subTest(context=context), self.assertRaises(ValueError):
                evaluate("alarp_probability", self.inputs("alarp_probability"), context)
        result = evaluate("alarp_probability", self.inputs("alarp_probability"), {"as_of": "2024-02-29"})
        self.assertEqual(result["context"]["as_of"], "2024-02-29")

    def test_caller_input_and_catalogue_not_mutated(self):
        model = get_model("hand")
        inputs = deepcopy(model["example_inputs"])
        before = deepcopy(inputs)
        evaluate("hand", inputs)
        self.assertEqual(inputs, before)
        model["example_inputs"].clear()
        self.assertTrue(get_model("hand")["example_inputs"])


class InterpreterAndCLI(unittest.TestCase):
    def test_sequential_large_integer_sum_uses_binary64_at_each_step(self):
        expression = {"op": "add", "args": [10000000000000000, 1, 1]}
        self.assertEqual(_evaluate_expression(expression, {}), 1e16)
        self.assertEqual(_evaluate_expression({"op": "sub", "args": [9007199254740993, 9007199254740992]}, {}), 0)

    def test_generic_arrays_preserve_order_ties_and_binary64_accumulation(self):
        self.assertEqual(_evaluate_expression({"op": "argmin", "args": [[2, 1, 1, 3]]}, {}), [1, 2])
        self.assertEqual(_evaluate_expression({"op": "sum", "args": [[1e16, 1, 1]]}, {}), 1e16)
        self.assertEqual(_evaluate_expression({"op": "sum", "args": [[]]}, {}), 0)
        mapped = {"op": "map", "items": [3, 1, 2], "value": {"op": "mul", "args": [{"var": "item"}, 2]}}
        self.assertEqual(_evaluate_expression(mapped, {}), [6, 2, 4])
        self.assertEqual(_evaluate_expression({"op": "pow", "args": [2, 3]}, {}), 8)

    def test_lazy_if_does_not_evaluate_impossible_branch(self):
        expression = {"op": "if", "condition": True, "then": 9,
                      "else": {"op": "div", "args": [1, 0]}}
        self.assertEqual(_evaluate_expression(expression, {}), 9)

    def test_interpreter_has_no_eval_and_strict_path_lookups(self):
        for expression in [
            {"op": "eval", "args": ["__import__('os')"]},
            {"var": "input.__class__"},
            {"op": "div", "args": [1, 0]},
            {"op": "mul", "args": [True, 5]},
            {"op": "at", "args": [[1, 2], -1]},
        ]:
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                _evaluate_expression(expression, {"input": {}})
        self.assertFalse(_evaluate_expression({"op": "eq", "args": [1, True]}, {}))

    def test_cli_example_request_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            request_path = Path(directory) / "request.json"
            response_path = Path(directory) / "response.json"
            self.assertEqual(main(["example", "loss_of_chance", "--output", str(request_path)]), 0)
            self.assertEqual(main(["evaluate", "--input", str(request_path), "--output", str(response_path)]), 0)
            response = json.loads(response_path.read_text(encoding="utf-8"))
            self.assertAlmostEqual(response["results"]["chance_value"], 300000)
            self.assertIsNone(response["legal_conclusion"])

    def test_cli_rejects_duplicate_nan_null_context_and_formula_injection(self):
        base = {"model_id": "hand", "model_version": "1", "inputs": get_model("hand")["example_inputs"]}
        requests = [
            '{"model_id":"hand","model_id":"loss_of_chance","model_version":"1","inputs":{}}',
            json.dumps({**base, "inputs": {**base["inputs"], "p": math.nan}}),
            json.dumps({**base, "context": None}),
            json.dumps({**base, "formula": "1"}),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            for request in requests:
                with self.subTest(request=request):
                    path.write_text(request, encoding="utf-8")
                    with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                        self.assertEqual(main(["evaluate", "--input", str(path)]), 2)


if __name__ == "__main__":
    unittest.main()
