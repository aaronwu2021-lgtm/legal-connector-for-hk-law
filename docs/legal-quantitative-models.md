# 法律量化模型：从问题、前提到可复核计算

本模块共17类模型，使用同一套 Python、REST 和 MCP 接口。其中7类针对法律标准本身，见[法律标准本身如何计算](legal-normative-standards.md)。本页保留汉德公式与原有10类辅助方法的说明；贝叶斯更新、损失金额和和解经济学等，不能直接作为“法律要求做到什么程度”的答案。所有模型都不把不同法律要件加总成一个“责任分数”。

所有内置例子均为教学假设。本文以元作示例金额单位；实际计算必须统一币种、价格基准和期间。模型编号与输入字段以 [`legal_quant/models.json`](../legal_quant/models.json) 为准，来源核验记录见 [`legal_quant/sources.json`](../legal_quant/sources.json)。

## 1. 三层逻辑

| 层 | 需要回答的问题 | 本模块的处理 |
|---|---|---|
| 法律前提 | 什么法域、什么时间、哪项请求或抗辩、哪些要件及计算规则适用？ | 每模型列出 `required_legal_findings`；保留适用状态，计算不代替认定 |
| 事实与估计 | 输入是已证明事实、数据估计，还是演示假设？单位与证据是什么？ | 通过 `context.input_basis`、`context.sources` 记录；真实案件数据要求来源说明 |
| 条件计算 | 当前提及输入给定时，结果怎样得出？ | 同一公式定义产生逐步结果、单位及限制；目录关联来源；`legal_conclusion` 始终为空 |

三个层次不能互相代替：来源原文读过，不等于该来源适用于香港；算术成立，不等于事实成立；赔偿金额算出，不等于损失项目可赔。

本版本的香港法律适用性均未由模块核验。选择 `jurisdiction: "HK"` 记录分析对象，不会把美国规则、国际软法或一般经济理论转成香港现行法。

### 选择顺序

1. 先确定要解决的是事实命题、金额、方案比较、原则权衡、政策激励还是市场结构。
2. 再列出法律上的必备条件。必要条件不成立，其他数字再高也不能补足；未知条件保持未知。
3. 选择回答该具体问题的模型，核对输入依据、单位及适用前提。
4. 读取数值结果和计算轨迹，同时保留不确定性及尚缺的法律判断。
5. 如需比较情景，改变有争议的输入重新计算，并记录改变了哪些假设。当前通用模块不自动估计概率、拟合回归或生成置信区间。

本模块与现有 doctrine 体系并列：现有要件、门槛及适用规则仍由原来的法律分析路径处理，量化结果可以作为其中一项材料，不能覆盖其结论。

完整过失责任的逐要件示例另见 [`examples/negligence_quant/README.md`](../examples/negligence_quant/README.md)。该示例覆盖注意义务、违反义务、因果关系、损失和赔偿调整等分析记录；此处十一模型提供跨法律领域的通用计算目录，两者的作用不同。

## 2. 模型目录

| ID | 所问的问题 | 输出性质 |
|---|---|---|
| `hand` | 指定措施减少的预期损失是否超过其成本？ | 经济比较 |
| `alexy` | 给定原则强度和可靠性等级后，理论权重比是多少？ | 论证结构中的比值 |
| `bayes` | 一项证据如何更新一个具体事实命题？ | 条件后验概率 |
| `deterrence` | 什么制裁额使预期制裁等于给定社会损害？ | 简化政策基准 |
| `coase` | 已列出的方案哪项总社会成本最低？ | 方案成本比较 |
| `settlement` | 双方给定预期和未来成本是否产生和解区间？ | 决策区间 |
| `cover_damages` | 替代购买价差及调整后的金额是多少？ | 条件赔偿金额 |
| `loss_of_chance` | 一个机会的价值减少了多少？ | 条件机会价值 |
| `present_value` | 给定未来现金流在估值日值多少？ | 条件现值 |
| `counterfactual_damage` | 给定反事实价格后，过收费路径的损失是多少？ | 条件经济损失 |
| `hhi` | 两家企业合并使给定市场的集中度改变多少？ | 市场结构指标 |

### 2.1 `hand`：汉德公式与增量风险比较

原式为 \(B<PL\)。本实现比较一项措施实际能够减少的损失：

