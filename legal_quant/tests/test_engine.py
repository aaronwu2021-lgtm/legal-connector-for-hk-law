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
from legal_quant.engine import _evaluate_expression


class ModelCalculations(unittest.TestCase):
    def inputs(self, name, **updates):
        return {**get_model(name)["example_inputs"], **updates}

    def calculate(self, name, **updates):
        return evaluate(name, self.inputs(name, **updates))["results"]

    def test_all_examples_have_traces_and_no_legal_conclusion(self):
        models = list_models()
        self.assertEqual(len(models), 17)
        self.assertEqual(len({model["id"] for model in models}), 17)
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

    def test_alexy_ratio_is_not_bounded_as_a_probability(self):
        actual = self.calculate("alexy", I_i=4, W_i=4, R_i=1, I_j=1, W_j=1, R_j=0.25)
        self.assertEqual(actual["weight_ratio"], 64)
        self.assertEqual(self.calculate("alexy")["weight_ratio"], 1)

    def test_bayes_known_posterior_and_neutral_evidence(self):
        self.assertAlmostEqual(self.calculate("bayes")["posterior"], 2 / 3)
        for prior in [0, 0.01, 0.2, 0.8, 1]:
            with self.subTest(prior=prior):
                self.assertAlmostEqual(self.calculate("bayes", prior=prior, likelihood_ratio=1)["posterior"], prior)

    def test_bayes_stronger_evidence_increases_posterior(self):
        values = [self.calculate("bayes", likelihood_ratio=lr)["posterior"] for lr in [0, 0.5, 1, 2, 8]]
        self.assertEqual(values, sorted(values))
        self.assertEqual(values[0], 0)

    def test_deterrence_benchmark_and_full_enforcement(self):
        self.assertEqual(self.calculate("deterrence")["benchmark_sanction"], 500000)
        self.assertEqual(self.calculate("deterrence")["expected_sanction"], 100000)
        self.assertEqual(self.calculate("deterrence", sanction_probability=1)["benchmark_sanction"], 100000)

    def test_coase_counts_all_costs_and_preserves_ties(self):
        actual = self.calculate("coase")
        self.assertEqual(actual["total_costs"], [40000, 90000, 100000])
        self.assertEqual(actual["minimum_indices"], [0])
        candidates = self.inputs("coase")["alternatives"]
        candidates.append({**candidates[0], "name": "另一同价方案"})
        tied = self.calculate("coase", alternatives=candidates)
        self.assertEqual(tied["minimum_indices"], [0, 3])

    def test_settlement_overlap_gap_and_negative_reservation(self):
        actual = self.calculate("settlement")
        self.assertEqual((actual["lower"], actual["upper"], actual["overlap"]), (500000, 600000, True))
        gap = self.calculate("settlement", plaintiff_probability=0.9, defendant_probability=0.1)
        self.assertEqual((gap["interval_width"], gap["overlap"]), (-550000, False))
        negative = self.calculate("settlement", plaintiff_probability=0)
        self.assertEqual(negative["lower"], -150000)

    def test_cover_value_and_negative_difference_are_preserved(self):
        self.assertEqual(self.calculate("cover_damages")["net_amount"], 45000)
        actual = self.calculate("cover_damages", replacement_price=80000, other_losses=0, saved_costs=0)
        self.assertEqual(actual["raw_difference"], -20000)
        self.assertEqual(actual["net_amount"], -20000)

    def test_python_integer_inputs_follow_binary64_calculation(self):
        # Both prices round to 2**53 as JavaScript numbers. Python must not use
        # arbitrary-precision subtraction and claim a spurious unit difference.
        actual = self.calculate("cover_damages", replacement_price=9007199254740993,
                                contract_price=9007199254740992, other_losses=0, saved_costs=0)
        self.assertEqual(actual["raw_difference"], 0)
        self.assertEqual(actual["net_amount"], 0)

    def test_loss_of_chance_values_probability_change(self):
        self.assertAlmostEqual(self.calculate("loss_of_chance")["chance_value"], 300000)
        self.assertEqual(self.calculate("loss_of_chance", probability_after=0.4)["chance_value"], 0)

    def test_present_value_and_zero_discount(self):
        self.assertAlmostEqual(self.calculate("present_value")["present_value"], 268996.7393502677)
        self.assertEqual(self.calculate("present_value", discount_rate=0)["present_value"], 285000)
        immediate = self.calculate("present_value", cashflows=[{"amount": 100, "year": 0, "probability": 0.5}])
        self.assertEqual(immediate["present_value"], 50)

    def test_higher_discount_lowers_present_value(self):
        low = self.calculate("present_value", discount_rate=0.01)["present_value"]
        high = self.calculate("present_value", discount_rate=0.1)["present_value"]
        self.assertGreater(low, high)

    def test_counterfactual_transfers_and_volume_loss(self):
        actual = self.calculate("counterfactual_damage")
        self.assertEqual(actual["gross_overcharge"], 200000)
        self.assertEqual(actual["net_damage"], 160000)
        fully_passed = self.calculate("counterfactual_damage", passed_on=200000, volume_lost_profit=0)
        self.assertEqual(fully_passed["net_damage"], 0)

    def test_hhi_known_values_and_merger_identity(self):
        actual = self.calculate("hhi")
        self.assertEqual(actual, {"pre_hhi": 3000, "delta_hhi": 400, "post_hhi": 3400})
        for shares, a, b in [([50, 50], 0, 1), ([20, 20, 20, 20, 20], 1, 4), ([99, 1, 0], 0, 2)]:
            actual = self.calculate("hhi", shares=shares, merger_index_a=a, merger_index_b=b)
            merged = [share for i, share in enumerate(shares) if i not in (a, b)] + [shares[a] + shares[b]]
            self.assertEqual(actual["post_hhi"], sum(share ** 2 for share in merged))

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
        bad = [
            {"prior": 0.2},
            {"prior": 0.2, "likelihood_ratio": 8, "formula": "execute()"},
            {"prior": True, "likelihood_ratio": 8},
            {"prior": 0.2, "likelihood_ratio": "8"},
            [],
        ]
        for inputs in bad:
            with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                evaluate("bayes", inputs)

    def test_nonfinite_numbers_rejected(self):
        for number in [math.inf, -math.inf, math.nan, 10 ** 1000]:
            with self.subTest(number=str(number)[:25]), self.assertRaises(ValueError):
                evaluate("bayes", self.inputs("bayes", likelihood_ratio=number))

    def test_overflowing_intermediate_results_rejected(self):
        with self.assertRaises(ValueError):
            evaluate("hand", self.inputs("hand", N=1e308, p=1, L=1e308))
        with self.assertRaises(ValueError):
            evaluate("present_value", self.inputs("present_value", discount_rate=1e308))

    def test_invalid_probability_ranges(self):
        for probability in [-0.001, 1.001]:
            with self.subTest(probability=probability), self.assertRaises(ValueError):
                evaluate("bayes", self.inputs("bayes", prior=probability))

    def test_alexy_only_uses_declared_grades(self):
        for key, value in [("I_i", 3), ("R_i", 0), ("R_i", 0.75)]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                evaluate("alexy", self.inputs("alexy", **{key: value}))

    def test_zero_bayes_denominator_and_enforcement_probability(self):
        with self.assertRaises(ValueError):
            evaluate("bayes", self.inputs("bayes", prior=1, likelihood_ratio=0))
        with self.assertRaises(ValueError):
            evaluate("deterrence", self.inputs("deterrence", sanction_probability=0))

    def test_nested_missing_unknown_bool_and_empty_arrays(self):
        for cashflows in [
            [],
            [{"amount": 10, "probability": 1}],
            [{"amount": 10, "year": 1, "probability": 1, "x": 2}],
            [{"amount": True, "year": 1, "probability": 1}],
            [{"amount": 10, "year": 0.5, "probability": 1}],
            [{"amount": 10, "year": -1, "probability": 1}],
        ]:
            with self.subTest(cashflows=cashflows), self.assertRaises(ValueError):
                evaluate("present_value", self.inputs("present_value", cashflows=cashflows))

    def test_chance_and_counterfactual_cross_field_constraints(self):
        for name, updates in [
            ("loss_of_chance", {"probability_after": 0.5}),
            ("counterfactual_damage", {"actual_price": 90}),
            ("counterfactual_damage", {"passed_on": 200001}),
        ]:
            with self.subTest(name=name, updates=updates), self.assertRaises(ValueError):
                evaluate(name, self.inputs(name, **updates))

    def test_hhi_rejects_bad_sum_self_merger_and_bad_index(self):
        for updates in [
            {"shares": [40, 30, 20, 9]},
            {"shares": [0.4, 0.3, 0.2, 0.1]},
            {"shares": [True, 99]},
            {"merger_index_a": 3, "merger_index_b": 3},
            {"merger_index_a": -1},
            {"merger_index_b": 4},
            {"merger_index_a": 0.5},
            {"merger_index_a": 10 ** 20},
        ]:
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                evaluate("hhi", self.inputs("hhi", **updates))

    def test_case_data_require_sources_for_every_top_level_input(self):
        for context in [
            {"input_basis": "case_data"},
            {"input_basis": "case_data", "sources": {"prior": "专家报告"}},
            {"input_basis": "case_data", "sources": {"prior": "专家报告", "likelihood_ratio": " "}},
        ]:
            with self.subTest(context=context), self.assertRaises(ValueError):
                evaluate("bayes", self.inputs("bayes"), context)
        context = {"input_basis": "case_data", "sources": {"prior": "专家假设第2页", "likelihood_ratio": "鉴定报告第5页"},
                   "jurisdiction": "HK", "as_of": "2026-10-20", "applicability": "externally_assessed"}
        result = evaluate("bayes", self.inputs("bayes"), context)
        self.assertEqual(result["context"], context)
        self.assertEqual(result["applicability_status"], "externally_assessed")
        self.assertIsNone(result["legal_conclusion"])

    def test_context_dates_values_and_unknown_sources(self):
        invalid = [
            {"as_of": "2025-02-29"}, {"as_of": "2026-2-1"}, {"as_of": "0000-01-01"},
            {"as_of": True}, {"jurisdiction": " "}, {"input_basis": "verified"},
            {"applicability": "automatically_approved"}, {"extra": "x"},
            {"sources": {"fake": "document"}}, {"sources": {"prior": None}},
        ]
        for context in invalid:
            with self.subTest(context=context), self.assertRaises(ValueError):
                evaluate("bayes", self.inputs("bayes"), context)
        result = evaluate("bayes", self.inputs("bayes"), {"as_of": "2024-02-29"})
        self.assertEqual(result["context"]["as_of"], "2024-02-29")

    def test_caller_input_and_catalogue_not_mutated(self):
        model = get_model("coase")
        inputs = deepcopy(model["example_inputs"])
        before = deepcopy(inputs)
        evaluate("coase", inputs)
        self.assertEqual(inputs, before)
        model["example_inputs"]["alternatives"].clear()
        self.assertTrue(get_model("coase")["example_inputs"]["alternatives"])


