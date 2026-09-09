import { after, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import handler from '../netlify/functions/api.mjs';

// Exercise the deployed handler without starting a server or contacting sources.
const originalFetch = globalThis.fetch;
let networkAttempts = 0;
globalThis.fetch = async () => {
  networkAttempts += 1;
  throw new Error('Network is forbidden in scoring contract tests');
};
after(() => {
  globalThis.fetch = originalFetch;
  assert.equal(networkAttempts, 0, 'the scoring suite must remain offline');
});

async function get(path) {
  const response = await handler(new Request(`http://offline.invalid/api/${path}`));
  assert.equal(response.status, 200);
  return response.json();
}

async function rest(body, raw = false) {
  const init = { method: 'POST', headers: { 'content-type': 'application/json' } };
  if (body !== undefined) init.body = raw ? body : JSON.stringify(body);
  const response = await handler(new Request('http://offline.invalid/api/score', init));
  return { status: response.status, body: await response.json() };
}

async function mcp(args) {
  const response = await handler(new Request('http://offline.invalid/api/mcp', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 2, method: 'tools/call',
      params: { name: 'score_factors', arguments: args },
    }),
  }));
  const envelope = await response.json();
  const out = envelope.result?.content?.[0]?.text;
  return {
    status: response.status,
    envelope,
    body: out === undefined ? envelope.error : JSON.parse(out),
  };
}

async function score(module, facts = {}) {
  const input = { module, facts };
  const direct = await rest(input);
  const tool = await mcp(input);
  assert.equal(direct.status, 200, JSON.stringify(direct.body));
  assert.ok(!tool.envelope.error, JSON.stringify(tool.envelope));
  assert.notEqual(tool.envelope.result?.isError, true);
  assert.deepEqual(tool.body, direct.body, `${module}: REST/MCP agreement`);
  return direct.body;
}

async function reject(input, field) {
  const direct = await rest(input);
  assert.ok(direct.status >= 400 && direct.status < 500, JSON.stringify(direct));
  assert.ok(direct.body.error || direct.body.errors?.length, 'actionable REST error');
  if (field) assert.ok(JSON.stringify(direct.body).includes(field), `error identifies ${field}`);
  const tool = await mcp(input);
  assert.ok(tool.envelope.error || tool.envelope.result?.isError === true, 'MCP must flag rejection');
  assert.ok(tool.body?.error || tool.body?.errors?.length || tool.envelope.error, 'actionable MCP error');
  if (field) assert.ok(JSON.stringify(tool.body).includes(field), `MCP error identifies ${field}`);
}

const index = await get('scored');
const modules = await Promise.all(index.modules.map((m) => get(`scored/${encodeURIComponent(m.id)}`)));
const moduleById = (id) => {
  const module = modules.find((m) => m.id === id);
  assert.ok(module, `fixture module ${id} exists`);
  return module;
};
const allFactors = (stage) => [...(stage.factors || []), ...(stage.counter_factors || [])];
const moduleFacts = (module, value) => Object.fromEntries(module.stages.flatMap(allFactors).map((f) => [f.id, value]));
const ids = (list) => list.map((f) => f.id).sort();
const stageResult = (output, id) => {
  const stage = output.stages.find((s) => s.stage === id);
  assert.ok(stage, `result stage ${id} exists`);
  return stage;
};
const approx = (actual, expected, message = '') => {
  assert.ok(Number.isFinite(actual), `${message}: expected finite number, got ${actual}`);
  assert.ok(Math.abs(actual - expected) < 1e-9, `${message}: ${actual} != ${expected}`);
};

it('preserves module and stage litigation positions across REST and MCP scoring', async () => {
  const source = moduleById('NYC');
  const output = await score('NYC');
  for (const field of ['litigation_postures', 'litigation_track', 'primary_posture', 'legal_kind', 'role_confidence', 'court_own_motion_summary', 'litigation_note']) {
    assert.deepEqual(output[field], source[field], `NYC module ${field}`);
  }
  for (const sourceStage of source.stages) {
    const resultStage = stageResult(output, sourceStage.id);
    for (const field of ['litigation_postures', 'litigation_track', 'primary_posture', 'court_own_motion', 'litigation_note']) {
      assert.deepEqual(resultStage[field], sourceStage[field], `${sourceStage.id} ${field}`);
    }
  }
  assert.deepEqual(stageResult(output, 'NY-2').litigation_postures, []);
  assert.equal(stageResult(output, 'NY-2').court_own_motion, true);
});

