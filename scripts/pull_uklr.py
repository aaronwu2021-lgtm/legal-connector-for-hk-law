# -*- coding: utf-8 -*-
"""Refresh the UKLR source snapshot under data/sources/uklr/ (the pull pipeline).

Usage (run from the repo root):
  python3 scripts/pull_uklr.py splits [--workdir DIR]
  python3 scripts/pull_uklr.py crawl [--workdir DIR] [--limit N]
  python3 scripts/pull_uklr.py derive [--workdir DIR]
  python3 scripts/pull_uklr.py all [--workdir DIR]

What each step does:
  splits — re-download the llms-cases.txt snapshot (the only split the builder
    consumes) into data/sources/uklr/.
  crawl  — re-fetch the 449 case detail pages (~12 min at 1 req/s politeness
    delay; checkpointed, re-runs resume) as raw HTML into the workdir.
  derive — parse treatment badges, case-name mentions, related and official
    links out of the raw HTML and write the three derived fact files into
    data/sources/uklr/. NOTE: mention-bearing note text is read transiently
    and never persisted — only labels, names, years and links cross into the
    repo (licence posture, see SOURCING.md).

Working copies (raw HTML) default to the system temp dir and are never
committed. Respects robots.txt: content pages only; /search and /api/ untouched.
"""
import html as ihtml
import json
import os
import re
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "data", "sources", "uklr")
UA = ("doctrine-connector-research/0.1 (academic legal-AI research; "
      "EN common-law index)")
SPLITS_BASE = "https://uklawreference.com/llms-cases.txt"

SIGNAL = {
    "Followed": "good-law", "Applied": "good-law", "Approved": "good-law",
    "Affirmed": "good-law", "Confirmed": "good-law", "Good law": "good-law",
    "Good law (narrowed)": "qualified", "Good law (modified by statute)": "qualified",
    "Good law (reformulated)": "qualified", "Leading Authority": "good-law",
    "Foundational": "good-law", "Extended": "good-law", "Developed": "good-law",
    "Explained": "good-law", "Distinguished": "qualified", "Overruled": "negative",
    "Overruled (in part)": "negative", "Doubted": "negative",
    "Criticised": "negative", "Reversed": "negative", "Superseded": "negative",
    "Partially superseded": "negative", "Superseded by statute": "superseded",
    "Modified by statute": "superseded", "Statutory development": "superseded",
    "Legislated": "superseded", "Led to Legislation": "superseded",
    "Modified": "qualified", "Qualified": "qualified",
    "Narrowly confined": "qualified", "Restricted": "qualified",
    "Limited": "qualified", "Reconsidered": "qualified", "Refined": "qualified",
    "Reformulated": "qualified", "Challenged": "negative",
    "Cited": "context", "Considered": "context", "Discussed": "context",
    "Noted": "context", "Historic importance": "historic", "Historical": "historic",
}
LEAD = re.compile(r"(?:applied|followed|distinguished|overruled|approved|affirmed|"
                  r"confirmed|considered|cited|discussed|noted|explained|referred to|"
                  r"relied on|adopted|rejected|confined|extended|modified|qualified|"
                  r"criticised|doubted|reversed|superseded|reformulated|challenged|"
                  r"developed|limited|restricted)\s+(?:in|by|to|for|from|as)\s+", re.I)
MENTION = re.compile(
    r"\b([A-Z][A-Za-z'’\-.&]*(?:\s+(?:[A-Z][A-Za-z'’\-.&]*|v\.?|of|the|and|for|de|in))*?"
    r"\s+v\.?\s+[A-Z][A-Za-z'’\-.&]*(?:\s+[A-Z][A-Za-z'’\-.&]*)*)"
    r"(?:\s*\[(\d{4})\][^\s]*)?")
SUFFIX = re.compile(r"\b(plc|pty|ltd|limited|co|sa|ag|gmbh|inc|llp|llc|nv|bv|spa|uk|the)\b")


