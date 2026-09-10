import { liveCitation } from './live-citation.mjs';
import CORPUS from './_corpus.mjs';
import ELEMENTS from './_elements.mjs';
import MAINT from './_maintenance.mjs';
import SCORED from './_scored.mjs';
import REGISTRY from './_registry.mjs';
import PERSUASIVE from './_persuasive.mjs';
import { createCitationIndex, matchesCaseName } from './citation.mjs';
import { parseAsOf, createHistoricalLibrary } from './historical.mjs';
import { scoreModule as evaluateScoreModule, validateScoreRequest, validationError as scoringValidationError } from './scoring.mjs';

/* ──────────────────────────────────────────────────────────────
   Cold-start indexes
   ────────────────────────────────────────────────────────────── */

const slugOf = (url) => url.replace(/^https?:\/\/[^/]+\//, '').replace(/\/$/, '');
const yearOf = (r) => (r.date || slugOf(r.url)).slice(0, 4);

const POSTS = CORPUS.map((r, i) => ({ ...r, id: i, slug: slugOf(r.url), year: yearOf(r) }));

const norm = (s) => (s || '').toLowerCase().replace(/[^a-z0-9一-鿿]+/g, ' ').trim();
const tokens = (s) => norm(s).split(' ').filter((t) => t.length > 1);

// inverted index: token -> Set(postId)
const INDEX = new Map();
for (const p of POSTS) {
  const bag = [
    p.title, p.summary, (p.topics || []).join(' '),
    (p.cases || []).map((c) => c.name).join(' '),
    (p.statutes || []).join(' '),
  ].join(' ');
  for (const t of new Set(tokens(bag))) {
    if (!INDEX.has(t)) INDEX.set(t, new Set());
    INDEX.get(t).add(p.id);
  }
}

// case index
const CASES = new Map(); // key -> {name, citations:Set, courts:Set, jurisdictions:Set, posts:[id]}
for (const p of POSTS) {
  for (const c of p.cases || []) {
    if (!c.name) continue;
    const key = norm(c.name);
    if (!CASES.has(key)) CASES.set(key, { key, name: c.name, citations: new Set(), courts: new Set(), jurisdictions: new Set(), posts: [] });
    const e = CASES.get(key);
    if (c.citation) e.citations.add(c.citation);
    if (c.court) e.courts.add(c.court);
    if (c.jurisdiction) e.jurisdictions.add(c.jurisdiction);
    e.posts.push(p.id);
  }
}
const caseOut = (e) => ({
  key: e.key, name: e.name,
  citations: [...e.citations], courts: [...e.courts], jurisdictions: [...e.jurisdictions],
  count: e.posts.length, posts: e.posts,
});
const CASE_LIST = [...CASES.values()].map(caseOut).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));

// topic index + co-occurrence
const TOPICS = new Map();
for (const p of POSTS) for (const t of p.topics || []) {
  if (!TOPICS.has(t)) TOPICS.set(t, []);
  TOPICS.get(t).push(p.id);
}
const TOPIC_LIST = [...TOPICS.entries()].map(([t, ids]) => ({ topic: t, count: ids.length })).sort((a, b) => b.count - a.count);

const COOC = new Map();
for (const p of POSTS) {
  const ts = [...new Set(p.topics || [])].sort();
  for (let i = 0; i < ts.length; i++) for (let j = i + 1; j < ts.length; j++) {
    const k = ts[i] + '\u0000' + ts[j];
    COOC.set(k, (COOC.get(k) || 0) + 1);
  }
}

const STATUTES = new Map();
for (const p of POSTS) for (const s of p.statutes || []) {
  if (!STATUTES.has(s)) STATUTES.set(s, []);
  STATUTES.get(s).push(p.id);
}
const STATUTE_LIST = [...STATUTES.entries()].map(([s, ids]) => ({ statute: s, count: ids.length, posts: ids })).sort((a, b) => b.count - a.count);

const counter = (arr) => {
  const m = new Map();
  for (const x of arr) if (x != null) m.set(x, (m.get(x) || 0) + 1);
  return [...m.entries()].sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ key: k, count: v }));
};

const ALL_CASE_ENTRIES = POSTS.flatMap((p) => (p.cases || []).map((c) => ({ ...c, post: p.id })));

const STATS = {
  posts: POSTS.length,
  byType: counter(POSTS.map((p) => p.type)),
  byYear: counter(POSTS.map((p) => p.year)).sort((a, b) => a.key.localeCompare(b.key)),
  caseMentions: ALL_CASE_ENTRIES.length,
  uniqueCases: CASE_LIST.length,
  byJurisdiction: counter(ALL_CASE_ENTRIES.map((c) => c.jurisdiction)),
  byCourt: counter(ALL_CASE_ENTRIES.map((c) => c.court)),
  topics: TOPIC_LIST.length,
  statutes: STATUTE_LIST.length,
  elementSubTests: ELEMENTS.elements.reduce((n, e) => n + e.sub_tests.length, 0) + ELEMENTS.defences.length,
  timelines: Object.keys(ELEMENTS.timelines).length,
  timelineEvents: Object.values(ELEMENTS.timelines).reduce((n, t) => n + t.events.length, 0),
  jurisdictionCases: Object.values(ELEMENTS.jurisdictions).reduce((n, j) => n + (j.cases ? j.cases.length : 0), 0),
  corpusSource: 'hklandlaw.wordpress.com',
  datasetVersion: ELEMENTS.version,
  persuasiveCases: PERSUASIVE.stats.cases,
  persuasiveEdges: PERSUASIVE.stats.edges,
};

/* ──────────────────────────────────────────────────────────────
   Query helpers
   ────────────────────────────────────────────────────────────── */

function searchPosts(params) {
  const q = params.get('q') || '';
  const topic = params.get('topic');
  const year = params.get('year');
  const court = params.get('court');
  const juris = params.get('juris');
  const type = params.get('type');
  const caseKey = params.get('case');
  const statute = params.get('statute');
  const limit = Math.min(+(params.get('limit') || 30), 200);
  const offset = +(params.get('offset') || 0);

  let scored;
  if (q.trim()) {
    const qt = tokens(q);
    const hits = new Map();
    for (const t of qt) {
      // prefix matching so "estopp" finds "estoppel"
      for (const [tok, ids] of INDEX) {
        if (tok === t || tok.startsWith(t)) {
          const w = tok === t ? 2 : 1;
          for (const id of ids) hits.set(id, (hits.get(id) || 0) + w);
        }
      }
    }
    scored = [...hits.entries()].map(([id, s]) => {
      const p = POSTS[id];
      const titleBonus = norm(p.title).includes(norm(q)) ? 6 : 0;
      return { p, score: s + titleBonus };
    });
  } else {
    scored = POSTS.map((p) => ({ p, score: 0 }));
  }

  let out = scored.filter(({ p }) =>
    (!topic || (p.topics || []).includes(topic)) &&
    (!year || p.year === year) &&
    (!type || p.type === type) &&
    (!court || (p.cases || []).some((c) => c.court === court)) &&
    (!juris || (p.cases || []).some((c) => c.jurisdiction === juris)) &&
    (!caseKey || (p.cases || []).some((c) => norm(c.name) === caseKey)) &&
    (!statute || (p.statutes || []).includes(statute))
  );

  out.sort((a, b) => b.score - a.score || (b.p.date || '').localeCompare(a.p.date || ''));
  const total = out.length;
  return {
    total,
    limit, offset,
    facets: {
      topics: counter(out.flatMap(({ p }) => p.topics || [])).slice(0, 24),
      years: counter(out.map(({ p }) => p.year)).sort((a, b) => b.key.localeCompare(a.key)),
      courts: counter(out.flatMap(({ p }) => (p.cases || []).map((c) => c.court))),
      jurisdictions: counter(out.flatMap(({ p }) => (p.cases || []).map((c) => c.jurisdiction))),
      types: counter(out.map(({ p }) => p.type)),
    },
    results: out.slice(offset, offset + limit).map(({ p, score }) => ({
      id: p.id, slug: p.slug, url: p.url, title: p.title, date: p.date, type: p.type,
      topics: p.topics, summary: p.summary, cases: p.cases, statutes: p.statutes, score,
    })),
  };
}

function timelineAsOf(id, asOf, jFilter) {
  const t = ELEMENTS.timelines[id] || MODULE_TIMELINES[id];
  if (!t) return null;
  const cutoff = asOf ? +asOf : 9999;
  const events = t.events
    .filter((e) => !jFilter || jFilter.includes(e.j))
    .slice()
    .sort((a, b) => a.y - b.y);
  // Standing rule per jurisdiction: the HIGHEST court's in-force statement,
  // most recent among equals. Recency alone would let a later first-instance
  // decision override the Court of Appeal, which is not how precedent works.
  const standing = {}, latest = {}, conflicts = {};
  for (const e of events) {
    if (e.y > cutoff) continue;
    latest[e.j] = e;
    const cur = standing[e.j];
    const r = e.court_rank ?? 2, cr = cur ? (cur.court_rank ?? 2) : -1;
    if (!cur || r > cr || (r === cr && e.y >= cur.y)) standing[e.j] = e;
  }
  for (const [j, s] of Object.entries(standing)) {
    const later = events.filter((e) => e.j === j && e.y <= cutoff && e.y > s.y && (e.court_rank ?? 2) < (s.court_rank ?? 2)
      && Math.sign(e.f) !== Math.sign(s.f));
    if (later.length) conflicts[j] = later.map((e) => ({ year: e.y, case: e.case, court: e.court, treatment: e.treat, effect: e.eff,
      note: `${e.court} (${e.y}) points the other way on this sub-test and post-dates the governing ${s.court} statement (${s.y}). The higher court outranks it, but the two may be reconcilable — check whether they address the same question before treating either as displaced.` }));
  }
  const earlierHigher = {};
  for (const [j, l] of Object.entries(latest)) {
    const s = standing[j];
    if (s && l !== s) earlierHigher[j] = { latest_event: { year: l.y, case: l.case, court: l.court }, governing: { year: s.y, case: s.case, court: s.court },
      note: `The most recent decision is not the highest: ${s.court} (${s.y}) outranks ${l.court} (${l.y}). Cite the governing statement for the binding rule and the latest for how it is currently being applied.` };
  }
  const row = (e) => ({ jurisdiction: e.j, since: e.y, case: e.case, court: e.court, court_rank: e.court_rank, treatment: e.treat, effect: e.eff, favour: e.f });
  return {
    id, title: t.title, title_en: t.title_en, sub_test: t.sub_test, note: t.note,
    as_of: asOf ? +asOf : null,
    resolution: 'standing_rules = highest court rank among in-force events, then most recent (the binding statement). latest_rules = most recent in-force event regardless of court (current application). Where they differ, latest_is_not_governing says so.',
    events: events.map((e) => ({ ...e, in_force_at_as_of: e.y <= cutoff })),
    standing_rules: Object.values(standing).map(row),
    latest_rules: Object.values(latest).map(row),
    subordinate_conflicts: Object.keys(conflicts).length ? conflicts : undefined,
    latest_is_not_governing: Object.keys(earlierHigher).length ? earlierHigher : undefined,
    jurisdictions_with_no_authority_at_as_of: [...new Set(events.map((e) => e.j))].filter((j) => !standing[j]),
  };
}

