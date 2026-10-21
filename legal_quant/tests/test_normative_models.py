"""Semantic boundaries for computational portions of legal standards."""

from copy import deepcopy
import unittest

from legal_quant import evaluate, get_model, list_models


NEW_MODELS = {
    "alarp", "interim_injunction", "procedural_safeguards", "necessity",
    "reasonable_mitigation", "penalty_proportionality",
}


class NormativeModels(unittest.TestCase):
    def calculate(self, name, **updates):
        inputs = deepcopy(get_model(name)["example_inputs"])
        inputs.update(updates)
        return evaluate(name, inputs)

    def test_classification_keeps_supporting_analysis_separate(self):
        for model in list_models():
            with self.subTest(model=model["id"]):
                normative = model["id"] in NEW_MODELS | {"hand"}
                self.assertEqual(model["analysis_layer"],
                                 "legal_standard" if normative else "supporting_analysis")
                if normative:
                    self.assertEqual(model["category"], "legal_standard")
                    self.assertEqual(model["formula_authority"],
                                     "judicial_heuristic" if model["id"] in
                                     {"hand", "interim_injunction"} else "legal_test_formalisation")

    def test_all_new_examples_are_hypothetical_without_legal_verdict(self):
        for name in NEW_MODELS:
            with self.subTest(model=name):
                response = self.calculate(name)
                self.assertIsNone(response["legal_conclusion"])
                self.assertEqual(response["context"]["input_basis"], "hypothetical")
                self.assertEqual(response["applicability_status"], "unreviewed")
                self.assertTrue(response["required_legal_findings"])

    def test_alarp_ratio_has_no_gross_disproportion_threshold(self):
        self.assertEqual(self.calculate("alarp")["results"], {"cost_risk_ratio": 3})
        self.assertEqual(self.calculate("alarp", precaution_cost=20000)["results"],
                         {"cost_risk_ratio": 1})
        huge = self.calculate("alarp", precaution_cost=2000000000)
        self.assertEqual(huge["results"], {"cost_risk_ratio": 100000})
        self.assertIsNone(huge["legal_conclusion"])

    def test_alarp_zero_risk_reduction_is_undefined_not_permission(self):
        for cost in [0, 100]:
            result = self.calculate("alarp", precaution_cost=cost,
                                    monetised_risk_reduction=0)
            self.assertEqual(result["results"], {"cost_risk_ratio": None})
            self.assertIsNone(result["legal_conclusion"])

    def test_injunction_compares_both_kinds_of_error(self):
        result = self.calculate("interim_injunction")["results"]
        self.assertEqual(result["weighted_denial_harm"], 400000)
        self.assertEqual(result["weighted_grant_harm"], 120000)
        self.assertEqual(result["weighted_harm_difference"], 280000)
        self.assertTrue(result["numerical_balance_favours_grant"])
        for p, denial, grant in [(0, 0, 200000), (1, 1000000, 0)]:
            result = self.calculate("interim_injunction", success_probability=p)["results"]
            self.assertEqual((result["weighted_denial_harm"], result["weighted_grant_harm"]),
                             (denial, grant))

    def test_injunction_equal_harms_do_not_create_a_verdict(self):
        result = self.calculate("interim_injunction", success_probability=0.5,
                                harm_if_denied=100, harm_if_granted=100)
        self.assertEqual(result["results"]["weighted_harm_difference"], 0)
        self.assertFalse(result["results"]["numerical_balance_favours_grant"])
        self.assertIsNone(result["legal_conclusion"])

    def test_procedure_uses_incremental_error_risk_not_entire_loss(self):
        result = self.calculate("procedural_safeguards")["results"]
        self.assertAlmostEqual(result["avoided_expected_error_harm"], 4000)
        self.assertAlmostEqual(result["net_expected_benefit"], 3000)
        worsening = self.calculate("procedural_safeguards", error_probability_after=0.2)
        self.assertLess(worsening["results"]["avoided_expected_error_harm"], 0)
        self.assertFalse(worsening["results"]["positive_quantified_balance"])
        self.assertIsNone(worsening["legal_conclusion"])

    def test_procedure_equality_is_only_a_numerical_tie(self):
        result = self.calculate("procedural_safeguards", error_probability_before=0.5,
                                error_probability_after=0.25, conditional_harm=100,
                                added_procedure_cost=25)
        self.assertEqual(result["results"]["net_expected_benefit"], 0)
        self.assertFalse(result["results"]["positive_quantified_balance"])
        self.assertIsNone(result["legal_conclusion"])

    def test_necessity_excludes_infeasible_alternatives_and_retains_order(self):
        result = self.calculate("necessity")["results"]
        self.assertEqual(result["candidate_review_flags"], [True, False, False])
        self.assertEqual(result["flagged_candidate_count"], 1)
        self.assertEqual(len(result["candidate_names"]), 3)
        alternative = deepcopy(get_model("necessity")["example_inputs"]["candidates"][0])
        alternative["feasible"] = 0
        result = self.calculate("necessity", candidates=[alternative])["results"]
        self.assertEqual(result["candidate_review_flags"], [False])

    def test_necessity_requires_strictly_lower_burden_not_strictly_higher_effect(self):
        alternative = {"name": "Same effect, lower burden", "feasible": 1,
                       "effectiveness": 0.9, "rights_burden": 23}
        result = self.calculate("necessity", candidates=[alternative])["results"]
        self.assertEqual(result["candidate_review_flags"], [True])
        alternative["rights_burden"] = 24
        result = self.calculate("necessity", candidates=[alternative])["results"]
        self.assertEqual(result["candidate_review_flags"], [False])

    def test_no_candidates_does_not_prove_necessity(self):
        result = self.calculate("necessity", candidates=[])
        self.assertEqual(result["results"], {"candidate_names": [],
                         "candidate_review_flags": [], "flagged_candidate_count": 0})
        self.assertIsNone(result["legal_conclusion"])

    def test_mitigation_net_benefit_and_tie_do_not_determine_reasonableness(self):
        result = self.calculate("reasonable_mitigation")["results"]
        self.assertEqual(result["expected_avoided_loss"], 60000)
        self.assertEqual(result["net_expected_benefit"], 40000)
        tie = self.calculate("reasonable_mitigation", mitigation_cost=60000)
        self.assertEqual(tie["results"]["net_expected_benefit"], 0)
        self.assertFalse(tie["results"]["positive_quantified_balance"])
        self.assertIsNone(tie["legal_conclusion"])

    def test_penalty_gateway_and_zero_loss_keep_ratio_undefined(self):
        result = self.calculate("penalty_proportionality", secondary_obligation=0)
        self.assertEqual(result["results"], {"secondary_gateway_assumed": False,
                                            "detriment_loss_ratio": None})
        for detriment in [0, 30000]:
            result = self.calculate("penalty_proportionality", clause_detriment=detriment,
                                    anticipated_compensatory_loss=0)
            self.assertEqual(result["results"], {"secondary_gateway_assumed": True,
                                                "detriment_loss_ratio": None})
            self.assertIsNone(result["legal_conclusion"])

    def test_penalty_large_ratio_is_not_invalidity(self):
        result = self.calculate("penalty_proportionality", clause_detriment=1000000000)
        self.assertEqual(result["results"]["detriment_loss_ratio"], 100000)
        self.assertEqual(set(result["results"]), {"secondary_gateway_assumed", "detriment_loss_ratio"})
        self.assertIsNone(result["legal_conclusion"])

    def test_external_gateways_require_numeric_zero_or_one(self):
        for invalid in [True, False, -1, 0.5, 2, "1"]:
            with self.subTest(value=invalid):
                with self.assertRaises(ValueError):
                    self.calculate("penalty_proportionality", secondary_obligation=invalid)
                candidate = deepcopy(get_model("necessity")["example_inputs"]["candidates"][0])
                candidate["feasible"] = invalid
                with self.assertRaises(ValueError):
                    self.calculate("necessity", candidates=[candidate])

    def test_probability_domains_are_checked(self):
        for model, field in [("interim_injunction", "success_probability"),
                             ("procedural_safeguards", "error_probability_before"),
                             ("procedural_safeguards", "error_probability_after"),
                             ("reasonable_mitigation", "success_probability")]:
            for invalid in [-0.01, 1.01, True]:
                with self.subTest(model=model, field=field, value=invalid):
                    with self.assertRaises(ValueError):
                        self.calculate(model, **{field: invalid})


if __name__ == "__main__":
    unittest.main()
