"""Build the frozen content manifest for the current legal review pack.

The manifest binds files and individual rubric records. It deliberately records
external legal sign-off as pending; hashes prove content identity, not legal
correctness.
"""
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DATE = "2026-09-08"
DEFAULT_OUTPUT = ROOT / "docs" / "review" / f"legal-reliability-review-manifest-{SNAPSHOT_DATE}.json"
SUPERSEDES = "docs/review/legal-reliability-review-manifest-2026-09-06.json"
EXPERIMENTS = (
    ("exp3-hk-matter", ROOT / "experiments" / "exp3-hk-matter"),
    ("exp4-cfa", ROOT / "experiments" / "exp4-cfa"),
)
BASE_FILES = (
    "scripts/build_legal_review_manifest.py",
    "scripts/build_elements.py",
    "scripts/build_registry.py",
    "scripts/build_scored.py",
    "scripts/logic_schema.py",
    "scripts/apply_tiers.py",
    "scripts/build_maintenance.py",
    "scripts/build_persuasive.py",
    "scripts/tests/test_build_reproducibility.py",
    "data/elements-misrepresentation.v0.2.yaml",
    "data/elements.json",
    "data/registry.json",
    "data/scored.json",
    "data/maintenance.json",
    "data/persuasive.json",
    "server/netlify/functions/_elements.mjs",
    "server/netlify/functions/_registry.mjs",
    "server/netlify/functions/_scored.mjs",
    "server/netlify/functions/_maintenance.mjs",
    "server/netlify/functions/_persuasive.mjs",
    "docs/review/independent-legal-review-protocol.md",
    "docs/review/legal-reliability-2026-09-06.md",
)
EXPERIMENT_FILES = (
    "README.md",
    "build_tasks.py",
    "validate_tasks.py",
    "build_reader_checklist.py",
    "tasks.json",
    "reader_checklist.md",
)


def sha256_bytes(blob):
    return hashlib.sha256(blob).hexdigest()


def canonical_sha256(value):
    blob = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return sha256_bytes(blob)


def relative(path):
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def load_json(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream, parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError("nonfinite JSON constant: " + value)))


def build_manifest():
    file_paths = {ROOT / name for name in BASE_FILES}
    source_records, criterion_records, experiment_summaries = [], [], []

    source_root = ROOT / "data" / "sources"
    if source_root.is_dir():
        file_paths.update(path for path in source_root.rglob("*") if path.is_file())

    for experiment_name, experiment_root in EXPERIMENTS:
        file_paths.update(experiment_root / name for name in EXPERIMENT_FILES)
        if experiment_name == "exp4-cfa":
            file_paths.add(experiment_root / "test_review_tools.py")
        document = load_json(experiment_root / "tasks.json")
        criteria_count = 0
        for task in document["tasks"]:
            task_context = {
                key: task[key]
                for key in sorted(task)
                if key not in {"rubric", "sources"}
            }
            task_context_hash = canonical_sha256(task_context)
            for filename in task["files"]:
                file_paths.add(experiment_root / "matter" / filename)
            for filename in task.get("files_inv", []):
                file_paths.add(experiment_root / "matter" / filename)
            for source in task.get("sources", []):
                source_path = experiment_root / "matter" / source["source_file"]
                file_paths.add(source_path)
                source_records.append({
                    "experiment": experiment_name,
                    "task_id": task["id"],
                    "citation": source["citation"],
                    "source_file": relative(source_path),
                    "source_record_sha256": canonical_sha256(source),
                })
            for criterion in task["rubric"]:
                criteria_count += 1
                criterion_records.append({
                    "experiment": experiment_name,
                    "task_id": task["id"],
                    "criterion_id": criterion["id"],
                    "as_of": task["as_of"],
                    "task_context_sha256": task_context_hash,
                    "criterion_text_sha256": sha256_bytes(criterion["criterion"].encode("utf-8")),
                    "criterion_record_sha256": canonical_sha256(criterion),
                })
        experiment_summaries.append({
            "experiment": experiment_name,
            "tasks": len(document["tasks"]),
            "criteria": criteria_count,
            "tasks_file_sha256": sha256_bytes((experiment_root / "tasks.json").read_bytes()),
        })

    missing = sorted(relative(path) for path in file_paths if not path.is_file())
    if missing:
        raise FileNotFoundError("review files missing: " + ", ".join(missing))

    files = {
        relative(path): {
            "bytes": path.stat().st_size,
            "sha256": sha256_bytes(path.read_bytes()),
        }
        for path in sorted(file_paths, key=lambda item: relative(item))
    }
    criterion_records.sort(key=lambda item: (item["experiment"], item["task_id"], item["criterion_id"]))
    source_records.sort(key=lambda item: (item["experiment"], item["task_id"], item["citation"]))
    return {
        "schema": "legal-reliability-review-manifest-v1",
        "review_snapshot_date": SNAPSHOT_DATE,
        "supersedes": SUPERSEDES,
        "status": {
            "local_identity_date_phrase_checks": "see generated experiment checklists",
            "independent_legal_review": "pending external reviewer sign-off",
            "formal_experiment_readiness": False,
        },
        "scope": (
            "Frozen named legal-data inputs, builders and outputs, Exp3/Exp4 tasks, "
            "matter files, source-check extracts, blank read-only checklists and review "
            "protocol. Hashes bind content but do not prove legal correctness or source "
            "authenticity. A completed external-review response is a separately hashed "
            "output and is not an input to this manifest."
        ),
        "scope_limitations": [
            "The nine task-source associations are all from Experiment 4 and bind seven distinct local source-check extracts, not complete authenticated copies of the official sources.",
            "Experiment 3 citations and pins are frozen inside task and checklist files, but this manifest has no separate Experiment 3 original-source records.",
            "Model outputs, human grading records, statistical results and a completed external-review response do not yet exist and are not frozen here.",
        ],
        "counts": {
            "experiments": len(experiment_summaries),
            "tasks": sum(item["tasks"] for item in experiment_summaries),
            "criteria": sum(item["criteria"] for item in experiment_summaries),
            "source_records": len(source_records),
            "source_record_associations": len(source_records),
            "distinct_source_files": len({item["source_file"] for item in source_records}),
            "files": len(files),
        },
        "experiments": experiment_summaries,
        "criterion_records": criterion_records,
        "source_records": source_records,
        "files": files,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a deterministic legal-review manifest and SHA-256 companion.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    manifest = build_manifest()
    body = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False,
                       allow_nan=False) + "\n").encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(body)
    digest = sha256_bytes(body)
    companion = output.with_suffix(output.suffix + ".sha256")
    companion.write_text(digest + "  " + output.name + "\n", encoding="utf-8", newline="\n")
    print("review manifest: {tasks} tasks / {criteria} criteria / {files} files".format(
        **manifest["counts"]))
    print("sha256: " + digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
