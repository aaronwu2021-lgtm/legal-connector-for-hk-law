# -*- coding: utf-8 -*-
"""Validate Experiment 4 structure and report source/reader readiness.

Each criterion maps its phrases to one exact citation. This prevents a phrase
from one judgment in a source bundle from appearing to verify another. Local
identity and phrase checks remain mechanical: they do not establish that the
cited passage supports the legal proposition, and this tool never supplies an
independent reader's sign-off.
"""
import argparse
from datetime import date
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent

_NEUTRAL_CITATION_RE = re.compile(
    r"\[(?P<year>[1-9]\d{3})\]\s+(?P<series>[A-Z][A-Z0-9]*)\s+(?P<number>[1-9]\d*)",
    re.I,
)
_LEGISLATION_CITATION_RE = re.compile(
    r"Cap\.?\s+(?P<chapter>[1-9]\d*[A-Z]?)"
    r"(?:\s+(?P<label>ss?\.?)\s+(?P<sections>[1-9]\d*(?:\([^)]+\))?"
    r"(?:\s*,\s*[1-9]\d*(?:\([^)]+\))?)*))?",
    re.I,
)


def norm_text(value):
    """Case-fold while preserving Unicode letters and numbers."""
    if not isinstance(value, str):
        return ""
    folded = value.casefold()
    return " ".join("".join(ch if ch.isalnum() else " " for ch in folded).split())


norm = norm_text


def match(name, seen):
    """Return one exact complete case-name match; never infer an alias."""
    query = norm_text(name)
    hits = [case for case in seen
            if isinstance(case, str) and norm_text(case) == query and query]
    return hits[0] if len(hits) == 1 else None


def _nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def _contains_phrase(blob, phrase):
    phrase = norm_text(phrase)
    if not phrase:
        return False
    start = 0
    while True:
        index = blob.find(phrase, start)
        if index < 0:
            return False
        end = index + len(phrase)
        left_ok = index == 0 or not blob[index - 1].isalnum()
        right_ok = end == len(blob) or not blob[end].isalnum()
        if left_ok and right_ok:
            return True
        start = index + 1


def _date(value):
    if isinstance(value, bool):
        raise ValueError("boolean cutoff")
    if isinstance(value, int) and 1000 <= value <= 9999:
        return date(value, 12, 31)
    if isinstance(value, str):
        if re.fullmatch(r"[1-9]\d{3}", value):
            return date(int(value), 12, 31)
        if re.fullmatch(r"[1-9]\d{3}-\d{2}-\d{2}", value):
            return date.fromisoformat(value)
    raise ValueError("expected a four-digit year or valid YYYY-MM-DD")


def _source_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"[1-9]\d{3}-\d{2}-\d{2}", value):
        raise ValueError("expected a valid YYYY-MM-DD")
    return date.fromisoformat(value)


def _local_file(base, name):
    if not _nonblank(name):
        raise ValueError("file name must be a nonblank relative path")
    relative = Path(name)
    if relative.is_absolute():
        raise ValueError("absolute source paths are not allowed")
    base = Path(base).resolve()
    target = (base / relative).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("source path leaves the matter directory") from exc
    if not target.is_file():
        raise ValueError("local file is missing")
    return target


def _authority_chunks(value):
    """Split an authority field without guessing names or source identities."""
    if not _nonblank(value):
        return None
    chunks = [chunk.strip() for chunk in value.split(";")]
    return chunks if chunks and all(chunks) else None


def _citation_key(value):
    """Return a structure-preserving key for one supported citation."""
    if not _nonblank(value):
        return None
    raw = value.strip()
    neutral = _NEUTRAL_CITATION_RE.fullmatch(raw)
    if neutral:
        return "neutral:{year}:{series}:{number}".format(
            year=neutral.group("year"),
            series=neutral.group("series").casefold(),
            number=neutral.group("number"),
        )
    legislation = _LEGISLATION_CITATION_RE.fullmatch(raw)
    if legislation:
        chapter = legislation.group("chapter").casefold()
        label = (legislation.group("label") or "").replace(".", "").casefold()
        sections = re.sub(r"\s+", "", legislation.group("sections") or "").casefold()
        return f"legislation:cap{chapter}:{label}:{sections}"
    return None


