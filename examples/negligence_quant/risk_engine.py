"""Quantify precaution economics without deciding negligence or legal causation.

All monetary amounts must use the same currency and price year. Event probability
is per exposure; category shares describe mutually exclusive losses conditional
on an event. Measures are alternative complete packages, not additive actions.

``evaluate_risk`` uses the mode of each triangular input for its point estimate,
conservative parameter corners for bounds, and a seeded Monte Carlo simulation
of uncertain parameters. It does not simulate realized accidents or estimate the
probability that a court will impose liability.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Any


@dataclass(frozen=True)
class _Triangle:
    low: float
    mode: float
    high: float

    def sample(self, rng: random.Random) -> float:
        if self.low == self.high:
            return self.low
        return rng.triangular(self.low, self.high, self.mode)


@dataclass(frozen=True)
class _Category:
    name: str
    share: float
    components: tuple[_Triangle, ...]


@dataclass(frozen=True)
class _Measure:
    id: str
    name: str
    initial_cost: _Triangle
    capital_factor: float
    annual_costs: tuple[_Triangle, ...]
    probability_reduction: _Triangle
    severity_reduction: _Triangle

    def burden(self, position: str) -> float:
        return _finite_result(
            getattr(self.initial_cost, position) * self.capital_factor
            + sum(getattr(amount, position) for amount in self.annual_costs),
            f"measure {self.id} annual burden",
        )

    def sample_burden(self, rng: random.Random) -> float:
        return _finite_result(
            self.initial_cost.sample(rng) * self.capital_factor
            + sum(amount.sample(rng) for amount in self.annual_costs),
            f"measure {self.id} sampled annual burden",
        )


def _object(value: Any, path: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    return value


def _required(obj: dict, key: str, path: str) -> Any:
    if key not in obj:
        raise ValueError(f"{path}.{key} is required; missing values are not zero")
    return obj[key]


def _array(value: Any, path: str, *, nonempty: bool = False) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be an array")
    if nonempty and not value:
        raise ValueError(f"{path} must not be empty")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a nonempty string")
    return value


def _number(value: Any, path: str, *, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path} must be a finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f"{path} must be a finite number") from None
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{path} must be finite and nonnegative")
    if maximum is not None and result > maximum:
        raise ValueError(f"{path} must be in [0, {maximum:g}]")
    return result


def _positive_integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{path} must be a positive integer")
    _number(value, path)
    return value


def _triangle(value: Any, path: str, *, unit_interval: bool = False) -> _Triangle:
    obj = _object(value, path)
    values = [
        _number(
            _required(obj, key, path),
            f"{path}.{key}",
            maximum=1.0 if unit_interval else None,
        )
        for key in ("low", "mode", "high")
    ]
    if not values[0] <= values[1] <= values[2]:
        raise ValueError(f"{path} must satisfy low <= mode <= high")
    return _Triangle(*values)


def _finite_result(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{label} exceeds finite numeric range; rescale inputs")
    return value


def _annual_capital_factor(rate: float, life: int) -> float:
    if rate == 0:
        return 1.0 / life
    # Algebraically r*(1+r)**T / ((1+r)**T-1), stable for small r and large T.
    denominator = -math.expm1(-life * math.log1p(rate))
    return _finite_result(rate / denominator, "annual capital factor")


def _parse(config: dict) -> tuple[int, _Triangle, list[_Category], list[_Measure]]:
    obj = _object(config, "config")
    exposures = _positive_integer(
        _required(obj, "exposure_count_per_year", "config"),
        "config.exposure_count_per_year",
    )
    if _required(obj, "event_probability_basis", "config") != "per_exposure":
        raise ValueError("config.event_probability_basis must be 'per_exposure'")
    probability = _triangle(
        _required(obj, "baseline_event_probability", "config"),
        "config.baseline_event_probability",
        unit_interval=True,
    )
    rate = _number(
        _required(obj, "discount_rate", "config"), "config.discount_rate"
    )
    categories = []
    raw_categories = _array(
        _required(obj, "loss_categories", "config"),
        "config.loss_categories",
        nonempty=True,
    )
    for index, raw_category in enumerate(raw_categories):
        path = f"config.loss_categories[{index}]"
        category = _object(raw_category, path)
        name = _text(_required(category, "name", path), f"{path}.name")
        share = _number(
            _required(category, "share", path), f"{path}.share", maximum=1.0
        )
        components = []
        for component_index, raw_component in enumerate(
            _array(
                _required(category, "components", path),
                f"{path}.components",
                nonempty=True,
            )
        ):
            component_path = f"{path}.components[{component_index}]"
            component = _object(raw_component, component_path)
            _text(_required(component, "name", component_path), f"{component_path}.name")
            components.append(
                _triangle(
                    _required(component, "amount", component_path),
                    f"{component_path}.amount",
                )
            )
        categories.append(_Category(name, share, tuple(components)))
    if not math.isclose(
        math.fsum(category.share for category in categories),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise ValueError("config.loss_categories shares must sum to 1")

    measures = []
    seen = {"baseline"}
    for index, raw_measure in enumerate(
        _array(_required(obj, "measures", "config"), "config.measures")
    ):
        path = f"config.measures[{index}]"
        measure = _object(raw_measure, path)
        measure_id = _text(_required(measure, "id", path), f"{path}.id")
        if measure_id in seen:
            raise ValueError(f"{path}.id must be unique and cannot be 'baseline'")
        seen.add(measure_id)
        name = _text(_required(measure, "name", path), f"{path}.name")
        life = _positive_integer(
            _required(measure, "life_years", path), f"{path}.life_years"
        )
        annual_costs = []
        for cost_index, raw_cost in enumerate(
            _array(_required(measure, "annual_costs", path), f"{path}.annual_costs")
        ):
            cost_path = f"{path}.annual_costs[{cost_index}]"
            cost = _object(raw_cost, cost_path)
            _text(_required(cost, "name", cost_path), f"{cost_path}.name")
            annual_costs.append(
                _triangle(_required(cost, "amount", cost_path), f"{cost_path}.amount")
            )
        measures.append(
            _Measure(
                id=measure_id,
                name=name,
                initial_cost=_triangle(
                    _required(measure, "initial_cost", path), f"{path}.initial_cost"
                ),
                capital_factor=_annual_capital_factor(rate, life),
                annual_costs=tuple(annual_costs),
                probability_reduction=_triangle(
                    _required(measure, "probability_reduction", path),
                    f"{path}.probability_reduction",
                    unit_interval=True,
                ),
                severity_reduction=_triangle(
                    _required(measure, "severity_reduction", path),
                    f"{path}.severity_reduction",
                    unit_interval=True,
                ),
            )
        )
    return exposures, probability, categories, measures


def _loss_at(categories: list[_Category], position: str) -> float:
    return _finite_result(
        sum(
            category.share
            * sum(getattr(component, position) for component in category.components)
            for category in categories
        ),
        f"{position} conditional loss",
    )


def _combined_reduction(probability_reduction: float, severity_reduction: float) -> float:
    return probability_reduction + (1.0 - probability_reduction) * severity_reduction


def _support(avoided: float, burden: float) -> str:
    if math.isclose(avoided, burden, rel_tol=1e-12, abs_tol=1e-12):
        return "equal"
    return "positive" if avoided > burden else "negative"


def _ratio(numerator: float, denominator: float, label: str) -> float | None:
    if denominator == 0:
        return None
    return _finite_result(numerator / denominator, label)


def _quantile(sorted_values: list[float], probability: float) -> float:
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def evaluate_risk(config: dict, draws: int = 10000, seed: int = 42) -> dict:
    """Return point estimates, parameter bounds and Monte Carlo summaries.

    Raises ``ValueError`` for missing, invalid or numerically overflowing inputs.
    ``break_even_probability_reduction`` is the raw fractional threshold holding
    severity reduction fixed: a negative value means severity reduction alone
    suffices, and a value above 1 means no feasible probability reduction suffices.
    An undefined ratio or threshold is represented as ``None`` (JSON ``null``).
    """
    _positive_integer(draws, "draws")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    exposures, probability, categories, measures = _parse(config)
    loss = _loss_at(categories, "mode")
    baseline = _finite_result(exposures * probability.mode * loss, "baseline annual loss")
    point_measures = []
    preferred_id = "baseline"
    preferred_net_benefit = 0.0
    bound_measures = []
    baseline_low = _finite_result(
        exposures * probability.low * _loss_at(categories, "low"), "lower baseline loss"
    )
    baseline_high = _finite_result(
        exposures * probability.high * _loss_at(categories, "high"), "upper baseline loss"
    )

    for measure in measures:
        burden = measure.burden("mode")
        probability_reduction = measure.probability_reduction.mode
        severity_reduction = measure.severity_reduction.mode
        combined = _combined_reduction(probability_reduction, severity_reduction)
        avoided = _finite_result(baseline * combined, "avoided annual loss")
        residual = _finite_result(
            baseline * (1.0 - probability_reduction) * (1.0 - severity_reduction),
            "residual annual loss",
        )
        total_cost = _finite_result(burden + residual, "total social cost")
        support = _support(avoided, burden)
        threshold_probability = _ratio(
            burden,
            _finite_result(exposures * loss * combined, "probability threshold denominator"),
            "break-even probability",
        )
        threshold_reduction = _ratio(
            burden - baseline * severity_reduction,
            baseline * (1.0 - severity_reduction),
            "break-even probability reduction",
        )
        point_measures.append(
            {
                "id": measure.id,
                "name": measure.name,
                "burden_annual": burden,
                "baseline_expected_loss_annual": baseline,
                "residual_expected_loss_annual": residual,
                "avoided_expected_loss_annual": avoided,
                "net_benefit_annual": avoided - burden,
                "total_social_cost_annual": total_cost,
                "benefit_cost_ratio": _ratio(avoided, burden, "benefit-cost ratio"),
                "break_even_probability_per_exposure": threshold_probability,
                "break_even_probability_reduction": threshold_reduction,
                "combined_loss_reduction": combined,
                "economic_support": support,
            }
        )
        net_benefit = avoided - burden
        if support == "positive" and net_benefit > preferred_net_benefit and not math.isclose(
            net_benefit, preferred_net_benefit, rel_tol=1e-12, abs_tol=1e-12
        ):
            preferred_id = measure.id
            preferred_net_benefit = net_benefit
        bound_measures.append(
            {
                "id": measure.id,
                "name": measure.name,
                "net_benefit_annual": {
                    "min": baseline_low
                    * _combined_reduction(
                        measure.probability_reduction.low, measure.severity_reduction.low
                    )
                    - measure.burden("high"),
                    "max": baseline_high
                    * _combined_reduction(
                        measure.probability_reduction.high, measure.severity_reduction.high
                    )
                    - measure.burden("low"),
                },
            }
        )

    rng = random.Random(seed)
    samples: dict[str, list[float]] = {measure.id: [] for measure in measures}
    positive_counts = {measure.id: 0 for measure in measures}
    preferred_counts = {"baseline": 0, **{measure.id: 0 for measure in measures}}
    for _ in range(draws):
        sampled_probability = probability.sample(rng)
        sampled_loss = _finite_result(
            sum(
                category.share
                * sum(component.sample(rng) for component in category.components)
                for category in categories
            ),
            "sampled conditional loss",
        )
        sampled_baseline = _finite_result(
            exposures * sampled_probability * sampled_loss, "sampled baseline loss"
        )
        best_id = "baseline"
        best_net_benefit = 0.0
        for measure in measures:
            burden = measure.sample_burden(rng)
            probability_reduction = measure.probability_reduction.sample(rng)
            severity_reduction = measure.severity_reduction.sample(rng)
            combined = _combined_reduction(probability_reduction, severity_reduction)
            avoided = sampled_baseline * combined
            net_benefit = avoided - burden
            samples[measure.id].append(net_benefit)
            support = _support(avoided, burden)
            if support == "positive":
                positive_counts[measure.id] += 1
            _finite_result(
                burden
                + sampled_baseline
                * (1.0 - probability_reduction)
                * (1.0 - severity_reduction),
                "sampled total social cost",
            )
            if support == "positive" and net_benefit > best_net_benefit and not math.isclose(
                net_benefit, best_net_benefit, rel_tol=1e-12, abs_tol=1e-12
            ):
                best_id = measure.id
                best_net_benefit = net_benefit
        preferred_counts[best_id] += 1

    simulation_measures = []
    for measure in measures:
        values = sorted(samples[measure.id])
        share = positive_counts[measure.id] / draws
        simulation_measures.append(
            {
                "id": measure.id,
                "name": measure.name,
                "p05": _quantile(values, 0.05),
                "p50": _quantile(values, 0.50),
                "p95": _quantile(values, 0.95),
                "positive_share": share,
                "mc_standard_error": math.sqrt(share * (1.0 - share) / draws),
            }
        )

    return {
        "units": {
            "currency": "input_currency",
            "time_basis": "per_year",
            "event_probability_basis": "per_exposure",
        },
        "point_estimate": {
            "method": "triangular_modes; not the mean of the uncertain output",
            "conditional_expected_loss_per_event": loss,
            "expected_event_count_annual": exposures * probability.mode,
            "baseline_expected_loss_annual": baseline,
            "measures": point_measures,
            "preferred_measure_id": preferred_id,
        },
        "bounds": {
            "method": "conservative input corners; not confidence intervals",
            "baseline_expected_loss_annual": {"min": baseline_low, "max": baseline_high},
            "measures": bound_measures,
        },
        "simulation": {
            "draws": draws,
            "seed": seed,
            "method": "independent triangular parameter draws with a shared baseline",
            "net_benefit_by_measure": simulation_measures,
            "preferred_share": {
                measure_id: count / draws for measure_id, count in preferred_counts.items()
            },
            "tie_policy": "baseline first, then input order; numerical equality tolerance 1e-12",
        },
        "assumptions": [
            "All monetary inputs use one currency and price year; all comparisons are annual.",
            "N is annual exposures and p is event probability per exposure; N*p is an expected event count, not a probability.",
            "Loss-category shares are fixed, mutually exclusive, exhaustive and conditional on one event.",
            "Loss components within each category are additive and must not double-count the same loss.",
            "Each measure is an alternative complete package; effects of separate packages are not combined.",
            "Initial cost is annualized over its useful life with no residual value; annual costs and risks are stationary.",
            "The same loss-proportion reduction applies across categories; probability and severity reductions multiply residual loss.",
            "Monte Carlo assumes independent marginal triangular parameter distributions; all measures share each draw's baseline probability and losses.",
            "Monte Carlo represents input uncertainty, not realized accidents or a probability of legal liability.",
            "positive_share is the fraction of assumed parameter draws with positive net benefit; mc_standard_error is simulation error, not empirical uncertainty.",
            "Equal economic values use relative and absolute floating-point tolerances of 1e-12; baseline wins ties.",
            "Economic support, risk differences and relative reductions do not establish legal breach or causation.",
        ],
    }
