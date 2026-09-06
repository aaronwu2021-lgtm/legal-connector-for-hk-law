import {after, test} from 'node:test';
import assert from 'node:assert/strict';
import handler from '../netlify/functions/api.mjs';
import ELEMENTS from '../netlify/functions/_elements.mjs';
import PERSUASIVE from '../netlify/functions/_persuasive.mjs';
import {createHistoricalLibrary, eligibleAt, parseAsOf} from '../netlify/functions/historical.mjs';

// Independent acceptance: node --test server/test/historical-review.test.mjs
// Import generated snapshots only; never execute/import builders or use HTTP.
const savedFetch = globalThis.fetch;
let networkAttempts = 0;
globalThis.fetch = async () => { networkAttempts += 1; throw new Error('Historical review is offline'); };
const original = JSON.stringify({ELEMENTS, PERSUASIVE});
after(() => {
  globalThis.fetch = savedFetch;
  assert.equal(networkAttempts, 0);
  assert.equal(JSON.stringify({ELEMENTS, PERSUASIVE}), original);
});

async function rest(path, params = {}) {
  const query = new URLSearchParams({...params, live: '0'});
  const response = await handler(new Request(`http://offline.invalid/api/${path}?${query}`));
  return {status: response.status, body: await response.json()};
}
async function mcp(name, args, method = 'tools/call') {
  const response = await handler(new Request('http://offline.invalid/api/mcp', {
    method: 'POST', headers: {'content-type': 'application/json'},
    body: JSON.stringify({jsonrpc: '2.0', id: 81, method, params: {name, arguments: args}}),
  }));
  const envelope = await response.json();
  return {status: response.status, envelope, body: envelope.result?.content?.[0]?.text
    ? JSON.parse(envelope.result.content[0].text) : envelope};
}
const pairs = [
  ['checklist', {jurisdiction: 'HK'}, 'pleading_checklist', {jurisdiction: 'HK'}],
  ['elements', {jurisdiction: 'HK'}, 'get_elements', {claim: 'misrepresentation', jurisdiction: 'HK'}],
  ['element/E3c', {}, 'get_element_test', {id: 'E3c'}],
  ['element/D1', {}, 'get_element_test', {id: 'D1'}],
  ['timeline/T2', {j: 'SG'}, 'get_timeline', {id: 'T2', jurisdictions: ['SG']}],
  ['verify', {cite: 'Long Year Development v Tse Fuk Man'}, 'verify_citation', {citation: 'Long Year Development v Tse Fuk Man'}],
];
const prose = new Set(['holding','holdings','note','notes','source','src','eff','effect','effects','rule','rules',
  'test','plead','statute','statutes','statute_by_jurisdiction','treat','treatment','signal_note','summary','gaps']);
function hasNoOriginalProse(value, path = '') {
  if (!value || typeof value !== 'object') return;
  for (const [key, child] of Object.entries(value)) {
    // The rank/recency difference contains a newly generated metadata explanation.
    if (key === 'note' && /Rank and recency identify different recorded authorities/.test(child)) continue;
    assert.ok(!prose.has(key), `${path}.${key}: historical output must omit unversioned source prose`);
    hasNoOriginalProse(child, `${path}.${key}`);
  }
}

test('public REST and MCP historical projections agree for every paired surface', async () => {
  for (const year of ['1990', '2013', '2026']) for (const [path, query, tool, args] of pairs) {
    const a = await rest(path, {...query, as_of: year});
    const b = await mcp(tool, {...args, as_of: Number(year)});
    assert.equal(a.status, 200, `${path}: ${JSON.stringify(a.body)}`);
    assert.equal(b.envelope.result?.isError, false, `${tool}: ${JSON.stringify(b)}`);
    assert.deepEqual(a.body, b.body, `${path}/${tool}`);
    assert.equal(a.body.historical_rule_status, 'historical-rule-not-modelled');
    hasNoOriginalProse(a.body);
  }
});

test('each MCP historical tool rejects explicit null/boolean/fraction/invalid calendar cutoffs', async () => {
  for (const [, , name, args] of pairs) for (const as_of of [null, false, true, [], {}, 999, 10000, 1990.1,
    '', ' 1990', '1990x', '1900-02-29', '2026-02-29', '2026-04-31', '2026-13-01']) {
    const out = await mcp(name, {...args, as_of});
    assert.ok(out.status < 500, `${name}/${JSON.stringify(as_of)}`);
    assert.equal(out.envelope.result?.isError, true, JSON.stringify(out));
    assert.equal(out.body.code, 'invalid-as-of', JSON.stringify(out));
  }
});

test('each REST historical endpoint rejects malformed cutoffs instead of exposing the current view', async () => {
  for (const [path, query] of [...pairs, ['jurisdictions', {}]]) for (const as_of of [
    '', 'null', 'false', 'true', '999', '10000', '1990.1', '1990 ', '2026-02-29', '2026-01-32',
  ]) {
    const out = await rest(path, {...query, as_of});
    assert.equal(out.status, 400, `${path}/${as_of}: ${JSON.stringify(out)}`);
    assert.equal(out.body.code, 'invalid-as-of');
  }
});

