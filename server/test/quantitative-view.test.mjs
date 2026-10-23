import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const script = await readFile(new URL('../public/quantitative.js', import.meta.url), 'utf8');
const markup = await readFile(new URL('../public/quantitative.html', import.meta.url), 'utf8');
const catalogue = JSON.parse(await readFile(new URL('../../legal_quant/models.json', import.meta.url), 'utf8'));

class Element {
  constructor(tag, registry) {
    this.tagName = tag;
    this.registry = registry;
    this.children = [];
    this.listeners = new Map();
    this.dataset = {};
    this.attributes = {};
    this._text = '';
    this.value = '';
    this.hidden = false;
  }
  set id(value) { this._id = value; this.registry.set(value, this); }
  get id() { return this._id; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
  set innerHTML(_) { throw new Error('HTML injection sink must not be used'); }
  append(...children) {
    this.children.push(...children);
    if (this.tagName === 'select' && !this.value && this.children.length) this.value = this.children[0].value;
  }
  replaceChildren(...children) {
    this.children = [];
    this._text = '';
    if (this.tagName === 'select') this.value = '';
    this.append(...children);
  }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(name, callback) {
    const list = this.listeners.get(name) || [];
    list.push(callback);
    this.listeners.set(name, list);
  }
  async emit(name) {
    for (const callback of this.listeners.get(name) || []) await callback({ preventDefault() {} });
  }
  click() { return this.emit('click'); }
  scrollIntoView() {}
  remove() {}
}

async function harness(modelCatalogue = catalogue) {
  const nodes = new Map();
  for (const match of markup.matchAll(/<([a-z]+)[^>]*\sid="([^"]+)"/g)) {
    const node = new Element(match[1], nodes);
    node.id = match[2];
  }
  nodes.get('jurisdiction').value = 'HK';
  nodes.get('as-of').value = '';
  const requests = [];
  const downloads = [];
  class DownloadURL extends URL {
    static createObjectURL(blob) { downloads.push(blob); return `blob:test-${downloads.length}`; }
    static revokeObjectURL() {}
  }
  const context = vm.createContext({
    document: {
      getElementById: id => nodes.get(id),
      createElement: tag => new Element(tag, nodes),
      body: new Element('body', nodes),
    },
    fetch: (url, options) => {
      if (url === '/api/quant/models') return Promise.resolve({
        ok: true, json: async () => ({ version: '1', models: modelCatalogue.models, sources: [] }),
      });
      return new Promise((resolve, reject) => requests.push({
        payload: JSON.parse(options.body), signal: options.signal, resolve, reject,
      }));
    },
    AbortController, URL: DownloadURL, Blob, Intl, setTimeout: () => {},
  });
  vm.runInContext(script, context);
  await new Promise(resolve => setImmediate(resolve));
  return {
    nodes, requests, downloads, at: id => nodes.get(id),
    emit: (id, event) => nodes.get(id).emit(event),
    async choose(id) {
      const model = modelCatalogue.models.find(model => model.id === id);
      nodes.get('category').value = model.category;
      await nodes.get('category').emit('change');
      nodes.get('model').value = id;
      await nodes.get('model').emit('change');
    },
    async import(data) {
      nodes.get('case-file').files = [{ size: 10, text: async () => JSON.stringify(data) }];
      await nodes.get('case-file').emit('change');
    },
  };
}

function resultFor(request, label = '经过核对的计算值') {
  return {
    model_id: request.payload.model_id, model_version: '1',
    results: { sample: 125 }, steps: [{ id: 'sample', label, formula: '5 × 25', unit: '货币', value: 125 }],
    assumptions: ['示例假设'], limitations: ['不能自动作出法律结论'],
    required_legal_findings: ['适用法须独立核验'], applicability_status: 'unreviewed', legal_conclusion: null,
  };
}
function resolveResult(request, label) {
  request.resolve({ ok: true, json: async () => resultFor(request, label) });
}
function inputRecord(modelId = 'hand') {
  const model = catalogue.models.find(model => model.id === modelId);
  return {
    model_id: modelId, model_version: '1', inputs: structuredClone(model.example_inputs),
    context: {
      jurisdiction: 'HK', as_of: '2026-10-20', input_basis: 'hypothetical', applicability: 'unreviewed',
      sources: Object.fromEntries(model.fields.map(field => [field.id, '教学假设（synthetic）'])),
    },
  };
}