const LEVEL_DESC = {
  'verified-primary': 'the judgment text was read; proposition cited to a paragraph or page',
  'verified-quoted': 'the operative passage was read verbatim in a later judgment that pin-cites it; the report itself unseen',
  'verified-web': 'matched against accessible sources; NOT read and NOT pin-cited — treat the characterisation as unaudited',
  'unverified': 'drafted from doctrine, not checked',
};
const LEVEL_RANK = { 'verified-primary': 3, 'verified-quoted': 2, 'verified-web': 1, 'unverified': 0 };

function verificationSummary(auths) {
  const counts = {};
  for (const a of auths) counts[a.verified || 'unverified'] = (counts[a.verified || 'unverified'] || 0) + 1;
  const weakest = auths.length ? auths.reduce((m, a) => LEVEL_RANK[a.verified] < LEVEL_RANK[m] ? a.verified : m, 'verified-primary') : null;
  return { counts, weakest_level: weakest, levels: LEVEL_DESC,
    caution: weakest && LEVEL_RANK[weakest] <= 1
      ? 'At least one authority here is at verified-web: its stated proposition has not been checked against the judgment. Do not cite it as read.' : undefined };
}

// Every authority in the library, flattened, for citation checking.
const AUTH_INDEX = (() => {
  const out = [];
  const yearOf = (a) => a.year || +((String(a.cite || '').match(/[\[(](\d{4})[\])]/) || [])[1]) || null;
  const push = (a, where) => out.push({ ...a, case: a.case || a.name, cite: a.cite, court: a.court, pin: a.pin || null,
    year: yearOf(a), verified: a.verified || 'unverified', note: a.note, where, branch: 'core' });
  for (const el of ELEMENTS.elements) for (const st of el.sub_tests) for (const a of st.auth || []) push(a, st.id);
  for (const d of ELEMENTS.defences) for (const a of d.auth || []) push(a, d.id);
  for (const [j, jur] of Object.entries(ELEMENTS.jurisdictions)) for (const c of jur.cases || []) push(c, `${j} overlay`);
  return out;
})();

// Identity and per-record provenance are independent of proposition verification.
const CITATIONS = createCitationIndex([
  ...AUTH_INDEX,
  ...PERSUASIVE.cases.map((record) => ({ ...record, case: record.name, branch: 'persuasive', where: `persuasive/${record.slug}` })),
]);

function verifyCitation(args) {
  if (!args || typeof args !== 'object' || Array.isArray(args)) return CITATIONS.lookup(undefined);
  const result = CITATIONS.lookup(args.citation);
  if (!result.found) return result;
  const authority = result.authority;
  const anachronistic = args.as_of && authority.year && authority.year > +args.as_of;
  return { ...result,
    level_meaning: result.persuasive_only ? 'Unverified persuasive index evidence; identity only, not governing doctrine.' : LEVEL_DESC[authority.verified],
    anachronistic: anachronistic || undefined,
    anachronism_warning: anachronistic ? `Decided in ${authority.year}, after your as_of date of ${args.as_of}. It did not exist when the advice is dated; do not cite it as the law at that time.` : undefined,
  };
}

function lookupCase(name, fullPosts = false) {
  const identity = CITATIONS.lookup(name);
  const expand = (hit) => ({ ...hit, posts: hit.posts.map((id) => fullPosts ? POSTS[id]
    : ({ url: POSTS[id].url, title: POSTS[id].title, date: POSTS[id].date, summary: POSTS[id].summary })) });
  if (identity.found) {
    const corpus = CASE_LIST.find((record) => identity.identity.names.some((alias) => norm(alias) === record.key));
    return { ...(corpus ? expand(corpus) : {}), ...identity,
      ...(identity.persuasive_only ? { incoming_treatment: PERSUASIVE.edges.filter((edge) => edge.to_slug === identity.authority.slug) } : {}),
    };
  }
  if (identity.status !== 'not-found') return identity;
  const candidates = CASE_LIST.filter((record) => matchesCaseName(name, record.name));
  if (candidates.length > 1) return { found: false, status: 'ambiguous', proposition_check: 'not-performed',
    candidates: candidates.map((record) => ({ case: record.name, citations: record.citations, branches: ['corpus'] })) };
  if (!candidates.length) return { ...identity, error: 'no such case in corpus or authority indexes', suggestions: [] };
  return { ...expand(candidates[0]), found: true, status: 'matched', proposition_check: 'not-performed', other_matches: [] };
}

// Which jurisdiction overlay applies. Keyword resolution over the library's
// own jurisdiction records, so it cannot return a jurisdiction the library
// does not carry. Fixes the Experiment 1 defect of injecting without a
// jurisdiction-resolution stage.
const JUR_KEYS = {
  HK: ['hong kong', 'hksar', 'hkiac', 'cap. 284', 'cap 284', 'hkcfi', 'hkca', 'hkcfa', 'court of first instance'],
  SG: ['singapore', 'siac', 'sgca', 'sghc', 'application of english law act'],
  AU: ['australia', 'australian', 'new south wales', 'victoria', 'queensland', 'acl', 'competition and consumer act', 'hca'],
  EN: ['england', 'english law', 'england and wales', 'ewca', 'ewhc', 'uksc', 'ukhl', 'lcia', 'london', 'misrepresentation act 1967'],
};
function resolveJurisdiction(text) {
  const t = norm(text || '');
  const scores = {};
  for (const [j, keys] of Object.entries(JUR_KEYS)) for (const k of keys) if (t.includes(k)) scores[j] = (scores[j] || 0) + (k.length > 6 ? 2 : 1);
  const ranked = Object.entries(scores).sort((a, b) => b[1] - a[1]);
  if (!ranked.length) return { resolved: null, candidates: [], warning: 'No jurisdiction signal found. Do not assume England by default — ask which law governs and where the forum sits.' };
  const [j, score] = ranked[0];
  const tie = ranked.length > 1 && ranked[1][1] === score;
  const jur = ELEMENTS.jurisdictions[j];
  return { resolved: tie ? null : j, candidates: ranked.map(([k, v]) => ({ jurisdiction: k, score: v })),
    warning: tie ? 'Ambiguous: more than one jurisdiction signalled equally. Governing law and seat may differ — resolve both before injecting doctrine.' : undefined,
    overlay: tie ? undefined : { name: jur.name, regime: jur.regime, apex: jur.apex, authority_rule: jur.authority_rule,
      statutes: (jur.statutes || []).map((x) => ({ ref: x.ref, verified: x.verified })), gaps: jur.gaps || [] } };
}

// A pleading checklist: what must be pleaded, on what authority, at what
// verification level, and where the library has nothing. For a lawyer drafting
// a statement of claim this is the output that matters.
function pleadingChecklist(jurisdiction, variant, asOf) {
  const j = jurisdiction && ELEMENTS.jurisdictions[jurisdiction] ? jurisdiction : null;
  const rows = [];
  for (const el of ELEMENTS.elements) {
    for (const st of el.sub_tests) {
      if (st.variant && variant && st.variant !== variant) continue;
      const auths = (st.auth || []).map((a) => ({ case: a.case, cite: a.cite, court: a.court, pin: a.pin || null, verified: a.verified, note: a.note }));
      const jc = j ? (ELEMENTS.jurisdictions[j].cases || []) : [];
      const local = jc.filter((c) => (c.maps_to || []).includes(st.id));
      const related = jc.filter((c) => !(c.maps_to || []).includes(st.id) && (c.maps_to || []).includes(el.id));
      const drift = st.drift ? timelineAsOf(st.drift, asOf, j ? [j] : null) : null;
      const standing = drift ? drift.standing_rules.find((r) => !j || r.jurisdiction === j) : null;
      rows.push({
        element: el.id, element_en: el.en, sub_test: st.id, sub_test_en: st.en,
        litigation_postures: st.litigation_postures,
        litigation_track: st.litigation_track,
        litigation_position_source: st.litigation_position_source,
        plead: st.test,
        statute: st.statute_by_jurisdiction && j ? st.statute_by_jurisdiction[j] : undefined,
        backbone_authority: auths,
        local_authority: local.map((c) => ({ case: c.name, cite: c.cite, court: c.court, year: c.year, pin: c.pin || null, verified: c.verified, holding: c.holding })),
        related_local_authority: related.length ? related.map((c) => ({ case: c.name, cite: c.cite, year: c.year, verified: c.verified, note: `mapped to ${el.id} generally, not to ${st.id}` })) : undefined,
        standing_rule_as_of: standing ? { since: standing.since, case: standing.case, effect: standing.effect } : undefined,
        local_authority_gap: j && !local.length ? `No ${j} authority on file for ${st.id}. Do not infer the ${j} position from the English backbone; research it.` : undefined,
        verification: verificationSummary([...auths, ...local]),
      });
    }
  }
  const defences = ELEMENTS.defences.map((d) => ({ id: d.id, en: d.en,
    litigation_postures: d.litigation_postures,
    litigation_track: d.litigation_track,
    litigation_position_source: d.litigation_position_source,
    test: d.test,
    authority: (d.auth || []).map((a) => ({ case: a.case, cite: a.cite, pin: a.pin || null, verified: a.verified })) }));
  return { claim: ELEMENTS.claim, jurisdiction: j, variant: variant || 'any', as_of: asOf ? +asOf : null,
    authority_rule: j ? ELEMENTS.jurisdictions[j].authority_rule : undefined,
    elements: rows, defences_to_anticipate: defences,
    jurisdiction_gaps: j ? ELEMENTS.jurisdictions[j].gaps || [] : undefined,
    note: 'Every authority carries a verification level; verified-web means NOT read. A local_authority_gap is a coverage gap, not evidence that no authority exists.' };
}

function findSubTest(id) {
  for (const el of ELEMENTS.elements) {
    if (el.id === id) return { kind: 'element', element: el };
    for (const st of el.sub_tests) if (st.id === id) return { kind: 'sub_test', element: el, sub_test: st };
  }
  for (const d of ELEMENTS.defences) if (d.id === id) return { kind: 'defence', defence: d };
  return null;
}

const TAXONOMY_MODULE_REFS = {
  remoteness: { module_id: 'CONTRACT', stage_ids: ['CT-3'], coverage: 'partial' },
  penalty: { module_id: 'PENALTY', coverage: 'logic-full' },
  'negligent-misstatement': { module_id: 'NMS', coverage: 'logic-full' },
  'proprietary-estoppel': { module_id: 'PE', coverage: 'logic-full' },
  'constructive-trust': { module_id: 'CICT', coverage: 'logic-full' },
  veil: { module_id: 'VEIL', coverage: 'logic-full' },
  privilege: { module_id: 'LPP', coverage: 'logic-full' },
  discovery: { module_id: 'DISC', coverage: 'logic-full' },
  'adverse-possession': { module_id: 'AP', coverage: 'logic-full' },
  easements: { module_id: 'EASE', coverage: 'partial' },
  dmc: { module_id: 'DMC', coverage: 'logic-full' },
  'ny-convention': { module_id: 'NYC', coverage: 'logic-full' },
  'arbitrator-challenge': { module_id: 'ARBCH', coverage: 'logic-full' },
};

const TAXONOMY_CLAIM_OVERRIDES = {
  remoteness: { legal_kind: 'damages-limitation' },
};

