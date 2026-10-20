import copy
import json
from pathlib import Path
import unittest

from assessment import (
    assess, association_comparison, calculate_damages, evaluate_declared_path,
    observed_frequency, quantify_observations,
)


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.case = json.loads(Path(__file__).with_name("example_case.json").read_text(encoding="utf-8"))

    def test_economic_support_never_resolves_unknown_law(self):
        result = assess(self.case, draws=40)
        self.assertEqual(result["legal"]["state"], "unresolved")
        self.assertIsNone(result["claimant_damages"]["legally_payable_amount"])
        self.assertAlmostEqual(result["claimant_damages"]["conditional_net_damages"]["mode"], 264000)
        self.assertAlmostEqual(result["risk"]["point_estimate"]["baseline_expected_loss_annual"], 832000)

    def test_missing_loss_or_apportionment_is_not_zero(self):
        damages = copy.deepcopy(self.case["damages"])
        damages["contributory_fraction"]["amount"] = None
        self.assertIsNone(calculate_damages(damages)["conditional_net_damages"])
        damages = copy.deepcopy(self.case["damages"])
        damages["components"].pop()
        self.assertIn("非财产损害情景", calculate_damages(damages)["missing"])

    def test_zero_events_still_has_positive_upper_bound(self):
        result = observed_frequency({"exposures": 1000, "accidents": 0,
                                     "at_most_one_accident_per_exposure": True})
        self.assertGreater(result["wilson_95_interval"][1], 0)
        self.assertLess(result["wilson_95_interval"][1], 0.004)

    def test_zero_baseline_does_not_invent_relative_effect(self):
        baseline = {"exposures": 1000, "accidents": 0, "at_most_one_accident_per_exposure": True}
        comparison = dict(baseline, accidents=1)
        result = association_comparison(baseline, comparison)
        self.assertIsNone(result["risk_ratio_comparison_over_baseline"])
        self.assertIsNone(result["observed_relative_reduction"])
        self.assertLess(result["risk_difference_per_exposure"], 0)

    def test_factual_indicators_keep_units_and_do_not_score_elements(self):
        items = quantify_observations(self.case["quantified_observations"])
        by_id = {item["id"]: item for item in items}
        self.assertAlmostEqual(by_id["inspection_completion"]["value"], 2 / 3)
        self.assertEqual(by_id["response_delay"]["value"], 20)
        self.assertEqual(by_id["elapsed_since_incident"]["value"], 49)
        self.assertEqual(self.case["legal"]["issues"][0]["finding"], "unknown")

    def test_future_cashflow_discounting_and_no_double_discounting(self):
        damages = copy.deepcopy(self.case["damages"])
        damages["required_components"] = ["future"]
        damages["components"] = [{
            "name": "future", "kind": "annual_future_stream",
            "amount": {"low": 110, "mode": 110, "high": 110},
            "years": 1, "discount_rate": 0.1, "source": "test",
        }]
        result = calculate_damages(damages)
        self.assertAlmostEqual(result["known_component_subtotal"]["mode"], 100)
        self.assertAlmostEqual(result["conditional_net_damages"]["mode"], 80)

    def test_finite_amounts_cannot_overflow_total_silently(self):
        damages = copy.deepcopy(self.case["damages"])
        for component in damages["components"]:
            component["amount"] = dict.fromkeys(("low", "mode", "high"), 1e308)
        with self.assertRaises(ValueError):
            calculate_damages(damages)

    def test_future_knowledge_rejected_for_breach_inputs(self):
        self.case["risk"]["information_available_by"] = "2026-10-01"
        with self.assertRaises(ValueError):
            assess(self.case, draws=1)

    def test_declared_path_does_not_hide_failed_or_unknown_issues(self):
        legal = self.case["legal"]
        legal["issues"][0]["finding"] = "not_supported"
        result = evaluate_declared_path(legal)
        self.assertEqual(result["state"], "declared_path_not_supported")
        self.assertIn("duty_of_care", result["not_supported"])
        self.assertIn("factual_causation", result["unresolved"])


if __name__ == "__main__":
    unittest.main()