test('all model examples produce valid typed requests from the generated form', async () => {
  const h = await harness();
  assert.equal(h.at('workspace').hidden, false);
  assert.equal(catalogue.models.length, 4);
  assert.equal(h.at('category').value, 'substantive_probability');
  assert.equal(h.at('model').children.length, 4);
  assert.match(h.at('formula-authority').textContent, /判决/);
  for (const model of catalogue.models) {
    await h.choose(model.id);
    await h.emit('load-example', 'click');
    const pending = h.emit('analysis-form', 'submit');
    const request = h.requests.at(-1);
    assert.equal(request.payload.model_id, model.id);
    assert.deepEqual(request.payload.inputs, model.example_inputs);
    assert.equal(request.payload.context.input_basis, 'hypothetical');
    resolveResult(request);
    await pending;
    assert.equal(h.at('results').hidden, false);
    assert.match(h.at('result-applicability').textContent, /待独立审查/);
  }
});

test('navigation invalidates pending results even if the server ignores cancellation', async () => {
  const h = await harness();
  await h.emit('load-example', 'click');
  const pending = h.emit('analysis-form', 'submit');
  const request = h.requests[0];
  await h.choose('reasonable_mitigation');
  assert.equal(request.signal.aborted, true);
  resolveResult(request, '已过期的结果');
  await pending;
  assert.equal(h.at('results').hidden, true);
  assert.doesNotMatch(h.at('calculation-steps').textContent, /已过期/);
  assert.equal(h.at('field-0').value, '');
});

test('editing clears completed results and stale errors cannot replace the input status', async () => {
  const h = await harness();
  await h.emit('load-example', 'click');
  const first = h.emit('analysis-form', 'submit');
  resolveResult(h.requests[0]);
  await first;
  assert.equal(h.at('results').hidden, false);
  const pending = h.emit('analysis-form', 'submit');
  await h.emit('analysis-form', 'input');
  h.requests[1].reject(new Error('旧请求错误'));
  await pending;
  assert.equal(h.at('results').hidden, true);
  assert.match(h.at('form-status').textContent, /输入已改变/);
});

test('reset clears all inputs and sources and prevents a pending result from returning', async () => {
  const h = await harness();
  await h.emit('load-example', 'click');
  const pending = h.emit('analysis-form', 'submit');
  await h.emit('reset', 'click');
  resolveResult(h.requests[0]);
  await pending;
  assert.equal(h.at('results').hidden, true);
  assert.equal(h.at('field-0').value, '');
  assert.equal(h.at('field-0-source').value, '');
});

test('case data require all provenance but source wording is not treated as proof of authenticity', async () => {
  const h = await harness();
  await h.emit('load-example', 'click');
  h.at('input-basis').value = 'case_data';
  await h.emit('analysis-form', 'change');
  h.at('field-0-source').value = '';
  await h.emit('analysis-form', 'submit');
  assert.equal(h.requests.length, 0);
  assert.match(h.at('form-status').textContent, /每项输入的来源/);
  h.at('field-0-source').value = 'Synthetic Materials Ltd 报告第 3 页；与教学假设对照';
  const pending = h.emit('analysis-form', 'submit');
  assert.equal(h.requests.length, 1);
  resolveResult(h.requests[0]);
  await pending;
});