test('unsupported historical surfaces explicitly reject a cutoff', async () => {
  for (const path of ['scored', 'score', 'case', 'search', 'persuasive', 'maintenance']) {
    const out = await rest(path, {as_of: '1990', name: 'Hayward', q: 'Hayward'});
    assert.equal(out.status, 400, JSON.stringify(out));
    assert.equal(out.body.code, 'unsupported-as-of');
  }
  for (const name of ['lookup_case','search_corpus','score_factors','resolve_jurisdiction']) {
    const out = await mcp(name, {as_of: 1990, name: 'Hayward', q: 'Hayward', module: 'HKJUR', text: 'Hong Kong'});
    assert.equal(out.envelope.result?.isError, true, JSON.stringify(out));
    assert.equal(out.body.code, 'unsupported-as-of');
  }
});

test('MCP advertises the same bounded year/date schema on all historical tools', async () => {
  const {envelope} = await mcp(undefined, undefined, 'tools/list');
  const tools = envelope.result.tools;
  const schemas = [...new Set(pairs.map(p => p[2]))].map(name => {
    const schema = tools.find(t => t.name === name)?.inputSchema?.properties?.as_of;
    assert.ok(schema, `${name} exposes as_of`);
    assert.equal(schema.oneOf.find(s => s.type === 'integer').minimum, 1000);
    assert.equal(schema.oneOf.find(s => s.type === 'integer').maximum, 9999);
    assert.ok(schema.oneOf.some(s => s.type === 'string' && s.pattern));
    return schema;
  });
  schemas.forEach(s => assert.deepEqual(s, schemas[0]));
});

test('complete 1990 research responses contain no future names or evidence through nested parents', async () => {
  for (const [path, query] of [...pairs.filter(p => p[0] !== 'verify'), ['jurisdictions', {}], ['elements', {}]]) {
    const {body} = await rest(path, {...query, as_of: '1990'});
    const json = JSON.stringify(body);
    for (const text of ['Long Year', 'Hayward', 'Joytex', 'Shine Grace', 'Li Yuhong', 'Koo Ming', 'Alireza', '2016', '2026']) {
      assert.ok(!json.includes(text), `${path}: leaked ${text}`);
    }
    hasNoOriginalProse(body);
  }
});

test('a valid 2013 SG timeline event cannot carry its retrospective 2016 commentary', async () => {
  for (const out of [(await rest('timeline/T2', {j: 'SG', as_of: '2013'})).body,
    (await mcp('get_timeline', {id: 'T2', jurisdictions: ['SG'], as_of: 2013})).body]) {
    assert.ok(out.events.some(e => e.y === 2013));
    assert.ok(!JSON.stringify(out).includes('2016'));
    hasNoOriginalProse(out);
  }
});

test('same-year precise cutoffs omit year-only records while year-end includes them', async () => {
  const record = ELEMENTS.jurisdictions.SG.cases.find(r => (r.case || r.name || '').startsWith('Wee Chiaw Sek Anna'));
  assert.ok(record);
  const name = record.case || record.name;
  for (const day of ['2013-01-01','2013-12-30']) {
    const out = (await rest('verify', {cite: name, as_of: day})).body;
    assert.equal(out.identity_exists, true);
    assert.equal(out.usable_at_as_of, false);
    assert.deepEqual(out.evidence_records, []);
    assert.ok(out.historical_limitations.excluded_counts['insufficient-date-precision']);
    const timeline = (await rest('timeline/T2', {j: 'SG', as_of: day})).body;
    assert.ok(!JSON.stringify(timeline).includes(name));
  }
  const end = (await rest('verify', {cite: name, as_of: '2013-12-31'})).body;
  assert.equal(end.usable_at_as_of, true);
  assert.ok(end.evidence_records.length > 0);
  assert.equal(end.evidence_records[0].pin, record.pin);
  assert.equal(end.evidence_records[0].verified, record.verified);
});

test('a future direct identity and a mismatched citation remain distinct without future prose', async () => {
  const name = 'Koo Ming Kown v The Baptist Convention of Hong Kong';
  const good = (await rest('verify', {cite: name, as_of: '1990'})).body;
  assert.equal(good.identity_exists, true);
  assert.equal(good.usable_at_as_of, false);
  assert.equal(good.authority.identity_only, true);
  assert.deepEqual(good.evidence_records, []);
  hasNoOriginalProse(good);
  const bad = (await rest('verify', {cite: 'Derry v Peek [2016] UKSC 48', as_of: '1990'})).body;
  assert.equal(bad.found, false);
  assert.equal(bad.status, 'citation-mismatch');
  assert.equal(bad.authority, undefined);
  assert.ok(!JSON.stringify(bad).includes('Hayward'));
});

test('a historical query does not damage subsequent current provenance', async () => {
  const query = {cite: 'Long Year Development v Tse Fuk Man'};
  const before = (await rest('verify', query)).body;
  assert.ok(before.evidence_records.some(r => r.verified === 'verified-quoted'));
  assert.ok(before.evidence_records.some(r => r.source || r.src));
  const historical = (await rest('verify', {...query, as_of: '1991'})).body;
  assert.equal(historical.identity_exists, true);
  assert.deepEqual(historical.evidence_records, []);
  assert.ok(historical.historical_limitations.excluded_counts['source-chronology-not-modelled']);
  assert.deepEqual((await rest('verify', query)).body, before);
});

