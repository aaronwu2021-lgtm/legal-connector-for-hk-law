import { after, test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import handler from '../netlify/functions/api.mjs';
import { quantitativeCatalogue, evaluateQuantitative, quantitativeRequest, parseQuantitativeJSON, evaluateExpression, quantitativeTools } from '../netlify/functions/quantitative.mjs';

const savedFetch = globalThis.fetch;
let networkAttempts = 0;
globalThis.fetch = async () => { networkAttempts++; throw new Error('Quantitative tests must be offline'); };
after(() => { globalThis.fetch = savedFetch; assert.equal(networkAttempts, 0); });

const catalogue = quantitativeCatalogue();
const removedModels = ['alexy', 'bayes', 'deterrence', 'coase', 'settlement', 'cover_damages',
  'present_value', 'counterfactual_damage', 'hhi', 'alarp', 'interim_injunction',
  'procedural_safeguards', 'necessity', 'penalty_proportionality'];
function request(id, overrides = {}) {
  const model = catalogue.models.find(item => item.id === id);
  return { model_id: id, model_version: model.version, inputs: { ...structuredClone(model.example_inputs), ...overrides } };
}
const result = (id, overrides) => evaluateQuantitative(request(id, overrides)).results;
const close = (actual, expected) => assert.ok(Math.abs(actual - expected) <= 1e-9 * Math.max(1, Math.abs(expected)), `${actual} != ${expected}`);

async function rest(payload, options = {}) {
  const response = await handler(new Request('http://offline.invalid/api/quant/evaluate', {
    method: options.method || 'POST',
    ...(options.method === 'GET' ? {} : { body: options.raw ?? JSON.stringify(payload) }),
  }));
  return { status: response.status, cache: response.headers.get('cache-control'), body: await response.json() };
}
async function mcp(name, args) {
  const response = await handler(new Request('http://offline.invalid/api/mcp', {
    method: 'POST',
    body: JSON.stringify({ jsonrpc: '2.0', id: 17, method: 'tools/call', params: { name, arguments: args } }),
  }));
  const envelope = await response.json();
  return { body: JSON.parse(envelope.result.content[0].text), failed: envelope.result.isError, cache: response.headers.get('cache-control') };
}

test('all models have source records, explicit premises and traceable non-legal results', () => {
  assert.deepEqual(catalogue.models.map(model => model.id).sort(),
    ['hand', 'alarp_probability', 'reasonable_mitigation', 'loss_of_chance'].sort());
  const sources = new Set(catalogue.sources.map(source => source.id));
  for (const model of catalogue.models) {
    assert.ok(model.required_legal_findings.length);
    assert.ok(model.assumptions.length);
    assert.ok(model.limitations.length);
    assert.ok(model.source_ids.length);
    model.source_ids.forEach(id => assert.ok(sources.has(id), `${model.id}: ${id}`));
    const calculated = evaluateQuantitative(request(model.id));
    assert.equal(calculated.legal_conclusion, null);
    assert.equal(calculated.analysis_layer, model.analysis_layer);
    assert.equal(calculated.formula_authority, model.formula_authority);
    assert.equal(calculated.applicability_status, 'unreviewed');
    assert.equal(calculated.context.as_of, null);
    assert.deepEqual(calculated.inputs, model.example_inputs);
    assert.equal(calculated.steps.length, Object.keys(calculated.results).length);
    assert.doesNotThrow(() => JSON.stringify(calculated));
  }
});

test('Hand accounts for actual risk reduction and treats break-even as neither a finding nor a net gain', () => {
  assert.deepEqual(result('hand'), { expected_before: 832000, expected_after: 332800,
    avoided_expected_loss: 499200, net_benefit: 379200, economically_favourable: true });
  assert.equal(result('hand', { prob_reduction: 0 }).net_benefit, -120000);
  assert.equal(result('hand', { annual_B: 499200 }).economically_favourable, false);
  assert.equal(result('hand', { prob_reduction: 1 }).expected_after, 0);
  close(result('hand', { N: 1e9, p: 0.1, L: 1e9, prob_reduction: 1e-18 }).avoided_expected_loss, 0.1);
});

test('ALARP uses avoided expected loss and leaves zero-denominator ratios undefined', () => {
  const inputs = { probability_before: 0.08, probability_after: 0.02, loss_if_harm: 1000000, precaution_cost: 180000 };
  close(result('alarp_probability', inputs).avoided_expected_loss, 60000);
  close(result('alarp_probability', inputs).cost_risk_ratio, 3);
  for (const cost of [0, 100]) {
    assert.deepEqual(result('alarp_probability', { ...inputs, probability_after: 0.08, precaution_cost: cost }),
      { avoided_expected_loss: 0, cost_risk_ratio: null });
    assert.deepEqual(result('alarp_probability', { ...inputs, loss_if_harm: 0, precaution_cost: cost }),
      { avoided_expected_loss: 0, cost_risk_ratio: null });
  }
  assert.equal(evaluateQuantitative(request('alarp_probability', { ...inputs, precaution_cost: 6e9 })).legal_conclusion, null);
});

test('mitigation and loss of chance preserve zero-probability and break-even meanings', () => {
  assert.equal(result('reasonable_mitigation').expected_avoided_loss, 60000);
  assert.equal(result('reasonable_mitigation').net_expected_benefit, 40000);
  assert.equal(result('reasonable_mitigation', { mitigation_cost: 60000 }).positive_quantified_balance, false);
  assert.equal(result('reasonable_mitigation', { success_probability: 0 }).net_expected_benefit, -20000);
  close(result('loss_of_chance').chance_value, 300000);
  assert.equal(result('loss_of_chance', { probability_before: 0, probability_after: 0 }).chance_value, 0);
  assert.equal(quantitativeRequest(request('loss_of_chance', { probability_after: 0.9 })).status, 400);
});

test('generic expression arrays preserve order and ties without unrelated published models', () => {
  assert.deepEqual(evaluateExpression({ op: 'argmin', args: [[2, 1, 1, 3]] }, {}), [1, 2]);
  assert.deepEqual(evaluateExpression({ op: 'map', items: [3, 1, 2],
    value: { op: 'mul', args: [{ var: 'item' }, 2] } }, {}), [6, 2, 4]);
  assert.equal(evaluateExpression({ op: 'sum', args: [[1e16, 1, 1]] }, {}), 1e16);
  assert.equal(evaluateExpression({ op: 'sum', args: [[]] }, {}), 0);
  assert.equal(evaluateExpression({ op: 'pow', args: [2, 3] }, {}), 8);
  assert.equal(evaluateExpression({ op: 'if', condition: true, then: 9,
    else: { op: 'div', args: [1, 0] } }, {}), 9);
  for (const expression of [{ op: 'eval', args: ['process.exit()'] }, { var: 'input.constructor' },
    { op: 'at', args: [[1, 2], -1] }, { op: 'mul', args: [true, 5] },
    { op: 'div', args: [1, 0] }, { op: 'pow', args: [1e308, 2] },
    { op: 'map', items: Array(257).fill(1), value: { var: 'item' } }]) {
    assert.throws(() => evaluateExpression(expression, { input: {} }));
  }
});

test('retired models are unavailable through catalogue, REST, MCP schema and MCP execution', async () => {
  const active = new Set(catalogue.models.map(model => model.id));
  const schemaIds = quantitativeTools.find(tool => tool.name === 'evaluate_quantitative_model').inputSchema.properties.model_id.enum;
  assert.deepEqual([...schemaIds].sort(), [...active].sort());
  for (const id of removedModels) {
    assert.equal(active.has(id), false, id);
    assert.equal(schemaIds.includes(id), false, id);
    const payload = { model_id: id, model_version: '1', inputs: {} };
    assert.equal(quantitativeRequest(payload).status, 404, id);
    assert.equal((await rest(payload)).status, 404, id);
    assert.equal((await mcp('evaluate_quantitative_model', payload)).failed, true, id);
  }
});

test('missing, extra, mistyped, nonfinite and excessive inputs are rejected before calculation', () => {
  const missing = request('hand');
  delete missing.inputs.p;
  const invalid = [
    missing, request('hand', { p: null }), request('hand', { p: true }),
    request('hand', { p: '0.1' }), request('hand', { p: -0.01 }),
    request('hand', { p: Infinity }), request('hand', { p: NaN }),
    request('hand', { N: 1e308, L: 1e308 }),
    request('hand', { typo: 0 }), request('alarp_probability', { loss_if_harm: -1 }),
    request('alarp_probability', { probability_before: 0.1, probability_after: 0.2 }),
    request('reasonable_mitigation', { success_probability: 1.01 }),
    { ...request('hand'), expression: 0 },
    { ...request('hand'), context: null },
    { ...request('hand'), context: { as_of: '2025-02-29' } },
  ];
  for (const input of invalid) assert.equal(quantitativeRequest(input).status, 400);
  assert.equal(quantitativeRequest({ ...request('hand'), model_version: '2' }).status, 409);
  assert.equal(quantitativeRequest({ ...request('hand'), model_id: 'unknown' }).status, 404);
});

test('case input provenance is required and an external assessment is not a legal conclusion', () => {
  const input = request('hand');
  input.context = { input_basis: 'case_data', applicability: 'externally_assessed', sources: {} };
  assert.equal(quantitativeRequest(input).status, 400);
  input.context.sources = Object.fromEntries(Object.keys(input.inputs).map(key => [key, `synthetic test source: ${key}`]));
  const output = evaluateQuantitative(input);
  assert.equal(output.applicability_status, 'externally_assessed');
  assert.equal(output.legal_conclusion, null);
  assert.deepEqual(output.context.sources, input.context.sources);
  input.context.sources.extra = 'unknown parameter';
  assert.equal(quantitativeRequest(input).status, 400);
});

test('raw JSON rejects ambiguous duplicate keys at every nesting level, including escaped spellings', async () => {
  for (const raw of [
    '{"prior":0.2,"prior":0.8}',
    '{"inputs":{"prior":0.2,"pr\\u0069or":0.8}}',
    '{"items":[{"name":"a","name":"b"}]}',
  ]) assert.throws(() => parseQuantitativeJSON(raw), /重复字段/);
  const distinct = '{"a":{"x":1},"b":{"x":2},"text":"{},[]:\\\"x\\\"","list":[1,2,null]}';
  assert.deepEqual(parseQuantitativeJSON(distinct), JSON.parse(distinct));
  const duplicate = '{"model_id":"hand","model_version":"1","inputs":{"p":0.2,"p":0.8}}';
  assert.equal((await rest(null, { raw: duplicate })).status, 400);
  const rpc = await handler(new Request('http://offline.invalid/api/mcp', {
    method: 'POST', body: `{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"evaluate_quantitative_model","arguments":${duplicate}}}`,
  }));
  assert.equal(rpc.status, 400);
  assert.equal(rpc.headers.get('cache-control'), 'no-store');
  assert.equal((await rpc.json()).error.code, -32700);
});

test('REST and MCP expose identical model calculations and no-store responses', async () => {
  const catalogResponse = await handler(new Request('http://offline.invalid/api/quant/models'));
  assert.deepEqual(await catalogResponse.json(), catalogue);
  assert.deepEqual((await mcp('list_quantitative_models', {})).body, catalogue);
  assert.equal((await mcp('list_quantitative_models', { as_of: '2025' })).failed, true);
  for (const model of catalogue.models) {
    const input = request(model.id);
    const direct = await rest(input);
    const rpc = await mcp('evaluate_quantitative_model', input);
    assert.equal(direct.status, 200);
    assert.equal(rpc.failed, false);
    assert.equal(direct.cache, 'no-store');
    assert.equal(rpc.cache, 'no-store');
    assert.deepEqual(direct.body, rpc.body);
  }
  const invalid = request('hand', { p: 2 });
  assert.equal((await rest(invalid)).status, 400);
  assert.equal((await mcp('evaluate_quantitative_model', invalid)).failed, true);
  assert.equal((await rest({}, { raw: '{' })).status, 400);
  assert.equal((await rest({}, { raw: ' '.repeat(131073) })).status, 413);
  assert.equal((await rest({}, { method: 'GET' })).status, 405);
  const historical = await handler(new Request('http://offline.invalid/api/quant/models?as_of=2000'));
  assert.notEqual(historical.status, 200, 'unversioned model catalogue must not masquerade as historical law');
});

test('Python, JavaScript and REST agree across examples and boundary cases', async () => {
  const fixtures = catalogue.models.map(model => request(model.id));
  fixtures.push(request('hand', { prob_reduction: 0, annual_B: 0 }),
    request('hand', { N: 1e9, p: 0.1, L: 1e9, prob_reduction: 1e-18 }),
    request('hand', { p: 0 }), request('hand', { p: 1 }), request('hand', { p: 2 }),
    request('alarp_probability', { probability_before: 0, probability_after: 0 }),
    request('alarp_probability', { probability_before: 0.5, probability_after: 0.5, precaution_cost: 0 }),
    request('alarp_probability', { loss_if_harm: 0 }),
    request('alarp_probability', { probability_before: 1, probability_after: 0, precaution_cost: 0 }),
    request('alarp_probability', { probability_before: 0.1, probability_after: 0.2 }),
    request('alarp_probability', { precaution_cost: -1 }),
    request('reasonable_mitigation', { success_probability: 0 }),
    request('reasonable_mitigation', { success_probability: 1 }),
    request('reasonable_mitigation', { mitigation_cost: 60000 }),
    request('reasonable_mitigation', { success_probability: true }),
    request('loss_of_chance', { probability_before: 0, probability_after: 0 }),
    request('loss_of_chance', { probability_before: 1, probability_after: 0 }),
    request('loss_of_chance', { probability_before: 0.5, probability_after: 0.5 }),
    request('loss_of_chance', { probability_after: 1 }),
    ...removedModels.map(id => ({ model_id: id, model_version: '1', inputs: {} })));
  const pythonCode = `
import json, sys
from legal_quant import evaluate
out=[]
for item in json.load(sys.stdin):
    try:
        out.append({"ok": True, "value": evaluate(item["model_id"], item["inputs"], item.get("context"), item["model_version"])})
    except ValueError:
        out.append({"ok": False})
sys.stdout.write(json.dumps(out, ensure_ascii=True, allow_nan=False))
`;
  const processResult = spawnSync(process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3'), ['-B', '-c', pythonCode], {
    input: JSON.stringify(fixtures), encoding: 'utf8', timeout: 30000,
    cwd: fileURLToPath(new URL('../../', import.meta.url)),
    env: { ...process.env, PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1' },
  });
  assert.ifError(processResult.error);
  assert.equal(processResult.status, 0, processResult.stderr);
  const pyResults = JSON.parse(processResult.stdout);
  function compare(a, b, path) {
    if (typeof a === 'number' && typeof b === 'number') return close(a, b);
    if (a && b && typeof a === 'object' && typeof b === 'object') {
      assert.deepEqual(Object.keys(a).sort(), Object.keys(b).sort(), path);
      for (const key of Object.keys(a)) compare(a[key], b[key], `${path}.${key}`);
    } else assert.deepEqual(a, b, path);
  }
  for (const [index, fixture] of fixtures.entries()) {
    const js = quantitativeRequest(fixture);
    assert.equal(pyResults[index].ok, js.status === 200, `${fixture.model_id} validation differs`);
    const http = await rest(fixture);
    assert.equal(http.status, js.status, `${fixture.model_id} REST validation differs`);
    if (js.status === 200) {
      compare(js.body, pyResults[index].value, fixture.model_id);
      compare(http.body, pyResults[index].value, `${fixture.model_id}.REST`);
    }
  }
});
