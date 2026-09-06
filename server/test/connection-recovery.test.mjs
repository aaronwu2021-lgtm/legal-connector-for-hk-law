import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

// Every request in this suite uses a local adapter, including stalled bodies.
const originalFetch = globalThis.fetch;
let realNetworkAttempts = 0;
globalThis.fetch = () => {
  realNetworkAttempts += 1;
  throw new Error('Real network access is forbidden in connection recovery tests');
};
const { createApiClient, createBootstrap } = await import('../public/connection.js');
after(() => {
  globalThis.fetch = originalFetch;
  assert.equal(realNetworkAttempts, 0);
});

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function response(data, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => data };
}

function client(fetcher, options = {}) {
  const statuses = [];
  const request = createApiClient({
    fetcher, timeoutMs: 1000, ...options,
    onStatus: value => statuses.push({ ...value }),
  });
  return { request, statuses, states: () => statuses.map(value => value.state) };
}

const errorCode = code => error => {
  assert.ok(error instanceof Error);
  assert.equal(error.code, code);
  assert.match(error.message, /[\u3400-\u9fff]/, 'the visible failure has a Chinese explanation');
  return true;
};

test('a successful request returns the decoded API result and establishes online status', async () => {
  const calls = [];
  const h = client(async (...args) => { calls.push(args); return response({ modules: ['HKJUR'] }); });
  assert.deepEqual(await h.request('/modules'), { ok: true, status: 200, data: { modules: ['HKJUR'] } });
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], '/api/modules');
  assert.equal(h.states()[0], 'connecting');
  assert.equal(h.states().at(-1), 'online');
  assert.ok(calls[0][1].signal instanceof AbortSignal);
});

test('later online requests do not repeatedly show an initial connecting status', async () => {
  const h = client(async () => response({ ok: true }));
  await h.request('/one');
  await h.request('/two');
  assert.equal(h.states().filter(state => state === 'connecting').length, 1);
  assert.equal(h.states().at(-1), 'online');
});

test('HTTP errors retain their JSON details and are distinct from a lost connection', async () => {
  for (const status of [400, 404, 429, 503]) {
    const data = { error: 'Synthetic HTTP failure', status };
    const h = client(async () => response(data, status));
    assert.deepEqual(await h.request('/failure'), { ok: false, status, data });
    assert.equal(h.states().at(-1), 'error');
    assert.ok(!h.states().includes('offline'));
  }
});

test('an established connection can fail and recover after one explicit retry', async () => {
  let calls = 0;
  const h = client(async () => {
    calls += 1;
    if (calls === 2) throw new TypeError('Synthetic adapter failure');
    return response({ call: calls });
  });
  await h.request('/first');
  await assert.rejects(h.request('/lost'), errorCode('network'));
  assert.equal(h.states().at(-1), 'offline');
  assert.equal(calls, 2, 'the failed request is not retried automatically');
  assert.deepEqual((await h.request('/retry')).data, { call: 3 });
  assert.equal(h.states().at(-1), 'online');
  assert.equal(h.states().filter(state => state === 'connecting').length, 2);
});

test('a POST request preserves its options and is sent once on network failure', async () => {
  const calls = [];
  const body = JSON.stringify({ module: 'HKJUR', facts: { known: true } });
  const headers = { 'content-type': 'application/json', 'x-fixture': 'offline' };
  const h = client(async (...args) => {
    calls.push(args);
    throw new TypeError('Synthetic POST failure');
  }, { base: '/custom/api' });
  await assert.rejects(h.request('/score', { method: 'POST', body, headers }), errorCode('network'));
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], '/custom/api/score');
  assert.equal(calls[0][1].method, 'POST');
  assert.equal(calls[0][1].body, body);
  assert.deepEqual(calls[0][1].headers, headers);
});

