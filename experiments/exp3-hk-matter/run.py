# -*- coding: utf-8 -*-
"""Experiment 3 harness: build the prompts, run them, blind the outputs.

This is the missing piece between the task set and a result. It does three
things and deliberately not a fourth:

  build   assemble one prompt bundle per (task, condition) — the instruction,
          the matter file, and for the connector condition the payload pulled
          from the running local API for that task's jurisdiction and as_of.
  run     call a model on each bundle. The model call is a single function,
          `complete()`, that reads MODEL_CMD from the environment: a shell
          command that takes the prompt on stdin and writes the answer to
          stdout. Nothing here is tied to a vendor.
  blind   shuffle the outputs under opaque labels and write the key to a
          separate file, so the judge never sees the condition.

It does NOT judge. Judging is a separate, pre-registered step: the rubric in
tasks.json is the key, each criterion is pass/fail, and the judge sees only the
blinded output and the criterion text. judge.py is the place for that once a
judge protocol is agreed. Do not collapse the two into one script.

    python run.py build
    MODEL_CMD='...' python run.py run
    python run.py blind
"""
import json
import os
import random
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.environ.get("CONNECTOR_API", "http://localhost:8899/api")
OUT = os.path.join(HERE, "runs")

load = lambda p: json.load(open(p, encoding="utf-8"))
tasks = load(os.path.join(HERE, "tasks.json"))["tasks"]


def get(path):
    with urllib.request.urlopen(API + path, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


SYSTEM = (
    "You are a Hong Kong-qualified solicitor. Answer from the matter file and "
    "your own knowledge of the law. Cite authority for every legal proposition. "
    "Where you are unsure whether an authority exists, say so rather than "
    "supplying one. Advise as the law stood on the as-of date given."
)

CONNECTOR_PREAMBLE = (
    "A doctrine connector has supplied the structured material below. It is a "
    "curated library, not a search engine: every authority carries a "
    "verification level, and verified-web means the proposition was matched "
    "against secondary sources but NOT read from the judgment. Where the library "
    "reports a coverage gap, treat it as a gap — do not infer the local position "
    "from English law. Where it gives a pin cite, you may cite it."
)


def payload_for(task):
    """Pull the connector material a competent agent would fetch for this task."""
    j = "HK"
    res = get(f"/resolve?text={urllib.request.quote(task['instruction'][:300])}")
    if res.get("resolved"):
        j = res["resolved"]
    chk = get(f"/checklist?jurisdiction={j}&as_of={task['as_of']}")
    t1 = get(f"/timeline/T1?as_of={task['as_of']}")
    t3 = get(f"/timeline/T3?as_of={task['as_of']}")
    t2 = get(f"/timeline/T2?as_of={task['as_of']}")
    return {"resolved_jurisdiction": res, "pleading_checklist": chk,
            "timelines_as_of": {"T1": t1, "T2": t2, "T3": t3}}


def build():
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for t in tasks:
        matter = "\n\n".join(
            f"### {f}\n" + open(os.path.join(HERE, "matter", f), encoding="utf-8").read()
            for f in t["files"])
        for cond in ("bare", "conn"):
            parts = [SYSTEM, f"AS-OF DATE: 1 December {t['as_of']}.", "", "INSTRUCTION",
                     t["instruction"], "", "MATTER FILE", matter]
            if cond == "conn":
                parts += ["", "CONNECTOR MATERIAL", CONNECTOR_PREAMBLE,
                          json.dumps(payload_for(t), ensure_ascii=False, indent=1)]
            prompt = "\n".join(parts)
            with open(os.path.join(OUT, f"{t['id']}.{cond}.prompt.txt"), "w",
                      encoding="utf-8", newline="\n") as f:
                f.write(prompt)
            n += 1
    print(f"built {n} prompt bundles in {OUT}/")


def complete(prompt):
    cmd = os.environ.get("MODEL_CMD")
    if not cmd:
        sys.exit("set MODEL_CMD to a shell command that reads the prompt on stdin "
                 "and writes the completion to stdout")
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, shell=True,
                       encoding="utf-8")
    if r.returncode != 0:
        sys.exit(f"MODEL_CMD failed: {r.stderr[:500]}")
    return r.stdout


def run():
    n = 0
    for fn in sorted(os.listdir(OUT)):
        if not fn.endswith(".prompt.txt"):
            continue
        out = os.path.join(OUT, fn.replace(".prompt.txt", ".answer.md"))
        if os.path.exists(out):
            continue
        prompt = open(os.path.join(OUT, fn), encoding="utf-8").read()
        ans = complete(prompt)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(ans)
        n += 1
        print("  answered", fn)
    print(f"ran {n} new completions")


def blind():
    answers = sorted(f for f in os.listdir(OUT) if f.endswith(".answer.md"))
    if not answers:
        sys.exit("no answers to blind — run first")
    rng = random.Random(20260901)
    labels = [f"OUT{i:02d}" for i in range(len(answers))]
    rng.shuffle(labels)
    key = {}
    bd = os.path.join(OUT, "blinded")
    os.makedirs(bd, exist_ok=True)
    for fn, lbl in zip(answers, labels):
        task, cond = fn.split(".")[0], fn.split(".")[1]
        key[lbl] = {"task": task, "condition": cond}
        with open(os.path.join(bd, f"{lbl}.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(open(os.path.join(OUT, fn), encoding="utf-8").read())
    with open(os.path.join(OUT, "blind_key.json"), "w", encoding="utf-8") as f:
        json.dump(key, f, indent=1)
    print(f"blinded {len(answers)} outputs into {bd}/; key in runs/blind_key.json — "
          "do not open the key until judging is complete")


if __name__ == "__main__":
    {"build": build, "run": run, "blind": blind}.get(
        sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