test('import validates versions, numeric types and dates before replacing the form', async () => {
  const h = await harness();
  const invalid = [
    { ...inputRecord(), model_version: 1 },
    { ...inputRecord(), model_id: 'missing' },
    { ...inputRecord(), inputs: { ...inputRecord().inputs, N: '100000' } },
    { ...inputRecord(), context: { ...inputRecord().context, as_of: '2026-02-30' } },
    { ...inputRecord(), context: { ...inputRecord().context, as_of: '0000-01-01' } },
    { ...inputRecord('loss_of_chance'), inputs: { ...inputRecord('loss_of_chance').inputs, probability_before: -1 } },
    { ...inputRecord('alarp_probability'), inputs: { ...inputRecord('alarp_probability').inputs, probability_after: true } },
  ];
  for (const data of invalid) {
    await h.import(data);
    assert.equal(h.at('file-status').dataset.error, 'true');
    assert.equal(h.at('model').value, 'hand');
  }
});

test('removed model imports cannot restore a retired calculator', async () => {
  const h = await harness();
  for (const id of ['alexy', 'bayes', 'deterrence', 'coase', 'settlement', 'cover_damages',
    'present_value', 'counterfactual_damage', 'hhi', 'alarp', 'interim_injunction',
    'procedural_safeguards', 'necessity', 'penalty_proportionality']) {
    await h.import({ model_id: id, model_version: '1', inputs: {} });
    assert.equal(h.at('file-status').dataset.error, 'true', id);
    assert.equal(h.at('model').value, 'hand');
    assert.equal(h.requests.length, 0);
  }
});

test('generic array imports validate every entry using a local synthetic schema', async () => {
  const modelCatalogue = structuredClone(catalogue);
  const model = modelCatalogue.models.find(model => model.id === 'hand');
  model.fields = [
    { id: 'values', label: 'Synthetic numeric array', type: 'number_array', min: 0, max: 1 },
    { id: 'rows', label: 'Synthetic object array', type: 'object_array', items: [
      { id: 'name', label: 'Name', type: 'string' },
      { id: 'count', label: 'Count', type: 'integer', min: 0 },
    ] },
  ];
  const valid = { model_id: 'hand', model_version: '1', inputs: { values: [0, 1], rows: [{ name: 'Synthetic', count: 1 }] } };
  const h = await harness(modelCatalogue);
  for (const inputs of [
    { ...valid.inputs, values: [-1, 1] }, { ...valid.inputs, values: [false] },
    { ...valid.inputs, values: [] }, { ...valid.inputs, values: Array(257).fill(0) },
    { ...valid.inputs, rows: [{ name: 'Synthetic' }] },
    { ...valid.inputs, rows: [{ name: 'Synthetic', count: 1, extra: 0 }] },
    { ...valid.inputs, rows: [{ name: 'Synthetic', count: 0.5 }] },
    { ...valid.inputs, rows: [{ name: '', count: 1 }] },
  ]) {
    await h.import({ ...valid, inputs });
    assert.equal(h.at('file-status').dataset.error, 'true');
    assert.equal(h.at('field-0').value, '');
  }
  await h.import(valid);
  assert.match(h.at('file-status').textContent, /已导入/);
  const pending = h.emit('analysis-form', 'submit');
  assert.deepEqual(h.requests[0].payload.inputs, valid.inputs);
  resolveResult(h.requests[0]);
  await pending;
});

test('CLI null-date input and requests without context import, calculate and export with engine defaults', async () => {
  const defaults = { jurisdiction: 'HK', as_of: null, input_basis: 'hypothetical', sources: {}, applicability: 'unreviewed' };
  for (const context of [defaults, undefined, {}]) {
    const h = await harness();
    const data = inputRecord('reasonable_mitigation');
    if (context === undefined) delete data.context;
    else data.context = context;
    await h.import(data);
    assert.match(h.at('file-status').textContent, /已导入/);
    assert.equal(h.at('as-of').value, '');
    const pending = h.emit('analysis-form', 'submit');
    assert.deepEqual(h.requests[0].payload.context, defaults);
    resolveResult(h.requests[0]);
    await pending;
    assert.match(h.at('result-context').textContent, /未记录日期/);
    await h.emit('download-case', 'click');
    const exported = JSON.parse(await h.downloads[0].text());
    assert.deepEqual(exported, { ...data, context: defaults });
  }
  assert.doesNotMatch(markup, /id="as-of"[^>]*(?:required|value=)/);
});

