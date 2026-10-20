"""Standard-library interpreter for the shared, declarative model catalogue.

There is deliberately no eval, generated Python, external execution or legal
threshold inference here. Legal eligibility remains an external input.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
import math
from pathlib import Path
import re
from typing import Any

CATALOGUE_PATH = Path(__file__).with_name("models.json")
MAX_SAFE_INTEGER = 9_007_199_254_740_991
_CONTEXT_KEYS = {"jurisdiction", "as_of", "input_basis", "sources", "applicability"}


def _number(value: Any, label: str = "数值") -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label}必须是数字，布尔值不能作为数字。")
    try:
        # Use the same binary64 arithmetic as the JavaScript runtime, including
        # when Python's JSON decoder initially produced an arbitrary-size int.
        number = float(value)
        finite = math.isfinite(number)
    except (OverflowError, TypeError):
        finite = False
    if not finite:
        raise ValueError(f"{label}必须是有限数值。")
    return number


def _finite_tree(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return _number(value, "计算结果")
    if isinstance(value, list):
        for item in value:
            _finite_tree(item)
        return value
    raise ValueError("计算表达式产生了不支持的结果类型。")


def _arity(args: list[Any], minimum: int, maximum: int | None = None) -> None:
    if len(args) < minimum or (maximum is not None and len(args) > maximum):
        raise ValueError("表达式参数数量不正确。")


def _boolean(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError("逻辑表达式必须返回布尔值。")
    return value


def _lookup(path: str, scope: dict[str, Any]) -> Any:
    if not isinstance(path, str) or not path:
        raise ValueError("表达式变量路径无效。")
    value: Any = scope
    for segment in path.split("."):
        if not isinstance(value, dict) or segment not in value:
            raise ValueError(f"表达式变量不存在：{path}")
        value = value[segment]
    return value


def _same_scalar(a: Any, b: Any) -> bool:
    """Match JavaScript strict primitive equality, without bool/int coercion."""
    if isinstance(a, (list, dict)) or isinstance(b, (list, dict)):
        raise ValueError("相等比较只支持标量。")
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return _number(a) == _number(b)
    return type(a) is type(b) and a == b


def _evaluate_expression(expression: Any, scope: dict[str, Any]) -> Any:
    if expression is None or isinstance(expression, (str, bool)):
        return expression
    if isinstance(expression, (int, float)):
        return _number(expression, "表达式常量")
    if isinstance(expression, list):
        return [_evaluate_expression(item, scope) for item in expression]
    if not isinstance(expression, dict):
        raise ValueError("表达式必须是JSON标量、列表或声明式节点。")
    if "var" in expression:
        if set(expression) != {"var"}:
            raise ValueError("变量表达式包含未知属性。")
        return _lookup(expression["var"], scope)
    name = expression.get("op")
    if name == "if":
        if set(expression) != {"op", "condition", "then", "else"}:
            raise ValueError("条件表达式属性不正确。")
        condition = _boolean(_evaluate_expression(expression["condition"], scope))
        return _evaluate_expression(expression["then" if condition else "else"], scope)
    if name == "map":
        if set(expression) != {"op", "items", "value"}:
            raise ValueError("map表达式属性不正确。")
        items = _evaluate_expression(expression["items"], scope)
        if not isinstance(items, list):
            raise ValueError("map需要数组。")
        return [_evaluate_expression(expression["value"], {**scope, "item": item, "index": index})
                for index, item in enumerate(items)]
    if set(expression) != {"op", "args"} or not isinstance(expression["args"], list):
        raise ValueError("运算表达式属性不正确。")
    args = [_evaluate_expression(arg, scope) for arg in expression["args"]]
    try:
        result = _apply_operator(name, args)
    except (ArithmeticError, TypeError) as exc:
        raise ValueError(f"运算{name}失败：数值溢出、非法类型或除以零。") from exc
    return _finite_tree(result)


def _apply_operator(name: str, args: list[Any]) -> Any:
    if name in {"and", "or"}:
        _arity(args, 1)
        flags = [_boolean(arg) for arg in args]
        return all(flags) if name == "and" else any(flags)
    if name in {"eq", "ne"}:
        _arity(args, 2, 2)
        equal = _same_scalar(*args)
        return equal if name == "eq" else not equal
    if name in {"lt", "le", "gt", "ge"}:
        _arity(args, 2, 2)
        a, b = [_number(arg) for arg in args]
        return {"lt": lambda: a < b, "le": lambda: a <= b,
                "gt": lambda: a > b, "ge": lambda: a >= b}[name]()
    if name == "at":
        _arity(args, 2, 2)
        items, index = args
        if not isinstance(items, list):
            raise ValueError("at需要数组。")
        _number(index, "数组索引")
        if int(index) != index or index < 0 or index >= len(items):
            raise ValueError("数组索引必须是范围内非负整数。")
        return items[int(index)]
    if name in {"sum", "argmin"}:
        _arity(args, 1, 1)
        if not isinstance(args[0], list):
            raise ValueError(f"{name}需要数组。")
        numbers = [_number(value) for value in args[0]]
        if name == "sum":
            # Sequential accumulation agrees with JavaScript's evaluator.
            result: int | float = 0
            for number in numbers:
                result = _number(result + number, "中间计算结果")
            return result
        if not numbers:
            raise ValueError("argmin需要非空数组。")
        smallest = min(numbers)
        return [index for index, number in enumerate(numbers) if number == smallest]
    if name in {"min", "max"}:
        _arity(args, 1)
        values = args[0] if len(args) == 1 and isinstance(args[0], list) else args
        if not values:
            raise ValueError(f"{name}需要非空数组或至少一个标量。")
        numbers = [_number(value) for value in values]
        return min(numbers) if name == "min" else max(numbers)
    if name in {"add", "mul"}:
        _arity(args, 1)
        result = 0 if name == "add" else 1
        for arg in args:
            value = _number(arg)
            result = _number(result + value if name == "add" else result * value, "中间计算结果")
        return result
    if name == "abs":
        _arity(args, 1, 1)
        return abs(_number(args[0]))
    if name in {"sub", "div", "pow"}:
        _arity(args, 2, 2)
        a, b = [_number(arg) for arg in args]
        if name == "sub":
            return a - b
        if name == "div":
            if b == 0:
                raise ValueError("除数不能为零。")
            return a / b
        # Use binary64 power, as JavaScript does, avoiding huge Python integers.
        return math.pow(a, b)
    raise ValueError(f"未知运算：{name}")


def _catalogue() -> list[dict[str, Any]]:
    payload = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))
    if payload["schema_version"] != "1":
        raise ValueError("不支持的模型目录版本。")
    return payload["models"]


def list_models() -> list[dict[str, Any]]:
    """Return all model definitions, including formulas and hypothetical inputs."""
    return deepcopy(_catalogue())


def get_model(model_id: str, model_version: str = "1") -> dict[str, Any]:
    if not isinstance(model_id, str):
        raise ValueError("model_id必须是字符串。")
    for model in _catalogue():
        if model["id"] == model_id:
            if model_version != model["version"]:
                raise ValueError(f"模型版本不匹配：{model_id}只支持版本{model['version']}。")
            return deepcopy(model)
    raise ValueError(f"未知模型：{model_id}")


def _validate_field(value: Any, spec: dict[str, Any], path: str) -> None:
    kind = spec["type"]
    if kind in {"number", "integer"}:
        _number(value, path)
        if kind == "integer" and (int(value) != value or abs(value) > MAX_SAFE_INTEGER):
            raise ValueError(f"{path}必须是可精确表达的安全整数。")
        for bound, predicate, description in [
            ("min", lambda x, y: x >= y, "不得小于"),
            ("max", lambda x, y: x <= y, "不得大于"),
            ("exclusiveMinimum", lambda x, y: x > y, "必须大于"),
            ("exclusiveMaximum", lambda x, y: x < y, "必须小于"),
        ]:
            if bound in spec and not predicate(value, spec[bound]):
                raise ValueError(f"{path}{description}{spec[bound]}。")
        if "enum" in spec and not any(_same_scalar(value, allowed) for allowed in spec["enum"]):
            raise ValueError(f"{path}必须是允许的等级：{spec['enum']}。")
        return
    if kind == "string":
        if not isinstance(value, str) or not value.strip() or len(value) > spec.get("maxLength", 2000):
            raise ValueError(f"{path}必须是非空且长度有效的字符串。")
        return
    if kind in {"number_array", "object_array"}:
        if not isinstance(value, list):
            raise ValueError(f"{path}必须是数组。")
        if len(value) < spec.get("minItems", 1) or len(value) > min(spec.get("maxItems", 256), 256):
            raise ValueError(f"{path}数组长度超出允许范围。")
        for index, item in enumerate(value):
            item_path = f"{path}[{index}]"
            if kind == "number_array":
                _validate_field(item, {**spec, "type": "number"}, item_path)
            else:
                _validate_inputs(item, spec["items"], item_path)
        return
    raise ValueError(f"不支持的输入类型：{kind}")


def _validate_inputs(inputs: Any, fields: list[dict[str, Any]], path: str = "inputs") -> None:
    if not isinstance(inputs, dict):
        raise ValueError(f"{path}必须是对象。")
    if not all(isinstance(key, str) for key in inputs):
        raise ValueError(f"{path}字段名称必须是字符串。")
    expected = {field["id"] for field in fields}
    unknown, missing = set(inputs) - expected, expected - set(inputs)
    if unknown:
        raise ValueError(f"{path}包含未知字段：{', '.join(sorted(unknown))}。")
    if missing:
        raise ValueError(f"{path}缺少必需字段：{', '.join(sorted(missing))}。")
    for field in fields:
        _validate_field(inputs[field["id"]], field, f"{path}.{field['id']}")


def _context(context: Any, fields: list[dict[str, Any]]) -> dict[str, Any]:
    if context is None:
        context = {}
    if not isinstance(context, dict) or not all(isinstance(key, str) for key in context):
        raise ValueError("context必须是字段名为字符串的对象。")
    if set(context) - _CONTEXT_KEYS:
        raise ValueError("context包含未知字段。")
    normalized = {
        "jurisdiction": "HK", "as_of": None, "input_basis": "hypothetical",
        "sources": {}, "applicability": "unreviewed", **deepcopy(context),
    }
    jurisdiction = normalized["jurisdiction"]
    if not isinstance(jurisdiction, str) or not jurisdiction.strip() or len(jurisdiction) > 100:
        raise ValueError("jurisdiction必须是非空字符串（最多100字符）。")
    as_of = normalized["as_of"]
    if as_of is not None:
        if not isinstance(as_of, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
            raise ValueError("as_of必须为null或YYYY-MM-DD日期。")
        try:
            date.fromisoformat(as_of)
        except ValueError as exc:
            raise ValueError("as_of不是有效日期。") from exc
    if normalized["input_basis"] not in ("hypothetical", "case_data"):
        raise ValueError("input_basis必须是hypothetical或case_data。")
    if normalized["applicability"] not in ("unreviewed", "externally_assessed"):
        raise ValueError("applicability必须是unreviewed或externally_assessed。")
    sources = normalized["sources"]
    if not isinstance(sources, dict) or not all(isinstance(key, str) for key in sources):
        raise ValueError("sources必须是输入字段名称到来源说明的对象。")
    field_ids = {field["id"] for field in fields}
    if set(sources) - field_ids:
        raise ValueError("sources包含未知的输入字段名称。")
    for name, source in sources.items():
        if not isinstance(source, str) or not source.strip() or len(source) > 4000:
            raise ValueError(f"sources.{name}必须是非空来源说明（最多4000字符）。")
    if normalized["input_basis"] == "case_data" and set(sources) != field_ids:
        raise ValueError("case_data要求每个顶级输入字段均附非空来源说明。")
    return normalized


def evaluate(model_id: str, inputs: dict[str, Any], context: dict[str, Any] | None = None,
             model_version: str = "1") -> dict[str, Any]:
    """Validate and calculate one model, with no inference of legal conclusions.

    ``externally_assessed`` records the caller's assertion, never verification by
    this engine. All calculations retain ``legal_conclusion: None``.
    """
    model = get_model(model_id, model_version)
    _validate_inputs(inputs, model["fields"])
    normalized_context = _context(context, model["fields"])
    results: dict[str, Any] = {}
    scope = {"input": deepcopy(inputs), "out": results}
    for constraint in model["constraints"]:
        if not _boolean(_evaluate_expression(constraint["expression"], scope)):
            raise ValueError(constraint["message"])
    steps = []
    for output in model["outputs"]:
        value = _finite_tree(_evaluate_expression(output["expression"], scope))
        results[output["id"]] = value
        steps.append({key: output[key] for key in ("id", "label", "unit", "formula")} | {"value": value})
    response = {
        "model_id": model_id,
        "model_version": model["version"],
        "category": model["category"],
        "output_kind": model["output_kind"],
        "context": normalized_context,
        "inputs": deepcopy(inputs),
        "source_ids": model["source_ids"],
        "legal_status": model["legal_status"],
        "results": results,
        "steps": steps,
        "assumptions": model["assumptions"],
        "limitations": model["limitations"],
        "required_legal_findings": model["required_legal_findings"],
        "legal_conclusion": None,
        "applicability_status": normalized_context["applicability"],
    }
    # A last serialization check guarantees API-safe finite JSON.
    try:
        json.dumps(response, allow_nan=False)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("输出不是有效的有限JSON数据。") from exc
    return response
