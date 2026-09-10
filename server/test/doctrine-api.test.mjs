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
  assert.deepEqual(body.jurisdiction_catalog.map(item => item.id), ['HK', 'EN', 'SG', 'AU']);
  for (const claim of claims) {
    assert.ok(Array.isArray(claim.elements), `${claim.id}: elements`);
    assert.ok(Array.isArray(claim.defences), `${claim.id}: defences`);
    assert.ok(claim.model_ref === null || typeof claim.model_ref.module_id === 'string', `${claim.id}: model_ref`);
    assert.deepEqual(Object.keys(claim.coverage).sort(),
      ['analysis_structure', 'corpus', 'elements', 'jurisdiction_overlays', 'logic'], `${claim.id}: coverage`);
    assert.notEqual(claim.coverage.analysis_structure, 'none', `${claim.id}: analysis structure must be explicit`);
    assert.notEqual(claim.coverage.elements, 'none', `${claim.id}: elements layer must distinguish stages, xref or non-applicability`);
    assert.notEqual(claim.coverage.logic, 'none', `${claim.id}: logic layer must distinguish stages or cross-references`);
    assert.ok(Array.isArray(claim.jurisdictions), `${claim.id}: jurisdictions`);
    assert.equal(new Set(claim.jurisdictions).size, claim.jurisdictions.length, `${claim.id}: unique jurisdictions`);
    assert.ok(claim.jurisdictions.length > 0, `${claim.id}: navigation scope must not silently disappear`);
    assert.ok(claim.jurisdictions.every(id => ['HK', 'EN', 'SG', 'AU'].includes(id)), `${claim.id}: known jurisdictions`);
    assert.equal(typeof claim.jurisdiction_scope_source, 'string', `${claim.id}: jurisdiction scope source`);
    assert.ok(['merits', 'procedure', 'jurisdiction'].includes(claim.litigation_track),
      `${claim.id}: classified matter track`);
    assert.ok(Array.isArray(claim.litigation_postures) && claim.litigation_postures.length > 0,
      `${claim.id}: classified spear/shield posture`);
  }
  const byId = new Map(claims.map(claim => [claim.id, claim]));
  assert.deepEqual(byId.get('private-nuisance').jurisdictions, ['HK', 'EN']);
  assert.deepEqual(byId.get('misrepresentation').jurisdictions, ['HK', 'EN', 'SG', 'AU']);
  assert.deepEqual(byId.get('deceit').jurisdictions, byId.get('misrepresentation').jurisdictions,
    'cross-referenced claims inherit the referenced data scope');
  assert.equal(byId.get('deceit').logic_status, 'xref');
  assert.equal(byId.get('rescission').logic_status, 'xref');
  assert.deepEqual(byId.get('private-nuisance').litigation_postures, ['spear', 'shield']);
  assert.deepEqual(byId.get('illegality').litigation_postures, ['shield']);
  assert.equal(byId.get('arbitrator-challenge').litigation_track, 'procedure');
  assert.equal(byId.get('hong-kong-jurisdiction').litigation_track, 'jurisdiction');
  assert.equal(body.jurisdiction_catalog.find(item => item.id === 'HK').claim_count,
    claims.filter(claim => claim.jurisdictions.includes('HK')).length);
});

test('all six formerly empty matters expose purpose-built legal-test modules', async () => {
  const { body } = await get('taxonomy');
  const claims = new Map(body.areas.flatMap(area => area.claims).map(claim => [claim.id, claim]));
  const expected = {
    penalty: 'PENALTY',
    'negligent-misstatement': 'NMS',
    privilege: 'LPP',
    discovery: 'DISC',
    easements: 'EASE',
    dmc: 'DMC',
  };
  for (const [claimId, moduleId] of Object.entries(expected)) {
    const claim = claims.get(claimId);
    assert.equal(claim.model_ref.module_id, moduleId, claimId);
    const expectedCoverage = claimId === 'easements' ? 'partial' : 'full';
    assert.equal(claim.coverage.analysis_structure, expectedCoverage, claimId);
    assert.equal(claim.coverage.logic, expectedCoverage, claimId);
    const { response, body: doctrine } = await get(`doctrine/${claimId}`);
    assert.equal(response.status, 200, claimId);
    assert.equal(doctrine.logic.module_id, moduleId, claimId);
    assert.ok(doctrine.logic.module.stages.length > 0, claimId);
    assert.ok(doctrine.logic.module.stages.every(stage => stage.doctrinal_role), claimId);
  }
  assert.deepEqual((await get('doctrine/negligent-misstatement')).body.logic.element_stage_ids,
    ['NMS-1', 'NMS-2', 'NMS-3']);
  assert.deepEqual((await get('doctrine/privilege')).body.logic.element_stage_ids, []);
  assert.equal(claims.get('privilege').coverage.elements, 'not-applicable');
});

test('jurisdiction-specific stages are filtered without importing Hong Kong prescription into England', async () => {
  const [hk, en] = await Promise.all([
    get('doctrine/easements?jurisdiction=HK'),
    get('doctrine/easements?jurisdiction=EN'),
  ]);
  assert.equal(hk.response.status, 200);
  assert.equal(en.response.status, 200);
  assert.deepEqual(hk.body.logic.module.stages.map(stage => stage.id), ['EA-1', 'EA-2', 'EA-3', 'EA-4']);
  assert.deepEqual(en.body.logic.module.stages.map(stage => stage.id), ['EA-1', 'EA-2', 'EA-4']);
  assert.deepEqual(hk.body.logic.module.stages.find(stage => stage.id === 'EA-3').jurisdictions, ['HK']);
  assert.equal(en.body.logic.element_stage_ids.includes('EA-3'), false);
});

test('cross-referenced matters return their selected element paths instead of empty placeholders', async () => {
  const [deceit, rescission] = await Promise.all([
    get('doctrine/deceit?jurisdiction=HK'),
    get('doctrine/rescission?jurisdiction=HK'),
  ]);
  assert.deepEqual(deceit.body.elements.map(element => element.id), ['E1', 'E2', 'E3', 'E4', 'E5']);
  assert.deepEqual(deceit.body.elements.find(element => element.id === 'E4').sub_tests.map(test => test.id), ['E4a']);
  assert.deepEqual(deceit.body.elements.find(element => element.id === 'E5').sub_tests.map(test => test.id), ['E5b']);
  assert.deepEqual(deceit.body.defences.map(defence => defence.id), ['D2']);
  assert.equal(deceit.body.composition.elements_source, 'xref');
  assert.deepEqual(rescission.body.elements.map(element => element.id), ['E5']);
  assert.deepEqual(rescission.body.elements[0].sub_tests.map(test => test.id), ['E5a']);
  assert.equal(rescission.body.composition.elements_source, 'xref');
});

test('non-cause matters distinguish analysis structure from an inapplicable element layer', async () => {
  const { body } = await get('doctrine/privilege?jurisdiction=HK');
  assert.equal(body.composition.analysis_structure_source, 'logic-stages');
  assert.equal(body.composition.elements_source, 'not-applicable');
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
