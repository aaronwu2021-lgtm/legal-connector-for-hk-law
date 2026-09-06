import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

// Run the real page functions, rather than a duplicate of their navigation
// guards. These cases stop before a current successful score view needs a DOM.
const html = readFileSync(new URL('../public/index.html', import.meta.url), 'utf8');
const start = html.indexOf('const SF = {};');
const end = html.indexOf("$('#gq').addEventListener", start);
assert.ok(start >= 0 && end > start, 'the scoring/navigation source boundaries must exist');
const pageFunctions = html.slice(start, end);
assert.match(pageFunctions, /async function viewScored\(main\)/);
assert.match(pageFunctions, /async function route\(\)/);

const metadataPaths = ['/scored', '/registry', '/calibration-queue', '/scored/HKJUR'];
const currentPage = 'CURRENT API PAGE';

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function harness(pendingAt) {
  const pending = deferred();
  const reached = deferred();
  const main = { child:null, replaceChildren(child){this.child=child;}, get innerHTML(){return this.child?.innerHTML||'';} };
  const calls = [];
  let networkAttempts = 0;
  const context = vm.createContext({
    state: { mode: 'scored' },
    document: {createElement:()=>({innerHTML:''})},
    api: async path => {
      const index = calls.length;
      calls.push(path);
      assert.equal(path, metadataPaths[index], 'only the expected metadata request is allowed');
      if (index === pendingAt) {
        reached.resolve();
        return pending.promise;
      }
      return {};
    },
    fetch: () => {
      networkAttempts += 1;
      throw new Error('Real network access is forbidden in navigation tests');
    },
    $: selector => {
      assert.equal(selector, '#main');
      return main;
    },
    renderModes: () => {},
    renderContext: () => {},
    viewApi: async node => { node.innerHTML = currentPage; },
    esc: value => String(value).replace(/[&<>"']/g, character => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[character])),
  });
  vm.runInContext(pageFunctions, context, { filename: 'index.html-scoring-navigation' });
  return {
    pending, reached: reached.promise, main, calls,
    route: () => vm.runInContext('route()', context),
    navigateAway: async () => {
      context.state.mode = 'api';
      await vm.runInContext('route()', context);
      assert.equal(main.innerHTML, currentPage);
    },
    assertOffline: () => assert.equal(networkAttempts, 0),
  };
}

for (const [index, path] of metadataPaths.entries()) {
  test(`late ${path} failure cannot replace a newer page`, async () => {
    const h = harness(index);
    const oldRoute = h.route();
    await h.reached;
    await h.navigateAway();
    h.pending.reject(new Error('STALE SCORING METADATA FAILURE'));
    await oldRoute;
    assert.equal(h.main.innerHTML, currentPage);
    assert.doesNotMatch(h.main.innerHTML, /加载失败|STALE SCORING/);
    h.assertOffline();
  });

  test(`current ${path} failure remains visible`, async () => {
    const h = harness(index);
    const currentRoute = h.route();
    await h.reached;
    h.pending.reject(new Error('CURRENT SCORING METADATA FAILURE'));
    await currentRoute;
    assert.match(h.main.innerHTML, /加载失败/);
    assert.match(h.main.innerHTML, /CURRENT SCORING METADATA FAILURE/);
    assert.equal(h.calls.length, index + 1, 'a failed load must not continue to later metadata');
    h.assertOffline();
  });

  test(`late ${path} success cannot replace a newer page`, async () => {
    const h = harness(index);
    const oldRoute = h.route();
    await h.reached;
    await h.navigateAway();
    h.pending.resolve({});
    await oldRoute;
    assert.equal(h.main.innerHTML, currentPage);
    h.assertOffline();
  });
}
