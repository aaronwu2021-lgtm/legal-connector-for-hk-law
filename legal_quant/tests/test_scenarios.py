"""Tests for scenario arithmetic and rejection of misleading inputs."""

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
import unittest
from unittest.mock import patch

from legal_quant.scenarios import evaluate, main


class ScenarioCalculations(unittest.TestCase):
    def test_selected_risk_is_joint_contribution_not_conditional_mean(self):
        outcome = evaluate("risk_distribution", {"rows": [
            {"p": 0.8, "loss": 10}, {"p": 0.2, "loss": 100, "selected": True},
        ]})
        self.assertEqual(outcome["results"], {
            "expected_loss": 28, "selected_probability": 0.2, "selected_expected_loss": 20,
        })
        self.assertIsNone(outcome["legal_conclusion"])
        self.assertEqual(outcome["input_basis"], "explicit_scenarios_not_case_findings")

    def test_paired_outcomes_preserve_negative_effects_and_scope(self):
        result = evaluate("paired_counterfactual", {"rows": [
            {"p": 0.25, "actual_loss": 100, "compliant_loss": 0, "in_scope": True},
            {"p": 0.75, "actual_loss": 0, "compliant_loss": 80, "in_scope": False},
        ]})["results"]
        self.assertEqual(result, {"actual_expected_loss": 25, "compliant_expected_loss": 60,
                                 "signed_difference": -35, "in_scope_signed_difference": 25,
                                 "actual_harm_probability": 0.25, "compliant_harm_probability": 0.75})

    def test_precaution_carries_counter_risk_and_cost_once(self):
        result = evaluate("precaution_comparison", {"cost": 5, "rows": [
            {"p": 0.5, "current_loss": 100, "alternative_loss": 0},
            {"p": 0.5, "current_loss": 0, "alternative_loss": 80},
        ]})["results"]
        self.assertEqual(result, {"current_expected_loss": 50, "alternative_expected_loss": 40,
                                 "avoided_expected_loss": 10, "net_benefit": 5})
        negative = evaluate("precaution_comparison", {"cost": 0, "rows": [
            {"p": 1, "current_loss": 0, "alternative_loss": 80},
        ]})["results"]
        self.assertEqual(negative["net_benefit"], -80)

    def test_cap_insurance_and_resources_use_same_capped_liability(self):
        inputs = {"cap": 100, "insurance_limit": 50, "insurance_deductible": 20, "resources": 50,
                  "rows": [{"p": 0.25, "loss": 200, "insurable": True},
                           {"p": 0.25, "loss": 80, "insurable": False},
                           {"p": 0.5, "loss": 10, "insurable": True}]}
        result = evaluate("liability_cap", inputs)["results"]
        self.assertEqual(result, {
            "expected_uncapped_liability": 75, "expected_capped_liability": 50,
            "expected_transferred_to_claimant": 25, "expected_insurer_payment": 12.5,
            "expected_provider_retained": 37.5, "resource_shortfall_probability": 0.25,
        })
        self.assertEqual(result["expected_uncapped_liability"],
                         result["expected_transferred_to_claimant"] + result["expected_insurer_payment"] + result["expected_provider_retained"])

    def test_zero_cap_and_zero_resources_do_not_divide_by_zero(self):
        result = evaluate("liability_cap", {"cap": 0, "insurance_limit": 0, "insurance_deductible": 0,
                         "resources": 0, "rows": [{"p": 1, "loss": 100, "insurable": True}]})["results"]
        self.assertEqual(result["expected_transferred_to_claimant"], 100)
        self.assertEqual(result["expected_provider_retained"], 0)
        self.assertEqual(result["resource_shortfall_probability"], 0)

    def test_deadline_includes_exact_boundary_but_does_not_set_reasonableness(self):
        result = evaluate("timely_performance", {"deadline": 5, "rows": [
            {"p": 0.2, "duration": 0}, {"p": 0.3, "duration": 5}, {"p": 0.5, "duration": 10},
        ]})
        self.assertEqual(result["results"], {"probability_by_deadline": 0.5, "expected_duration": 6.5})
        self.assertIsNone(result["legal_conclusion"])

    def test_execution_keeps_negative_proceeds_and_signed_gap(self):
        inputs = {"quantity": 2, "cost": 25, "actual_net_proceeds": -3,
                  "rows": [{"p": 0.5, "price": 8}, {"p": 0.5, "price": 12}]}
        original = deepcopy(inputs)
        result = evaluate("execution_value", inputs)["results"]
        self.assertEqual(result, {"expected_compliant_net_proceeds": -5, "signed_gap": -2})
        self.assertEqual(inputs, original)


