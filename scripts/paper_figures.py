# -*- coding: utf-8 -*-
"""Print every figure the paper quotes, computed from the released artefacts.

The paper's thesis is that a claim should carry the evidence behind it. Its own
numbers were not held to that: a hand-maintained table said the type
distribution was counted "over 26 modelled stages" while the table's own columns
summed to 30, because 26 counted registry.json alone and the table counted
registry plus scored. The drift-interval sentence went stale the moment a node
was filled.

So the numbers are computed here instead of remembered. Run this, quote the
output, and re-run it after any builder change.

    python scripts/paper_figures.py
"""
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load = lambda *p: json.load(open(os.path.join(ROOT, *p), encoding="utf-8"))

el = load("data", "elements.json")
reg = load("data", "registry.json")
sc = load("data", "scored.json")
mt = load("data", "maintenance.json")

print("=" * 66)
print("ELEMENT LIBRARY")
print("=" * 66)
subtests = sum(len(e["sub_tests"]) for e in el["elements"]) + len(el["defences"])
print(f"  sub-tests in the misrepresentation family : {subtests}")
print(f"  jurisdictions                             : {len(el['jurisdictions'])}")
print(f"  timelines / timeline events               : {len(el['timelines'])} / "
      f"{sum(len(t['events']) for t in el['timelines'].values())}")
print(f"  jurisdiction case records                 : "
      f"{sum(len(j.get('cases', [])) for j in el['jurisdictions'].values())}")

lv = Counter()
def tally(o):
    if isinstance(o, dict):
        for a in o.get("auth", []) or []:
            lv[a.get("verified")] += 1
        if ("holding" in o or "ref" in o) and "verified" in o:
            lv[o["verified"]] += 1
        for v in o.values(): tally(v)
    elif isinstance(o, list):
        for v in o: tally(v)
tally(el)
print(f"\n  VERIFICATION LEVELS (total {sum(lv.values())})")
for k in ("verified-primary", "verified-quoted", "verified-web", "unverified"):
    if lv.get(k):
        print(f"    {k:20s} {lv[k]}")

print("\n" + "=" * 66)
print("TYPED REGISTRY  (registry.json + scored.json — the paper counts BOTH)")
print("=" * 66)
mods = reg["modules"] + sc["modules"]
stages = [s for m in mods for s in m["stages"]]
print(f"  causes of action modelled                 : {len(mods)}"
      f"  ({len(reg['modules'])} registry + {len(sc['modules'])} scored)")
print(f"  modelled stages                           : {len(stages)}"
      f"  ({len([s for m in reg['modules'] for s in m['stages']])} + "
      f"{len([s for m in sc['modules'] for s in m['stages']])})")
kinds = Counter(s.get("test_type") for s in stages)
print("  structural kinds:")
for k in ("conjunctive", "balancing", "disjunctive-gateway",
          "threshold-discretion", "presumption-rebuttal"):
    print(f"    {k:24s} {kinds.get(k, 0)}")
print(f"    {'(sum)':24s} {sum(kinds.values())}")

tiered = sum(1 for m in mods for s in m["stages"]
             if s.get("test_type") == "balancing"
             for f in s.get("factors", []) + s.get("counter_factors", [])
             if f.get("tier"))
print(f"  balancing factors carrying a tier         : {tiered}")

print("\n" + "=" * 66)
print("DRIFT")
print("=" * 66)
att = [n for n in mt["nodes"] if n["status"] == "attested"]
rate = sum(n["rate_per_year"] for n in att)
print(f"  nodes (sub-tests x jurisdictions)         : {len(mt['nodes'])}")
print(f"  attested / coverage gaps                  : {len(att)} / "
      f"{len(mt['nodes']) - len(att)}")
print(f"  aggregate drift events per year           : {rate:.2f}")
print(f"  extrapolated to a 15-claim library        : {rate * 15:.0f}/yr")
byiv = sorted(att, key=lambda n: n["expected_interval_years"])
print(f"  shortest expected interval                : "
      f"{byiv[0]['expected_interval_years']:.1f}y  ({byiv[0]['node']}, {byiv[0]['en']})")
print(f"  longest expected interval                 : "
      f"{byiv[-1]['expected_interval_years']:.1f}y  ({byiv[-1]['node']}, {byiv[-1]['en']})")

print("\n" + "=" * 66)
print("CORPUS AND EXPERIMENTS")
print("=" * 66)
print(f"  HK land-law case notes                    : "
      f"{len(load('data', 'corpus', 'hklandlaw-casenotes.json'))}")

e1 = load("experiments", "exp1-lab", "scored_criteria_ids.json")["tasks"]
scored = sum(len(v["scored_criteria"]) for v in e1.values())
total = sum(v["n_criteria_total"] for v in e1.values())
print(f"  exp1 tasks / scored criteria / of total   : "
      f"{len(e1)} / {scored} / {total}")

items = load("experiments", "exp2-probe", "probe.json")["items"]
cls = Counter(i["class"] for i in items)
print(f"  exp2 probe items                          : {len(items)}  "
      + ", ".join(f"{k}={v}" for k, v in sorted(cls.items())))
print(f"  exp2 controls flagged uncovered           : "
      f"{sum(1 for i in items if i['class'] == 'CTRL' and not i.get('connector_covers'))}"
      f"/{cls.get('CTRL', 0)}")

t3 = load("experiments", "exp3-hk-matter", "tasks.json")["counts"]
print(f"  exp3 tasks / criteria / drift-sensitive   : "
      f"{t3['tasks']} / {t3['criteria']} / {t3['drift_sensitive_criteria']}")

print("\n" + "=" * 66)
print("EXPERIMENT OUTCOMES (quote these, not hand counts)")
print("=" * 66)
e1r = load("experiments", "exp1-lab", "results.json")["rows"]
ap, wb, wc = {}, 0, 0
for r in e1r:
    ap.setdefault(r["slug"], {})[r["condition"]] = (r["pass"] == r["n"])
    if r["condition"] == "base":
        wb += r.get("words", 0)
    else:
        wc += r.get("words", 0)
un = sum(1 for v in ap.values()
         if v.get("base") == v.get("conn") and "base" in v and "conn" in v)
pb = sum(r["pass"] for r in e1r if r["condition"] == "base")
nb = sum(r["n"] for r in e1r if r["condition"] == "base")
pc = sum(r["pass"] for r in e1r if r["condition"] == "conn")
nc = sum(r["n"] for r in e1r if r["condition"] == "conn")
print(f"  exp1 base / conn                          : {pb}/{nb} vs {pc}/{nc}")
print(f"  exp1 tasks unchanged (all-pass same)      : {un}/{len(ap)}")
print(f"  exp1 output words base -> conn            : {wb} -> {wc} "
      f"({100 * (wb - wc) / wb:.1f}% drop)")
e2j = {c: load("experiments", "exp2-probe", "probe_judged", c + ".json")
       for c in ("SET-A", "SET-B")}
for c, lab in (("SET-A", "bare"), ("SET-B", "conn")):
    items = e2j[c]["items"]
    print(f"  exp2 {lab} hallucinations                : "
          f"{sum(1 for i in items if i.get('hallucinated'))}/{len(items)}")
print()
