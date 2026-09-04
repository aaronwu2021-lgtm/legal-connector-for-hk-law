# -*- coding: utf-8 -*-
"""Judge blinded Experiment 3 outputs, one criterion at a time.

Pre-registered by construction: the key is the rubric in tasks.json, fixed
before any output existed, and each criterion already names the wrong answer
it is meant to catch. The judge sees ONE blinded output and ONE criterion per
call and returns pass/fail with a one-line reason. It never sees the condition,
the blind key, or the other output for the same task.

This script does not open runs/blind_key.json and must not be edited to. Scoring
and unblinding happen in score.py, after every verdict is on disk.

    JUDGE_CMD='...' python judge.py          # judges everything in runs/blinded/
    python judge.py --dry                    # prints the prompts, calls nothing
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "runs")
BLIND = os.path.join(RUNS, "blinded")
VERD = os.path.join(RUNS, "verdicts")

tasks = {t["id"]: t for t in json.load(open(os.path.join(HERE, "tasks.json"), encoding="utf-8"))["tasks"]}

PROMPT = """You are grading one criterion of a legal-drafting rubric. Answer only from the
output below. Do not reward hedging, length or fluency; reward the criterion
being met. If the output is silent on the point, it FAILS.

CRITERION
{criterion}

THIS CRITERION IS SPECIFICALLY DESIGNED TO CATCH
{against}

OUTPUT UNDER REVIEW
<<<
{output}
>>>

Reply with exactly one JSON object and nothing else:
{{"verdict": "PASS" or "FAIL", "reason": "<one sentence quoting or pointing to the decisive passage>"}}"""


def judge_one(prompt, dry):
    if dry:
        return {"verdict": "DRY", "reason": ""}
    cmd = os.environ.get("JUDGE_CMD")
    if not cmd:
        sys.exit("set JUDGE_CMD to a shell command that reads the prompt on stdin and "
                 "writes the reply to stdout")
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, shell=True,
                       encoding="utf-8")
    if r.returncode != 0:
        sys.exit(f"JUDGE_CMD failed: {r.stderr[:500]}")
    txt = r.stdout.strip()
    try:
        j = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
        assert j.get("verdict") in ("PASS", "FAIL")
        return j
    except Exception:
        return {"verdict": "UNPARSEABLE", "reason": txt[:300]}


def main():
    dry = "--dry" in sys.argv
    if not os.path.isdir(BLIND):
        sys.exit("no runs/blinded/ — run `python run.py blind` first")
    os.makedirs(VERD, exist_ok=True)

    # The task each blinded label belongs to is needed to pick the rubric, but
    # NOT the condition. run.py writes the task id into the blinded file's
    # first line as a comment for exactly this reason; the condition lives only
    # in blind_key.json, which this script never reads.
    n = 0
    for fn in sorted(os.listdir(BLIND)):
        if not fn.endswith(".md"):
            continue
        label = fn[:-3]
        out_path = os.path.join(VERD, label + ".json")
        if os.path.exists(out_path) and not dry:
            continue
        text = open(os.path.join(BLIND, fn), encoding="utf-8").read()
        first, _, body = text.partition("\n")
        task_id = first.replace("<!-- task:", "").replace("-->", "").strip()
        if task_id not in tasks:
            sys.exit(f"{fn}: first line must be '<!-- task:HKM-xx -->', got {first!r}")
        verdicts = []
        for c in tasks[task_id]["rubric"]:
            p = PROMPT.format(criterion=c["criterion"], against=c["discriminates_against"],
                              output=body.strip())
            if dry:
                print(f"--- {label} / {c['id']} ---\n{p[:400]}...\n")
            v = judge_one(p, dry)
            verdicts.append({"criterion": c["id"], **v})
        if not dry:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"label": label, "task": task_id, "verdicts": verdicts}, f,
                          ensure_ascii=False, indent=1)
            print(f"  judged {label} ({task_id}): "
                  f"{sum(1 for v in verdicts if v['verdict'] == 'PASS')}/{len(verdicts)} pass")
        n += 1
    print(f"{'would judge' if dry else 'judged'} {n} outputs")


if __name__ == "__main__":
    main()
