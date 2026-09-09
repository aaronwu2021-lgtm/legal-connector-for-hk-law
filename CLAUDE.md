# Doctrine Connector — project notes

A typed, time-indexed element library for English-common-law-family doctrine
(EN / HK / SG / AU), served to LLM agents over REST and MCP.
Live: https://doctrine-drift-atlas.netlify.app

## Layout

- `data/` — the library. `elements.json` (misrepresentation family), `registry.json`
  (14 typed legal-test modules across registry + scored), `scored.json` (legal-test catalogue plus the HKJUR module; numeric bands apply only to balancing stages), `maintenance.json`
  (drift ledger), `persuasive.json` (449-case E&W index: metadata + treatment
  edges only, all `unverified` / persuasive-only — never doctrine), `corpus/`
  (745 HK land-law case notes).
  **Never hand-edit these** — they are build outputs. Edit the builders in `scripts/`
  and re-run, or the next build silently reverts your change.
- `scripts/` — builders. Order matters:
  `build_elements.py` → `build_registry.py` → `build_scored.py` →
  `apply_tiers.py` (assigns weight bands to every balancing factor) →
  `build_maintenance.py` (derives the drift ledger from the timelines).
  `build_persuasive.py` is order-independent (reads only `data/sources/uklr/`).
  Each writes both `data/*.json` and `server/netlify/functions/_*.mjs`.
- `server/` — Netlify functions. `api.mjs` is the whole API surface (REST + MCP);
  `_*.mjs` are generated data modules. `public/index.html` is the entire UI,
  single file, no build step.
- `experiments/` — exp1 and exp2 are the two studies written up in the paper,
  which is kept outside this repository. exp2 is self-contained; exp1 needs a
  local clone of harveyai/harvey-labs (not vendored here). exp3 is the HK matter-file eval set and is **unrun** — do not report a
  result from it. Its rubrics are build outputs too: edit `build_tasks.py`, then
  run `validate_tasks.py`, which fails on a criterion that is ungrounded,
  anachronistic for its `as_of`, or names no wrong answer to discriminate
  against.

## Working rules

**Verification levels are load-bearing.** Every authority carries `verified`:
`unverified` → `web` (checked against accessible sources) → `quoted` (the
operative passage read verbatim in a later judgment that pin-cites it, the
report itself unseen) → `primary` (the judgment text itself read, with a pin
cite). Never upgrade a level without actually reading the source, and never add
an authority at `web` that you have not checked. `verified-quoted` exists so
that "a later court quoted it at length" does not get laundered into "I read
it" — do not collapse the two to save a level. `A()` refuses `primary` or
`quoted` without a pin, and `quoted` without the quoting judgment.

**BAILII and AustLII are off limits to automation.** AustLII returns 403;
BAILII now serves a proof-of-work anti-bot challenge. Do not attempt to defeat
either — use Find Case Law (`caselaw.nationalarchives.gov.uk/<court>/<year>/<num>/data.xml`,
Akoma Ntoso with paragraph numbers, English judgments from ~2003) and
eLitigation (`elitigation.sg/gd/s/<year>_SGCA_<num>`), both of which serve
plain requests.

**Weights are `doctrinal-tier`, not law.** Tiers map to bands (heavy 20–30% …
marginal 1–4%). No court assigns numbers. If a factor gets an empirical weight
from outcome regression, change its `weight_source` to `regression` — do not
silently overwrite a tier.

**Test type before weights.** A claim is conjunctive, balancing,
disjunctive-gateway, threshold–discretion, or presumption–rebuttal. Weights are
meaningless for anything but balancing; the scorer refuses to score the others.
Getting the type wrong is worse than getting a weight wrong.

**Litigation position uses two axes.** `litigation_postures` is a non-empty,
possibly multi-valued list of `spear` / `shield`; `litigation_track` is one of
`merits` / `procedure` / `jurisdiction`. Never put procedure or jurisdiction
back into the posture axis. Keep the old `role` field only as a compatibility
view. Every stage must have an entry in `STAGE_LITIGATION_POSITIONS`; an empty
posture list is valid only for a `court_own_motion` stage. Update the profiles
in `scripts/logic_schema.py`, then rebuild.