const TAXONOMY_MODULE_ADDITIONS = [
  { area: 'Contract', id: 'breach-of-contract', zh: '违约', en: 'Breach of contract', module_id: 'CONTRACT' },
  { area: 'Contract', id: 'illegality', zh: '违法性抗辩', en: 'Illegality defence', module_id: 'ILLEG' },
  { area: 'Contract', id: 'exemption-reasonableness', zh: '免责条款合理性', en: 'Exemption-clause reasonableness', module_id: 'CECO' },
  { area: 'Tort', id: 'private-nuisance', zh: '私人妨害', en: 'Private nuisance', module_id: 'NUIS' },
  { area: 'Equity', id: 'resulting-trust', zh: '归复信托与预付推定', en: 'Resulting trust / advancement', module_id: 'RT' },
  { area: 'Equity', id: 'undue-influence', zh: '不当影响', en: 'Undue influence', module_id: 'UI' },
  { area: 'Land', id: 'lease-or-licence', zh: '租赁抑或许可', en: 'Lease or licence', module_id: 'LEASE' },
  { area: 'Jurisdiction', area_zh: '管辖', id: 'hong-kong-jurisdiction', zh: '香港法院管辖权', en: 'Hong Kong civil jurisdiction', module_id: 'HKJUR' },
];

const TAXONOMY_JURISDICTIONS = [
  { id: 'HK', zh: '香港', en: 'Hong Kong SAR' },
  { id: 'EN', zh: '英格兰及威尔士', en: 'England & Wales' },
  { id: 'SG', zh: '新加坡', en: 'Singapore' },
  { id: 'AU', zh: '澳大利亚', en: 'Australia' },
];

function taxonomyJurisdictions(value) {
  const supplied = new Set(String(value || '').toUpperCase().split(/[^A-Z]+/).filter(Boolean));
  return TAXONOMY_JURISDICTIONS.map((jurisdiction) => jurisdiction.id).filter((id) => supplied.has(id));
}

const TAXONOMY_EXPLICIT_PROFILES = {
  deceit: { litigation_postures: ['spear'], litigation_track: 'merits', primary_posture: 'spear', legal_kind: 'cause-of-action' },
  rescission: { litigation_postures: ['spear'], litigation_track: 'merits', primary_posture: 'spear', legal_kind: 'remedy' },
  'negligent-misstatement': { litigation_postures: ['spear'], litigation_track: 'merits', primary_posture: 'spear', legal_kind: 'cause-of-action', jurisdictions: ['EN', 'HK'], jurisdiction_scope_source: 'editorial-scope' },
  penalty: { litigation_postures: ['shield'], litigation_track: 'merits', primary_posture: 'shield', legal_kind: 'defence', jurisdictions: ['EN', 'HK'], jurisdiction_scope_source: 'editorial-scope' },
  privilege: { litigation_postures: ['shield'], litigation_track: 'procedure', primary_posture: 'shield', legal_kind: 'procedural-protection', jurisdictions: ['HK', 'EN'], jurisdiction_scope_source: 'editorial-scope' },
  discovery: { litigation_postures: ['spear', 'shield'], litigation_track: 'procedure', primary_posture: null, legal_kind: 'procedural-doctrine', jurisdictions: ['HK', 'EN'], jurisdiction_scope_source: 'editorial-scope' },
  easements: { litigation_postures: ['spear', 'shield'], litigation_track: 'merits', primary_posture: null, legal_kind: 'property-right', jurisdictions: ['HK', 'EN'], jurisdiction_scope_source: 'editorial-scope' },
  dmc: { litigation_postures: ['spear', 'shield'], litigation_track: 'merits', primary_posture: null, legal_kind: 'claim-family', jurisdictions: ['HK'], jurisdiction_scope_source: 'hklandlaw-corpus' },
};

function taxonomyLitigationPosition(module, reference) {
  if (!reference.stage_ids) return {
    litigation_postures: module.litigation_postures,
    litigation_track: module.litigation_track,
    primary_posture: module.primary_posture,
    litigation_note: module.litigation_note || module.role_note,
    court_own_motion_summary: module.court_own_motion_summary || { stage_count: 0, stage_ids: [] },
  };

  if (!Array.isArray(reference.stage_ids) || !reference.stage_ids.length) {
    throw new Error('taxonomy stage reference must contain at least one stage for ' + module.id);
  }
  const byStage = new Map(module.stages.map((stage) => [stage.id, stage]));
  const stages = reference.stage_ids.map((stageId) => {
    const stage = byStage.get(stageId);
    if (!stage) throw new Error('taxonomy references unknown stage ' + module.id + '/' + stageId);
    return stage;
  });
  const tracks = [...new Set(stages.map((stage) => stage.litigation_track))];
  if (tracks.length !== 1) throw new Error('taxonomy stage reference spans matter tracks for ' + module.id);
  const primaryPostures = [...new Set(stages.map((stage) => stage.primary_posture ?? null))];
  const ownMotionStageIds = stages.filter((stage) => stage.court_own_motion).map((stage) => stage.id);
  return {
    litigation_postures: [...new Set(stages.flatMap((stage) => stage.litigation_postures || []))],
    litigation_track: tracks[0],
    primary_posture: primaryPostures.length === 1 ? primaryPostures[0] : null,
    litigation_note: stages.length === 1
      ? stages[0].litigation_note
      : stages.map((stage) => stage.id + '：' + stage.litigation_note).join('；'),
    court_own_motion_summary: { stage_count: ownMotionStageIds.length, stage_ids: ownMotionStageIds },
  };
}

function taxonomyReferencedStages(module, reference) {
  if (!reference.stage_ids) return module.stages;
  const wanted = new Set(reference.stage_ids);
  return module.stages.filter((stage) => wanted.has(stage.id));
}

function taxonomyElementCoverage(module, reference) {
  const stages = taxonomyReferencedStages(module, reference);
  return stages.some((stage) => stage.doctrinal_role === 'claim-elements')
    ? 'logic-stages' : 'not-applicable';
}

