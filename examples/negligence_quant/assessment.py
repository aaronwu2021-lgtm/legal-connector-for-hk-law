"""Evidence-led negligence worksheet. Standard library only; no legal prediction."""
from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import date
from pathlib import Path

from risk_engine import evaluate_risk


CORE_ISSUES = (
    "duty_of_care", "breach", "factual_causation",
    "scope_and_remoteness", "actionable_damage",
)
FINDINGS = {"supported", "not_supported", "unknown", "not_applicable"}


def number(value, label, lower=0, upper=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label}: a finite number is required")
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f"{label}: a finite number is required") from None
    if not math.isfinite(value) or value < lower or (upper is not None and value > upper):
        raise ValueError(f"{label}: outside its permitted range")
    return float(value)


def interval(value, label, upper=None):
    values = {key: number(value[key], f"{label}.{key}", upper=upper)
              for key in ("low", "mode", "high")}
    if not values["low"] <= values["mode"] <= values["high"]:
        raise ValueError(f"{label}: require low <= mode <= high")
    return values


def observed_frequency(observations):
    """Wilson interval for independent Bernoulli exposures, NOT annual event probability."""
    n = observations["exposures"]
    k = observations["accidents"]
    if (type(n) is not int or type(k) is not int or n <= 0 or not 0 <= k <= n):
        raise ValueError("observations: require integer exposures > 0 and 0 <= accidents <= exposures")
    if observations["at_most_one_accident_per_exposure"] is not True:
        raise ValueError("Binomial model is unsuitable for recurrent events within one exposure")
    p, z = k / n, 1.959963984540054
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return {
        "accidents": k, "exposures": n,
        "source": observations.get("source", "not supplied"),
        "observed_probability_per_exposure": p,
        "accidents_per_100000_exposures": p * 100000,
        "wilson_95_interval": [max(0.0, centre - half), min(1.0, centre + half)],
        "assumptions": [
            "Independent, comparable exposures; one binary accident outcome per exposure.",
            "Clustering, changing conditions and under-reporting can invalidate this interval.",
            "A zero count does not establish zero risk.",
            "This sampling interval is distinct from the risk engine's assumed triangular range.",
        ],
    }


def quantify_observations(items):
    """Calculate factual indicators; no indicator is converted into a legal finding."""
    results = []
    for item in items:
        kind = item["kind"]
        if kind == "ratio":
            numerator = number(item["numerator"], f"{item['id']}.numerator")
            denominator = number(item["denominator"], f"{item['id']}.denominator")
            if denominator == 0:
                raise ValueError(f"{item['id']}: denominator must be greater than zero")
            value = numerator / denominator
        elif kind == "elapsed_days":
            value = (date.fromisoformat(item["end"]) - date.fromisoformat(item["start"])).days
            if value < 0:
                raise ValueError(f"{item['id']}: end precedes start")
        elif kind == "difference":
            value = (number(item["observed"], f"{item['id']}.observed")
                     - number(item["comparison"], f"{item['id']}.comparison"))
        elif kind == "quantity":
            value = number(item["value"], f"{item['id']}.value")
        else:
            raise ValueError(f"Unknown observation kind: {kind}")
        results.append({
            "id": item["id"], "issue_id": item["issue_id"],
            "label": item["label"], "value": value,
            "unit": item["unit"], "source": item["source"],
            "interpretation_limit": item["interpretation_limit"],
        })
    return results


def association_comparison(baseline, comparison):
    """Descriptive cohort association, not an identified causal effect."""
    first = observed_frequency(baseline)
    second = observed_frequency(comparison)
    p0 = first["observed_probability_per_exposure"]
    p1 = second["observed_probability_per_exposure"]
    return {
        "baseline": first, "comparison": second,
        "risk_difference_per_exposure": p0 - p1,
        "risk_ratio_comparison_over_baseline": p1 / p0 if p0 else None,
        "observed_relative_reduction": 1 - p1 / p0 if p0 else None,
        "note": "Descriptive association only; nonrandom assignment, confounding and sampling error remain. "
                "It neither estimates individual causation nor automatically sets the preventive effect input.",
    }


