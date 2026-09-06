// Offline identity lookup over stored records. No judgment/proposition is checked.
const compact = (text) => String(text).toLowerCase().replace(/\s+/gu, '');
const words = (text) => String(text || '').toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
const specificCitation = (text) => /[a-z]/i.test(text) && /\d/.test(text);
const citationParts = (record) => String(record.cite || '').split(/\s*;\s*/).filter(specificCitation);
const suffix = /\s+(?:ltd|limited|plc|co|company|corp|corporation|inc|incorporated)$/;

function withoutCompanySuffix(text) {
  let value = words(text), prior;
  do { prior = value; value = value.replace(suffix, ''); } while (prior !== value);
  return value;
}
function parties(text) {
  return String(text).split(/\s+v(?:s\.?|\.|ersus)?\s+/i).map(words);
}
const prefix = (short, long) => Boolean(short) && (short === long || long.startsWith(short + ' '));
function matchesParty(query, stored) {
  if (prefix(query, stored)) return true;
  // Corporate normalization is grounded in the stored party, never invented
  // by appending Ltd/Co/etc. to a person whose record has no such suffix.
  return suffix.test(stored) && prefix(withoutCompanySuffix(query), withoutCompanySuffix(stored));
}

export function matchesCaseName(query, name) {
  if (words(query) && words(query) === words(name)) return true;
  const q = parties(query), n = parties(name);
  if (q.some((part) => !part) || q.length > 2) return false;
  if (q.length === 2) return n.length === 2 && matchesParty(q[0], n[0]) && matchesParty(q[1], n[1]);
  return matchesParty(q[0], n[0]);
}

function compatibleNames(a, b) {
  const x = parties(a), y = parties(b);
  return x.length === y.length && x.every((part, i) => prefix(part, y[i]) || prefix(y[i], part));
}

function compactPositions(text) {
  const positions = [], chars = [];
  for (let i = 0; i < text.length; i++) if (!/\s/u.test(text[i])) {
    chars.push(text[i].toLowerCase()); positions.push(i);
  }
  return { value: chars.join(''), positions };
}