function taxonomy() {
  const result = {
    version: REGISTRY.version,
    component_versions: {
      elements: ELEMENTS.version,
      registry: REGISTRY.version,
      scored: SCORED.version,
    },
    areas: [
      { zh: '合同法', en: 'Contract', claims: [
        { id: 'misrepresentation', zh: '失实陈述', en: 'Misrepresentation', status: 'full',
          elements: ELEMENTS.elements.map((e) => ({ id: e.id, zh: e.zh, en: e.en,
            sub_tests: e.sub_tests.map((s) => ({ id: s.id, zh: s.zh, en: s.en, drift: s.drift || null })) })),
          defences: ELEMENTS.defences.map((d) => ({ id: d.id, zh: d.zh, en: d.en, drift: d.drift || null })) },
        { id: 'remoteness', zh: '损害远隔性', en: 'Remoteness of damage', status: 'planned',
          note: 'Hadley (1854) → Victoria Laundry → Heron II → The Achilleas [2008] → John Grimes / Wellesley — the standard oscillating curve.',
          lab: 'LAB rubric: 77 criteria / 33 tasks' },
        { id: 'penalty', zh: '违约金条款', en: 'Penalty clauses', status: 'planned',
          note: 'Dunlop (1915) genuine pre-estimate → Cavendish / ParkingEye [2015] legitimate interest; HK adoption line to verify.',
          lab: 'LAB rubric: 3 criteria / 2 tasks' } ] },
      { zh: '侵权法', en: 'Tort', claims: [
        { id: 'deceit', zh: '欺诈之诉', en: 'Deceit', status: 'xref', xref: 'misrepresentation#E4a',
          element_refs: [{ id: 'E1' }, { id: 'E2' }, { id: 'E3' }, { id: 'E4', sub_tests: ['E4a'] }, { id: 'E5', sub_tests: ['E5b'] }],
          defence_refs: ['D2'],
          note: 'Five elements per Derry v Peek — see Misrepresentation E4a. Australia retains the same backbone via Magill v Magill [2006] HCA 51.' },
        { id: 'negligent-misstatement', zh: '过失性失实陈述', en: 'Negligent misstatement', status: 'planned',
          note: 'Hedley Byrne [1964] assumption of responsibility (Caparo three-stage → Robinson swing-back).' } ] },
      { zh: '衡平法', en: 'Equity', claims: [
        { id: 'rescission', zh: '撤销', en: 'Rescission', status: 'xref', xref: 'misrepresentation#E5a',
          element_refs: [{ id: 'E5', sub_tests: ['E5a'] }],
          note: 'As a misrepresentation remedy see E5a (bars: affirmation / lapse / restitution impossible / third-party rights).' },
        { id: 'proprietary-estoppel', zh: '不动产禁反言', en: 'Proprietary estoppel', status: 'corpus-only',
          note: 'Not yet modelled as elements, but the corpus is dense here — assurance / reliance / detriment / unconscionability.',
          corpusTopics: ['proprietary-estoppel', 'detrimental-reliance', 'assurance'] },
        { id: 'constructive-trust', zh: '共同意图推定信托', en: 'Common intention constructive trust', status: 'corpus-only',
          corpusTopics: ['common-intention-constructive-trust', 'constructive-trust', 'resulting-trust', 'family-home'] } ] },
      { zh: '公司法', en: 'Company', claims: [
        { id: 'veil', zh: '揭开公司面纱', en: 'Piercing the corporate veil', status: 'planned',
          note: 'Salomon (1897) → DHN (1976) → Woolfson (1978) → Adams v Cape (1990) → Prest [2013] concealment/evasion.',
          lab: 'LAB rubric: 36 criteria / 7 tasks' } ] },
      { zh: '程序与证据', en: 'Procedure & Evidence', claims: [
        { id: 'privilege', zh: '法律专业特权', en: 'Legal professional privilege', status: 'planned',
          note: 'Legal advice + litigation privilege + without prejudice. HK/EN true fork: Citic Pacific [2015] HKCA declined Three Rivers (No 5); ENRC [2018] could not overturn it in England.',
          lab: 'LAB rubric: 366 criteria / 42 tasks — highest demand' },
        { id: 'discovery', zh: '文件披露范围', en: 'Discovery scope', status: 'planned',
          note: 'HK retains Peruvian Guano (1873) train-of-inquiry breadth; England narrowed via CPR 1999 → PD57AD.',
          lab: 'LAB rubric: 119 criteria / 32 tasks' } ] },
      { zh: '土地法', en: 'Land', claims: [
        { id: 'adverse-possession', zh: '逆权侵占', en: 'Adverse possession', status: 'corpus-only',
          corpusTopics: ['adverse-possession', 'limitation'] },
        { id: 'easements', zh: '地役权', en: 'Easements', status: 'corpus-only',
          corpusTopics: ['easements', 'prescription', 'right-of-way'] },
        { id: 'dmc', zh: '公契与大厦管理', en: 'DMC & building management', status: 'corpus-only',
          corpusTopics: ['deed-of-mutual-covenant', 'building-management', 'common-parts'] } ] },
      { zh: '仲裁', en: 'Arbitration', claims: [
        { id: 'ny-convention', zh: '裁决执行抗辩', en: 'Award enforcement (NY Convention)', status: 'planned',
          note: 'Art V closed list — the most naturally machine-readable element table; HK Cap 609 + Hebei v Polytek (1999) CFA public policy standard.',
          lab: 'LAB rubric: 32 criteria / 5 tasks' },
        { id: 'arbitrator-challenge', zh: '仲裁员回避与披露', en: 'Arbitrator challenge', status: 'planned',
          note: 'Model Law art 12 justifiable doubts + IBA Guidelines + Halliburton v Chubb [2020] UKSC.',
          lab: 'LAB rubric: 33 criteria / 8 tasks' } ] },
    ],
  };

  const modules = [...SCORED.modules, ...REGISTRY.modules];
  const byModule = new Map(modules.map((module) => [module.id, module]));
  for (const addition of TAXONOMY_MODULE_ADDITIONS) {
    const module = byModule.get(addition.module_id);
    if (!module) throw new Error('taxonomy addition references unknown module ' + addition.module_id);
    let area = result.areas.find((item) => item.en === addition.area);
    if (!area) {
      area = { zh: addition.area_zh, en: addition.area, claims: [] };
      result.areas.push(area);
    }
    area.claims.push({ id: addition.id, zh: addition.zh, en: addition.en,
      status: module.corpus_hits > 0 ? 'corpus-only' : 'planned',
      logic_status: 'full', model_ref: { module_id: addition.module_id, coverage: 'logic-full' } });
  }

  for (const claim of result.areas.flatMap((area) => area.claims)) {
    if (claim.id === 'misrepresentation') {
      Object.assign(claim, ELEMENTS.litigation_profile || {});
      claim.jurisdictions = taxonomyJurisdictions(Object.keys(ELEMENTS.jurisdictions || {}).join('/'));
      claim.jurisdiction_scope_source = 'elements-dataset';
      claim.logic_status = 'full';
      claim.coverage = { analysis_structure: 'full', elements: 'full', logic: 'conjunctive', corpus: 'partial', jurisdiction_overlays: 'full' };
      continue;
    }
    const reference = claim.model_ref || TAXONOMY_MODULE_REFS[claim.id];
    if (reference) {
      const module = byModule.get(reference.module_id);
      if (!module) throw new Error('taxonomy references unknown module ' + reference.module_id);
      const position = taxonomyLitigationPosition(module, reference);
      claim.model_ref = reference;
      claim.logic_status = reference.coverage === 'partial' ? 'partial' : 'full';
      claim.litigation_postures = position.litigation_postures;
      claim.litigation_track = position.litigation_track;
      claim.primary_posture = position.primary_posture;
      claim.legal_kind = module.legal_kind;
      claim.role_confidence = module.role_confidence;
      claim.court_own_motion_summary = position.court_own_motion_summary;
      claim.litigation_note = position.litigation_note;
      claim.role_note = position.litigation_note;
      claim.jurisdictions = taxonomyJurisdictions(module.jurisdiction);
      claim.jurisdiction_scope_source = 'logic-module';
      claim.note = reference.coverage === 'partial'
        ? (reference.stage_ids?.length
          ? '已作为法律测试模块 '+module.id+' 的 '+reference.stage_ids.join('、')+' 阶段建模；尚不是独立完整要件数据集。'
          : module.note)
        : module.note;
      if (TAXONOMY_CLAIM_OVERRIDES[claim.id]) Object.assign(claim, TAXONOMY_CLAIM_OVERRIDES[claim.id]);
      claim.coverage = { analysis_structure: reference.coverage === 'partial' ? 'partial' : 'full', elements: taxonomyElementCoverage(module, reference),
        logic: reference.coverage === 'partial' ? 'partial' : 'full',
        corpus: module.corpus_hits > 0 ? 'indexed' : 'none', jurisdiction_overlays: 'partial' };
      continue;
    }
    if (TAXONOMY_EXPLICIT_PROFILES[claim.id]) Object.assign(claim, TAXONOMY_EXPLICIT_PROFILES[claim.id]);
    claim.logic_status = claim.xref ? 'xref' : 'none';
  }

  const allClaims = result.areas.flatMap((area) => area.claims);
  const claimsById = new Map(allClaims.map((claim) => [claim.id, claim]));
  for (const claim of allClaims) {
    if (Array.isArray(claim.jurisdictions)) continue;
    const crossReference = claim.xref && claimsById.get(claim.xref.split('#')[0]);
    if (crossReference?.jurisdictions?.length) {
      claim.jurisdictions = [...crossReference.jurisdictions];
      claim.jurisdiction_scope_source = 'cross-reference';
    } else if (claim.corpusTopics?.length || claim.status === 'corpus-only') {
      claim.jurisdictions = ['HK'];
      claim.jurisdiction_scope_source = 'hklandlaw-corpus';
    } else {
      claim.jurisdictions = [];
      claim.jurisdiction_scope_source = 'unclassified';
    }
  }

  // Keep the claim catalogue structurally uniform. Consumers can compose one
  // cause-centred view without guessing whether a missing property means
  // "not modelled" or merely a different claim shape.
  for (const claim of result.areas.flatMap((area) => area.claims)) {
    claim.elements = Array.isArray(claim.elements) ? claim.elements : [];
    claim.defences = Array.isArray(claim.defences) ? claim.defences : [];
    claim.model_ref = claim.model_ref || null;
    claim.jurisdictions = [...new Set(claim.jurisdictions || [])]
      .filter((id) => TAXONOMY_JURISDICTIONS.some((jurisdiction) => jurisdiction.id === id));
    claim.coverage = {
      analysis_structure: claim.xref ? 'xref' : 'none',
      elements: claim.elements.length ? 'full' : claim.xref ? 'xref' : 'none',
      logic: claim.xref ? 'xref' : claim.logic_status || 'none',
      corpus: claim.corpusTopics?.length || claim.status === 'corpus-only' ? 'indexed' : 'none',
      jurisdiction_overlays: claim.xref ? 'xref' : 'none',
      ...(claim.coverage || {}),
    };
  }

  result.posture_catalog = REGISTRY.posture_catalog || SCORED.posture_catalog || {};
  result.track_catalog = REGISTRY.track_catalog || SCORED.track_catalog || {};
  result.doctrinal_role_catalog = REGISTRY.doctrinal_role_catalog || SCORED.doctrinal_role_catalog || {};
  result.jurisdiction_catalog = TAXONOMY_JURISDICTIONS.map((jurisdiction) => {
    const coveredAreas = result.areas.filter((area) =>
      area.claims.some((claim) => claim.jurisdictions.includes(jurisdiction.id)));
    return {
      ...jurisdiction,
      claim_count: coveredAreas.reduce((count, area) => count
        + area.claims.filter((claim) => claim.jurisdictions.includes(jurisdiction.id)).length, 0),
      area_count: coveredAreas.length,
    };
  });
  result.litigation_position_note = '诉讼姿态（矛／盾）可多选；程序与管辖属于事项轨道。它们描述测试通常如何进入争议，不是额外法律要件。';
  result.modelled_modules = modules.length;
  result.legal_test_modules = modules.map((module) => ({
    id: module.id, zh: module.zh, en: module.en,
    litigation_postures: module.litigation_postures,
    litigation_track: module.litigation_track,
    court_own_motion_summary: module.court_own_motion_summary || { stage_count: 0, stage_ids: [] },
  }));
  return result;
}

/* ──────────────────────────────────────────────────────────────
   MCP endpoint (JSON-RPC 2.0 subset)
   ────────────────────────────────────────────────────────────── */


/* ──────────────────────────────────────────────────────────────
   Maintenance layer — drift ledger, staleness model, review queue
   ────────────────────────────────────────────────────────────── */

const M_NODES = MAINT.nodes;
const ATTESTED = M_NODES.filter((n) => n.work_type === 'staleness');
const GAPS = M_NODES.filter((n) => n.work_type === 'coverage-gap');
const ANNUAL_RATE = ATTESTED.reduce((a, n) => a + n.rate_per_year, 0);

const maintOverview = () => ({
  generated: MAINT.generated,
  dataset_version: MAINT.dataset_version,
  claim_families_covered: 1,
  nodes: { total: M_NODES.length, attested: ATTESTED.length, coverage_gaps: GAPS.length },
  annual_drift_events: {
    this_dataset: +ANNUAL_RATE.toFixed(2),
    per_claim_family: +ANNUAL_RATE.toFixed(2),
    extrapolated_15_claim_library: Math.round(ANNUAL_RATE * 15),
    note: 'Poisson arrivals per (sub-test x jurisdiction); rate shrunk toward a 1-per-10-years prior.',
  },
  policy: MAINT.policy,
  endpoints: ['/api/maintenance/calendar', '/api/maintenance/gaps', '/api/maintenance/queue',
              '/api/maintenance/watchlist', '/api/maintenance/node/{id}', '/api/maintenance/propose (POST)'],
});

// P(at least one missed change) at an arbitrary evaluation year
const pMissedAt = (n, year) => {
  if (n.work_type !== 'staleness') return null;
  const t = Math.max(0, year - (n.last_reviewed || year));
  return +(1 - Math.exp(-n.rate_per_year * t)).toFixed(4);
};

const maintCalendar = (horizonYear) => {
  const y = horizonYear || 2036;
  const rows = ATTESTED
    .map((n) => ({
      node: n.node, sub_test: n.sub_test, jurisdiction: n.jurisdiction, en: n.en, zh: n.zh,
      timeline: n.timeline, events_observed: n.events_observed,
      expected_interval_years: n.expected_interval_years,
      last_event_year: n.last_event_year, review_due_year: n.review_due_year,
      p_missed_at_horizon: pMissedAt(n, y),
    }))
    .sort((a, b) => a.review_due_year - b.review_due_year);
  const byYear = {};
  for (const r of rows) {
    const k = String(Math.floor(r.review_due_year));
    (byYear[k] = byYear[k] || []).push(r.node);
  }
  return { horizon: y, trigger_probability: MAINT.policy.review_trigger_probability,
           reviews_per_year: +(rows.length / Math.max(1, (Math.max(...rows.map((r) => r.review_due_year)) - 2026))).toFixed(1),
           schedule: byYear, rows };
};

const maintGaps = () => ({
  total: GAPS.length,
  note: 'A gap is a (sub-test x jurisdiction) cell with no authority on file. Gaps outrank staleness: nothing to go stale yet.',
  by_jurisdiction: counter(GAPS.map((n) => n.jurisdiction)),
  rows: GAPS.map(({ node, sub_test, jurisdiction, parent, kind, en, zh }) =>
    ({ node, sub_test, jurisdiction, parent, kind, en, zh })),
});

