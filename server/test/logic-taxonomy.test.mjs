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
const POSTURES = ['spear', 'shield'];
const TRACKS = ['merits', 'procedure', 'jurisdiction'];
const allModules = [...SCORED.modules, ...REGISTRY.modules];
const allFactors = stage => [...(stage.factors || []), ...(stage.counter_factors || [])];

async function get(path) {
  const response = await handler(new Request(`http://offline.invalid/api/${path}`));
  assert.equal(response.status, 200);
  return response.json();
}

async function mcp(name, args) {
  const response = await handler(new Request('http://offline.invalid/api/mcp', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 17, method: 'tools/call', params: { name, arguments: args } }),
  }));
  assert.equal(response.status, 200);
  const envelope = await response.json();
  assert.notEqual(envelope.result?.isError, true, JSON.stringify(envelope));
  return JSON.parse(envelope.result.content[0].text);
}

test('one canonical catalogue exposes all five legal-test logic types', () => {
  assert.deepEqual(Object.keys(SCORED.test_types), TYPES);
  assert.deepEqual(Object.keys(REGISTRY.test_types), TYPES);
  assert.deepEqual(TYPES.map(type => SCORED.test_types[type].zh), expectedLabels);
  assert.deepEqual(REGISTRY.test_types, SCORED.test_types);
});

test('registry and scored data expose litigation posture and track as separate axes', () => {
  assert.equal(allModules.length, 14);
  assert.equal(new Set(allModules.map(module => module.id)).size, 14);
  for (const index of [REGISTRY, SCORED]) {
    assert.deepEqual(Object.keys(index.posture_catalog).sort(), [...POSTURES].sort());
    assert.deepEqual(Object.keys(index.track_catalog).sort(), [...TRACKS].sort());
  }
  for (const module of allModules) {
    assert.ok(Array.isArray(module.litigation_postures) && module.litigation_postures.length > 0, module.id);
    assert.ok(module.litigation_postures.every(posture => POSTURES.includes(posture)), module.id);
    assert.ok(TRACKS.includes(module.litigation_track), module.id);
    assert.equal(typeof module.role, 'string', `${module.id}: legacy role must remain available`);
    assert.ok(module.role.length > 0, `${module.id}: legacy role must remain populated`);
  }

  const byId = Object.fromEntries(allModules.map(module => [module.id, module]));
  assert.deepEqual(byId.HKJUR.litigation_postures, ['spear', 'shield']);
  assert.equal(byId.HKJUR.litigation_track, 'jurisdiction');
  assert.deepEqual(byId.PE.litigation_postures, ['shield', 'spear']);
  assert.equal(byId.PE.litigation_track, 'merits');
  assert.deepEqual(byId.NYC.litigation_postures, ['shield']);
  assert.equal(byId.NYC.litigation_track, 'procedure');
  assert.deepEqual(byId.ARBCH.litigation_postures, ['spear']);
  assert.equal(byId.ARBCH.litigation_track, 'procedure');
});

