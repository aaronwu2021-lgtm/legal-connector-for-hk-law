# OpenCode task 03b: strict historical projection

Status: implemented by Codex and independently accepted (28 historical tests, original A01–A05 probe all passing). See `task03-acceptance-2026-09-05.md`. The original specification follows.

Run only after 03a is accepted. Use the selected free model; no paid fallback. Read `CLAUDE.md`. Preserve existing work, citation behavior, and tests. No builder execution/import, generated-data changes, verification upgrades, external requests, commits, push, or deployment. A builder's `--help` is not safe to run.

## Scope

Allowed: date parsing, historical response projection, and corresponding schema paths in `server/netlify/functions/api.mjs`; new `server/test/historical.test.mjs`; a small private historical helper if needed. Do not rewrite citation identity matching, scoring, live retrieval, UI, existing tests, or the independent audit. Preserve encoding and unrelated bytes. Temporary helpers belong under `.git/codex-review/`.

The historical API must report only what the encoded dates/provenance support. It must not present today's prose as doctrine at an earlier date. Do not fill missing history with legal inference.

## Required behavior

1. Use one `as_of` parser everywhere. Accept integer/string four-digit years as end-of-year cutoffs and valid `YYYY-MM-DD` dates; reject booleans, malformed dates, fractions, nonfinite values, and years outside the documented four-digit range. Do not default an explicitly invalid cutoff to the current view. A year-only authority date cannot establish eligibility earlier within that year; omit it for a same-year precise-date query unless a compatible full decision date is stored, and report the precision limitation.
2. With any valid cutoff, use a strict projection by default. Omit future authorities/events and their names, holdings, notes, and source prose from research responses, including nested parent/sibling objects. Do not reintroduce them under excluded/debug/audit fields. Exclusion counts and reason codes are sufficient.
3. Build historical results from an allowlist of safe fields, not regex removal from prose. Stable structural IDs/titles and eligible identity metadata may remain. Current unversioned tests, statutes, notes, holdings, effects, jurisdiction rules, gaps, and summaries must be withheld unless structured effective dates/provenance establish them at the cutoff. Return an explicit `historical-rule-not-modelled` gap instead. In particular, a 2013 event's current effect mentioning the 2016 English position must not leak through.
4. Retained evidence keeps its original pin, source, verification level, and location. Where source chronology cannot be established safely, withhold the evidence record and explain by count/gap; do not strip the quoting source while retaining a verification label. A quoted 1991 authority verified through later judgments is not automatically safe evidence for 1991. Keep identity-only metadata distinct from evidence and from a legal proposition.
5. Apply the projection to checklist, timeline, element, and corresponding MCP tools. Add optional `as_of` to `get_elements` so historical requests are not silently ignored. Preserve safe rank/recency metadata and the distinction between standing/latest authority, while explicitly withholding unmodelled historical rule text. Do not return an unfiltered parent element around a filtered child.
6. For a direct query naming a case later than the cutoff, an identity-only result may state `identity_exists:true` and `usable_at_as_of:false`, without future holdings or source prose. Keep this distinct from citation mismatch. No-cutoff responses retain complete current provenance and useful existing content. Do not change live lookup behavior in this task.

## Acceptance

Test complete serialized REST/MCP responses, not only `standing_rules`: the 1990 checklist, nested backbone/local/related/defence evidence, future timeline entries/current notes, and the retrospective SG 2013 T2 effect. Include leap/invalid dates, explicit null/boolean cutoffs, same-year precision limits, eligible safe metadata, direct future-case identities, and no-cutoff provenance preservation. Use stored fixtures; deny all network access.

Run syntax checks and all offline tests. The unchanged independent audit must pass A01-A05. Report exact changed files, test counts, date/provenance limitations, and unmodelled historical content. Stop for Codex review; software acceptance does not certify legal accuracy.