test('the deadline bounds a fetch adapter that never settles', { timeout: 1000 }, async () => {
  let calls = 0, signal;
  const h = client((_path, options) => {
    calls += 1;
    signal = options.signal;
    return new Promise(() => {});
  }, { timeoutMs: 15 });
  await assert.rejects(h.request('/stalled', { method: 'POST', body: '{}' }), errorCode('timeout'));
  assert.equal(calls, 1);
  assert.equal(signal.aborted, true);
  assert.equal(h.states().at(-1), 'offline');
});

test('the same deadline includes JSON body reading after successful response headers', { timeout: 1000 }, async () => {
  let bodyReads = 0, signal;
  const h = client(async (_path, options) => {
    signal = options.signal;
    return { ok: true, status: 200, json: () => { bodyReads += 1; return new Promise(() => {}); } };
  }, { timeoutMs: 15 });
  await assert.rejects(h.request('/stalled-body'), errorCode('timeout'));
  assert.equal(bodyReads, 1);
  assert.equal(signal.aborted, true);
  assert.equal(h.states().at(-1), 'offline');
});

test('invalid JSON becomes a visible response error instead of an online success', async () => {
  const h = client(async () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError('Synthetic JSON error'); } }));
  await assert.rejects(h.request('/not-json'), errorCode('invalid-response'));
  assert.equal(h.states().at(-1), 'error');
  assert.ok(!h.states().includes('online'));
});

for (const phase of ['fetch', 'body']) {
  test(`caller cancellation during ${phase} is an AbortError and preserves online status`, { timeout: 1000 }, async () => {
    let calls = 0;
    const reached = deferred();
    const h = client(async () => {
      calls += 1;
      if (calls === 1) return response({ ready: true });
      if (phase === 'fetch') { reached.resolve(); return new Promise(() => {}); }
      return { ok: true, status: 200, json: () => { reached.resolve(); return new Promise(() => {}); } };
    }, { timeoutMs: 5000 });
    await h.request('/online');
    const before = h.states();
    const controller = new AbortController();
    const pending = h.request('/cancel', { signal: controller.signal });
    const rejected = assert.rejects(pending, error => error.name === 'AbortError');
    await reached.promise;
    controller.abort();
    await rejected;
    assert.deepEqual(h.states(), before);
  });
}

test('an already aborted caller signal does not send a new request or replace online status', async () => {
  let calls = 0;
  const h = client(async () => { calls += 1; return response({}); });
  await h.request('/online');
  const before = h.states();
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(h.request('/cancelled', { signal: controller.signal }), error => error.name === 'AbortError');
  assert.equal(calls, 1);
  assert.deepEqual(h.states(), before);
});

test('a late older network failure cannot replace a newer online result', async () => {
  const old = deferred();
  let calls = 0;
  const h = client(() => ++calls === 1 ? old.promise : Promise.resolve(response({ newest: true })));
  const pending = h.request('/old');
  const rejected = assert.rejects(pending, errorCode('network'));
  await h.request('/new');
  const before = h.states();
  old.reject(new TypeError('Old adapter failure'));
  await rejected;
  assert.deepEqual(h.states(), before);
  assert.equal(h.states().at(-1), 'online');
});

test('a late older success cannot erase a newer offline result', async () => {
  const old = deferred();
  let calls = 0;
  const h = client(() => ++calls === 1 ? old.promise : Promise.reject(new TypeError('Newest request failed')));
  const pending = h.request('/old');
  await assert.rejects(h.request('/new'), errorCode('network'));
  const before = h.states();
  old.resolve(response({ stale: true }));
  await pending;
  assert.deepEqual(h.states(), before);
  assert.equal(h.states().at(-1), 'offline');
});

test('an older deadline cannot turn a newer successful connection offline', { timeout: 1000 }, async () => {
  let calls = 0;
  const h = client(() => ++calls === 1 ? new Promise(() => {}) : Promise.resolve(response({})), { timeoutMs: 15 });
  const rejected = assert.rejects(h.request('/old'), errorCode('timeout'));
  await h.request('/new');
  const before = h.states();
  await rejected;
  assert.deepEqual(h.states(), before);
});

