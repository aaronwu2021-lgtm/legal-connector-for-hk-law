import { test } from 'node:test';
import assert from 'node:assert/strict';
import handler from '../netlify/functions/api.mjs';

async function get(path) {
  const response = await handler(new Request(`http://offline.invalid/api/${path}`));
  return { response, body: await response.json() };
}

async function mcp(name, args) {
  const response = await handler(new Request('http://offline.invalid/api/mcp', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 23, method: 'tools/call',
      params: { name, arguments: args },
    }),
  }));
  assert.equal(response.status, 200);
  const envelope = await response.json();
  return { envelope, body: JSON.parse(envelope.result.content[0].text) };
}

test('taxonomy gives every claim a uniform composition contract', async () => {
  const { response, body } = await get('taxonomy');
  assert.equal(response.status, 200);
  const claims = body.areas.flatMap((area) => area.claims);
  assert.ok(claims.length > 0);
  for (const claim of claims) {
    assert.ok(Array.isArray(claim.elements), `${claim.id}: elements`);
    assert.ok(Array.isArray(claim.defences), `${claim.id}: defences`);
    assert.ok(claim.model_ref === null || typeof claim.model_ref.module_id === 'string', `${claim.id}: model_ref`);
    assert.deepEqual(Object.keys(claim.coverage).sort(),
      ['corpus', 'elements', 'jurisdiction_overlays', 'logic'], `${claim.id}: coverage`);
  }
});

test('one doctrine response composes the private-nuisance claim and its logic module', async () => {
  const { response, body } = await get('doctrine/private-nuisance');
  assert.equal(response.status, 200);
  assert.equal(body.claim.id, 'private-nuisance');
  assert.equal(body.claim.legal_kind, 'cause-of-action');
  assert.deepEqual(body.elements, []);
  assert.deepEqual(body.defences, []);
  assert.equal(body.logic.module_id, 'NUIS');
  assert.equal(body.logic.stage_ids, null);
  assert.equal(body.logic.module.id, 'NUIS');
  assert.ok(body.logic.module.stages.length > 0);
  const stageIds = body.logic.module.stages.map((stage) => stage.id);
  assert.equal(new Set(stageIds).size, stageIds.length);
  assert.ok(stageIds.every(Boolean));
  assert.ok(body.logic.element_stage_ids.length > 0);
  assert.ok(body.logic.element_stage_ids.every((id) =>
    body.logic.module.stages.find((stage) => stage.id === id)?.doctrinal_role === 'claim-elements'));
  assert.equal(body.composition.elements_source, 'logic-stages');
  assert.equal(body.coverage.logic, 'full');
});

test('partial model references expose only the mapped stages', async () => {
  const { response, body } = await get('doctrine/remoteness');
  assert.equal(response.status, 200);
  assert.deepEqual(body.logic.stage_ids, ['CT-3']);
  assert.deepEqual(body.logic.module.stages.map((stage) => stage.id), ['CT-3']);
  assert.equal(body.coverage.logic, 'partial');
});

test('misrepresentation doctrine returns full elements while the legacy endpoint remains compatible', async () => {
  const [doctrine, legacy] = await Promise.all([
    get('doctrine/misrepresentation'),
    get('elements'),
  ]);
  assert.equal(doctrine.response.status, 200);
  assert.equal(legacy.response.status, 200);
  assert.equal(doctrine.body.claim.id, 'misrepresentation');
  assert.equal(doctrine.body.logic, null);
  assert.deepEqual(doctrine.body.elements, legacy.body.elements);
  assert.deepEqual(doctrine.body.defences, legacy.body.defences);
  assert.ok(doctrine.body.elements[0].sub_tests[0].test);
  assert.ok(Array.isArray(doctrine.body.elements[0].sub_tests[0].auth));
});

test('unknown doctrine claims return a useful 404', async () => {
  const { response, body } = await get('doctrine/not-a-claim');
  assert.equal(response.status, 404);
  assert.equal(body.error, 'unknown doctrine claim');
  assert.ok(body.available.includes('private-nuisance'));
});

test('MCP never substitutes misrepresentation elements for another claim', async () => {
  const unsupported = await mcp('get_elements', { claim: 'private-nuisance' });
  assert.equal(unsupported.envelope.result.isError, true);
  assert.equal(unsupported.body.code, 'elements-not-available');
  assert.equal(unsupported.body.claim, 'private-nuisance');
  assert.equal(unsupported.body.model_ref.module_id, 'NUIS');
  assert.equal(Object.hasOwn(unsupported.body, 'elements'), false);

  const unified = await mcp('get_doctrine', { claim: 'private-nuisance' });
  assert.notEqual(unified.envelope.result.isError, true);
  assert.equal(unified.body.logic.module_id, 'NUIS');

  const legacyDefault = await mcp('get_elements', {});
  assert.notEqual(legacyDefault.envelope.result.isError, true);
  assert.equal(legacyDefault.body.claim, 'misrepresentation');
});

test('REST elements keeps its legacy default but rejects an unsupported explicit claim', async () => {
  const legacy = await get('elements');
  assert.equal(legacy.response.status, 200);
  assert.equal(legacy.body.claim, 'misrepresentation');

  const unsupported = await get('elements?claim=private-nuisance');
  assert.equal(unsupported.response.status, 404);
  assert.equal(unsupported.body.code, 'elements-not-available');
  assert.equal(unsupported.body.model_ref.module_id, 'NUIS');
  assert.equal(Object.hasOwn(unsupported.body, 'elements'), false);
});
