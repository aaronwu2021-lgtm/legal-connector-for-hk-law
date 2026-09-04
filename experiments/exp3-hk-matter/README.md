# Experiment 3 — Hong Kong matter-file eval set

**Status: UNRUN.** This is a task set with answer keys. No model has been scored
against it and no result is claimed here. It exists because the paper's closing
paragraph says this is the thing that is missing.

## Why the existing benchmark cannot test the claim

Experiment 1 used a public long-horizon legal agent benchmark and produced a
null result. The reason is visible in the design, not the numbers: its matter
files are US and English, and its rubric criteria are about structure, numeric
accuracy, record citation and fact analysis. A criterion of the form "states the
correct measure of damages" is passed by a model that answers with the English
rule. Nothing in that benchmark can distinguish a model that knows Hong Kong law
from a model that knows English law and is answering a Hong Kong question.

That is exactly the distinction this connector exists to serve, so it needed a
set that tests it.

## What is here

| File | Contents |
|---|---|
| `build_tasks.py` | The task definitions and the synthetic matter files. Run it to regenerate `tasks.json` and `matter/`. |
| `validate_tasks.py` | Checks the rubrics against `data/elements.json`. Exits non-zero on an ungrounded, anachronistic or non-discriminating criterion. |
| `tasks.json` | 5 tasks, 31 criteria, 6 drift-sensitive. Build output — edit the builder, not this. |
| `matter/` | 13 synthetic matter files. Build output. |

```bash
python build_tasks.py && python validate_tasks.py
```

## The five tasks

| ID | as_of | Criteria | What it tests |
|---|---|---|---|
| HKM-01 | 2026 | 7 | Damages measure under Cap. 284 s.3(1): the deceit measure, unforeseeable loss recoverable, tortious counterfactual |
| HKM-02 | 2026 | 7 | Non-reliance clauses: the Cap. 284 s.4 → Cap. 71 route, Chang Pui Yin, the limits of contractual estoppel |
| HKM-03 | **2015** | 6 | The same matter file as HKM-02, answered as at 1 December 2015 |
| HKM-04 | 2026 | 6 | Inducement: inference of fact not law, where the burden lies, belief not required |
| HKM-05 | 2026 | 5 | Which authorities bind a Hong Kong CFI, and why |

Grading is all-pass per task, matching the benchmark this set is modelled on.

## Three design commitments

**Every criterion is grounded in a pin-cited record, and this is checked.**
A criterion resting on a `verified-web` characterisation would test the
compiler's guesses rather than the law, so `validate_tasks.py` resolves each
criterion's authority against `data/elements.json` and fails the build if it
does not exist or post-dates the task's `as_of`. Three criteria rest on
authorities still at `verified-web` (Royscot itself, DBS v San-Hot); the
validator reports them rather than hiding them, because in each the proposition
tested is carried by a pinned Hong Kong case cited alongside.

Writing the validator was not ceremony. It caught a criterion on the damages
measure that had silently been grounded on *Long v Lloyd*, a rescission case,
rather than *Long Year Development* — a matching bug in the first draft that no
amount of reading the rubric would have surfaced.

**Every criterion names the wrong answer it discriminates against.** A rubric
line that a model passes by writing competent general misrepresentation prose
measures nothing. Each criterion carries `discriminates_against` naming the
specific English default a good English lawyer would reach for: MA 1967 s.2(1)
for Cap. 284 s.3(1), UCTA s.11(1) for CECO s.3(1), First Tower Trustees for
Chang Pui Yin.

**The as_of pair is the point.** HKM-02 and HKM-03 put the same matter file
twice, three years either side of *Chang Pui Yin*. A model that has memorised
current Hong Kong law passes HKM-02 and fails HKM-03, because HKM-03 requires
knowing that the counter-limit for unsophisticated customers was not available
in 2015. This is the only construction in the set that tests time-indexing
rather than recall, and it is the claim the connector's `as_of` queries make.

## Limits, before anyone runs it

- **Five tasks is small**, and the criteria were written by the same author as
  the connector they test. That is the same conflict the paper already
  acknowledges for Experiments 1 and 2, and it is not cured by this set.
- **The rubrics inherit the library's coverage.** They test the parts of Hong
  Kong misrepresentation law that have been read; they say nothing about the
  parts that have not.
- **No result may be reported from this file alone.** The protocol now exists
  (`run.py` → `judge.py` → `score.py`, see the README at the repository root)
  but has not been run; the rubric in `tasks.json` is the pre-registered key.
- **The matter files are synthetic** and marked as such in an HTML comment at
  the head of each. Parties, sums and dates are invented. They are drafted to be
  closed-universe: everything needed to apply the law is in the file, and
  nothing in the file resolves the legal question for the model.
