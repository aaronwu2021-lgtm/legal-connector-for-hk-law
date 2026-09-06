# -*- coding: utf-8 -*-
"""Build the England-and-Wales persuasive index: data/persuasive.json.

Reads data/sources/uklr/ (verbatim llms-cases.txt snapshot + derived
treatment edges, official-link and related-link fact lists) and emits a typed,
time-indexed, jurisdiction-tagged authority index for use as PERSUASIVE
material in Hong Kong matters. See data/sources/uklr/SOURCING.md.

Doctrine actually enforced here (not just documented):

- Every record ships verified="unverified" with hk_status="persuasive-only".
  NOTHING in this pipeline upgrades a level. Bulk re-scraping is explicitly
  not verification (see SOURCING.md). Upgrade path is per-case human check.
- NO test_type and NO weights anywhere in this file. Typing 449 cases without
  reading them would violate "test type before weights" — getting the type
  wrong is worse than getting a weight wrong. This branch is an authority
  index (status signals + treatment edges + staleness), not a test library.
- NO source prose reproduced (ratio/facts/notes stay on the source pages, per
  data/LICENSE-DATA). Labels, names, links, dates and our own signal classes
  are metadata. Every record links back.
- Three hierarchies, kept apart, E&W flavour: doctrinal (area tags only, no
claim structure), institutional (court_rank on the E&W ladder below — apex 4
  UKSC/HL, intermediate appellate 3, superior first instance 2, other 1;
  supranational and non-court bodies get null, never a guessed rank), temporal
  (decision year + source reviewed date; as_of filtering is the consumer's).
- Unknown courts FAIL THE BUILD. A guessed rank is a laundered rank.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import emit, DATA_DIR

SRC = os.path.join(DATA_DIR, "sources", "uklr")


def load(name):
    with open(os.path.join(SRC, name), encoding="utf-8") as f:
        return json.load(f) if name.endswith(".json") else f.read()


# Explicit E&W institutional ladder. Keyed on normalised court strings.
RANK_4 = {"supreme court", "house of lords"}
RANK_3 = {"court of appeal", "court of appeal criminal division",
          "court of appeal courts martial appeal", "courts martial appeal court",
          "court martial appeal court court of appeal", "court of appeal in chancery",
          "privy council", "crown cases reserved", "court of criminal appeal"}
RANK_2 = {"high court", "high court tcc", "technology and construction court",
          "high court administrative court", "high court chancery division",
          "high court qbd", "high court admin", "high court divisional court",
          "chancery division", "court of chancery", "rolls court",
          "queens bench division", "kings bench division",
          "queens bench division commercial court", "queens bench",
          "kings bench", "queens bench divisional court",
          "kings bench divisional court", "court of kings bench",
          "employment appeal tribunal", "upper tribunal tax and chancery",
          "competition appeal tribunal", "court of ecclesiastical causes reserved",
          "court of arches", "election court", "court of common pleas",
          "court of exchequer"}
RANK_NULL = {"european court of human rights",
             "court of justice of the european union",
             "court of justice of the european communities",
             "public inquiry", "oxford consistory court"}


def norm_court(c):
    c = (c or "").lower().replace("'", "").replace("’", "")
    c = re.sub(r"[^a-z ]", " ", c)
    c = re.sub(r"\([^)]*\)", " ", c)
    return re.sub(r"\s+", " ", c).strip()


def court_rank(court):
    c = norm_court(court)
    if c in RANK_4:
        return 4, None
    if c in RANK_3:
        return 3, None
    if c in RANK_2:
        return 2, None
    if c in RANK_NULL:
        return None, "supranational or non-court body: outside the E&W precedent ladder"
    for prefix, rank in (("high court", 2), ("court of appeal", 3),
                         ("queens bench", 2), ("kings bench", 2),
                         ("chancery", 2)):
        if c.startswith(prefix):
            return rank, None
    return "UNKNOWN", court


def jurisdiction_of(court):
    c = norm_court(court)
    if "human rights" in c:
        return "ECHR"
    if "european union" in c or "european communities" in c:
        return "EU"
    return "EN"


def split_cite(title):
    m = re.search(r"\s+([\[\(]\d{4}[\]\)].*)$", title.strip())
    if m:
        return title[:m.start()].strip(), m.group(1).strip()
    m2 = re.search(r"\s+(\(\d{4}\)\s+\d+.*)$", title.strip())
    if m2:
        return title[:m2.start()].strip(), m2.group(1).strip()
    return title.strip(), None


def parse_snapshot(text):
    out = []
    for b in re.split(r"(?m)^## ", text)[1:]:
        lines = b.strip().splitlines()
        title = lines[0].strip()
        rec = {"title": title}
        for ln in lines[1:]:
            m = re.match(r"Court:\s*(.*?)\s*\((\d{4})\)\.\s*Area:\s*(.*?)\.\s*Reviewed:\s*(\S+)", ln)
            if m:
                rec["court"], rec["year"], rec["area"], rec["reviewed"] = \
                    m.group(1), int(m.group(2)), m.group(3), m.group(4).rstrip(".")
            if ln.startswith("URL:"):
                rec["url"] = ln[len("URL:"):].strip()
        out.append(rec)
    return out


# UI gloss for the 89+ area labels, not doctrine. An unmapped area FAILS THE
# BUILD (same rule as unknown courts): a silently English-only filter is a
# quieter version of the same laundering this file refuses elsewhere.
AREA_ZH = {
 "Administrative & Public Law": "行政与公法",
 "Administrative Law": "行政法",
 "Animal Welfare": "动物福利",
 "Animal Welfare & Agricultural Law": "动物福利与农业法",
 "Arbitration & ADR": "仲裁与替代性争议解决",
 "Aviation & Transport Law": "航空与运输法",
 "Building Safety": "楼宇安全",
 "Burial & Cremation Law": "殡葬与火化法",
 "Charity Law": "慈善法",
 "Childcare & Safeguarding": "儿童保育与保障",
 "Commercial Law": "商法",
 "Company & Commercial Law": "公司与商事法",
 "Company Law": "公司法",
 "Competition Law": "竞争法",
 "Conflict of Laws": "冲突法",
 "Constitutional & Public Law": "宪制与公法",
 "Constitutional Law": "宪法",
 "Construction Law": "建筑法",
 "Consumer Protection Law": "消费者保障法",
 "Contract Law": "合同法",
 "Coroners & Inquests": "死因裁判",
 "Counter-Terrorism": "反恐",
 "Counter-Terrorism Law": "反恐法",
 "Criminal Law": "刑法",
 "Cyber & Technology Law": "网络与科技法",
 "Data Protection": "数据保障",
 "Data Protection & Privacy Law": "数据保障与隐私法",
 "Defamation & Privacy": "诽谤与隐私",
 "Drug Regulation Law": "药物管制法",
 "Ecclesiastical Law": "教会法",
 "Education Law": "教育法",
 "Election & Political Law": "选举与政治法",
 "Election Law": "选举法",
 "Employment Law": "雇佣法",
 "Energy Law": "能源法",
 "Environmental Law": "环境法",
 "Equality & Discrimination": "平等与歧视",
 "Equity & Trusts": "衡平与信托",
 "Evidence": "证据",
 "Extradition & Mutual Legal Assistance": "引渡与司法互助",
 "Extradition Law": "引渡法",
 "Family Law": "家事法",
 "Financial Services": "金融服务",
 "Food Safety & Standards": "食物安全与标准",
 "Fraud & Economic Crime": "欺诈与经济犯罪",
 "Gambling & Betting Law": "博彩与投注法",
 "Gambling Law": "博彩法",
 "Health & Safety Law": "健康与安全法",
 "Heritage & Listed Buildings": "文物与登录建筑",
 "Housing Law": "房屋法",
 "Human Rights": "人权法",
 "Human Rights & EU Retained Law": "人权与欧盟保留法",
 "Immigration & Nationality": "入境与国籍",
 "Information Law": "信息法",
 "Insolvency": "无力偿债",
 "Insolvency & Restructuring Law": "无力偿债与重组法",
 "Insolvency Law": "无力偿债法",
 "Insurance Law": "保险法",
 "Intellectual Property": "知识产权",
 "International Law": "国际法",
 "Land Law": "土地法",
 "Licensing Law": "牌照法",
 "Local Government Law": "地方政府法",
 "Maritime Law": "海商法",
 "Media & Communications Law": "媒体与通讯法",
 "Media & Entertainment Law": "媒体与娱乐法",
 "Medical & Healthcare Law": "医疗健康法",
 "Medical Negligence": "医疗疏忽",
 "Mental Health Law": "精神健康法",
 "Military Law": "军事法",
 "Modern Slavery": "现代奴役",
 "Modern Slavery & Trafficking": "现代奴役与贩运",
 "Pensions Law": "退休金法",
 "Planning Law": "规划法",
 "Police Powers": "警察权力",
 "Prison & Parole": "监狱与假释",
 "Procurement Law": "采购法",
 "Property Law": "财产法",
 "Public Law": "公法",
 "Refugee & Asylum Law": "难民与庇护法",
 "Sentencing": "量刑",
 "Sentencing Law": "量刑法",
 "Social Housing": "社会房屋",
 "Sports Law": "体育法",
 "Tax Law": "税法",
 "Telecommunications Law": "电讯法",
 "Tort": "侵权法",
 "Tort Law": "侵权法",
 "Unjust Enrichment": "不当得利",
 "Water & Sewerage Law": "供水与污水法",
 "Welfare Law": "福利法",
 "Wills, Probate & Succession": "遗嘱、遗嘱认证与继承",
}


def area_zh(area):
    if area not in AREA_ZH:
        raise SystemExit("UNMAPPED AREA (refusing a silently English-only filter): %r" % area)
    return AREA_ZH[area]


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build the persuasive authority index from local snapshots.')
    parser.parse_args(argv)
    entries = parse_snapshot(load("llms-cases.txt"))
    edges = load("uklr-treatment-slim.json")
    official = load("uklr-official-links.json")
    related = load("uklr-related-links.json")
    by_slug = {}
    for e in entries:
        slug = e["url"].rstrip("/").rsplit("/", 1)[-1]
        by_slug[slug] = e
    edge_by_to = {}
    for e in edges["edges"]:
        edge_by_to.setdefault(e["to_slug"], []).append(e)
    node_status = {n["slug"]: n for n in edges["nodes"]}

    unknowns, cases = [], []
    for slug, e in by_slug.items():
        rank, note = court_rank(e.get("court"))
        if rank == "UNKNOWN":
            unknowns.append(e.get("court"))
            continue
        name, cite = split_cite(e["title"])
        st = node_status.get(slug, {})
        cases.append({
            "slug": slug, "name": name, "cite": cite,
            "court": e.get("court"), "court_rank": rank,
            "court_rank_note": note, "year": e.get("year"), "area": e.get("area"),
            "area_zh": area_zh(e.get("area")),
            "jurisdiction": jurisdiction_of(e.get("court")),
            "hk_status": "persuasive-only",
            "hk_note": "E&W authority is persuasive only in Hong Kong; pre/post-1997 "
                       "bindingness turns on court, route and date — resolve per matter, never assume.",
            "verified": "unverified",
            "source": {"site": "uklawreference.com", "page": e.get("url"),
                       "reviewed": e.get("reviewed"), "snapshot": "llms-cases.txt 2026-09-04",
                       "note": "Independent editorial summary; authoritative text via official links."},
            "official": official.get(slug, []),
            "status": st.get("status", []), "signal": st.get("signal", "context"),
            "signal_note": "Editorial normalisation of the source's treatment labels, not law.",
            "treatment": [{"type": t["type"], "signal": t["signal"], "case": t["from_name"],
                           "case_year": t.get("from_year"),
                           "case_slug": t["from_slug"]} for t in edge_by_to.get(slug, [])],
            "related": related.get(slug, {"cases": [], "legislation": [], "guides": []}),
            "staleness": {"reviewed": e.get("reviewed")},
        })
    if unknowns:
        raise SystemExit("UNKNOWN COURTS (refusing to guess ranks): %s" % sorted(set(unknowns)))

    out_edges = []
    for e in edges["edges"]:
        if e["to_slug"] in by_slug:
            out_edges.append({"from_slug": e["from_slug"], "from_name": e["from_name"],
                              "to_slug": e["to_slug"], "type": e["type"], "signal": e["signal"]})
    obj = {
        "generated": "2026-09-04", "version": "0.1",
        "doctrine": "England-and-Wales persuasive authority index (449 leading cases). "
                    "Unverified secondary index: every record verified='unverified', "
                    "hk_status='persuasive-only'. Propositions must be checked against "
                    "primary sources before reliance. See data/sources/uklr/SOURCING.md.",
        "jurisdiction": "EN (per-record exceptions: ECHR, EU)",
        "hk_status": "persuasive-only",
        "court_rank_table": {"4": "apex (UKSC, House of Lords)",
                             "3": "intermediate appellate (EWCA, JCPC, historic equivalents)",
                             "2": "superior first instance (EWHC and divisions, specialist tribunals)",
                             "1": "(reserved)", "null": "supranational or non-court: outside the ladder"},
        "signal_legend": {"good-law": "treatment affirms standing", "qualified": "limited/distinguished/modified",
                          "negative": "overruled/doubted/reversed/criticised", "superseded": "overtaken by statute",
                          "historic": "historic interest", "context": "cited without stance"},
        "stats": {"cases": len(cases), "edges": len(out_edges),
                  "resolved_edges": sum(1 for x in out_edges if x["from_slug"]),
                  "signals": {s: sum(1 for c in cases if c["signal"] == s)
                              for s in sorted(set(c["signal"] for c in cases))}},
        "cases": cases, "edges": out_edges,
    }
    emit("persuasive", obj, indent=1)
    print("cases: %d  edges: %d (resolved %d)" % (len(cases), len(out_edges), obj["stats"]["resolved_edges"]))
    print("signals:", obj["stats"]["signals"])


if __name__ == "__main__":
    raise SystemExit(main())