test('unknown request, context, source and input keys are rejected before changing the form', async () => {
  const h = await harness();
  const invalid = [
    { ...inputRecord(), unexpected: 1 },
    { ...inputRecord(), context: { ...inputRecord().context, unexpected: 1 } },
    { ...inputRecord(), context: { ...inputRecord().context, sources: { unexpected: '报告' } } },
    { ...inputRecord(), inputs: { ...inputRecord().inputs, unexpected: 1 } },
  ];
  for (const data of invalid) {
    await h.import(data);
    assert.equal(h.at('file-status').dataset.error, 'true');
    assert.match(h.at('file-status').textContent, /未识别|未定义/);
    assert.equal(h.at('field-0').value, '');
  }
});

test('provenance length limits match engine limits and explicitly empty source entries are rejected', async () => {
  const h = await harness();
  const data = inputRecord('hand');
  data.context.jurisdiction = 'H'.repeat(100);
  data.context.sources.N = '文'.repeat(4000);
  await h.import(data);
  assert.match(h.at('file-status').textContent, /已导入/);
  for (const invalid of [
    { ...data, context: { ...data.context, jurisdiction: 'H'.repeat(101) } },
    { ...data, context: { ...data.context, sources: { N: '文'.repeat(4001) } } },
    { ...data, context: { ...data.context, sources: { N: '' } } },
  ]) {
    await h.import(invalid);
    assert.equal(h.at('file-status').dataset.error, 'true');
  }
});

test('integer safety and exclusive numeric bounds are validated on import', async () => {
  const modelCatalogue = structuredClone(catalogue);
  const field = modelCatalogue.models.find(model => model.id === 'hand').fields.find(field => field.id === 'N');
  field.type = 'integer';
  field.exclusiveMinimum = 0;
  field.exclusiveMaximum = 1000000;
  const h = await harness(modelCatalogue);
  for (const value of [0, 1000000]) {
    const data = inputRecord();
    data.inputs.N = value;
    await h.import(data);
    assert.equal(h.at('file-status').dataset.error, 'true');
    assert.match(h.at('file-status').textContent, /须大于|须小于/);
  }
  const unsafe = inputRecord();
  unsafe.inputs.N = Number.MAX_SAFE_INTEGER + 1;
  await h.import(unsafe);
  assert.match(h.at('file-status').textContent, /安全整数/);
});

test('import round trip preserves explicit context and renders arbitrary strings only as text', async () => {
  const h = await harness();
  const data = inputRecord('reasonable_mitigation');
  data.context.jurisdiction = '<img src=x onerror=alert(1)>';
  data.context.as_of = '2025-01-17';
  data.context.applicability = 'externally_assessed';
  await h.import(data);
  assert.equal(h.at('model').value, 'reasonable_mitigation');
  assert.equal(h.at('as-of').value, '2025-01-17');
  const pending = h.emit('analysis-form', 'submit');
  assert.deepEqual(h.requests[0].payload, data);
  resolveResult(h.requests[0], '<svg onload=alert(2)>');
  await pending;
  assert.match(h.at('result-context').textContent, /<img src=x/);
  assert.match(h.at('calculation-steps').textContent, /<svg onload/);
});

test('a response for a different model cannot display as the current result', async () => {
  const h = await harness();
  await h.emit('load-example', 'click');
  const pending = h.emit('analysis-form', 'submit');
  const result = resultFor(h.requests[0]);
  result.model_id = 'reasonable_mitigation';
  h.requests[0].resolve({ ok: true, json: async () => result });
  await pending;
  assert.equal(h.at('results').hidden, true);
  assert.match(h.at('form-status').textContent, /不匹配/);
});
