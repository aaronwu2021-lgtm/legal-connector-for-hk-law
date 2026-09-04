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


def emit(name, obj, indent=None):
    """Write data/<name>.json and server/netlify/functions/_<name>.mjs."""
    with open(data_path(name), "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)
    mjs = os.path.join(FUNC_DIR, "_" + name + ".mjs")
    with open(mjs, "w", encoding="utf-8", newline="\n") as f:
        f.write("export default " + json.dumps(obj, ensure_ascii=False) + ";\n")
