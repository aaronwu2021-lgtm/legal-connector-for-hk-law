# Doctrine Connector — project notes

A typed, time-indexed element library for English-common-law-family doctrine
(EN / HK / SG / AU), served to LLM agents over REST and MCP.
Live: https://doctrine-drift-atlas.netlify.app

## Layout

- `data/` — the library. `elements.json` (misrepresentation family), `registry.json`
  (14 typed causes of action), `scored.json` (weighted modules), `maintenance.json`
  (drift ledger), `corpus/` (745 HK land-law case notes).
  **Never hand-edit these** — they are build outputs. Edit the builders in `scripts/`
  and re-run, or the next build silently reverts your change.
- `scripts/` — builders. Order matters:
  `build_elements.py` → `build_registry.py` → `build_scored.py` →
  `apply_tiers.py` (assigns weight bands to every balancing factor) →
  `build_maintenance.py` (derives the drift ledger from the timelines).
  Each writes both `data/*.json` and `server/netlify/functions/_*.mjs`.
- `server/` — Netlify functions. `api.mjs` is the whole API surface (REST + MCP);
  `_*.mjs` are generated data modules. `public/index.html` is the entire UI,
  single file, no build step.
- `experiments/` — the two studies in the paper. exp2 is self-contained; exp1
  needs a local clone of harveyai/harvey-labs (not vendored here).
- `paper/` — JURIX 2026 short paper.

## Working rules

**Verification levels are load-bearing.** Every authority carries `verified`:
`unverified` → `web` (checked against accessible sources) → `primary` (pin-cited
to a judgment paragraph). Nothing is at `primary` yet. Never upgrade a level
without actually reading the source, and never add an authority at `web` that
you have not checked.

**Weights are `doctrinal-tier`, not law.** Tiers map to bands (heavy 20–30% …
marginal 1–4%). No court assigns numbers. If a factor gets an empirical weight
from outcome regression, change its `weight_source` to `regression` — do not
silently overwrite a tier.

**Test type before weights.** A claim is conjunctive, balancing,
disjunctive-gateway, threshold–discretion, or presumption–rebuttal. Weights are
meaningless for anything but balancing; the scorer refuses to score the others.
Getting the type wrong is worse than getting a weight wrong.

**Coverage gaps are reported, not filled.** 59 of 68 nodes have no authority on
file. The API says so. Do not let a model infer across a gap.

## Common tasks

```bash
# rebuild everything after editing a builder
cd scripts && for f in build_elements build_registry build_scored apply_tiers build_maintenance; do python3 $f.py; done

# run locally
cd server && npx netlify dev

# deploy (needs Netlify auth)
cd server && npx netlify deploy --prod
```

## Open work

1. Upgrade the 22 backbone authorities from `web` to `primary` (needs judgment PDFs;
   several repositories block automated fetch).
2. Fill the HK branch of timeline T3 (Royscot measure under Cap. 284 s.3(1)) and
   hunt for CFA-level non-reliance authority — see `data/maintenance.json` queue.
3. Replace tier bands with regression weights, starting with lease-vs-licence
   (352 corpus cases, the cheapest to calibrate).
4. Build the HK matter-file eval set the paper argues is missing.
