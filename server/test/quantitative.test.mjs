import { after, test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import handler from '../netlify/functions/api.mjs';
import { quantitativeCatalogue, evaluateQuantitative, quantitativeRequest, parseQuantitativeJSON } from '../netlify/functions/quantitative.mjs';

const savedFetch = globalThis.fetch;
let networkAttempts = 0;
globalThis.fetch = async () => { networkAttempts++; throw new Error('Quantitative tests must be offline'); };
after(() => { globalThis.fetch = savedFetch; assert.equal(networkAttempts, 0); });

const catalogue = quantitativeCatalogue();
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

test('all 11 models have source records, explicit premises and traceable non-legal results', () => {
  assert.equal(catalogue.models.length, 11);
  const sources = new Set(catalogue.sources.map(source => source.id));
  for (const model of catalogue.models) {
    assert.ok(model.required_legal_findings.length);
    assert.ok(model.assumptions.length);
    assert.ok(model.limitations.length);
    assert.ok(model.source_ids.length);
    model.source_ids.forEach(id => assert.ok(sources.has(id), `${model.id}: ${id}`));
    const calculated = evaluateQuantitative(request(model.id));
    assert.equal(calculated.legal_conclusion, null);
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

test('evidence and policy models retain their meanings at probability boundaries', () => {
  close(result('bayes').posterior, 2 / 3);
  assert.equal(result('bayes', { likelihood_ratio: 1 }).posterior, 0.2);
  assert.equal(result('bayes', { prior: 0 }).posterior, 0);
  assert.equal(result('bayes', { prior: 1 }).posterior, 1);
  assert.equal(quantitativeRequest(request('bayes', { prior: 1, likelihood_ratio: 0 })).status, 400);
  assert.equal(result('alexy').weight_ratio, 1);
  close(result('alexy', { I_i: 4, W_i: 4, R_i: 1, I_j: 1, W_j: 1, R_j: 0.25 }).weight_ratio, 64);
  assert.equal(result('deterrence').benchmark_sanction, 500000);
  assert.equal(quantitativeRequest(request('deterrence', { sanction_probability: 0 })).status, 400);
});

test('alternative comparisons preserve ties and settlement can have no overlap', () => {
  const alternative = request('coase').inputs.alternatives[0];
  assert.deepEqual(result('coase', { alternatives: [alternative, { ...alternative, name: '同成本方案' }] }).minimum_indices, [0, 1]);
  assert.deepEqual(result('settlement'), { lower: 500000, upper: 600000, overlap: true, interval_width: 100000 });
  const noOverlap = result('settlement', { plaintiff_probability: 0.9, defendant_probability: 0.1 });
  assert.equal(noOverlap.overlap, false);
  assert.ok(noOverlap.lower > noOverlap.upper);
});

test('damages models expose conditional arithmetic without silently clipping negative amounts', () => {
  assert.equal(result('cover_damages').net_amount, 45000);
  assert.equal(result('cover_damages', { replacement_price: 0, other_losses: 0, saved_costs: 0 }).net_amount, -100000);
  close(result('loss_of_chance').chance_value, 300000);
  assert.equal(quantitativeRequest(request('loss_of_chance', { probability_after: 0.9 })).status, 400);
  close(result('present_value').present_value, 268996.7393502677);
  close(result('present_value', { discount_rate: 0 }).present_value, 285000);
  assert.equal(result('counterfactual_damage').net_damage, 160000);
  assert.equal(quantitativeRequest(request('counterfactual_damage', { passed_on: 200001 })).status, 400);
});

test('HHI checks share scale and merger indices rather than inferring a legal concentration threshold', () => {
  assert.deepEqual(result('hhi'), { pre_hhi: 3000, delta_hhi: 400, post_hhi: 3400 });
  for (const input of [{ shares: [0.4, 0.3, 0.2, 0.1] }, { shares: [40, 30, 20, 9] },
    { merger_index_a: 3, merger_index_b: 3 }, { merger_index_b: 4 }, { merger_index_a: 0.5 }]) {
    assert.equal(quantitativeRequest(request('hhi', input)).status, 400);
  }
  assert.equal(evaluateQuantitative(request('hhi')).legal_conclusion, null);
});

test('missing, extra, mistyped, nonfinite and excessive inputs are rejected before calculation', () => {
  const missing = request('hand');
  delete missing.inputs.p;
  const invalid = [
    missing, request('hand', { p: null }), request('hand', { p: true }),
    request('hand', { p: '0.1' }), request('hand', { p: -0.01 }),
    request('hand', { p: Infinity }), request('hand', { p: NaN }),
    request('hand', { N: 1e308, L: 1e308 }),
    request('hand', { typo: 0 }), request('alexy', { I_i: 3 }),
    request('coase', { alternatives: [] }),
    request('present_value', { cashflows: Array(257).fill({ year: 0, amount: 0, probability: 1 }) }),
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
  const duplicate = '{"model_id":"bayes","model_version":"1","inputs":{"prior":0.2,"prior":0.8,"likelihood_ratio":8}}';
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

test('Python and JavaScript agree across examples and boundary cases', () => {
  const fixtures = catalogue.models.map(model => request(model.id));
  fixtures.push(request('hand', { prob_reduction: 0, annual_B: 0 }),
    request('hand', { N: 1e9, p: 0.1, L: 1e9, prob_reduction: 1e-18 }),
    request('cover_damages', { replacement_price: 2 ** 53, contract_price: 2 ** 53, other_losses: 0, saved_costs: 0 }),
    request('bayes', { prior: 0 }), request('bayes', { prior: 1 }),
    request('settlement', { plaintiff_probability: 0.9, defendant_probability: 0.1 }),
    request('present_value', { discount_rate: 0 }),
    request('hhi', { shares: [50, 50], merger_index_a: 0, merger_index_b: 1 }),
    request('hand', { p: 2 }), request('bayes', { prior: 1, likelihood_ratio: 0 }),
    request('deterrence', { sanction_probability: 0 }), request('alexy', { R_i: 0 }),
    request('hhi', { merger_index_a: 9 }), request('hhi', { merger_index_a: 0.5 }),
    request('loss_of_chance', { probability_after: 1 }));
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
  fixtures.forEach((fixture, index) => {
    const js = quantitativeRequest(fixture);
    assert.equal(pyResults[index].ok, js.status === 200, `${fixture.model_id} validation differs`);
    if (js.status === 200) compare(js.body, pyResults[index].value, fixture.model_id);
  });
});
