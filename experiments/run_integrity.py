"""Content-bound exploratory experiment runs. Importing this module does no I/O.

Hashes detect inconsistent artefacts, not malicious forgery or model-provider
identity. Generator identifiers are operator declarations, not attestations.
"""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import subprocess
import urllib.parse
import urllib.request


class IntegrityError(ValueError):
    pass


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def object_hash(value):
    return sha256_bytes(canonical_bytes(value))


def hash_file(path):
    return sha256_bytes(Path(path).read_bytes())


def safe_path(root, relative):
    root = Path(root).resolve()
    if not isinstance(relative, (str, os.PathLike)):
        raise IntegrityError("artefact path must be a string")
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(p in {"..", "."} for p in path.parts):
        raise IntegrityError("artefact path must be relative and contained: " + str(relative))
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root) or resolved == root:
        raise IntegrityError("artefact path escapes its root: " + str(relative))
    return resolved


def _reject_constant(value):
    raise IntegrityError("nonfinite JSON constant: " + value)


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise IntegrityError("duplicate JSON key: " + key)
        result[key] = value
    return result


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=_reject_constant, object_pairs_hook=_unique_keys)
    except (OSError, UnicodeError, ValueError) as error:
        raise IntegrityError("cannot read valid JSON: " + str(path)) from error