const fixture = events => createHistoricalLibrary({elements: [], defences: [], jurisdictions: {},
  timelines: {T: {events}}});
const cutoff = year => parseAsOf(year);

test('all stored year declarations must agree with a full date and each other', () => {
  for (const record of [
    {y: 2026, decision_date: '1990-01-01'},
    {year: 1990, y: 2026},
    {decision_date: '1990-01-01', cite: '[2026] UKSC 1'},
    {y: 2026, decision_date: '1990-01-01', cite: '[1990] UKHL 1'},
  ]) {
    assert.equal(eligibleAt(record, cutoff(1990)).eligible, false, JSON.stringify(record));
    assert.equal(eligibleAt(record, cutoff(1990)).reason, 'conflicting-record-date', JSON.stringify(record));
  }
});

test('conflicting timeline chronology cannot expose a future event under an old full date', () => {
  const out = fixture([{j: 'HK', y: 2026, decision_date: '1990-01-01', case: 'FUTURE CASE', court_rank: 4}])
    .timeline('T', cutoff(1990));
  assert.deepEqual(out.events, []);
  assert.ok(!JSON.stringify(out).includes('FUTURE CASE'));
  assert.ok(out.historical_limitations.excluded_counts['conflicting-record-date']);
});

test('eligible timeline dates normalize the year before sorting and reporting recency', () => {
  const out = fixture([
    {j: 'HK', year: 2002, case: 'Later year', court_rank: 3},
    {j: 'HK', decision_date: '2001-12-31', case: 'Earlier date', court_rank: 3},
  ]).timeline('T', cutoff(2002));
  assert.deepEqual(out.events.map(e => e.y), [2001, 2002]);
  assert.equal(out.latest_rules[0].case, 'Later year');
  assert.equal(out.latest_rules[0].since, 2002);
  assert.equal(out.standing_rules[0].case, 'Later year');
});

test('invalid historical MCP jurisdiction filters produce a structured tool error', async () => {
  for (const jurisdictions of [42, {}, true, 'HK', ['HK', 42]]) {
    const out = await mcp('get_timeline', {id: 'T1', as_of: 1990, jurisdictions});
    assert.ok(out.status < 500, JSON.stringify(out));
    assert.equal(out.envelope.result?.isError, true, JSON.stringify(out));
    assert.ok(out.body.error);
  }
});

test('same-rank same-year records cannot acquire a unique recency winner from array order', () => {
  const events = [{j: 'HK', y: 2001, case: 'First fixture', court_rank: 3},
    {j: 'HK', y: 2001, case: 'Second fixture', court_rank: 3}];
  for (const ordered of [events, events.toReversed()]) {
    const out = fixture(ordered).timeline('T', cutoff(2001));
    assert.equal(out.events.length, 2, 'both dated identities remain useful');
    for (const key of ['latest_rules', 'standing_rules']) {
      const selected = out[key].filter(r => r.case);
      assert.notEqual(selected.length, 1, `${key}: only a year cannot select a unique winner`);
    }
  }
});

test('full decision dates resolve recency while mixed year/day precision does not', () => {
  const earlier = {j: 'HK', decision_date: '2001-01-01', case: 'Earlier fixture', court_rank: 3};
  const later = {j: 'HK', decision_date: '2001-12-01', case: 'Later fixture', court_rank: 3};
  const precise = fixture([later, earlier]).timeline('T', cutoff(2001));
  assert.equal(precise.latest_rules[0].case, later.case);
  assert.equal(precise.standing_rules[0].case, later.case);
  for (const second of [{...later, decision_date: undefined, y: 2001}, {...later, decision_date: earlier.decision_date}]) {
    const uncertain = fixture([second, earlier]).timeline('T', cutoff(2001));
    for (const key of ['latest_rules', 'standing_rules']) {
      assert.notEqual(uncertain[key].filter(r => r.case).length, 1, `${key}: chronology is tied or insufficient`);
    }
  }
});

test('quoted aliases and source-bearing evidence are withheld without changing original provenance', () => {
  const library = fixture([]);
  for (const provenance of [{verified: 'quoted'}, {verified: 'verified-quoted'},
    {verified: 'verified-primary', source: ''}, {verified: 'verified-primary', src: null},
    {verified: 'primary', source: 'A source with no structured chronology'}]) {
    const record = {case: 'Fixture v Other', year: 1991, cite: '[1991] QB 1', pin: '[4]', ...provenance};
    const before = JSON.stringify(record);
    const out = library.verification({found: true, authority: record, evidence_records: [record]}, cutoff(1991));
    assert.equal(out.identity_exists, true);
    assert.deepEqual(out.evidence_records, [], JSON.stringify(provenance));
    assert.ok(out.historical_limitations.excluded_counts['source-chronology-not-modelled']);
    assert.equal(JSON.stringify(record), before);
  }
});
