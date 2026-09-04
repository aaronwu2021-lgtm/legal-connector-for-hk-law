# -*- coding: utf-8 -*-
"""Unblind and score Experiment 3. Run only after judge.py has finished.

Reports, per task: criteria passed under each condition, all-pass under each
condition, and the drift-sensitive subset separately — because the as_of pair
(HKM-02 / HKM-03) is the only part of the design that tests time-indexing, and
its result should not be averaged away. Paired statistics use McNemar's exact
test on discordant pairs, as in Experiment 2.

    python score.py
"""
import json
import os
from math import comb

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "runs")
load = lambda p: json.load(open(p, encoding="utf-8"))

key = load(os.path.join(RUNS, "blind_key.json"))
tasks = {t["id"]: t for t in load(os.path.join(HERE, "tasks.json"))["tasks"]}
drift_ids = {c["id"] for t in tasks.values() for c in t["rubric"] if c["drift_sensitive"]}

# label -> verdicts, joined to condition through the key
res = {}   # (task, cond) -> {criterion: PASS/FAIL}
for label, meta in key.items():
    p = os.path.join(RUNS, "verdicts", label + ".json")
    if not os.path.exists(p):
        raise SystemExit(f"missing verdict for {label} — judging is incomplete; do not score")
    v = load(p)
    res[(meta["task"], meta["condition"])] = {x["criterion"]: x["verdict"] for x in v["verdicts"]}


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


print(f"{'task':8s} {'bare':>10s} {'conn':>10s}   all-pass bare/conn   drift-sensitive bare/conn")
tot = {"bare": [0, 0], "conn": [0, 0]}
allpass = {"bare": 0, "conn": 0}
crit_gain = crit_loss = 0
drift_tot = {"bare": [0, 0], "conn": [0, 0]}
for tid, t in tasks.items():
    row = {}
    for cond in ("bare", "conn"):
        v = res.get((tid, cond), {})
        n = len(t["rubric"])
        p = sum(1 for c in t["rubric"] if v.get(c["id"]) == "PASS")
        d = [c["id"] for c in t["rubric"] if c["drift_sensitive"]]
        dp = sum(1 for cid in d if v.get(cid) == "PASS")
        row[cond] = (p, n, p == n, dp, len(d))
        tot[cond][0] += p; tot[cond][1] += n
        allpass[cond] += p == n
        drift_tot[cond][0] += dp; drift_tot[cond][1] += len(d)
    for c in t["rubric"]:
        b = res.get((tid, "bare"), {}).get(c["id"]); k = res.get((tid, "conn"), {}).get(c["id"])
        if b != "PASS" and k == "PASS": crit_gain += 1
        if b == "PASS" and k != "PASS": crit_loss += 1
    b, k = row["bare"], row["conn"]
    print(f"{tid:8s} {b[0]:>4}/{b[1]:<5} {k[0]:>4}/{k[1]:<5}   "
          f"{'Y' if b[2] else 'n'} / {'Y' if k[2] else 'n'}            "
          f"{b[3]}/{b[4]} / {k[3]}/{k[4]}" + ("" if b[4] else "   (none)"))

print()
print(f"criteria   bare {tot['bare'][0]}/{tot['bare'][1]}   conn {tot['conn'][0]}/{tot['conn'][1]}   "
      f"discordant {crit_gain}-{crit_loss}   McNemar exact p={mcnemar(crit_gain, crit_loss):.4f}")
print(f"all-pass   bare {allpass['bare']}/{len(tasks)}   conn {allpass['conn']}/{len(tasks)}")
print(f"drift-sensitive criteria   bare {drift_tot['bare'][0]}/{drift_tot['bare'][1]}   "
      f"conn {drift_tot['conn'][0]}/{drift_tot['conn'][1]}   <- the time-indexing claim lives here")
print()
print("Report all three lines. The drift-sensitive line is the one neither earlier "
      "experiment could produce; if it is at ceiling in both conditions, say so.")
