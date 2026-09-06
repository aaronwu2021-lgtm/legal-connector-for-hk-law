# Sourcing note — `data/sources/uklr/`

Third-party identity index. Content: UK Law Reference (`uklawreference.com`),
an England-and-Wales legal-information site that publishes machine-readable
`llms*.txt` splits for LLM consumption (see its `/llms.txt` and `/ai.txt`).
Pulled 2026-09-04. `robots.txt` respected throughout: content pages only,
`/search` and `/api/` untouched.

## Files

- `llms-cases.txt` — VERBATIM snapshot of the site's `llms-cases.txt`
  (449 leading-case entries: title, court, year, area, reviewed date, truncated
  ratio, page URL). Kept verbatim so re-pulls diff cleanly. Refresh:
  `python3 scripts/pull_uklr.py splits` (or `all` for the full pipeline:
  splits → crawl → derive → then run `build_persuasive.py`).
- `uklr-treatment-slim.json` — DERIVED structure (own work): per-case treatment
  labels and typed case-name edges (`{from -> to, type}`), scraped from the
  "Subsequent Treatment" section of each of the 449 case detail pages with a
  1s politeness delay. Editorial note prose is NOT reproduced. Unresolvable
  mentions are kept name-only, never invented.
- `uklr-official-links.json` — DERIVED fact list: `{slug: [official URLs]}`
  (BAILII / Find Case Law / legislation.gov.uk links found on each page).
  URLs are facts, not expression.

## Licence posture (mirrors `data/corpus/`)

`data/LICENSE-DATA` applies to our structuring, not to their prose. Per that
file's rule — *structured metadata and original summaries; no source text is
reproduced* — the built `persuasive.json` carries metadata, links, labels and
our own signal classification only. Full editorial text stays on the source
pages; every record links back. Follow the source's own terms for any use
beyond this index.

## Verification doctrine (load-bearing)

Every record ships `verified: "unverified"` with `hk_status:
"persuasive-only"`. UKLR reviewed-dates are staleness signals, not
verification. Upgrade path is per-case human check (→ `web` only if actually
checked, → `quoted`/`primary` only via the core rules in CLAUDE.md). Bulk
re-verification by re-scraping is NOT verification — do not automate a level
upgrade.