function bootstrapHarness() {
  const rounds = [], events = [];
  const bootstrap = createBootstrap({
    load: signal => {
      const pending = deferred();
      rounds.push({ signal, ...pending });
      return pending.promise;
    },
    commit: data => events.push(['commit', data]),
    onLoading: () => events.push(['loading']),
    onError: error => events.push(['error', error]),
    onReady: data => events.push(['ready', data]),
  });
  return { bootstrap, rounds, events };
}

test('bootstrap commits complete data before marking the page ready', async () => {
  const h = bootstrapHarness();
  const pending = h.bootstrap();
  const data = { modules: ['HKJUR'], registry: ['MR'], health: { ok: true } };
  assert.deepEqual(h.events, [['loading']]);
  h.rounds[0].resolve(data);
  await pending;
  assert.deepEqual(h.events, [['loading'], ['commit', data], ['ready', data]]);
});

test('bootstrap failure commits nothing and a manual retry can succeed', async () => {
  const h = bootstrapHarness();
  const failure = new Error('Synthetic bootstrap failure');
  const first = h.bootstrap();
  h.rounds[0].reject(failure);
  await first;
  assert.deepEqual(h.events, [['loading'], ['error', failure]]);
  assert.equal(h.rounds.length, 1, 'no automatic retry');
  const second = h.bootstrap();
  assert.equal(h.rounds[0].signal.aborted, true);
  const data = { modules: ['LATEST'] };
  h.rounds[1].resolve(data);
  await second;
  assert.deepEqual(h.events.slice(-3), [['loading'], ['commit', data], ['ready', data]]);
});

for (const outcome of ['success', 'failure']) {
  test(`an older bootstrap ${outcome} cannot overwrite the latest completed round`, async () => {
    const h = bootstrapHarness();
    const first = h.bootstrap();
    const second = h.bootstrap();
    assert.equal(h.rounds[0].signal.aborted, true);
    assert.equal(h.rounds[1].signal.aborted, false);
    const latest = { modules: ['LATEST'] };
    h.rounds[1].resolve(latest);
    await second;
    const before = [...h.events];
    if (outcome === 'success') h.rounds[0].resolve({ modules: ['STALE'] });
    else h.rounds[0].reject(new Error('Stale bootstrap failure'));
    await first;
    assert.deepEqual(h.events, before);
    assert.deepEqual(h.events.filter(event => event[0] === 'commit'), [['commit', latest]]);
  });
}

test('an older bootstrap success cannot replace the newest visible failure', async () => {
  const h = bootstrapHarness();
  const first = h.bootstrap();
  const second = h.bootstrap();
  const failure = new Error('Latest bootstrap failed');
  h.rounds[1].reject(failure);
  await second;
  const before = [...h.events];
  h.rounds[0].resolve({ modules: ['STALE'] });
  await first;
  assert.deepEqual(h.events, before);
  assert.deepEqual(h.events.filter(event => event[0] === 'commit'), []);
  assert.deepEqual(h.events.at(-1), ['error', failure]);
});

test('commit failure is visible and does not claim readiness', async () => {
  const events = [];
  const failure = new Error('Synthetic commit error');
  const bootstrap = createBootstrap({
    load: async () => ({ ready: true }),
    commit: () => { throw failure; },
    onLoading: () => events.push('loading'),
    onError: error => events.push(error),
    onReady: () => events.push('ready'),
  });
  await bootstrap();
  assert.deepEqual(events, ['loading', failure]);
});

test('bootstrap awaits asynchronous readiness work', async () => {
  const ready = deferred(), reached = deferred();
  let settled = false;
  const bootstrap = createBootstrap({
    load: async () => ({ ready: true }), commit: () => {}, onLoading: () => {},
    onError: error => assert.fail(error),
    onReady: () => { reached.resolve(); return ready.promise; },
  });
  const pending = bootstrap().then(() => { settled = true; });
  await reached.promise;
  assert.equal(settled, false);
  ready.resolve();
  await pending;
  assert.equal(settled, true);
});

