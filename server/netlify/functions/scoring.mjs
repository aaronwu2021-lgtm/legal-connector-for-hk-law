// Pure scoring helpers. Stored model data is read, never changed.
// Intervals describe model scenarios, not a probability or a court outcome.

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const own = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
const clean = (value) => Number(value.toPrecision(15));
const objectRecord = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

export function validationError(message, errors = [message]) {
  return { error: message, errors, result: 'invalid-input' };
}

export function validateScoreRequest(body, requireModule = false) {
  if (!objectRecord(body)) return validationError('Score request must be a non-null object.');
  if (body.module === undefined && !requireModule) return { module: 'HKJUR', facts: body.facts };
  if (typeof body.module !== 'string' || !body.module.trim()) {
    return validationError('module must be a nonempty string identifying a supported module.');
  }
  return { module: body.module, facts: body.facts };
}

function factState(value) {
  if (value === undefined || value === null || value === 'unknown' || value === '?') return 'unknown';
  if (value === true || value === 1 || value === 'true' || value === 'yes') return 'present';
  if (value === false || value === 0 || value === 'false' || value === 'no') return 'absent';
  return null;
}

function normalizeFacts(module, supplied) {
  const facts = supplied === undefined ? {} : supplied;
  if (!objectRecord(facts)) return validationError('facts must be a non-null object mapping factor IDs to supported fact values.');
  const ids = new Set(module.stages.flatMap((stage) =>
    [...(stage.factors || []), ...(stage.counter_factors || [])].map((factor) => factor.id)));
  const errors = [];
  const states = Object.create(null);
  for (const [id, value] of Object.entries(facts)) {
    if (!ids.has(id)) {
      errors.push(`Unknown factor ID: ${id}. Use factor IDs from this module.`);
      continue;
    }
    const state = factState(value);
    if (!state) errors.push(`Invalid value for ${id}: use true/false, 1/0, "true"/"false", "yes"/"no", null, "unknown", or "?".`);
    else states[id] = state;
  }
  return errors.length ? validationError('Invalid facts.', errors) : { states };
}

// An explicitly supplied bad/partial range is not replaced with its midpoint.
function magnitudes(factor, direction) {
  let values;
  if (own(factor, 'weight_low') || own(factor, 'weight_high')) {
    if (!finite(factor.weight_low) || !finite(factor.weight_high)) return null;
    values = [factor.weight_low, factor.weight_high];
    if ((values[0] < 0 && values[1] > 0) || (values[0] > 0 && values[1] < 0)) return null;
  } else {
    if (!finite(factor.weight)) return null;
    values = [factor.weight, factor.weight];
  }
  if (direction === 'pro' && values.some((value) => value < 0)) return null;
  return [Math.min(...values.map(Math.abs)), Math.max(...values.map(Math.abs))];
}

function stageFacts(stage, states) {
  const entries = [
    ...(stage.factors || []).map((factor) => ({ factor, direction: 'pro' })),
    ...(stage.counter_factors || []).map((factor) => ({ factor, direction: 'counter' })),
  ].map((entry) => ({ ...entry, state: states[entry.factor.id] || 'unknown' }));
  const row = ({ factor, direction }) => ({
    id: factor.id, zh: factor.zh, en: factor.en, direction,
    tier: factor.tier || null, look_for: factor.evidence || null,
  });
  const resolved = entries.filter((entry) => entry.state !== 'unknown').length;
  return {
    entries,
    checklist: {
      factors_present: entries.filter((entry) => entry.state === 'present' && entry.direction === 'pro').map(row),
      factors_against: entries.filter((entry) => entry.state === 'present' && entry.direction === 'counter').map(row),
      factors_absent: entries.filter((entry) => entry.state === 'absent').map(row),
      unresolved: entries.filter((entry) => entry.state === 'unknown').map(row),
      next_evidence: [],
      evidence_resolved: entries.length ? clean(resolved / entries.length) : 0,
    },
    row,
  };
}

function manual(base, reason, extras = {}) {
  return { ...base, result: 'manual-checklist', status: 'manual', reason,
    effect: base.rule, ...extras };
}

const bandOf = (value) => value >= 0.55 ? 'strongly for' : value >= 0.30 ? 'leans for'
  : value > -0.10 ? 'finely balanced' : value > -0.35 ? 'leans against' : 'strongly against';