def canon(s):
    s = s.lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = SUFFIX.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch(url):
    for _ in range(3):
        try:
            body = get(url)
            if len(body) > 20000 and "Subsequent Treatment" in body:
                return body
        except Exception:
            time.sleep(2)
    return None


def clean(s):
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", ihtml.unescape(s)).strip()


def treatment_of(page_html):
    m = re.search(r"<h2[^>]*>.*?Subsequent Treatment\s*</h2>(.*?)(?:<h2|</section>)",
                  page_html, flags=re.S | re.I)
    if not m:
        return []
    out = []
    pat = re.compile(r'<div class="inline-flex items-center rounded-full[^"]*">([^<]+)</div>\s*'
                     r"<p[^>]*>(.*?)</p>", flags=re.S)
    for label, note_html in pat.findall(m.group(1)):
        note = clean(note_html)
        men = []
        for mm in MENTION.finditer(note):
            name = LEAD.sub("", re.sub(r"\s+", " ", mm.group(1)).strip(" .,;")).strip()
            if 5 <= len(name) <= 90 and re.search(r"\bv\.?\s+[A-Z]", name):
                men.append({"name": name, "year": mm.group(2)})
        out.append({"label": label.strip(), "mentions": men})
    return out


def links_of(page_html):
    rel = sorted(set(re.findall(r'href="((?:/cases/|/legislation/|/guides/)[^"]+)"', page_html)))
    off = sorted(set(re.findall(
        r'href="(https?://(?:www\.bailii\.org|caselaw\.nationalarchives\.gov\.uk|www\.legislation\.gov\.uk)[^"]*)"',
        page_html)))
    return rel, off


def slugs():
    slugs = []
    txt = open(os.path.join(SRC, "llms-cases.txt"), encoding="utf-8").read()
    for b in re.split(r"(?m)^## ", txt)[1:]:
        for ln in b.strip().splitlines():
            if ln.startswith("URL:"):
                slugs.append(ln[len("URL:"):].strip().rstrip("/").rsplit("/", 1)[-1])
                break
    return slugs


