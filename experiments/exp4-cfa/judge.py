# -*- coding: utf-8 -*-
"""Bound exploratory review entrypoint. Legacy unbound results are rejected.

Reporting is descriptive only. Independent legal-key review and calibration
are separate requirements; this command grants no formal reporting status.
"""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
from review_results import PROMPT, PROMPT_VERSION, combine, judge_main


def main(argv=None):
    return judge_main(HERE, argv)


if __name__ == '__main__':
    raise SystemExit(main())
