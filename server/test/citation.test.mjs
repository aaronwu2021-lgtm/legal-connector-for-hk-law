import { after, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import handler from '../netlify/functions/api.mjs';
import ELEMENTS from '../netlify/functions/_elements.mjs';
import PERSUASIVE from '../netlify/functions/_persuasive.mjs';

// Stored fixtures only. Never import builders or resolve a citation over HTTP.
const originalFetch = globalThis.fetch;
let networkAttempts = 0;
globalThis.fetch = async () => {
  networkAttempts += 1;
  throw new Error('Network is forbidden in citation identity tests');
};
after(() => {
  globalThis.fetch = originalFetch;
  assert.equal(networkAttempts, 0, 'citation identity checks must remain offline');
});

const coreRecords = [];
for (const element of ELEMENTS.elements) for (const subtest of element.sub_tests) {
  for (const authority of subtest.auth || []) coreRecords.push({ ...authority, where: subtest.id, branch: 'core' });
}
for (const defence of ELEMENTS.defences) {
  for (const authority of defence.auth || []) coreRecords.push({ ...authority, where: defence.id, branch: 'core' });
}
for (const [jurisdiction, overlay] of Object.entries(ELEMENTS.jurisdictions)) {
  for (const authority of overlay.cases || []) coreRecords.push({ ...authority, where: `${jurisdiction} overlay`, branch: 'core' });
}
const caseName = (record) => record.case || record.name;
function core(name) {
  const record = coreRecords.find((r) => caseName(r).includes(name));
  assert.ok(record, `stored core fixture ${name} exists`);
  return record;
}
function persuasive(name) {
  const record = PERSUASIVE.cases.find((r) => r.name.includes(name));
  assert.ok(record, `stored persuasive fixture ${name} exists`);
  return record;
}
const hayward = core('Hayward');
const derry = core('Derry v Peek');
const bv = core('BV Nederlandse');
const edgington = coreRecords.filter((r) => caseName(r) === 'Edgington v Fitzmaurice');
const longYear = coreRecords.filter((r) => caseName(r).startsWith('Long Year Development'));
const dbs = coreRecords.filter((r) => caseName(r).startsWith('DBS Bank (HK)'));
const barr = persuasive('Barr v Biffa');
const criminal = persuasive('R v HTM Ltd');
const splitCites = (record) => record.cite.split(';').map((cite) => cite.trim());
const firstCite = (record) => splitCites(record)[0];
const storedSnapshot = JSON.stringify({ ELEMENTS, PERSUASIVE });
after(() => assert.equal(JSON.stringify({ ELEMENTS, PERSUASIVE }), storedSnapshot, 'stored evidence remains unchanged'));

async function rest(citation) {
  const query = new URLSearchParams({ live: '0' });
  if (citation !== undefined) query.set('cite', citation);
  const response = await handler(new Request(`http://offline.invalid/api/verify?${query}`));
  assert.ok(response.status < 500, 'citation lookup must not return a server error');
  return { status: response.status, body: await response.json() };
}

async function mcp(args) {
  const response = await handler(new Request('http://offline.invalid/api/mcp', {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 3, method: 'tools/call', params: { name: 'verify_citation', arguments: args } }),
  }));
  const envelope = await response.json();
  assert.ok(response.status < 500, JSON.stringify(envelope));
  assert.ok(envelope.result?.content?.[0]?.text, JSON.stringify(envelope));
  return { envelope, body: JSON.parse(envelope.result.content[0].text) };
}

async function lookup(citation) {
  const direct = await rest(citation);
  const tool = await mcp({ citation });
  assert.deepEqual(direct.body, tool.body, `REST/MCP agreement: ${String(citation)}`);
  return direct.body;
}