function scoreStage(stage, states) {
  const { entries, checklist, row } = stageFacts(stage, states);
  const base = {
    stage: stage.id, zh: stage.zh, en: stage.en, test_type: stage.test_type,
    litigation_postures: stage.litigation_postures || [],
    litigation_track: stage.litigation_track || null,
    primary_posture: stage.primary_posture ?? null,
    court_own_motion: !!stage.court_own_motion,
    litigation_note: stage.litigation_note || null,
    rule: stage.rule, ...checklist,
  };

  switch (stage.test_type) {
    case 'conjunctive':
      return manual(base, 'The listed factors form a checklist. Required/optional factors and exceptions are not encoded; apply the rule with independent judgment.');
    case 'presumption-rebuttal':
      return manual(base, 'Trigger and rebuttal roles are not modelled with sufficient structure to determine this stage.');
    case 'disjunctive-gateway': {
      const logical = entries.some((entry) => entry.state === 'present') ? 'at-least-one-present'
        : entries.some((entry) => entry.state === 'unknown') || !entries.length ? 'undetermined' : 'none-present';
      return manual(base, 'Gateway roles and legal polarity are not encoded. The logical factor checklist does not determine whether a legal threshold is satisfied.', {
        logical_result: logical, logical_result_is_legal_determination: false, gateways_open: [],
      });
    }
    case 'threshold-discretion': {
      const gates = entries.filter(({ factor }) => factor.gate === true);
      const overrides = entries.filter(({ factor }) => factor.override === true);
      if (gates.length !== 1 || overrides.length !== 1 || gates[0] === overrides[0]
          || gates[0].factor.id === overrides[0].factor.id || entries.length !== 2) {
        return manual(base, 'Exactly one distinct gate and override are not encoded; the threshold requires independent judgment.', { engaged: null });
      }
      const gate = gates[0], override = overrides[0];
      if (gate.state === 'unknown') return {
        ...base, engaged: null, result: 'undetermined', status: 'insufficient-evidence',
        reason: 'The gate fact is unknown; no conclusion about whether this stage is engaged can be drawn.',
        effect: 'Gate presence must be established before applying the encoded override logic.',
      };
      if (gate.state === 'absent') return {
        ...base, engaged: false, result: 'not-engaged', status: 'encoded-gate-result',
        reason: 'The supplied gate fact is false. This describes the encoded stage only, not the module outcome.',
        effect: 'This gate is not engaged on the supplied facts.',
      };
      if (override.state === 'unknown') return {
        ...base, engaged: true, result: 'undetermined', status: 'insufficient-evidence',
        reason: 'The gate is present but the override fact is unknown; enforcement cannot be determined.',
        effect: 'Resolve the override fact before applying the encoded gate logic.',
      };
      return {
        ...base, engaged: true,
        result: override.state === 'present' ? 'departure-permitted' : 'clause-enforced',
        status: 'encoded-gate-result',
        reason: 'This is the already encoded gate/override logic on the supplied facts; it is not a module-wide legal conclusion.',
        effect: override.state === 'present'
          ? 'The encoded override is present; departure is permitted at this stage.'
          : 'The encoded gate is present and its override is absent.',
      };
    }
    case 'balancing':
      break;
    default:
      return manual(base, `Unsupported test type: ${String(stage.test_type)}. No numerical score has been computed.`, { result: 'unsupported', status: 'unsupported' });
  }

  const weighted = entries.map((entry) => ({ ...entry, bounds: magnitudes(entry.factor, entry.direction) }));
  const usable = weighted.filter((entry) => entry.bounds);
  const unresolved = weighted.filter((entry) => entry.state === 'unknown');
  const evidenceRow = (entry) => ({
    ...row(entry),
    swing: entry.bounds ? [0, entry.bounds[1]] : null,
    maximum_swing: entry.bounds ? entry.bounds[1] : null,
  });
  const next = unresolved.map(evidenceRow).sort((a, b) => (b.maximum_swing ?? -1) - (a.maximum_swing ?? -1));
  if (!weighted.length || usable.length !== weighted.length) {
    return manual({ ...base, next_evidence: next },
      'One or more factors lack a usable finite weight or range. No aggregate score has been computed; supplying model weights and gathering fact evidence are separate tasks.', {
        score: null, weights: usable.length ? 'incomplete' : 'unassigned',
        missing_weights: weighted.filter((entry) => !entry.bounds).map(row),
        weight_source: stage.weight_source || 'unspecified',
        caveat: 'Weight assignment is a modelling question; empirical validation is separate. Doctrinal bands are model assumptions and are not outcome probabilities.',
      });
  }

  const withRange = (entry) => ({ ...row(entry),
    range: entry.direction === 'counter' ? [-entry.bounds[1], -entry.bounds[0]] : [...entry.bounds] });
  let low = 0, high = 0, proLow = 0, proHigh = 0, counterLow = 0, counterHigh = 0;
  for (const entry of weighted) {
    if (entry.state === 'absent') continue;
    const [lo, hi] = entry.bounds;
    let a, b;
    if (entry.direction === 'counter') {
      a = -hi; b = entry.state === 'unknown' ? 0 : -lo;
      counterLow += a; counterHigh += b;
    } else {
      a = entry.state === 'unknown' ? 0 : lo; b = hi;
      proLow += a; proHigh += b;
    }
    low += a; high += b;
  }
  if (![low, high, proLow, proHigh, counterLow, counterHigh].every(finite) || low > high) {
    return manual({ ...base, next_evidence: next }, 'The aggregate interval is not a usable finite range; no score has been computed.', { score: null, weights: 'incomplete' });
  }
  const scoreLow = clean(low), scoreHigh = clean(high);
  const hasEvidence = checklist.evidence_resolved > 0;
  const lowerBand = bandOf(scoreLow), upperBand = bandOf(scoreHigh);
  const decided = hasEvidence && lowerBand === upperBand;
  return {
    ...base,
    result: hasEvidence ? 'heuristic-range' : 'undetermined',
    status: hasEvidence ? 'heuristic-only' : 'insufficient-evidence',
    score_low: scoreLow, score_high: scoreHigh, score_mid: clean(scoreLow / 2 + scoreHigh / 2),
    interval_decides: decided,
    band: lowerBand === upperBand ? lowerBand : `${lowerBand} … ${upperBand}`,
    band_meaning: 'Heuristic model band, not a court outcome or probability of success.',
    pro: [clean(proLow), clean(proHigh)], against: [clean(counterLow), clean(counterHigh)],
    factors_present: weighted.filter((entry) => entry.state === 'present' && entry.direction === 'pro').map(withRange),
    factors_against: weighted.filter((entry) => entry.state === 'present' && entry.direction === 'counter').map(withRange),
    unresolved: unresolved.map(evidenceRow), next_evidence: next,
    weight_source: stage.weight_source || 'unspecified',
    uncertainty: {
      fact_presence: unresolved.length > 0,
      weight_bands: weighted.some((entry) => entry.bounds[0] !== entry.bounds[1]),
      legal_outcome_not_computed: true,
    },
    reason: !hasEvidence
      ? 'Insufficient evidence: all applicable facts are unknown. The interval is a scenario range only.'
      : 'The scenario range includes assigned weight bands and every unresolved fact contribution.',
    caveat: !hasEvidence
      ? 'No evidence is resolved, so no heuristic band is declared stable. Gather facts before interpreting the scenario range.'
      : decided
        ? 'The heuristic band is stable across the encoded weight and fact scenarios. This is not a legal determination.'
        : 'The heuristic range spans bands. Unknown facts and assigned weight uncertainty both remain relevant; this is not a legal determination.',
  };
}