**Three hierarchies, kept apart.** Doctrinal (claim -> element -> sub-test),
institutional (`court_rank` on every timeline event: 4 apex, 3 intermediate
appellate incl. a CFA Appeal Committee determination, 2 superior first
instance, 1 lower), and temporal (`as_of`). `timelineAsOf` returns
`standing_rules` (highest rank, then most recent) AND `latest_rules` (most
recent regardless), plus `latest_is_not_governing` and `subordinate_conflicts`
where they disagree. Never collapse these back to one field: recency alone lets
a CFI decision override the CA; rank alone hides twenty years of lower-court
development under a 2001 CFA ruling. Events without a parenthetical court on
their case name need an explicit `court` key or the build raises.

**Coverage gaps are reported, not filled.** 58 of 68 nodes have no authority on
file. The API says so. Do not let a model infer across a gap.

**HKLII is the working route into HK primary sources**, and it is two APIs, not
the search box (which is reCAPTCHA-gated in the UI):
`/api/simplesearch?searchstring=...&disablefuzzy=true` for full text,
`/api/getjudgment?lang=en|tc&abbr=hkcfi&year=&num=` for a judgment,
`/api/getcasenoteup?abbr=&year=&num=` for what cites it, and
`/api/getcasefiles?caseDb=hkcfa&lang=EN&itemsPerPage=500&page=1` for the index.
Search coverage is uneven — a "Derry v Peek" search returns 12 hits, all
post-2021 — so a nil result is not evidence that no authority exists, and must
never be recorded as one. HKLII carries no pre-1997 first-instance judgments.

## Common tasks

```bash
# rebuild everything after editing a builder
cd scripts && for f in build_elements build_registry build_scored apply_tiers build_maintenance; do python3 $f.py; done

# run locally -- needs the Netlify CLI
cd server && npx netlify dev

# run locally with nothing but Node (same handler, current data/)
node server/devserver.mjs        # http://localhost:8899

# deploy (needs Netlify auth)
cd server && npx netlify deploy --prod
```

## Open work

1. Upgrade the remaining EN / SG / AU authorities from `web` to `primary`. The HK
   branch is done (8 authorities, read from judgment text via the HKLII API).
   BAILII / AustLII / e-Legislation still block automated fetch.
2. ~~Fill the HK branch of timeline T3~~ — done: Long Year Development v Tse Fuk
   Man Norman [1991] 2 HKC 393, 407D-408D adopted Royscot. Later reviewed CFI
   and DC decisions cite or apply it, but the current record contains no CA or
   CFA ruling on the point and does not prove the absence of contrary authority.
   Q-001 is only partially answered: the apex has spoken on contractual
   estoppel, but through an Appeal Committee determination refusing leave.
3. Replace tier bands with regression weights, starting with lease-vs-licence
   (352 corpus cases, the cheapest to calibrate).
4. ~~Build the HK matter-file eval set~~ — built AND the protocol is complete
   (`run.py build|run|blind` → `judge.py` → `score.py`, the rubric is the
   pre-registered key). What it still needs is to be RUN: a model choice
   (`MODEL_CMD`, `JUDGE_CMD`) and an independent reader to check the keys
   against the pin cites first, given what Experiment 2's re-score found.
5. ~~`propose_amendment` enum mismatch~~ — fixed; the tool now takes the data's
   vocabulary and refuses `quoted`/`primary` without a pin, like the builder.
6. Experiment 2 was re-scored against the law (`exp2-probe/rescore.py`):
   16/21→21/21 became 15/21→19/21 after HK-07 and SG-01 were found to key the
   library's own errors. The original verdicts are untouched beside it. Any
   future key must be checked against pin cites by someone who did not write
   the library.
7. Persuasive E&W branch (`persuasive.json`, all 449 `unverified`) is an index,
   not doctrine. Upgrade path is per-case human check via
   `/api/persuasive/queue` (negative/superseded/qualified first) — re-scraping
   upgrades nothing. Guarded by `scripts/check_persuasive.py`.
