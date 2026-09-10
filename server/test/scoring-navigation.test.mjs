import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync(new URL('../public/index.html', import.meta.url), 'utf8');

test('navigation is cause-centred and has no independent logic catalogue tab', () => {
  const modes = html.slice(html.indexOf('const MODES = ['), html.indexOf('const SUBS ='));
  assert.match(modes, /诉因分析 Doctrine · Logic/);
  assert.doesNotMatch(modes, /\['scored'/);
  assert.doesNotMatch(html, /async function viewScored|state\.mode\s*=\s*'scored'|state\.mode\s*===\s*'scored'/);
  assert.match(html, /api\('\/doctrine\/'\+encodeURIComponent\(claimId\)\)/);
  assert.match(html, /appendElementGroups\(main,doctrine\);\s*appendDoctrineLogic\(main,doctrine/,
    'logic must be rendered after the elements for the same cause');
});

test('coverage copy keeps element, logic, corpus and jurisdiction coverage distinct', () => {
  for (const layer of ['构成要件 Elements', '判断逻辑 Logic', '语料 Corpus', '法域资料 Jurisdictions']) {
    assert.match(html, new RegExp(layer));
  }
  assert.match(html, /“判断逻辑已建”只说明列出的判断阶段已有模型，不表示该诉因的完整构成要件/);
  assert.match(html, /这个缺口不表示该诉因没有法律要件/);
  assert.match(html, /st\.applies_when/);
  assert.match(html, /法域规则 Jurisdiction rules/);
  assert.match(html, /sameName\?'诉因内部判断结构'/);
  assert.ok(html.includes("factor.role==='discretion' ? '救济裁量事项'"));
  assert.ok(html.includes("mod.note&&(!sameName||mod.note!==doctrine.claim.note)"));
  assert.ok(html.includes("replace(/^logic-/,'')"));
  assert.match(html, /诉因结构 <span[^>]*>Doctrine · Logic<\/span>/);
  assert.match(html, /if\(composedFromLogic\)[\s\S]*?else if\(!data\.elements\.length\)/,
    'a cause composed from logic stages must not render a false element-gap card');
  assert.match(html, /统一诉因结构直接表达本诉因的构成要件、内部标准、抗辩与救济/,
    'the unified cause view should explain that logic stages are the doctrine structure');
});

const scopeStart = html.indexOf('function scopeScoreToStages');
const scopeEnd = html.indexOf('function appendDoctrineLogic', scopeStart);
assert.ok(scopeStart >= 0 && scopeEnd > scopeStart, 'score scoping helper must exist');
const scopeContext = vm.createContext({});
vm.runInContext(html.slice(scopeStart, scopeEnd) + ';this.scopeScoreToStages=scopeScoreToStages;', scopeContext);

test('score results and priority evidence are restricted to model_ref stages', () => {
  const result = {
    overall: 'undetermined', overall_reason: 'whole module',
    stages: [{ stage: 'CT-1' }, { stage: 'CT-2' }, { stage: 'CT-3' }],
    priority_evidence: [{ id: 'f1' }, { id: 'f3' }],
  };
  const selected = [{ id: 'CT-3', factors: [{ id: 'f3' }], counter_factors: [] }];
  const scoped = scopeContext.scopeScoreToStages(result, selected);
  assert.deepEqual(Array.from(scoped.stages, stage => stage.stage), ['CT-3']);
  assert.deepEqual(Array.from(scoped.priority_evidence, factor => factor.id), ['f3']);
  assert.match(scoped.overall_reason, /当前诉因引用的判断阶段/);
  assert.equal(result.stages.length, 3, 'the server result is not mutated');
});

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

const viewStart = html.indexOf('let DOCTRINE_VIEW=0;');
const viewEnd = html.indexOf('async function viewCorpus', viewStart);
assert.ok(viewStart >= 0 && viewEnd > viewStart, 'doctrine view source boundaries must exist');

test('a doctrine response that finishes after leaving cannot paint the old cause', async () => {
  const pending = deferred();
  const context = vm.createContext({
    state: { mode: 'doctrine', claim: 'private-nuisance', elements: null },
    api: path => { assert.equal(path, '/doctrine/private-nuisance'); return pending.promise; },
    encodeURIComponent, esc: String,
    el: (_tag, _className, innerHTML = '') => ({ innerHTML }),
    appendCoveragePanel() {}, appendLitigationPosition() {}, appendCorpusLinks() {},
    appendElementGroups() {}, appendDoctrineLogic() {}, claimStatusLabel() { return ''; },
    route() {}, window: { scrollTo() {} },
  });
  const main = { innerHTML: 'NEWER PAGE', children: [], appendChild(node) { this.children.push(node); } };
  context.main = main;
  vm.runInContext(html.slice(viewStart, viewEnd), context, { filename: 'index.html-doctrine-view' });
  const old = vm.runInContext('viewDoctrine(main)', context);
  context.state.mode = 'api';
  pending.resolve({ claim: { id: 'private-nuisance' }, area: { zh: '侵权法', en: 'Tort' } });
  await old;
  assert.equal(main.innerHTML, 'NEWER PAGE');
  assert.deepEqual(main.children, []);
});

test('a current doctrine failure remains available to the route error boundary', async () => {
  const context = vm.createContext({
    state: { mode: 'doctrine', claim: 'private-nuisance', elements: null },
    api: async () => { throw new Error('CURRENT DOCTRINE FAILURE'); },
    encodeURIComponent, esc: String,
    el: () => ({}), appendCoveragePanel() {}, appendLitigationPosition() {}, appendCorpusLinks() {},
    appendElementGroups() {}, appendDoctrineLogic() {}, claimStatusLabel() { return ''; },
    route() {}, window: { scrollTo() {} }, main: { innerHTML: '' },
  });
  vm.runInContext(html.slice(viewStart, viewEnd), context, { filename: 'index.html-doctrine-view' });
  await assert.rejects(vm.runInContext('viewDoctrine(main)', context), /CURRENT DOCTRINE FAILURE/);
});