function nonnumeric(stage) {
  for (const field of ['score', 'score_low', 'score_high', 'score_mid']) {
    assert.ok(stage[field] === undefined || stage[field] === null, `${stage.stage}: ${field} must be absent/null`);
  }
  assert.notEqual(stage.interval_decides, true);
}

function manual(stage) {
  assert.ok(['manual-checklist', 'unsupported'].includes(stage.result), JSON.stringify(stage));
  nonnumeric(stage);
  assert.doesNotMatch([stage.reason, stage.note, stage.caveat].filter(Boolean).join(' '), /calibrat|regression/i,
    'missing legal semantics must not be described as missing weight calibration');
}

function checklist(stage, fixture) {
  assert.equal(stage.zh, fixture.zh);
  assert.equal(stage.en, fixture.en);
  assert.equal(stage.test_type, fixture.test_type);
  for (const key of ['factors_present', 'factors_absent', 'factors_against', 'unresolved', 'next_evidence']) {
    assert.ok(Array.isArray(stage[key]), `${stage.stage}: ${key} is a checklist`);
  }
  const assigned = [...stage.factors_present, ...stage.factors_absent, ...stage.factors_against, ...stage.unresolved];
  assert.deepEqual(ids(assigned), ids(allFactors(fixture)), `${stage.stage}: every factor represented once`);
}

describe('scoring public input contract', () => {
  it('defaults an omitted REST module to HKJUR and omitted facts to an empty record', async () => {
    const expected = await score('HKJUR');
    assert.deepEqual((await rest({})).body, expected);
    assert.deepEqual((await rest({ facts: {} })).body, expected);
    assert.deepEqual((await rest({ module: 'HKJUR' })).body, expected);
    assert.deepEqual((await mcp({ module: 'HKJUR' })).body, expected);
  });

  it('rejects malformed, missing and nonobject REST bodies', async () => {
    for (const body of [undefined, '{', '', 'null', '[]', '"text"', 'false', '0']) {
      const response = await rest(body, true);
      assert.ok(response.status >= 400 && response.status < 500, `body ${String(body)}: ${JSON.stringify(response)}`);
      assert.ok(response.body.error || response.body.errors?.length);
    }
  });

  it('rejects nonobject MCP arguments and requires its module', async () => {
    for (const args of [undefined, null, [], ['HKJUR'], 'HKJUR', 0, false, {}, { facts: {} }]) {
      const response = await mcp(args);
      assert.ok(response.envelope.error || response.envelope.result?.isError === true, JSON.stringify(response));
      assert.ok(response.body?.error || response.body?.errors?.length || response.envelope.error);
    }
  });

  it('rejects invalid module values instead of silently applying the default', async () => {
    for (const module of [null, '', ' ', false, 0, [], {}, 'not-a-module']) {
      await reject({ module, facts: {} }, 'module');
    }
  });

  it('rejects explicitly invalid facts shapes', async () => {
    for (const facts of [null, [], [true], false, true, 0, 1, '', 'unknown']) {
      await reject({ module: 'HKJUR', facts }, 'facts');
    }
  });

  it('rejects unsupported fact values with the offending factor id', async () => {
    for (const value of ['', 'TRUE', 'False', ' yes ', '1', '0', 'maybe', 2, -1, 0.5, [], [true], {}]) {
      await reject({ module: 'HKJUR', facts: { 'F-governing-law': value } }, 'F-governing-law');
    }
  });

  it('rejects unknown factor ids, including false/unknown values and object prototype names', async () => {
    for (const value of [true, false, null, '?']) {
      await reject({ module: 'HKJUR', facts: { 'F-governing-lwa': value } }, 'F-governing-lwa');
    }
    for (const id of ['constructor', 'toString', '__proto__']) {
      const facts = JSON.parse(`{"${id}":true}`);
      await reject({ module: 'HKJUR', facts }, id);
    }
    const foreign = moduleById('CONTRACT').stages[0].factors[0].id;
    await reject({ module: 'HKJUR', facts: { [foreign]: true } }, foreign);
  });

  for (const [state, aliases] of [
    [true, [true, 1, 'true', 'yes']],
    [false, [false, 0, 'false', 'no']],
    [null, [null, 'unknown', '?']],
  ]) {
    it(`normalizes all ${String(state)} aliases consistently across weighted and gate factors`, async () => {
      const fixtureIds = ['F-governing-law', 'C-alt-forum', 'G-presence', 'E-ejc-present', 'E-strong-cause'];
      const expected = await score('HKJUR', Object.fromEntries(fixtureIds.map((id) => [id, state])));
      for (const alias of aliases) {
        const output = await score('HKJUR', Object.fromEntries(fixtureIds.map((id) => [id, alias])));
        assert.deepEqual(output, expected);
      }
      if (state === null) assert.deepEqual(expected, await score('HKJUR', {}));
    });
  }
});

