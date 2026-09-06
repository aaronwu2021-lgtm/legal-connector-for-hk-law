"""Check local builds in disposable copies; never publish back to the source tree.

The report distinguishes repeatability, baseline drift and evidence completeness.
Passing a structural provenance check does not verify a legal proposition.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile


SOURCE_ROOT = Path(__file__).resolve().parent.parent
NAMES = ("elements", "registry", "scored", "maintenance", "persuasive")
CORE = tuple("scripts/" + name + ".py" for name in (
    "build_elements", "build_registry", "build_scored", "apply_tiers",
    "build_maintenance", "build_persuasive", "check_persuasive",
))
SOURCES = tuple("data/sources/uklr/" + name for name in (
    "llms-cases.txt", "uklr-treatment-slim.json", "uklr-official-links.json",
    "uklr-related-links.json",
))
EXPERIMENTS = {
    "exp2-probe": ("build_probe.py",),
    "exp3-hk-matter": ("build_tasks.py", "validate_tasks.py", "build_reader_checklist.py"),
    "exp4-cfa": ("build_tasks.py", "validate_tasks.py", "build_reader_checklist.py"),
}
OUTPUTS = tuple(path for name in NAMES for path in (
    "data/" + name + ".json", "server/netlify/functions/_" + name + ".mjs",
))


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def contained(path, root):
    return Path(path).resolve().is_relative_to(Path(root).resolve())


def require_copy(path, root, original):
    resolved = Path(path).resolve()
    if not contained(resolved, root) or contained(resolved, original):
        raise ValueError("path escapes disposable copy: " + str(path))
    return resolved


def read_optional(path):
    return path.read_bytes() if path.is_file() else None


def protected_manifest(root):
    """Paths, hashes and mtimes of original data and experiment artefacts."""
    result = {}
    for directory in (root / "data", root / "experiments"):
        for path in sorted(directory.rglob("*")):
            if "__pycache__" in path.parts or path.suffix in {".py", ".pyc"}:
                continue
            result[path.relative_to(root).as_posix()] = (
                [digest(path.read_bytes()), path.stat().st_mtime_ns] if path.is_file() else None
            )
    for path in sorted((root / "server/netlify/functions").glob("_*.mjs")):
        result[path.relative_to(root).as_posix()] = [digest(path.read_bytes()), path.stat().st_mtime_ns]
    return result


def capture_inputs(source, experiments=False):
    paths = list(CORE) + ["scripts/_paths.py"] + list(SOURCES)
    if experiments:
        for group, scripts in EXPERIMENTS.items():
            paths.extend("experiments/" + group + "/" + script for script in scripts)
        # These are explicit local inputs to exp4, not a clone of all experiments.
        matter = source / "experiments/exp4-cfa/matter"
        paths.extend(p.relative_to(source).as_posix() for p in sorted(matter.rglob("*"))
                     if p.is_file() and p.suffix in {".md", ".txt"})
    snapshot = {}
    missing = []
    for relative in paths:
        path = source / relative
        if not contained(path, source):
            raise ValueError("input escapes source root: " + relative)
        if not path.is_file():
            missing.append(relative)
        else:
            snapshot[relative] = path.read_bytes()
    return snapshot, missing


def materialize(root, original, snapshot):
    """Write captured bytes as ordinary files; no links or source-tree outputs."""
    require_copy(root, root, original)
    for relative, blob in snapshot.items():
        path = require_copy(root / relative, root, original)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        if path.is_symlink() or path.stat().st_nlink != 1:
            raise ValueError("copy must contain ordinary independent files: " + relative)
    for relative in ("data", "server/netlify/functions", "empty-cwd"):
        require_copy(root / relative, root, original).mkdir(parents=True, exist_ok=True)


# Runs only an allowlisted copied entrypoint, with normal CLI semantics. The hook
# blocks reads outside copied inputs/runtime and all writes outside the copy.
RUNNER = r'''
import importlib.util
import os
from pathlib import Path
import sys
import sysconfig

root, target, original = (Path(p).resolve() for p in sys.argv[1:4])
def inside(path, base):
    return path.is_relative_to(base)
assert inside(target, root) and not inside(root, original)
assert inside(Path.cwd().resolve(), root) and not inside(target, original)
assert target.is_file() and not target.is_symlink() and target.stat().st_nlink == 1
assert sys.dont_write_bytecode and sys.flags.utf8_mode
assert not sys.flags.ignore_environment
assert os.environ.get("PYTHONHASHSEED") == sys.argv[4]
assert all(not inside(Path(p).resolve(), original) for p in sys.path if p)
sys.path.insert(0, str(target.parent))
runtime = {Path(sysconfig.get_path(k)).resolve() for k in ("stdlib", "platstdlib")}
runtime.add(Path(sys.base_prefix).resolve())
assert all(not inside(original, base) for base in runtime)
violations = []
def deny(message):
    violations.append(message)
    raise RuntimeError(message)
def file_path(value):
    if not isinstance(value, (str, bytes, os.PathLike)):
        deny("untracked file descriptor access")
    return Path(os.fsdecode(value)).resolve()
def audit(event, args):
    if (event.startswith("socket.") or event.startswith("subprocess.")
        or event.startswith("os.exec") or event.startswith("os.spawn")
        or event in {"os.system", "os.fork", "os.forkpty"}):
        deny("network/process operation forbidden: " + event)
    if event == "open":
        path = file_path(args[0])
        mode, flags = args[1:]
        writing = (mode and any(c in mode for c in "wax+")) or flags & (
            os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        if inside(path, original):
            deny("original repository access forbidden: " + str(path))
        if inside(path, root):
            return
        if not writing and any(inside(path, base) for base in runtime):
            return
        deny("file access outside copy/runtime: " + str(path))
    if event in {"os.rename", "os.link", "os.symlink"}:
        paths = args[:2]
    elif event in {"os.mkdir", "os.remove", "os.rmdir", "os.truncate", "os.chmod", "os.chown", "os.utime", "os.chdir"}:
        paths = args[:1]
    else:
        paths = []
    for value in paths:
        path = file_path(value)
        if not inside(path, root) or inside(path, original):
            deny("filesystem mutation outside copy: " + str(path))
    if event in {"os.link", "os.symlink"}:
        deny("links forbidden in disposable copy")
sys.addaudithook(audit)
sys.argv = [str(target)]
spec = importlib.util.spec_from_file_location("__main__", target)
module = importlib.util.module_from_spec(spec)
sys.modules["__main__"] = module
status = 0
try:
    spec.loader.exec_module(module)
except SystemExit as exc:
    status = exc.code
finally:
    assert not violations, violations
    assert Path(module.__file__).resolve() == target
    for key in ("HERE", "ROOT", "REPO"):
        value = getattr(module, key, None)
        if isinstance(value, (str, Path)):
            assert inside(Path(value).resolve(), root)
    for name in ("_paths", "validate_tasks"):
        if name in sys.modules:
            dependency = Path(sys.modules[name].__file__).resolve()
            assert dependency == target.parent / (name + ".py")
            assert inside(dependency, root) and not inside(dependency, original)
    if "_paths" in sys.modules:
        paths = sys.modules["_paths"]
        assert Path(paths.ROOT).resolve() == root
        assert Path(paths.DATA_DIR).resolve() == root / "data"
        assert Path(paths.FUNC_DIR).resolve() == root / "server/netlify/functions"
    if target.name == "build_reader_checklist.py" and "validate_tasks" in sys.modules:
        assert module.match_case is sys.modules["validate_tasks"].match
raise SystemExit(status)
'''


def run_stage(root, original, relative, seed="1"):
    allowed = set(CORE) | {
        "experiments/" + group + "/" + script
        for group, scripts in EXPERIMENTS.items() for script in scripts
    }
    if relative not in allowed:
        raise ValueError("entrypoint not on build allowlist: " + relative)
    target = require_copy(root / relative, root, original)
    cwd = require_copy(root / "empty-cwd", root, original)
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PYTHON")}
    env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED=str(seed))
    try:
        # -I would ignore PYTHONHASHSEED. -S disables site startup, a scrubbed
        # environment excludes Python overrides, and runner removes cwd.
        result = subprocess.run(
            [sys.executable, "-S", "-B", "-X", "utf8", "-c",
             "import sys; sys.path = [p for p in sys.path if p];\n" + RUNNER,
             str(root), str(target), str(original), str(seed)],
            cwd=cwd, env=env, encoding="utf-8", capture_output=True, timeout=30,
            check=False,
        )
        return {"script": relative, "returncode": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"script": relative, "returncode": 1, "stdout": "", "stderr": str(error)}


def run_order(root, original, scripts=CORE, seed="1"):
    stages = []
    for script in scripts:
        stage = run_stage(root, original, script, seed)
        stages.append(stage)
        if stage["returncode"] != 0:
            break
    return {"ok": len(stages) == len(scripts) and all(s["returncode"] == 0 for s in stages),
            "stages": stages}


def parse_output(blob, path):
    text = blob.decode("utf-8")
    if path.endswith(".mjs"):
        if not text.startswith("export default ") or not text.rstrip().endswith(";"):
            raise ValueError("not a fixed JSON export")
        text = text[len("export default "):].rstrip()[:-1]
    def reject_constant(token):
        raise ValueError("non-JSON numeric constant: " + token)
    return json.loads(text, parse_constant=reject_constant)


def inspect_pair_bytes(blobs):
    pairs, objects = {}, {}
    for name in NAMES:
        try:
            paths = ("data/" + name + ".json", "server/netlify/functions/_" + name + ".mjs")
            if any(blobs.get(p) is None for p in paths):
                raise ValueError("missing JSON/MJS representation")
            left = parse_output(blobs[paths[0]], paths[0])
            objects[name] = left
            right = parse_output(blobs[paths[1]], paths[1])
            pairs[name] = {"equal": left == right}
        except (OSError, ValueError, UnicodeError) as error:
            pairs[name] = {"equal": False, "error": str(error)}
    return pairs, objects


def inspect_pairs(root):
    return inspect_pair_bytes(output_bytes(root))


def difference_paths(before, after, path="$", limit=30):
    differences = []
    def walk(a, b, where):
        if len(differences) >= limit or a == b:
            return
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(a.keys() | b.keys()):
                if key not in a or key not in b:
                    differences.append(where + "." + key)
                else:
                    walk(a[key], b[key], where + "." + key)
                if len(differences) >= limit: break
        elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
            for i, (av, bv) in enumerate(zip(a, b)):
                walk(av, bv, where + "[%d]" % i)
        else:
            differences.append(where)
    walk(before, after, path)
    return differences


def compare_output(before, after, path):
    result = {"baseline_sha256": digest(before) if before is not None else None,
              "built_sha256": digest(after) if after is not None else None}
    if before is None or after is None:
        result["status"] = "missing_baseline" if before is None else "missing_output"
    elif before == after:
        result["status"] = "unchanged"
    else:
        try:
            if path.endswith((".json", ".mjs")):
                left, right = parse_output(before, path), parse_output(after, path)
            else:
                left, right = (b.decode("utf-8").replace("\r\n", "\n") for b in (before, after))
            result["status"] = "serialization_drift" if left == right else "semantic_drift"
            if left != right:
                result["changed_paths"] = difference_paths(left, right)
        except (ValueError, UnicodeError) as error:
            result.update(status="invalid_representation", error=str(error))
    return result


def provenance(objects):
    """Every explicit verified occurrence, including statutes and manual overlays.

    Identity matches elsewhere, narrative notes and undeclared timeline levels
    never supply missing evidence. This checks fields, not proposition truth.
    """
    issues, counts, levels = [], {}, {}
    def text(value):
        return isinstance(value, str) and bool(value.strip())
    def source(value):
        if text(value): return True
        return isinstance(value, dict) and any(text(value.get(key)) for key in
            ("case", "name", "cite", "citation", "url", "page", "judgment"))
    def walk(value, path, dataset):
        if isinstance(value, dict):
            if "verified" in value:
                counts[dataset] = counts.get(dataset, 0) + 1
                declared = value["verified"]
                aliases = {"unverified": "unverified", "web": "web", "verified-web": "web",
                           "quoted": "quoted", "verified-quoted": "quoted",
                           "primary": "primary", "verified-primary": "primary"}
                level = aliases.get(declared, "invalid") if isinstance(declared, str) else "invalid"
                levels[level] = levels.get(level, 0) + 1
                if level == "invalid":
                    issues.append({"path": path + ".verified", "issue": "invalid_verification_level"})
                if level in {"primary", "quoted"} and not text(value.get("pin")):
                    issues.append({"path": path + ".pin", "issue": "missing_pin", "level": level})
                if level == "quoted" and not (source(value.get("source")) or source(value.get("src"))):
                    issues.append({"path": path + ".source", "issue": "missing_quoting_source", "level": level})
            for key, item in value.items():
                walk(item, path + "." + key, dataset)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                walk(item, path + "[%d]" % i, dataset)
    for name, obj in objects.items():
        counts[name] = 0
        walk(obj, name + ":$", name)
    return {"ok": not issues, "scope": "all explicit verified occurrences, including statutes; no deduplication or inferred levels",
            "counts": counts, "levels": levels, "issues": issues}


def output_bytes(root):
    return {p: read_optional(root / p) for p in OUTPUTS}


def band_integrity(objects):
    counts, issues = {}, []
    for name in ("registry", "scored"):
        counts[name] = 0
        for module in objects.get(name, {}).get("modules", []):
            for stage in module.get("stages", []):
                if stage.get("test_type") != "balancing": continue
                for factor in stage.get("factors", []) + stage.get("counter_factors", []):
                    counts[name] += 1
                    bounds = [factor.get("weight_low"), factor.get("weight_high")]
                    valid = (all(isinstance(v, (int, float)) and not isinstance(v, bool)
                                 and math.isfinite(v) for v in bounds)
                             and bounds[0] <= bounds[1]
                             and isinstance(factor.get("tier"), str) and bool(factor["tier"].strip())
                             and factor.get("weight_source") == "doctrinal-tier")
                    if not valid:
                        issues.append("%s/%s/%s/%s" % (name, module.get("id"), stage.get("id"), factor.get("id")))
    return {"ok": not issues, "counts": counts, "issues": issues}


def experiment_paths(source, group):
    base = "experiments/" + group + "/"
    if group == "exp2-probe":
        return [base + "probe.json", base + "probe_questions.json"]
    paths = [base + "tasks.json", base + "reader_checklist.md"]
    if group == "exp3-hk-matter":
        paths.extend(p.relative_to(source).as_posix() for p in sorted((source / base / "matter").rglob("*")) if p.is_file())
    return paths


def check(source=SOURCE_ROOT, experiments=False):
    source = Path(source).resolve()
    protected = protected_manifest(source)
    snapshot, missing = capture_inputs(source, experiments)
    baseline = {p: read_optional(source / p) for p in OUTPUTS}
    baseline_pairs, baseline_objects = inspect_pair_bytes(baseline)
    experiment_baseline = {g: {p: read_optional(source / p) for p in experiment_paths(source, g)}
                           for g in EXPERIMENTS} if experiments else {}
    report = {"input_sha256": {p: digest(b) for p, b in snapshot.items()},
              "missing_inputs": missing, "experiments": {}, "overall_ok": False}
    report["baseline"] = {"pairs": baseline_pairs, "provenance": provenance(baseline_objects)}
    try:
        with tempfile.TemporaryDirectory(prefix="doctrine-build-") as temporary:
            root = Path(temporary).resolve()
            materialize(root, source, snapshot)
            core = run_order(root, source)
            report["core"] = core
            if core["ok"]:
                pairs, objects = inspect_pairs(root)
                core["pairs"] = pairs
                first = output_bytes(root)
                core["comparison"] = {p: compare_output(baseline[p], first[p], p) for p in OUTPUTS}
                core["provenance"] = provenance(objects)
                core["bands"] = band_integrity(objects)
                repeat = run_order(root, source)
                core["repeat"] = {"ok": repeat["ok"] and output_bytes(root) == first,
                                  "stages": repeat["stages"]}
                core["hash_seeds"] = {}
                for seed in ("1", "2"):
                    with tempfile.TemporaryDirectory(prefix="doctrine-seed-") as directory:
                        seeded = Path(directory).resolve()
                        materialize(seeded, source, snapshot)
                        built = run_order(seeded, source, seed=seed)
                        emitted = output_bytes(seeded)
                        core["hash_seeds"][seed] = {
                            "ok": built["ok"] and emitted == first,
                            "output_sha256": {p: digest(b) if b is not None else None for p, b in emitted.items()},
                            "stages": built["stages"],
                        }
                core["deterministic"] = (all(p["equal"] for p in pairs.values())
                    and core["repeat"]["ok"] and all(r["ok"] for r in core["hash_seeds"].values()))
                for group, old in experiment_baseline.items():
                    scripts = tuple("experiments/" + group + "/" + s for s in EXPERIMENTS[group])
                    outcome = run_order(root, source, scripts)
                    paths = sorted(set(old) | set(experiment_paths(root, group)))
                    outcome["comparison"] = {p: compare_output(old.get(p), read_optional(root / p), p) for p in paths}
                    outcome["baseline_equal"] = all(c["status"] == "unchanged" for c in outcome["comparison"].values())
                    report["experiments"][group] = outcome
                report["overall_ok"] = (not missing and core["deterministic"] and core["provenance"]["ok"] and core["bands"]["ok"]
                    and all(p["equal"] for p in baseline_pairs.values()) and report["baseline"]["provenance"]["ok"]
                    and all(c["status"] == "unchanged" for c in core["comparison"].values())
                    and all(g["ok"] and g["baseline_equal"] for g in report["experiments"].values()))
    finally:
        report["original_unchanged"] = protected_manifest(source) == protected
        report["protected_entries"] = len(protected)
        report["overall_ok"] = report["overall_ok"] and report["original_unchanged"]
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiments", action="store_true", help="also rebuild/check archived experimental artefacts in copies")
    parser.add_argument("--json", action="store_true", help="print the complete machine-readable report to stdout")
    args = parser.parse_args(argv)
    try:
        report = check(experiments=args.experiments)
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps({"overall_ok": False, "error": str(error)}))
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        core = report["core"]
        print("core stages:", "PASS" if core["ok"] else "FAIL")
        if core["ok"]:
            print("deterministic build:", "PASS" if core["deterministic"] else "FAIL")
            print("weight bands:", "PASS" if core["bands"]["ok"] else "FAIL", core["bands"]["counts"])
            for path, result in core["comparison"].items():
                print(result["status"] + ": " + path)
            for issue in core["provenance"]["issues"]:
                print("built provenance: " + issue["path"] + " — " + issue["issue"])
            print("provenance scope:", core["provenance"]["scope"])
        for issue in report["baseline"]["provenance"]["issues"]:
            print("baseline provenance: " + issue["path"] + " — " + issue["issue"])
        for group, result in report["experiments"].items():
            print(group + ": stages=" + ("PASS" if result["ok"] else "FAIL")
                  + ", baseline=" + ("SAME" if result["baseline_equal"] else "DIFF"))
        for result in [core, *report["experiments"].values()]:
            for stage in result["stages"]:
                if stage["returncode"]:
                    print("failed stage: " + stage["script"] + "\n" + stage["stderr"])
        print("original artefacts unchanged:", report["original_unchanged"])
        print("overall integrity:", "PASS" if report["overall_ok"] else "FAIL")
    return 0 if report["overall_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