class InterpreterAndCLI(unittest.TestCase):
    def test_sequential_large_integer_sum_uses_binary64_at_each_step(self):
        expression = {"op": "add", "args": [10000000000000000, 1, 1]}
        self.assertEqual(_evaluate_expression(expression, {}), 1e16)
        self.assertEqual(_evaluate_expression({"op": "sub", "args": [9007199254740993, 9007199254740992]}, {}), 0)

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
            self.assertEqual(main(["example", "hhi", "--output", str(request_path)]), 0)
            self.assertEqual(main(["evaluate", "--input", str(request_path), "--output", str(response_path)]), 0)
            response = json.loads(response_path.read_text(encoding="utf-8"))
            self.assertEqual(response["results"]["post_hhi"], 3400)
            self.assertIsNone(response["legal_conclusion"])

    def test_cli_rejects_duplicate_nan_null_context_and_formula_injection(self):
        requests = [
            '{"model_id":"bayes","model_id":"hhi","model_version":"1","inputs":{}}',
            '{"model_id":"bayes","model_version":"1","inputs":{"prior":NaN,"likelihood_ratio":8}}',
            '{"model_id":"bayes","model_version":"1","inputs":{"prior":0.2,"likelihood_ratio":8},"context":null}',
            '{"model_id":"bayes","model_version":"1","inputs":{"prior":0.2,"likelihood_ratio":8},"formula":"1"}',
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