test('every legal-test stage declares its own litigation position', () => {
  const stages = allModules.flatMap(module => module.stages.map(stage => ({ module, stage })));
  assert.equal(stages.length, 36);
  for (const { module, stage } of stages) {
    const id = `${module.id}/${stage.id}`;
    for (const key of ['litigation_postures', 'litigation_track', 'primary_posture', 'court_own_motion', 'litigation_note']) {
      assert.equal(Object.hasOwn(stage, key), true, `${id}: missing ${key}`);
    }
    assert.ok(Array.isArray(stage.litigation_postures), `${id}: postures must be an array`);
    assert.equal(new Set(stage.litigation_postures).size, stage.litigation_postures.length, `${id}: duplicate posture`);
    assert.ok(stage.litigation_postures.every(posture => POSTURES.includes(posture)), `${id}: unknown posture`);
    assert.equal(stage.litigation_track, module.litigation_track, `${id}: stage must state its inherited matter track`);
    assert.equal(typeof stage.court_own_motion, 'boolean', `${id}: court_own_motion must be boolean`);
    assert.ok(stage.litigation_postures.length > 0 || stage.court_own_motion, `${id}: empty posture needs own-motion authority`);
    if (stage.primary_posture !== null) {
      assert.ok(stage.litigation_postures.includes(stage.primary_posture), `${id}: primary posture is outside posture set`);
    }
    assert.ok(stage.litigation_note.trim().length > 0, `${id}: litigation note must explain the mapping`);
    assert.equal(Object.hasOwn(module, 'court_own_motion'), false, `${module.id}: module boolean would overgeneralise`);
    const ownMotionIds = module.stages.filter(item => item.court_own_motion).map(item => item.id);
    assert.deepEqual(module.court_own_motion_summary.stage_ids, ownMotionIds, `${module.id}: own-motion summary`);
    assert.equal(module.court_own_motion_summary.stage_count, ownMotionIds.length, `${module.id}: own-motion count`);
  }

  const byStage = Object.fromEntries(stages.map(({ stage }) => [stage.id, stage]));
  assert.deepEqual(stages.filter(({ stage }) => stage.litigation_postures.length === 0).map(({ stage }) => stage.id), ['NY-2']);
  assert.deepEqual(stages.filter(({ stage }) => stage.court_own_motion).map(({ stage }) => stage.id), ['NY-2']);
  assert.deepEqual(byStage['NY-1'].litigation_postures, ['shield']);
  assert.equal(byStage['NY-1'].primary_posture, 'shield');
  assert.equal(byStage['NY-1'].court_own_motion, false);
  assert.deepEqual(byStage['NY-2'].litigation_postures, []);
  assert.equal(byStage['NY-2'].primary_posture, null);
  assert.equal(byStage['NY-2'].court_own_motion, true);
  assert.equal(byStage['NY-3'].test_type, 'threshold-discretion');
  assert.deepEqual(byStage['NY-3'].litigation_postures, ['shield']);
  assert.match(byStage['NY-3'].litigation_note, /裁量/);

  const expectedHkJur = {
    'HKJUR-1': [['spear'], 'spear'],
    'HKJUR-2': [['shield'], 'shield'],
    'HKJUR-3': [['spear'], 'spear'],
    'HKJUR-4': [['spear', 'shield'], null],
  };
  for (const [id, [postures, primary]] of Object.entries(expectedHkJur)) {
    assert.deepEqual(byStage[id].litigation_postures, postures, id);
    assert.equal(byStage[id].primary_posture, primary, id);
    assert.equal(byStage[id].court_own_motion, false, id);
  }
});

test('registry API exposes litigation catalogs and filters modules by posture and track', async () => {
  const registry = await get('registry');
  assert.deepEqual(Object.keys(registry.posture_catalog).sort(), [...POSTURES].sort());
  assert.deepEqual(Object.keys(registry.track_catalog).sort(), [...TRACKS].sort());
  assert.ok(registry.modules.length > 0);
  for (const module of registry.modules) {
    assert.ok(module.litigation_postures.length > 0, module.id);
    assert.ok(module.litigation_postures.every(posture => POSTURES.includes(posture)), module.id);
    assert.ok(TRACKS.includes(module.litigation_track), module.id);
    assert.ok(module.role, `${module.id}: legacy role must remain available through the API`);
  }

  const shield = await get('registry?posture=shield');
  const expectedShield = registry.modules
    .filter(module => module.litigation_postures.includes('shield'))
    .map(module => module.id)
    .sort();
  assert.ok(expectedShield.length > 0);
  assert.ok(expectedShield.length < registry.modules.length);
  assert.deepEqual(shield.modules.map(module => module.id).sort(), expectedShield);
  assert.ok(shield.modules.every(module => module.litigation_postures.includes('shield')));

  const procedure = await get('registry?track=procedure');
  const expectedProcedure = registry.modules
    .filter(module => module.litigation_track === 'procedure')
    .map(module => module.id)
    .sort();
  assert.deepEqual(expectedProcedure, ['ARBCH', 'NYC']);
  assert.deepEqual(procedure.modules.map(module => module.id).sort(), expectedProcedure);
  assert.ok(procedure.modules.every(module => module.litigation_track === 'procedure'));
});