// the verification gate a proposed amendment must clear
const GATE = MAINT.policy.verification_gate;
function validateAmendment(body) {
  const TREAT = ['establishes', 'applies', 'affirms', 'broadens', 'clarifies', 'narrows', 'distinguishes', 'doubts', 'overrules'];
  const JURIS = ['EN', 'HK', 'SG', 'AU'];
  const LEVELS = ['unverified', 'verified-web', 'verified-quoted', 'verified-primary'];
  const isText = (v) => typeof v === 'string' && v.trim().length > 0;
  const gates = () => GATE.map((g) => ({ check: g, satisfied: null }));
  const echoLevel = (b) => (b && b.verified) || 'unverified';
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return {
      accepted: false,
      errors: ['proposal must be a non-null object'],
      status: 'rejected',
      verification_gate: gates(),
      verification_level: 'unverified',
      node_before: null,
      patch: null,
      next_steps: ['fix the errors above and resubmit'],
    };
  }
  const errors = [];
  const reqText = ['sub_test', 'jurisdiction', 'case', 'citation', 'court', 'treatment', 'effect'];
  const bad = reqText.filter((k) => !isText(body[k]));
  if (bad.length) errors.push(`missing fields: ${bad.join(', ')}`);
  if (isText(body.jurisdiction) && !JURIS.includes(body.jurisdiction)) {
    errors.push(`jurisdiction must be one of: ${JURIS.join(' | ')}`);
  }
  if (body.year === undefined) {
    errors.push('missing fields: year');
  } else if (typeof body.year !== 'number' || !Number.isFinite(body.year) || !Number.isInteger(body.year) || body.year < 1700 || body.year > 2100) {
    errors.push('year must be an integer number in [1700, 2100]');
  }
  if (isText(body.treatment) && !TREAT.includes(body.treatment)) {
    errors.push(`treatment must be one of: ${TREAT.join(' | ')}`);
  }
  let declared = 'unverified';
  if (body.verified === undefined) {
    declared = 'unverified';
  } else if (typeof body.verified === 'string' && LEVELS.includes(body.verified)) {
    declared = body.verified;
  } else {
    errors.push(`verified must be one of: ${LEVELS.join(' | ')}`);
  }
  if (body.verified === 'verified-primary' && !isText(body.pin)) {
    errors.push('verified-primary requires a paragraph or page pin cite');
  }
  if (body.verified === 'verified-quoted') {
    if (!isText(body.pin)) errors.push('verified-quoted requires a paragraph or page pin cite');
    if (!isText(body.source)) errors.push('verified-quoted requires the quoting judgment in source');
  }
  if (body.pin !== undefined && !isText(body.pin) && body.verified !== 'verified-primary' && body.verified !== 'verified-quoted') {
    errors.push('pin must be a nonempty string');
  }
  if (body.source !== undefined && !isText(body.source) && body.verified !== 'verified-quoted') {
    errors.push('source must be a nonempty string');
  }
  if (body.favor !== undefined && (typeof body.favor !== 'number' || !Number.isFinite(body.favor))) {
    errors.push('favor must be a finite number');
  }
  const known = isText(body.sub_test) && isText(body.jurisdiction)
    ? M_NODES.some((n) => n.sub_test === body.sub_test && n.jurisdiction === body.jurisdiction)
    : false;
  if (isText(body.sub_test) && isText(body.jurisdiction) && !known) {
    errors.push(`unknown node ${body.sub_test}@${body.jurisdiction}`);
  }
  const node = isText(body.sub_test) && isText(body.jurisdiction)
    ? M_NODES.find((n) => n.sub_test === body.sub_test && n.jurisdiction === body.jurisdiction)
    : undefined;
  const node_before = node ? { events_observed: node.events_observed, rate_per_year: node.rate_per_year,
    last_event_year: node.last_event_year, review_due_year: node.review_due_year } : null;
  const pin_required = ['verified-primary', 'verified-quoted'].includes(body.verified) && !isText(body.pin)
    ? `${body.verified} requires a paragraph or page pin cite` : undefined;
  if (errors.length) {
    return {
      accepted: false,
      errors,
      status: 'rejected',
      verification_gate: gates(),
      verification_level: echoLevel(body),
      pin_required,
      node_before,
      patch: null,
      next_steps: ['fix the errors above and resubmit'],
    };
  }
  return {
    accepted: true,
    errors: [],
    status: 'pending-independent-review',
    verification_gate: gates(),
    verification_level: declared,
    pin_required,
    warning: 'Structural acceptance only -- pending independent review against the cited source. The submitted verification level is a submitter declaration, not proof; no verification gate is satisfied and no dataset write has occurred.',
    node_before,
    patch: {
      op: 'append_event',
      timeline: node && node.timeline ? node.timeline : `NEW:${body.sub_test}`,
      event: { j: body.jurisdiction, y: body.year, case: body.case, citation: body.citation,
               court: body.court, treat: body.treatment, eff: body.effect,
               f: body.favor ?? null, verified: declared,
               pin: isText(body.pin) ? body.pin : null,
               source: isText(body.source) ? body.source : null },
    },
    next_steps: [
      'independent review of the judgment text with a pin cite',
      'confirm the treatment label and bindingness in this jurisdiction',
      'git-review the patch in the dataset repo -- proposals are not live writes',
    ],
  };
}


/* ──────────────────────────────────────────────────────────────
   Typed legal tests — logic first, numeric modelling only where applicable.
   Five structures are catalogued: conjunctive, disjunctive-gateway,
   balancing, threshold-discretion and presumption-rebuttal. Numeric weight
   bands belong only to balancing stages and are never legal authority.
   ────────────────────────────────────────────────────────────── */

const MODULES = [...SCORED.modules, ...REGISTRY.modules];
const REG_META = { version: REGISTRY.version, generated: REGISTRY.generated,
  principle: REGISTRY.principle, test_types: REGISTRY.test_types || SCORED.test_types,
  posture_catalog: REGISTRY.posture_catalog || SCORED.posture_catalog || {},
  track_catalog: REGISTRY.track_catalog || SCORED.track_catalog || {},
  doctrinal_role_catalog: REGISTRY.doctrinal_role_catalog || SCORED.doctrinal_role_catalog || {},
  source_catalog: REGISTRY.source_catalog || SCORED.source_catalog || {} };
const findModule = (id) => MODULES.find((m) => m.id === id);
const MODULE_TIMELINES = {};
for (const m of MODULES) for (const [tid, t] of Object.entries(m.timelines || {})) MODULE_TIMELINES[tid] = { ...t, module: m.id };
const findStage = (m, sid) => m && m.stages.find((s) => s.id === sid);

function moduleLogicTypes(module) {
  const canonical = SCORED.test_types || {};
  const result = [];
  if (canonical[module.top_type]) result.push(module.top_type);
  for (const stage of module.stages || []) {
    if (canonical[stage.test_type] && !result.includes(stage.test_type)) result.push(stage.test_type);
  }
  return result;
}

function moduleSourceCounts(module) {
  if (module.source_counts && typeof module.source_counts === 'object') return module.source_counts;
  return module.corpus_hits == null ? {} : { hklandlaw: module.corpus_hits };
}

function factorHasNumericWeight(factor) {
  return Number.isFinite(factor.weight)
    || (Number.isFinite(factor.weight_low) && Number.isFinite(factor.weight_high));
}

function stageWeightProfile(stage) {
  if (stage.test_type !== 'balancing') return { status: 'not-applicable', provenance: null };
  const factors = [...(stage.factors || []), ...(stage.counter_factors || [])];
  const assigned = factors.filter(factorHasNumericWeight).length;
  if (!assigned) return { status: 'unassigned', provenance: null };
  if (assigned !== factors.length) return { status: 'partial', provenance: null };
  const sources = new Set(factors.map((factor) => factor.weight_source || stage.weight_source).filter(Boolean));
  return { status: 'assigned', provenance: sources.size === 1 ? [...sources][0]
    : sources.size ? 'mixed' : 'unspecified' };
}

function stageIndexRow(stage) {
  const weight = stageWeightProfile(stage);
  return { id: stage.id, zh: stage.zh, en: stage.en, test_type: stage.test_type,
    doctrinal_role: stage.doctrinal_role || null,
    jurisdictions: stage.jurisdictions || null,
    factors: (stage.factors || []).length + (stage.counter_factors || []).length,
    litigation_postures: stage.litigation_postures || [],
    litigation_track: stage.litigation_track || null,
    primary_posture: stage.primary_posture ?? null,
    court_own_motion: !!stage.court_own_motion,
    litigation_note: stage.litigation_note || null,
    weight_applicable: stage.test_type === 'balancing', weight_status: weight.status,
    weight_provenance: weight.provenance, weighted: weight.status === 'assigned' };
}

function projectedCrossReferenceData(claim) {
  if (!claim.xref) return { elements: [], defences: [] };
  const [target] = claim.xref.split('#');
  if (target !== ELEMENTS.claim) throw new Error('unsupported cross-reference target ' + target);
  const elements = (claim.element_refs || []).map((reference) => {
    const source = ELEMENTS.elements.find((element) => element.id === reference.id);
    if (!source) throw new Error('cross-reference identifies unknown element ' + reference.id);
    const selected = reference.sub_tests
      ? source.sub_tests.filter((subTest) => reference.sub_tests.includes(subTest.id))
      : source.sub_tests;
    if (reference.sub_tests && selected.length !== reference.sub_tests.length) {
      throw new Error('cross-reference identifies unknown sub-test in ' + reference.id);
    }
    return { ...source, sub_tests: selected };
  });
  const defences = (claim.defence_refs || []).map((id) => {
    const source = ELEMENTS.defences.find((defence) => defence.id === id);
    if (!source) throw new Error('cross-reference identifies unknown defence ' + id);
    return source;
  });
  return { elements, defences };
}

function doctrineView(id, jurisdiction = null) {
  const catalog = taxonomy();
  const available = [];
  let match = null;
  for (const area of catalog.areas) for (const claim of area.claims) {
    available.push(claim.id);
    if (claim.id === id) match = { area, claim };
  }
  if (!match) return { error: 'unknown doctrine claim', claim: id, available };

  if (jurisdiction && !TAXONOMY_JURISDICTIONS.some((item) => item.id === jurisdiction)) {
    return { error: 'unknown jurisdiction', jurisdiction, available: TAXONOMY_JURISDICTIONS.map((item) => item.id) };
  }
  const { elements: taxonomyElements = [], defences: taxonomyDefences = [], ...claim } = match.claim;
  const projected = projectedCrossReferenceData(claim);
  const elements = claim.id === ELEMENTS.claim ? ELEMENTS.elements
    : projected.elements.length ? projected.elements : taxonomyElements;
  const defences = claim.id === ELEMENTS.claim ? ELEMENTS.defences
    : projected.defences.length ? projected.defences : taxonomyDefences;
  let logic = null;
  if (claim.model_ref) {
    const module = findModule(claim.model_ref.module_id);
    if (!module) throw new Error('doctrine claim references unknown module ' + claim.model_ref.module_id);
    const requestedStageIds = claim.model_ref.stage_ids || null;
    const allowed = requestedStageIds ? new Set(requestedStageIds) : null;
    const stages = module.stages.filter((stage) => (!allowed || allowed.has(stage.id))
      && (!jurisdiction || !stage.jurisdictions?.length || stage.jurisdictions.includes(jurisdiction)));
    const role_stage_ids = {};
    for (const stage of stages) {
      const role = stage.doctrinal_role;
      if (!role_stage_ids[role]) role_stage_ids[role] = [];
      role_stage_ids[role].push(stage.id);
    }
    logic = {
      module_id: module.id,
      coverage: claim.model_ref.coverage,
      jurisdiction,
      stage_ids: requestedStageIds,
      role_stage_ids,
      element_stage_ids: stages.filter((stage) => ['claim-elements', 'element-set'].includes(stage.doctrinal_role)).map((stage) => stage.id),
      module: { ...module, stages },
    };
  }

  return {
    version: catalog.version,
    claim,
    area: { zh: match.area.zh, en: match.area.en },
    elements,
    defences,
    logic,
    coverage: claim.coverage,
    composition: {
      analysis_structure_source: claim.xref ? 'xref' : elements.length ? 'elements-dataset'
        : logic ? 'logic-stages' : 'none',
      elements_source: claim.xref ? 'xref' : elements.length ? 'elements-dataset'
        : claim.coverage.elements === 'not-applicable' ? 'not-applicable'
        : logic ? 'logic-stages' : 'none',
      xref_target: claim.xref || null,
    },
  };
}

