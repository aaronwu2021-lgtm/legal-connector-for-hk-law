"""Shared output plumbing for the builders.

Every builder writes the same artefact twice: `data/<name>.json` (the published
dataset) and `server/netlify/functions/_<name>.mjs` (the module the Netlify
functions import). Paths resolve from this file, so a builder runs correctly
from any working directory. Everything is UTF-8 — the dataset is bilingual and
the platform default encoding is not always.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
FUNC_DIR = os.path.join(ROOT, "server", "netlify", "functions")


def data_path(name):
    return os.path.join(DATA_DIR, name + ".json")


def load(name):
    with open(data_path(name), encoding="utf-8") as f:
        return json.load(f)


def serialize(obj, indent=None):
    """Finish JSON serialization and UTF-8 encoding before opening any output."""
    data = json.dumps(obj, ensure_ascii=False, indent=indent, allow_nan=False).encode("utf-8")
    module = ("export default " + json.dumps(obj, ensure_ascii=False, allow_nan=False) + ";\n").encode("utf-8")
    return data, module


def publish(name, representations):
    """Publish prepared bytes. The two writes are not a cross-file transaction.

    An I/O failure propagates to the caller; check_build detects incomplete pairs.
    """
    data, module = representations
    with open(data_path(name), "wb") as f:
        f.write(data)
    mjs = os.path.join(FUNC_DIR, "_" + name + ".mjs")
    with open(mjs, "wb") as f:
        f.write(module)


def emit(name, obj, indent=None):
    """Write both representations, with no truncation on serialization failure."""
    publish(name, serialize(obj, indent=indent))