def normalize_as_of(value):
    if isinstance(value, bool):
        raise IntegrityError("as_of must be a year or exact ISO date")
    if isinstance(value, int) and 1000 <= value <= 9999:
        return f"{value}-12-31"
    if isinstance(value, str) and re.fullmatch(r"[1-9]\d{3}", value):
        return value + "-12-31"
    if isinstance(value, str) and re.fullmatch(r"[1-9]\d{3}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            pass
    raise IntegrityError("as_of must be a year or exact valid ISO date")


def _string(value, label):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise IntegrityError("missing or invalid " + label)
    return value


def _sha(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise IntegrityError("invalid hash: " + label)
    return value


def _self_hash(value, field):
    if not isinstance(value, dict) or value.get(field) != object_hash({k: v for k, v in value.items() if k != field}):
        raise IntegrityError("manifest content/hash mismatch: " + field)


def _verified_file(root, relative, expected):
    path = safe_path(root, relative)
    try:
        if hash_file(path) != _sha(expected, str(relative)):
            raise IntegrityError("file hash mismatch: " + str(relative))
    except OSError as error:
        raise IntegrityError("missing bound artefact: " + str(relative)) from error
    return path


def _tasks(root, manifest):
    path = _verified_file(root, manifest.get("tasks_file"), manifest.get("tasks_sha256"))
    document = read_json(path)
    tasks = document.get("tasks") if isinstance(document, dict) else None
    if not isinstance(tasks, list) or not tasks:
        raise IntegrityError("tasks snapshot must contain a nonempty task list")
    index = {}
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("rubric"), list) or not task["rubric"]:
            raise IntegrityError("task requires a nonempty rubric")
        task_id = _string(task.get("id"), "task ID")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", task_id) or task_id in index:
            raise IntegrityError("unsafe or duplicate task ID")
        index[task_id] = task
    return document, index


def _model(value):
    if not isinstance(value, dict):
        raise IntegrityError("missing generator declaration")
    _string(value.get("id"), "generator ID")
    _string(value.get("family"), "generator family")
    if value.get("identity_basis") != "operator-declared":
        raise IntegrityError("generator identity basis must remain operator-declared")
    return value


def load_manifest(run_dir, verify_current=False):
    root = Path(run_dir).resolve()
    manifest = read_json(root / "manifest.json")
    _self_hash(manifest, "manifest_sha256")
    if manifest.get("schema_version") != "doctrine-run-v1":
        raise IntegrityError("unsupported or legacy run manifest")
    _model(manifest.get("model"))
    _, tasks = _tasks(root, manifest)
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise IntegrityError("manifest requires entries")
    identifiers, matrix, files = set(), set(), set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise IntegrityError("invalid run entry")
        task_id, condition, variant = (entry.get(k) for k in ("task_id", "condition", "variant"))
        if (not isinstance(task_id, str) or not isinstance(condition, str) or not isinstance(variant, str)
                or task_id not in tasks or condition not in {"bare", "conn"} or variant not in {"base", "inv"}):
            raise IntegrityError("invalid task/condition/variant")
        entry_id = f"{task_id}.{condition}.{variant}"
        if entry.get("entry_id") != entry_id or entry_id in identifiers:
            raise IntegrityError("duplicate or inconsistent entry identity")
        identifiers.add(entry_id)
        matrix.add((task_id, condition, variant))
        if entry.get("as_of") != normalize_as_of(tasks[task_id].get("as_of")):
            raise IntegrityError("entry cutoff differs from task snapshot")
        if entry.get("rubric_sha256") != object_hash(tasks[task_id]["rubric"]):
            raise IntegrityError("entry rubric hash differs from task snapshot")
        for kind in ("prompt_file", "answer_file", "meta_file"):
            name = entry.get(kind)
            safe_path(root, name)
            if name in files:
                raise IntegrityError("artefact path reused by multiple entries")
            files.add(name)
        _verified_file(root, entry["prompt_file"], entry.get("prompt_sha256"))
    selected = manifest.get("task_ids")
    variant = manifest.get("variant")
    if (not isinstance(selected, list) or not all(isinstance(item, str) for item in selected)
            or len(set(selected)) != len(selected)
            or matrix != {(task_id, cond, variant) for task_id in selected for cond in ("bare", "conn")}):
        raise IntegrityError("manifest does not contain the exact declared task matrix")
    if set(p.name for p in root.glob("*.prompt.txt")) != {e["prompt_file"] for e in entries}:
        raise IntegrityError("unbound or missing prompt files")
    inputs = manifest.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise IntegrityError("missing local source snapshot hashes")
    for item in inputs:
        if not isinstance(item, dict):
            raise IntegrityError("invalid local input declaration")
        _sha(item.get("sha256"), "input")
        source_path = Path(_string(item.get("source_path"), "input source path"))
        if not source_path.is_absolute():
            raise IntegrityError("input source path must be absolute")
        if verify_current:
            try:
                if hash_file(source_path) != item["sha256"]:
                    raise IntegrityError("current source differs from run snapshot: " + str(source_path))
            except OSError as error:
                raise IntegrityError("bound current source is unavailable: " + str(source_path)) from error
    requests = manifest.get("payload_requests")
    if not isinstance(requests, list):
        raise IntegrityError("missing payload request inventory")
    by_request = {}
    for request in requests:
        if not isinstance(request, dict):
            raise IntegrityError("invalid payload request declaration")
        request_id = _string(request.get("request_id"), "payload request ID")
        task_id = request.get("task_id")
        if request_id in by_request or not isinstance(task_id, str) or task_id not in tasks:
            raise IntegrityError("duplicate or invalid payload request identity")
        by_request[request_id] = request
        if request.get("as_of") != normalize_as_of(tasks[task_id].get("as_of")):
            raise IntegrityError("payload request cutoff differs from task")
        url = urllib.parse.urlsplit(_string(request.get("url"), "payload request URL"))
        query = urllib.parse.parse_qs(url.query)
        if query.get("as_of") != [request["as_of"]] or url.scheme not in {"http", "https"} or not url.netloc:
            raise IntegrityError("payload request URL lacks the bound cutoff")
        if request.get("hash_basis") != "canonical-json-decoded-response":
            raise IntegrityError("unknown captured API response hash basis")
        response = read_json(_verified_file(root, request["response_file"], request["response_file_sha256"]))
        if object_hash(response) != request.get("response_sha256"):
            raise IntegrityError("captured API response hash mismatch")
        if request.get("historical_mode") != "strict":
            raise IntegrityError("non-strict captured API response")
        strict_payload(response, request["as_of"])
    used = set()
    for entry in entries:
        refs = entry.get("payload_request_ids")
        if not isinstance(refs, list) or not all(isinstance(item, str) for item in refs) or len(refs) != len(set(refs)):
            raise IntegrityError("invalid entry payload references")
        expected = {key for key, request in by_request.items() if request["task_id"] == entry["task_id"]} if entry["condition"] == "conn" else set()
        if set(refs) != expected:
            raise IntegrityError("entry payload references differ from task/condition")
        used.update(refs)
    if used != set(by_request):
        raise IntegrityError("unbound captured API request")
    _utc(manifest.get("created_utc"))
    return manifest


def _utc(value):
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
            raise ValueError()
        return stamp
    except (AttributeError, TypeError, ValueError) as error:
        raise IntegrityError("invalid UTC timestamp") from error


def validate_answers(run_dir, manifest=None, require_complete=True):
    root = Path(run_dir).resolve()
    manifest = load_manifest(root) if manifest is None else manifest
    _self_hash(manifest, "manifest_sha256")
    expected_answers = {e["answer_file"] for e in manifest["entries"]}
    expected_meta = {e["meta_file"] for e in manifest["entries"]}
    if (not {p.name for p in root.glob("*.answer.md")} <= expected_answers
            or not {p.name for p in root.glob("*.meta.json")} <= expected_meta):
        raise IntegrityError("unbound answer or metadata files in run directory")
    complete = []
    for entry in manifest["entries"]:
        answer_path, meta_path = (safe_path(root, entry[k]) for k in ("answer_file", "meta_file"))
        if not answer_path.exists() and not meta_path.exists() and not require_complete:
            continue
        if not answer_path.is_file() or not meta_path.is_file():
            raise IntegrityError("missing answer/metadata pair: " + entry["entry_id"])
        meta = read_json(meta_path)
        expected = {"schema_version": "doctrine-answer-v1", "manifest_sha256": manifest["manifest_sha256"],
                    "entry_id": entry["entry_id"], "task_id": entry["task_id"], "condition": entry["condition"],
                    "variant": entry["variant"], "prompt_sha256": entry["prompt_sha256"],
                    "model_id": manifest["model"]["id"], "model_family": manifest["model"]["family"],
                    "identity_basis": "operator-declared"}
        if not isinstance(meta, dict) or any(meta.get(k) != v for k, v in expected.items()):
            raise IntegrityError("answer metadata binding mismatch: " + entry["entry_id"])
        if meta.get("parameters") != manifest["model"].get("parameters"):
            raise IntegrityError("answer parameter declaration differs from generator manifest")
        _verified_file(root, entry["prompt_file"], meta["prompt_sha256"])
        _verified_file(root, entry["answer_file"], meta.get("answer_sha256"))
        answer = answer_path.read_text(encoding="utf-8")
        if not answer.strip():
            raise IntegrityError("empty answer: " + entry["entry_id"])
        start, end = _utc(meta.get("started_utc")), _utc(meta.get("ended_utc"))
        duration = meta.get("duration_s")
        if (not isinstance(duration, (int, float)) or isinstance(duration, bool) or not math.isfinite(duration)
                or duration < 0 or end < start or abs((end - start).total_seconds() - duration) > 0.01):
            raise IntegrityError("invalid answer timing: " + entry["entry_id"])
        if start < _utc(manifest.get("created_utc")):
            raise IntegrityError("answer predates manifest")
        complete.append({"entry": entry, "meta": meta, "answer": answer})
    return complete


def load_blind_manifest(run_dir):
    """Judge-safe validation: never reads manifest.json or blind_key.json."""
    root = Path(run_dir).resolve()
    manifest = read_json(root / "blind_manifest.json")
    _self_hash(manifest, "blind_manifest_sha256")
    if manifest.get("schema_version") != "doctrine-blind-v1":
        raise IntegrityError("unsupported or legacy blind manifest")
    _sha(manifest.get("manifest_sha256"), "run manifest")
    _model(manifest.get("model"))
    _, tasks = _tasks(root, manifest)
    def no_condition(value):
        if isinstance(value, dict):
            if set(value) & {"condition", "variant", "entry_id", "prompt_file", "answer_file", "meta_file"}:
                raise IntegrityError("blind manifest exposes treatment mapping")
            for child in value.values(): no_condition(child)
        elif isinstance(value, list):
            for child in value: no_condition(child)
    no_condition(manifest)
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries or manifest.get("expected_answer_count") != len(entries):
        raise IntegrityError("incomplete blinded answer inventory")
    labels, files = set(), set()
    for entry in entries:
        label = entry.get("label")
        if not isinstance(label, str) or not re.fullmatch(r"OUT\d{2,}", label) or label in labels:
            raise IntegrityError("invalid or duplicate blind label")
        labels.add(label)
        task_id = entry.get("task_id")
        if task_id not in tasks or entry.get("rubric_sha256") != object_hash(tasks[task_id]["rubric"]):
            raise IntegrityError("blinded task/rubric binding mismatch")
        if entry.get("blinded_file") != "blinded/" + label + ".md":
            raise IntegrityError("invalid blinded file path")
        path = _verified_file(root, entry["blinded_file"], entry.get("blinded_sha256"))
        content = path.read_bytes()
        header = f"<!-- task:{task_id} -->\n".encode("utf-8")
        if not content.startswith(header) or sha256_bytes(content[len(header):]) != entry.get("answer_sha256"):
            raise IntegrityError("blinded answer hash/header mismatch")
        files.add(path.name)
    if {p.name for p in (root / "blinded").iterdir()} != files:
        raise IntegrityError("blinded directory differs from exact manifest inventory")
    return manifest


_HISTORICAL_KEYS = set("""claim jurisdiction variant elements defences_to_anticipate
as_of historical_mode historical_rule_status historical_rule_gap historical_limitations
element element_en sub_test sub_test_en backbone_authority local_authority related_local_authority
standing_rule_as_of standing_authorities_as_of id en zh auth authority cite case court year decision_date
court_rank where pin verified date_precision proposition_check title title_en events j y since
in_force_at_as_of standing_rules latest_rules recency_unresolved_jurisdictions latest_is_not_governing
subordinate_conflicts_status jurisdictions_with_no_authority_at_as_of resolution latest_event governing
recency_status note EN HK SG AU""".split())
_RANK_NOTE = "Rank and recency identify different recorded authorities; historical rule text is not modelled."


def strict_payload(response, cutoff):
    """Accept only strict dated metadata; reject unknown prose-bearing schema.

    API explanatory text is replaced with local fixed explanations before it is
    included in a prompt. Actual response hashes remain separately recorded.
    """
    cutoff = normalize_as_of(cutoff)
    if (not isinstance(response, dict) or response.get("historical_mode") != "strict"
            or response.get("historical_rule_status") != "historical-rule-not-modelled"
            or normalize_as_of(response.get("as_of")) != cutoff):
        raise IntegrityError("API response lacks strict historical mode or has a different cutoff")
    def project(value):
        if isinstance(value, list):
            return [project(item) for item in value]
        if not isinstance(value, dict):
            if isinstance(value, str):
                if len(value) > 2000:
                    raise IntegrityError("unexpected long text in historical metadata")
                if any(int(y) > int(cutoff[:4]) for y in re.findall(r"\b([1-9]\d{3})\b", value)):
                    raise IntegrityError("future year in historical metadata")
            return value
        for key in ("year", "y", "since"):
            if key in value:
                year = value[key]
                if isinstance(year, bool) or not isinstance(year, int) or not 1000 <= year <= int(cutoff[:4]):
                    raise IntegrityError("future or invalid authority year")
                if year == int(cutoff[:4]) and cutoff[5:] != "12-31" and "decision_date" not in value:
                    raise IntegrityError("same-year metadata lacks an exact decision date")
        if "decision_date" in value:
            if not isinstance(value["decision_date"], str) or len(value["decision_date"]) != 10 or normalize_as_of(value["decision_date"]) > cutoff:
                raise IntegrityError("future decision date in historical payload")
        out = {}
        for key, child in value.items():
            if key not in _HISTORICAL_KEYS:
                raise IntegrityError("non-metadata field in historical response: " + key)
            if key == "historical_limitations":
                out[key] = {"rule_text": "Historical legal rules are not modelled; only dated catalogue metadata is supplied."}
            elif key == "note":
                if child != _RANK_NOTE:
                    raise IntegrityError("unversioned note in historical response")
                out[key] = child
            elif key == "resolution":
                out[key] = "Rank and date ordering are metadata; they do not establish a historical legal rule."
            else:
                out[key] = project(child)
        return out
    return project(response)


def api_get(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        blob = response.read(4 * 1024 * 1024 + 1)
    if len(blob) > 4 * 1024 * 1024:
        raise IntegrityError("connector response is too large")
    try:
        return json.loads(blob.decode("utf-8"), parse_constant=_reject_constant, object_pairs_hook=_unique_keys)
    except (UnicodeError, ValueError) as error:
        raise IntegrityError("connector did not return valid JSON") from error


def _config(here, experiment):
    here = Path(here).resolve()
    model_id = _string(os.environ.get("MODEL_ID"), "MODEL_ID (required before build/run)")
    family = _string(os.environ.get("MODEL_FAMILY"), "MODEL_FAMILY (required before build/run)").casefold()
    variant = os.environ.get("CONNECTOR_VARIANT", "base")
    if variant not in {"base", "inv"}:
        raise IntegrityError("CONNECTOR_VARIANT must be base or inv")
    output_var = "EXP4_RUNS_DIR" if experiment == "exp4-cfa" else "EXP3_RUNS_DIR"
    # Preserve exp4's old EXP3_RUNS_DIR override while supporting its own name.
    output = os.environ.get(output_var) or (os.environ.get("EXP3_RUNS_DIR") if experiment == "exp4-cfa" else None)
    def anchored(value, default):
        path = Path(value) if value else here / default
        return (here / path).resolve() if not path.is_absolute() else path.resolve()
    return {"here": here, "repo": here.parent.parent,
            "output": anchored(output, "runs"),
            "tasks": anchored(os.environ.get("EXP_TASKS"), "tasks.json"),
            "matter": anchored(os.environ.get("EXP_MATTER_DIR"), "matter"),
            "api": os.environ.get("CONNECTOR_API", "http://localhost:8899/api").rstrip("/"),
            "variant": variant, "include_heldout": os.environ.get("CONNECTOR_INCLUDE_HELDOUT") == "1",
            "model": {"id": model_id, "family": family, "identity_basis": "operator-declared",
                      "parameters": {"status": "not-recorded", "reason": "MODEL_CMD is opaque"}}}


def _readiness():
    return {"run_kind": "exploratory", "formal_ready": False,
            "independent_review": {"status": "not-recorded", "reader": None, "date": None},
            "source_verification": "not-verified",
            "calibration": {"status": "not-recorded"}}


def _exclusive(path, blob):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(blob)


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8") + b"\n"


def _config_matches(manifest, config, experiment):
    expected = {"experiment": experiment, "model": config["model"], "variant": config["variant"],
                "include_heldout": config["include_heldout"], "tasks_source": str(config["tasks"]),
                "matter_source": str(config["matter"]), "connector_api": config["api"]}
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise IntegrityError("run configuration differs; use a new directory")


def build_run(here, experiment, system, preamble, getter=None):
    config = _config(here, experiment)
    root = config["output"]
    if root.exists() and any(root.iterdir()):
        manifest = load_manifest(root, verify_current=True)
        _config_matches(manifest, config, experiment)
        validate_answers(root, manifest, require_complete=False)
        if any((root / name).exists() for name in ("blinded", "blind_manifest.json", "blind_key.json", "verdicts", "judging_manifest.json")):
            answers = validate_answers(root, manifest, require_complete=True)
            _validate_blind_key(root, manifest, load_blind_manifest(root), answers)
        print("existing manifest and prompt bindings verified; no files rewritten")
        return manifest
    getter = api_get if getter is None else getter
    tasks_bytes = config["tasks"].read_bytes()
    document = json.loads(tasks_bytes.decode("utf-8"), parse_constant=_reject_constant, object_pairs_hook=_unique_keys)
    tasks = document.get("tasks") if isinstance(document, dict) else None
    if not isinstance(tasks, list) or not tasks:
        raise IntegrityError("tasks must be a nonempty list")
    selected, ids = [], set()
    for task in tasks:
        task_id = task.get("id") if isinstance(task, dict) else None
        if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", task_id) or task_id in ids:
            raise IntegrityError("unsafe or duplicate task ID")
        ids.add(task_id)
        if config["include_heldout"] or not task.get("held_out", False): selected.append(task)
    if not selected:
        raise IntegrityError("no selected tasks")
    source_paths = {config["tasks"], config["here"] / "run.py", Path(__file__).resolve()}
    api_sources = sorted((config["repo"] / "server/netlify/functions").glob("*.mjs"))
    data_sources = sorted((config["repo"] / "data").glob("*.json"))
    if not api_sources or not data_sources:
        raise IntegrityError("local API source/data snapshot is missing")
    source_paths.update(api_sources + data_sources)
    input_hashes = {p.resolve(): hash_file(p) for p in source_paths}
    input_hashes[config["tasks"]] = sha256_bytes(tasks_bytes)
    artifacts = {"tasks.snapshot.json": tasks_bytes}
    entries, requests = [], []
    for task in selected:
        task_id = task["id"]
        cutoff = normalize_as_of(task.get("as_of"))
        instruction = _string(task.get("instruction"), "task instruction")
        rubric = task.get("rubric")
        if not isinstance(rubric, list) or not rubric:
            raise IntegrityError("task requires a rubric")
        files = task.get("files_inv", task.get("files")) if config["variant"] == "inv" else task.get("files")
        if not isinstance(files, list) or not files or len(set(files)) != len(files):
            raise IntegrityError("task requires distinct matter files")
        matter_parts = []
        for filename in files:
            path = safe_path(config["matter"], filename)
            source_paths.add(path)
            blob = path.read_bytes()
            digest = sha256_bytes(blob)
            if path in input_hashes and input_hashes[path] != digest:
                raise IntegrityError("shared matter source changed between tasks")
            input_hashes[path] = digest
            matter_parts.append("### " + filename + "\n" + blob.decode("utf-8").replace("\r\n", "\n"))
        parts = [system, "AS-OF DATE: " + cutoff + ".", "", "INSTRUCTION", instruction,
                 "", "MATTER FILE", "\n\n".join(matter_parts)]
        spec = task.get("payload", {"timelines": ["T1", "T2", "T3"], "checklist": True})
        if (not isinstance(spec, dict) or set(spec) - {"timelines", "checklist"}
                or not isinstance(spec.get("checklist", True), bool)
                or not isinstance(spec.get("timelines", []), list)):
            raise IntegrityError("unsupported task payload schema")
        jurisdiction = task.get("jurisdiction", "HK")
        if jurisdiction not in {"HK", "EN", "SG", "AU"}:
            raise IntegrityError("unsupported task jurisdiction")
        payload = {"jurisdiction": jurisdiction, "as_of": cutoff, "timelines_as_of": {}}
        endpoints = []
        if spec.get("checklist", True):
            endpoints.append(("checklist", "/checklist?" + urllib.parse.urlencode({"jurisdiction": jurisdiction, "as_of": cutoff})))
        for timeline in spec.get("timelines", []):
            if not isinstance(timeline, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", timeline):
                raise IntegrityError("invalid timeline identifier")
            endpoints.append((timeline, "/timeline/" + timeline + "?" + urllib.parse.urlencode({"as_of": cutoff})))
        request_ids = []
        for number, (key, endpoint) in enumerate(endpoints):
            url = config["api"] + endpoint
            response = getter(url)
            projected = strict_payload(response, cutoff)
            response_file = f"payloads/{task_id}.{number}.json"
            blob = _json_bytes(response)
            artifacts[response_file] = blob
            request_id = f"{task_id}.{number}"
            request_ids.append(request_id)
            requests.append({"request_id": request_id, "task_id": task_id, "url": url,
                "response_file": response_file, "response_file_sha256": sha256_bytes(blob),
                "response_sha256": object_hash(response), "hash_basis": "canonical-json-decoded-response",
                "as_of": cutoff, "historical_mode": "strict"})
            if key == "checklist": payload["pleading_checklist"] = projected
            else: payload["timelines_as_of"][key] = projected
        for condition in ("bare", "conn"):
            entry_id = f"{task_id}.{condition}.{config['variant']}"
            bundle = parts if condition == "bare" else parts + ["", "CONNECTOR MATERIAL", preamble,
                json.dumps(payload, ensure_ascii=False, indent=1, allow_nan=False)]
            prompt = "\n".join(bundle).encode("utf-8")
            prompt_file = entry_id + ".prompt.txt"
            artifacts[prompt_file] = prompt
            entries.append({"entry_id": entry_id, "task_id": task_id, "condition": condition,
                "variant": config["variant"], "matter_variant": "inv" if config["variant"] == "inv" and "files_inv" in task else "base",
                "as_of": cutoff, "rubric_sha256": object_hash(rubric), "prompt_file": prompt_file,
                "prompt_sha256": sha256_bytes(prompt), "answer_file": entry_id + ".answer.md",
                "meta_file": entry_id + ".meta.json", "payload_request_ids": request_ids if condition == "conn" else []})
    manifest = {"schema_version": "doctrine-run-v1", "experiment": experiment,
        "created_utc": datetime.now(timezone.utc).isoformat(), "tasks_file": "tasks.snapshot.json",
        "tasks_sha256": sha256_bytes(tasks_bytes), "tasks_source": str(config["tasks"]),
        "matter_source": str(config["matter"]), "connector_api": config["api"],
        "variant": config["variant"], "include_heldout": config["include_heldout"],
        "task_ids": [t["id"] for t in selected], "model": config["model"], "readiness": _readiness(),
        "inputs": [{"source_path": str(p), "sha256": value} for p, value in sorted(input_hashes.items())],
        "input_identity_basis": "local-source-snapshot; not an attestation of remote or running API code",
        "payload_requests": requests, "entries": entries}
    manifest["manifest_sha256"] = object_hash(manifest)
    if any(hash_file(path) != expected for path, expected in input_hashes.items()):
        raise IntegrityError("local inputs changed while building; use a new snapshot")
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise IntegrityError("output directory became nonempty; use a new directory")
    for relative, blob in artifacts.items():
        _exclusive(safe_path(root, relative), blob)
    _exclusive(root / "manifest.json", _json_bytes(manifest))
    load_manifest(root, verify_current=True)
    print(f"built {len(entries)} exploratory prompt bundles; formal readiness remains false")
    return manifest


def complete_command(prompt):
    command = os.environ.get("MODEL_CMD")
    if not command:
        raise IntegrityError("MODEL_CMD is required to generate missing answers")
    try:
        result = subprocess.run(command, input=prompt, capture_output=True, text=True,
            encoding="utf-8", shell=True, timeout=300, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise IntegrityError("model command failed or timed out; no answer accepted") from error
    if result.returncode:
        # Commands and their stderr can contain credentials. Neither is stored.
        raise IntegrityError("model command failed with exit code " + str(result.returncode))
    return result.stdout


def run_answers(here, experiment, completion=None):
    config = _config(here, experiment)
    root = config["output"]
    manifest = load_manifest(root, verify_current=True)
    _config_matches(manifest, config, experiment)
    completed = validate_answers(root, manifest, require_complete=False)
    cached = {item["entry"]["entry_id"] for item in completed}
    pending = [entry for entry in manifest["entries"] if entry["entry_id"] not in cached]
    if pending and any((root / name).exists() for name in ("blinded", "blind_manifest.json", "blind_key.json", "verdicts", "judging_manifest.json")):
        raise IntegrityError("cannot add answers to a blinded or judged run; use a new directory")
    completion = complete_command if completion is None else completion
    for entry in pending:
        prompt = _verified_file(root, entry["prompt_file"], entry["prompt_sha256"]).read_text(encoding="utf-8")
        started = datetime.now(timezone.utc)
        answer = completion(prompt)
        ended = datetime.now(timezone.utc)
        if not isinstance(answer, str) or not answer.strip():
            raise IntegrityError("model returned an empty or non-text answer")
        # Reject a result if its source or prompt changed while the opaque
        # model command was running. The answer must bind the same snapshot.
        load_manifest(root, verify_current=True)
        blob = answer.encode("utf-8")
        meta = {"schema_version": "doctrine-answer-v1", "manifest_sha256": manifest["manifest_sha256"],
            "entry_id": entry["entry_id"], "task_id": entry["task_id"], "condition": entry["condition"],
            "variant": entry["variant"], "prompt_sha256": entry["prompt_sha256"],
            "answer_sha256": sha256_bytes(blob), "model_id": manifest["model"]["id"],
            "model_family": manifest["model"]["family"], "identity_basis": "operator-declared",
            "parameters": manifest["model"]["parameters"],
            "started_utc": started.isoformat(), "ended_utc": ended.isoformat(),
            "duration_s": round((ended - started).total_seconds(), 6),
            "prompt_chars": len(prompt), "answer_chars": len(answer), "tokens": {"status": "not-recorded"}}
        # Exclusive writes deliberately leave a detectable incomplete pair if
        # publication fails, rather than inventing metadata on a later retry.
        _exclusive(safe_path(root, entry["answer_file"]), blob)
        _exclusive(safe_path(root, entry["meta_file"]), _json_bytes(meta))
    validate_answers(root, manifest, require_complete=True)
    if not pending and any((root / name).exists() for name in ("blinded", "blind_manifest.json", "blind_key.json", "verdicts", "judging_manifest.json")):
        _validate_blind_key(root, manifest, load_blind_manifest(root), completed)
    print(f"generated {len(pending)} answers; reused {len(cached)} fully bound answers; exploratory only")
    return manifest


def _validate_blind_key(root, manifest, blinded, answers):
    key = read_json(root / "blind_key.json")
    if (key.get("schema_version") != "doctrine-blind-key-v1"
            or key.get("manifest_sha256") != manifest["manifest_sha256"]
            or key.get("blind_manifest_sha256") != blinded["blind_manifest_sha256"]
            or blinded.get("manifest_sha256") != manifest["manifest_sha256"]):
        raise IntegrityError("blind/run/key binding mismatch")
    mapping = key.get("entries")
    if not isinstance(mapping, dict) or set(mapping) != {e["label"] for e in blinded["entries"]}:
        raise IntegrityError("blind key inventory mismatch")
    by_id = {item["entry"]["entry_id"]: item for item in answers}
    used = set()
    for public in blinded["entries"]:
        private = mapping[public["label"]]
        item = by_id.get(private.get("entry_id"))
        if item is None or private["entry_id"] in used:
            raise IntegrityError("blind key is not a one-to-one answer mapping")
        entry, meta = item["entry"], item["meta"]
        expected = {k: entry[k] for k in ("entry_id", "task_id", "condition", "variant")}
        expected["answer_sha256"] = meta["answer_sha256"]
        if private != expected or public["task_id"] != entry["task_id"] or public["answer_sha256"] != meta["answer_sha256"]:
            raise IntegrityError("blind key task/condition/variant or answer binding mismatch")
        used.add(entry["entry_id"])
    if used != set(by_id):
        raise IntegrityError("blinding does not contain the complete answer set")
    return key


def blind_run(here, experiment):
    config = _config(here, experiment)
    root = config["output"]
    manifest = load_manifest(root, verify_current=True)
    _config_matches(manifest, config, experiment)
    answers = validate_answers(root, manifest, require_complete=True)
    existing = any((root / name).exists() for name in ("blinded", "blind_manifest.json", "blind_key.json", "verdicts", "judging_manifest.json"))
    if existing:
        blinded = load_blind_manifest(root)
        _validate_blind_key(root, manifest, blinded, answers)
        # Existing verdicts are never opened/reused here. Judge owns verification
        # of that separately bound stage; this command never rewrites its files.
        print("existing blinding bindings verified; no files or label order changed")
        return blinded
    labels = [f"OUT{i:02d}" for i in range(len(answers))]
    secrets.SystemRandom().shuffle(labels)
    entries, mapping, artifacts = [], {}, {}
    for item, label in zip(answers, labels):
        entry, meta = item["entry"], item["meta"]
        # Preserve exact answer bytes; do not redact text to make treatment
        # harder to guess. Blinding withholds metadata, not answer content.
        raw = safe_path(root, entry["answer_file"]).read_bytes()
        blob = f"<!-- task:{entry['task_id']} -->\n".encode("utf-8") + raw
        filename = "blinded/" + label + ".md"
        artifacts[filename] = blob
        entries.append({"label": label, "task_id": entry["task_id"], "rubric_sha256": entry["rubric_sha256"],
            "blinded_file": filename, "blinded_sha256": sha256_bytes(blob), "answer_sha256": meta["answer_sha256"]})
        mapping[label] = {k: entry[k] for k in ("entry_id", "task_id", "condition", "variant")}
        mapping[label]["answer_sha256"] = meta["answer_sha256"]
    blinded = {"schema_version": "doctrine-blind-v1", "manifest_sha256": manifest["manifest_sha256"],
        "tasks_file": manifest["tasks_file"], "tasks_sha256": manifest["tasks_sha256"],
        "model": manifest["model"], "readiness": manifest["readiness"], "expected_answer_count": len(answers),
        "entries": sorted(entries, key=lambda item: item["label"])}
    blinded["blind_manifest_sha256"] = object_hash(blinded)
    key = {"schema_version": "doctrine-blind-key-v1", "manifest_sha256": manifest["manifest_sha256"],
        "blind_manifest_sha256": blinded["blind_manifest_sha256"], "entries": mapping}
    for relative, blob in artifacts.items(): _exclusive(safe_path(root, relative), blob)
    _exclusive(root / "blind_key.json", _json_bytes(key))
    _exclusive(root / "blind_manifest.json", _json_bytes(blinded))
    load_blind_manifest(root)
    _validate_blind_key(root, manifest, blinded, answers)
    print(f"blinded {len(answers)} complete answers; private key withheld from judging")
    return blinded


def command_main(here, experiment, system, preamble, argv=None):
    parser = argparse.ArgumentParser(description="Build, answer and blind an immutable exploratory experiment run.")
    parser.add_argument("command", choices=("build", "run", "blind"))
    args = parser.parse_args(argv)
    try:
        if args.command == "build": build_run(here, experiment, system, preamble)
        elif args.command == "run": run_answers(here, experiment)
        else: blind_run(here, experiment)
        return 0
    except (IntegrityError, OSError, ValueError) as error:
        print("INTEGRITY ERROR: " + str(error), file=__import__("sys").stderr)
        return 1