function matched(output) {
  assert.equal(output.found, true, JSON.stringify(output));
  assert.equal(output.status, 'matched');
  assert.equal(output.proposition_check, 'not-performed');
  assert.ok(output.identity && typeof output.identity === 'object', 'matched identity metadata');
  assert.ok(output.authority && typeof output.authority === 'object', 'truthful representative authority remains available');
  assert.ok(Array.isArray(output.evidence_records) && output.evidence_records.length, 'separate stored evidence records');
  for (const record of output.evidence_records) {
    assert.ok(typeof record.where === 'string' && record.where.trim(), 'every source retains its record location');
    assert.ok(typeof record.verified === 'string' && record.verified, 'every source retains its original level');
  }
}

const forbiddenCandidateFields = new Set([
  'verified', 'pin', 'source', 'src', 'note', 'holding', 'effect', 'eff', 'treatment',
  'signal', 'signal_note', 'authority', 'evidence_records', 'level_meaning', 'maps_to',
]);
function identityOnly(value) {
  if (Array.isArray(value)) return value.forEach(identityOnly);
  if (!value || typeof value !== 'object') return;
  for (const [key, child] of Object.entries(value)) {
    assert.ok(!forbiddenCandidateFields.has(key), `conflict candidate must not expose evidence field ${key}`);
    identityOnly(child);
  }
}

function unresolved(output, statuses) {
  assert.equal(output.found, false, JSON.stringify(output));
  assert.ok(statuses.includes(output.status), JSON.stringify(output));
  assert.ok(output.authority === undefined || output.authority === null, 'conflict must not carry a successful authority');
  assert.ok(output.evidence_records === undefined || output.evidence_records.length === 0, 'conflict must not expose evidence as a result');
  assert.ok(output.level_meaning === undefined || output.level_meaning === null, 'conflict must not inherit a verification description');
  if (output.candidates) identityOnly(output.candidates);
}

function retains(record, original) {
  assert.equal(caseName(record), caseName(original));
  for (const field of ['cite', 'verified', 'court', 'pin', 'source', 'src', 'note', 'holding']) {
    if (Object.hasOwn(original, field)) assert.deepEqual(record[field], original[field], `${caseName(original)}: retain ${field}`);
    else if (['pin', 'source', 'src', 'note'].includes(field)) {
      assert.ok(record[field] === undefined || record[field] === null, `${caseName(original)}: do not borrow ${field} from another source`);
    }
  }
  if (original.where) assert.equal(record.where, original.where);
}

describe('explicit citations and case names must identify the same stored case', () => {
  it('rejects the reproduced wrong Hayward neutral citation instead of falling back to its name', async () => {
    unresolved(await lookup(`${caseName(hayward)} [2099] UKSC 999`), ['citation-mismatch', 'unresolved-citation']);
  });

  it('rejects Derry named with Hayward citation even though each separately exists', async () => {
    unresolved(await lookup(`${caseName(derry)} ${firstCite(hayward)}`), ['citation-mismatch']);
    unresolved(await lookup(`${caseName(hayward)} ${firstCite(derry)}`), ['citation-mismatch']);
  });

  it('parses EWCA Civ and rejects a wrong number without accepting a name-only match', async () => {
    const wrong = firstCite(bv).replace(/596$/, '999999');
    assert.notEqual(wrong, firstCite(bv));
    unresolved(await lookup(`${caseName(bv)} ${wrong}`), ['citation-mismatch', 'unresolved-citation']);
  });

  it('honors the supplied second party with and without an explicit citation', async () => {
    for (const citation of [
      `Hayward v Peek ${firstCite(hayward)}`,
      `Derry v Zurich Insurance ${firstCite(derry)}`,
      `DBS Bank (HK) v Unrelated Synthetic Defendant ${firstCite(dbs[0])}`,
      `${caseName(barr).split(' v ')[0]} v Unrelated Synthetic Defendant ${barr.cite}`,
    ]) unresolved(await lookup(citation), ['citation-mismatch']);
    for (const name of ['Hayward v Peek', 'Derry v Zurich Insurance', 'DBS Bank (HK) v Unrelated Synthetic Defendant']) {
      unresolved(await lookup(name), ['citation-mismatch', 'not-found']);
    }
  });

  it('checks every extra citation regardless of order or separator', async () => {
    const known = firstCite(hayward);
    const conflict = firstCite(barr);
    for (const input of [
      `${caseName(hayward)} ${known}; ${conflict}`,
      `${caseName(hayward)} ${conflict}; ${known}`,
      `${caseName(hayward)} ${known}, ${conflict}`,
      `${caseName(hayward)} ${known} ${conflict}`,
      `${known}; ${conflict}`,
    ]) unresolved(await lookup(input), ['citation-mismatch']);
  });

  it('rejects an additional unresolved report citation, rather than ignoring it', async () => {
    for (const input of [
      `${caseName(hayward)} ${firstCite(hayward)}; [2099] QB 999`,
      `${caseName(hayward)} [2099] QB 999; ${firstCite(hayward)}`,
      `${caseName(bv)} [2020] QB 999999`,
      '[2099] 7 Synthetic Reports 999',
    ]) unresolved(await lookup(input), ['unresolved-citation', 'citation-mismatch']);
  });

  it('keeps report and neutral series distinct instead of matching only their year and number', async () => {
    for (const input of [`${caseName(hayward)} [2016] AC 48`, `${caseName(bv)} [2019] QB 596`]) {
      unresolved(await lookup(input), ['unresolved-citation', 'citation-mismatch']);
    }
  });

  it('does not permit a persuasive match to override conflicting core name evidence', async () => {
    unresolved(await lookup(`${caseName(derry)} ${barr.cite}`), ['citation-mismatch']);
    unresolved(await lookup(`${caseName(barr)} ${firstCite(derry)}`), ['citation-mismatch']);
  });
});

