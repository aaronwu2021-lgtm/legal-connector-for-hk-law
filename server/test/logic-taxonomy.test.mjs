import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import handler from '../netlify/functions/api.mjs';
import REGISTRY from '../netlify/functions/_registry.mjs';
import SCORED from '../netlify/functions/_scored.mjs';

const TYPES = [
  'conjunctive',
  'disjunctive-gateway',
  'balancing',
  'threshold-discretion',
  'presumption-rebuttal',
];
const expectedLabels = ['合取要件', '择一门槛', '多因素权衡', '门槛后裁量', '推定与反驳'];
const allModules = [...SCORED.modules, ...REGISTRY.modules];
const allFactors = stage => [...(stage.factors || []), ...(stage.counter_factors || [])];

async function get(path) {
  const response = await handler(new Request(`http://offline.invalid/api/${path}`));
  assert.equal(response.status, 200);
  return response.json();
}

test('one canonical catalogue exposes all five legal-test logic types', () => {
  assert.deepEqual(Object.keys(SCORED.test_types), TYPES);
  assert.deepEqual(Object.keys(REGISTRY.test_types), TYPES);
  assert.deepEqual(TYPES.map(type => SCORED.test_types[type].zh), expectedLabels);
  assert.deepEqual(REGISTRY.test_types, SCORED.test_types);
});

test('weights exist only inside multi-factor balancing stages', () => {
  for (const module of allModules) for (const stage of module.stages) {
    assert.ok(TYPES.includes(stage.test_type), `${module.id}/${stage.id}: unknown test type`);
    if (stage.test_type === 'balancing') continue;
    for (const factor of allFactors(stage)) {
      for (const key of ['weight', 'weight_low', 'weight_high', 'weight_source', 'weight_status', 'tier']) {
        assert.equal(Object.hasOwn(factor, key), false, `${module.id}/${stage.id}/${factor.id}: ${key} is not applicable`);
      }
    }
  }
});

test('logic profiles and hklandlaw coverage are separate structured metadata', () => {
  for (const module of REGISTRY.modules) {
    assert.ok(Array.isArray(module.logic_types) && module.logic_types.length > 0, module.id);
    assert.ok(module.logic_types.every(type => TYPES.includes(type)), module.id);
    assert.deepEqual(module.source_counts, { hklandlaw: module.corpus_hits });
  }
  const rt = REGISTRY.modules.find(module => module.id === 'RT');
  assert.ok(rt.logic_types.includes('presumption-rebuttal'));
  assert.ok(rt.logic_types.includes('disjunctive-gateway'));
  assert.equal(REGISTRY.source_catalog.hklandlaw.unit, 'article');
});

test('registry and scored indexes agree on explicit weight applicability and status', async () => {
  const [registry, scored] = await Promise.all([get('registry'), get('scored')]);
  assert.deepEqual(Object.keys(registry.by_test_type), TYPES);
  assert.deepEqual(registry.by_test_type, registry.stage_counts_by_test_type);
  assert.match(registry.by_test_type_scope, /stages/);
  assert.equal(registry.stage_counts_by_test_type['presumption-rebuttal'], 0);
  assert.equal(registry.module_counts_by_logic_type['presumption-rebuttal'], 2);
  const stageRows = index => new Map(index.modules.flatMap(module => module.stages.map(stage => [
    `${module.id}/${stage.id}`, stage,
  ])));
  const left = stageRows(registry), right = stageRows(scored);
  assert.deepEqual([...left.keys()], [...right.keys()]);
  for (const [id, stage] of left) {
    const peer = right.get(id);
    assert.equal(stage.weight_applicable, stage.test_type === 'balancing', id);
    assert.equal(stage.weight_applicable, peer.weight_applicable, id);
    assert.equal(stage.weight_status, peer.weight_status, id);
    assert.equal(stage.weight_provenance, peer.weight_provenance, id);
    assert.equal(stage.weighted, peer.weighted, id);
    if (!stage.weight_applicable) {
      assert.equal(stage.weight_status, 'not-applicable', id);
      assert.equal(stage.weight_provenance, null, id);
    } else if (stage.weight_status === 'assigned') {
      assert.equal(stage.weighted, true, id);
      assert.equal(stage.weight_provenance, 'doctrinal-tier', id);
    }
  }
});

test('presumption-rebuttal filtering finds modules with an overall presumption structure', async () => {
  const response = await handler(new Request('http://offline.invalid/api/mcp', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: {
      name: 'list_causes_of_action', arguments: { test_type: 'presumption-rebuttal' },
    } }),
  }));
  const envelope = await response.json();
  const data = JSON.parse(envelope.result.content[0].text);
  assert.deepEqual(data.modules.map(module => module.id).sort(), ['RT', 'UI']);
});

test('the balancing queue treats a complete range as assigned and returns structured source counts', async () => {
  const module = REGISTRY.modules.find(item => item.id === 'PE');
  const stage = module.stages.find(item => item.test_type === 'balancing');
  const factor = stage.factors[0];
  const saved = {
    weight: factor.weight,
    weight_low: factor.weight_low,
    weight_high: factor.weight_high,
  };
  try {
    delete factor.weight;
    let queue = await get('calibration-queue');
    assert.equal(queue.rows.some(row => row.module === module.id && row.stage === stage.id), false);

    delete factor.weight_low;
    delete factor.weight_high;
    queue = await get('calibration-queue');
    const row = queue.rows.find(item => item.module === module.id && item.stage === stage.id);
    assert.ok(row);
    assert.deepEqual(row.source_counts, { hklandlaw: module.corpus_hits });
    assert.ok(row.factors.some(item => item.id === factor.id));
  } finally {
    Object.assign(factor, saved);
  }
});

test('the page names logic, source coverage and balancing-only quantities separately', () => {
  const html = readFileSync(new URL('../public/index.html', import.meta.url), 'utf8');
  assert.match(html, /判断逻辑 Logic/);
  assert.doesNotMatch(html, /权重 Scoring/);
  assert.match(html, /hklandlaw · /);
  assert.match(html, /isBalancing\?'相对份量（编者档位）':'逻辑作用'/);
  assert.doesNotMatch(html, /<th>权重<\/th>/);
  assert.match(html, /证据与阶段结果/);
});
