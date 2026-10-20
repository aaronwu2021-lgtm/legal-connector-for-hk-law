"""Behavioral checks for the precaution-economics model (standard library only)."""

from copy import deepcopy
import json
import math
import unittest

try:
    from .risk_engine import evaluate_risk
except ImportError:
    from risk_engine import evaluate_risk


def fixed(value):
    return {"low": value, "mode": value, "high": value}


def example():
    return {
        "exposure_count_per_year": 1000,
        "event_probability_basis": "per_exposure",
        "baseline_event_probability": fixed(0.01),
        "discount_rate": 0,
        "loss_categories": [
            {
                "name": "minor",
                "share": 0.75,
                "components": [{"name": "repair", "amount": fixed(100), "source": "test"}],
            },
            {
                "name": "major",
                "share": 0.25,
                "components": [
                    {"name": "repair", "amount": fixed(400), "source": "test"},
                    {"name": "other distinct loss", "amount": fixed(100), "source": "test"},
                ],
            },
        ],
        "measures": [
            {
                "id": "guard",
                "name": "Protective guard",
                "initial_cost": fixed(1000),
                "life_years": 10,
                "annual_costs": [{"name": "maintenance", "amount": fixed(100)}],
                "probability_reduction": fixed(0.5),
                "severity_reduction": fixed(0.2),
            }
        ],
    }