describe('positive citation identities and grounded names', () => {
  for (const record of [hayward, bv, derry, barr, criminal]) {
    it(`${caseName(record)}: exact stored name, citation and parallel citations agree`, async () => {
      const full = await lookup(`${caseName(record)} ${record.cite}`);
      matched(full);
      for (const input of [caseName(record), record.cite, ...splitCites(record), `${caseName(record)} ${splitCites(record).reverse().join('; ')}`]) {
        const result = await lookup(input);
        matched(result);
        assert.deepEqual(result.identity, full.identity, input);
        assert.deepEqual(result.evidence_records, full.evidence_records, input);
      }
    });
  }

  it('normalizes harmless case and whitespace for a multiword court citation', async () => {
    const expected = await lookup(`${caseName(bv)} ${bv.cite}`);
    const input = `${caseName(bv).toUpperCase()}   [2019]   ewca\tCIV   596 ; [2020]   qb   551`;
    const normalized = await lookup(input);
    matched(normalized);
    assert.deepEqual(normalized.identity, expected.identity);
    assert.deepEqual(normalized.evidence_records, expected.evidence_records);
  });

  it('recognizes the complete EWCA Crim court token and refuses a changed division or number', async () => {
    matched(await lookup(`${caseName(criminal)} ${criminal.cite}`));
    for (const cite of [criminal.cite.replace('Crim', 'Civ'), criminal.cite.replace(/\d+$/, '999999')]) {
      unresolved(await lookup(`${caseName(criminal)} ${cite}`), ['citation-mismatch', 'unresolved-citation']);
    }
  });

  it('recognizes an abbreviation only where it is present in the stored name', async () => {
    const peekay = core('Peekay Intermark v ANZ');
    const result = await lookup(`${caseName(peekay)} ${peekay.cite}`);
    matched(result);
    assert.ok(result.evidence_records.some((r) => caseName(r) === caseName(peekay)));
  });

  it('keeps Long v Lloyd distinct from the longer Long Year party name', async () => {
    const lloyd = core('Long v Lloyd');
    const result = await lookup(`${caseName(lloyd)} ${lloyd.cite}`);
    matched(result);
    assert.ok(result.evidence_records.every((r) => !caseName(r).startsWith('Long Year')));
    unresolved(await lookup(`${caseName(lloyd)} ${longYear[0].cite}`), ['citation-mismatch']);
  });
});

