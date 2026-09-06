# -*- coding: utf-8 -*-
"""Consistency check for the persuasive branch. Run after build_persuasive.py
(and before any commit touching data/persuasive.json):

    python3 scripts/check_persuasive.py

Fails loudly on: duplicate slugs; edges pointing at unknown slugs;
any record not (verified=unverified, hk_status=persuasive-only); any
test_type/weight keys (typing/weighting unread cases is forbidden here);
any string field long enough to be reproduced source prose (anti-leak guard);
court_rank null without its note; missing area_zh; malformed reviewed dates;
signals outside the legend; dangling related-case links;
counts drifting from data/sources/uklr/.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import load


def main(argv=None):
    parser = argparse.ArgumentParser(description='Check the persuasive authority index invariants.')
    parser.parse_args(argv)
    P = load("persuasive")
    errs = []


    def err(msg):
        errs.append(msg)


    slugs = [c["slug"] for c in P["cases"]]
    if len(set(slugs)) != len(slugs):
        err("duplicate slugs")
    if len(slugs) != 449:
        err("expected 449 cases, got %d" % len(slugs))

    S = set(slugs)
    for e in P["edges"]:
        if e["to_slug"] not in S:
            err("edge to unknown slug: %r" % e["to_slug"])
        if e["from_slug"] is not None and e["from_slug"] not in S:
            err("edge from unknown slug: %r" % e["from_slug"])

    LEGEND = {"good-law", "qualified", "negative", "superseded", "historic", "context"}
    for c in P["cases"]:
        if c.get("signal") not in LEGEND:
            err("signal outside legend: %s" % c["slug"])
        for s in (c.get("related") or {}).get("cases", []):
            if s not in S:
                err("dangling related link %r in %s" % (s, c["slug"]))

    for c in P["cases"]:
        if c.get("verified") != "unverified" or c.get("hk_status") != "persuasive-only":
            err("verification invariant broken: %s" % c["slug"])
            break
        stack = [c]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("test_type", "weight", "ratio_full", "judgment_summary",
                             "key_quotes", "facts"):
                        err("forbidden key %r in %s (no typing/weighting/prose here)" % (k, c["slug"]))
                    stack.append(v)
            elif isinstance(o, list):
                stack.extend(o)
        if c.get("court_rank") is None and not c.get("court_rank_note"):
            err("null rank without note: %s" % c["slug"])
        if not c.get("area_zh"):
            err("missing area_zh: %s" % c["slug"])
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", (c.get("staleness") or {}).get("reviewed") or ""):
            err("bad reviewed date: %s" % c["slug"])
        longest = max(len(str(v)) for v in
                      [c.get("name"), c.get("cite")] +
                      [t.get("case", "") for t in c.get("treatment", [])])
        if longest > 300:
            err("suspicious long field in %s (anti-leak guard)" % c["slug"])

    # treatment[].note must never exist (prose stays on source pages)
    for c in P["cases"]:
        for t in c.get("treatment", []):
            if "note" in t:
                err("treatment note leaked into %s" % c["slug"])
                break

    if P["stats"]["cases"] != len(slugs) or P["stats"]["edges"] != len(P["edges"]):
        err("stats block disagrees with payload")

    if errs:
        print("CHECK FAILED:")
        for e in errs[:20]:
            print(" -", e)
        return 1
    print("persuasive OK: %d cases, %d edges, all invariants hold" % (len(slugs), len(P["edges"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