function extractInput(text, knownKeys) {
  const { value, positions } = compactPositions(text);
  const spans = [];
  for (const match of text.matchAll(/\b(?:at|paras?\.?|paragraphs?)\s*\[\s*\d+\s*\](?:\s*[-–]\s*\[\s*\d+\s*\])?/gi)) {
    const end = match.index + match[0].length;
    // An explicit court/reporter and number after [YYYY] is a citation even
    // when preceded by "at". It must still participate in identity checking.
    if (!/^\s*(?:\d+\s*)?[A-Za-z][A-Za-z'’&().\s-]*\d/.test(text.slice(end))) {
      spans.push({ start: match.index, end, pin: true });
    }
  }
  const overlaps = (start, end) => spans.some((span) => start < span.end && end > span.start);
  // Recognize complete stored citation forms, including old reports and dockets.
  // Longest first prevents a shorter page/number prefix consuming a full citation.
  for (const key of knownKeys) {
    let offset = 0, at;
    while ((at = value.indexOf(key, offset)) !== -1) {
      offset = at + key.length;
      const start = positions[at], end = positions[offset - 1] + 1;
      const previous = text[start - 1], next = text[end];
      const mergedNumber = /\d/.test(key.at(-1)) && /\d/.test(value[offset] || '');
      if (mergedNumber || (previous && /[\p{L}\p{N}]/u.test(previous))
          || (next && /[\p{L}\p{N}]/u.test(next)) || overlaps(start, end)) continue;
      spans.push({ start, end, key, raw: text.slice(start, end), known: true });
    }
  }
  // Every remaining explicit dated citation is unresolved, never name fallback.
  const markers = [...text.matchAll(/[\[(]\s*\d{4}\s*[\])]/g)];
  for (let i = 0; i < markers.length; i++) {
    const marker = markers[i], start = marker.index;
    if (spans.some((span) => start >= span.start && start < span.end)) continue;
    const nextMarker = markers[i + 1]?.index ?? text.length;
    const semicolon = text.indexOf(';', start);
    const nextKnown = spans.filter((span) => span.start > start).reduce((end, span) => Math.min(end, span.start), text.length);
    const end = Math.min(nextMarker, nextKnown, semicolon === -1 ? text.length : semicolon);
    if (!overlaps(start, end)) spans.push({ start, end, raw: text.slice(start, end).trim(), known: false });
  }
  for (const match of text.matchAll(/\b(?:HCA|HCCL|CACV|FAMV|HCMP|HCAL|CACC|DCCJ)\s*\d+\s*\/\s*\d{4}\b|\b\d+\s+(?:ER|ALR|FCR)\s+\d+\b/gi)) {
    if (!overlaps(match.index, match.index + match[0].length)) {
      spans.push({ start: match.index, end: match.index + match[0].length, raw: match[0], known: false });
    }
  }
  spans.sort((a, b) => a.start - b.start);
  let residual = '', last = 0;
  for (const span of spans) { residual += text.slice(last, span.start) + ' '; last = span.end; }
  residual += text.slice(last);
  residual = residual.replace(/\b(?:at|paras?\.?|paragraphs?)\s*\[?\d+\]?(?:\s*[-–]\s*\[?\d+\]?)?/gi, ' ')
    .replace(/\[\d{1,3}\](?:\s*[-–]\s*\[\d{1,3}\])?/g, ' ')
    .replace(/^[\s,;:/-]+|[\s,;:/-]+$/g, '').replace(/\s+and\s*$/i, '').trim();
  if (/^and$/i.test(residual)) residual = '';
  return { citations: spans.filter((span) => !span.pin), name: residual };
}

const coverageNote = 'This is a lookup in the stored library, not evidence that an unlisted case does not exist.';

export function createCitationIndex(inputRecords) {
  const records = inputRecords.map((record) => ({ ...record }));
  const recordKeys = records.map((record) => citationParts(record).map(compact));
  const parent = records.map((_, index) => index);
  const root = (index) => { while (parent[index] !== index) index = parent[index]; return index; };
  const byKey = new Map();
  records.forEach((record, index) => {
    for (const key of recordKeys[index]) {
      const peers = byKey.get(key) || [];
      for (const peer of peers) {
        if (compatibleNames(record.case || record.name, records[peer].case || records[peer].name)) {
          parent[root(index)] = root(peer);
        }
      }
      peers.push(index); byKey.set(key, peers);
    }
  });
  const grouped = new Map();
  records.forEach((record, index) => {
    const id = root(index);
    if (!grouped.has(id)) grouped.set(id, []);
    grouped.get(id).push(record);
  });
  const groups = [...grouped.entries()].map(([id, evidence]) => ({
    id: `stored-case-${id}`,
    evidence,
    names: [...new Set(evidence.map((record) => record.case || record.name).filter(Boolean))],
    citations: [...new Set(evidence.flatMap(citationParts))],
    keys: new Set(evidence.flatMap((record) => citationParts(record).map(compact))),
  }));
  const knownKeys = [...byKey.keys()].sort((a, b) => b.length - a.length);
  const identity = (group) => ({
    identity_id: group.id, case: group.names[0], names: group.names,
    identity_kind: group.names.some((name) => name.includes(';') && parties(name).length > 2) ? 'combined-case-record' : 'case-record',
    citations: group.citations, branches: [...new Set(group.evidence.map((record) => record.branch || 'core'))],
  });
  const rejected = (status, citation, candidates = [], extra = {}) => ({
    found: false, status, citation, proposition_check: 'not-performed',
    candidates: [...new Set(candidates)].map(identity), note: coverageNote, ...extra,
  });

  return {
    lookup(text) {
      if (typeof text !== 'string' || !text.trim()) {
        return rejected('invalid-input', typeof text === 'string' ? text : undefined, [], {
          error: 'citation must be a nonempty string containing a case name and/or citation.',
        });
      }
      const input = extractInput(text, knownKeys);
      const names = input.name ? groups.filter((group) => group.names.some((name) => matchesCaseName(input.name, name))) : [];
      const known = input.citations.filter((cite) => cite.known);
      const unknown = input.citations.filter((cite) => !cite.known);
      const citationGroups = known.map((cite) => groups.filter((group) => group.keys.has(cite.key)));
      if (unknown.length) return rejected('unresolved-citation', text, [...names, ...citationGroups.flat()], {
        unresolved_citations: unknown.map((cite) => cite.raw),
        citation_mismatch: names.length > 0 || known.length > 0,
      });
      let candidates;
      if (known.length) {
        candidates = citationGroups[0].filter((group) => citationGroups.every((list) => list.includes(group)));
        if (!candidates.length || (input.name && !candidates.some((group) => names.includes(group)))) {
          return rejected('citation-mismatch', text, [...names, ...citationGroups.flat()], { citation_mismatch: true });
        }
        if (input.name) candidates = candidates.filter((group) => names.includes(group));
      } else candidates = names;
      if (!candidates.length) return rejected('not-found', text);
      if (candidates.length > 1) return rejected('ambiguous', text, candidates);
      const group = candidates[0];
      // Retain source order: never select the maximum verification level.
      const authority = group.evidence.find((record) => record.branch !== 'persuasive') || group.evidence[0];
      const persuasiveOnly = group.evidence.every((record) => record.branch === 'persuasive');
      return {
        found: true, status: 'matched', identity_match: true, proposition_check: 'not-performed',
        matched_by: known.length ? (input.name ? 'citation and party name' : 'explicit citation') : 'party name',
        identity: identity(group), authority: { ...authority },
        evidence_records: group.evidence.map((record) => ({ ...record })),
        verification_levels: [...new Set(group.evidence.map((record) => record.verified || 'unverified'))],
        ...(persuasiveOnly ? { persuasive_only: true, hk_status: 'persuasive-only' } : {}),
        caution: identity(group).identity_kind === 'combined-case-record'
          ? 'The complete title of a combined case entry was matched. Its citations are associated with that stored entry; this lookup does not establish that they are parallel citations of one proceeding. All original sources and levels are retained.'
          : 'Only stored case identity was matched. Evidence retains its original source and verification level; no proposition was checked or verification upgraded.',
      };
    },
  };
}
