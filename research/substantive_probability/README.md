# 实体法律概率分析目录

本目录有19个分析条目：2项深化原有合理注意、合理减损模块，14项补充实体标准或赔偿问题，3项明确标为有前提的法律拓展。下表按12组问题组织，并非19个独立诉因或法院规定的数学公式。

| 法律问题组 | 条目 |
|---|---|
| 注意与技能 | `care` |
| 可预见性及损失范围 | `foreseeability`、`contract_remoteness`、`scope_of_duty` |
| 事实因果 | `causation` |
| 条款合理性及不合情理 | `cap_reasonableness`、`unconscionability` |
| 失实陈述 | `representation_belief`、`inducement` |
| 合同裁量 | `discretion` |
| 担保变现 | `security_sale` |
| 不可抗力 | `force_majeure` |
| 信托及衡平补偿 | `trustee_care`、`equitable_compensation` |
| 重大过失、故意失当 | `serious_default` |
| 减损、合同价值及机会 | `mitigation`、`contract_value`、`loss_of_chance` |
| 履行时间 | `reasonable_time` |

`scope_of_duty`、`loss_of_chance`、`reasonable_time`属于须进一步确认的拓展。其余条目有现有诉辩对应，但数值模型仍是分析工具；主观实际依赖、义务范围、法定适用和责任成立没有概率判定器。程序法、证据可信度、胜诉率、仲裁费用不纳入。

## 文件与阅读

- `catalogue.json`：通用法律标准、法源核验级别、公式性质、数据清单和教学例子。
- `examples/`：19份纯合成输入，每份均可用Python直接运行。
- `render_atlas.py`：从目录生成无外部依赖的HTML，可选合并本地私有案件映射。
- `../../server/public/substantive-probability.html`：通用版页面；由目录生成，不手工修改。
- `local/matter-map.json`、`local/SOC-SOD-实体概率分析.md`、`local/index.html`：本地案件对应材料；Git忽略，位于公开部署目录之外。

## 运行

在仓库根目录运行，Python标准库即可：

```powershell
python -m legal_quant.scenarios liability_cap research/substantive_probability/examples/cap_reasonableness.json
python -m legal_quant.scenarios paired_counterfactual research/substantive_probability/examples/causation.json
python research/substantive_probability/validate_atlas.py
python research/substantive_probability/render_atlas.py --catalogue research/substantive_probability/catalogue.json --output server/public/substantive-probability.html
```

有本地案件映射时另生成私有版：

```powershell
python research/substantive_probability/render_atlas.py --catalogue research/substantive_probability/catalogue.json --mapping research/substantive_probability/local/matter-map.json --output research/substantive_probability/local/index.html
python -m http.server 8928 --bind 127.0.0.1 --directory research/substantive_probability/local
```

这项服务只用于本机查看。私有目录不放到`server/public/`，也不随通用代码提交或部署。

## 六类情景计算

| 运算 | 输出 |
|---|---|
| `risk_distribution` | 期望损失、选定损害类别的概率与期望损失 |
| `paired_counterfactual` | 共同场景下的实际/合规损失差及外部认定的范围内差额 |
| `precaution_comparison` | 预防前后风险、减少损失及净收益 |
| `liability_cap` | 上限的风险转移、保险给付、保留风险及资源缺口概率 |
| `timely_performance` | 在候选时限内完成的概率及平均时长 |
| `execution_value` | 同一数量下的期望净变现价值与实际差额 |

输入场景必须互斥、穷尽且概率合计1（仅允许1e-9浮点误差，不自动归一化）。布尔值不能伪装数字；未知字段、负概率、NaN及无穷大被拒绝。差额保留符号，避免把每个场景只取正值而夸大损失。`legal_conclusion`始终为`null`。

示例仅是离散情景算术。实际账户的强平时点、订单簿执行、资金到达、保证金阶梯以及统计校准，需要独立重建，不能从19个小例子推断本案结果。

## 法源口径

香港法例依据本地Verified Copy及具体条文核对；官方网页本次未返回正文，因此不声称完成最新修订或事件时点沿革复核。英国原判已读者标明`primary`；通过后案转引的旧案保留`quoted`。本地原判报告标`primary_local_copy`，其公开链接有时仅是检索入口，准确文件位置保存在本地核验记录。

特别注意Cap.457 s.8(1)的消费者禁止排除规则；不能拿保险或期望损失比较重新认可依法禁止的免责。Zhang Hong Li是香港终审法院判决，但讨论泽西法信托；Nigeria是英国银行背景；两者均不提供重大过失数值门槛。ALARP仍仅在原比较法教学计算器保留，不计为本案独立实体依据。
