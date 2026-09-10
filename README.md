# Doctrine Connector

A typed, time-indexed element library for English-common-law-family doctrine
(England, Hong Kong, Singapore, Australia), served to LLM agents over REST and
the Model Context Protocol.

Live: **https://doctrine-drift-atlas.netlify.app** — REST at `/api/*`, MCP at `/api/mcp`.

This repository accompanies a JURIX 2026 short-paper submission. The paper
itself is not distributed here.

---

## What is in here

| Path | Contents |
|---|---|
| `data/` | The element library: misrepresentation family (17 sub-tests × 4 jurisdictions), a 14-module typed registry of legal-test logic and two-axis litigation positions (numeric bands only inside multi-factor balancing stages), the drift/maintenance ledger, a 745-document Hong Kong land-law case-note corpus, and a 449-case England-and-Wales persuasive index (unverified, persuasive-only in HK). CC BY 4.0. |
| `server/` | The connector itself — Netlify serverless functions implementing the REST API and a 13-tool MCP server, plus the browser UI. MIT. |
| `experiments/exp1-lab/` | In-benchmark pilot: 6 arbitration tasks, 2 conditions, blind paired judging over 59 legal-standard criteria. Null result. |
| `experiments/exp2-probe/` | Jurisdiction-specific probe: 21 items, 2 conditions, blind judging against a pre-registered key. 16/21 → 21/21 as originally scored; **15/21 → 19/21 re-scored against the law** after two keys were found wrong (`rescore.py`, `probe_results_rescored.json`). |
| `experiments/exp3-hk-matter/` | The Hong Kong matter-file eval set the paper identified as missing: 5 tasks, 31 criteria, 6 drift-sensitive, with an as_of pair either side of *Chang Pui Yin*. **Unrun** — a task set with answer keys, no results claimed. |
| `experiments/exp4-cfa/` | A CFA arbitration set: 3 tasks and 13 criteria covering the 2022/2023 *C v D* as-of pair and the layered 2020/2024/2026 *Eton* decisions. **Unrun** — local source checks are complete; independent legal sign-off is pending. |
| `scripts/` | Builders that regenerate every artefact in `data/` from source. |

## Three design commitments

**Tests are typed, and the type is load-bearing.** Legal tests are not uniformly
conjunctive. The registry distinguishes five kinds — conjunctive (emit a gap
list; a percentage is meaningless), disjunctive-gateway (any one of a closed
list), balancing (weighted factors), threshold–discretion, and
presumption–rebuttal. Type is verifiable from doctrine in a way numeric weights
are not. Piercing the corporate veil is the worked example: a multi-factor
enquiry before *Prest v Petrodel* [2013] UKSC 34 and two principled gateways
after it, so a weighted model would encode a superseded test in a form that
looks quantitatively rigorous.

**Litigation position has two axes.** `litigation_postures` records whether a
test is usually asserted as a spear, used responsively as a shield, or both.
`litigation_track` separately records merits, procedure, or jurisdiction. A
procedure is therefore never treated as the opposite of a defence. The legacy
single-value `role` remains in REST and MCP responses for compatibility;
clients should use `posture` and `track` filters for new integrations. Every
modelled stage carries its own position metadata. For example, New York
Convention Article V(1) is a respondent's shield, while Article V(2) is marked
as a court-own-motion stage; element sub-tests state their inherited track and
posture explicitly as well.

**Weights are bands, and the interval propagates.** No court assigns numbers to
the factors in a balancing test. Each factor carries an ordinal tier (heavy
20–30% … marginal 1–4%) with provenance `doctrinal-tier`, kept distinct from a
future `regression` level. Scoring returns an interval, and where the interval
straddles two qualitative bands the API says its weights are too coarse to
decide and names the unresolved factor with the largest band.

**The maintenance rate is a modelling assumption.** Each (sub-test × jurisdiction)
node is modelled as receiving test-changing decisions as a Poisson process,
with a one-per-decade prior. The current misrepresentation model gives 1.02
events per year across four jurisdictions. This is a maintenance heuristic
derived from the collected timeline and prior, not a validated population
drift rate. Historical `as_of` queries return eligible dated authority metadata;
unversioned rule text is withheld with `historical-rule-not-modelled`.

**Court level is separate from time.** Timeline metadata includes `court` and
`court_rank`. Historical `standing_rules` retains the highest-rank dated
candidates, while `latest_rules` retains the most recent dated candidates.
Overlapping dates remain tied. These legacy field names identify catalogue
records; they do not establish a binding historical rule. Current editorial
conflict text is withheld from historical responses because it is not versioned.