function elementDatasetForClaim(requestedClaim, jurisdiction) {
  const claim = requestedClaim || ELEMENTS.claim;
  if (claim !== ELEMENTS.claim) {
    const doctrine = doctrineView(claim);
    if (doctrine.error) return doctrine;
    return {
      error: `full element dataset is not available for ${claim}`,
      code: 'elements-not-available',
      claim,
      available: [ELEMENTS.claim],
      coverage: doctrine.coverage,
      model_ref: doctrine.claim.model_ref,
      doctrine_endpoint: `/api/doctrine/${encodeURIComponent(claim)}`,
      note: 'Use the unified doctrine endpoint for any mapped legal-test stages; an empty element dataset must not be replaced with another claim\'s elements.',
    };
  }

  const all = [];
  for (const el of ELEMENTS.elements) for (const st of el.sub_tests) all.push(...(st.auth || []));
  for (const d of ELEMENTS.defences) all.push(...(d.auth || []));
  if (jurisdiction && ELEMENTS.jurisdictions[jurisdiction]) all.push(...(ELEMENTS.jurisdictions[jurisdiction].cases || []));
  return {
    claim: ELEMENTS.claim, version: ELEMENTS.version, variants: ELEMENTS.variants,
    posture_catalog: ELEMENTS.posture_catalog, track_catalog: ELEMENTS.track_catalog,
    litigation_profile: ELEMENTS.litigation_profile,
    elements: ELEMENTS.elements, defences: ELEMENTS.defences,
    jurisdiction: jurisdiction ? ELEMENTS.jurisdictions[jurisdiction] : undefined,
    verification: verificationSummary(all),
    coverage_gaps: jurisdiction ? (ELEMENTS.jurisdictions[jurisdiction]?.gaps || []) : undefined,
    note: 'Every authority carries a verification level; see verification.levels for what each means. A jurisdiction gap is reported as a gap — do not infer the local position from the English backbone.',
  };
}

function scoreModule(id, facts) {
  const module = findModule(id);
  if (!module) return { ...scoringValidationError(`unknown module ${String(id)}`), available: MODULES.map((item) => item.id) };
  return evaluateScoreModule(module, facts);
}

function scoreRequest(body, requireModule = false) {
  const request = validateScoreRequest(body, requireModule);
  if (request.error) return request;
  return scoreModule(request.module, request.facts);
}

const scoredIndex = () => ({
  tiers: SCORED.tiers,
  version: SCORED.version, generated: SCORED.generated,
  test_types: SCORED.test_types, source_catalog: SCORED.source_catalog || REGISTRY.source_catalog || {},
  posture_catalog: SCORED.posture_catalog || REGISTRY.posture_catalog || {},
  track_catalog: SCORED.track_catalog || REGISTRY.track_catalog || {},
  doctrinal_role_catalog: SCORED.doctrinal_role_catalog || REGISTRY.doctrinal_role_catalog || {},
  provenance_levels: SCORED.provenance_levels,
  modules: MODULES.map((m) => ({ id: m.id, zh: m.zh, en: m.en, jurisdiction: m.jurisdiction,
    litigation_postures: m.litigation_postures, litigation_track: m.litigation_track,
    primary_posture: m.primary_posture ?? null, legal_kind: m.legal_kind || null,
    role_confidence: m.role_confidence || null,
    court_own_motion_summary: m.court_own_motion_summary || { stage_count: 0, stage_ids: [] },
    logic_types: moduleLogicTypes(m), source_counts: moduleSourceCounts(m),
    stages: m.stages.map(stageIndexRow) })),
  conjunctive_note: 'The misrepresentation elements at /api/elements follow a conjunctive structure: they take a gap list, not a score.',
});

const HISTORICAL = createHistoricalLibrary(ELEMENTS, MODULE_TIMELINES);
const AS_OF_SCHEMA = { oneOf: [
  { type: 'integer', minimum: 1000, maximum: 9999 },
  { type: 'string', pattern: '^[1-9][0-9]{3}(-[0-9]{2}-[0-9]{2})?$' },
], description: 'Year (end of year) or YYYY-MM-DD. Historical views withhold unversioned rule text and records whose date or source chronology is insufficient.' };
const HISTORICAL_TOOLS = new Set(['pleading_checklist','verify_citation','get_elements','get_element_test','get_timeline']);
function historicalCall(name,args) {
  const cutoff=parseAsOf(args.as_of);
  if(cutoff?.error) return cutoff;
  if(!HISTORICAL_TOOLS.has(name)) return {error:'as_of is not supported by this tool; use a historical element, checklist, timeline or citation query.',code:'unsupported-as-of'};
  switch(name) {
    case 'pleading_checklist': return HISTORICAL.checklist(args.jurisdiction,args.variant,cutoff);
    case 'verify_citation': return HISTORICAL.verification(verifyCitation({citation:args.citation}),cutoff);
    case 'get_elements':
      if (args.claim && args.claim !== ELEMENTS.claim) return elementDatasetForClaim(args.claim, args.jurisdiction);
      return HISTORICAL.elements(cutoff,args.jurisdiction);
    case 'get_element_test': return HISTORICAL.element(args.id,cutoff);
    case 'get_timeline': return HISTORICAL.timeline(args.id,cutoff,args.jurisdictions);
  }
}

const MCP_TOOLS = [
  { name: 'resolve_jurisdiction',
    description: 'Decide WHICH jurisdiction overlay applies before pulling doctrine. Give it the governing-law clause, seat, forum or any text naming courts or statutes; it returns the resolved jurisdiction with its precedent rule and statutes, or says it is ambiguous. Call this first — injecting English doctrine into a Hong Kong matter is the failure this tool exists to prevent.',
    inputSchema: { type: 'object', properties: { text: { type: 'string', description: 'governing law clause, seat, forum, or a description of the matter' } }, required: ['text'] } },
  { name: 'pleading_checklist',
    description: 'For drafting a statement of claim or advice: every element and sub-test of the claim, what must be pleaded for each, the backbone and LOCAL authority with pin cites and verification level, the standing rule as at a year, and — explicitly — where the library has no local authority so the drafter does not infer the local position from English law.',
    inputSchema: { type: 'object', properties: { jurisdiction: { type: 'string', enum: ['EN','HK','SG','AU'] }, variant: { type: 'string', enum: ['fraudulent-deceit','negligent-statutory','innocent'] }, as_of: AS_OF_SCHEMA } } },
  { name: 'verify_citation',
    description: 'Match a case identity against the stored core and persuasive indexes. Supplied names and all explicit citations must agree; conflicts and ambiguity are reported. Each original evidence record retains its source, pin and verification level. This lookup does not check a proposition or upgrade verification; a miss is a coverage statement.',
    inputSchema: { type: 'object', properties: { citation: { type: 'string', description: 'case name and/or citation as you intend to cite it' }, as_of: AS_OF_SCHEMA }, required: ['citation'] } },
  { name: 'score_factors',
    description: 'Inspect factors in a typed legal-test model. Balancing stages return scenario intervals including unknown facts and weight bands; other stages return explicit checklists or encoded gate states. Unencoded stage dependencies prevent a module-wide legal conclusion. Weights are model assumptions, not legal authority or outcome probabilities.',
    inputSchema: { type: 'object', properties: { module: { type: 'string', description: 'module id, e.g. HKJUR' }, facts: { type: 'object', description: 'map of factor id -> true | false | "unknown"' } }, required: ['module'] } },
  { name: 'list_causes_of_action',
    description: 'List every modelled legal-test module with its test logic, litigation postures and matter track. A module can be both spear and shield; procedure and jurisdiction are tracks, not competing postures. Only balancing stages use numeric weight bands.',
    inputSchema: { type: 'object', properties: { area: { type: 'string' }, test_type: { type: 'string' },
      posture: { type: 'string', enum: ['spear', 'shield'] },
      track: { type: 'string', enum: ['merits', 'procedure', 'jurisdiction'] },
      role: { type: 'string', enum: ['spear', 'shield', 'jurisdiction', 'procedure'], description: 'Legacy primary-role filter retained for compatibility; prefer posture and track.' } } } },
  { name: 'list_scored_tests',
    description: 'List the typed legal-test modules and their logic structures. The legacy tool name is retained for compatibility; numeric weights apply only to balancing stages.',
    inputSchema: { type: 'object', properties: {} } },
  { name: 'check_staleness',
    description: 'Report drift risk for an element sub-test: observed drift rate, expected interval between test-changing decisions, when the node is next due for review, and P(a change has been missed) at a given year.',
    inputSchema: { type: 'object', properties: { sub_test: { type: 'string' }, jurisdiction: { type: 'string', enum: ['EN','HK','SG','AU'] }, at_year: { type: 'number' } }, required: ['sub_test'] } },
  { name: 'propose_amendment',
    description: 'Submit a newly decided case as a proposed amendment to a sub-test timeline. Validates the treatment label and required fields, returns the JSON patch plus the verification steps still outstanding. Does not write — amendments are reviewed in the dataset repo.',
    inputSchema: { type: 'object', properties: { sub_test: { type: 'string' }, jurisdiction: { type: 'string', enum: ['EN','HK','SG','AU'] }, case: { type: 'string' }, citation: { type: 'string' }, court: { type: 'string' }, year: { type: 'integer', minimum: 1700, maximum: 2100 }, treatment: { type: 'string', enum: ['establishes','applies','affirms','broadens','clarifies','narrows','distinguishes','doubts','overrules'] }, effect: { type: 'string' }, favor: { type: 'number' }, verified: { type: 'string', enum: ['unverified','verified-web','verified-quoted','verified-primary'], default: 'unverified', description: 'Submitter-declared level only, not proof of independent verification. verified-primary requires pin; verified-quoted requires pin and source.' }, pin: { type: 'string', description: 'Paragraph or page pin cite. Required for verified-primary and verified-quoted.' }, source: { type: 'string', description: 'Quoting judgment identifying the verbatim passage. Required for verified-quoted.' } }, required: ['sub_test','jurisdiction','case','citation','court','year','treatment','effect'] } },
  { name: 'get_elements',
    description: 'Return the full element dataset for a supported claim, optionally filtered to one jurisdiction. Unsupported claims return an explicit coverage error and point to get_doctrine; they never fall back to another claim\'s elements.',
    inputSchema: { type: 'object', properties: {
      claim: { type: 'string', description: 'e.g. misrepresentation' },
      jurisdiction: { type: 'string', enum: ['EN', 'HK', 'SG', 'AU'] }, as_of: AS_OF_SCHEMA }, required: ['claim'] } },
  { name: 'get_doctrine',
    description: 'Return one matter-centred doctrine view: claim metadata, any element data, and its mapped legal-test module. A jurisdiction filter removes stages that do not apply in that jurisdiction; partial model references expose only their selected stages.',
    inputSchema: { type: 'object', properties: {
      claim: { type: 'string', description: 'taxonomy claim id, e.g. private-nuisance' },
      jurisdiction: { type: 'string', enum: ['EN', 'HK', 'SG', 'AU'] } }, required: ['claim'] } },
  { name: 'get_element_test',
    description: 'Return one sub-test with its authorities, and the standing rule as at a given year.',
    inputSchema: { type: 'object', properties: {
      id: { type: 'string', description: 'sub-test id, e.g. E3c or D1' },
      as_of: AS_OF_SCHEMA }, required: ['id'] } },
  { name: 'get_timeline',
    description: 'Return a drift timeline with per-jurisdiction standing rules as at a year. Covers element timelines (T1-T3) and module timelines (NYC-V, ARBCH-12, HKJUR-J23, HKJUR-J4).',
    inputSchema: { type: 'object', properties: {
      id: { type: 'string', enum: ['T1', 'T2', 'T3', 'NYC-V', 'ARBCH-12', 'HKJUR-J23', 'HKJUR-J4'] },
      as_of: AS_OF_SCHEMA,
      jurisdictions: { type: 'array', items: { type: 'string' } } }, required: ['id'] } },
  { name: 'search_corpus',
    description: 'Full-text search over the Hong Kong land law case-note corpus (metadata + short summaries, each linking to the source post).',
    inputSchema: { type: 'object', properties: {
      q: { type: 'string' }, topic: { type: 'string' }, year: { type: 'string' },
      court: { type: 'string' }, jurisdiction: { type: 'string' }, limit: { type: 'number' } } } },
  { name: 'lookup_case',
    description: 'Look up a case by name: corpus citations and discussing posts, falling back to the E&W persuasive index when the corpus is silent.',
    inputSchema: { type: 'object', properties: { name: { type: 'string' } }, required: ['name'] } },
];