def _split_reference(value):
    """Split an exact ``title + citation`` reference without erasing syntax."""
    if not _nonblank(value):
        return None
    raw = value.strip()
    for pattern in (_NEUTRAL_CITATION_RE, _LEGISLATION_CITATION_RE):
        matches = [matched for matched in pattern.finditer(raw)
                   if matched.end() == len(raw)]
        if len(matches) != 1:
            continue
        matched = matches[0]
        title = raw[:matched.start()].strip()
        citation = _citation_key(matched.group(0))
        if title and citation:
            return norm_text(title), citation
    return None


def _source_name_present(text, case, citation):
    """Require a complete labelled case or instrument title."""
    expected = (norm_text(case), _citation_key(citation))
    for line in text.splitlines():
        matched = re.match(r"^\s*(?:case name|case|title|instrument|source name)\s*:\s*(.*)$",
                           line, flags=re.I)
        if not matched:
            continue
        if _split_reference(matched.group(1)) == expected:
            return True
    return False


def validate_document(document, matter_dir=None):
    """Return separate structural, local-source and independent-review states."""
    matter_dir = Path(matter_dir) if matter_dir is not None else ROOT / "matter"
    errors, issues = [], []

    def error(path, message):
        errors.append({"code": "invalid-task-structure", "path": path, "message": message})

    def issue(code, path, message):
        issues.append({"code": code, "path": path, "message": message})

    report = {
        "schema_valid": False,
        "structural_errors": errors,
        "counts": {"tasks": 0, "criteria": 0},
        "source_verification": {
            "status": "incomplete",
            "issues": issues,
            "scope": "Per-citation local identity, availability-date and verbatim-phrase checks only; paragraph support is not established.",
        },
        "independent_review": {"status": "pending", "reader": None, "date": None},
        "proposition_verification": "not-performed",
        "ready_for_experiment": False,
    }
    if not isinstance(document, dict):
        error("$", "document must be an object")
        return report
    if not _nonblank(document.get("dataset")):
        error("dataset", "dataset must be a nonblank string")
    tasks = document.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        error("tasks", "tasks must be a nonempty array")
        return report

    report["counts"]["tasks"] = len(tasks)
    task_ids, criterion_ids = set(), set()
    valid_tasks = []
    for ti, task in enumerate(tasks):
        tp = f"tasks[{ti}]"
        if not isinstance(task, dict):
            error(tp, "task must be an object")
            continue
        for field in ("id", "instruction"):
            if not _nonblank(task.get(field)):
                error(tp + "." + field, "must be a nonblank string")
        task_id = task.get("id")
        if isinstance(task_id, str):
            if task_id in task_ids:
                error(tp + ".id", "duplicate task id")
            task_ids.add(task_id)
        try:
            as_of = _date(task.get("as_of"))
        except (ValueError, TypeError):
            as_of = None
            error(tp + ".as_of", "must be a four-digit year or valid YYYY-MM-DD")

        files = task.get("files")
        if not isinstance(files, list) or not files or not all(_nonblank(name) for name in files):
            error(tp + ".files", "must be a nonempty array of relative file names")
        else:
            for fi, filename in enumerate(files):
                try:
                    _local_file(matter_dir, filename)
                except (ValueError, OSError) as exc:
                    error(f"{tp}.files[{fi}]", str(exc))

        payload = task.get("payload")
        if not isinstance(payload, dict):
            error(tp + ".payload", "must be an object")
        else:
            if "timelines" in payload and (
                not isinstance(payload["timelines"], list)
                or not all(_nonblank(value) for value in payload["timelines"])
            ):
                error(tp + ".payload.timelines", "must be an array of nonblank timeline ids")
            if "checklist" in payload and not isinstance(payload["checklist"], bool):
                error(tp + ".payload.checklist", "must be boolean")
        if "held_out" in task and not isinstance(task["held_out"], bool):
            error(tp + ".held_out", "must be boolean")

        sources = task.get("sources")
        source_keys, source_files = set(), set()
        if not isinstance(sources, list) or not sources:
            error(tp + ".sources", "must be a nonempty array of source records")
            sources = []
        for si, source in enumerate(sources):
            sp = f"{tp}.sources[{si}]"
            if not isinstance(source, dict):
                error(sp, "source must be an object")
                continue
            for field in ("case", "citation", "court", "source_type", "available_date",
                          "official_url", "source_file"):
                if not _nonblank(source.get(field)):
                    error(sp + "." + field, "must be a nonblank string")
            legal_dates = [field for field in ("decision_date", "version_date")
                           if _nonblank(source.get(field))]
            if len(legal_dates) != 1:
                error(sp + ".legal_date", "provide exactly one decision_date or version_date")
            key = _citation_key(source.get("citation"))
            if key is None:
                error(sp + ".citation", "must be one neutral citation or a precise Cap. reference, without a title prefix")
            elif key in source_keys:
                error(sp + ".citation", "duplicate citation within task")
            else:
                source_keys.add(key)
            if _nonblank(source.get("source_file")):
                local_key = source["source_file"].replace("\\", "/").casefold()
                if local_key in source_files:
                    error(sp + ".source_file", "each source in a task must use a separate local check file")
                source_files.add(local_key)
            try:
                legal_date = _source_date(source.get(legal_dates[0])) if len(legal_dates) == 1 else None
                available = _source_date(source.get("available_date"))
                if legal_date is not None and legal_date > available:
                    error(sp + ".available_date", "cannot precede the decision or version date")
            except (ValueError, TypeError):
                error(sp + ".legal_date", "source dates must be valid YYYY-MM-DD values")
            if _nonblank(source.get("official_url")) and not source["official_url"].startswith("https://"):
                error(sp + ".official_url", "must be an HTTPS URL")

        rubric = task.get("rubric")
        if not isinstance(rubric, list) or not rubric:
            error(tp + ".rubric", "must be a nonempty array")
            continue
        report["counts"]["criteria"] += len(rubric)
        for ci, criterion in enumerate(rubric):
            cp = f"{tp}.rubric[{ci}]"
            if not isinstance(criterion, dict):
                error(cp, "criterion must be an object")
                continue
            for field in ("id", "criterion", "authority", "pin", "discriminates_against"):
                if not _nonblank(criterion.get(field)):
                    error(cp + "." + field, "must be a nonblank string")
            cid = criterion.get("id")
            if isinstance(cid, str):
                if cid in criterion_ids:
                    error(cp + ".id", "duplicate criterion id")
                criterion_ids.add(cid)
            if not isinstance(criterion.get("drift_sensitive"), bool):
                error(cp + ".drift_sensitive", "must be boolean")
            if "polarity" in criterion and criterion["polarity"] not in ("positive", "negative"):
                error(cp + ".polarity", "must be positive or negative when supplied")
            checks = criterion.get("source_checks")
            if checks is not None:
                if not isinstance(checks, list) or not checks:
                    error(cp + ".source_checks", "must be a nonempty array when supplied")
                else:
                    check_keys = set()
                    for xi, check in enumerate(checks):
                        xp = f"{cp}.source_checks[{xi}]"
                        if not isinstance(check, dict):
                            error(xp, "source check must be an object")
                            continue
                        key = _citation_key(check.get("citation"))
                        if key is None:
                            error(xp + ".citation", "must contain one citation and no party-name prefix")
                        elif key in check_keys:
                            error(xp + ".citation", "duplicate citation within criterion")
                        else:
                            check_keys.add(key)
                        if not _nonblank(check.get("locator")):
                            error(xp + ".locator", "must be a nonblank source-specific paragraph or section locator")
                        phrases = check.get("pin_phrases")
                        if (not isinstance(phrases, list) or not phrases
                                or not all(_nonblank(phrase) and norm_text(phrase) for phrase in phrases)):
                            error(xp + ".pin_phrases", "must be a nonempty array of meaningful phrases")
        valid_tasks.append((tp, task, as_of))

    counts = document.get("counts")
    if counts is not None:
        if not isinstance(counts, dict):
            error("counts", "must be an object when supplied")
        else:
            for key in ("tasks", "criteria"):
                if key in counts and (isinstance(counts[key], bool) or counts[key] != report["counts"][key]):
                    error("counts." + key, "declared count does not match task data")

    report["schema_valid"] = not errors
    if errors:
        issue("structure-invalid", "$", "Source checks cannot complete until structural errors are fixed.")
        return report

    for tp, task, as_of in valid_tasks:
        source_map = {}
        resolved_source_paths = []
        for si, source in enumerate(task["sources"]):
            sp = f"{tp}.sources[{si}]"
            key = _citation_key(source["citation"])
            record = dict(source)
            record["available"] = _source_date(source["available_date"])
            record["blob"] = None
            try:
                source_path = _local_file(matter_dir, source["source_file"])
                previous = next(
                    (previous_path for prior_path, previous_path in resolved_source_paths
                     if source_path.samefile(prior_path)),
                    None,
                )
                if previous is not None:
                    issue("source-file-reused", sp + ".source_file",
                          "This path resolves to the same local file as " + previous + "; each source requires a separate file.")
                else:
                    resolved_source_paths.append((source_path, sp))
                source_text = source_path.read_text(encoding="utf-8")
                blob = norm_text(source_text)
                record["blob"] = blob
                if not _source_name_present(source_text, source["case"], source["citation"]):
                    issue("source-identity-not-in-text", sp, "The complete declared name and citation were not found in the local source.")
            except (ValueError, OSError, UnicodeError) as exc:
                issue("unavailable-source-file", sp + ".source_file", str(exc))
            source_map[key] = record

        for ci, criterion in enumerate(task["rubric"]):
            cp = f"{tp}.rubric[{ci}]"
            authority_chunks = _authority_chunks(criterion["authority"])
            if not authority_chunks:
                issue("unparseable-authority", cp + ".authority", "Authority must use nonempty semicolon-separated source references.")
                authority_chunks = []
            authority_keys = set()
            for chunk in authority_chunks:
                reference = _split_reference(chunk)
                matches = [key for key, source in source_map.items()
                           if reference == (norm_text(source["case"]), key)]
                if len(matches) != 1:
                    issue("authority-source-mismatch", cp + ".authority",
                          "Each authority segment must exactly equal one recorded source title plus its citation.")
                else:
                    authority_keys.add(matches[0])
            checks = criterion.get("source_checks")
            if not checks:
                issue("missing-source-checks", cp + ".source_checks", "No per-citation phrase checks are recorded.")
                checks = []
            check_map = {_citation_key(check["citation"]): check for check in checks}
            if set(check_map) != authority_keys:
                issue("source-check-coverage-mismatch", cp + ".source_checks", "Source checks must cover every authority citation exactly, with no unrelated citation.")

            for citation in authority_keys:
                source = source_map[citation]
                if source["available"] > as_of and criterion.get("polarity") != "negative":
                    issue("future-positive-authority", cp + ".authority", "The source became available after the task cutoff without negative polarity.")

            for citation, check in check_map.items():
                source = source_map.get(citation)
                if source is None:
                    continue
                if source["blob"] is not None:
                    for pi, phrase in enumerate(check["pin_phrases"]):
                        if not _contains_phrase(source["blob"], phrase):
                            issue("phrase-not-in-source", f"{cp}.source_checks[{checks.index(check)}].pin_phrases[{pi}]", "The recorded phrase is absent from its cited local source.")
            if "polarity" not in criterion:
                issue("missing-polarity", cp + ".polarity", "Polarity is not recorded; it is not inferred from criterion wording.")

    report["source_verification"]["status"] = "incomplete" if issues else "checked"
    return report


