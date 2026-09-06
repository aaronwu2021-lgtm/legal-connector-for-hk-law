# Live citation — independent offline review

Recorded 2026-09-05 23:09 UTC. This freezes the observed result for the hashes below; later changes require a new acceptance record.

**18/18 independent tests passed** with `node --test test/live-citation-review.test.mjs` from `server/`. No actual network requests or builders were used. The test's unexpected-network counter remained zero, stored evidence snapshots were unchanged, and the historical 100-file protected SHA-256 baseline was independently rechecked 100/100 unchanged.

The positive fixture uses the provided HKLII response shape: neutral citation, ISO date with +08:00 offset, full database name and HTML content. It is synthetic and does not establish that this reviewer read an actual judgment.

## Verified behavior

- A valid response identifies only the neutral citation retrieved. It does not check party names, pins or propositions, upgrade catalogue verification, or expose the judgment body as verified evidence.
- A positive online result cannot override a conflicting citation/name, an unresolved named query, or inconsistent parallel citations. Such queries made no fetch call.
- Year-only and full-date historical requests add no live title, judgment text or source URL. Invalid historical dates are rejected before any fetch.
- HTTP 301/302/307/308/403/404/429/502 responses leave existence unknown. An English-endpoint 404 reports English-version unavailability, not case nonexistence.
- Redirected 200 responses are rejected, even when a mock fetch adapter ignores the requested redirect policy.
- HTML/error pages, invalid JSON, invalid UTF-8, empty bodies, malformed calendar/time strings and mismatched neutral metadata do not produce successful verification.
- Declared oversized bodies are cancelled without reading; streaming responses are limited by actual received bytes even with a false small Content-Length header. The streamed overflow test confirmed cancellation on the fifth 1 MiB chunk.
- A simulated timeout during body reading yields an unknown/timeout result without leaking partial content or exception text. This tests abort handling deterministically; it does not wait for a real ten-second network timeout.
- For a catalogue match, the live response preserves the complete offline evidence result. For an unlisted bare neutral, successful retrieval leaves the catalogue `found` value false.

## Findings addressed during review

An injected successful response with `redirected: true` originally yielded `matched-neutral`. Native fetch should reject a redirect under `redirect: 'error'`; an explicit guard was added for adapters that ignore that policy.

A declared oversized response originally returned an invalid result without cancelling its body. Early body cancellation was added. Both reproductions are retained as passing regression tests. The implementation changes were made by the root agent; this reviewer added only the independent test and this report.

## Observed source hashes

```text
server/netlify/functions/live-citation.mjs 75cfec3906499bdb933c2a0b7d7f9ddb46421bedf7b06d9fed7fab5783f61f58
server/netlify/functions/api.mjs 29b4f792a350657aad704aed344ecf9e3585e2bbb5d539a8fb6dcb0620a5c857
server/test/live-citation-review.test.mjs 5b985bf3171ae3dad87295029858da6345f41e025a84c586c365a2c48f966822
```

This is an engineering acceptance result, not a legal-source verification or a completeness claim about the underlying library.