test('doctrine taxonomy separates legacy content status from legal-test coverage', async () => {
  const [taxonomy, elements] = await Promise.all([get('taxonomy'), get('elements')]);
  const claims = taxonomy.areas.flatMap(area => area.claims);
  assert.deepEqual(taxonomy.component_versions, {
    elements: elements.version,
    registry: REGISTRY.version,
    scored: SCORED.version,
  });
  const refs = new Set(claims.map(claim => claim.model_ref?.module_id).filter(Boolean));
  assert.deepEqual([...refs].sort(), allModules.map(module => module.id).sort());
  const legacyStatuses = {
    'proprietary-estoppel': 'corpus-only',
    'constructive-trust': 'corpus-only',
    veil: 'planned',
    'adverse-possession': 'corpus-only',
    'ny-convention': 'planned',
    'arbitrator-challenge': 'planned',
  };
  for (const [id, legacyStatus] of Object.entries(legacyStatuses)) {
    const claim = claims.find(item => item.id === id);
    assert.equal(claim.status, legacyStatus, `${id}: legacy taxonomy status`);
    assert.equal(claim.logic_status, 'full', `${id}: legal-test coverage`);
    assert.ok(claim.litigation_postures.length > 0, id);
    assert.ok(TRACKS.includes(claim.litigation_track), id);
  }
  const remoteness = claims.find(claim => claim.id === 'remoteness');
  const contractRemoteness = allModules.find(module => module.id === 'CONTRACT').stages
    .find(stage => stage.id === 'CT-3');
  assert.equal(remoteness.status, 'planned');
  assert.equal(remoteness.logic_status, 'partial');
  assert.deepEqual(remoteness.model_ref.stage_ids, ['CT-3']);
  assert.deepEqual(remoteness.litigation_postures, contractRemoteness.litigation_postures);
  assert.deepEqual(remoteness.litigation_postures, ['shield']);
  assert.equal(remoteness.litigation_track, contractRemoteness.litigation_track);
  assert.equal(remoteness.litigation_track, 'merits');
  assert.equal(remoteness.primary_posture, contractRemoteness.primary_posture);
  assert.equal(remoteness.primary_posture, 'shield');
  assert.equal(remoteness.litigation_note, contractRemoteness.litigation_note);
  assert.equal(remoteness.role_note, contractRemoteness.litigation_note);
  assert.deepEqual(remoteness.court_own_motion_summary, { stage_count: 0, stage_ids: [] });
  for (const id of ['veil', 'ny-convention', 'arbitrator-challenge', 'exemption-reasonableness']) {
    assert.equal(claims.find(claim => claim.id === id).coverage.corpus, 'none', `${id}: zero corpus hits`);
  }
  assert.equal(claims.find(claim => claim.id === 'proprietary-estoppel').coverage.corpus, 'indexed');
  assert.deepEqual(elements.litigation_profile.groups.elements.litigation_postures, ['spear']);
  assert.deepEqual(elements.litigation_profile.groups.defences.litigation_postures, ['shield']);
  for (const element of elements.elements) {
    assert.deepEqual(element.litigation_postures, ['spear'], element.id);
    assert.equal(element.litigation_track, 'merits', element.id);
    assert.equal(element.litigation_position_source, 'claim-elements', element.id);
    for (const subTest of element.sub_tests) {
      assert.deepEqual(subTest.litigation_postures, ['spear'], subTest.id);
      assert.equal(subTest.litigation_track, 'merits', subTest.id);
      assert.equal(subTest.litigation_position_source, element.id, subTest.id);
    }
  }
  for (const defence of elements.defences) {
    assert.deepEqual(defence.litigation_postures, ['shield'], defence.id);
    assert.equal(defence.litigation_track, 'merits', defence.id);
    assert.equal(defence.litigation_position_source, 'defences', defence.id);
  }
});

test('pleading checklist preserves element and defence litigation positions in REST and MCP', async () => {
  const rest = await get('checklist?jurisdiction=HK');
  const tool = await mcp('pleading_checklist', { jurisdiction: 'HK' });
  assert.deepEqual(tool, rest);
  assert.ok(rest.elements.length > 0);
  assert.ok(rest.defences_to_anticipate.length > 0);
  for (const row of rest.elements) {
    assert.deepEqual(row.litigation_postures, ['spear'], row.sub_test);
    assert.equal(row.litigation_track, 'merits', row.sub_test);
    assert.equal(row.litigation_position_source, row.element, row.sub_test);
  }
  for (const defence of rest.defences_to_anticipate) {
    assert.deepEqual(defence.litigation_postures, ['shield'], defence.id);
    assert.equal(defence.litigation_track, 'merits', defence.id);
    assert.equal(defence.litigation_position_source, 'defences', defence.id);
  }
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
    assert.deepEqual(stage.litigation_postures, peer.litigation_postures, id);
    assert.equal(stage.litigation_track, peer.litigation_track, id);
    assert.equal(stage.primary_posture, peer.primary_posture, id);
    assert.equal(stage.court_own_motion, peer.court_own_motion, id);
    assert.equal(stage.litigation_note, peer.litigation_note, id);
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

test('the page explains litigation posture and track in the doctrine interface', () => {
  const html = readFileSync(new URL('../public/index.html', import.meta.url), 'utf8');
  assert.match(html, /诉讼位置 Litigation position/);
  assert.match(html, /矛 Spear/);
  assert.match(html, /盾 Shield/);
  assert.match(html, /程序 Procedure/);
  assert.match(html, /管辖 Jurisdiction/);
  assert.match(html, /主张要件/);
  assert.match(html, /抗辩/);
});
