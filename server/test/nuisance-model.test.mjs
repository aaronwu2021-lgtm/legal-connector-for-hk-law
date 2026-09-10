import { test } from 'node:test';
import assert from 'node:assert/strict';
import REGISTRY from '../netlify/functions/_registry.mjs';

const WEIGHT_KEYS = ['weight', 'weight_low', 'weight_high', 'weight_source', 'weight_status', 'tier'];

test('private nuisance is one cause structure with elements, an internal test, defences and remedy', () => {
  const nuisance = REGISTRY.modules.find((module) => module.id === 'NUIS');
  assert.ok(nuisance);
  assert.equal(nuisance.legal_kind, 'cause-of-action');
  assert.equal(nuisance.top_type, 'conjunctive');
  assert.deepEqual(nuisance.logic_types, [
    'conjunctive',
    'disjunctive-gateway',
    'threshold-discretion',
  ]);

  assert.deepEqual(nuisance.stages.map((stage) => [stage.id, stage.doctrinal_role]), [
    ['NU-1', 'claim-elements'],
    ['NU-2', 'claim-elements'],
    ['NU-3', 'claim-elements'],
    ['NU-4', 'internal-test'],
    ['NU-5', 'claim-elements'],
    ['NU-6', 'defence'],
    ['NU-7', 'remedy'],
  ]);
  assert.deepEqual(nuisance.stages.find((stage) => stage.id === 'NU-4').applies_when, {
    stage_id: 'NU-2',
    factor_ids: ['NU-route-amenity'],
  });
});

test('private nuisance liability has no numeric balance and public interest appears only at remedy', () => {
  const nuisance = REGISTRY.modules.find((module) => module.id === 'NUIS');
  assert.ok(nuisance.stages.every((stage) => stage.test_type !== 'balancing'));

  for (const stage of nuisance.stages) for (const factor of stage.factors) {
    for (const key of WEIGHT_KEYS) {
      assert.equal(Object.hasOwn(factor, key), false, `${stage.id}/${factor.id}: ${key}`);
    }
  }

  const publicInterestStages = nuisance.stages.filter((stage) =>
    stage.factors.some((factor) => factor.id === 'NU-public-interest-remedy'));
  assert.deepEqual(publicInterestStages.map((stage) => stage.id), ['NU-7']);
  const remedy = nuisance.stages.find((stage) => stage.id === 'NU-7');
  assert.match(remedy.rule, /门槛成立后/);
  assert.equal(remedy.factors.find((factor) => factor.id === 'NU-remedy-threshold').gate, true);
  assert.ok(
    remedy.factors
      .filter((factor) => factor.id !== 'NU-remedy-threshold')
      .every((factor) => factor.role === 'discretion'),
  );
});

test('private nuisance authorities disclose primary pins and the HK authority limitation', () => {
  const nuisance = REGISTRY.modules.find((module) => module.id === 'NUIS');
  assert.equal(nuisance.authorities.length, 7);
  for (const authority of nuisance.authorities) {
    assert.equal(authority.verified, 'primary', authority.case);
    assert.ok(authority.pin, authority.case);
    assert.match(authority.src, /^https:\/\/\S+$/, authority.case);
  }
  assert.match(nuisance.note, /CFI/);
  assert.match(nuisance.note, /Fearn 在香港仅具说服力/);
  assert.match(nuisance.note, /SG 整体在本版本不作结论/);
  assert.match(nuisance.note, /quia timet/);
  const temporal = nuisance.stages.find((stage) => stage.id === 'NU-3');
  assert.match(temporal.jurisdiction_rules.EN, /Network Rail/);
  assert.match(temporal.jurisdiction_rules.HK, /覆盖缺口/);
  assert.deepEqual(temporal.factors.map((factor) => factor.id), ['NU-accrued', 'NU-quia-timet']);
  const amenity = nuisance.stages.find((stage) => stage.id === 'NU-4');
  assert.match(amenity.jurisdiction_rules.EN, /Fearn/);
  assert.match(amenity.jurisdiction_rules.HK, /Century Way/);
});
