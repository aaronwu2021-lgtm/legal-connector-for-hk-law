// Offline acceptance probe for five API findings recorded on 2026-09-05.
// Run from the repository root, with no npm install:
//   node scripts/audit_api_contract.mjs
// To also save a NEW report (an existing file is never overwritten):
//   node scripts/audit_api_contract.mjs --output docs/review/2026-09-05-api-baseline.json
// Exit 0 = all five invariants hold; exit 1 = unresolved findings or probe error.
// The handler is called directly. No HTTP server or external service is used.

import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const deniedFetches = [];
globalThis.fetch = async (input) => {
  const address = input instanceof Request ? input.url : String(input);
  deniedFetches.push(address);
  throw new Error('Network access is forbidden in the offline API audit');
};

const handler = (await import('../server/netlify/functions/api.mjs')).default;

async function request(route, body) {
  const method = body === undefined ? 'GET' : 'POST';
  const response = await handler(new Request(`http://offline.invalid/api/${route}`, {
    method,
    ...(body === undefined ? {} : {
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    }),
  }));
  return { status: response.status, body: await response.json() };
}

const successful = (response) => response.status >= 200 && response.status < 300;
const numeric = (value) => typeof value === 'number' && Number.isFinite(value);
const cases = [];

async function probe(id, requests, desiredInvariant, inspect) {
  const initialFetchCount = deniedFetches.length;
  try {
    const { observed, pass } = await inspect();
    cases.push({
      id, request: requests, desired_invariant: desiredInvariant, observed,
      pass: Boolean(pass) && deniedFetches.length === initialFetchCount,
    });
  } catch (error) {
    cases.push({
      id, request: requests, desired_invariant: desiredInvariant,
      observed: { probe_error: String(error?.message || error) }, pass: false,
    });
  }
}

const proposal = {
  sub_test: 'E3c', jurisdiction: 'HK', case: 'Offline audit fixture',
  citation: '[2026] HKCFA 1', court: 'CFA', year: 2026,
  treatment: 'clarifies', effect: 'Synthetic validation fixture; no legal proposition.',
  verified: 'unverified',
};
const invalidProposals = [
  ['primary_without_pin', { ...proposal, verified: 'verified-primary' }],
  ['quoted_without_quoting_source', { ...proposal, verified: 'verified-quoted', pin: '[1]' }],
  ['invalid_verification_level', { ...proposal, verified: 'invented-level' }],
  ['nonnumeric_year', { ...proposal, year: 'not-a-year' }],
  ['treatment_substring', { ...proposal, treatment: 'does not overrules' }],
];

await probe('A01-amendment-validation', invalidProposals.map(([label, body]) => ({
  label, method: 'POST', path: '/api/maintenance/propose', body,
})), 'Every structurally invalid proposal is rejected with an error and no patch; selecting a verification level alone must not certify the evidence gates.', async () => {
  const observed = [];
  for (const [label, body] of invalidProposals) {
    const result = await request('maintenance/propose', body);
    observed.push({
      label, status: result.status, accepted: result.body.accepted,
      errors: result.body.errors || result.body.error || null,
      patch_returned: result.body.patch != null,
      gates_claimed_satisfied: (result.body.verification_gate || []).filter((gate) => gate.satisfied === true).length,
    });
  }
  return {
    observed,
    pass: observed.every((row) => row.status < 500 && row.accepted !== true
      && !row.patch_returned && row.gates_claimed_satisfied === 0
      && (row.status >= 400 || (Array.isArray(row.errors) ? row.errors.length > 0 : Boolean(row.errors)))),
  };
});

await probe('A02-unknown-evidence', {
  method: 'POST', path: '/api/score', body: { module: 'HKJUR', facts: {} },
}, 'With every fact unknown, scoring must remain undetermined: no decisive zero-width balance and no assertion that an unknown clause is absent.', async () => {
  const result = await request('score', { module: 'HKJUR', facts: {} });
  const stages = result.body.stages || [];
  const balances = stages.filter((stage) => stage.test_type === 'balancing');
  const threshold = stages.find((stage) => stage.stage === 'HKJUR-4');
  const balanceUncertain = balances.length > 0 && balances.every((stage) => {
    const noInterval = stage.score_low == null && stage.score_high == null;
    const openInterval = numeric(stage.score_low) && numeric(stage.score_high)
      && stage.score_low < stage.score_high && stage.score_low <= 0 && stage.score_high >= 0;
    return stage.interval_decides !== true && (noInterval || openInterval);
  });
  const overall = String(result.body.overall || '');
  return {
    observed: {
      status: result.status, overall: result.body.overall,
      balancing_stages: balances.map(({ stage, score_low, score_high, evidence_resolved, interval_decides, band }) =>
        ({ stage, score_low, score_high, evidence_resolved, interval_decides, band })),
      clause_stage: threshold && { engaged: threshold.engaged, result: threshold.result },
    },
    pass: successful(result) && balanceUncertain && Boolean(threshold)
      && threshold.engaged !== false && !['not-engaged', 'clause-enforced'].includes(threshold.result)
      && /undetermined|unknown|insufficient|unresolved|incomplete|not.computed|awaiting/i.test(overall),
  };
});

