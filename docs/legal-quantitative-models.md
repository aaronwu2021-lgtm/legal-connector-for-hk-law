# 实体法律概率模型：Python与接口

仅提供 `hand`、`alarp_probability`、`reasonable_mitigation`、`loss_of_chance`。实体问题、概率含义、公式地位和法源见[标准说明](legal-normative-standards.md)。网页、Python、REST及MCP共用[模型定义](../legal_quant/models.json)。

## Python

在项目根目录使用 Python 3.10 或以上，无需第三方依赖：

```python
from legal_quant import evaluate

result = evaluate("alarp_probability", {
    "probability_before": 0.02,
    "probability_after": 0.01,
    "loss_if_harm": 1_000_000,
    "precaution_cost": 30_000,
})
print(result["results"])
# {'avoided_expected_loss': 10000.0, 'cost_risk_ratio': 3.0}
assert result["legal_conclusion"] is None
```

这里是损害概率；3.0不是法定免责倍数。命令行可查看、导出和计算：

```text
python -m legal_quant list
python -m legal_quant show loss_of_chance
python -m legal_quant example reasonable_mitigation --output request.json
python -m legal_quant evaluate --input request.json --output result.json
python -m unittest discover -s legal_quant/tests -v
```

内置数值全为教学假设，不推测缺失概率，也不从AI信心生成概率。

## 输入、版本和来源

```json
{
  "model_id": "loss_of_chance",
  "model_version": "1",
  "inputs": {
    "probability_before": 0.4,
    "probability_after": 0.1,
    "net_value": 1000000
  },
  "context": {
    "jurisdiction": "HK",
    "as_of": null,
    "input_basis": "hypothetical",
    "sources": {},
    "applicability": "unreviewed"
  }
}
```

`jurisdiction`与`as_of`记录背景，不认证适用法律或自动检索历史法。`input_basis="case_data"`时，每个输入字段须在`sources`附非空出处和定位。来源文字是使用者记录，不是机器已核实的事实。

缺失、超出0–1的概率、布尔值冒充数字、非有限数值、重复JSON键及未知字段均被拒绝。减险和机会下降情景的后概率不得高于前概率。采用浮点计算，保留原始值，展示时舍入。

`alarp_probability`是新编号，版本`"1"`。原`alarp`的已货币化收益接口已移除，不会重解释旧输入。其他退出范围的模型亦从目录、网页及调用中移除；旧输入报告未知模型，不会悄悄切换。

## 输出

保留输入、背景、法源编号、逐步公式、数值、假设、限制及未完成的法律判断：

| 字段 | 意义 |
|---|---|
| `analysis_layer` | `substantive_law`，实体法律分析 |
| `formula_authority` | 判决启发式、法律测试形式化或实体赔偿规则形式化 |
| `legal_conclusion` | 始终`null`，不自动认定责任或可赔性 |
| `applicability_status` | 记录使用者独立审查状态 |

前三项的量化收益不等于完整合理性判断；机会价值以可赔性及因果等前提为条件。ALARP零收益的比值为`null`，不把除以零伪装成法律判断。

## 网页与接口

启动本地预览后打开`/quantitative.html`。可导出输入、导回继续计算及下载解释结果。

- `GET /api/quant/models`：四项模型及四项法源。
- `POST /api/quant/evaluate`：接收上述请求，返回条件计算。
- MCP：`list_quantitative_models`、`evaluate_quantitative_model`。

响应为`Cache-Control: no-store`。输入发往当前项目服务，使用真实资料前须核对服务地址。完整协议见[SCHEMA.md](../legal_quant/SCHEMA.md)。