describe('every module preserves evidence and stage semantics', () => {
  it('covers all 14 currently exposed modules', () => assert.equal(modules.length, 14));

  for (const fixture of modules) {
    it(`${fixture.id}: empty facts are unresolved and never decisive`, async () => {
      const result = await score(fixture.id);
      assert.equal(result.overall, 'undetermined');
      assert.ok(typeof result.overall_reason === 'string' && result.overall_reason.trim());
      assert.equal(result.stages.length, fixture.stages.length);
      for (const raw of fixture.stages) {
        const stage = stageResult(result, raw.id);
        checklist(stage, raw);
        assert.deepEqual(ids(stage.unresolved), ids(allFactors(raw)));
        assert.equal(stage.factors_present.length + stage.factors_absent.length + stage.factors_against.length, 0);
        if (stage.evidence_resolved !== undefined) assert.equal(stage.evidence_resolved, 0);
        assert.notEqual(stage.interval_decides, true);
        if (raw.test_type === 'balancing') {
          assert.equal(stage.result, 'undetermined');
          assert.equal(stage.interval_decides, false);
          assert.equal(stage.evidence_resolved, 0);
          assert.ok(stage.reason || stage.note || stage.caveat, 'insufficient evidence explanation');
          assert.ok(stage.score_low <= stage.score_high);
        } else if (raw.id === 'HKJUR-4') {
          assert.equal(stage.result, 'undetermined');
          assert.equal(stage.engaged, null);
          nonnumeric(stage);
        } else manual(stage);
      }
    });

    it(`${fixture.id}: complete true/false and partial records retain per-stage checklists`, async () => {
      for (const value of [true, false]) {
        const result = await score(fixture.id, moduleFacts(fixture, value));
        if (fixture.stages.length > 1) {
          assert.equal(result.overall, 'undetermined');
          assert.ok(result.overall_reason);
        }
        for (const raw of fixture.stages) {
          const stage = stageResult(result, raw.id);
          checklist(stage, raw);
          assert.equal(stage.unresolved.length, 0);
          assert.equal(stage.next_evidence.length, 0);
          if (value) {
            assert.deepEqual(ids(stage.factors_present), ids(raw.factors || []));
            assert.deepEqual(ids(stage.factors_against), ids(raw.counter_factors || []));
            assert.equal(stage.factors_absent.length, 0);
          } else {
            assert.deepEqual(ids(stage.factors_absent), ids(allFactors(raw)));
            assert.equal(stage.factors_present.length + stage.factors_against.length, 0);
          }
          if (raw.test_type === 'balancing') {
            assert.equal(stage.evidence_resolved, 1);
            assert.ok(Number.isFinite(stage.score_low) && Number.isFinite(stage.score_high));
            assert.ok(stage.score_low <= stage.score_high);
            assert.ok(stage.score_mid >= stage.score_low && stage.score_mid <= stage.score_high);
            for (const range of [stage.pro, stage.against, ...stage.factors_present.map((f) => f.range), ...stage.factors_against.map((f) => f.range)]) {
              assert.ok(range.every(Number.isFinite) && range[0] <= range[1], `${raw.id}: every displayed range is ordered`);
            }
          } else if (raw.id !== 'HKJUR-4') manual(stage);
        }
      }
      const first = fixture.stages.flatMap(allFactors)[0];
      const partial = await score(fixture.id, { [first.id]: true });
      for (const raw of fixture.stages) {
        const stage = stageResult(partial, raw.id);
        checklist(stage, raw);
        if (stage.evidence_resolved !== undefined) {
          assert.ok(stage.evidence_resolved >= 0 && stage.evidence_resolved <= 1);
        }
      }
    });
  }

  it('keeps conjunctive and mixed-role OR stages manual even with favorable facts', async () => {
    for (const id of ['CONTRACT', 'LEASE', 'RT', 'VEIL', 'NYC', 'UI']) {
      const fixture = moduleById(id);
      const output = await score(id, moduleFacts(fixture, true));
      for (const raw of fixture.stages.filter((s) => ['conjunctive', 'disjunctive-gateway'].includes(s.test_type))) {
        manual(stageResult(output, raw.id));
      }
      assert.equal(output.overall, 'undetermined', `${id}: no invented dependency graph`);
    }
  });
});

