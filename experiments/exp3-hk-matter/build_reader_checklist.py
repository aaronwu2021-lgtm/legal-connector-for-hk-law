# -*- coding: utf-8 -*-
"""Build the independent-reader checklist for the Experiment 3 keys.

Experiment 2's re-score showed that keys taken from the library under test
measure agreement with the artefact, not correctness: HK-07 and SG-01 keyed
the library's own errors. So before Experiment 3 is run, someone who did not
write the library must check every rubric criterion against its pin cite.

This script joins tasks.json against data/elements.json and writes
reader_checklist.md: a priority-ordered review queue plus a per-criterion
table with the verification level found in the library. Regenerate, don't
hand-edit:

    python build_reader_checklist.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from validate_tasks import match as match_case  # noqa: E402

REPO = os.path.dirname(os.path.dirname(HERE))
PINNED = {"verified-primary", "verified-quoted"}
EXEMPT = re.compile(r"Cap\.|statute|authority_rule|gaps|test$|^[DET]\d")


def case_index():
    """case name -> (set of levels, blob of recorded pins)."""
    with open(os.path.join(REPO, "data", "elements.json"), encoding="utf-8") as f:
        d = json.load(f)
    seen = {}

    def walk(o):
        if isinstance(o, dict):
            for a in o.get("auth", []) or []:
                e = seen.setdefault(a["case"], {"levels": set(), "pins": []})
                e["levels"].add(a.get("verified"))
                if a.get("pin"):
                    e["pins"].append(a["pin"])
            if "holding" in o and "name" in o:
                e = seen.setdefault(o["name"], {"levels": set(), "pins": []})
                e["levels"].add(o.get("verified"))
                if o.get("pin"):
                    e["pins"].append(o["pin"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(d)
    return seen


def norm_pin(s):
    return re.sub(r"[\s\[\]\(\)\u00b6\u00a7,;]", "", s or "")


def pin_numbers(blob):
    """Covered paragraph/page numbers: explicit [n] plus [a]-[b] ranges."""
    nums = set()
    for a, b in re.findall(r"\[(\d+)\]\s*-\s*\[(\d+)\]", blob):
        nums.update(range(int(a), int(b) + 1))
    for n in re.findall(r"\[(\d+)\]", blob):
        nums.add(int(n))
    return nums


def is_date_ref(chunk):
    """Chunk whose only numbers are calendar years (or the word 'decided')."""
    if "decided" in chunk.lower():
        return True
    digits = re.findall(r"\d+", chunk)
    return bool(digits) and all(
        len(d) == 4 and d.startswith(("19", "20")) for d in digits)


def match_part(part, seen):
    """match_case on the full party-one; fall back to the first two words.

    The fallback only fires where the full phrase fails (e.g. a shortened
    case name in the authority string) and is flagged approximate: it is
    used to gather pins for a human reader, never to pass validation.
    """
    hit = match_case(part, {k: set() for k in seen})
    if hit:
        return hit, False
    from validate_tasks import norm
    words = norm(part).split()
    if len(words) >= 2:
        phrase = " ".join(words[:2])
        for case in seen:
            if norm(case).split(" v ")[0].startswith(phrase):
                return case, True
    return None, False


def check_pin(crit_pin, recorded_pins):
    """Return the pin chunks of the criterion not covered by recorded pins.

    Skips date references (a year establishing anachronism is not a pin to
    cover) and purely descriptive pins ('Appeal Committee'), which the reader
    checks against the record's court field instead.
    """
    blob = " ".join(recorded_pins)
    covered_nums = pin_numbers(blob)
    flat = norm_pin(blob)
    missing = []
    for chunk in re.split(r";", crit_pin or ""):
        c = chunk.strip()
        if not c or is_date_ref(c):
            continue
        if not re.search(r"\d", c):
            continue  # descriptive pin, no passage number to cover
        nums = [int(x) for x in re.findall(r"\[(\d+)\]", c)
                if not (1700 <= int(x) <= 2100)]
        if nums or re.search(r"\[\d+\]", c):
            if nums and all(n in covered_nums for n in nums):
                continue
            if not nums:
                continue  # only year-like brackets: a date reference
            missing.append(c)
            continue
        if norm_pin(c) and norm_pin(c) in flat:
            continue
        # page-pin style (407D-408D): compare digit runs
        digits = re.findall(r"\d+[A-Z]?", c)
        if digits and all(re.search(r"\b" + re.escape(dg), blob) for dg in digits):
            continue
        missing.append(c)
    return missing


def main():
    seen = case_index()
    with open(os.path.join(HERE, "tasks.json"), encoding="utf-8") as f:
        ts = json.load(f)["tasks"]

    rows = []
    for t in ts:
        for cr in t["rubric"]:
            parts = [p.strip() for p in cr["authority"].split(";")]
            matched, structural, web_only, missing_pins = [], [], [], []
            approx = []
            for p in parts:
                if EXEMPT.search(p):
                    structural.append(p)
                    continue
                hit, is_approx = match_part(p, seen)
                if hit is None:
                    structural.append(p + "  [no case record: human-check only]")
                    continue
                matched.append((p, hit))
                if is_approx:
                    approx.append("%s ~ %s" % (p[:60], hit))
                if not (seen[hit]["levels"] & PINNED):
                    web_only.append(hit)
            if matched:
                rec = []
                for _, hit in matched:
                    rec.extend(seen[hit]["pins"])
                # No recorded pins anywhere (e.g. a web-only record): there is
                # nothing to compare, and the case is already in P0-a.
                if rec:
                    missing_pins = check_pin(cr.get("pin", ""), rec)
            negative = cr["criterion"].lower().startswith(("does not", "does not claim", "does not treat"))
            rows.append({"task": t["id"], "as_of": t["as_of"], "cr": cr,
                         "matched": matched, "structural": structural,
                         "web_only": web_only, "missing_pins": missing_pins,
                         "approx": approx, "negative": negative})

    p0_web = [r for r in rows if r["web_only"]]
    p0_pin = [r for r in rows if r["missing_pins"]]
    p1_struct = [r for r in rows if r["structural"] and r not in p0_web]
    p1_recent = [r for r in rows if re.search(r"\[(2025|2026)\]", r["cr"]["authority"]) and r not in p0_web + p0_pin]
    rest = [r for r in rows if r not in p0_web + p0_pin + p1_struct + p1_recent]

    L = []
    A = L.append
    A("<!-- GENERATED by build_reader_checklist.py -- do not edit by hand. -->\n")
    A("# Experiment 3 — independent-reader checklist\n")
    A("Status of the keys: **UNRUN, UNREVIEWED**. No model output has been judged "
      "against `tasks.json`, and no independent reader has signed off the keys. "
      "Do not run `run.py run` until the P0 queue below is cleared.\n")
    A("## Why this exists\n")
    A("Experiment 2's keys came from the library under test, so two of them keyed "
      "the library's own errors (HK-07's phantom gap, SG-01's phantom divergence) "
      "and the connector was scored correct for repeating them. Re-scored against "
      "the law, 16/21 to 21/21 became 15/21 to 19/21. This set has the same "
      "conflict — its criteria were written by the library's author — so every "
      "criterion below must be checked against its pin cite by someone who did "
      "not write the library.\n")
    A("## P0 — must clear before any run\n")
    if p0_web:
        A("### P0-a. Criteria resting on `verified-web` (no pin cite read)\n")
        for r in p0_web:
            A("- **%s** (as_of %s): %s\n  Library level: %s. Read the judgment (HKLII should "
              "carry both, 2013/2015 CFI) and either upgrade the library record "
              "to `verified-primary` or rewrite the criterion.\n"
              % (r["cr"]["id"], r["as_of"], r["cr"]["criterion"][:160],
                 ", ".join(sorted({str(x) for _, h in r["matched"] for x in seen[h]["levels"]}))))
    else:
        A("### P0-a. No `verified-web` criteria. (Queue clear.)\n")
    if p0_pin:
        A("### P0-b. Pins not among the library's recorded pins\n")
        for r in p0_pin:
            rec = sorted({p for _, h in r["matched"] for p in seen[h]["pins"]})
            A("- **%s**: criterion pin `%s` is not covered by recorded pins %s. "
              "Confirm the passage supports the criterion or correct the pin.\n"
              % (r["cr"]["id"], r["cr"].get("pin"), rec if rec else "none"))
    else:
        A("### P0-b. All pins covered. (Queue clear.)\n")
    approx_all = sorted({a for r in rows for a in r["approx"]})
    if approx_all:
        A("### Note. Approximate case matches (pins gathered for the reader; "
          "the validator does not rely on them)\n")
        for a in approx_all:
            A("- %s\n" % a)
    A("## P1 — check during the same pass\n")
    A("### P1-a. Validator-exempt authority (statute / rule / gap — human-check only)\n")
    for r in p1_struct:
        auth = r["cr"]["authority"][:110]
        notes = [s for s in r["structural"] if "human-check only" in s]
        if re.search(r"gaps|^T1\b|[DET]\d test", r["cr"]["authority"]):
            guidance = ("Verify against the timeline/gap register and read every "
                        "passage named in the pin; for tension criteria confirm both sides.")
        elif notes:
            guidance = " ".join(notes) + " — this authority has no record in elements.json at all."
        else:
            guidance = "Verify against the primary source (e-Legislation / Basic Law)."
        A("- **%s**: `%s`. %s%s\n" % (r["cr"]["id"], auth, guidance,
                                      " Negative criterion: verify the authority indeed post-dates as_of / has the stated character." if r["negative"] else ""))
    if p1_recent:
        A("### P1-b. 2026 authorities (recency risk)\n")
        for r in p1_recent:
            A("- **%s**: `%s` at `%s`. Confirm the passage text has not moved on appeal.\n"
              % (r["cr"]["id"], r["cr"]["authority"][:100], r["cr"].get("pin")))
    if rest:
        A("### P2. Routine confirm (%d criteria)\n" % len(rest))
        A("Pin-cited, pinned, validator-clean. Read the pin, confirm the proposition, tick the box.\n")
        for r in rest:
            A("- %s\n" % r["cr"]["id"])
    A("## Per-criterion table\n")
    A("| ID | as_of | Authority | Pin | Level in library | Class |\n")
    A("|---|---|---|---|---|---|\n")
    for r in rows:
        lvls = sorted({str(x) for _, h in r["matched"] for x in seen[h]["levels"]})
        cls = ("WEB-ONLY" if r["web_only"]
               else "PIN-GAP" if r["missing_pins"]
               else "STRUCTURAL" if r["structural"] and not r["matched"]
               else "STRUCTURAL+MIXED" if r["structural"] else "PINNED")
        A("| %s | %s | %s | %s | %s | %s |\n"
          % (r["cr"]["id"], r["as_of"], r["cr"]["authority"][:70], r["cr"].get("pin", "")[:40],
             ", ".join(lvls) if lvls else "n/a (structural)", cls))
    A("## Sign-off\n")
    A("Reader (name, no prior library authorship): ____________________  Date: __________\n")
    A("- [ ] P0-a cleared (each item: upgraded, rewritten, or withdrawn with reason)\n")
    A("- [ ] P0-b cleared (each pin confirmed or corrected in the builder)\n")
    A("- [ ] P1 items checked; findings recorded beside each line above\n")
    A("- [ ] After any key change: `python build_tasks.py && python validate_tasks.py && python build_reader_checklist.py`\n")

    with open(os.path.join(HERE, "reader_checklist.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))
    print("P0-web: %d  P0-pin: %d  P1-structural: %d  P1-recent: %d  P2: %d"
          % (len(p0_web), len(p0_pin), len(p1_struct), len(p1_recent), len(rest)))
    print("wrote reader_checklist.md")


if __name__ == "__main__":
    main()
