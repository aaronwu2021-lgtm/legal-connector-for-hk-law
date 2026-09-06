import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import handler from '../netlify/functions/api.mjs';

const base = () => ({
  sub_test: 'E3c',
  jurisdiction: 'HK',
  case: 'Synthetic Fixture v Test Case',
  citation: '[2026] SYN 1',
  court: 'Synthetic Test Court',
  year: 2026,
  treatment: 'clarifies',
  effect: 'Synthetic validation fixture; no legal proposition.',
});

async function rest(body) {
  const init = { method: 'POST', headers: { 'content-type': 'application/json' } };
  if (body !== undefined) init.body = JSON.stringify(body);
  const res = await handler(new Request('http://offline.invalid/api/maintenance/propose', init));
  return { status: res.status, body: await res.json() };
}

async function mcpCall(name, args) {
  const res = await handler(new Request('http://offline.invalid/api/mcp', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name, arguments: args } }),
  }));
  const envelope = await res.json();
  return JSON.parse(envelope.result.content[0].text);
}

async function mcpRaw(name, args) {
  const res = await handler(new Request('http://offline.invalid/api/mcp', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name, arguments: args } }),
  }));
  const envelope = await res.json();
  return { status: res.status, envelope, out: JSON.parse(envelope.result.content[0].text) };
}

async function mcpTools() {
  const res = await handler(new Request('http://offline.invalid/api/mcp', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/list', params: {} }),
  }));
  const envelope = await res.json();
  return envelope.result.tools;
}

const gatesSatisfied = (r) => (r.verification_gate || []).filter((g) => g.satisfied === true).length;

