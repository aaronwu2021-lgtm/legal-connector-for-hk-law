# -*- coding: utf-8 -*-
"""Build, run and blind content-bound exploratory prompts.

MODEL_ID and MODEL_FAMILY are operator declarations required before build/run.
MODEL_CMD is used only by run and is never recorded. Legacy/unbound directories
are refused; choose a new output directory. Formal readiness remains false.
"""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from run_integrity import build_run, run_answers, blind_run, complete_command, command_main

EXPERIMENT = 'exp4-cfa'
SYSTEM = 'You are a Hong Kong-qualified solicitor advising on final appeal prospects. Answer from the matter file and your own knowledge of the law. Cite authority for every legal proposition. Where you are unsure whether an authority exists, say so rather than supplying one. Do not cite English authority as binding in Hong Kong. Advise as the law stood on the as-of date given.'
CONNECTOR_PREAMBLE = (
    "The connector supplies strict, date-filtered catalogue metadata below. "
    "Historical rule text is not modelled. Verification labels describe the "
    "current catalogue, not a completed check of your legal proposition or "
    "what was verified at the cutoff. Do not fill gaps or infer a historical "
    "legal rule from the existence, rank or date of an authority."
)


def build():
    return build_run(HERE, EXPERIMENT, SYSTEM, CONNECTOR_PREAMBLE)


def complete(prompt):
    return complete_command(prompt)


def run():
    return run_answers(HERE, EXPERIMENT, completion=complete)


def blind():
    return blind_run(HERE, EXPERIMENT)


def main(argv=None):
    return command_main(HERE, EXPERIMENT, SYSTEM, CONNECTOR_PREAMBLE, argv)


if __name__ == "__main__":
    raise SystemExit(main())
