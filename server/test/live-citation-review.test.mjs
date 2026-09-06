import {test, after, afterEach} from 'node:test';
import assert from 'node:assert/strict';
import {liveCitation} from '../netlify/functions/live-citation.mjs';
import handler from '../netlify/functions/api.mjs';
import ELEMENTS from '../netlify/functions/_elements.mjs';
import PERSUASIVE from '../netlify/functions/_persuasive.mjs';

// All responses below are synthetic. No live source, builder or data mutation.
const savedFetch = globalThis.fetch;
const stored = JSON.stringify({ELEMENTS, PERSUASIVE});
let unexpectedNetwork = 0;
const denied = async () => { unexpectedNetwork++; throw Error('Review is offline'); };
globalThis.fetch = denied;
afterEach(() => { globalThis.fetch = denied; });
after(() => {
  globalThis.fetch = savedFetch;
  assert.equal(unexpectedNetwork, 0);
  assert.equal(JSON.stringify({ELEMENTS, PERSUASIVE}), stored);
});

const cite = '[2022] HKCFA 25';
const unresolved = {found: false, status: 'unresolved-citation'};
const fixture = {neutral: cite, db: 'Court of Final Appeal', date: '2022-12-12T00:00:00+08:00',
  content: '<html><head><title>Synthetic judgment</title></head><body>Synthetic text</body></html>'};
const jsonResponse = (value, extra = {}) => new Response(JSON.stringify(value), {
  ...extra, headers: {'content-type': 'application/json', ...extra.headers},
});
const unknown = (result) => {
  assert.equal(result.exists, null, JSON.stringify(result));
  assert.equal(result.proposition_check, 'not-performed');
  assert.equal(result.verified, undefined);
};
const retrieve = (response) => liveCitation(cite, unresolved, {fetcher: async () => response});
async function rest(citation, params = {}) {
  const response = await handler(new Request('http://offline.invalid/api/verify?' +
    new URLSearchParams({cite: citation, ...params})));
  return {status: response.status, body: await response.json()};
}

test('review: valid HKLII-shaped JSON confirms only neutral retrieval', async () => {
  const local = {found: true, authority: {verified: 'verified-quoted', pin: '[7]', source: 'original source'}};
  const before = JSON.stringify(local);
  const result = await liveCitation(cite, local, {fetcher: async (url, options) => {
    assert.equal(new URL(url).origin, 'https://www.hklii.hk');
    assert.equal(options.redirect, 'error');
    assert.equal(options.headers.accept, 'application/json');
    return jsonResponse(fixture);
  }});
  assert.equal(result.status, 'matched-neutral');
  assert.equal(result.identity_scope, 'neutral-citation-only');
  assert.equal(result.proposition_check, 'not-performed');
  assert.equal(result.exists, true);
  assert.equal(result.date, '2022-12-12');
  assert.equal(result.verified, undefined);
  assert.equal(result.pin, undefined);
  assert.equal(result.content, undefined);
  assert.equal(JSON.stringify(local), before);
});

test('review: redirected success responses are rejected even if a fetch adapter ignored redirect:error', async () => {
  const response = jsonResponse(fixture);
  Object.defineProperty(response, 'redirected', {value: true});
  unknown(await retrieve(response));
});

for (const status of [301, 302, 307, 308, 403, 404, 429, 502]) {
  test(`review: HTTP ${status} never asserts nonexistence`, async () => {
    const result = await retrieve(new Response('upstream response', {status, headers: {location: 'https://invalid.example/'}}));
    unknown(result);
    assert.equal(result.http_status, status);
    if (status === 404) {
      assert.equal(result.status, 'english-version-unavailable');
      assert.equal(result.english_judgment_available, false);
    }
  });
}

test('review: malformed successful bodies remain unknown', async () => {
  const responses = [
    new Response('<html>Login page</html>', {headers: {'content-type': 'text/html'}}),
    new Response('<html>Error page</html>', {headers: {'content-type': 'application/json'}}),
    new Response(new Uint8Array([0xc3, 0x28]), {headers: {'content-type': 'application/json'}}),
    new Response(null, {status: 204}),
    jsonResponse({message: 'not found'}),
    jsonResponse({...fixture, neutral: '[2023] HKCFA 16'}),
    jsonResponse({...fixture, content: '  '}),
    jsonResponse({...fixture, date: '2022-12-12 trailing-junk'}),
    jsonResponse({...fixture, date: '2022-12-12T99:99:99+08:00'}),
    jsonResponse({...fixture, date: '2022-02-30T00:00:00+08:00'}),
  ];
  for (const response of responses) unknown(await retrieve(response));
});