describe('amendment evidence validation', () => {
  it('accepts a minimal unverified proposal as pending review with no satisfied gates', async () => {
    const r = await rest({ ...base(), verified: 'unverified' });
    assert.equal(r.body.accepted, true);
    assert.deepEqual(r.body.errors, []);
    assert.equal(r.body.status, 'pending-independent-review');
    assert.equal(gatesSatisfied(r.body), 0);
    assert.ok(r.body.patch);
    assert.equal(r.body.patch.event.verified, 'unverified');
  });

  it('defaults omitted verification to unverified', async () => {
    const r = await rest(base());
    assert.equal(r.body.accepted, true);
    assert.equal(r.body.verification_level, 'unverified');
    assert.equal(r.body.patch.event.verified, 'unverified');
  });

  it('rejects a non-numeric year string', async () => {
    const r = await rest({ ...base(), year: 'not-a-year' });
    assert.equal(r.body.accepted, false);
    assert.ok(r.body.errors.length > 0);
    assert.equal(r.body.patch, null);
  });

  it('rejects numeric-string and array years', async () => {
    for (const year of ['2026', [2026], NaN, 2026.5, 1699, 2101]) {
      const r = await rest({ ...base(), year });
      assert.equal(r.body.accepted, false, `year ${JSON.stringify(year)} should reject`);
      assert.equal(r.body.patch, null);
    }
  });

  it('rejects a treatment that merely contains a valid word', async () => {
    const r = await rest({ ...base(), treatment: 'does not overrules' });
    assert.equal(r.body.accepted, false);
    assert.ok(r.body.errors.join(' ').includes('treatment must be one of'));
    assert.equal(r.body.patch, null);
  });

  it('rejects an unknown verification level', async () => {
    const r = await rest({ ...base(), verified: 'verified-primary-v2' });
    assert.equal(r.body.accepted, false);
    assert.equal(r.body.patch, null);
  });

  it('rejects null and array bodies without throwing', async () => {
    for (const bad of [null, [], ['x']]) {
      const r = await rest(bad);
      assert.equal(r.status < 500, true);
      assert.notEqual(r.body.accepted, true);
      assert.equal(r.body.patch, null);
      assert.ok(Array.isArray(r.body.errors) ? r.body.errors.length > 0 : !!r.body.error);
    }
  });

  it('rejects whitespace-only fields', async () => {
    const r = await rest({ ...base(), case: '   ', pin: '   ', verified: 'verified-primary' });
    assert.equal(r.body.accepted, false);
    assert.equal(r.body.patch, null);
  });

  it('rejects verified-primary without a pin', async () => {
    const r = await rest({ ...base(), verified: 'verified-primary' });
    assert.equal(r.body.accepted, false);
    assert.equal(r.body.patch, null);
    assert.equal(gatesSatisfied(r.body), 0);
  });

  it('rejects verified-quoted with a pin but no quoting source', async () => {
    const r = await rest({ ...base(), verified: 'verified-quoted', pin: '[1]' });
    assert.equal(r.body.accepted, false);
    assert.equal(r.body.patch, null);
  });

  it('rejects wrong-type and whitespace-only evidence', async () => {
    const a = await rest({ ...base(), verified: 'verified-primary', pin: 123 });
    assert.equal(a.body.accepted, false);
    const b = await rest({ ...base(), verified: 'verified-quoted', pin: '[1]', source: '   ' });
    assert.equal(b.body.accepted, false);
  });

  it('accepts valid primary and quoted proposals and preserves pin/source', async () => {
    const p = await rest({ ...base(), verified: 'verified-primary', pin: '[12]' });
    assert.equal(p.body.accepted, true);
    assert.equal(p.body.patch.event.pin, '[12]');
    assert.equal(p.body.patch.event.verified, 'verified-primary');
    const q = await rest({ ...base(), verified: 'verified-quoted', pin: '[12]', source: 'Synthetic Quoting Judgment [2026] SYN 2 at [5]' });
    assert.equal(q.body.accepted, true);
    assert.equal(q.body.patch.event.pin, '[12]');
    assert.equal(q.body.patch.event.source, 'Synthetic Quoting Judgment [2026] SYN 2 at [5]');
  });

  it('never marks gates satisfied from the submitted level alone', async () => {
    for (const v of ['unverified', 'verified-web', 'verified-quoted', 'verified-primary']) {
      const extra = v === 'verified-primary' ? { pin: '[1]' } : v === 'verified-quoted' ? { pin: '[1]', source: 'Synthetic Quoting Judgment' } : {};
      const r = await rest({ ...base(), verified: v, ...extra });
      assert.equal(gatesSatisfied(r.body), 0, `level ${v} must not satisfy gates`);
      assert.equal(r.body.status, 'pending-independent-review');
    }
  });

  it('rejects unknown jurisdiction/node', async () => {
    const a = await rest({ ...base(), jurisdiction: 'XX' });
    assert.equal(a.body.accepted, false);
    const b = await rest({ ...base(), sub_test: 'NOPE', jurisdiction: 'HK' });
    assert.equal(b.body.accepted, false);
  });

  it('matches REST and MCP behavior', async () => {
    const invalid = { ...base(), year: 'not-a-year' };
    const rr = await rest(invalid);
    const mr = await mcpCall('propose_amendment', invalid);
    assert.equal(rr.body.accepted, false);
    assert.equal(mr.accepted, false);
    assert.equal(rr.body.patch, null);
    assert.equal(mr.patch, null);
    const valid = { ...base(), verified: 'verified-primary', pin: '[3]' };
    const rv = await rest(valid);
    const mv = await mcpCall('propose_amendment', valid);
    assert.equal(rv.body.accepted, true);
    assert.equal(mv.accepted, true);
    assert.equal(mv.patch.event.pin, '[3]');
  });

  it('keeps the MCP schema consistent with runtime validation', async () => {
    const tools = await mcpTools();
    const t = tools.find((x) => x.name === 'propose_amendment');
    assert.ok(t);
    assert.equal(t.inputSchema.properties.year.type, 'integer');
    assert.equal(t.inputSchema.properties.year.minimum, 1700);
    assert.equal(t.inputSchema.properties.year.maximum, 2100);
    assert.deepEqual(t.inputSchema.properties.jurisdiction.enum, ['EN', 'HK', 'SG', 'AU']);
    assert.ok(t.inputSchema.properties.treatment.enum.includes('overrules'));
    assert.ok(t.inputSchema.properties.verified.enum.includes('verified-primary'));
    assert.ok(t.inputSchema.properties.pin);
    assert.ok(t.inputSchema.properties.source);
  });

  it('rejects non-finite and non-numeric favor', async () => {
    for (const favor of [null, 'high', [1], { v: 1 }, NaN, Infinity]) {
      const r = await rest({ ...base(), favor });
      assert.equal(r.body.accepted, false, `favor ${String(favor)} should reject`);
      assert.equal(r.body.patch, null);
    }
    const m = await mcpCall('propose_amendment', { ...base(), favor: 'high' });
    assert.equal(m.accepted, false);
    assert.equal(m.patch, null);
  });

  it('accepts a finite favor and preserves it', async () => {
    const r = await rest({ ...base(), favor: 0.5 });
    assert.equal(r.body.accepted, true);
    assert.equal(r.body.patch.event.f, 0.5);
  });

  it('rejects null pin/source even when otherwise valid', async () => {
    for (const extra of [{ pin: null }, { source: null }, { pin: null, source: null }]) {
      const r = await rest({ ...base(), ...extra });
      assert.equal(r.body.accepted, false, `unverified with ${JSON.stringify(extra)} should reject`);
      assert.equal(r.body.patch, null);
    }
    const p = await rest({ ...base(), verified: 'verified-primary', pin: null });
    assert.equal(p.body.accepted, false);
    const q = await rest({ ...base(), verified: 'verified-quoted', pin: '[1]', source: null });
    assert.equal(q.body.accepted, false);
  });

  it('accepts boundary years 1700 and 2100', async () => {
    for (const year of [1700, 2100]) {
      const r = await rest({ ...base(), year });
      assert.equal(r.body.accepted, true, `year ${year} should accept`);
      assert.ok(r.body.patch);
    }
    for (const year of [1699, 2101]) {
      const r = await rest({ ...base(), year });
      assert.equal(r.body.accepted, false, `year ${year} should reject`);
      assert.equal(r.body.patch, null);
    }
  });

  it('rejects malformed required string types', async () => {
    for (const field of ['sub_test', 'jurisdiction', 'case', 'citation', 'court', 'treatment', 'effect']) {
      for (const value of [123, ['x'], { text: 'x' }, null]) {
        const r = await rest({ ...base(), [field]: value });
        assert.equal(r.body.accepted, false, `${field}=${JSON.stringify(value)} should reject`);
        assert.equal(r.body.patch, null);
      }
    }
  });

  it('marks rejected MCP amendments as errors without changing other tools', async () => {
    const bad = await mcpRaw('propose_amendment', { ...base(), year: 'not-a-year' });
    assert.equal(bad.out.accepted, false);
    assert.equal(bad.out.patch, null);
    assert.equal(bad.envelope.result.isError, true);
    assert.ok(bad.envelope.result.content[0].text.includes('"accepted": false'));
    const good = await mcpRaw('propose_amendment', { ...base(), verified: 'verified-primary', pin: '[3]' });
    assert.equal(good.out.accepted, true);
    assert.ok(!good.envelope.result.isError);
    const other = await mcpRaw('get_elements', {});
    assert.ok(!other.envelope.result.isError);
    assert.ok(other.out.claim);
  });

  it('makes no network calls and writes nothing to the dataset', async () => {
    const calls = [];
    const realFetch = globalThis.fetch;
    globalThis.fetch = async (input) => { calls.push(String(input)); throw new Error('network forbidden in test'); };
    try {
      const before = await handler(new Request('http://offline.invalid/api/maintenance'));
      const beforeBody = await before.json();
      const v1 = await rest({ ...base(), verified: 'verified-primary', pin: '[9]' });
      assert.equal(v1.body.accepted, true);
      await rest({ ...base(), year: 'not-a-year' });
      await mcpCall('propose_amendment', { ...base(), favor: 'high' });
      const v2 = await rest({ ...base(), verified: 'verified-primary', pin: '[9]' });
      assert.deepEqual(v2.body.node_before, v1.body.node_before);
      const after = await handler(new Request('http://offline.invalid/api/maintenance'));
      assert.deepEqual(await after.json(), beforeBody);
      assert.equal(calls.length, 0);
    } finally {
      globalThis.fetch = realFetch;
    }
  });
});
