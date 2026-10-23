"""Auditable arithmetic over explicit risk scenarios, never a legal verdict.

Probabilities describe specified events or counterfactual outcomes, not evidential
confidence, a court's decision, or a percentage of legal responsibility. Inputs must
share a time horizon, currency and population. This module does not infer them.

CLI: ``python -m legal_quant.scenarios KIND INPUT.json``; use ``-`` for stdin.
"""

import argparse
import json
import math
from pathlib import Path
import sys


KINDS = (
    "risk_distribution", "paired_counterfactual", "precaution_comparison",
    "liability_cap", "timely_performance", "execution_value",
)
PROBABILITY_TOLERANCE = 1e-9


def _object(value, required, optional=(), label="inputs"):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    if set(required) - value.keys():
        raise ValueError(f"{label} missing fields: {', '.join(sorted(set(required) - value.keys()))}")
    unknown = value.keys() - set(required) - set(optional)
    if unknown:
        raise ValueError(f"{label} has unknown fields: {', '.join(sorted(map(str, unknown)))}")


def _number(value, label, *, signed=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number, not a boolean")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{label} must be finite") from exc
    if not math.isfinite(result) or (not signed and result < 0):
        raise ValueError(f"{label} must be finite" + ("" if signed else " and nonnegative"))
    return result


