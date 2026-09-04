# -*- coding: utf-8 -*-
"""Check that the eval set's rubrics are actually grounded.

build_tasks.py ASSERTS that every criterion rests on a pin-cited authority. This
checks it, so the claim survives someone editing a rubric later. It reports:

  1. criteria naming a case that does not appear in data/elements.json at all;
  2. criteria naming a case that appears only at verified-web, i.e. with no pin
     cite — the rubric would then be testing an unaudited characterisation;
  3. criteria citing authority that post-dates the task's as_of year, which
     would make the criterion unpassable rather than drift-sensitive;
  4. criteria with no `discriminates_against`, which test nothing specific.

Exits non-zero if anything in (1), (3) or (4) is found. Category (2) is reported
but tolerated where the criterion rests on a statute rather than a case.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(ROOT))
PINNED = {"verified-primary", "verified-quoted"}


def index_elements():
    """case name -> set of verification levels seen for it"""
    with open(os.path.join(REPO, "data", "elements.json"), encoding="utf-8") as f:
        d = json.load(f)
    seen, years = {}, {}

    def walk(o):
        if isinstance(o, dict):
            for a in o.get("auth", []) or []:
                seen.setdefault(a["case"], set()).add(a.get("verified"))
            if "holding" in o and "name" in o:
                seen.setdefault(o["name"], set()).add(o.get("verified"))
                if o.get("year"):
                    years[o["name"]] = o["year"]
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(d)
    return seen, years


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s.lower())).strip()


def match(name, seen):
    """Longest dataset case name whose party-one words all appear in `name`.

    Longest-wins matters: keying on the first word alone made "Long Year
    Development" match the record for "Long v Lloyd", which silently grounded a
    damages criterion on the wrong case.
    """
    n = norm(name)
    best = None
    for case in seen:
        key = norm(re.split(r"\s+v\.?\s+", case.lower())[0])
        if not key:
            continue
        if re.search(r"\b" + re.escape(key) + r"\b", n):
            if best is None or len(key) > len(norm(re.split(r"\s+v\.?\s+", best.lower())[0])):
                best = case
    return best


def main():
    with open(os.path.join(ROOT, "tasks.json"), encoding="utf-8") as f:
        ts = json.load(f)
    seen, years = index_elements()

    unknown, unpinned, anachronistic, undiscriminating = [], [], [], []

    for t in ts["tasks"]:
        as_of = t["as_of"]
        for cr in t["rubric"]:
            if not cr.get("discriminates_against"):
                undiscriminating.append(cr["id"])

            # every 4-digit year named in the authority string
            for y in re.findall(r"\b(19|20)\d{2}\b", cr["authority"] + " " + cr["pin"]):
                pass
            for y in [int(x) for x in re.findall(r"\b((?:19|20)\d{2})\b",
                                                 cr["authority"] + " " + cr["pin"])]:
                # a criterion may legitimately name a later case in order to
                # require that it NOT be used; those say so.
                if y > as_of and "NOT" not in cr["criterion"] and "not " not in cr["criterion"].lower():
                    anachronistic.append((cr["id"], y, as_of))

            hit = match(cr["authority"], seen)
            if hit is None:
                if not re.search(r"Cap\.|statute|authority_rule|gaps|test$|^[DET]\d", cr["authority"]):
                    unknown.append((cr["id"], cr["authority"]))
            elif not (seen[hit] & PINNED):
                unpinned.append((cr["id"], hit, sorted(x for x in seen[hit] if x)))

    n = len(ts["tasks"])
    tot = sum(len(t["rubric"]) for t in ts["tasks"])
    print(f"tasks {n}  criteria {tot}")
    print(f"  criteria with no discriminator      : {len(undiscriminating)}")
    print(f"  authority not found in elements.json: {len(unknown)}")
    print(f"  authority present but not pin-cited : {len(unpinned)}")
    print(f"  authority post-dating as_of         : {len(anachronistic)}")

    for cid, a in unknown:
        print(f"    UNKNOWN   {cid}: {a}")
    for cid, hit, lv in unpinned:
        print(f"    NO PIN    {cid}: {hit} at {lv}")
    for cid, y, a in anachronistic:
        print(f"    ANACHRON  {cid}: cites {y} in an as_of={a} task")

    bad = len(unknown) + len(anachronistic) + len(undiscriminating)
    if bad:
        print(f"\nFAIL: {bad} criteria must be fixed")
        return 1
    print("\nOK: every criterion names a discriminator and a resolvable, "
          "non-anachronistic authority")
    return 0


if __name__ == "__main__":
    sys.exit(main())