describe('name ambiguity and per-source evidence preservation', () => {
  it('returns distinct identity candidates for DBS Bank (HK), with no selected authority', async () => {
    assert.equal(dbs.length, 2, 'two stored DBS identities underpin the ambiguity fixture');
    for (const input of ['DBS Bank (HK)', 'DBS Bank(HK)']) {
      const result = await lookup(input);
      unresolved(result, ['ambiguous']);
      assert.ok(Array.isArray(result.candidates) && result.candidates.length === 2);
      for (const record of dbs) {
        const secondParty = caseName(record).split(' v ')[1];
        assert.ok(JSON.stringify(result.candidates).includes(secondParty), `${secondParty} candidate retained`);
      }
    }
  });

  it('disambiguates DBS by its complete second party and own citation', async () => {
    for (const record of dbs) {
      const named = await lookup(caseName(record));
      matched(named);
      const cited = await lookup(`${caseName(record)} ${record.cite}`);
      matched(cited);
      assert.deepEqual(cited.identity, named.identity);
      assert.ok(cited.evidence_records.every((r) => caseName(r) === caseName(record)));
    }
    unresolved(await lookup(`${caseName(dbs[0])} ${dbs[1].cite}`), ['citation-mismatch']);
  });

  it('retains Long Year quoting source, individual pins and source-bearing overlay notes', async () => {
    assert.equal(longYear.length, 2);
    const result = await lookup('Long Year Development');
    matched(result);
    assert.equal(result.evidence_records.length, longYear.length, 'repeated case records are one identity with two sources');
    for (const original of longYear) {
      const record = result.evidence_records.find((r) => r.where === original.where);
      assert.ok(record, original.where);
      retains(record, original);
      assert.equal(record.verified, 'verified-quoted');
    }
    for (const original of longYear) {
      const aliased = await lookup(`${caseName(original)} ${original.cite}`);
      matched(aliased);
      assert.deepEqual(aliased.identity, result.identity, 'the shared stored citation grounds both names');
    }
  });

  it('retains Edgington quoted and web records separately without giving the web record a pin or source', async () => {
    assert.equal(edgington.length, 2);
    const result = await lookup('Edgington v Fitzmaurice');
    matched(result);
    assert.equal(result.evidence_records.length, 2);
    assert.deepEqual(result.evidence_records.map((r) => r.verified).sort(), ['verified-quoted', 'verified-web']);
    for (const original of edgington) {
      const record = result.evidence_records.find((r) => r.where === original.where);
      assert.ok(record, original.where);
      retains(record, original);
    }
    const representative = edgington.find((r) => r.where === result.authority.where);
    assert.ok(representative, 'representative is a real source record');
    retains(result.authority, representative);
  });

  it('groups the core and persuasive Derry records while preserving the unverified branch', async () => {
    const persuasiveDerry = persuasive('Derry v Peek');
    const result = await lookup(`${caseName(derry)} ${derry.cite}`);
    matched(result);
    assert.equal(result.evidence_records.length, 2);
    const coreEvidence = result.evidence_records.find((r) => r.branch === 'core');
    const persuasiveEvidence = result.evidence_records.find((r) => r.branch === 'persuasive');
    assert.ok(coreEvidence && persuasiveEvidence);
    retains(coreEvidence, derry);
    retains(persuasiveEvidence, persuasiveDerry);
    assert.equal(persuasiveEvidence.verified, 'unverified');
    assert.equal(persuasiveEvidence.hk_status, 'persuasive-only');
    assert.notEqual(result.persuasive_only, true, 'a mixed group retains its core evidence separately');
  });

  it('preserves Barr persuasive-only metadata and structured source without upgrading it', async () => {
    const result = await lookup(`${barr.name} ${barr.cite}`);
    matched(result);
    assert.equal(result.persuasive_only, true);
    assert.equal(result.hk_status, 'persuasive-only');
    assert.equal(result.authority.verified, 'unverified');
    assert.equal(result.evidence_records.length, 1);
    retains(result.authority, barr);
    retains(result.evidence_records[0], barr);
  });
});