export function scoreModule(module, facts) {
  if (!module || !Array.isArray(module.stages)) return validationError('The requested scoring module is unavailable.');
  const normalized = normalizeFacts(module, facts);
  if (normalized.error) return normalized;
  const stages = module.stages.map((stage) => scoreStage(stage, normalized.states));
  const ownMotionStageIds = module.stages.filter((stage) => stage.court_own_motion).map((stage) => stage.id);
  const courtOwnMotionSummary = module.court_own_motion_summary || {
    stage_count: ownMotionStageIds.length,
    stage_ids: ownMotionStageIds,
  };
  const multiStage = stages.length !== 1;
  const singleHeuristic = !multiStage && stages[0].result === 'heuristic-range';
  return {
    module: module.id, zh: module.zh, en: module.en, jurisdiction: module.jurisdiction,
    litigation_postures: module.litigation_postures || [],
    litigation_track: module.litigation_track || null,
    primary_posture: module.primary_posture ?? null,
    legal_kind: module.legal_kind || null,
    role_confidence: module.role_confidence || null,
    court_own_motion_summary: courtOwnMotionSummary,
    litigation_note: module.litigation_note || null,
    overall: singleHeuristic ? 'heuristic-only' : 'undetermined',
    overall_reason: multiStage
      ? 'Stage dependencies and alternative-route semantics are not encoded. Review each stage independently; no module-wide legal conclusion is computed.'
      : singleHeuristic
        ? 'The single-stage output is a heuristic model range, not a court outcome.'
        : 'Evidence or model semantics are insufficient for an overall determination. Use the stage checklists and reasons.',
    authorities: module.authorities, stages,
    priority_evidence: stages.flatMap((stage) => stage.next_evidence)
      .sort((a, b) => (b.maximum_swing ?? -1) - (a.maximum_swing ?? -1)).slice(0, 6),
    note: module.note,
  };
}
