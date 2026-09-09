"""Offline entrypoint checks; never import or build in the working repository.

Every invocation gets a fresh, source-only ordinary copy and child process.
Only import/help/invalid-argument paths run; normal builds belong to task 04b.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[2]
ENTRYPOINTS = (
    "scripts/build_elements.py",
    "scripts/build_registry.py",
    "scripts/build_scored.py",
    "scripts/build_maintenance.py",
    "scripts/build_persuasive.py",
    "scripts/apply_tiers.py",
    "scripts/check_persuasive.py",
    "scripts/check_build.py",
    "experiments/exp2-probe/build_probe.py",
    "experiments/exp3-hk-matter/build_tasks.py",
    "experiments/exp3-hk-matter/build_reader_checklist.py",
    "experiments/exp3-hk-matter/validate_tasks.py",
    "experiments/exp4-cfa/build_tasks.py",
    "experiments/exp4-cfa/build_reader_checklist.py",
    "experiments/exp4-cfa/validate_tasks.py",
)


def within(path, root):
    return path.resolve().is_relative_to(root.resolve())


def fingerprint(path):
    stat = path.stat()
    return (hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_mtime_ns)


def tree_manifest(root):
    """Include directories so a failed mkdir also fails the no-change check."""
    return {
        str(path.relative_to(root)): fingerprint(path) if path.is_file() else None
        for path in sorted(root.rglob("*"))
    }


def protected_manifest():
    result = {}
    for directory in (REPO / "data", REPO / "experiments"):
        for path in sorted(directory.rglob("*")):
            if "__pycache__" in path.parts or path.suffix in {".py", ".pyc"}:
                continue
            result[str(path.relative_to(REPO))] = fingerprint(path) if path.is_file() else None
    for path in sorted((REPO / "server/netlify/functions").glob("_*.mjs")):
        result[str(path.relative_to(REPO))] = fingerprint(path)
    return result


# This harness is passed with -c, not imported from the original repository.
# The audit hook is installed before executing any copied target or dependency.
CHILD = r'''
import importlib.util
import os
from pathlib import Path
import sys
import sysconfig

root = Path(sys.argv[1]).resolve()
target = (root / sys.argv[2]).resolve()
operation = sys.argv[3]
original = Path(sys.argv[4]).resolve()

def inside(path, directory):
    return path.is_relative_to(directory)

assert inside(target, root) and not inside(root, original)
assert not inside(target, original)
assert operation in {"import", "--help", "-h", "--definitely-unsupported-option"}
assert Path.cwd().resolve() == root / "cwd"
assert sys.dont_write_bytecode and sys.flags.utf8_mode

dependencies = {}
if target.parent == root / "scripts" and target.name not in {"_paths.py", "check_build.py"}:
    dependencies["_paths"] = root / "scripts/_paths.py"
if target.name in {"build_elements.py", "build_registry.py", "build_scored.py"}:
    dependencies["logic_schema"] = root / "scripts/logic_schema.py"
if target.name == "build_reader_checklist.py":
    dependencies["validate_tasks"] = target.parent / "validate_tasks.py"
source_files = {target, *(path.resolve() for path in dependencies.values())}
for path in source_files:
    assert inside(path, root) and not inside(path, original)
    assert path.is_file() and not path.is_symlink()
    assert path.stat().st_nlink == 1
code_files = source_files | {
    Path(importlib.util.cache_from_source(str(path))).resolve() for path in source_files
}

# -I discards the original cwd and inherited Python module search paths.
# Add only the copied sibling directory needed by these source imports.
assert all(not inside(Path(p).resolve(), original) for p in sys.path if p)
sys.path.insert(0, str(target.parent))
runtime_roots = {
    Path(sysconfig.get_path(name)).resolve() for name in ("stdlib", "platstdlib")
}
runtime_roots.add(Path(sys.base_prefix).resolve())
assert all(not inside(original, path) for path in runtime_roots)
write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
mutations = {
    "os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.link", "os.symlink",
    "os.truncate", "os.chmod", "os.chown", "os.utime", "os.chdir",
}
violations = []

def deny(message):
    violations.append(message)
    raise RuntimeError(message)

def audit(event, args):
    if (event.startswith("socket.") or event.startswith("subprocess.")
            or event.startswith("os.exec") or event.startswith("os.spawn")
            or event in {"os.system", "os.fork", "os.forkpty"}):
        deny("blocked network/process operation: " + event)
    if event in mutations:
        deny("blocked filesystem mutation: " + event)
    if event == "open":
        name, mode, flags = args
        if (mode and any(c in mode for c in "wax+")) or (flags & write_flags):
            deny("blocked file write: " + str(name))
        if not isinstance(name, (str, bytes, os.PathLike)):
            deny("blocked file-descriptor read")
        path = Path(os.fsdecode(name)).resolve()
        if inside(path, original):
            deny("blocked original repository access: " + str(path))
        if path in code_files:
            return
        if any(inside(path, base) for base in runtime_roots):
            return
        deny("blocked data or non-runtime read: " + str(path))

sys.addaudithook(audit)
sys.argv = [str(target)] + ([] if operation == "import" else [operation])
name = "entrypoint_under_test" if operation == "import" else "__main__"
spec = importlib.util.spec_from_file_location(name, target)
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
code = 0
try:
    spec.loader.exec_module(module)
except SystemExit as exc:
    if operation == "import":
        raise RuntimeError("import attempted SystemExit") from exc
    code = exc.code
finally:
    assert not violations, violations
    assert Path(module.__file__).resolve() == target
    for name, expected in dependencies.items():
        dependency = sys.modules[name]
        assert Path(dependency.__file__).resolve() == expected.resolve()
        assert not inside(Path(dependency.__file__).resolve(), original)
    paths = module if target.name == "_paths.py" else sys.modules.get("_paths")
    if paths is not None:
        assert Path(paths.ROOT).resolve() == root
        assert Path(paths.DATA_DIR).resolve() == root / "data"
        assert Path(paths.FUNC_DIR).resolve() == root / "server/netlify/functions"
    if "validate_tasks" in dependencies:
        assert module.match_case is sys.modules["validate_tasks"].match
if operation == "import" and target.name != "_paths.py":
    assert callable(module.main)
    assert module.main.__code__.co_varnames[0] == "argv"
    assert module.main.__defaults__ == (None,)
raise SystemExit(code)
'''


class BuilderEntrypoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        before = protected_manifest()
        cls.addClassCleanup(cls.assert_original_unchanged, before)

    @classmethod
    def assert_original_unchanged(cls, before):
        if protected_manifest() != before:
            raise AssertionError("original generated data or experiment artefacts changed")

    def check_entrypoint(self, relative, operation):
        with tempfile.TemporaryDirectory(prefix="doctrine-entrypoint-") as directory:
            root = Path(directory).resolve()
            self.assertFalse(within(root, REPO))
            sources = {relative}
            if relative.startswith("scripts/"):
                sources.add("scripts/_paths.py")
            if relative in {"scripts/build_elements.py", "scripts/build_registry.py", "scripts/build_scored.py"}:
                sources.add("scripts/logic_schema.py")
            if relative.endswith("/build_reader_checklist.py"):
                sources.add(str(Path(relative).parent / "validate_tasks.py"))
            for name in sources:
                original = (REPO / name).resolve()
                copied = root / name
                self.assertTrue(within(original, REPO))
                self.assertTrue(within(copied, root))
                self.assertFalse(within(copied, REPO))
                copied.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, copied)  # ordinary bytes, never a link
                self.assertFalse(copied.is_symlink())
                self.assertEqual(copied.stat().st_nlink, 1)

            # Resolve every output base before launching any copied source.
            # There are deliberately no generated datasets or matter files.
            output_bases = (
                root / "data", root / "server/netlify/functions",
                (root / relative).parent, root / "cwd",
            )
            for base in output_bases:
                self.assertTrue(within(base, root))
                self.assertFalse(within(base, REPO))
                base.mkdir(parents=True, exist_ok=True)
            (root / "sentinel.txt").write_text("must remain unchanged\n", encoding="utf-8")
            before = tree_manifest(root)
            env = dict(os.environ)
            for key in tuple(env):
                if key.upper() in {"PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"}:
                    env.pop(key)
            env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
            result = subprocess.run(
                [sys.executable, "-I", "-B", "-X", "utf8", "-c", CHILD,
                 str(root), relative, operation, str(REPO)],
                cwd=root / "cwd", env=env, encoding="utf-8", errors="strict",
                capture_output=True, timeout=15, check=False,
            )
            self.assertEqual(tree_manifest(root), before, "copy contents or mtimes changed")
            detail = result.stdout + result.stderr
            if operation == "import":
                self.assertEqual(result.returncode, 0, detail)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")
            elif operation in {"--help", "-h"}:
                self.assertEqual(result.returncode, 0, detail)
                self.assertIn("usage:", result.stdout.lower())
                self.assertEqual(result.stderr, "")
            else:
                self.assertEqual(result.returncode, 2, detail)
                self.assertIn("usage:", result.stderr.lower())
                self.assertIn("unrecognized arguments", result.stderr.lower())
                self.assertEqual(result.stdout, "")


def add_case(relative, operation, suffix):
    def check(self):
        self.check_entrypoint(relative, operation)
    stem = relative.removesuffix(".py").replace("/", "_").replace("-", "_")
    setattr(BuilderEntrypoints, "test_" + stem + "_" + suffix, check)


for _entrypoint in ENTRYPOINTS:
    for _operation, _suffix in (
        ("import", "import"), ("--help", "help"), ("-h", "short_help"),
        ("--definitely-unsupported-option", "unknown_argument"),
    ):
        add_case(_entrypoint, _operation, _suffix)
add_case("scripts/_paths.py", "import", "import")


if __name__ == "__main__":
    unittest.main()
