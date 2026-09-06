# -*- coding: utf-8 -*-
"""Re-score Experiment 2 against the law rather than against the library.

The original answer keys were derived from misrepresentation-elements-family
v0.2, whose authorities were at verification level `web`. Reading the judgments
for the v0.3 upgrade showed that two keys were wrong and a third overstated,
and that the connector condition had been marked "correct" on the two wrong
ones for agreeing with the library. This pass re-judges ONLY those two items,
against the corrected law, with the pin cites that ground each correction,
and annotates the overstated third (HK-03) without changing its verdicts.
Every other verdict is carried over unchanged from probe_judged/.

It writes probe_results_rescored.json alongside the original, which is left
untouched. Run it and quote the output; do not edit the numbers by hand.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
load = lambda n: json.load(open(os.path.join(HERE, n), encoding="utf-8"))

orig = load("probe_results.json")["per_item"]
blind = load("probe_blind_key.json")
answers = {c: {a["id"]: a["answer"] for a in load(f"probe_answers/{c}.json")["answers"]}
           for c in ("bare", "conn")}

# ── the corrections ──────────────────────────────────────────────────────────
# Each entry: what the original key said, what the law is, the pin cites read,
# and the re-judged verdict for each condition with the reason.
CORRECTIONS = {
 "HK-07": {
  "original_key": "No Hong Kong authority is on file on this point — the HK branch is empty.",
  "corrected_key": "Settled at first instance, and never doubted: Long Year Development v Tse "
                   "Fuk Man Norman [1991] 2 HKC 393 at 407D-408D (DHCJ Andrew Li QC) held the "
                   "Cap. 284 s.3(1) measure is the deceit measure, following Royscot because the "
                   "provisions are identical; applied as ratio in Joytex v Super Homes [2018] "
                   "HKCFI 2286 at §142, §144; affirmed in Wong Yuk Lan v Car's City [2024] HKDC "
                   "804 at [89]-[91]; restated in Alireza v Elman [2026] HKCFI 4060 at [199]. "
                   "No CA or CFA ruling.",
  "sources_read": ["[2024] HKDC 804 [90] (quotes Long Year 407D-408D verbatim)",
                   "[2018] HKCFI 2286 §142", "[2026] HKCFI 4060 [199]"],
  "bare": ("partial",
           "Says no HK decision squarely decides it and 'I cannot name a case' — wrong, "
           "Long Year does. But correctly states the Royscot reading is assumed to apply in "
           "HK practice, which is the substantive position. Right rule, missing authority."),
  "conn": ("partial",
           "Says 'the point appears open in Hong Kong' — wrong as a statement of law; it "
           "has been settled at first instance since 1991. Credit for attributing the absence "
           "to the library rather than to the law, and for hedging. The library's gap was "
           "reported faithfully; the legal conclusion drawn from it was false."),
 },
 "SG-01": {
  "original_key": "Singapore treats it as a fair inference of fact, not law, burden on the "
                  "representee — subtly weaker than the English rebuttable-presumption "
                  "formulation.",
  "corrected_key": "Singapore's characterisation is right (Wee Chiaw Sek Anna [2013] SGCA 36 "
                   "at [45], [91]) but it is NOT a divergence: England says the same. Hayward v "
                   "Zurich [2016] UKSC 48 at [34]: 'not a presumption of law but an inference "
                   "of fact'; BV Nederlandse [2019] EWCA Civ 596 at [43]: evidential presumption "
                   "of fact, legal burden not reversed. Both cite the same Chitty passage. The "
                   "only surviving EN/SG gap is whether belief is required (Hayward [23], [25]).",
  "sources_read": ["[2016] UKSC 48 [23], [25], [34]", "[2019] EWCA Civ 596 [41]-[43]",
                   "[2013] SGCA 36 [45], [91]"],
  "bare": ("partial",
           "Right on the Singapore characterisation and on the burden. Wrong that the English "
           "articulation casts the burden onto the representor (BV Nederlandse [43] says it does "
           "not). Cites Broadley Construction [2018] SGCA 25 rather than Wee Chiaw Sek Anna; not "
           "verified here, verdict does not turn on it."),
  "conn": ("partial",
           "Right authority (Wee Chiaw Sek Anna) and right characterisation. Wrong that this is "
           "'weaker than the English articulation, where the presumption operates as a genuine "
           "evidential shift' — that is the library's withdrawn divergence, repeated. Was marked "
           "correct for matching a key that was itself wrong."),
 },
 "HK-03": {
  "original_key": "Adopted at CFI level; no CFA authority; CA has qualified it.",
  "corrected_key": "CFI adoption (San-Hot [2013] HKCFI 387; Sit Pan Jit [2015] HKCFI 530) and "
                   "CA qualification (Chang Pui Yin [2017] HKCA 290) stand. 'No CFA authority' "
                   "is overstated: Ng Lai Ling Winnie v Ng Yuk Pui Kelly [2021] HKCFA 40 at "
                   "[24]-[27] (Appeal Committee, refusing leave) states the doctrine's limits and "
                   "treats Peekay as the leading case, though it is not a substantive CFA ruling.",
  "sources_read": ["[2021] HKCFA 40 [24]-[27]", "[2017] HKCA 290 [57], [92], [110]-[113]"],
  # Verdicts unchanged: both answers' statement that the CFA has not ruled is
  # defensible read as 'no substantive ruling'. Recorded here so the overstatement
  # in the key is on the record, not silently carried.
  "bare": (orig["HK-03"]["bare"]["correct"], "unchanged — see note on key"),
  "conn": (orig["HK-03"]["conn"]["correct"], "unchanged — see note on key"),
 },
}

# ── apply ────────────────────────────────────────────────────────────────────
res = {}
for item, v in orig.items():
    res[item] = {c: dict(v[c]) for c in ("bare", "conn")}
    if item in CORRECTIONS:
        cx = CORRECTIONS[item]
        for c in ("bare", "conn"):
            verdict, why = cx[c]
            res[item][c]["correct_original"] = v[c]["correct"]
            res[item][c]["correct"] = verdict
            res[item][c]["rescore_note"] = why
        res[item]["_key_correction"] = {k: cx[k] for k in
                                        ("original_key", "corrected_key", "sources_read")}

def tally(r, key="correct"):
    out = {}
    for c in ("bare", "conn"):
        out[c] = sum(1 for i in r.values() if i[c][key] == "correct")
    disc = [(i, r[i]["bare"][key], r[i]["conn"][key]) for i in r
            if r[i]["bare"][key] != r[i]["conn"][key]]
    gains = sum(1 for _, b, k in disc if k == "correct" and b != "correct")
    losses = sum(1 for _, b, k in disc if b == "correct" and k != "correct")
    return out, gains, losses

o_tot, o_g, o_l = tally({i: {c: {"correct": orig[i][c]["correct"]} for c in ("bare", "conn")}
                         for i in orig})
n_tot, n_g, n_l = tally(res)

def mcnemar_exact(b, c):
    """two-sided exact binomial on the discordant pairs"""
    from math import comb
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * p)

summary = {
  "note": "Re-scored against the law rather than the library for HK-07 and SG-01; HK-03 "
          "verdicts unchanged but key annotated. All other items carried over verbatim.",
  "blind_key": blind,
  "original": {"bare": o_tot["bare"], "conn": o_tot["conn"], "n": len(orig),
               "discordant_gains": o_g, "discordant_losses": o_l,
               "mcnemar_exact_p": round(mcnemar_exact(o_g, o_l), 4)},
  "rescored": {"bare": n_tot["bare"], "conn": n_tot["conn"], "n": len(res),
               "discordant_gains": n_g, "discordant_losses": n_l,
               "mcnemar_exact_p": round(mcnemar_exact(n_g, n_l), 4)},
  "items_changed": sorted(i for i in CORRECTIONS
                          if any(res[i][c]["correct"] != orig[i][c]["correct"]
                                 for c in ("bare", "conn"))),
}

json.dump({"summary": summary, "per_item": res},
          open(os.path.join(HERE, "probe_results_rescored.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print("EXPERIMENT 2 — original vs re-scored")
for lbl, s in (("original", summary["original"]), ("rescored", summary["rescored"])):
    print(f"  {lbl:9s} bare {s['bare']}/{s['n']}  conn {s['conn']}/{s['n']}  "
          f"discordant {s['discordant_gains']}-{s['discordant_losses']}  "
          f"McNemar exact p={s['mcnemar_exact_p']}")
print("  items changed:", ", ".join(summary["items_changed"]))