// Enumerate concrete worlds: each selected fact is present/absent and each
// assigned band takes either endpoint. This checks the returned interval against
// realizable scores, independently of the scorer's interval aggregation formula.
function endpointWorlds(selected, states) {
  let worlds = [0];
  for (let i = 0; i < selected.length; i += 1) {
    const { factor, counter } = selected[i];
    const endpoints = [factor.weight_low ?? factor.weight, factor.weight_high ?? factor.weight];
    assert.ok(endpoints.every(Number.isFinite));
    const contributions = [];
    for (const present of states[i] === null ? [false, true] : [states[i]]) {
      for (const endpoint of endpoints) contributions.push(present ? (counter ? -Math.abs(endpoint) : Math.abs(endpoint)) : 0);
    }
    worlds = worlds.flatMap((sum) => contributions.map((delta) => sum + delta));
  }
  return worlds;
}

describe('balancing uncertainty ranges and evidence priority', () => {
  for (const [moduleId, stageId] of [['HKJUR', 'HKJUR-2'], ['NUIS', 'NU-1']]) {
    it(`${stageId}: intervals exactly contain all endpoint worlds for 81 tri-state combinations`, async () => {
      const fixture = moduleById(moduleId);
      const raw = fixture.stages.find((s) => s.id === stageId);
      const selected = [
        ...raw.factors.slice(0, 2).map((factor) => ({ factor, counter: false })),
        ...raw.counter_factors.slice(0, 2).map((factor) => ({ factor, counter: true })),
      ];
      assert.equal(selected.length, 4);
      assert.ok(selected.some(({ factor, counter }) => counter && factor.weight_low < 0), 'real negative counter fixture');
      for (let combination = 0; combination < 81; combination += 1) {
        let cursor = combination;
        const states = selected.map(() => {
          const state = [false, true, null][cursor % 3];
          cursor = Math.floor(cursor / 3);
          return state;
        });
        const facts = moduleFacts(fixture, false);
        selected.forEach(({ factor }, i) => { facts[factor.id] = states[i]; });
        const stage = stageResult(await score(moduleId, facts), stageId);
        const worlds = endpointWorlds(selected, states);
        for (const world of worlds) {
          assert.ok(world >= stage.score_low - 1e-9 && world <= stage.score_high + 1e-9,
            `${stageId} ${JSON.stringify(states)} excludes ${world} from [${stage.score_low}, ${stage.score_high}]`);
        }
        approx(stage.score_low, Math.min(...worlds), `${stageId} lower endpoint`);
        approx(stage.score_high, Math.max(...worlds), `${stageId} upper endpoint`);
        assert.ok(stage.score_low <= stage.score_mid && stage.score_mid <= stage.score_high);
        assert.ok(stage.evidence_resolved >= 0 && stage.evidence_resolved <= 1);
      }
    });
  }

  it('includes every unresolved pro/counter factor with sorted maximum swing', async () => {
    const output = await score('HKJUR');
    for (const raw of moduleById('HKJUR').stages.filter((s) => s.test_type === 'balancing')) {
      const stage = stageResult(output, raw.id);
      assert.deepEqual(ids(stage.next_evidence), ids(allFactors(raw)));
      let previous = Infinity;
      for (const item of stage.next_evidence) {
        const factor = allFactors(raw).find((f) => f.id === item.id);
        const max = Math.max(Math.abs(factor.weight_low ?? factor.weight), Math.abs(factor.weight_high ?? factor.weight));
        assert.equal(item.direction, raw.counter_factors?.some((f) => f.id === item.id) ? 'counter' : 'pro');
        assert.deepEqual(item.swing, [0, max]);
        approx(item.maximum_swing, max, item.id);
        assert.ok(item.maximum_swing <= previous, 'priority sorted by maximum swing');
        previous = item.maximum_swing;
      }
    }
    assert.ok(output.priority_evidence.some((f) => f.id === 'C-alt-forum' && f.direction === 'counter'));
    for (let i = 1; i < output.priority_evidence.length; i += 1) {
      assert.ok(output.priority_evidence[i].maximum_swing <= output.priority_evidence[i - 1].maximum_swing);
    }
  });

  it('retains unknown counter risk when known pro factors would otherwise look decisive', async () => {
    const fixture = moduleById('HKJUR');
    const raw = fixture.stages.find((s) => s.id === 'HKJUR-2');
    const facts = moduleFacts(fixture, false);
    for (const factor of raw.factors) facts[factor.id] = true;
    for (const factor of raw.counter_factors) delete facts[factor.id];
    const partial = stageResult(await score('HKJUR', facts), raw.id);
    const worlds = endpointWorlds([
      ...raw.factors.map((factor) => ({ factor, counter: false })),
      ...raw.counter_factors.map((factor) => ({ factor, counter: true })),
    ], [...raw.factors.map(() => true), ...raw.counter_factors.map(() => null)]);
    approx(partial.score_low, Math.min(...worlds));
    approx(partial.score_high, Math.max(...worlds));
    assert.equal(partial.interval_decides, false);
    assert.deepEqual(ids(partial.next_evidence), ids(raw.counter_factors));
    assert.ok(partial.evidence_resolved > 0 && partial.evidence_resolved < 1);
  });
});