def cmd_splits():
    body = None
    for _ in range(3):
        try:
            body = get(SPLITS_BASE)
            if "## " in body:
                break
        except Exception:
            time.sleep(2)
    if not body or "## " not in body:
        sys.exit("splits download failed")
    with open(os.path.join(SRC, "llms-cases.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    print("snapshot refreshed: %d bytes" % len(body))


def cmd_crawl(workdir, limit=None):
    os.makedirs(os.path.join(workdir, "html"), exist_ok=True)
    prog_p = os.path.join(workdir, "progress.json")
    done = set(json.load(open(prog_p, encoding="utf-8"))) if os.path.exists(prog_p) else set()
    all_slugs = slugs()
    todo = [s for s in all_slugs if s not in done][:limit] if limit else \
        [s for s in all_slugs if s not in done]
    print("crawl: %d todo (%d already done)" % (len(todo), len(done)))
    fails = []
    base = "https://uklawreference.com/cases/"
    for i, slug in enumerate(todo):
        body = fetch(base + slug)
        if body is None:
            fails.append(slug)
            print("[%d/%d] FAIL %s" % (i + 1, len(todo), slug))
            continue
        with open(os.path.join(workdir, "html", slug + ".html"), "w", encoding="utf-8") as f:
            f.write(body)
        done.add(slug)
        if (i + 1) % 10 == 0 or (i + 1) == len(todo):
            json.dump(sorted(done), open(prog_p, "w", encoding="utf-8"))
            print("[%d/%d] ok (fails=%d)" % (i + 1, len(todo), len(fails)))
        time.sleep(1.0)
    json.dump(sorted(done), open(prog_p, "w", encoding="utf-8"))
    print("crawl done: %d ok, %d failed" % (len(done), len(fails)))
    for s in fails:
        print("FAIL:", s)
    return fails


def cmd_derive(workdir):
    html_dir = os.path.join(workdir, "html")
    names = sorted(f[:-5] for f in os.listdir(html_dir) if f.endswith(".html"))
    print("derive: %d pages" % len(names))
    by_slug_case = {}
    for b in re.split(r"(?m)^## ", open(os.path.join(SRC, "llms-cases.txt"),
                                        encoding="utf-8").read())[1:]:
        title = b.strip().splitlines()[0].strip()
        for ln in b.strip().splitlines()[1:]:
            if ln.startswith("URL:"):
                by_slug_case[ln[len("URL:"):].strip().rstrip("/").rsplit("/", 1)[-1]] = title
                break
    canon_map = {}
    for slug, title in by_slug_case.items():
        canon_map.setdefault(canon(re.split(r"\s*[\[(]\d{4}[\])]", title)[0]), slug)
    nodes, edges, official, related = [], {}, {}, {}
    for slug in names:
        h = open(os.path.join(html_dir, slug + ".html"), encoding="utf-8").read()
        rel, off = links_of(h)
        official[slug] = off
        related[slug] = {
            "cases": sorted({l.rsplit("/", 1)[-1] for l in rel if l.startswith("/cases/")}),
            "legislation": sorted({l for l in rel if l.startswith("/legislation/")}),
            "guides": sorted({l for l in rel if l.startswith("/guides/")})}
        labels = []
        for t in treatment_of(h):
            labels.append(t["label"])
            for men in t["mentions"]:
                key = (t["label"], men["name"])
                if key not in edges:
                    edges[key] = {"to_slug": slug, "type": t["label"],
                                  "signal": SIGNAL.get(t["label"], "context"),
                                  "from_name": men["name"], "from_year": men["year"],
                                  "from_slug": None}
                hit = canon_map.get(canon(men["name"]))
                if hit is None:
                    first = canon(men["name"]).split(" v ")[0]
                    cands = [s for k, s in canon_map.items() if k.startswith(first + " ")]
                    hit = cands[0] if len(cands) == 1 else None
                if hit is not None:
                    edges[key]["from_slug"] = hit
        nodes.append({"slug": slug,
                      "title": by_slug_case.get(slug, slug),
                      "status": labels,
                      "signal": sorted({SIGNAL.get(x, "context") for x in labels},
                                       key=lambda s: {"good-law": 3, "qualified": 2, "context": 1,
                                                      "historic": 1, "superseded": 0,
                                                      "negative": 0}.get(s, 1),
                                       reverse=True)[0] if labels else "context"})
    with open(os.path.join(SRC, "uklr-treatment-slim.json"), "w", encoding="utf-8") as f:
        json.dump({"nodes": nodes, "edges": list(edges.values()),
                   "stats": {}}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(SRC, "uklr-official-links.json"), "w", encoding="utf-8") as f:
        json.dump(official, f, ensure_ascii=False, indent=1)
    with open(os.path.join(SRC, "uklr-related-links.json"), "w", encoding="utf-8") as f:
        json.dump(related, f, ensure_ascii=False, indent=1)
    print("derived: %d nodes, %d edges (%d resolved)" %
          (len(nodes), len(edges), sum(1 for e in edges.values() if e["from_slug"])))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    wd = tempfile.mkdtemp(prefix="uklr-pull-")
    for i, a in enumerate(sys.argv):
        if a == "--workdir" and i + 1 < len(sys.argv):
            wd = sys.argv[i + 1]
    if cmd == "splits":
        cmd_splits()
    elif cmd == "crawl":
        lim = None
        for i, a in enumerate(sys.argv):
            if a == "--limit" and i + 1 < len(sys.argv):
                lim = int(sys.argv[i + 1])
        cmd_crawl(wd, lim)
    elif cmd == "derive":
        cmd_derive(wd)
    elif cmd == "all":
        cmd_splits()
        fails = cmd_crawl(wd)
        if fails:
            sys.exit("crawl had %d failures; fix before derive" % len(fails))
        cmd_derive(wd)
        print("next: python3 scripts/build_persuasive.py && python3 scripts/check_persuasive.py")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