function mcpCall(name, args = {}) {
  if(args && typeof args==='object' && Object.prototype.hasOwnProperty.call(args,'as_of') && args.as_of!==undefined) return historicalCall(name,args);
  switch (name) {
    case 'resolve_jurisdiction':
      return resolveJurisdiction(args.text);
    case 'pleading_checklist':
      return pleadingChecklist(args.jurisdiction, args.variant, args.as_of);
    case 'verify_citation':
      return verifyCitation(args);

    case 'get_elements':
      return elementDatasetForClaim(args.claim, args.jurisdiction);
    case 'get_doctrine':
      return doctrineView(args.claim, args.jurisdiction);
    case 'get_element_test': {
      const found = findSubTest(args.id);
      if (!found) return { error: `unknown sub-test ${args.id}` };
      const st = found.sub_test || found.defence || found.element;
      const drift = st.drift ? timelineAsOf(st.drift, args.as_of, null) : null;
      return { ...found, timeline: drift };
    }
    case 'get_timeline':
      return timelineAsOf(args.id, args.as_of, args.jurisdictions) || { error: 'unknown timeline' };
    case 'search_corpus': {
      const p = new URLSearchParams();
      for (const [k, v] of Object.entries(args)) if (v != null) p.set(k === 'jurisdiction' ? 'juris' : k, v);
      const r = searchPosts(p);
      return { total: r.total, results: r.results.map(({ id, url, title, date, topics, summary, cases }) => ({ id, url, title, date, topics, summary, cases })) };
    }
    case 'score_factors':
      return scoreRequest(args, true);
    case 'list_causes_of_action': {
      let ms = MODULES;
      if (args.area) ms = ms.filter((m) => (m.area || '').includes(args.area));
      if (args.test_type) ms = ms.filter((m) => moduleLogicTypes(m).includes(args.test_type));
      if (args.role) ms = ms.filter((m) => m.role === args.role);
      if (args.posture) ms = ms.filter((m) => (m.litigation_postures || []).includes(args.posture));
      if (args.track) ms = ms.filter((m) => m.litigation_track === args.track);
      return { total: ms.length, principle: REG_META.principle,
        doctrinal_role_catalog: REG_META.doctrinal_role_catalog,
        modules: ms.map((m) => ({ id: m.id, zh: m.zh, en: m.en, area: m.area, top_type: m.top_type,
          logic_types: moduleLogicTypes(m), jurisdiction: m.jurisdiction,
          corpus_hits: m.corpus_hits ?? null, source_counts: moduleSourceCounts(m), note: m.note,
          role: m.role || null, role_zh: m.role_zh || null, role_note: m.role_note || undefined,
          litigation_postures: m.litigation_postures, litigation_track: m.litigation_track,
          primary_posture: m.primary_posture ?? null, legal_kind: m.legal_kind || null,
          role_confidence: m.role_confidence || null,
          court_own_motion_summary: m.court_own_motion_summary || { stage_count: 0, stage_ids: [] },
          litigation_note: m.litigation_note || undefined,
          timelines: Object.keys(m.timelines || {}),
          stages: m.stages.map((s2) => ({ ...stageIndexRow(s2), rule: s2.rule })) })) };
    }
    case 'list_scored_tests':
      return scoredIndex();
    case 'check_staleness': {
      const y = args.at_year || 2026.65;
      const rows = M_NODES.filter((n) => n.sub_test === args.sub_test &&
        (!args.jurisdiction || n.jurisdiction === args.jurisdiction));
      if (!rows.length) return { error: `unknown sub-test ${args.sub_test}` };
      return { sub_test: args.sub_test, evaluated_at: y,
        nodes: rows.map((n) => ({ ...n, p_missed_at: pMissedAt(n, y) })),
        policy: { model: MAINT.policy.model, trigger: MAINT.policy.review_trigger_probability } };
    }
    case 'propose_amendment':
      return validateAmendment(args);
    case 'lookup_case':
      return lookupCase(args && typeof args === 'object' && !Array.isArray(args) ? args.name : undefined);

    default:
      return { error: `unknown tool ${name}` };
  }
}

/* ──────────────────────────────────────────────────────────────
   Router
   ────────────────────────────────────────────────────────────── */

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'content-type': 'application/json; charset=utf-8', 'access-control-allow-origin': '*', 'cache-control': 'public, max-age=300' },
});


/* Persuasive branch (E&W index). Read-only. Every record is
   verified:'unverified' + hk_status:'persuasive-only' by construction —
   this surface reports status, it never upgrades it. */
const P_CASES = PERSUASIVE.cases;
const P_BY_SLUG = new Map(P_CASES.map(c => [c.slug, c]));
const P_EDGES = PERSUASIVE.edges;
function persuasiveSearch(params) {
  const q = (params.get('q') || '').toLowerCase();
  const area = params.get('area'), signal = params.get('signal'),
        court = params.get('court'), year = params.get('year'),
        juris = params.get('jurisdiction') || params.get('juris');
  const lim = Math.min(+(params.get('limit') || 30), 200);
  const toks = q.split(/\s+/).filter(t => t.length > 1);
  const out = P_CASES.filter(c =>
    (!area || (c.area || '').toLowerCase().includes(area.toLowerCase()) || (c.area_zh || '').includes(area)) &&
    (!signal || c.signal === signal) &&
    (!court || (c.court || '').toLowerCase().includes(court.toLowerCase())) &&
    (!year || String(c.year) === year) &&
    (!juris || (c.jurisdiction || '') === juris.toUpperCase()) &&
    (!toks.length || toks.every(t => ((c.name || '') + ' ' + (c.cite || '') + ' ' + (c.area || '') + ' ' + (c.court || '') + ' ' + (c.signal || '') + ' ' + (c.status || []).join(' ')).toLowerCase().includes(t))));
  return { total: out.length, limit: lim, results: out.slice(0, lim),
    hk_status: PERSUASIVE.hk_status, doctrine: PERSUASIVE.doctrine };
}


