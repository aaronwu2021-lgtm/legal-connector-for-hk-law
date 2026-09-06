# 2026-09-06 法律可靠性复核与外部签核包

本轮已完成可由代码、公开一手来源和本地验证完成的修订。实验 3 与实验
4 的答案标准仍未获得项目之外的合资格香港法律审阅人逐项签署，因此本页
不把它们描述为“已完成独立法律审阅”或“正式实验就绪”。

## 当前状态

| 项目 | 当前结果 |
|---|---|
| 核心法律数据来源结构 | 构建审计未发现缺少 pin/source 的已核验记录；重复构建一致 |
| 实验 3 | 5 个任务、31 条标准；本地目录、pin 和截止日期检查全部通过；独立签核待定 |
| 实验 4 | 3 个任务、13 条标准；每个来源分别完成身份、日期、locator 和短句检查；独立签核待定 |
| 正式模型实验 | 未运行；没有新增模型成绩或统计结论 |
| 冻结审阅对象 | 由 `legal-reliability-review-manifest-2026-09-06.json` 及其 `.sha256` 文件绑定；签署结果另存并另算哈希 |

## 本轮修订的法律内容

1. **香港成文法来源。** 《失实陈述条例》(Cap. 284) 现在记录官方现行
   XML 的版本日期和 ss. 2、3(1)–(2)、4；Cap. 71 与 Cap. 458 分别记录
   具体条文、官方链接和司法适用来源。法条文字与 *Chang Pui Yin* 对私人
   银行条款的适用已分开，不再把判例结论写成法条原文。
2. **Long Year。** 名称已统一为 *Long Year Development*。现有资料只能
   通过后来的香港判决核对其被引段落，因此维持 `verified-quoted`，明确写出
   *Wong Yuk Lan* [90] 与 *Joytex* [152] 的转引来源；没有把未读到的 1991
   报告冒充 `verified-primary`。关于“香港最稳定”或不存在相反权威的过度
   表述已经删除。
3. **San-Hot 与 Sit Pan Jit。** 两案已使用不同的正确中立引证、判决日期
   和段落。*San-Hot* 对 contractual estoppel 的讨论被限定为法院认可该原则，
   但在其事实裁断上并非必要；*Sit Pan Jit* 则记录为对当事人合同的适用，
   并与法定合理性审查分开。
4. **实验 3 的历史任务。** 2015 任务使用精确截止日 2015-12-01，不再预设
   银行条款“很可能有效”，并明确排除把 2017、2018、2021 年判决用于 2015
   法律意见。验证器按完整中立引证、完整判决日期、pin 和显式正反向检查。
5. **C v D。** 2022 年上诉法院实体裁判、2022 年终审上诉许可决定、2023
   年终审实体裁判及 Cap. 609 ss. 34、81 均为独立来源。Art 16(3) 的初步
   裁定途径与 Art 34 的撤销裁决途径已直接绑定法例文本。2023 标准区分
   Ribeiro PJ 的多数理由与 Gummow NPJ 的不同理由，并补入 Cheung CJ
   [10]–[11] 和 Lam PJ [103]–[104]。
6. **Eton 来源层次。** [2020] HKCFA 32 是实体判决，[2024] HKCFI 1291
   是损害评估，[2026] HKCFA 30 是其后拒绝许可上诉的理由。答案标准现在
   直接使用 2020 [122]、[126]–[128] 和 2024 [18]，并把 2026 [12]、[14]
   明确标作对早期裁判的回顾或转引。救济范围同时保留“落实终局裁决”和
   “受裁决范围限制”的边界。标准也已明确：成文法判决本身不阻止把普通法
   赔偿作为替代请求提出，但当事人不能同时保有不相容的最终救济；“18 年”
   只描述量化程序距裁决的时间，不再误写成新论点提出的时间。

## 一手来源

- [香港电子版法例的核证法例说明及 Cap. 609 记录](https://www.elegislation.gov.hk/verifiedlist)
- [司法部现行法例开放数据集](https://data.gov.hk/en-data/dataset/hk-doj-hkel-legislation-current)
- [C v D [2022] HKCA 729](https://www.hklii.hk/api/getjudgment?lang=en&abbr=hkca&year=2022&num=729)
- [C v D [2022] HKCFA 25](https://www.hklii.hk/api/getjudgment?lang=en&abbr=hkcfa&year=2022&num=25)
- [C v D [2023] HKCFA 16](https://www.hklii.hk/api/getjudgment?lang=en&abbr=hkcfa&year=2023&num=16)
- [Eton [2020] HKCFA 32](https://www.hklii.hk/api/getjudgment?lang=en&abbr=hkcfa&year=2020&num=32)
- [廈門新景地 [2024] HKCFI 1291](https://www.hklii.hk/api/getjudgment?lang=en&abbr=hkcfi&year=2024&num=1291)
- [Eton [2026] HKCFA 30](https://www.hklii.hk/api/getjudgment?lang=en&abbr=hkcfa&year=2026&num=30)

## 本地验证记录

- 核心构建审计：`overall_ok: true`，来源结构问题为 0，所有五组数据与服务
  模块重复构建一致。
- Python 整库测试：135 项通过。
- 实验 4 独立验证工具测试：29 项通过，包括 Unicode 当事人名称、跨来源
  短句借用、严格来源日期、法例引用结构、路径别名、硬链接复用、相似文件名
  区分和待签状态。
- Node 接口及页面测试：243 项通过。
- 实验 4 的完整 readiness 命令仍返回非零；报告同时显示
  `schema_valid: true`、`source_verification: checked`、0 个本地来源问题，
  原因仅是 `independent_review: pending` 和
  `proposition_verification: not-performed`。这是预定的真实性门槛。

## 明确保留的限制

- *Long Year* 的 1991 报告原文仍未取得；只对后来一手判决实际转引的段落
  使用 `verified-quoted`。
- [2020] HKCFA 32 与 [2024] HKCFI 1291 的原始上传日期未另外证实；记录以
  判决日期作为 availability proxy。两者均远早于 2026-09-06 截止日。
- 本轮不声称穷尽所有相反或后续权威。维护数据仍如实报告未有在库权威的
  节点；这需要持续研究，不能由短句匹配自动补全。
- 哈希能证明外部审阅人看到的内容没有变化，不能证明法律判断正确、来源
  真实或审阅人独立。
- manifest 的 9 条“任务—来源”关联全部属于实验 4，共绑定 7 份不同的本地
  短摘录；它们不是完整、经认证的官方原文。实验 3 的引证和 pin 已通过任务、
  标准和清单哈希冻结，但没有另列原文来源记录；审阅人必须自行读取官方原文
  并在签署结果中记录来源身份、取得信息和哈希。

## 外部签核

外部审阅人应按照 `independent-legal-review-protocol.md`，把实验 3 和实验
4 的生成清单作为只读空白模板，另存一份不属于冻结输入的完成答复。答复须
对全部 44 条标准逐项选择结论，记录理由、回避决定、实际 UTC 时间、签名或
可追踪批准记录，并引用原 manifest SHA-256 及相应标准哈希。完成答复另算
SHA-256；它是审阅输出，不会反过来令所签 manifest 失效。签核人必须没有
参与本库、案卷、构建器或答案标准的编写，资格核验与利益冲突评估均须完成。
任何相关任务事实、命题、截止日、来源或 locator 改变后，才须建立新 manifest
版本并复审受影响部分。
