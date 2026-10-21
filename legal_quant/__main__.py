"""Run with ``python -m legal_quant --help`` from the repository root."""

import argparse
import json
from pathlib import Path
import sys

from .engine import evaluate, get_model, list_models


def _bad_constant(value):
    raise ValueError(f"JSON不允许非有限数值：{value}")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON包含重复字段：{key}")
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="法律标准与辅助量化模型；区分公式依据，计算不认定法律责任。")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="列出模型目录")
    show = commands.add_parser("show", help="查看完整模型定义、边界和示例")
    show.add_argument("model_id")
    example = commands.add_parser("example", help="输出可直接计算的完整教学请求JSON")
    example.add_argument("model_id")
    example.add_argument("--output", help="写入UTF-8文件（省略则输出到终端）")
    calculation = commands.add_parser("evaluate", help="读取请求JSON并计算")
    calculation.add_argument("--input", required=True, help="请求JSON路径，或-从标准输入读取")
    calculation.add_argument("--output", help="写入UTF-8结果文件（省略则输出到终端）")
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            result = [{"id": m["id"], "version": m["version"], "title": m["title"],
                       "category": m["category"], "question": m["question"],
                       "analysis_layer": m["analysis_layer"],
                       "formula_authority": m["formula_authority"]} for m in list_models()]
        elif args.command == "show":
            result = get_model(args.model_id)
        elif args.command == "example":
            model = get_model(args.model_id)
            result = {"model_id": model["id"], "model_version": model["version"],
                      "inputs": model["example_inputs"],
                      "context": {"jurisdiction": "HK", "as_of": None, "input_basis": "hypothetical",
                                  "sources": {}, "applicability": "unreviewed"}}
        else:
            raw = sys.stdin.read(2_000_001) if args.input == "-" else Path(args.input).read_text(encoding="utf-8-sig")
            if len(raw) > 2_000_000:
                raise ValueError("请求JSON过大（最多2000000字符）。")
            request = json.loads(raw, parse_constant=_bad_constant, object_pairs_hook=_unique_object)
            if not isinstance(request, dict):
                raise ValueError("请求必须是JSON对象。")
            required = {"model_id", "model_version", "inputs"}
            if not required <= set(request) or set(request) - (required | {"context"}):
                raise ValueError("请求必须包含model_id、model_version、inputs；仅context可选。")
            if "context" in request and not isinstance(request["context"], dict):
                raise ValueError("context必须是对象；省略该字段可使用默认值。")
            result = evaluate(request["model_id"], request["inputs"],
                              request.get("context"), request["model_version"])
        serialized = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        output = getattr(args, "output", None)
        if output:
            Path(output).write_text(serialized, encoding="utf-8")
        else:
            sys.stdout.write(serialized)
        return 0
    except (ValueError, OSError) as exc:
        sys.stderr.write(f"错误：{exc}\n")
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