def _reject_constant(value):
    raise ValueError("nonfinite JSON constant: " + value)


def load_document(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream, parse_constant=_reject_constant)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate Experiment 4 structure and report source/independent-review readiness.")
    parser.add_argument("--tasks", type=Path, default=ROOT / "tasks.json")
    parser.add_argument("--matter-dir", type=Path, default=ROOT / "matter")
    parser.add_argument("--json", action="store_true", help="emit the complete machine-readable report")
    parser.add_argument("--structure-only", action="store_true", help="check shape only; success does not verify sources or legal propositions")
    args = parser.parse_args(argv)
    try:
        report = validate_document(load_document(args.tasks), args.matter_dir)
    except (OSError, UnicodeError, ValueError) as exc:
        report = validate_document(None, args.matter_dir)
        report["structural_errors"].append({"code": "unreadable-tasks", "path": str(args.tasks), "message": str(exc)})
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("tasks {tasks}  criteria {criteria}".format(**report["counts"]))
        print("Structure: " + ("valid" if report["schema_valid"] else "invalid"))
        print("Source verification: " + report["source_verification"]["status"])
        for item in report["structural_errors"] + report["source_verification"]["issues"]:
            print("  {code}: {path}: {message}".format(**item))
        print("Independent reader sign-off: pending. Proposition support: not verified.")
        print("Experiment readiness: incomplete; structure/phrase checks do not clear this gate.")
    if args.structure_only:
        return 0 if report["schema_valid"] else 1
    return 0 if report["ready_for_experiment"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
