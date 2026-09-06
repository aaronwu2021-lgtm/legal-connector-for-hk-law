import argparse
import json, datetime, math, collections

from _paths import emit, load

# ── policy ───────────────────────────────────────────────────────────────
POLICY = {
  "model": "Poisson arrival of drift events per (sub_test x jurisdiction)",
  "prior_rate_per_year": 0.10,        # ~1 test-changing decision per node per 10 yrs
  "prior_strength_years": 20,         # pseudo-observation window for shrinkage
  "review_trigger_probability": 0.35, # queue a node once P(missed change) exceeds this
  "annual_event_budget": 27,          # derived: 90 sub-tests x 3 juris x 0.10/yr
  "verification_gate": ["citation exists", "court + date correct",
                        "proposition matches the judgment", "treatment label justified",
                        "bindingness in this jurisdiction stated"]
}

def rate(n_obs, span):
    """shrunk rate: observed events blended toward the prior"""
    p = POLICY['prior_rate_per_year']; k = POLICY['prior_strength_years']
    return (n_obs + p*k) / (span + k)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the maintenance ledger from the generated datasets.")
    parser.parse_args(argv)
    E = load('elements')
    TODAY = "2026-08-25"; NOW = 2026.65

    # ── inventory every reviewable node: (sub_test x jurisdiction) ────────────
    subtests = []
    for el in E['elements']:
        for st in el['sub_tests']:
            subtests.append({'id': st['id'], 'parent': el['id'], 'en': st['en'], 'zh': st.get('zh',''),
                             'kind': 'element', 'drift': st.get('drift')})
    for d in E['defences']:
        subtests.append({'id': d['id'], 'parent': 'D', 'en': d['en'], 'zh': d.get('zh',''),
                         'kind': 'defence', 'drift': d.get('drift')})

    JUR = ['EN','HK','SG','AU']
    JZH = {'EN':'英国','HK':'香港','SG':'新加坡','AU':'澳大利亚'}

    # ── observed drift events, from the timelines already in the dataset ─────
    events = collections.defaultdict(list)          # (sub_test, juris) -> [event]
    for tid, tl in E['timelines'].items():
        st = tl['sub_test']
        for ev in tl['events']:
            events[(st, ev['j'])].append({**ev, 'timeline': tid})


    nodes = []
    for st in subtests:
        for j in JUR:
            ev = sorted(events.get((st['id'], j), []), key=lambda e: e['y'])
            span = (NOW - ev[0]['y']) if ev else 40.0
            lam  = rate(len(ev), span)
            last_event = ev[-1]['y'] if ev else None
            # last_reviewed: the dataset was compiled now, so every node with attested
            # authority counts as reviewed today; nodes with no authority are unreviewed.
            last_reviewed = 2026.65 if ev else None
            elapsed = (NOW - last_reviewed) if last_reviewed else max(0.0, NOW - (last_event or 2006))
            p_missed = 1 - math.exp(-lam * elapsed)
            nodes.append({
              'node': f"{st['id']}@{j}", 'sub_test': st['id'], 'jurisdiction': j,
              'parent': st['parent'], 'kind': st['kind'], 'en': st['en'], 'zh': st['zh'],
              'timeline': st.get('drift'),
              'events_observed': len(ev), 'span_years': round(span,1),
              'rate_per_year': round(lam,4), 'expected_interval_years': round(1/lam,1),
              'last_event_year': last_event,
              'last_reviewed': round(last_reviewed,2) if last_reviewed else None,
              'years_since_review': round(elapsed,2),
              'p_missed_change': round(p_missed,4) if ev else None,
              'status': 'attested' if ev else 'no-authority-on-file',
              'work_type': 'staleness' if ev else 'coverage-gap',
              'priority': round(p_missed,4) if ev else 1.0,
              # when does P(missed change) cross the review trigger, if left alone?
              'review_due_year': (round((last_reviewed or NOW) + (-math.log(1-POLICY['review_trigger_probability'])/lam),1)) if ev else None,
            })

    # ── watchlist: what a monitor should actually poll ───────────────────────

    # -- module timelines (registry + scored litigation modules) -------------
    # Same Poisson policy, SEPARATE ledger: paper_figures.py reads mt["nodes"]
    # only, so the paper's 68-node figures are unaffected by this section.
    # Nodes are (module-timeline x module jurisdiction); events from other
    # jurisdictions still display whole via /api/timeline/{id}.
    REG = load('registry'); SCO = load('scored')
    module_nodes = []
    for m in REG['modules'] + SCO['modules']:
        jurs = [j for j in (m.get('jurisdiction') or '').split('/') if j]
        for tid, tl in (m.get('timelines') or {}).items():
            for j in jurs:
                ev = sorted([e for e in tl['events'] if e['j'] == j], key=lambda e: e['y'])
                span = (NOW - ev[0]['y']) if ev else 40.0
                lam = rate(len(ev), span)
                last_event = ev[-1]['y'] if ev else None
                last_reviewed = 2026.65 if ev else None
                elapsed = (NOW - last_reviewed) if last_reviewed else max(0.0, NOW - (last_event or 2006))
                p_missed = 1 - math.exp(-lam * elapsed)
                module_nodes.append({
                  'node': f"{tid}@{j}", 'timeline': tid, 'module': m['id'],
                  'jurisdiction': j, 'kind': 'module',
                  'en': tl.get('title_en', ''), 'zh': tl.get('title', ''),
                  'sub_test': tl.get('sub_test'),
                  'events_observed': len(ev), 'span_years': round(span, 1),
                  'rate_per_year': round(lam, 4), 'expected_interval_years': round(1 / lam, 1),
                  'last_event_year': last_event,
                  'last_reviewed': round(last_reviewed, 2) if last_reviewed else None,
                  'years_since_review': round(elapsed, 2),
                  'p_missed_change': round(p_missed, 4) if ev else None,
                  'status': 'attested' if ev else 'no-authority-on-file',
                  'work_type': 'staleness' if ev else 'coverage-gap',
                  'priority': round(p_missed, 4) if ev else 1.0,
                  'review_due_year': (round((last_reviewed or NOW) + (-math.log(1 - POLICY['review_trigger_probability']) / lam), 1)) if ev else None,
                })

    WATCH = {
     "courts": [
      {"j":"EN","court":"UKSC","feed":"supremecourt.uk decided cases","approx_per_year":"38–56 (all subjects)"},
      {"j":"EN","court":"EWCA Civ","feed":"caselaw.nationalarchives.gov.uk","approx_per_year":"~1000 judgments, selective reporting"},
      {"j":"EN","court":"UKPC","feed":"jcpc.uk","approx_per_year":"~40, persuasive across the family"},
      {"j":"HK","court":"HKCFA","feed":"legalref.judiciary.hk / HKLII","approx_per_year":"~30–50"},
      {"j":"HK","court":"HKCA / HKCFI","feed":"HKLII","approx_per_year":"hundreds; filter by doctrine"},
      {"j":"SG","court":"SGCA","feed":"elitigation.sg","approx_per_year":"~30–50"},
      {"j":"AU","court":"HCA","feed":"hcourt.gov.au","approx_per_year":"~40–50"}
     ],
     "treatment_markers": {
      "note":"judicial language that signals a test is being restated rather than applied",
      "narrows":["is distinguishable because","should be confined to its facts","goes too far","cannot be read as"],
      "broadens":["is not limited to","applies equally where","the principle extends"],
      "overrules":["we decline to follow","should no longer be followed","is overruled","was wrongly decided"],
      "clarifies":["the correct test is","the question is not … but whether","properly understood"],
      "doubts":["we express no view on whether","may require reconsideration","with respect, we doubt"]
     },
     "citation_lag": {
      "note":"contemporaneous landmark judgment is unreliable; citation accumulation lags 3–10 years",
      "evidence":"in the HK corpus the most-discussed authorities (Stack v Dowden 27, Jones v Kernott 14) accreted weight over a decade",
      "consequence":"run both detectors — language markers for same-year capture, citation counts for retrospective weighting"
     }
    }

    # ── queue: candidates awaiting review ────────────────────────────────────
    QUEUE = [
     {"id":"Q-001","sub_test":"D1","jurisdiction":"HK","state":"partially-answered",
      "question":"Is there CFA-level authority on contractual estoppel / non-reliance clauses?",
      "why":"adoption currently rests at CFI (San-Hot 2013, Sit Pan Jit 2015) with CA-level qualification (Chang Pui Yin 2017); the apex is a hole in the timeline",
      "action":"HKLII full-text search: 'contractual estoppel' + CFA; check any CFA leave decisions",
      "found":"Ng Lai Ling Winnie v Ng Yuk Pui Kelly [2021] HKCFA 40 at [24]-[27] (Appeal Committee: Ribeiro PJ, Fok PJ, Chan NPJ) states the doctrine's outer limit — it binds only parties to the contract, on their mutual agreement, as to what the agreement was directed at — and treats Peekay as the leading case",
      "residual":"a reasoned determination refusing leave is not a substantive CFA appeal judgment, and it says nothing about non-reliance clauses in mis-selling. The hole is narrower, not closed."},
     {"id":"Q-002","sub_test":"E5c","jurisdiction":"HK","state":"answered",
      "question":"Has any HK court adopted or rejected the Royscot fiction-of-fraud measure under Cap 284 s.3(1)?",
      "why":"T3 has no HK branch at all; SG has doubted it obiter (RBC 2014), EN left it open (Smith New Court 1996)",
      "action":"HKLII: 'section 3(1)' + damages measure; check HK textbook commentary",
      "found":"ADOPTED in the decisions reviewed. Long Year Development v Tse Fuk Man Norman [1991] 2 HKC 393 at 407D-408D (DHCJ Andrew Li QC) followed Royscot; Joytex [2018] HKCFI 2286 §142/§144 applied that measure, Wong Yuk Lan [2024] HKDC 804 [89]-[91] applied it, and Alireza [2026] HKCFI 4060 [199] discussed the tortious counterfactual obiter.",
      "residual":"the reviewed HK line is CFI/HC/DC — the current record contains no CA or CFA ruling on the s.3(1) measure. The limited survey cannot establish that the rule has never been doubted or that Hong Kong is the family's most settled jurisdiction."},
     {"id":"Q-003","sub_test":"E3c","jurisdiction":"HK","state":"answered",
      "question":"Does HK follow the strengthened English inducement presumption (Hayward 2016 / BV Nederlandse 2019)?",
      "why":"only CFI-level application on file (Shine Grace 2018); post-1997 English authority is persuasive only, so adoption must be shown",
      "action":"HKLII: 'presumption of inducement'; cross-check CA decisions 2019–2026",
      "found":"Split. Li Yuhong v OOO Securities [2025] HKCFI 5270 [109] adopts Hayward §§33-35 in its strong form; but the CA in Koo Ming Kown v Baptist Convention [2026] HKCA 372 [67] reads the presumption as an inference of FACT, not of law, rebuttable on all the evidence — the Singapore position",
      "residual":"CA outranks CFI, so the inference-of-fact reading governs, but the CFI restatement is months older and unaddressed. Watch for the next CFI decision to see which line it takes."},
     {"id":"Q-006","sub_test":"*","jurisdiction":"*","state":"open",
      "question":"Which HK authorities on this family have been tested above first instance?",
      "why":"every HK node upgraded to verified-primary in this pass sits at CFI, DC or the CFA Appeal Committee; the CA appears once (Koo Ming Kown) and contradicts the CFI",
      "action":"noteup each HK authority via hklii.hk/api/getcasenoteup and record appellate treatment"},
     {"id":"Q-004","sub_test":"*","jurisdiction":"*","state":"open",
      "question":"Upgrade every authority from verified:web to verified:primary (paragraph pin-cite)",
      "why":"22 backbone authorities are verified against reputable secondary sources only; BAILII / AustLII / e-Legislation blocked automated fetch",
      "action":"pull judgment PDFs manually or via an authenticated feed; record paragraph numbers"},
     {"id":"Q-005","sub_test":"E1a","jurisdiction":"SG","state":"open",
      "question":"Any SGCA development on implied representations since Tan Chin Seng (2003)?",
      "why":"the fact/opinion boundary is the sub-test most exposed to implied-representation expansion, and the SG branch is 20+ years stale",
      "action":"elitigation.sg: 'statement of intention' / 'implied representation' 2003–2026"}
    ]

    QUEUE.extend([
     {"id": "Q-007", "sub_test": "AC-1", "jurisdiction": "HK", "state": "open",
      "question": "Any Hong Kong authority on arbitrator challenge/bias (Model Law art 12)?",
      "why": "AC-1 has EN only (Halliburton 2020); HKLII full-text searches returned nothing usable and two Halliburton-citing HK cases were checked and ruled out (Centre Chase [2024] HKCA 1179, China Medical [2026] HKCFI 276 - neither an arbitrator-bias decision)",
      "action": "HKLII: Chinese terms + 'arbitrator misconduct'; noteup Halliburton citers via getcasenoteup"},
     {"id": "Q-008", "sub_test": "AC-1", "jurisdiction": "SG", "state": "open",
      "question": "Any SGCA authority on Art 12 challenge?",
      "why": "eLitigation down at survey (503, whole site); SG branch empty",
      "action": "retry elitigation.sg/gd/s/; check IBA Guidelines reception in SG"},
    ])

    out = {"generated": TODAY, "dataset_version": E['version'], "policy": POLICY,
           "jurisdiction_labels": JZH, "nodes": nodes, "module_nodes": module_nodes, "watchlist": WATCH, "queue": QUEUE,
           "history": [{"timeline": tid, "sub_test": tl['sub_test'], "title_en": tl.get('title_en', tl['title']),
                        "events": tl['events']} for tid, tl in E['timelines'].items()]}
    emit('maintenance', out, indent=1)

    att = [n for n in nodes if n['status']=='attested']
    gap = [n for n in nodes if n['work_type']=='coverage-gap']
    print(f"nodes: {len(nodes)}  attested: {len(att)}  no-authority: {len(nodes)-len(att)}")
    rate_att = sum(n['rate_per_year'] for n in att)
    print(f"annual expected drift events (attested nodes only): {rate_att:.2f}")
    print(f"  -> extrapolated to a 15-claim library: {rate_att/1*15:.0f}/yr  (this dataset = 1 claim family)")
    print(f"coverage gaps (no authority on file): {len(gap)} nodes")
    print("review calendar (attested nodes, when P(missed) crosses trigger):")
    for n in sorted(att,key=lambda x:x['review_due_year']):
        print(f"   {n['review_due_year']}  {n['node']:9s} interval~{n['expected_interval_years']:>5}y  {n['en'][:38]}")

    matt = [n for n in module_nodes if n['status'] == 'attested']
    mgap = [n for n in module_nodes if n['work_type'] == 'coverage-gap']
    print(f"module timelines: {len(module_nodes)} nodes ({len(matt)} attested, {len(mgap)} gaps)")
    for n in sorted(matt, key=lambda x: x['review_due_year']):
        print(f"   {n['review_due_year']}  {n['node']:12s} interval~{n['expected_interval_years']:>5}y  {n['en'][:38]}")
    for n in mgap:
        print(f"   {'--':>7}  {n['node']:12s} GAP  {n['en'][:38]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