def evaluate_declared_path(legal):
    """Track external findings. This is a declared analytical route, not encoded local law."""
    issues = legal["issues"]
    ids = [item["id"] for item in issues]
    if len(ids) != len(set(ids)):
        raise ValueError("legal issue ids must be unique")
    missing_core = sorted(set(CORE_ISSUES) - set(ids))
    if missing_core:
        raise ValueError(f"Missing core issues: {missing_core}")
    unresolved, not_supported = [], []
    for item in issues:
        if item["finding"] not in FINDINGS:
            raise ValueError(f"Invalid finding for {item['id']}")
        if not item.get("proposition") or not item.get("basis"):
            raise ValueError(f"{item['id']}: proposition and basis are required")
        if item["id"] in CORE_ISSUES and item["finding"] == "not_applicable":
            raise ValueError(f"Core issue cannot be skipped: {item['id']}")
        if item["finding"] == "unknown":
            unresolved.append(item["id"])
        elif item["finding"] == "not_supported":
            not_supported.append(item["id"])
    if legal["jurisdiction_review"]["finding"] not in {"supported", "unknown"}:
        raise ValueError("jurisdiction_review.finding must be supported or unknown")
    if legal["jurisdiction_review"]["finding"] != "supported":
        unresolved.insert(0, "jurisdiction_review")
    state = ("declared_path_not_supported" if not_supported else
             "unresolved" if unresolved else "conditional_support_only")
    return {
        "state": state,
        "unresolved": unresolved,
        "not_supported": not_supported,
        "issues": issues,
        "note": "Economic outputs never change a legal finding. No liability probability is calculated.",
    }


def calculate_damages(damages):
    """Conditional arithmetic for one claimant; separate from population risk valuations."""
    names = [item["name"] for item in damages["components"]]
    if len(names) != len(set(names)):
        raise ValueError("Damage component names must be unique to avoid duplicate counting")
    missing = list(sorted(set(damages["required_components"]) - set(names)))
    totals = dict.fromkeys(("low", "mode", "high"), 0.0)
    breakdown = []
    for component in damages["components"]:
        if not component.get("source"):
            raise ValueError(f"{component['name']}: source is required")
        if component.get("amount") is None:
            missing.append(component["name"])
            continue
        values = interval(component["amount"], component["name"])
        kind = component["kind"]
        if kind == "present_value":
            factor = 1.0
        elif kind == "annual_future_stream":
            years = component["years"]
            if type(years) is not int or years < 1:
                raise ValueError("Future stream years must be positive integer")
            rate = number(component["discount_rate"], "damages.discount_rate")
            number(years, "damages.years")
            factor = (float(years) if rate == 0 else
                      -math.expm1(-years * math.log1p(rate)) / rate)
        else:
            raise ValueError(f"Unknown damages component kind: {kind}")
        factor = number(factor, "present_value_factor")
        pv = {key: number(values[key] * factor, f"{component['name']}.present_value") for key in totals}
        breakdown.append({"name": component["name"], "present_value": pv})
        for key in totals:
            totals[key] = number(totals[key] + pv[key], "damage_total")

    mitigation = damages["mitigation_deduction"]
    share = damages["contributory_fraction"]
    for label, adjustment in (("mitigation_deduction", mitigation), ("contributory_fraction", share)):
        if not adjustment.get("basis") or not adjustment.get("source"):
            raise ValueError(f"{label}: basis and source must be stated")
        if adjustment.get("amount") is None:
            missing.append(label)
    if not damages["required_components"]:
        missing.append("required_component_inventory")
    result = {
        "valuation_date": damages["valuation_date"],
        "components": breakdown,
        "known_component_subtotal": totals,
        "missing": missing,
        "conditional_net_damages": None,
        "legally_payable_amount": None,
        "note": "Scenario only. Eligibility, deduction applicability and order need external legal findings.",
    }
    if missing:
        return result
    deduction = interval(mitigation["amount"], "mitigation_deduction")
    fraction = interval(share["amount"], "contributory_fraction", upper=1)
    result["conditional_net_damages"] = {
        "low": max(0, totals["low"] - deduction["high"]) * (1 - fraction["high"]),
        "mode": max(0, totals["mode"] - deduction["mode"]) * (1 - fraction["mode"]),
        "high": max(0, totals["high"] - deduction["low"]) * (1 - fraction["low"]),
    }
    return result