describe('coverage and invalid citation requests', () => {
  it('does not invent corporate-party aliases by adding a company suffix to a stored individual', async () => {
    for (const query of ['Derry Ltd v Peek', 'Derry v Peek Ltd (1889) 14 App Cas 337']) {
      unresolved(await lookup(query), ['not-found', 'citation-mismatch']);
    }
  });

  it('recognizes explicitly labelled long pinpoints without hiding an actual extra citation', async () => {
    for (const pin of ['at [1000]', 'para [1000]', 'paragraph [1000]-[1001]']) {
      matched(await lookup(`Hayward v Zurich [2016] UKSC 48 ${pin}`));
    }
    for (const extra of ['at [2099] UKSC 999', 'at[2099]UKSC999', 'para [2099] 2 QB 999']) {
      unresolved(await lookup(`Hayward v Zurich [2016] UKSC 48 ${extra}`), ['unresolved-citation', 'citation-mismatch']);
    }
  });

  it('does not hide an unknown dated citation when a known report reference follows in the same segment', async () => {
    const result = await lookup('Attwood v Small (2099) invented 7 ER 684');
    unresolved(result, ['unresolved-citation']);
    assert.ok(result.unresolved_citations.some((citation) => citation.includes('2099')));
  });

  it('matches exact combined stored titles while distinguishing them from parallel citations of one proceeding', async () => {
    const combined = PERSUASIVE.cases.filter((record) => record.name.includes(';'));
    assert.ok(combined.length > 0);
    for (const record of combined) {
      const result = await lookup(`${record.name} ${record.cite}`);
      matched(result);
      assert.equal(result.identity.identity_kind, 'combined-case-record');
      assert.equal(result.persuasive_only, true);
      assert.equal(result.authority.verified, 'unverified');
      assert.match(result.caution, /does not establish.*parallel citations/);
    }
  });

  it('reports an unknown name as a coverage miss without attaching evidence', async () => {
    const result = await lookup('Synthetic Unstored Claimant v Synthetic Unstored Defendant');
    unresolved(result, ['not-found']);
    assert.ok(result.note || result.reason || result.caution, 'explain the coverage limitation');
  });

  it('reports an unknown neutral citation as unresolved rather than verifying a case', async () => {
    unresolved(await lookup('[2099] UKSC 999999'), ['unresolved-citation']);
  });

  it('rejects missing and whitespace-only citation text in both transports', async () => {
    for (const value of ['', ' ', '\t\n']) unresolved(await lookup(value), ['invalid-input']);
    unresolved((await rest(undefined)).body, ['invalid-input']);
    unresolved((await mcp({})).body, ['invalid-input']);
  });

  it('rejects nonstring MCP citations with an actionable error', async () => {
    for (const citation of [null, 0, false, [], {}, ['Derry v Peek']]) {
      const response = await mcp({ citation });
      unresolved(response.body, ['invalid-input']);
      assert.ok(response.body.error || response.body.errors?.length || response.body.reason);
      assert.equal(response.envelope.result.isError, true);
    }
  });

  it('rejects missing/nonobject MCP argument records without a server exception', async () => {
    for (const args of [undefined, null, 0, false, [], 'Derry v Peek']) {
      const response = await mcp(args);
      unresolved(response.body, ['invalid-input']);
      assert.equal(response.envelope.result.isError, true);
    }
  });
});

// Synthetic records cover ambiguity and source-order cases absent from the
// existing fixtures. They are fresh local objects, never added to exported data.
async function syntheticIndex(records) {
  const { createCitationIndex } = await import('../netlify/functions/citation.mjs');
  return createCitationIndex(records);
}

