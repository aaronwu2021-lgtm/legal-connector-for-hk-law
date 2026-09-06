# -*- coding: utf-8 -*-
"""Snapshot the HKLII CFA index and derive the FACV candidate pool.

Methodology (reproduces the 2146 / ~677 figures from first principles):
  1. Paginate /api/getcasefiles?caseDb=hkcfa (index only — no judgment texts).
  2. Count totalfiles (expected: 2146 at time of writing) and bucket entries
     by case-number prefix (FACV civil appeals, FACC criminal, FAMV/FAMC leave).
  3. The FACV bucket is the candidate pool for direction-2 tasks. Selecting a
     case from the pool remains a reader judgment (doctrinal movement, cross-
     jurisdictional interest, closed-universe matter feasibility) — this script
     only proves the pool, it does not choose.

FACV counts drift as HKLII updates the index (674 live vs 677 reported
2026-09-04); totalfiles is the stable anchor. Re-run to refresh pool.json.

    python hkcfa_pool.py   # -> pool.json (index snapshot, no texts)
"""
import json
import os
import re
import urllib.request
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = ("https://www.hklii.hk/api/getcasefiles?caseDb=hkcfa&lang=EN"
        "&itemsPerPage=500&page=%d")


def main():
    pre, facv, n, page = Counter(), [], 0, 1
    while True:
        d = json.loads(urllib.request.urlopen(BASE % page, timeout=60).read().decode("utf-8"))
        js = d.get("judgments", [])
        if not js:
            break
        for j in js:
            n += 1
            s = json.dumps(j, ensure_ascii=False)
            m = re.search(r"(FACV|FAMV|FACC|FAMC)[0-9]", s)
            tag = m.group(1) if m else "other"
            pre[tag] += 1
            if tag == "FACV":
                num = re.search(r"FACV\s*([0-9]+/[0-9]+)", s)
                facv.append({"ref": num.group(0) if num else "?",
                             "entry": s[:220]})
        page += 1
        if page > 10:
            break
    out = {"totalfiles": n, "prefixes": dict(pre),
           "facv_pool": len(facv), "facv": facv,
           "note": "pool membership is necessary, not sufficient: case selection "
                   "is a reader judgment recorded in the task builder."}
    with open(os.path.join(HERE, "pool.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"totalfiles={n} prefixes={dict(pre)} FACV pool={len(facv)}")
    print("wrote pool.json")


if __name__ == "__main__":
    main()
