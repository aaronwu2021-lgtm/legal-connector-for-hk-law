# Offline CI acceptance — 2026-09-05

> Historical record: the unresolved source counts below describe the
> 2026-09-05 snapshot. See the
> [2026-09-06 legal-reliability review](legal-reliability-2026-09-06.md) for the
> current source and independent-sign-off status.

Added `.github/workflows/offline-regressions.yml`. No prior workflow existed. This change only adds the workflow and this note; it does not change tests, helpers, data, experiment artefacts, or README files. Nothing was pushed, and no GitHub Actions run was started.

## Two independent results

The **Software regressions** job runs the Node server/UI tests, the independent five-case API probe, Python builder-entrypoint safety, disposable-copy build/failure tests, Experiment 4 schema/reader tests, and synthetic run/judge/report identity tests. It uses no project package installation, real model command, external legal-service request, or supplied secret. The UI tests use mocked DOM/network behavior; this job does not claim hosted-browser coverage.

The **Data/source readiness** job runs `python -B scripts/check_build.py --experiments --json`. The checker executes builders only in independent temporary copies and checks that the original protected artefacts remain unchanged. It retains the actual nonzero exit status, writes actual `overall_ok` and original-artefact status to the job summary, and uploads the JSON even after failure. There is no `continue-on-error`. A zero checker exit paired with `overall_ok: false` also fails the job.

The current overall data audit is **not passed**: three source-field gaps, two serialization drifts, and Experiment 4 source/independent-review readiness gaps remain. The final independent audit is recorded in `docs/review/build-audit-final-2026-09-05.json`. Software tests passing because they detect these deficiencies does not make the underlying audit pass. Even a future structural data audit pass would not itself verify legal propositions, independent reader sign-offs, calibration, or formal experiment readiness.

Both jobs run automatically on push and ordinary pull requests, and can be dispatched manually. They have read-only repository permissions, do not persist checkout credentials, and use no privileged pull-request trigger. The separate data job is expected to remain red while its recorded deficiencies remain unresolved. Its report is retained for 14 days.

## Runtime and action verification

The workflow selects Windows Server 2025, Node 24 LTS, and Python 3.13. The existing tests use the Node/Python standard libraries. The runner disables Git checkout line-ending conversion before checkout, preserving committed bytes for baseline comparisons. This setting is applied only inside the ephemeral CI runner.

Official release/tag endpoints were checked on 2026-09-05; all four action references are pinned to the resolved full commit, rather than a movable major tag:

| Action | Release | Pinned commit |
| --- | --- | --- |
| checkout | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| setup-node | v7.0.0 | `820762786026740c76f36085b0efc47a31fe5020` |
| setup-python | v7.0.0 | `5fda3b95a4ea91299a34e894583c3862153e4b97` |
| upload-artifact | v7.0.1 | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` |

Primary references: [checkout release](https://github.com/actions/checkout/releases/tag/v7.0.1), [setup-node release](https://github.com/actions/setup-node/releases/tag/v7.0.0), [setup-python release](https://github.com/actions/setup-python/releases/tag/v7.0.0), [upload-artifact release](https://github.com/actions/upload-artifact/releases/tag/v7.0.1). The setup action documentation specifies the Node 24 action runtime and runner compatibility: [setup-node documentation](https://github.com/actions/setup-node/blob/v7.0.0/README.md), [setup-python documentation](https://github.com/actions/setup-python/blob/v7.0.0/README.md). Runtime/image support was checked against the [official Node release schedule](https://nodejs.org/en/about/previous-releases), [Python version status](https://devguide.python.org/versions/), and [Windows 2025 image inventory](https://github.com/actions/runner-images/blob/main/images/windows/Windows2025-Readme.md).

## Local verification and limits

- YAML parsed successfully. Triggers, job separation, read-only permissions, 40-character action pins, and all five Python test paths were checked.
- Every inline command parsed successfully with the PowerShell parser. The test files also parse under Python 3.13 syntax.
- The exact Node test command passed **214/214** with the already available **Node 24.19.0**, matching the CI major version.
- The parent agent's final combined run passed **135/135** Python tests (61 entrypoint, 16 build, 32 run-integrity, 26 review-results), **21/21** Experiment 4 review-tool tests, and **5/5** API acceptance cases. Python on this host is **3.13.14**. These software suites were not unnecessarily repeated for this workflow-only change.
- A temporary PowerShell simulation of the actual data-audit step retained JSON and truthful summaries in all three cases: checker exit 1 / false returned 1; checker exit 0 / false returned 1; checker exit 0 / true returned 0. The simulator replaced the checker command with fixed JSON; it executed no builder or experiment.

This is local command/static validation, not evidence of a successful hosted Actions run. Checkout, runtime download, and report upload use GitHub/official runtime infrastructure; the regression and audit payloads themselves run offline. No original build or archived experiment was rerun for this CI change.