describe('modeled threshold uses three-valued gate and override states', () => {
  for (const gate of [null, false, true]) for (const override of [null, false, true]) {
    it(`HKJUR-4 gate=${gate}, override=${override}`, async () => {
      const result = await score('HKJUR', { 'E-ejc-present': gate, 'E-strong-cause': override });
      const stage = stageResult(result, 'HKJUR-4');
      assert.equal(stage.engaged, gate);
      const expected = gate === null ? 'undetermined' : gate === false ? 'not-engaged'
        : override === null ? 'undetermined' : override ? 'departure-permitted' : 'clause-enforced';
      assert.equal(stage.result, expected);
      nonnumeric(stage);
      assert.equal(result.overall, 'undetermined');
      assert.ok(result.overall_reason);
    });
  }
});

// Private-helper fixtures exercise schema states absent from the current real
// dataset. Fresh objects only: generated modules and their exports are untouched.
function synthetic(stage) {
  return { id: 'SYNTHETIC', zh: '合成测试', en: 'Synthetic test fixture', jurisdiction: 'HK', stages: [stage] };
}
const factorFixture = (id, extra = {}) => ({ id, zh: `测试 ${id}`, en: `Fixture ${id}`, ...extra });
async function helperScore(stage, facts = {}) {
  const { scoreModule } = await import('../netlify/functions/scoring.mjs');
  return scoreModule(synthetic(stage), facts).stages[0];
}