\[
EL_0=NpL,\quad EL_1=Np(1-e_p)L(1-e_L),\quad NB=EL_0-EL_1-B
\]

| 输入 | 含义 |
|---|---|
| `N` | 同期间暴露次数 |
| `p` | 每次暴露事故概率，0–1 |
| `L` | 发生事故后的条件平均损失 |
| `annual_B` | 同期间措施成本；字段沿用年度名称，改变期间时须全部同步 |
| `prob_reduction` | \(e_p\)，概率减少比例，0–1 |
| `severity_reduction` | \(e_L\)，条件损失减少比例，0–1 |

例：\(N=100000,p=0.00008,L=104000,B=120000,e_p=0.6,e_L=0\)。措施前预期损失为832,000，措施后332,800，减少499,200，净收益379,200。`economically_favourable` 在净收益严格大于零时为真；等于零只表示经济收支相等。

该模型不能以经济净收益证明注意义务、可预见性、违反义务或个案因果关系。\(Np=8\) 是预期事故次数，不能称作“800%的事故概率”。依据是 [Carroll Towing 判词教学节选](https://sites.oxy.edu/whitney/xaccess/ec357/cases/tort/unitedstates_v_carrolltowing.htm)；增量比较是本模块的经济扩展。

### 2.2 `alexy`：原则间的理论权重

\[
W_{i,j}=\frac{I_iW_iR_i}{I_jW_jR_j}
\]

输入 `I_i` 表示原则i受到干预的强度，`I_j` 表示实现相冲突原则j的重要程度；两侧的 `W` 和 `R` 分别表示抽象重要性及前提可靠性等级。本版本把 \(I,W\) 编码为1、2、4，把 \(R\) 编码为1、0.5、0.25。编码及赋值理由必须外部提供。

例：\((4\times2\times0.5)/(2\times2\times1)=1\)。两侧在这组赋值下相等；若把 `R_i` 从0.5改为1，比值变为2。这说明赋值如何影响结果，不证明某项权利客观上重要两倍。

**权重比和可靠性等级都不是案件概率。**该模型不跳过合法目的、适当性、必要性等适用审查，也不是法定评分表。[Alexy 2014年论文书目](https://academic.oup.com/icon/article/12/3/511/763784)已核对，但本次无法读取全文，因此来源仅标为 `web`，尚不能声称已逐字核验该文的具体公式。

### 2.3 `bayes`：事实命题的证据更新

\[
P(H\mid E)=\frac{LRp}{1-p+LRp},\qquad LR=\frac{P(E\mid H)}{P(E\mid\neg H)}
\]

`prior` 是具体命题 \(H\) 的先验概率；`likelihood_ratio` 是对该命题及其备择命题的一项合并似然比。例：`prior=0.2`、`likelihood_ratio=8`，得到 `posterior≈0.666667`。

必须先说明命题是什么、两假说是否互斥且穷尽、先验和似然比从何而来。不能把 \(P(E\mid H)\) 与 \(P(H\mid E)\) 混淆，不能未经相关性分析就连乘多项证据。先验为1且似然比为0会产生不相容的零分母，程序拒绝计算。输出不设“胜诉”“有罪”或“承担责任”的阈值。参考 [NIST IR 8503 §4.3.2，印刷第81–82页](https://nvlpubs.nist.gov/nistpubs/ir/2024/NIST.IR.8503.pdf)。

### 2.4 `deterrence`：预期制裁

\[
F^*=\frac Hq,\qquad qF^*=H
\]

`harm` 是每次行为的社会损害，`sanction_probability` 是最终实际受制裁的概率，必须大于0且不超过1。例：损害100,000、概率0.2，基准制裁为500,000，预期制裁为100,000。

这是固定受罚概率、风险中性及简化制裁成本条件下的基准。它不包含法律授权、处罚上限或量刑裁量；低受罚概率算出高金额，不产生提高罚款的法律权限。参考 [Kaplow与Shavell原作者文稿 §6.2.1，印刷第68页](https://laweconcenter.law.harvard.edu/wp-content/uploads/2024/11/251.pdf)。

### 2.5 `coase`：候选方案的总成本

\[
TC_a=C_{\text{预防},a}+H_{\text{残余},a}+C_{\text{交易},a}+C_{\text{执行},a}
\]

`alternatives` 为方案数组，每项包含 `name`、`prevention_cost`、`residual_harm`、`transaction_cost`、`enforcement_cost`。模型返回各方案总成本、最低总成本及全部并列最低方案索引。

例：工厂隔音 \(30000+0+8000+2000=40000\)；居民搬迁 \(80000+0+8000+2000=90000\)；维持现状100,000。在列出的三种情景中，隔音总成本最低。它不决定谁享有权利或谁应负担成本。

各项必须使用相同评价范围和期间，避免把当事人之间的纯支付转移重复算为新增社会成本。这是受科斯问题意识启发的自建比较式，不是“科斯定理的法定公式”。[Coase 1960论文](https://www.journals.uchicago.edu/doi/10.1086/466560)仅核对出版书目，全文尚未阅读。

### 2.6 `settlement`：潜在和解区间

\[
S_{\min}=p_PD-C_P,\qquad S_{\max}=p_DD+C_D
\]

`plaintiff_probability` 和 `defendant_probability` 都是对“原告胜诉”的估计，分别由原告和被告持有。`award` 是假定胜诉时的固定金额，`plaintiff_cost`、`defendant_cost` 是尚未发生的诉讼成本。

例：金额1,000,000，双方估计0.65、0.5，双方未来成本150,000、100,000，得到500,000至600,000的潜在区间。如果下限大于上限，`overlap=false`，不能把两个数仍称为可接受区间。

双方风险中性、各自承担费用、赔偿额一致、忽略和解成本是本版本假设。模型不纳入香港讼费转移、要约后果、执行回收风险等，因此不能直接用作香港案件的建议底价。参考 [Kaplow与Shavell §5.2.1，印刷第49页](https://laweconcenter.law.harvard.edu/wp-content/uploads/2024/11/251.pdf)。

### 2.7 `cover_damages`：替代交易差额

\[
D_{\text{net}}=P_{\text{替代}}-P_{\text{合同}}+L_{\text{其他}}-C_{\text{节省}}
\]

输入为 `replacement_price`、`contract_price`、`other_losses`、`saved_costs`，均须采用同一交易数量及金额口径。例：价格差额 `raw_difference=30,000`；调整后 `net_amount=130,000−100,000+20,000−5,000=45,000`。净差额允许为负，以保留输入的真实算术关系，但不自动生成反向赔偿请求。

`other_losses` 表示已经另行筛选可赔性的项目，而不是任何可想到的损失。合理补购、善意、时间、因果关系及其他损失资格须另查。参考 [UCC §2-712(1)–(3)](https://www.law.cornell.edu/ucc/2/2-712)；这是Cornell刊载的统一文本，未核对特定州的现行制定法。

### 2.8 `loss_of_chance`：机会价值减少

\[
V_{\text{lost}}=(p_{\text{before}}-p_{\text{after}})V_{\text{net}}
\]

输入为 `probability_before`、`probability_after` 和成功时的净利益 `net_value`。前后概率均在0–1之间，且前者不得小于后者。例：\((0.4-0.1)\times1000000=300000\)。

这里的30%是机会减少30个百分点，不是被告“只应承担30%责任”。须先判断适用法是否承认这类机会为损失，再证明机会下降及相关因果关系。参考 [UNIDROIT 2016通则第7.4.3(2)条](https://www.unidroit.org/wp-content/uploads/2021/06/Unidroit-Principles-2016-English-bl.pdf)。通则属于国际商事合同软法，不自动成为香港法，也不据此扩展至所有医疗或人伤案件。

### 2.9 `present_value`：未来损失折现

\[
PV=\sum_t\frac{C_ts_t}{(1+r)^t}
\]

`cashflows` 数组每项含 `amount`、`year`、`probability`；`discount_rate` 是固定年折现率。估值日为 `year=0`，一年后的年末为1；概率是该项损失发生的联合条件概率，不得与已调整的金额重复计算。

例：三年条件金额各100,000，概率依次为1、0.95、0.9，折现率0.03：

\[
PV=\frac{100000}{1.03}+\frac{95000}{1.03^2}+\frac{90000}{1.03^3}\approx268996.74
\]

本版本支持0–200的整数年度及非负固定利率，不支持负利率、期中现金流或期限利率曲线。实际金额与实际利率、名义金额与名义利率须匹配。参考 [GAD Ogden表官方说明](https://www.gov.uk/government/publications/ogden-tables-actuarial-compensation-tables-for-injury-and-death)；本模块没有导入整套Ogden表、死亡率或当前司法折现率。

### 2.10 `counterfactual_damage`：给定反事实后的损害

\[
\text{毛多付款}=Q(P_{\text{实际}}-P_{\text{反事实}}),\quad
D=\text{毛多付款}-\text{转嫁额}+\text{销量减少的净利润损失}
\]

输入为 `quantity`、`actual_price`、`but_for_price`、`passed_on`、`volume_lost_profit`。例：购买10,000件，实际价120、反事实价100，毛多付款200,000；已转嫁50,000，销量损失净利润10,000，条件净损失160,000。

当前只支持实际价不低于反事实价的单期购买者过收费路径；转嫁金额不得超过毛多付款。反事实价格及销量利润损失由外部研究给定，程序不会自动用涨价事实推定违法因果关系。多期或多种商品须先统一口径并分别估计。参考 [欧委会2019/C 267/07指引，第8、15–16段及第5.1节](https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:52019XC0809(01))。

### 2.11 `hhi`：集中度与合并增量

\[
HHI=\sum_i s_i^2,\qquad \Delta HHI=2s_as_b,\qquad HHI_{\text{后}}=HHI_{\text{前}}+\Delta HHI
\]

`shares` 必须是0–100的百分数且合计100；`merger_index_a`、`merger_index_b` 为两个不同企业的数组索引，从0开始。例：`shares=[40,30,20,10]`，合并索引2、3即20%与10%的企业，合并前3000、增量400、合并后3400。

本版仅模拟两家企业合并且其他份额不变。先界定相关市场并统一份额期间和指标；错误的市场定义不能靠精确算术修复。模块不提供任何法域的集中度违法阈值、申报门槛或批准结论。参考 [CMA合并评估指引“Horizontal unilateral effects”的集中度段落及脚注79](https://www.gov.uk/government/publications/merger-assessment-guidelines/merger-assessment-guidelines-html-version)。

## 3. 一份公式定义，多个入口

[`legal_quant/models.json`](../legal_quant/models.json) 是公式的单一来源，包含：

- 模型编号、版本、分类、问题和输出类型；
- 输入字段、单位、范围、数组结构及跨字段约束；
- 有序输出及受限表达式树；
- 假设、限制、需另行判断的法律前提、来源编号；
- 明确标注为假设的示例输入。

Python与服务端JavaScript解释同一份定义。公式是受限的数据结构，不执行用户提供的Python或JavaScript表达式。修改公式后须同时检查两种运行时的结果一致性，避免网页与本地计算各有一套公式。

数值计算使用二进制浮点数。汉德模型以等价式 `NpL × (eₚ + eₗ − eₚeₗ)` 直接计算风险减少额，避免前后两个大数相减丢失极小效果。输出保留未舍入值；展示时才格式化。它不是任意精度的财务记账系统。

来源记录与公式分开维护。`verification=primary` 只说明已阅读该记录所指原始资料的相关部分；它不说明全文已审计、不说明模型是原作者逐字公式，更不说明香港适用性已核验。`web` 表示只核对了可访问转载或书目信息。具体范围写在每条来源的 `note`。

## 4. Python使用

在项目根目录运行：

```text
python -m legal_quant list
python -m legal_quant show hand
python -m legal_quant example hand --output case.json
python -m legal_quant evaluate --input case.json --output result.json
```

`example` 将包含模型编号、版本、输入和情景信息的完整请求以UTF-8保存为 `case.json`，省略 `--output` 时打印到终端。修改其中所需输入后运行 `evaluate`，即可得到同样可被REST及MCP消费的结构化结果。

Python调用入口：

```python
from legal_quant import evaluate

result = evaluate(
    "bayes",
    {"prior": 0.2, "likelihood_ratio": 8},
    context={
        "jurisdiction": "HK",
        "as_of": "2026-10-20",
        "input_basis": "hypothetical",
        "sources": {},
        "applicability": "unreviewed",
    },
    model_version="1",
)
```

## 5. 输入约定及校验

REST、MCP和CLI使用同一请求形状：

```json
{
  "model_id": "bayes",
  "model_version": "1",
  "inputs": {
    "prior": 0.2,
    "likelihood_ratio": 8
  },
  "context": {
    "jurisdiction": "HK",
    "as_of": "2026-10-20",
    "input_basis": "hypothetical",
    "sources": {},
    "applicability": "unreviewed"
  }
}
```

| 字段 | 作用 |
|---|---|
| `model_id` / `model_version` | 确定所用模型及版本；不支持的模型或版本应报错 |
| `inputs` | 该模型规定的完整数值或数组，不从缺失字段自动推定零 |
| `context.jurisdiction` | 记录拟分析的法域；不会加载或认证当地法律 |
| `context.as_of` | 记录分析基准日；缺省为未知，不推定“已核查现行法” |
| `context.input_basis` | `hypothetical`为假设；`case_data`为案件数据 |
| `context.sources` | 以顶层输入字段编号为键的非空证据或估计方法说明 |
| `context.applicability` | `unreviewed`或`externally_assessed`；后者仅记录调用者自述完成外部审查，不是程序认证 |

当 `input_basis="case_data"` 时，每个顶层输入必须有来源说明。例如 `prior` 应写明对应命题和先验方法；`cashflows` 应指明逐项计算表及证据；`alternatives` 应指明每个方案报价、损害估计和期间。来源字符串不是证据核验本身，程序不会把“填了来源”视作事实已被法院认定。

以下输入不能静默修复：

- 未知值、遗漏值或 `null`，不能当作0；如暂用假设值，应明确选用假设情景。
- 字符串 `"0.2"`、布尔值、非有限数字，不能冒充数值。
- 概率用0–1，HHI份额用0–100，折现率0.03表示3%；不能混用。
- 金额币种、价格基准、总价与单价、年度与单次概率不一致时，应先在外部统一。系统校验数值范围，但不会自动发现所有经济单位错误。
- 每个模型的跨字段约束仍须成立，如机会概率不得增加、HHI份额须合计100、除数不得为零。

## 6. 输出约定

| 字段 | 含义 |
|---|---|
| `model_id`、`model_version` | 本次实际使用的模型和版本 |
| `category`、`output_kind` | 输出的性质，例如金额、理论比值或条件事实概率 |
| `inputs` | 本次计算所用的完整输入，便于与结果一同保存 |
| `context` | 标准化后的分析背景、输入性质及来源说明 |
| `results` | 输出编号到计算值的映射 |
| `steps` | 有序的 `{id, label, unit, formula, value}` 计算步骤 |
| `assumptions`、`limitations` | 理解结果所需的前提和本版本范围 |
| `required_legal_findings` | 计算以外仍须解决的法律或证据问题 |
| `source_ids`、`legal_status` | 关联的来源编号及该模型的法律地位说明 |
| `legal_conclusion` | 始终为 `null`；没有通过计算自动作出法律结论 |
| `applicability_status` | 回显调用者所提供的适用审查状态 |

例如贝叶斯示例的数值部分为：

```json
{
  "results": {
    "denominator": 2.4000000000000004,
    "posterior": 0.6666666666666666
  },
  "legal_conclusion": null,
  "applicability_status": "unreviewed"
}
```

这是输出节选，完整输出还包括上表所列字段。计算使用浮点数；展示时可适当舍入，但需要保存原始值与输入。诸如 `0.30000000000000004` 的表示误差不应被误读为证据精度。`source_ids` 可解析到独立来源账本。

## 7. REST与MCP

| 入口 | 用途 |
|---|---|
| `GET /api/quant/models` | 读取模型目录、字段、公式、边界及示例 |
| `POST /api/quant/evaluate` | 提交第5节请求并计算 |
| MCP `list_quantitative_models` | 供连接器发现可用模型 |
| MCP `evaluate_quantitative_model` | 供连接器提交结构化请求 |

模型发现应先于模型调用。调用者根据 `question`、`output_kind` 和 `required_legal_findings` 选择模型，不应仅因法律问题出现“概率”二字就自动选择贝叶斯，也不应把所有模型的输出统一显示为百分制。

## 8. 当前范围与维护

这十一项是可重复的计算模块，不是完整法律专家系统。当前不提供案件结果训练、自动事实取证、多证据贝叶斯网络、经济计量反事实拟合、自动法域规则匹配或通用责任评分。

新增模型应先写清问题、法律地位、输入单位、证据需求、适用前提、公式、失败条件与输出解释，再放入模型目录；计算、来源核验和法律适用审查分别留痕。修改来源等级须有实际阅读证据，不能仅因链接存在或程序测试通过而升级。