// Execute the actual page handlers with a minimal local DOM, not copies of
// their retry, state-commit or navigation decisions.
const page = readFileSync(new URL('../public/index.html', import.meta.url), 'utf8');
function sourceBetween(start, end) {
  const first = page.indexOf(start), last = page.indexOf(end, first);
  assert.ok(first >= 0 && last > first, `real page boundaries exist: ${start}`);
  return page.slice(first, last);
}
const connectionSource = sourceBetween('function offerRetry(', 'const state =');
const navigationSource = sourceBetween('let navigationRequest=0;', "$('#gq').addEventListener");
const startupSource = sourceBetween('const init=createBootstrap({', '</script>');
assert.match(startupSource, /\ninit\(\);\s*$/);
const startupDefinitions = startupSource.replace(/\ninit\(\);\s*$/, '\n');

function domNode(tag = 'div') {
  const node = {
    tag, children: [], buttons: new Map(), dataset: {}, hidden: false, disabled: false,
    textContent: '', _html: '',
    get innerHTML() { return this._html + this.children.map(child => child.innerHTML || '').join(''); },
    set innerHTML(value) {
      this._html = String(value); this.children = []; this.buttons.clear();
      for (const match of this._html.matchAll(/\b(data-(?:startup|page)-retry)\b/g)) {
        this.buttons.set(`[${match[1]}]`, domNode('button'));
      }
    },
    appendChild(child) { this.children.push(child); return child; },
    replaceChildren(...children) { this._html = ''; this.buttons.clear(); this.children = children; },
    setAttribute(name, value) { this[name] = String(value); },
    querySelector(selector) {
      if (this.buttons.has(selector)) return this.buttons.get(selector);
      for (const child of this.children) {
        const found = child.querySelector?.(selector);
        if (found) return found;
      }
      return null;
    },
  };
  return node;
}