test('review: declared oversized bodies are cancelled without reading them', async () => {
  let reads = 0, cancelled = 0;
  const body = new ReadableStream({pull() {reads++;}, cancel() {cancelled++;}}, {highWaterMark: 0});
  const response = new Response(body, {headers: {'content-type': 'application/json', 'content-length': '9999999'}});
  unknown(await retrieve(response));
  assert.equal(reads, 0);
  assert.equal(cancelled, 1);
});

test('review: streaming size limit counts actual bytes despite a false small header', async () => {
  let reads = 0, cancelled = 0;
  const body = new ReadableStream({
    pull(controller) {reads++; controller.enqueue(new Uint8Array(1024 * 1024));},
    cancel() {cancelled++;},
  }, {highWaterMark: 0});
  unknown(await retrieve(new Response(body, {headers: {'content-type': 'application/json', 'content-length': '1'}})));
  assert.equal(reads, 5);
  assert.equal(cancelled, 1);
});

test('review: timeout during body reading is unknown and does not leak partial content', async () => {
  const originalTimeout = AbortSignal.timeout;
  const aborter = new AbortController();
  AbortSignal.timeout = (ms) => {assert.equal(ms, 10000); return aborter.signal;};
  try {
    const result = await liveCitation(cite, unresolved, {fetcher: async (_url, {signal}) => {
      const body = new ReadableStream({start(controller) {
        controller.enqueue(new TextEncoder().encode('{"private":"partial body"'));
        signal.addEventListener('abort', () => controller.error(signal.reason), {once: true});
        queueMicrotask(() => aborter.abort(new DOMException('private timeout reason', 'TimeoutError')));
      }});
      return new Response(body, {headers: {'content-type': 'application/json'}});
    }});
    unknown(result);
    assert.equal(result.status, 'upstream-timeout');
    assert.doesNotMatch(JSON.stringify(result), /private|partial body/);
  } finally {AbortSignal.timeout = originalTimeout;}
});

test('review: transport redirect failures are unavailable and expose no exception payload', async () => {
  const result = await liveCitation(cite, unresolved, {fetcher: async () => {throw new TypeError('secret redirect destination');}});
  unknown(result);
  assert.equal(result.status, 'upstream-unavailable');
  assert.doesNotMatch(JSON.stringify(result), /secret redirect/);
});

test('review: conflicting or unresolved identities cannot be rescued by online positives', async () => {
  let calls = 0;
  globalThis.fetch = async () => {calls++; return jsonResponse(fixture);};
  for (const query of [
    'Hayward v Zurich ' + cite,
    'Derry v Peek ' + cite,
    '[2021] HKCFA 40; [2099] UKSC 9',
    'Unrecorded v Parties ' + cite,
  ]) {
    const result = await rest(query);
    assert.equal(result.status, 200);
    assert.equal(result.body.found, false, JSON.stringify(result.body));
    unknown(result.body.hklii);
  }
  assert.equal(calls, 0);
});

test('review: historical requests block online titles, holdings and source URLs for all valid date forms', async () => {
  let calls = 0;
  globalThis.fetch = async () => {calls++; return jsonResponse({...fixture, content: '<html><title>FUTURE_MARKER</title>FUTURE_HOLDING</html>'});};
  for (const as_of of ['1990', '2022', '2022-12-11', '2022-12-12', '2026-09-05']) {
    const result = await rest(cite, {as_of});
    assert.equal(result.status, 200);
    assert.equal(result.body.hklii.status, 'not-requested-historical');
    unknown(result.body.hklii);
    assert.doesNotMatch(JSON.stringify(result.body.hklii), /FUTURE_|getjudgment|2022-12-12/);
  }
  for (const as_of of ['', 'bad', '2022-02-30']) {
    assert.equal((await rest(cite, {as_of})).status, 400);
  }
  assert.equal(calls, 0);
});

test('review: online retrieval does not upgrade local source records or turn an unlisted neutral into a catalogue hit', async () => {
  let calls = 0;
  globalThis.fetch = async (url) => {
    calls++;
    const query = new URL(url).searchParams;
    return jsonResponse({...fixture, neutral: `[${query.get('year')}] ${query.get('abbr').toUpperCase()} ${query.get('num')}`,
      date: `${query.get('year')}-01-01T00:00:00+08:00`});
  };
  const known = '[2021] HKCFA 40';
  const offline = (await rest(known, {live: '0'})).body;
  assert.equal(offline.found, true);
  const online = (await rest(known)).body;
  assert.equal(online.hklii.exists, true);
  delete online.hklii;
  assert.deepEqual(online, offline);
  const unlisted = (await rest(cite)).body;
  assert.equal(unlisted.found, false);
  assert.equal(unlisted.hklii.exists, true);
  assert.equal(unlisted.hklii.identity_scope, 'neutral-citation-only');
  assert.equal(unlisted.proposition_check, 'not-performed');
  assert.equal(calls, 2);
});