describe('identity grouping preserves whole source records', () => {
  it('does not promote the first source to a later source verification level', async () => {
    const records = [
      { case: 'Synthetic Alpha v Synthetic Beta', cite: '[2020] EWCA Civ 101', branch: 'core',
        where: 'weak-source', verified: 'verified-web', source: { site: 'synthetic editorial source' }, note: 'Unread source fixture' },
      { case: 'Synthetic Alpha v Synthetic Beta', cite: '[2020] EWCA Civ 101; [2021] QB 202', branch: 'core',
        where: 'strong-source', verified: 'verified-primary', pin: '[12]', src: 'synthetic judgment source', note: 'Read source fixture' },
      { name: 'Synthetic Alpha v Synthetic Beta', cite: '[2021] QB 202', branch: 'persuasive',
        where: 'persuasive-source', verified: 'unverified', source: { site: 'synthetic index' }, hk_status: 'persuasive-only' },
    ];
    const snapshot = structuredClone(records);
    const index = await syntheticIndex(records);
    const result = index.lookup('Synthetic Alpha v Synthetic Beta [2020] EWCA Civ 101; [2021] QB 202');
    matched(result);
    assert.equal(result.authority.where, 'weak-source');
    retains(result.authority, records[0]);
    assert.equal(result.evidence_records.length, records.length);
    for (const original of records) retains(result.evidence_records.find((r) => r.where === original.where), original);
    assert.deepEqual(records, snapshot, 'index construction and lookup do not rewrite stored evidence');
  });

  it('uses whole party tokens and requires both parties, even when one identity is a longer prefix match', async () => {
    const index = await syntheticIndex([
      { case: 'Synthetic North v Synthetic South', cite: '[2020] QB 11', branch: 'core', where: 'north', verified: 'unverified' },
      { case: 'Synthetic Northern v Synthetic Southern', cite: '[2020] QB 12', branch: 'core', where: 'northern', verified: 'unverified' },
    ]);
    const short = index.lookup('Synthetic North v Synthetic South [2020] QB 11');
    matched(short);
    assert.equal(short.authority.where, 'north');
    unresolved(index.lookup('Synthetic North v Synthetic Southern [2020] QB 11'), ['citation-mismatch']);
    unresolved(index.lookup('Synthetic North v Synthetic Southern'), ['not-found', 'citation-mismatch']);
  });

  it('returns one candidate per identity despite repeated evidence at different locations', async () => {
    const index = await syntheticIndex([
      { case: 'Synthetic Bank v First Borrower', cite: '[2020] QB 31', branch: 'core', where: 'one-a', verified: 'verified-web' },
      { case: 'Synthetic Bank v First Borrower', cite: '[2020] QB 31', branch: 'core', where: 'one-b', verified: 'verified-quoted', pin: '5', source: 'synthetic quote' },
      { case: 'Synthetic Bank v Second Borrower', cite: '[2021] QB 32', branch: 'core', where: 'two', verified: 'unverified' },
    ]);
    const ambiguous = index.lookup('Synthetic Bank');
    unresolved(ambiguous, ['ambiguous']);
    assert.equal(ambiguous.candidates.length, 2);
    const first = index.lookup('Synthetic Bank v First Borrower');
    matched(first);
    assert.equal(first.evidence_records.length, 2);
    unresolved(index.lookup('Synthetic Bank v First Borrower [2021] QB 32'), ['citation-mismatch']);
  });

  it('retains grounded names sharing a stored citation as aliases of one identity', async () => {
    const index = await syntheticIndex([
      { case: 'Synthetic Company v Synthetic Person', cite: '[2020] QB 41', branch: 'core', where: 'short-name', verified: 'verified-web' },
      { name: 'Synthetic Company Limited v Synthetic Person Fullname', cite: '[2020] QB 41', branch: 'persuasive', where: 'long-name', verified: 'unverified' },
    ]);
    const short = index.lookup('Synthetic Company v Synthetic Person [2020] QB 41');
    const long = index.lookup('Synthetic Company Limited v Synthetic Person Fullname [2020] QB 41');
    matched(short);
    matched(long);
    assert.deepEqual(short.identity, long.identity);
    assert.equal(short.evidence_records.length, 2);
    assert.deepEqual(short.evidence_records.map((r) => r.verified).sort(), ['unverified', 'verified-web']);
  });
});
