# -*- coding: utf-8 -*-
"""Check that the eval set's rubrics are actually grounded.

The bar is a pin-cited authority in data/elements.json or in a
data/registry.json module timeline / authority record. This checks it, so the
claim survives someone editing a rubric later. It reports:

  1. criteria naming a case that does not appear in data/elements.json at all;
  2. criteria naming a case that appears only at verified-web, i.e. with no pin
     cite — the rubric would then be testing an unaudited characterisation;
  3. criteria citing authority that post-dates the task's as_of year, which
     would make the criterion unpassable rather than drift-sensitive;
  4. criteria with no `discriminates_against`, which test nothing specific.

Exits non-zero if anything in (1)-(4) is found. No criterion is allowlisted to
rest on web-level authority.
"""
import argparse
from datetime import date
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(ROOT))
PINNED = {"verified-primary", "verified-quoted"}


def index_elements():
    """Return verification levels and exact decision dates by case name."""
    with open(os.path.join(REPO, "data", "elements.json"), encoding="utf-8") as f:
        d = json.load(f)
    seen, decision_dates, pins = {}, {}, {}

    def walk(o):
        if isinstance(o, dict):
            for a in o.get("auth", []) or []:
                seen.setdefault(a["case"], set()).add(a.get("verified"))
                if a.get("pin"):
                    pins.setdefault(a["case"], []).append(a["pin"])
            if "holding" in o and "name" in o:
                seen.setdefault(o["name"], set()).add(o.get("verified"))
                if o.get("pin"):
                    pins.setdefault(o["name"], []).append(o["pin"])
                if o.get("decision_date"):
                    decision_dates[o["name"]] = date.fromisoformat(o["decision_date"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(d)
    norm_level = {"primary": "verified-primary", "quoted": "verified-quoted",
                  "web": "verified-web", "unverified": "unverified",
                  "verified-primary": "verified-primary",
                  "verified-quoted": "verified-quoted",
                  "verified-web": "verified-web"}
    with open(os.path.join(REPO, "data", "registry.json"), encoding="utf-8") as f:
        for m in json.load(f)["modules"]:
            for a in m.get("authorities", []) or []:
                if (a.get("court") or "").strip() in ("-", "\u2013", "\u2014", ""):
                    continue  # legislation record, not a case
                seen.setdefault(a["case"], set()).add(
                    norm_level.get(a.get("verified"), a.get("verified")))
                if a.get("pin"):
                    pins.setdefault(a["case"], []).append(a["pin"])
            for t in (m.get("timelines") or {}).values():
                for e in t.get("events", []) or []:
                    seen.setdefault(e["case"], set()).add(
                        norm_level.get(e.get("verified"), e.get("verified")))
                    if e.get("pin"):
                        pins.setdefault(e["case"], []).append(e["pin"])
                    if e.get("decision_date"):
                        decision_dates[e["case"]] = date.fromisoformat(e["decision_date"])
    return seen, decision_dates, pins


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s.lower())).strip()


def match(name, seen):
    """Longest complete dataset case name present in the authority string."""
    n = norm(name)
    hits = [case for case in seen if re.search(r"\b" + re.escape(norm(case)) + r"\b", n)]
    return max(hits, key=lambda case: len(norm(case))) if hits else None


EXEMPT = re.compile(r"Cap\.|statute|authority_rule|gaps|test$|^[DET]\d|A Solicitor v Law Society")


def main(argv=None):
    parser = argparse.ArgumentParser(description='Validate the Experiment 3 task criteria.')
    parser.add_argument("tasks_path", nargs="?", default=os.path.join(ROOT, "tasks.json"),
                        help="optional tasks JSON path")
    args = parser.parse_args(argv)
    tasks_path = args.tasks_path
    with open(tasks_path, encoding="utf-8") as f:
        ts = json.load(f)
    seen, decision_dates, recorded_pins = index_elements()

    unknown, unpinned, anachronistic, date_unresolved, undiscriminating = [], [], [], [], []

    for t in ts["tasks"]:
        raw_as_of = t["as_of"]
        if isinstance(raw_as_of, bool):
            print(f"    INVALID   {t.get('id', '<unknown>')}: boolean as_of")
            return 1
        if isinstance(raw_as_of, int) and 1000 <= raw_as_of <= 9999:
            as_of = date(raw_as_of, 12, 31)
        elif isinstance(raw_as_of, str) and re.fullmatch(r"[1-9]\d{3}-\d{2}-\d{2}", raw_as_of):
            try:
                as_of = date.fromisoformat(raw_as_of)
            except ValueError:
                print(f"    INVALID   {t.get('id', '<unknown>')}: invalid as_of date {raw_as_of}")
                return 1
        else:
            print(f"    INVALID   {t.get('id', '<unknown>')}: as_of must be a year or YYYY-MM-DD")
            return 1
        for cr in t["rubric"]:
            if not cr.get("discriminates_against"):
                undiscriminating.append(cr["id"])
            if cr.get("authority_polarity") not in {"positive", "negative"}:
                undiscriminating.append(cr["id"] + " (invalid authority_polarity)")

            negative = cr.get("authority_polarity") == "negative"
            for authority_part in [part.strip() for part in cr["authority"].split(";") if part.strip()]:
                years = [int(x) for x in re.findall(r"\b((?:19|20)\d{2})\b", authority_part)]
                if years and max(years) > as_of.year and not negative:
                    anachronistic.append((cr["id"], max(years), raw_as_of))

                hit = match(authority_part, seen)
                if hit is None:
                    if not EXEMPT.search(authority_part):
                        unknown.append((cr["id"], authority_part))
                    continue
                if not (seen[hit] & PINNED) or not recorded_pins.get(hit):
                    unpinned.append((cr["id"], hit, sorted(x for x in seen[hit] if x)))
                if (not negative and isinstance(raw_as_of, str) and years
                        and max(years) == as_of.year):
                    decided = decision_dates.get(hit)
                    if decided is None:
                        date_unresolved.append((cr["id"], hit, raw_as_of))
                    elif decided > as_of:
                        anachronistic.append((cr["id"], decided.isoformat(), raw_as_of))

    n = len(ts["tasks"])
    tot = sum(len(t["rubric"]) for t in ts["tasks"])
    print(f"tasks {n}  criteria {tot}")
    print(f"  criteria with no discriminator      : {len(undiscriminating)}")
    print(f"  authority not found in elements.json: {len(unknown)}")
    print(f"  authority present but not pin-cited : {len(unpinned)}")
    print(f"  authority post-dating as_of         : {len(anachronistic)}")
    print(f"  same-year authority date unresolved : {len(date_unresolved)}")

    for cid, a in unknown:
        print(f"    UNKNOWN   {cid}: {a}")
    for cid, hit, lv in unpinned:
        print(f"    NO PIN    {cid}: {hit} at {lv}")
    for cid, y, a in anachronistic:
        print(f"    ANACHRON  {cid}: cites {y} in an as_of={a} task")
    for cid, hit, a in date_unresolved:
        print(f"    NO DATE   {cid}: {hit} has no exact decision_date for as_of={a}")

    bad = (len(unknown) + len(unpinned) + len(anachronistic)
           + len(date_unresolved) + len(undiscriminating))
    if bad:
        print(f"\nFAIL: {bad} criteria must be fixed")
        return 1
    print("\nOK: every criterion names a discriminator and a resolvable, "
          "non-anachronistic authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
