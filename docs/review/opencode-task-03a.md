# OpenCode task 03a: citation identity and source preservation

Status: implemented by Codex after the free-model stalls, independently accepted. See `task03-acceptance-2026-09-05.md`. The instructions below are the original bounded specification, not a new dispatch.

Run only after task02 is accepted. Use the selected free model; no paid fallback. Read `CLAUDE.md`. Preserve existing work and tests. Never execute or import a builder, even with `--help`. No generated-data changes, verification upgrades, external requests, commits, push, or deployment.

## Scope

Allowed: citation matching, authority projection, and relevant MCP schema/description code in `server/netlify/functions/api.mjs`; new `server/test/citation.test.mjs`; a small private citation helper if necessary. Preserve unrelated bytes and the existing file encoding/NUL. Do not edit the independent audit, scoring, historical projection, UI, or existing tests. Put temporary helpers under `.git/codex-review/`.

This task establishes which stored case an input identifies and preserves the evidence already stored. It does not check a legal proposition. Leave live HKLII behavior and `as_of` behavior unchanged; live-response hardening is a separate follow-up, and historical projection belongs to 03b. All tests must deny network access and use `live=0` for REST verification.

## Required behavior

1. Match the supplied name and explicit citations independently. When both are present, require consistency. A wrong citation must not become a successful name-only fallback; a citation for Hayward must not verify the name Derry. Return `found:false` with mismatch/conflict or unresolved-citation status and optional identity-only suggestions. A coverage miss is not proof that a case does not exist.
2. Parse neutral citations present in the data, including `EWCA Civ` and `EWCA Crim`. Keep report citations such as `[2020] QB 551` distinct. Normalize harmless whitespace/case only. Inspect every supplied citation: accept parallel citations only when their stored identity agrees; do not ignore an additional conflicting or unresolved citation.
3. For name-only inputs, return ambiguity and candidates where more than one identity fits. Respect the supplied second party. Support abbreviations grounded in the existing records; do not infer aliases from outside knowledge. Repeated appearances of one identity are evidence records, not distinct case candidates.
4. Apply the same consistency rules to core and persuasive records. A persuasive fallback cannot override a core conflict. Preserve its original unverified/persuasive-only status. Grouping records must retain each original verification level, pin, `source`/`src`, source-bearing notes, and record location; never replace them with the group's highest verification level. Keep existing response fields usable where truthful, and expose separate evidence records when one identity has multiple sources.
5. A successful identity lookup must explicitly say `proposition_check:"not-performed"`. It neither reads judgments nor upgrades evidence. Apply these rules consistently to REST `/api/verify?live=0` and MCP `verify_citation`; share matching/projection helpers where case lookup uses the same identities, without broad unrelated API changes.

## Acceptance

Use existing stored records to test: wrong Hayward citation; Derry with Hayward's citation; a multiword EWCA citation with a wrong number; ambiguous `DBS Bank (HK)`; supplied second-party conflicts; valid parallel citations; and repeated identity records retaining distinct evidence. `Long Year Development` must retain its actual quoting-source information. Add positive core and persuasive identity cases and REST/MCP agreement.

Run API syntax checking, all offline server tests, and the unchanged independent audit. A01/A02/A03/A05 must pass; A04 remains for 03b. Report changed files, test counts, compatibility choices, and unresolved identity coverage. Stop for Codex review before 03b.