def _boolean(value, label):
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _rows(inputs, numeric, required_flags=(), optional_flags=()):
    rows = inputs["rows"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("rows must be a nonempty array")
    validated = []
    for index, row in enumerate(rows):
        prefix = f"rows[{index}]"
        _object(row, {"p", *numeric, *required_flags}, optional_flags, prefix)
        checked = {key: _number(row[key], f"{prefix}.{key}") for key in ("p", *numeric)}
        if checked["p"] > 1:
            raise ValueError(f"{prefix}.p must be between 0 and 1")
        for key in required_flags:
            checked[key] = _boolean(row[key], f"{prefix}.{key}")
        for key in optional_flags:
            checked[key] = _boolean(row.get(key, False), f"{prefix}.{key}")
        validated.append(checked)
    try:
        total = math.fsum(row["p"] for row in validated)
    except OverflowError as exc:
        raise ValueError("probability sum is not finite") from exc
    if abs(total - 1.0) > PROBABILITY_TOLERANCE:
        raise ValueError("scenario probabilities must sum to 1 (tolerance 1e-9); no normalization is performed")
    return validated


def _weighted(rows, function):
    try:
        result = math.fsum(row["p"] * function(row) for row in rows)
    except (OverflowError, ValueError) as exc:
        raise ValueError("calculation overflow; use a suitable common unit") from exc
    if not math.isfinite(result):
        raise ValueError("calculation overflow; use a suitable common unit")
    return result


def evaluate(kind, inputs):
    """Evaluate one named calculation using a supplied complete scenario distribution.

    ``selected`` defaults to false; ``in_scope`` and ``insurable`` are mandatory
    booleans. Scope and insurance coverage are supplied legal assumptions, never
    inferred here. All prices, quantities, times, costs and losses are nonnegative;
    ``actual_net_proceeds`` and resulting differences may be negative.
    """
    if kind not in KINDS:
        raise ValueError(f"unknown scenario calculation: {kind!r}")
    top = {
        "risk_distribution": {"rows"},
        "paired_counterfactual": {"rows"},
        "precaution_comparison": {"rows", "cost"},
        "liability_cap": {"rows", "cap", "insurance_limit", "insurance_deductible", "resources"},
        "timely_performance": {"rows", "deadline"},
        "execution_value": {"rows", "quantity", "cost", "actual_net_proceeds"},
    }[kind]
    _object(inputs, top)
    constants = {key: _number(inputs[key], key, signed=(key == "actual_net_proceeds"))
                 for key in top - {"rows"}}

    if kind == "risk_distribution":
        rows = _rows(inputs, ("loss",), optional_flags=("selected",))
        results = {
            "expected_loss": _weighted(rows, lambda row: row["loss"]),
            "selected_probability": _weighted(rows, lambda row: int(row["selected"])),
            "selected_expected_loss": _weighted(rows, lambda row: row["loss"] if row["selected"] else 0),
        }
    elif kind == "paired_counterfactual":
        rows = _rows(inputs, ("actual_loss", "compliant_loss"), required_flags=("in_scope",))
        results = {
            "actual_expected_loss": _weighted(rows, lambda row: row["actual_loss"]),
            "compliant_expected_loss": _weighted(rows, lambda row: row["compliant_loss"]),
            "signed_difference": _weighted(rows, lambda row: row["actual_loss"] - row["compliant_loss"]),
            "in_scope_signed_difference": _weighted(rows, lambda row: row["actual_loss"] - row["compliant_loss"] if row["in_scope"] else 0),
            "actual_harm_probability": _weighted(rows, lambda row: int(row["actual_loss"] > 0)),
            "compliant_harm_probability": _weighted(rows, lambda row: int(row["compliant_loss"] > 0)),
        }
    elif kind == "precaution_comparison":
        rows = _rows(inputs, ("current_loss", "alternative_loss"))
        avoided = _weighted(rows, lambda row: row["current_loss"] - row["alternative_loss"])
        results = {
            "current_expected_loss": _weighted(rows, lambda row: row["current_loss"]),
            "alternative_expected_loss": _weighted(rows, lambda row: row["alternative_loss"]),
            "avoided_expected_loss": avoided,
            "net_benefit": avoided - constants["cost"],
        }
    elif kind == "liability_cap":
        rows = _rows(inputs, ("loss",), required_flags=("insurable",))

        def capped(row):
            return min(row["loss"], constants["cap"])

        def insurance(row):
            return min(max(capped(row) - constants["insurance_deductible"], 0),
                       constants["insurance_limit"]) if row["insurable"] else 0

        results = {
            "expected_uncapped_liability": _weighted(rows, lambda row: row["loss"]),
            "expected_capped_liability": _weighted(rows, capped),
            "expected_transferred_to_claimant": _weighted(rows, lambda row: row["loss"] - capped(row)),
            "expected_insurer_payment": _weighted(rows, insurance),
            "expected_provider_retained": _weighted(rows, lambda row: capped(row) - insurance(row)),
            "resource_shortfall_probability": _weighted(rows, lambda row: int(capped(row) - insurance(row) > constants["resources"])),
        }
    elif kind == "timely_performance":
        rows = _rows(inputs, ("duration",))
        results = {
            "probability_by_deadline": _weighted(rows, lambda row: int(row["duration"] <= constants["deadline"])),
            "expected_duration": _weighted(rows, lambda row: row["duration"]),
        }
    else:
        rows = _rows(inputs, ("price",))
        proceeds = _weighted(rows, lambda row: row["price"] * constants["quantity"] - constants["cost"])
        results = {
            "expected_compliant_net_proceeds": proceeds,
            "signed_gap": proceeds - constants["actual_net_proceeds"],
        }

    if any(not math.isfinite(value) for value in results.values()):
        raise ValueError("calculation overflow; use a suitable common unit")
    return {
        "kind": kind,
        "input_basis": "explicit_scenarios_not_case_findings",
        "description": "Arithmetic over the supplied scenarios; probabilities, legal scope, coverage and feasibility are input assumptions, not established case facts. No legal threshold or legal conclusion is inferred.",
        "results": results,
        "legal_conclusion": None,
    }


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _bad_constant(value):
    raise ValueError(f"non-finite JSON constant: {value}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Explicit substantive-law risk scenarios; arithmetic only, no legal verdict.")
    parser.add_argument("kind", choices=KINDS)
    parser.add_argument("input_file", help="JSON inputs file, or - for stdin")
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.read(2_000_001) if args.input_file == "-" else Path(args.input_file).read_text(encoding="utf-8-sig")
        if len(raw) > 2_000_000:
            raise ValueError("input JSON exceeds 2000000 characters")
        inputs = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_bad_constant)
        output = evaluate(args.kind, inputs)
        sys.stdout.write(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        return 0
    except (ValueError, OSError, UnicodeError, RecursionError) as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
