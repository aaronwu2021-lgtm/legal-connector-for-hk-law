"""Render a local, self-contained substantive-law probability atlas.

The optional mapping file is private case material. This renderer performs no
network requests and never writes it into the source catalogue.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import sys
from typing import Any, Callable
from urllib.parse import urlparse


STATUS_LABELS = {
    "direct": "现有计算模块的深化",
    "support": "概率辅助法律判断",
    "extension": "有前提的扩展",
}


def display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def esc(value: Any) -> str:
    return html.escape(display(value), quote=True)


def safe_url(value: Any) -> str | None:
    candidate = display(value).strip()
    parsed = urlparse(candidate)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return candidate
    return None


def paragraph(label: str, value: Any, css: str = "") -> str:
    if value is None or value == "" or value == []:
        return ""
    return f'<section class="{esc(css)}"><h3>{esc(label)}</h3><p>{esc(value)}</p></section>'


def bullets(label: str, values: Any) -> str:
    if not values:
        return ""
    items = values if isinstance(values, list) else [values]
    return f'<section><h3>{esc(label)}</h3><ul>' + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul></section>"


def source_card(source_id: Any, sources: dict[str, dict[str, Any]]) -> str:
    source = sources.get(str(source_id))
    if source is None:
        return f'<li class="source"><strong>{esc(source_id)}</strong><p>目录中缺少此法律来源；不能据此认定已核实。</p></li>'
    title = source.get("title", source_id)
    url = safe_url(source.get("url"))
    heading = f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(title)}</a>' if url else esc(title)
    metadata = " · ".join(display(source.get(field)) for field in ("jurisdiction", "pin", "verification") if source.get(field))
    note = f'<p>{esc(source["note"])}</p>' if source.get("note") else ""
    return f'<li class="source"><strong>{heading}</strong><p class="source-meta">{esc(metadata)}</p>{note}</li>'


def mapping_card(mapping: Any) -> str:
    if not isinstance(mapping, dict) or not mapping:
        return ""
    rows = []
    for side, label in (("soc", "SOC 论点"), ("sod", "SOD 回应")):
        for pin in mapping.get(side, []):
            if not isinstance(pin, dict):
                continue
            rows.append(f'<tr><th>{esc(label)}</th><td>{esc(pin.get("paragraphs"))}</td><td>{esc(pin.get("pages"))}</td><td>{esc(pin.get("argument"))}</td></tr>')
    table = '<div class="table-wrap"><table><thead><tr><th>案卷</th><th>段落</th><th>PDF 页码</th><th>对应论点</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>" if rows else ""
    return '<section class="case-map"><h3>本案对应 · 私有案卷映射</h3>' + table + paragraph("关联程度", mapping.get("fit")) + paragraph("适用说明", mapping.get("note")) + '<p class="muted">案卷中的主张不等于已经认定的事实；页码为所用 PDF 的页序。</p></section>'


def example_card(example: Any, evaluator: Callable[[str, dict[str, Any]], Any] | None) -> str:
    if not isinstance(example, dict) or "kind" not in example or "inputs" not in example:
        return ""
    kind, inputs = example["kind"], example["inputs"]
    try:
        if evaluator is None:
            root = Path(__file__).resolve().parents[2]
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from legal_quant.scenarios import evaluate
            result = evaluate(kind, inputs)
        else:
            result = evaluator(kind, inputs)
        result_html = '<h4>计算输出</h4><pre>' + esc(result) + "</pre>"
    except (ImportError, ValueError, TypeError, KeyError, ArithmeticError) as exc:
        result_html = '<p class="calculation-error">示例待验证：' + esc(f"{type(exc).__name__}: {exc}") + "</p>"
    payload = json.dumps({"kind": kind, "inputs": inputs}, ensure_ascii=False, indent=2)
    return '<section class="example"><h3>合成数据示例 · 非本案估值</h3><p class="muted">以下数字仅用于展示运算，不代表案卷事实、司法认定或胜诉率。</p><h4>运算类型与输入</h4><pre>' + esc(payload) + "</pre>" + result_html + "</section>"


def entry_card(entry: dict[str, Any], sources: dict[str, dict[str, Any]], evaluator: Callable | None) -> str:
    entry_id, title = entry.get("id", ""), entry.get("title", "未命名标准")
    status = entry.get("status", "support")
    filter_status = status if status in STATUS_LABELS else "support"
    label = STATUS_LABELS.get(status, display(status))
    search_text = " ".join(display(entry.get(field)) for field in ("title", "legal_question", "rule", "formula", "probability_meaning", "mapping"))
    sections = [
        paragraph("实体法律问题", entry.get("legal_question")),
        paragraph("法律标准", entry.get("rule")),
        paragraph("概率指什么", entry.get("probability_meaning")),
        '<section class="formula"><h3>计算表达</h3><pre>' + esc(entry.get("formula")) + "</pre></section>",
        paragraph("公式地位", entry.get("formula_status")),
    ]
    data_rows = []
    for datum in entry.get("data", []):
        if isinstance(datum, dict):
            data_rows.append(f'<tr><td>{esc(datum.get("name"))}</td><td>{esc(datum.get("unit"))}</td><td>{esc(datum.get("source"))}</td></tr>')
    if data_rows:
        sections.append('<section><h3>需要的数据</h3><div class="table-wrap"><table><thead><tr><th>数据</th><th>单位 / 口径</th><th>取得方式 / 来源</th></tr></thead><tbody>' + "".join(data_rows) + "</tbody></table></div></section>")
    sections.extend([
        bullets("计算边界与法律前提", entry.get("limits")),
        mapping_card(entry.get("mapping")),
        paragraph("示例实现范围", entry.get("example_note")),
        example_card(entry.get("example"), evaluator),
    ])
    source_ids = entry.get("source_ids", [])
    if source_ids:
        sections.append('<section><h3>法律依据与核实状态</h3><ul class="sources">' + "".join(source_card(sid, sources) for sid in source_ids) + "</ul></section>")
    return f'<details class="entry" data-status="{esc(filter_status)}" data-search="{esc(search_text.casefold())}" id="{esc(entry_id)}"><summary><span><span class="entry-id">{esc(entry_id)}</span><span class="entry-title">{esc(title)}</span></span><span class="badge">{esc(label)}</span></summary><div class="entry-body">' + "".join(sections) + "</div></details>"


STYLE = """
:root{color-scheme:light;--navy:#18324e;--ink:#243747;--muted:#647181;--paper:#faf8f3;--line:#dedfd9;--blue:#eaf0f6;--gold:#ece1c5}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:system-ui,-apple-system,'Segoe UI','Microsoft YaHei',sans-serif;line-height:1.75}main{max-width:1200px;margin:auto;padding:52px 28px 70px}header{border-top:6px solid var(--navy);padding:24px 0}h1{font-size:clamp(28px,4vw,43px);line-height:1.3;color:var(--navy);margin:12px 0}h2,h3,h4,p{margin:0 0 12px}h3{font-size:17px;color:var(--navy)}h4{font-size:14px}p{white-space:pre-wrap}a{color:#23577c;text-underline-offset:3px}.eyebrow,.entry-id{font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted)}.scope{max-width:980px;color:var(--muted)}.toolbar{position:sticky;top:0;z-index:2;background:var(--paper);padding:18px 0;border-bottom:1px solid var(--line);margin-bottom:20px}.search{display:block;width:100%;padding:13px 16px;border:1px solid #b7c1c9;border-radius:7px;background:white;color:var(--ink);font:inherit}.filters{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 8px}button{border:1px solid #b7c1c9;border-radius:20px;padding:7px 14px;background:transparent;color:var(--navy);font:inherit;font-size:13px;cursor:pointer}button[aria-pressed=true]{background:var(--navy);color:white;border-color:var(--navy)}button:focus-visible,summary:focus-visible,a:focus-visible{outline:3px solid #b98b39;outline-offset:3px}.count,.muted{color:var(--muted);font-size:13px}.entry{background:white;border:1px solid var(--line);border-radius:9px;margin-bottom:14px}.entry summary{padding:20px 23px;cursor:pointer;display:flex;align-items:center;justify-content:space-between;gap:18px;list-style:none}.entry summary::-webkit-details-marker{display:none}.entry summary:after{content:'+';font-size:22px;font-weight:300}.entry[open] summary:after{content:'−'}.entry summary>span:first-child{flex:1}.entry-id{display:block;margin-bottom:3px}.entry-title{font-size:19px;font-weight:650;color:var(--navy)}.badge{font-size:11px;white-space:nowrap;background:var(--blue);padding:4px 9px;border-radius:4px}.entry-body{padding:4px 23px 25px;border-top:1px solid var(--line)}section{margin-top:24px}.formula{background:var(--navy);color:#fff;border-radius:7px;padding:17px 20px}.formula h3{color:#f3dfab}.formula pre{background:none;border:0;padding:0;color:white}.case-map{background:#f5f1e7;padding:20px;border-left:3px solid #b99857}.case-map section{margin-top:14px}.example{border:1px dashed #b4c2cf;padding:20px;border-radius:6px}pre{margin:0 0 12px;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.55;font-size:13px;padding:14px 16px;background:#f4f6f8;border:1px solid #e4e9ed;border-radius:4px}ul{padding-left:22px;margin:0}li{margin:6px 0}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px;text-align:left}th,td{padding:11px 12px;border-bottom:1px solid var(--line);vertical-align:top;min-width:90px;overflow-wrap:anywhere}thead th{background:#f1f4f5;font-weight:600}.sources{padding:0;list-style:none}.source{border-top:1px solid var(--line);padding-top:12px;margin-top:14px}.source-meta{font-size:12px;color:var(--muted);margin:5px 0}.source p:last-child{font-size:13px}.calculation-error{color:#8a3c25}.empty{padding:35px;text-align:center;color:var(--muted)}footer{border-top:1px solid var(--line);margin-top:35px;padding-top:20px;font-size:12px;color:var(--muted)}[hidden]{display:none!important}@media(max-width:640px){main{padding:25px 14px 45px}.entry summary{padding:17px 15px;gap:8px;flex-wrap:wrap}.entry-title{font-size:17px}.entry-body{padding:3px 15px 20px}.badge{white-space:normal}.case-map,.example{padding:14px}.toolbar{position:static}th,td{padding:9px 7px}.formula{padding:14px}}
"""

SCRIPT = """
const search = document.querySelector('#search');
const entries = Array.from(document.querySelectorAll('.entry'));
const buttons = Array.from(document.querySelectorAll('[data-filter]'));
let filter = 'all';
function refresh(){
  const query = search.value.toLocaleLowerCase().trim();
  let visible = 0;
  for (const entry of entries){
    const match = (filter === 'all' || entry.dataset.status === filter) && (!query || entry.dataset.search.includes(query));
    entry.hidden = !match;
    if(match) visible++;
  }
  document.querySelector('#count').textContent = `显示 ${visible} / ${entries.length} 项实体法律问题`;
  document.querySelector('#empty').hidden = visible !== 0;
}
search.addEventListener('input',refresh);
for(const button of buttons) button.addEventListener('click',()=>{
  filter = button.dataset.filter;
  for(const other of buttons) other.setAttribute('aria-pressed',String(other === button));
  refresh();
});
document.querySelector('#expand').addEventListener('click',()=>{for(const entry of entries) if(!entry.hidden) entry.open = true;});
document.querySelector('#collapse').addEventListener('click',()=>{for(const entry of entries) entry.open = false;});
refresh();
"""


def render_atlas(catalogue: dict[str, Any], mapping: dict[str, Any] | None = None, evaluator: Callable | None = None) -> str:
    sources = {str(source["id"]): source for source in catalogue.get("sources", [])}
    entries = []
    for original in catalogue.get("entries", []):
        entry = dict(original)
        if mapping and entry.get("id") in mapping:
            entry["mapping"] = mapping[entry["id"]]
        entries.append(entry)
    has_mapping = any(entry.get("mapping") for entry in entries)
    mode = "本地私有案卷映射版" if has_mapping else "通用法律标准目录"
    filters = '<button type="button" data-filter="all" aria-pressed="true">全部</button>' + "".join(f'<button type="button" data-filter="{esc(key)}" aria-pressed="false">{esc(label)}</button>' for key, label in STATUS_LABELS.items())
    cards = "\n".join(entry_card(entry, sources, evaluator) for entry in entries)
    title = catalogue.get("title", "实体法律概率模型图谱")
    notes = bullets("统一计算口径", catalogue.get("common_method")) + bullets("明确不作概率判定的事项", catalogue.get("exclusions"))
    if mapping and isinstance(mapping.get("_meta"), dict):
        notes += bullets("本案来源与版本核对", mapping["_meta"].get("notes"))
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>{STYLE}</style></head>
<body><main><header><div class="eyebrow">SUBSTANTIVE LAW · PROBABILITY · {esc(mode)}</div><h1>{esc(title)}</h1><p class="scope">{esc(catalogue.get("scope_note"))}</p><p class="muted">只讨论实体法律标准。概率的对象、法律前提、数据口径与公式地位分别列明；合成示例不构成本案数值结论。</p><details><summary>计算口径、覆盖范围与来源版本</summary>{notes}</details></header>
<div class="toolbar"><label for="search" class="muted">搜索法律标准、公式或案卷论点</label><input id="search" class="search" type="search" placeholder="例如：可预见性、减损、免责上限" autocomplete="off"><div class="filters">{filters}<button type="button" id="expand">展开当前结果</button><button type="button" id="collapse">收起全部</button></div><div id="count" class="count" aria-live="polite">共 {len(entries)} 项实体法律问题</div></div>
<div id="entries">{cards}</div><p id="empty" class="empty" hidden>没有匹配结果。可清空搜索或切换到「全部」。</p>
<footer>本页为离线生成的独立 HTML，不加载外部脚本或资产。法律来源链接仅在点击时打开。涉及同一风险的多个法律标准可共用计算，但不因此成为多条独立法定公式。</footer></main><script>{SCRIPT}</script></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description="生成实体法律概率模型的离线 HTML 图谱")
    parser.add_argument("--catalogue", required=True, type=Path)
    parser.add_argument("--mapping", type=Path, help="可选私有映射 JSON，以 entry.id 为键")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    catalogue = json.loads(args.catalogue.read_text(encoding="utf-8-sig"))
    mapping = json.loads(args.mapping.read_text(encoding="utf-8-sig")) if args.mapping else None
    if mapping is not None and not isinstance(mapping, dict):
        parser.error("mapping 必须是以 entry.id 为键的 JSON 对象")
    rendered = render_atlas(catalogue, mapping)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(json.dumps({"output": str(args.output), "entries": len(catalogue.get("entries", [])), "private_mapping": bool(mapping), "example_errors": rendered.count('class="calculation-error"')}, ensure_ascii=False))


if __name__ == "__main__":
    main()