await probe('A03-conjunctive-type', {
  method: 'POST', path: '/api/score', body: { module: 'CONTRACT', facts: {} },
}, 'The CT-1 conjunctive stage returns its unresolved elements without numeric scoring or describing its weights as awaiting calibration.', async () => {
  const result = await request('score', { module: 'CONTRACT', facts: {} });
  const stage = (result.body.stages || []).find((item) => item.stage === 'CT-1');
  const commentary = [stage?.reason, stage?.caveat, stage?.note].filter(Boolean).join(' ');
  return {
    observed: {
      status: result.status, stage: stage?.stage, test_type: stage?.test_type,
      weights: stage?.weights, reason: stage?.reason, caveat: stage?.caveat,
      unresolved_count: stage?.unresolved?.length || 0,
    },
    pass: successful(result) && stage?.test_type === 'conjunctive'
      && (stage.unresolved || []).length > 0
      && !['score', 'score_low', 'score_high', 'score_mid'].some((field) => numeric(stage[field]))
      && stage.weights !== 'unassigned' && !/balancing|calibrat|regression/i.test(commentary),
  };
});

function futureAuthorities(value, cutoff, location = '$', results = []) {
  if (!value || typeof value !== 'object') return results;
  if (!Array.isArray(value) && (value.case || value.name)) {
    const citationYear = String(value.cite || value.citation || '').match(/[\[(](\d{4})[\])]/)?.[1];
    const year = Number(value.year || citationYear);
    if (year > cutoff) {
      const flagged = value.anachronistic === true || value.future === true || value.is_future === true
        || value.excluded === true || value.eligible_at_as_of === false || value.in_force_at_as_of === false;
      results.push({ location, case: value.case || value.name, year, explicitly_flagged: flagged });
    }
  }
  for (const [key, child] of Object.entries(value)) futureAuthorities(child, cutoff, `${location}.${key}`, results);
  return results;
}

await probe('A04-historical-authorities', {
  method: 'GET', path: '/api/checklist?jurisdiction=HK&as_of=1990',
}, 'A checklist dated 1990 must omit authorities from later years or explicitly mark each as unavailable at that date, including backbone, local, related, and defence authorities.', async () => {
  const result = await request('checklist?jurisdiction=HK&as_of=1990');
  const future = futureAuthorities(result.body, 1990);
  const unflagged = future.filter((authority) => !authority.explicitly_flagged);
  return {
    observed: {
      status: result.status, as_of: result.body.as_of,
      future_authority_count: future.length, unflagged_future_authority_count: unflagged.length,
      examples: unflagged.slice(0, 8),
    },
    pass: successful(result) && Number(result.body.as_of) === 1990
      && Array.isArray(result.body.elements) && result.body.elements.length > 0 && unflagged.length === 0,
  };
});

const conflictingCitation = 'Hayward v Zurich Insurance Co plc [2099] UKSC 999';
const verifyPath = `verify?live=0&cite=${encodeURIComponent(conflictingCitation)}`;
await probe('A05-citation-conflict', { method: 'GET', path: `/api/${verifyPath}` },
  'A known party name with an explicitly conflicting neutral citation must be rejected or labelled as a citation mismatch; a name match alone cannot verify the supplied citation.', async () => {
    const result = await request(verifyPath);
    const body = result.body;
    const warnings = [body.warning, body.citation_warning, body.mismatch_warning, body.caution, body.error]
      .filter(Boolean).join(' ');
    const mismatch = body.citation_mismatch === true || body.citation_conflict === true || body.mismatch === true
      || body.citation_matches === false || body.citation_verified === false
      || /citation[-_ ]mismatch|citation[-_ ]conflict/.test(String(body.status || ''))
      || /mismatch|conflict|does not match|incorrect|different citation|not match|invalid|disagree/i.test(warnings);
    return {
      observed: {
        status: result.status, found: body.found, matched_by: body.matched_by,
        returned_citation: body.authority?.cite, verification_level: body.authority?.verified,
        explicit_mismatch: mismatch, warnings: warnings || null,
      },
      pass: successful(result) && (body.found === false || mismatch),
    };
  });

const report = {
  audit: 'offline-api-contract', recorded_at: new Date().toISOString(),
  network: { allowed: false, attempts: deniedFetches.length },
  total: cases.length, passed: cases.filter((item) => item.pass).length,
  failed: cases.filter((item) => !item.pass).length,
  cases,
};
const output = `${JSON.stringify(report, null, 2)}\n`;
process.stdout.write(output);
process.exitCode = report.failed > 0 || deniedFetches.length > 0 ? 1 : 0;

const arguments_ = process.argv.slice(2);
if (arguments_.length) {
  if (arguments_.length !== 2 || arguments_[0] !== '--output') {
    throw new Error('Usage: node scripts/audit_api_contract.mjs [--output NEW_REPORT.json]');
  }
  const reportPath = path.resolve(arguments_[1]);
  await mkdir(path.dirname(reportPath), { recursive: true });
  await writeFile(reportPath, output, { encoding: 'utf8', flag: 'wx' });
}