class RiskEngineTests(unittest.TestCase):
    def evaluate(self, config=None, **kwargs):
        return evaluate_risk(example() if config is None else config, draws=200, **kwargs)

    def test_conditional_categories_annualization_and_combined_effect(self):
        result = self.evaluate()
        point = result["point_estimate"]
        measure = point["measures"][0]
        self.assertEqual(point["conditional_expected_loss_per_event"], 200)
        self.assertEqual(point["expected_event_count_annual"], 10)
        self.assertEqual(point["baseline_expected_loss_annual"], 2000)
        self.assertEqual(measure["burden_annual"], 200)
        self.assertEqual(measure["residual_expected_loss_annual"], 800)
        self.assertEqual(measure["avoided_expected_loss_annual"], 1200)
        self.assertEqual(measure["net_benefit_annual"], 1000)
        self.assertEqual(measure["total_social_cost_annual"], 1000)
        self.assertEqual(measure["benefit_cost_ratio"], 6)
        self.assertAlmostEqual(measure["break_even_probability_per_exposure"], 1 / 600)
        self.assertAlmostEqual(measure["break_even_probability_reduction"], -0.125)
        self.assertEqual(measure["economic_support"], "positive")
        self.assertEqual(point["preferred_measure_id"], "guard")
        self.assertEqual(result["simulation"]["preferred_share"], {"baseline": 0, "guard": 1})
        simulation = result["simulation"]["net_benefit_by_measure"][0]
        self.assertEqual(simulation["p05"], 1000)
        self.assertEqual(simulation["positive_share"], 1)
        self.assertEqual(simulation["mc_standard_error"], 0)
        json.dumps(result, allow_nan=False)

    def test_positive_discount_rate(self):
        config = example()
        config["discount_rate"] = 0.05
        measure = self.evaluate(config)["point_estimate"]["measures"][0]
        self.assertAlmostEqual(measure["burden_annual"], 229.5045749654566)

    def test_tiny_discount_rate_is_stable(self):
        config = example()
        config["discount_rate"] = 1e-20
        measure = self.evaluate(config)["point_estimate"]["measures"][0]
        self.assertAlmostEqual(measure["burden_annual"], 200)

    def test_ineffective_precaution_cannot_eliminate_baseline_loss(self):
        config = example()
        config["measures"][0]["probability_reduction"] = fixed(0)
        config["measures"][0]["severity_reduction"] = fixed(0)
        point = self.evaluate(config)["point_estimate"]
        measure = point["measures"][0]
        self.assertEqual(measure["net_benefit_annual"], -200)
        self.assertEqual(measure["residual_expected_loss_annual"], 2000)
        self.assertIsNone(measure["break_even_probability_per_exposure"])
        self.assertEqual(measure["economic_support"], "negative")
        self.assertEqual(point["preferred_measure_id"], "baseline")

    def test_full_probability_or_severity_reduction(self):
        for field in ("probability_reduction", "severity_reduction"):
            with self.subTest(field=field):
                config = example()
                config["measures"][0][field] = fixed(1)
                measure = self.evaluate(config)["point_estimate"]["measures"][0]
                self.assertEqual(measure["residual_expected_loss_annual"], 0)
                self.assertEqual(measure["avoided_expected_loss_annual"], 2000)
                if field == "severity_reduction":
                    self.assertIsNone(measure["break_even_probability_reduction"])

    def test_severity_reduction_alone_can_have_positive_benefit(self):
        config = example()
        config["measures"][0]["probability_reduction"] = fixed(0)
        measure = self.evaluate(config)["point_estimate"]["measures"][0]
        self.assertEqual(measure["avoided_expected_loss_annual"], 400)
        self.assertEqual(measure["net_benefit_annual"], 200)

    def test_unaffordable_measure_retains_infeasible_threshold(self):
        config = example()
        config["measures"][0]["annual_costs"][0]["amount"] = fixed(3000)
        point = self.evaluate(config)["point_estimate"]
        self.assertGreater(point["measures"][0]["break_even_probability_reduction"], 1)
        self.assertEqual(point["preferred_measure_id"], "baseline")
        self.assertEqual(point["measures"][0]["economic_support"], "negative")

    def test_zero_cost_and_zero_risk_are_explicit(self):
        config = example()
        config["baseline_event_probability"] = fixed(0)
        measure = config["measures"][0]
        measure["initial_cost"] = fixed(0)
        measure["annual_costs"] = []
        result = self.evaluate(config)
        point = result["point_estimate"]["measures"][0]
        self.assertIsNone(point["benefit_cost_ratio"])
        self.assertIsNone(point["break_even_probability_reduction"])
        self.assertEqual(point["economic_support"], "equal")
        self.assertEqual(result["point_estimate"]["preferred_measure_id"], "baseline")
        self.assertEqual(result["simulation"]["preferred_share"]["baseline"], 1)

    def test_mutually_exclusive_packages_choose_lowest_social_cost(self):
        config = example()
        other = deepcopy(config["measures"][0])
        other["id"] = "strong_guard"
        other["probability_reduction"] = fixed(0.9)
        other["initial_cost"] = fixed(2000)
        config["measures"].append(other)
        result = self.evaluate(config)
        self.assertEqual(result["point_estimate"]["preferred_measure_id"], "strong_guard")
        self.assertEqual(len(result["point_estimate"]["measures"]), 2)
        self.assertAlmostEqual(sum(result["simulation"]["preferred_share"].values()), 1)

    def test_baseline_only(self):
        config = example()
        config["measures"] = []
        result = self.evaluate(config)
        self.assertEqual(result["point_estimate"]["preferred_measure_id"], "baseline")
        self.assertEqual(result["point_estimate"]["measures"], [])
        self.assertEqual(result["simulation"]["preferred_share"], {"baseline": 1})

    def test_reproducible_parameter_uncertainty_and_corner_bounds(self):
        config = example()
        config["baseline_event_probability"] = {"low": 0.001, "mode": 0.01, "high": 0.03}
        config["measures"][0]["probability_reduction"] = {
            "low": 0.1, "mode": 0.5, "high": 0.9
        }
        result = self.evaluate(config, seed=17)
        self.assertEqual(result, self.evaluate(config, seed=17))
        self.assertNotEqual(
            result["simulation"]["net_benefit_by_measure"],
            self.evaluate(config, seed=18)["simulation"]["net_benefit_by_measure"],
        )
        bounds = result["bounds"]["measures"][0]["net_benefit_annual"]
        self.assertAlmostEqual(bounds["min"], -144)
        self.assertAlmostEqual(bounds["max"], 5320)
        simulation = result["simulation"]["net_benefit_by_measure"][0]
        self.assertLessEqual(bounds["min"], simulation["p05"])
        self.assertLessEqual(simulation["p05"], simulation["p50"])
        self.assertLessEqual(simulation["p50"], simulation["p95"])
        self.assertLessEqual(simulation["p95"], bounds["max"])
        proportion = simulation["positive_share"]
        self.assertAlmostEqual(
            simulation["mc_standard_error"], math.sqrt(proportion * (1 - proportion) / 200)
        )

    def test_all_options_share_each_baseline_draw(self):
        config = example()
        config["baseline_event_probability"] = {"low": 0.001, "mode": 0.01, "high": 0.1}
        identical = deepcopy(config["measures"][0])
        identical["id"] = "identical"
        config["measures"].append(identical)
        result = self.evaluate(config)
        first, second = result["simulation"]["net_benefit_by_measure"]
        for key in ("p05", "p50", "p95", "positive_share", "mc_standard_error"):
            self.assertEqual(first[key], second[key])
        self.assertEqual(result["simulation"]["preferred_share"]["identical"], 0)

    def test_missing_values_are_not_imputed(self):
        for field in (
            "exposure_count_per_year",
            "event_probability_basis",
            "baseline_event_probability",
            "discount_rate",
            "loss_categories",
            "measures",
        ):
            with self.subTest(field=field):
                config = example()
                del config[field]
                with self.assertRaisesRegex(ValueError, "required"):
                    self.evaluate(config)
        config = example()
        del config["measures"][0]["severity_reduction"]
        with self.assertRaisesRegex(ValueError, "required"):
            self.evaluate(config)

    def test_invalid_probabilities_and_amounts(self):
        for value in (math.nan, math.inf, -math.inf, -1, 1.01, True, "0.1", None):
            with self.subTest(value=value):
                config = example()
                config["baseline_event_probability"] = fixed(value)
                with self.assertRaises(ValueError):
                    self.evaluate(config)
        for value in (math.nan, math.inf, -1, False, "20"):
            with self.subTest(amount=value):
                config = example()
                config["measures"][0]["initial_cost"] = fixed(value)
                with self.assertRaises(ValueError):
                    self.evaluate(config)
        config = example()
        config["measures"][0]["initial_cost"] = {"low": 10, "mode": 2, "high": 20}
        with self.assertRaisesRegex(ValueError, "low <= mode <= high"):
            self.evaluate(config)

    def test_invalid_exposures_lifetimes_basis_and_shares(self):
        for value in (0, -2, 2.5, True):
            with self.subTest(value=value):
                for field in ("exposures", "life"):
                    config = example()
                    if field == "exposures":
                        config["exposure_count_per_year"] = value
                    else:
                        config["measures"][0]["life_years"] = value
                    with self.assertRaises(ValueError):
                        self.evaluate(config)
        config = example()
        config["event_probability_basis"] = "per_year"
        with self.assertRaisesRegex(ValueError, "per_exposure"):
            self.evaluate(config)
        config = example()
        config["loss_categories"][0]["share"] = 0.9
        with self.assertRaisesRegex(ValueError, "sum to 1"):
            self.evaluate(config)
        config = example()
        config["loss_categories"] = []
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            self.evaluate(config)

    def test_reserved_or_duplicate_ids(self):
        config = example()
        config["measures"][0]["id"] = "baseline"
        with self.assertRaisesRegex(ValueError, "unique"):
            self.evaluate(config)
        config = example()
        config["measures"].append(deepcopy(config["measures"][0]))
        with self.assertRaisesRegex(ValueError, "unique"):
            self.evaluate(config)

    def test_draws_and_seed_validation(self):
        for draws in (0, -1, 1.5, True):
            with self.subTest(draws=draws), self.assertRaises(ValueError):
                evaluate_risk(example(), draws=draws)
        with self.assertRaises(ValueError):
            self.evaluate(seed=True)
        result = evaluate_risk(example(), draws=1)
        self.assertEqual(result["simulation"]["draws"], 1)

    def test_overflow_is_reported_as_validation_error(self):
        config = example()
        config["loss_categories"][0]["components"][0]["amount"] = fixed(1e308)
        with self.assertRaisesRegex(ValueError, "finite numeric range"):
            self.evaluate(config)

    def test_does_not_mutate_input(self):
        config = example()
        original = deepcopy(config)
        self.evaluate(config)
        self.assertEqual(config, original)

    def test_large_common_baseline_does_not_hide_small_avoided_loss(self):
        config = example()
        config["exposure_count_per_year"] = 10**15
        config["baseline_event_probability"] = fixed(1)
        config["loss_categories"] = [
            {
                "name": "loss",
                "share": 1,
                "components": [{"name": "amount", "amount": fixed(1), "source": "test"}],
            }
        ]
        measure = config["measures"][0]
        measure["initial_cost"] = fixed(0.5)
        measure["life_years"] = 1
        measure["annual_costs"] = []
        measure["probability_reduction"] = fixed(1e-15)
        measure["severity_reduction"] = fixed(0)
        result = self.evaluate(config)
        self.assertAlmostEqual(result["point_estimate"]["measures"][0]["net_benefit_annual"], 0.5)
        self.assertEqual(result["point_estimate"]["preferred_measure_id"], "guard")
        self.assertEqual(result["simulation"]["preferred_share"]["guard"], 1)


if __name__ == "__main__":
    unittest.main()