def compare_options(risk):
    options = [{"id": "baseline", "burden_annual": 0,
                "residual_expected_loss_annual": risk["point_estimate"]["baseline_expected_loss_annual"]}]
    options.extend(risk["point_estimate"]["measures"])
    comparisons = []
    for i, first in enumerate(options):
        for second in options[i + 1:]:
            extra_cost = second["burden_annual"] - first["burden_annual"]
            extra_avoidance = first["residual_expected_loss_annual"] - second["residual_expected_loss_annual"]
            comparisons.append({
                "from": first["id"], "to": second["id"],
                "incremental_cost_annual": extra_cost,
                "incremental_avoided_loss_annual": extra_avoidance,
                "incremental_net_benefit_annual": extra_avoidance - extra_cost,
            })
    return comparisons


def audit_inputs(case):
    """List provenance limitations without inventing a reliability score."""
    audit = []
    if case["meta"]["data_status"] != "observed_case_data":
        audit.append("All demonstration values are synthetic; no empirical calibration has been established.")
    incident = date.fromisoformat(case["meta"]["incident_date"])
    cutoff = date.fromisoformat(case["risk"]["information_available_by"])
    if cutoff > incident:
        raise ValueError("Risk inputs for breach analysis must not use an information cutoff after the incident")
    evidence_ids = [item["id"] for item in case["evidence"]]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("Evidence ids must be unique")
    for item in case["legal"]["issues"]:
        for evidence_id in item["evidence_ids"]:
            if evidence_id not in evidence_ids:
                raise ValueError(f"Unknown evidence id: {evidence_id}")
    issue_ids = {item["id"] for item in case["legal"]["issues"]}
    indicator_ids = [item["id"] for item in case["quantified_observations"]]
    if len(indicator_ids) != len(set(indicator_ids)):
        raise ValueError("Quantified observation ids must be unique")
    for item in case["quantified_observations"]:
        if item["issue_id"] not in issue_ids or item["source"] not in evidence_ids:
            raise ValueError(f"{item['id']}: unknown issue or evidence source")
    for item in case["evidence"]:
        if item["status"] != "verified":
            audit.append(f"{item['id']}: {item['status']}; {item['description']}")
    audit.extend([
        "No risk score establishes duty, breach, factual causation, remoteness, or a defence.",
        "The selected option minimizes monetized expected cost only among the declared options.",
        "Tail severity, distributional effects and non-monetized rights remain separately recorded.",
        "Relative risk and risk reduction do not equal the probability that this defendant caused this injury.",
    ])
    return audit


def assess(case, draws=10000, seed=42):
    audit = audit_inputs(case)
    risk = evaluate_risk(case["risk"], draws=draws, seed=seed)
    risk["units"]["currency"] = case["meta"]["currency"]
    return {
        "meta": case["meta"],
        "legal": evaluate_declared_path(case["legal"]),
        "observed_frequency": observed_frequency(case["observations"]),
        "quantified_observations": quantify_observations(case["quantified_observations"]),
        "cohort_association": association_comparison(case["observations"], case["comparison_observations"]),
        "risk": risk,
        "incremental_comparisons": compare_options(risk),
        "claimant_damages": calculate_damages(case["damages"]),
        "non_monetized_constraints": case["non_monetized_constraints"],
        "input_audit": audit,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).with_name("example_case.json"))
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("results"))
    parser.add_argument("--draws", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        case = json.loads(args.input.read_text(encoding="utf-8"))
        result = assess(case, args.draws, args.seed)
    except (ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "assessment.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    measures = result["risk"]["point_estimate"]["measures"]
    if measures:
        with (args.out / "measures.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(measures[0]))
            writer.writeheader()
            writer.writerows(measures)
    print(f"Legal route: {result['legal']['state']}")
    print("Economic preferred option:", result["risk"]["point_estimate"]["preferred_measure_id"])
    print("Annual baseline expected loss:",
          f"{result['risk']['point_estimate']['baseline_expected_loss_annual']:,.2f}",
          result["meta"]["currency"])
    print(f"Saved: {args.out.resolve()}")


if __name__ == "__main__":
    main()