The rate is sensitive to coverage: filling a single node (the Hong Kong branch
of timeline T3) moved the aggregate from 0.82 to 1.02. Incomplete collection,
event coding and prior shrinkage prevent interpreting this value as a proven
lower bound. Observation-window, coverage and prior-sensitivity analyses remain
necessary before using it as an empirical maintenance estimate.

## Quick start

On Windows, double-click `Start Preview.cmd`, then open
`http://127.0.0.1:8918/`. The launcher starts a hidden local process, waits for
its health response, and records output in the ignored `server/.preview/`
directory. Running it again reuses this same healthy preview; it does not stop
other applications. A stopped preview must be started again, including after a
computer restart. This is a local preview, not a deployed or always-on service.
Reuse keeps the existing API process; it does not reload changed server modules.

The equivalent command is `node server/start-preview.mjs`. It does not
rebuild data or run model experiments. The foreground development command below
remains available.

```bash
# serve locally -- no dependencies, just Node
node server/devserver.mjs        # http://localhost:8899

# or via the Netlify CLI, matching the deployed environment
cd server && npm install && npx netlify dev

# or query the live deployment
curl https://doctrine-drift-atlas.netlify.app/api/registry
curl "https://doctrine-drift-atlas.netlify.app/api/timeline/T1?as_of=2015"
curl -X POST https://doctrine-drift-atlas.netlify.app/api/score \
  -H 'content-type: application/json' \
  -d '{"module":"HKJUR","facts":{"F-governing-law":true}}'
```

### MCP

Endpoint `POST /api/mcp`, JSON-RPC 2.0. Fourteen tools:

`resolve_jurisdiction` · `pleading_checklist` · `verify_citation` ·
`list_causes_of_action` · `get_doctrine` · `get_elements` · `get_element_test` · `get_timeline`
· `check_staleness` · `score_factors` · `list_scored_tests` · `search_corpus`
· `lookup_case` · `propose_amendment`

The first three exist because of what the experiments found. `resolve_jurisdiction`
answers the Experiment 1 defect (doctrine injected without deciding whose law
applied). `verify_citation` answers the one hallucination in Experiment 2 (a
garbled neutral citation) and refuses to confuse *Long v Lloyd* with *Long Year
Development*. `pleading_checklist` is the lawyer-facing output: every element,
what to plead, local authority with pin cite and verification level, and an
explicit gap wherever the library has no local authority so the drafter does
not infer the Hong Kong position from English law. `GET /api/verify?cite=` can
retrieve HKLII metadata for a consistent Hong Kong neutral citation. A matching
response establishes only that neutral-citation retrieval; access failures or
an unavailable English version leave case existence unknown. Historical queries
make no live request. Both identity endpoints preserve all stored evidence
occurrences and reject inconsistent names or citations, including conflicts
involving the persuasive index. Neither endpoint verifies a legal proposition.

The historical tools `pleading_checklist`, `verify_citation`, `get_elements`,
`get_element_test` and `get_timeline` accept `as_of` as a four-digit year
(1000–9999, interpreted as December 31) or an actual `YYYY-MM-DD` date. Their
corresponding REST endpoints share this parser. Invalid values and unsupported
historical requests are rejected. Year-only records cannot establish eligibility
earlier within the same year. Historical rule text and sources without usable
chronology are withheld; omission is reported as a gap, not evidence of absence.

### Persuasive E&W branch

`GET /api/persuasive` (search 449 leading E&W cases by name, citation, area,
court, signal), `/api/persuasive/{slug}` (record plus incoming treatment) and
`/api/persuasive/graph` (typed case-to-case edges: followed / applied /
distinguished / overruled …). Every record is `verified: "unverified"` with
`hk_status: "persuasive-only"` and carries its source page, reviewed date,
court rank and official links — status and staleness, not doctrine. There are
deliberately no test types and no weights here: typing 449 unread cases would
violate the project's own rule that getting the type wrong is worse than
getting a weight wrong. `/api/persuasive/queue` lists the unverified records
load-bearing-first as the human-check worklist. Built by `scripts/build_persuasive.py` from
`data/sources/uklr/`; see `SOURCING.md` there for provenance and the per-case
human-check upgrade path. `scripts/check_persuasive.py` guards the invariants.

