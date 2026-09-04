# Doctrine Connector

A typed, time-indexed element library for English-common-law-family doctrine
(England, Hong Kong, Singapore, Australia), served to LLM agents over REST and
the Model Context Protocol.

Live: **https://doctrine-drift-atlas.netlify.app** — REST at `/api/*`, MCP at `/api/mcp`.

This repository accompanies the JURIX 2026 short-paper submission in `paper/`.

---

## What is in here

| Path | Contents |
|---|---|
| `data/` | The element library: misrepresentation family (17 sub-tests × 4 jurisdictions), a 14-module typed registry of causes of action, weighted-factor modules, the drift/maintenance ledger, and a 745-document Hong Kong land-law case-note corpus. CC BY 4.0. |
| `server/` | The connector itself — Netlify serverless functions implementing the REST API and a 10-tool MCP server, plus the browser UI. MIT. |
| `experiments/exp1-lab/` | In-benchmark pilot: 6 arbitration tasks, 2 conditions, blind paired judging over 59 legal-standard criteria. Null result. |
| `experiments/exp2-probe/` | Jurisdiction-specific probe: 21 items, 2 conditions, blind judging against a pre-registered key. 16/21 → 21/21. |
| `scripts/` | Builders that regenerate every artefact in `data/` from source. |
| `paper/` | Short paper (LaTeX + PDF). |

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

**Weights are bands, and the interval propagates.** No court assigns numbers to
the factors in a balancing test. Each factor carries an ordinal tier (heavy
20–30% … marginal 1–4%) with provenance `doctrinal-tier`, kept distinct from a
future `regression` level. Scoring returns an interval, and where the interval
straddles two qualitative bands the API says its weights are too coarse to
decide and names the unresolved factor with the largest band.

**Standards drift, and the drift is measurable.** Each (sub-test × jurisdiction)
node is modelled as receiving test-changing decisions as a Poisson process, the
rate shrunk toward a one-per-decade prior. Fitted over the misrepresentation
family this gives 1.02 events per year for one claim family across four
jurisdictions. `as_of` queries return the standard as it stood at a stated year.

The rate is sensitive to coverage, which is the honest reading of it rather than
a caveat about it: filling a single node (the Hong Kong branch of timeline T3)
moved the aggregate from 0.82 to 1.02. A drift rate fitted over a library with
58 coverage gaps is a lower bound on the drift of the doctrine, not an estimate
of it.

## Quick start

```bash
# serve locally
cd server && npm install && npx netlify dev

# or query the live deployment
curl https://doctrine-drift-atlas.netlify.app/api/registry
curl "https://doctrine-drift-atlas.netlify.app/api/timeline/T1?as_of=2015"
curl -X POST https://doctrine-drift-atlas.netlify.app/api/score \
  -H 'content-type: application/json' \
  -d '{"module":"HKJUR","facts":{"F-governing-law":true}}'
```

### MCP

Endpoint `POST /api/mcp`, JSON-RPC 2.0. Ten tools:

`list_causes_of_action` · `get_elements` · `get_element_test` · `get_timeline`
· `check_staleness` · `score_factors` · `list_scored_tests` · `search_corpus`
· `lookup_case` · `propose_amendment`

```bash
curl -X POST https://doctrine-drift-atlas.netlify.app/api/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Reproducing the experiments

**Experiment 2** is self-contained: `experiments/exp2-probe/` holds the probe
items with pre-registered answer keys, the connector payload, both answer sets,
the blinding key and the per-item verdicts.

**Experiment 1** references [harveyai/harvey-labs](https://github.com/harveyai/harvey-labs)
(MIT). Its rubric text and matter documents are **not** redistributed here.
`scored_criteria_ids.json` lists the 59 criterion IDs scored; run
`prep_from_lab_clone.py` against your own clone to regenerate the task inputs.
Model outputs, blinding key and verdicts are included.

## Limitations — please read before relying on any of this

- **Authorities are mostly web-verified, not pin-cited.** The Hong Kong branch
  is the exception: eight HK authorities are at `verified-primary`, read from
  the judgment text and cited to a paragraph. Everything else was checked
  against accessible primary or reputable secondary sources and carries no
  paragraph pin cite. Each record carries its own level and the API reports it.
  Several primary repositories block automated retrieval.
- **Weights are compiler judgement.** Tiers are labelled `doctrinal-tier`. They
  are not evidence about how courts decide, and no court assigns percentages to
  these factors.
- **Coverage is thin and uneven.** The misrepresentation family has 10 attested
  nodes and 58 coverage gaps out of 68. A gap is reported as a gap, not
  silently filled.
- **Experiments are small and single-run.** n=59 criteria and n=21 items;
  Experiment 2's McNemar exact p=0.0625 is not conventionally significant.
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
