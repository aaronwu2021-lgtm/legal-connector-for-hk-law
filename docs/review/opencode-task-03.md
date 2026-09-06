# OpenCode task 03: citation identity and strict historical projections

Execute only after task02 is accepted. Codex directs and independently reviews; OpenCode implements using the selected Muse Spark 1.3 Free model. Read CLAUDE.md. Preserve all existing work and completed tests. No paid calls, actual external legal retrieval, commits, push, deployment, builder execution/import, generated data edits, or source verification upgrades. A builder called with --help still executes: never do this.

Allowed files: citation/temporal/API-schema paths in `server/netlify/functions/api.mjs`, new tests in `server/test/citation.test.mjs` and `server/test/historical.test.mjs`; small new private helper modules under `server/netlify/functions/` if they improve clarity. Do not edit existing audit probe or baseline. Preserve unrelated bytes, including the preexisting NUL in api.mjs, instead of rewriting encoding across the file. Temporary helpers must live under the task's `.git/codex-review/` directory, not be left in the project root.

## A05: distinguish identity matching from verifying a proposition

Reproductions through local `/api/verify?live=0`:

- `Hayward v Zurich [2016] UKSC 999` currently ignores the wrong number and reports success by name.
- `Derry v Peek [2016] UKSC 48` currently returns Hayward despite conflicting names.
- A BV Nederlandse name with `[2019] EWCA Civ 999` ignores the wrong number; multiword court abbreviations are not parsed.
- `DBS Bank (HK)` arbitrarily selects one of multiple cases.
- `Long Year Development` drops its quoting source from the projected authority while retaining verified-quoted.

Required behavior:

1. Match submitted citation and case name independently and require consistency when both are present. An explicit citation that does not match cannot fall back to a successful fuzzy name match. Return found:false plus conflict/mismatch status and optional identity-only suggestions; no verified proposition on a conflicting match. An unknown citation is a library coverage statement, not proof of nonexistence.
2. Recognize neutral citations including EWCA Civ/Crim and other court tokens in existing data; keep report citations distinct (e.g. [2020] QB 551). Normalize harmless whitespace/case, not years/court/numbers. Do not silently ignore a second conflicting explicit citation. Multiple valid parallel citations may refer to one case.
3. Name-only ambiguous queries return candidates and ambiguity, not whichever entry comes first. Deduplicate repeated locations for the same identity without elevating verification to the maximum or dropping lower-level source evidence. A supplied second-party name must not be ignored. Account for common abbreviated names already in the data without silently accepting contradictory names.
4. Apply identical identity-consistency rules to the core and persuasive indexes. A persuasive fallback cannot override a core conflict and always remains unverified/persuasive-only. Keep source, pin, original verification and record location for each matched authority. Report identity match separately from `proposition_check:"not-performed"`; the lookup does not read a judgment or check the user's proposition.
5. Live HKLII lookup remains a separately reported optional REST observation. HTTP 200 alone is not existence verification. Check shape and returned neutral citation, handle empty/wrong/malformed/404/403/429/500/network results distinctly, and never override a local conflict or upgrade library verification. Mock every live response in tests; no actual network calls. A language-specific miss is not global nonexistence.

## A04: no future content in a historical research response

Current failure extends beyond authority dates: the 1990 checklist lists 1991–2026 authorities; timelines return future events and current notes; even the eligible SG 2013 T2 event's present-day `eff` mentions England's 2016 result. A current paraphrase attached to an old event is not a proven historical rule.

Required behavior:

6. Use one shared as_of parser. Preserve numeric/string four-digit years as end-of-year queries; also accept real ISO YYYY-MM-DD calendar dates. Reject invalid dates, NaN, booleans and out-of-range years explicitly. Do not guess Jan 1 for year-only authority dates: a same-year authority cannot be proved eligible for an earlier precise date unless an explicit compatible decision date exists. Explain date precision limits.
7. Any as_of research response uses a strict historical projection by default. Omit future authorities/events/content entirely; do not move their holdings, notes, source snippets or names into the same response under audit/debug/excluded fields. Exclusion counts and reason codes are sufficient. With no as_of, preserve current-data functionality and original provenance.
8. Use an allowlist of historical fields, not regex cleaning of prose. Do not expose current unversioned `test`, statute descriptions, notes, holdings, effect text, jurisdiction rules, gaps or summaries as historical doctrine merely because a nearby judgment has an earlier year. When the data does not encode the effective interval/provenance necessary to establish that prose at the cutoff, return an explicit historical-rule-not-modelled gap and safe eligible identity metadata. Stable structural IDs/titles can remain. Do not fabricate historical rule text.
9. Preserve pin/source/verified on any returned evidence record. If provenance cannot safely be shown for a historical date (e.g. a quoted 1991 authority verified through 2018/2024/2026 judgments, with no structured quoting-source date), withhold the evidence record and emit a gap/count rather than strip the source and silently imply primary verification. Unknown source-date precision is a limitation. Current views still expose the original complete evidence.
10. Apply the same projection to checklist, timeline, element and corresponding MCP tools. Add optional as_of to get_elements if necessary so explicitly supplied historical requests cannot silently receive current full text. Do not leave a parent element containing all its unfiltered siblings inside a supposedly filtered child result. For timeline ranking retain rank/recency distinctions and safe metadata; unknown historical rule text stays explicitly unmodelled.
11. A direct query for an identified case later than as_of may state identity_exists/usable_at_as_of:false, but cannot include its future substantive holding or source prose. Keep identity mismatch distinct from historical ineligibility. Do not imply that a found case is applicable authority.
12. Cover REST and MCP both. Test full serialized historical JSON, not just standing_rules; ensure no current T2 note/2013 retrospective eff leaks. Include future nested local/related/backbone/defence evidence and malformed dates. Current-date/no-cutoff queries must retain full provenance and useful results. Reject invalid inputs with coherent transport behavior.

## Acceptance

Run syntax checks and the full offline server tests; the unchanged independent API audit must now pass all five findings (A01–A05). Add positive identity tests for real existing stored citation forms, conflict/ambiguity/parallel-citation tests, and stubbed live lookup outcomes. Add positive safe historical metadata cases and negative full-response future-content cases. Prove no network/data writes and preserve task01/task02 tests. Report exact changed files, test counts, and remaining data limitations. Stop for Codex independent review; passing software checks is not legal source verification.