class ScenarioValidation(unittest.TestCase):
    def valid(self):
        return {"rows": [{"p": 1, "loss": 10, "selected": False}]}

    def test_distribution_not_normalized(self):
        for probabilities in ([0.2, 0.7], [0, 0], [1.1, -0.1]):
            with self.subTest(probabilities=probabilities), self.assertRaises(ValueError):
                evaluate("risk_distribution", {"rows": [{"p": p, "loss": 1} for p in probabilities]})
        result = evaluate("risk_distribution", {"rows": [{"p": 0.9999999995, "loss": 1}]})
        self.assertEqual(result["results"]["expected_loss"], 0.9999999995)

    def test_missing_extra_and_nonobject_inputs(self):
        for inputs in (None, [], {}, {"rows": []}, {"rows": {}}, {"rows": [1]},
                       {"rows": [{"p": 1}]}, {"rows": [{"p": 1, "loss": 2, "unknown": 3}]},
                       {"rows": [{"p": 1, "loss": 2}], "unknown": 3}):
            with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                evaluate("risk_distribution", inputs)
        with self.assertRaisesRegex(ValueError, "unknown scenario"):
            evaluate("win_probability", self.valid())

    def test_booleans_nonfinite_negative_and_strings_rejected_as_numbers(self):
        for field in ("p", "loss"):
            for value in (True, False, float("nan"), float("inf"), -1, "1", None, 10 ** 400):
                inputs = self.valid()
                inputs["rows"][0][field] = value
                with self.subTest(field=field, value=str(value)), self.assertRaises(ValueError):
                    evaluate("risk_distribution", inputs)
        for value in (True, -1, float("inf")):
            with self.subTest(cost=value), self.assertRaises(ValueError):
                evaluate("execution_value", {"rows": [{"p": 1, "price": 1}], "quantity": 1,
                                           "cost": value, "actual_net_proceeds": 0})

    def test_flags_are_real_booleans_and_required_where_legal_scope_matters(self):
        for value in (0, 1, "true", None):
            inputs = self.valid()
            inputs["rows"][0]["selected"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                evaluate("risk_distribution", inputs)
        with self.assertRaisesRegex(ValueError, "in_scope"):
            evaluate("paired_counterfactual", {"rows": [{"p": 1, "actual_loss": 1, "compliant_loss": 0}]})
        with self.assertRaisesRegex(ValueError, "insurable"):
            evaluate("liability_cap", {"rows": [{"p": 1, "loss": 1}], "cap": 1,
                     "insurance_limit": 1, "insurance_deductible": 0, "resources": 1})

    def test_overflow_is_explicit_error_instead_of_infinite_result(self):
        with self.assertRaisesRegex(ValueError, "overflow"):
            evaluate("execution_value", {"rows": [{"p": 1, "price": 1e308}],
                     "quantity": 1e308, "cost": 0, "actual_net_proceeds": 0})

    def run_cli(self, raw):
        output, error = io.StringIO(), io.StringIO()
        with patch("sys.stdin", io.StringIO(raw)), redirect_stdout(output), redirect_stderr(error):
            code = main(["risk_distribution", "-"])
        return code, output.getvalue(), error.getvalue()

    def test_cli_json_round_trip(self):
        code, output, error = self.run_cli(json.dumps(self.valid()))
        self.assertEqual(code, 0)
        self.assertEqual(error, "")
        self.assertEqual(json.loads(output)["results"]["expected_loss"], 10)

    def test_cli_rejects_duplicate_nonfinite_and_invalid_json_without_traceback(self):
        for raw in ('{"rows": [], "rows": []}', '{"rows": [{"p": 1, "loss": NaN}]}',
                    '{"rows": [{"p": 1, "p": 0, "loss": 1}]}', '{bad', '[]'):
            with self.subTest(raw=raw):
                code, output, error = self.run_cli(raw)
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertIn("Error:", error)
                self.assertNotIn("Traceback", error)


if __name__ == "__main__":
    unittest.main()