export default async (req) => {
  const url = new URL(req.url);
  const path = url.pathname.replace(/^\/api\/?/, '').replace(/\/$/, '');
  const q = url.searchParams;

  if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: { 'access-control-allow-origin': '*', 'access-control-allow-headers': 'content-type', 'access-control-allow-methods': 'GET,POST,OPTIONS' } });

  try {
    if (path === '' || path === 'health') return json({ ok: true, service: 'doctrine-atlas-api', endpoints: ['/api/stats', '/api/taxonomy', '/api/doctrine/{claim}', '/api/elements', '/api/element/{id}', '/api/timeline/{id}?as_of=YYYY', '/api/jurisdictions', '/api/search?q=', '/api/cases', '/api/case?name=', '/api/topics', '/api/statutes', '/api/graph', '/api/maintenance', '/api/maintenance/calendar', '/api/maintenance/gaps', '/api/maintenance/queue', '/api/maintenance/watchlist', '/api/maintenance/propose (POST)', '/api/scored', '/api/scored/{id}', '/api/score (POST)', '/api/registry', '/api/calibration-queue', '/api/resolve?text=', '/api/checklist?jurisdiction=HK&variant=&as_of=', '/api/verify?cite=', '/api/persuasive', '/api/persuasive/{slug}', '/api/persuasive/graph', '/api/persuasive/queue', '/api/mcp (POST)'] });

    if(q.has('as_of') && path!=='verify') {
      const cutoff=parseAsOf(q.get('as_of'));
      if(cutoff.error) return json(cutoff,400);
      let historical;
      if(path==='checklist') historical=HISTORICAL.checklist(q.get('jurisdiction'),q.get('variant'),cutoff);
      else if(path==='elements') historical=q.has('claim') && q.get('claim') !== ELEMENTS.claim
        ? elementDatasetForClaim(q.get('claim'),q.get('jurisdiction'))
        : HISTORICAL.elements(cutoff,q.get('jurisdiction'));
      else if(path==='jurisdictions') {
        const projected=HISTORICAL.elements(cutoff);
        historical={jurisdictions:projected.jurisdictions,as_of:projected.as_of,historical_mode:projected.historical_mode,
          historical_rule_status:projected.historical_rule_status,historical_limitations:projected.historical_limitations};
      }
      else if(path.startsWith('element/')) historical=HISTORICAL.element(path.slice('element/'.length),cutoff);
      else if(path.startsWith('timeline/')) historical=HISTORICAL.timeline(path.slice('timeline/'.length),cutoff,q.get('j')?q.get('j').split(','):undefined);
      else return json({error:'as_of is not supported by this endpoint; use elements, element, timeline, checklist, jurisdictions or verify.',code:'unsupported-as-of'},400);
      return json(historical,historical.error?404:200);
    }

    if (path === 'resolve') return json(resolveJurisdiction(q.get('text') || ''));
    if (path === 'checklist') return json(pleadingChecklist(q.get('jurisdiction'), q.get('variant'), q.get('as_of')));
    if (path === 'verify') {
      const cite = q.get('cite') || '';
      const local = mcpCall('verify_citation', { citation: cite, as_of: q.has('as_of') ? q.get('as_of') : undefined });
      if(local.error) return json(local,400);
      const online = await liveCitation(cite,local,{historical:q.has('as_of'),disabled:q.get('live')==='0'});
      if(online) local.hklii=online;
      return json(local);
    }
    if (path === 'stats') return json(STATS);
    if (path === 'taxonomy') return json(taxonomy());
    if (path.startsWith('doctrine/')) {
      const claim = decodeURIComponent(path.slice('doctrine/'.length));
      const result = doctrineView(claim, q.get('jurisdiction'));
      return json(result, result.error ? 404 : 200);
    }
    if (path === 'elements') {
      if (!q.has('claim') || q.get('claim') === ELEMENTS.claim) return json(ELEMENTS);
      const result = elementDatasetForClaim(q.get('claim'), q.get('jurisdiction'));
      return json(result, result.error ? 404 : 200);
    }
    if (path === 'jurisdictions') return json(ELEMENTS.jurisdictions);

    if (path.startsWith('element/')) {
      const found = findSubTest(path.slice('element/'.length));
      if (!found) return json({ error: 'not found' }, 404);
      const st = found.sub_test || found.defence;
      const drift = st && st.drift ? timelineAsOf(st.drift, q.get('as_of'), null) : null;
      return json({ ...found, timeline: drift });
    }

    if (path.startsWith('timeline/')) {
      const t = timelineAsOf(path.slice('timeline/'.length), q.get('as_of'), q.get('j') ? q.get('j').split(',') : null);
      return t ? json(t) : json({ error: 'not found' }, 404);
    }

    if (path === 'search') return json(searchPosts(q));

    if (path === 'cases') {
      const s = norm(q.get('q') || '');
      const limit = Math.min(+(q.get('limit') || 60), 400);
      const offset = +(q.get('offset') || 0);
      const jf = q.get('juris');
      let list = CASE_LIST;
      if (s) list = list.filter((c) => c.key.includes(s));
      if (jf) list = list.filter((c) => c.jurisdictions.includes(jf));
      return json({ total: list.length, results: list.slice(offset, offset + limit) });
    }

    if (path === 'case') {
      const result = lookupCase(q.get('name'), true);
      return json(result, result.status === 'invalid-input' ? 400 : result.status === 'not-found' ? 404 : 200);
    }

    if (path === 'topics') return json({ total: TOPIC_LIST.length, results: TOPIC_LIST.slice(0, Math.min(+(q.get('limit') || 200), 1000)) });
    if (path === 'statutes') return json({ total: STATUTE_LIST.length, results: STATUTE_LIST.slice(0, Math.min(+(q.get('limit') || 120), 400)) });

    if (path === 'graph') {
      const top = Math.min(+(q.get('n') || 40), 120);
      const nodes = TOPIC_LIST.slice(0, top);
      const keep = new Set(nodes.map((n) => n.topic));
      const links = [];
      for (const [k, w] of COOC) {
        const [a, b] = k.split('\u0000');
        if (keep.has(a) && keep.has(b) && w >= +(q.get('min') || 2)) links.push({ source: a, target: b, weight: w });
      }
      links.sort((a, b) => b.weight - a.weight);
      return json({ nodes, links: links.slice(0, 400) });
    }

    if (path === 'post') {
      const s = q.get('slug'); const id = q.get('id');
      const p = id != null ? POSTS[+id] : POSTS.find((x) => x.slug === s);
      return p ? json(p) : json({ error: 'not found' }, 404);
    }

    if (path === 'registry') {
      const stageIdsByType = Object.fromEntries(Object.keys(SCORED.test_types || {}).map((key) => [key, []]));
      let rmods = MODULES;
      if (q.get('role')) rmods = rmods.filter((m) => m.role === q.get('role'));
      if (q.get('posture')) rmods = rmods.filter((m) => (m.litigation_postures || []).includes(q.get('posture')));
      if (q.get('track')) rmods = rmods.filter((m) => m.litigation_track === q.get('track'));
      for (const m of rmods) for (const st of m.stages) (stageIdsByType[st.test_type] = stageIdsByType[st.test_type] || []).push(m.id + '/' + st.id);
      const stageCounts = Object.fromEntries(Object.entries(stageIdsByType).map(([key, values]) => [key, values.length]));
      const moduleCounts = Object.fromEntries(Object.keys(SCORED.test_types || {}).map((key) => [key,
        rmods.filter((module) => moduleLogicTypes(module).includes(key)).length]));
      return json({ ...REG_META, total_modules: rmods.length,
        roles: ['spear', 'shield', 'jurisdiction', 'procedure'],
        postures: Object.keys(REG_META.posture_catalog), tracks: Object.keys(REG_META.track_catalog),
        stage_counts_by_test_type: stageCounts, module_counts_by_logic_type: moduleCounts,
        by_test_type: stageCounts, by_test_type_scope: 'stages; legacy alias of stage_counts_by_test_type',
        modules: rmods.map((m) => ({ id: m.id, area: m.area || null, zh: m.zh, en: m.en,
          jurisdiction: m.jurisdiction, top_type: m.top_type || null, corpus_hits: m.corpus_hits ?? null,
          logic_types: moduleLogicTypes(m), source_counts: moduleSourceCounts(m),
          role: m.role || null, role_zh: m.role_zh || null, role_note: m.role_note || undefined,
          litigation_postures: m.litigation_postures, litigation_track: m.litigation_track,
          primary_posture: m.primary_posture ?? null, legal_kind: m.legal_kind || null,
          role_confidence: m.role_confidence || null,
          court_own_motion_summary: m.court_own_motion_summary || { stage_count: 0, stage_ids: [] },
          litigation_note: m.litigation_note || undefined,
          timelines: Object.keys(m.timelines || {}),
          stages: m.stages.map(stageIndexRow) })) });
    }
    if (path === 'calibration-queue') {
      const rows = [];
      for (const m of MODULES) for (const st of m.stages) {
        if (st.test_type !== 'balancing') continue;
        const fs = (st.factors || []).concat(st.counter_factors || []);
        const un = fs.filter((factor) => !factorHasNumericWeight(factor));
        if (un.length) rows.push({ module: m.id, zh: m.zh, stage: st.id, stage_zh: st.zh,
          factors_unassigned: un.length, factors_total: fs.length,
          corpus_hits: m.corpus_hits ?? null, source_counts: moduleSourceCounts(m),
          method: 'code decided judgments for factor presence + outcome, fit logistic regression',
          factors: un.map((f) => ({ id: f.id, zh: f.zh, en: f.en })) });
      }
      rows.sort((a, b) => (b.corpus_hits || 0) - (a.corpus_hits || 0) || b.factors_unassigned - a.factors_unassigned);
      return json({ kind: 'balancing-weight-assignment-queue', total_stages: rows.length,
        total_factors: rows.reduce((a, r) => a + r.factors_unassigned, 0),
        empirical_calibration_status: 'not-assessed',
        note: 'Only balancing stages appear here. This queue tracks missing numeric model bands, not empirical outcome calibration.',
        rows });
    }
    if (path === 'scored') return json(scoredIndex());
    if (path.startsWith('scored/')) {
      const id = decodeURIComponent(path.slice(7));
      const m = findModule(id);
      return m ? json(m) : json({ error: 'unknown module', id, available: MODULES.map((x) => x.id) }, 404);
    }
    if (path === 'score') {
      if (req.method !== 'POST') return json({ error: 'POST required', example: { module: 'HKJUR', facts: { 'F-governing-law': true, 'F-plaintiff-connection': true } } }, 405);
      let body;
      try { body = await req.json(); }
      catch { return json(scoringValidationError('Score request must contain valid JSON.'), 400); }
      const result = scoreRequest(body);
      return json(result, result.error ? 400 : 200);
    }

    if (path === 'persuasive') return json(persuasiveSearch(q));
    if (path === 'persuasive/queue') {
      const rank = { negative: 0, superseded: 1, qualified: 2 };
      const rows = P_CASES
        .filter(c => c.verified === 'unverified')
        .map(c => ({ slug: c.slug, name: c.name, cite: c.cite, court: c.court,
          year: c.year, area: c.area, signal: c.signal, status: c.status,
          reviewed: (c.staleness || {}).reviewed || null }))
        .sort((a, b) => (rank[a.signal] ?? 3) - (rank[b.signal] ?? 3)
          || String(a.reviewed || '').localeCompare(String(b.reviewed || '')));
      const lim = Math.min(+(q.get('limit') || 100), 449);
      return json({ total: rows.length, limit: lim, results: rows.slice(0, lim),
        policy: 'Human-check queue for the persuasive index: load-bearing signals '
          + '(negative, superseded, qualified) first, stalest reviewed-date first. '
          + 'Checking a record upgrades NOTHING by itself; levels change only via the core rules.' });
    }
    if (path.startsWith('persuasive/')) {
      const rest = decodeURIComponent(path.slice('persuasive/'.length));
      if (rest === 'graph') {
        const ty = q.get('type'), sig = q.get('signal');
        const lim = Math.min(+(q.get('limit') || 500), 2000);
        const edges = P_EDGES.filter(e => (!ty || e.type === ty) && (!sig || e.signal === sig));
        return json({ total: edges.length, limit: lim, edges: edges.slice(0, lim),
          hk_status: PERSUASIVE.hk_status, signal_legend: PERSUASIVE.signal_legend });
      }
      const c = P_BY_SLUG.get(rest);
      if (!c) return json({ error: 'unknown persuasive case', slug: rest }, 404);
      return json({ ...c, incoming_treatment: P_EDGES.filter(e => e.to_slug === c.slug) });
    }
    if (path === 'maintenance') return json(maintOverview());
    if (path === 'maintenance/calendar') return json(maintCalendar(+(q.get('horizon') || 2036)));
    if (path === 'maintenance/gaps') return json(maintGaps());
    if (path === 'maintenance/queue') return json({ total: MAINT.queue.length, results: MAINT.queue });
    if (path === 'maintenance/watchlist') return json(MAINT.watchlist);
    if (path === 'maintenance/history') return json(MAINT.history);
    if (path.startsWith('maintenance/node/')) {
      const id = decodeURIComponent(path.slice('maintenance/node/'.length));
      const rows = M_NODES.filter((n) => n.node === id || n.sub_test === id);
      if (!rows.length) return json({ error: 'unknown node', id }, 404);
      const y = +(q.get('at') || 2026.65);
      return json({ id, evaluated_at: y, nodes: rows.map((n) => ({ ...n, p_missed_at: pMissedAt(n, y) })) });
    }
    if (path === 'maintenance/propose') {
      if (req.method !== 'POST') return json({ error: 'POST required', required_fields: ['sub_test','jurisdiction','case','citation','court','year','treatment','effect'] }, 405);
      const body = await req.json().catch(() => ({}));
      return json(validateAmendment(body));
    }

    if (path === 'mcp') {
      if (req.method !== 'POST') return json({ error: 'POST required', tools: MCP_TOOLS.map((t) => t.name) }, 405);
      const body = await req.json().catch(() => ({}));
      const { id = null, method, params = {} } = body;
      const ok = (result) => json({ jsonrpc: '2.0', id, result });
      if (method === 'initialize') return ok({ protocolVersion: '2024-11-05', capabilities: { tools: {} }, serverInfo: { name: 'doctrine-atlas', version: ELEMENTS.version } });
      if (method === 'tools/list') return ok({ tools: MCP_TOOLS });
      if (method === 'tools/call') {
        const args = ['score_factors', 'verify_citation', 'lookup_case'].includes(params.name) ? params.arguments : (params.arguments || {});
        const out = mcpCall(params.name, args);
        const failed = !!out.error || (params.name === 'propose_amendment' && !!out && out.accepted === false);
        return ok({ content: [{ type: 'text', text: JSON.stringify(out, null, 1) }], isError: failed });
      }
      return json({ jsonrpc: '2.0', id, error: { code: -32601, message: `unknown method ${method}` } }, 400);
    }

    return json({ error: 'unknown endpoint', path }, 404);
  } catch (err) {
    return json({ error: String(err && err.message || err) }, 500);
  }
};

export const config = { path: '/api/*' };
