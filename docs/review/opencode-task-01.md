# OpenCode task 01: enforce amendment evidence validation

Status: implemented by OpenCode using Muse Spark 1.3 Free; independently accepted by Codex on 2026-09-05. Final review: 236/236 independent REST/MCP checks, 23/23 regression tests, API syntax check passed. Amendment validator/schema and narrow MCP rejection handling changed; generated data and UI were preserved. This is structural validation only, not legal evidence certification.

Work in this repository. Read `CLAUDE.md` before editing. Codex owns the decisions and independent acceptance checks; OpenCode owns this bounded implementation. Use only the explicitly selected free model. Never switch to a paid provider, enable billing, or launch paid evaluations. If the provider reports a free-usage limit, report the block and stop.

## Scope

Fix `validateAmendment` and the `propose_amendment` MCP input schema in `server/netlify/functions/api.mjs`. Add offline regression tests using built-in `node:test`, plus an `npm test` script in `server/package.json`. No new dependencies.

Allowed modifications: `server/netlify/functions/api.mjs`, `server/package.json`, new tests under `server/test/`. Do not modify the independently authored audit probe or its saved baseline. Do not change generated data, builders, research results, UI, or unrelated files. The working tree already contains extensive user work: preserve it. No reset, checkout, stash, commit, push, deployment, scraping, or model-based evaluation.

## Reproduced defect

`POST /api/maintenance/propose` accepts a proposal with `verified: "verified-primary"`, no pin, `year: "not-a-year"`, and `treatment: "does not overrules"`. It returns `accepted: true`, an applicable patch, and marks every evidence gate satisfied. Missing pin is only an informational field; treatment uses substring matching; year accepts nonnumbers. The output patch drops supplied pin/source information.

## Required behavior

1. Validate a non-null, non-array object. Required textual fields must be nonempty strings after trimming. Reject malformed input with a structured validation result; do not throw an accidental TypeError.
2. `jurisdiction` must be EN/HK/SG/AU and the `(sub_test, jurisdiction)` node must exist. `year` must be a finite integer number in [1700, 2100]; numeric strings, arrays and nonnumbers are invalid.
3. Use exact treatment membership: establishes, applies, affirms, broadens, clarifies, narrows, distinguishes, doubts, overrules. No substring acceptance.
4. Verification values are exactly `unverified`, `verified-web`, `verified-quoted`, `verified-primary`. Omitted value defaults to unverified; unknown values are invalid. This is the submitter's declared level, not proof of independent verification.
5. `verified-primary` and `verified-quoted` require a nonempty string `pin`. `verified-quoted` also requires a nonempty string `source` identifying the quoting judgment. Preserve provided `pin` and `source` in `patch.event`, consistent with `scripts/build_elements.py::A`. Reject wrong types and whitespace-only evidence. Do not fetch sources or upgrade existing records.
6. Never mark the five evidentiary gates satisfied merely from a submitted level. Structural acceptance means only that a proposal is ready for review. Return explicit pending independent-review status and accurate next steps. Do not claim an unverified or quoted proposal can automatically be merged at verified-web.
7. Invalid proposals must have `accepted: false`, actionable errors, and `patch: null` through both REST and MCP. Structurally valid proposals retain the declared evidence, remain pending review, and do not write to the dataset.
8. Keep MCP schema consistent with runtime: integer year/range, exact enums, `pin` and `source` fields, and descriptions of conditional evidence requirements. Existing clients and unrelated tools should remain functional.
9. Add meaningful offline regression cases: minimal unverified proposal; invalid year/string/array; invalid treatment containing a valid word; invalid verification level; null/array bodies; whitespace fields; missing primary pin; quoted pin without source; valid primary and quoted proposals preserving evidence; no automatic gate success; matching REST/MCP behavior. Use synthetic fixture text, never fabricated real authority claims.
10. Review follow-up: when supplied, `favor` must be finite numeric and pin/source must be nonempty strings (explicit null is invalid). Rejected amendment MCP results set `isError:true`. The test command discovers future test files. All three requirements were independently verified after a second OpenCode pass.

## Acceptance and handback

Run `node --check server/netlify/functions/api.mjs` and `npm test --prefix server`. Run `node scripts/audit_api_contract.mjs`: only the amendment finding is expected to change in this task; leave the other findings visible for subsequent tasks. Report the exact changed files, commands, pass/fail counts, and any remaining concerns. Stop after this one task for Codex review. A green structural test is not legal source verification.