```bash
curl -X POST https://doctrine-drift-atlas.netlify.app/api/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Reproducing the experiments

**Experiment 2** is self-contained: `experiments/exp2-probe/` holds the probe
items, answer keys, connector payload, both answer sets, blinding key and
per-item verdicts. Stored keys alone do not establish external preregistration.
Use the corrected scoring record; retain the original record as an archive.

**Experiments 3 and 4 remain unrun as formal studies.** Their task validators
check structure and local source evidence, which does not establish that a cited
paragraph supports the complete answer-key proposition. Experiment 3 currently
passes all 31 catalogue/pin/date structure checks. Experiment 4 separately binds
every cited judgment, determination and Cap. 609 version to a source file,
locator and phrase; all 13 criteria pass those local checks. Both generated
reader checklists leave independent legal sign-off blank, so full readiness is
still refused. The frozen review object and sign-off rules are in the
[legal-review protocol](docs/review/independent-legal-review-protocol.md).

Both experiments use `run.py build`, `run.py run`, `run.py blind`, `judge.py`,
`score.py` and `eval_card.py`. A content-bound run manifest freezes selected
tasks, conditions, variants, prompts, retrieved payloads and declared model
identities. Answers and judgments bind to those exact inputs. Old directories
without a manifest and stale or conflicting artifacts are rejected. Blinded
judging uses a separate manifest without the condition key. Historical payloads
contain eligible dated metadata; unversioned legal rules are withheld. This
changes the intervention from the archived protocol.

Scores are paired descriptive summaries. Missing answers or verdicts, judge
disagreements and execution/parse errors remain distinct from legal failures.
No criterion-level significance test or automatic calibration adjustment is
reported. Cards read frozen execution records, not today's model environment.
Model identities remain operator declarations; hashes do not attest provider
identity. Every run retains `formal_ready: false` until a separately implemented
and independently reviewed study protocol exists. Offline fixtures test the
software and are not study results. See the [Experiment 3 workflow](experiments/exp3-hk-matter/README.md)
and [Experiment 4 workflow](experiments/exp4-cfa/README.md).

**Experiment 1** references [harveyai/harvey-labs](https://github.com/harveyai/harvey-labs)
(MIT). Its rubric text and matter documents are **not** redistributed here.
`scored_criteria_ids.json` lists the 59 criterion IDs scored; run
`prep_from_lab_clone.py` against your own clone to regenerate the task inputs.
Model outputs, blinding key and verdicts are included.

## Limitations — please read before relying on any of this

- **Verification labels describe individual stored evidence records.**
  `verified-primary` declares a primary-text check, `verified-quoted` declares
  a passage checked through a later quoting judgment, and `verified-web`
  declares a web-source check; `unverified` remains unverified. An identity
  match does not validate these declarations or the legal proposition. The
  previously reported missing statute pins and quoted-source field have been
  supplied in the canonical builders and regenerated data. The Long Year report
  itself has still not been read; that record remains `verified-quoted` and now
  identifies the later HK judgments and exact passages used. See the
  [current reliability review](docs/review/legal-reliability-2026-09-06.md) and
  the earlier [provenance audit](docs/review/task04b-acceptance-2026-09-05.md).

- **Reading the sources changed the doctrine, not just the citations.** The
  dataset previously recorded Singapore as diverging from England by treating
  the inducement presumption as an inference of fact rather than of law. Reading
  Hayward at [34] and BV Nederlandse at [43] showed that is the English position
  too, from the same Chitty passage; Singapore reached it three years earlier.
  That divergence has been withdrawn. Treat the remaining `verified-web`
  characterisations as unaudited.
- **Weights are compiler judgement.** Tiers are labelled `doctrinal-tier`. They
  are not evidence about how courts decide, and no court assigns percentages to
  these factors.
- **Coverage is thin and uneven.** The misrepresentation family has 10 attested
  nodes and 58 coverage gaps out of 68. A gap is reported as a gap, not
  silently filled. The 449-case E&W persuasive index widens coverage without
  deepening verification — all of it `unverified`, all of it persuasive-only
  in Hong Kong.
- **Experiments are small and single-run.** n=59 criteria and n=21 items;
  Experiment 2's corrected record gives 15/21 versus 19/21, four gains and no
  losses, with McNemar exact p=0.125. The original p=0.0625 is retained only in
  the archived original scoring; neither is conventionally significant.
  Agents and judges came from one model family, and the authors built both the
  connector and the probe.
- **Not legal advice.** This is a research artefact.

## Citation

```bibtex
@misc{wu2026doctrineconnector,
  author = {Wu, Jialun},
  title  = {Doctrine Connector: a typed, time-indexed element library for legal agents},
  year   = {2026},
  url    = {https://github.com/aaronwu2021-lgtm/legal-connector-for-hk-law}
}
```

## Licences

Code (`server/`, `scripts/`, `experiments/*.py`) — MIT, see `LICENSE`.
Data (`data/`) — CC BY 4.0, see `data/LICENSE-DATA`.
