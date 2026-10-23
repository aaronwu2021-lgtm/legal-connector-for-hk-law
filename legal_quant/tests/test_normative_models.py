"""Boundary cases for substantive legal standards involving probability."""

from copy import deepcopy
import unittest

from legal_quant import evaluate, get_model, list_models


AUTHORITIES = {
    "hand": "judicial_heuristic",
    "alarp_probability": "legal_test_formalisation",
    "reasonable_mitigation": "legal_test_formalisation",
    "loss_of_chance": "legal_rule_formalisation",
}


class NormativeModels(unittest.TestCase):
    def calculate(self, name, **updates):
        inputs = deepcopy(get_model(name)["example_inputs"])
        inputs.update(updates)
        return evaluate(name, inputs)

    def test_only_substantive_probability_models_with_correct_authority(self):
        self.assertEqual({model["id"] for model in list_models()}, set(AUTHORITIES))
        for model in list_models():
            with self.subTest(model=model["id"]):
                self.assertEqual(model["analysis_layer"], "substantive_law")
                self.assertEqual(model["category"], "substantive_probability")
                self.assertEqual(model["formula_authority"], AUTHORITIES[model["id"]])
                response = self.calculate(model["id"])
                self.assertIsNone(response["legal_conclusion"])
                self.assertEqual(response["context"]["input_basis"], "hypothetical")
                self.assertEqual(response["applicability_status"], "unreviewed")
                self.assertTrue(response["required_legal_findings"])

    def test_alarp_uses_incremental_expected_loss_without_disproportion_threshold(self):
        inputs = dict(probability_before=0.08, probability_after=0.02,
                      loss_if_harm=1000000, precaution_cost=180000)
        result = self.calculate("alarp_probability", **inputs)
        self.assertAlmostEqual(result["results"]["avoided_expected_loss"], 60000)
        self.assertAlmostEqual(result["results"]["cost_risk_ratio"], 3)
        huge = self.calculate("alarp_probability", **{**inputs, "precaution_cost": 6000000000})
        self.assertAlmostEqual(huge["results"]["cost_risk_ratio"], 100000)
        self.assertEqual(set(huge["results"]), {"avoided_expected_loss", "cost_risk_ratio"})
        self.assertIsNone(huge["legal_conclusion"])

    def test_alarp_zero_reduction_or_loss_has_undefined_ratio_not_permission(self):
        for cost in [0, 100]:
            for updates in [dict(probability_before=0.5, probability_after=0.5),
                            dict(probability_before=0, probability_after=0),
                            dict(loss_if_harm=0)]:
                with self.subTest(cost=cost, updates=updates):
                    result = self.calculate("alarp_probability", precaution_cost=cost, **updates)
                    self.assertEqual(result["results"], {"avoided_expected_loss": 0, "cost_risk_ratio": None})
                    self.assertIsNone(result["legal_conclusion"])

    def test_alarp_full_risk_removal_and_free_precaution(self):
        result = self.calculate("alarp_probability", probability_before=1, probability_after=0,
                                loss_if_harm=100, precaution_cost=0)
        self.assertEqual(result["results"], {"avoided_expected_loss": 100, "cost_risk_ratio": 0})

    def test_mitigation_benefit_and_tie_do_not_determine_reasonableness(self):
        result = self.calculate("reasonable_mitigation")["results"]
        self.assertEqual(result["expected_avoided_loss"], 60000)
        self.assertEqual(result["net_expected_benefit"], 40000)
        tie = self.calculate("reasonable_mitigation", mitigation_cost=60000)
        self.assertEqual(tie["results"]["net_expected_benefit"], 0)
        self.assertFalse(tie["results"]["positive_quantified_balance"])
        self.assertIsNone(tie["legal_conclusion"])
        ineffective = self.calculate("reasonable_mitigation", success_probability=0)
        self.assertEqual(ineffective["results"]["expected_avoided_loss"], 0)
        self.assertEqual(ineffective["results"]["net_expected_benefit"], -20000)

    def test_chance_zero_probability_has_zero_value_not_a_liability_finding(self):
        response = self.calculate("loss_of_chance", probability_before=0, probability_after=0)
        self.assertEqual(response["results"]["chance_value"], 0)
        self.assertIsNone(response["legal_conclusion"])

    def test_probability_domains_and_nonnegative_costs_are_checked(self):
        probability_fields = {
            "hand": ["p", "prob_reduction", "severity_reduction"],
            "alarp_probability": ["probability_before", "probability_after"],
            "reasonable_mitigation": ["success_probability"],
            "loss_of_chance": ["probability_before", "probability_after"],
        }
        for model, fields in probability_fields.items():
            for field in fields:
                for invalid in [-0.01, 1.01, True]:
                    with self.subTest(model=model, field=field, value=invalid), self.assertRaises(ValueError):
                        self.calculate(model, **{field: invalid})
        for field in ["precaution_cost", "loss_if_harm"]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.calculate("alarp_probability", **{field: -1})

    def test_risk_and_chance_cannot_increase_in_a_reduction_model(self):
        for name in ["alarp_probability", "loss_of_chance"]:
            with self.subTest(model=name), self.assertRaises(ValueError):
                self.calculate(name, probability_before=0.2, probability_after=0.3)


if __name__ == "__main__":
    unittest.main()
