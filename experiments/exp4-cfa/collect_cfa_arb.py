# -*- coding: utf-8 -*-
"""exp4 candidate collector: multi-query HKLII simplesearch survey of CFA
arbitration-related decisions 2018-2026.

Survey, not census: HKLII search coverage is uneven, so a nil result is
recorded as a nil, never as evidence of absence. Output is a candidate
list with neutral cites; keys are hand-written afterwards by reading the
judgment texts (see exp4 protocol), never inferred here.
Writes experiments/exp4-cfa/cfa_arb_candidates.json (ASCII-escaped)."""
import io
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

BASE = "https://www.hklii.hk/api/"
QUERIES = ["arbitration", "Model Law", "Cap 609", "New York Convention",
           "stay in favour of arbitration", "section 81",
           "section 34 arbitration", "arbitrator bias"]
OUT = Path(__file__).resolve().with_name("cfa_arb_candidates.json")


def get(path, params):
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "doctrine-connector-exp4/0.1"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


seen = {}
per_query = {}
for qstr in QUERIES:
    try:
        data = get("simplesearch", {"searchstring": qstr, "disablefuzzy": "true"})
    except Exception as e:  # keep survey going; record the failure
        per_query[qstr] = {"error": ascii(str(e))}
        continue
    results = data.get("results", [])
    per_query[qstr] = {"n_results": len(results)}
    for c in results:
        if c.get("db") not in ("Court of Final Appeal",):
            continue
        pub = c.get("pub_date", "") or ""
        if not pub[:4].isdigit() or int(pub[:4]) < 2018:
            continue
        key = c.get("neutral") or c.get("path")
        rec = seen.setdefault(key, {
            "neutral": c.get("neutral"), "path": c.get("path"),
            "pub_date": pub, "act": c.get("act"),
            "title": c.get("title"), "parallel": c.get("parallel"),
            "coram": c.get("coram"), "queries": []})
        if qstr not in rec["queries"]:
            rec["queries"].append(qstr)
    time.sleep(1)

payload = {
    "survey": "HKLII simplesearch survey, NOT a census. Nil results are nils, "
              "never evidence of absence. Queries run 2026-09-05.",
    "queries": QUERIES,
    "per_query": per_query,
    "n_candidates": len(seen),
    "candidates": sorted(seen.values(), key=lambda c: c.get("pub_date", "")),
}
io.open(OUT, "w", encoding="utf-8").write(
    json.dumps(payload, ensure_ascii=True, indent=1, sort_keys=True))
print(ascii("queries ok: %d/%d candidates: %d" %
            (sum(1 for v in per_query.values() if "n_results" in v),
             len(QUERIES), len(seen))))
for c in payload["candidates"]:
    print(ascii("%s %s | %s | %s" %
                (c.get("pub_date", "")[:10], c.get("neutral"),
                 c.get("act"), c.get("title", "")[:60])))