describe('explicit fallback for unusable weights or missing test semantics', () => {
  it('does not score an incomplete balancing stage from its remaining weighted factors', async () => {
    const good = factorFixture('good', { weight: 0.15, weight_low: 0.1, weight_high: 0.2 });
    for (const extra of [
      {}, { weight: null }, { weight: NaN }, { weight: Infinity }, { weight: '0.2' },
      { weight_low: 0.1 }, { weight_low: 0.1, weight_high: null },
      { weight_low: 0.1, weight_high: Infinity }, { weight_low: 0.1, weight_high: '0.2' },
      { weight: 0.15, weight_low: 0.1 }, { weight: 0.15, weight_low: null, weight_high: null },
      { weight: 0.15, weight_low: -0.1, weight_high: 0.2 },
      { weight: -0.1 }, { weight_low: -0.2, weight_high: -0.1 },
    ]) {
      const stage = await helperScore({ id: 'incomplete', test_type: 'balancing', factors: [good, factorFixture('bad', extra)] }, { good: true });
      nonnumeric(stage);
      assert.equal(stage.weights, 'incomplete', JSON.stringify(extra));
      assert.ok(stage.reason || stage.note);
      assert.deepEqual(ids(stage.unresolved), ['bad']);
    }
    const none = await helperScore({ id: 'unassigned', test_type: 'balancing', factors: [factorFixture('a')] });
    nonnumeric(none);
    assert.equal(none.weights, 'unassigned');
  });

  it('rejects missing or mixed-sign counter ranges without silently taking absolute values', async () => {
    for (const extra of [{}, { weight: 0.2, weight_low: -0.1, weight_high: 0.3 },
      { weight_low: -1e-200, weight_high: 1e-200 },
      { weight_low: 1e-200, weight_high: -1e-200 }]) {
      const stage = await helperScore({ id: 'bad-counter', test_type: 'balancing',
        factors: [factorFixture('p', { weight: 0.2 })],
        counter_factors: [factorFixture('c', extra)] }, { p: true, c: true });
      nonnumeric(stage);
      assert.equal(stage.weights, 'incomplete');
    }
  });

  it('does not declare a zero-weight unknown fact resolved merely because the interval has zero width', async () => {
    const fixture = { id: 'zero', test_type: 'balancing', factors: [factorFixture('f', { weight: 0 })] };
    const unknown = await helperScore(fixture);
    assert.equal(unknown.result, 'undetermined');
    assert.equal(unknown.evidence_resolved, 0);
    assert.equal(unknown.interval_decides, false);
    approx(unknown.score_low, 0);
    approx(unknown.score_high, 0);
    const resolved = await helperScore(fixture, { f: true });
    assert.equal(resolved.evidence_resolved, 1);
  });

  it('handles point weights and positive counter bands without reversing signed contributions', async () => {
    const stage = await helperScore({ id: 'point', test_type: 'balancing', factors: [factorFixture('p', { weight: 0.2 })],
      counter_factors: [factorFixture('c', { weight_low: 0.1, weight_high: 0.3 })] }, { p: true, c: true });
    approx(stage.score_low, -0.1);
    approx(stage.score_high, 0.1);
    assert.equal(stage.evidence_resolved, 1);
  });

  it('keeps unsupported, conjunctive and presumption-rebuttal types nonnumeric despite supplied weights', async () => {
    for (const type of ['future-unknown-type', 'conjunctive', 'presumption-rebuttal', 'disjunctive-gateway']) {
      const stage = await helperScore({ id: type, test_type: type, factors: [factorFixture('f', { weight: 1 })] }, { f: true });
      manual(stage);
      assert.deepEqual(ids(stage.factors_present), ['f']);
    }
  });

  it('requires distinct, uniquely identified gate and override roles before evaluating a threshold', async () => {
    const definitions = [
      [], [factorFixture('a')], [factorFixture('a', { gate: true })], [factorFixture('a', { override: true })],
      [factorFixture('a', { gate: true, override: true })],
      [factorFixture('a', { gate: true }), factorFixture('b', { gate: true }), factorFixture('c', { override: true })],
      [factorFixture('a', { gate: true }), factorFixture('b', { override: true }), factorFixture('c', { override: true })],
    ];
    for (const factors of definitions) {
      const facts = Object.fromEntries(factors.map((f) => [f.id, true]));
      const stage = await helperScore({ id: 'unmodeled', test_type: 'threshold-discretion', factors }, facts);
      manual(stage);
      assert.equal(stage.engaged, null);
    }
  });
});