function pageHarness(fetcher, { realRoute = false, viewApi } = {}) {
  const nodes = { '#main': domNode(), '#apistat': domNode('b'), '#connectionRetry': domNode('button') };
  const state = { mode: 'api', tax: null, elements: null, stats: null };
  let readyRoutes = 0;
  const context = vm.createContext({
    API: '/api', state, createBootstrap,
    createApiClient: options => createApiClient({ ...options, fetcher, timeoutMs: 1000 }),
    $: selector => { assert.ok(nodes[selector], `known page element: ${selector}`); return nodes[selector]; },
    el: (tag, className, html) => {
      const node = domNode(tag); node.className = className;
      if (html != null) node.innerHTML = html;
      return node;
    },
    esc: value => String(value ?? '').replace(/[&<>"']/g, character => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[character])),
    document: { createElement: tag => domNode(tag) },
    renderModes: () => {}, renderContext: () => {},
    route: async () => { readyRoutes += 1; },
    viewApi: viewApi || (async node => { node.innerHTML = 'SYNTHETIC API PAGE'; }),
    fetch: () => { realNetworkAttempts += 1; throw new Error('Real page network is forbidden'); },
  });
  vm.runInContext(connectionSource, context, { filename: 'index.html-connection-handlers' });
  if (realRoute) vm.runInContext(navigationSource, context, { filename: 'index.html-route-retry' });
  vm.runInContext(startupDefinitions, context, { filename: 'index.html-startup-retry' });
  return {
    nodes, state,
    evaluate: source => vm.runInContext(source, context),
    readyRoutes: () => readyRoutes,
  };
}

test('real startup failure offers a working retry and commits metadata only after all three requests succeed', async () => {
  const calls = [];
  const h = pageHarness((path, options) => {
    const pending = deferred(); calls.push({ path, options, ...pending }); return pending.promise;
  });
  const first = h.evaluate('init()');
  assert.deepEqual(calls.map(call => call.path), ['/api/taxonomy', '/api/elements', '/api/stats']);
  calls[0].resolve(response({ oldTaxonomy: true }));
  calls[1].resolve(response({ oldElements: true }));
  calls[2].reject(new TypeError('Synthetic missing metadata'));
  await first;
  assert.deepEqual([h.state.tax, h.state.elements, h.state.stats], [null, null, null]);
  assert.equal(h.readyRoutes(), 0);
  assert.match(h.nodes['#main'].innerHTML, /暂时无法读取资料|重试连接并加载/);
  const retry = h.nodes['#main'].querySelector('[data-startup-retry]');
  assert.equal(typeof retry?.onclick, 'function');
  const second = retry.onclick();
  assert.deepEqual(calls.slice(3).map(call => call.path), ['/api/taxonomy', '/api/elements', '/api/stats']);
  const values = [{ latestTaxonomy: true }, { latestElements: true }, { latestStats: true }];
  calls[3].resolve(response(values[0]));
  await Promise.resolve();
  assert.deepEqual([h.state.tax, h.state.elements, h.state.stats], [null, null, null]);
  calls[4].resolve(response(values[1]));
  calls[5].resolve(response(values[2]));
  await second;
  assert.deepEqual([h.state.tax, h.state.elements, h.state.stats], values);
  assert.equal(h.readyRoutes(), 1);
  assert.equal(calls.length, 6);
  assert.equal(h.nodes['#apistat'].dataset.state, 'online');
});

test('the real route error card retries the same page directly', async () => {
  let views = 0;
  const h = pageHarness(() => assert.fail('route fixture must not call the network'), {
    realRoute: true,
    viewApi: async node => {
      views += 1;
      if (views === 1) throw new Error('Synthetic page error <unsafe>');
      node.innerHTML = 'RECOVERED SAME PAGE';
    },
  });
  await h.evaluate('route()');
  assert.match(h.nodes['#main'].innerHTML, /加载失败/);
  assert.match(h.nodes['#main'].innerHTML, /&lt;unsafe&gt;/);
  const retry = h.nodes['#main'].querySelector('[data-page-retry]');
  assert.equal(typeof retry?.onclick, 'function');
  await retry.onclick();
  assert.equal(views, 2);
  assert.equal(h.state.mode, 'api');
  assert.equal(h.nodes['#main'].innerHTML, 'RECOVERED SAME PAGE');
});

test('the real top connection check uses health only after startup and never replays failed POSTs', async () => {
  const calls = [];
  const h = pageHarness(async (path, options) => {
    calls.push({ path, options });
    if (options.method === 'POST') throw new TypeError('Synthetic failed POST');
    return response({ path });
  });
  await h.evaluate('init()');
  assert.equal(h.readyRoutes(), 1);
  for (const path of ['/score', '/maintenance/propose']) {
    await assert.rejects(h.evaluate(`api(${JSON.stringify(path)}, {method:'POST', body:'{}'})`), errorCode('network'));
    assert.equal(h.nodes['#apistat'].dataset.state, 'offline');
    assert.match(h.nodes['#apistat'].textContent, /中断/);
    assert.equal(h.nodes['#connectionRetry'].hidden, false);
    const before = calls.length;
    await h.nodes['#connectionRetry'].onclick();
    assert.equal(calls.length, before + 1);
    assert.equal(calls.at(-1).path, '/api/health');
    assert.notEqual(calls.at(-1).options.method, 'POST');
    assert.equal(h.nodes['#apistat'].dataset.state, 'online');
    assert.match(h.nodes['#apistat'].textContent, /最近请求成功/);
    assert.doesNotMatch(h.nodes['#apistat'].textContent, /\blive\b|持续在线|实时在线/i);
    assert.equal(h.nodes['#connectionRetry'].disabled, false);
  }
  assert.equal(calls.filter(call => call.path === '/api/score').length, 1);
  assert.equal(calls.filter(call => call.path === '/api/maintenance/propose').length, 1);
  assert.equal(h.readyRoutes(), 1, 'a health check does not restart or navigate the page');
});
