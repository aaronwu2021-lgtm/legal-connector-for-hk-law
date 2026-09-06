# OpenCode task 04b：隔离的完整构建与一致性检查

仅在 04a 已被 Codex 验收且本任务被明确分派后执行。使用已选定的 Muse Spark 1.3 Free，不切换付费模型。先读 `CLAUDE.md`。保留现有工作；不改法律正文、authority、verification、日期、tier 分配、实验答案或验证豁免。禁止网络、模型运行、服务、commit、push、部署。

## 范围与边界

允许新增 `scripts/check_build.py`、`scripts/tests/test_build_reproducibility.py`，并为以下要求修改 `scripts/_paths.py`、core `build_*.py`、`apply_tiers.py`、`check_persuasive.py`。可以对 experiment 2 `build_probe.py` 做下述 UTF-8/路径修复。保留 04a 测试；不再扩大 API 或实验 schema 的范围。

**原仓库中所有生成数据与实验 artefact 必须保持原样。所有目标 builder 的执行或导入，只能发生在经检查的独立临时副本。** 正常运行新的非写入检查器可以创建临时副本，但不得把任何构建产物复制回原仓库。现有构建漂移或来源缺失必须报告，不能通过更新产物或改法律数据消除红灯。

## 实现要求

1. 新检查器 `python -B scripts/check_build.py` 默认只做检查；`--help` 不读数据、不创建副本。从当前工作区复制所需源码和本地输入，包含当前未提交、未追踪的必要 source snapshots；不能只用 `git archive HEAD`。排除 `.git`、依赖、缓存和凭据，不使用链接副本。检查解析后的所有执行/输出路径在临时副本内且不在原仓库内。
2. 子进程使用副本内 cwd、`-B`、`PYTHONUTF8=1`，清除继承的 `PYTHONPATH`，并禁止联网。路径来自副本脚本的 `__file__`。不要执行抓取器、模型 runner、judge、服务器或部署脚本。
3. 改进 `_paths.emit`：在打开最终路径前完成两种表示的序列化，避免序列化失败截断旧文件。可先写 sibling 临时文件再替换；如这样实现，明确两个文件的替换不是跨文件事务。失败必须非零且可检测，不宣称全构建原子性。
4. `apply_tiers` 先计算并验证 scored 和 registry 两份结果，再发布。缺少 tier 时非零失败，不能输出部分数据却标成完整。不得将已有 `regression` 权重静默覆盖为 doctrinal tier；不支持该表示时明确失败。本轮不能改变当前的 tier、权重或规则。
5. 修复 persuasive 构建中 `stats.signals` 遍历 set 的顺序不确定性，采用稳定键顺序。保留 case/edge 原有顺序及固定 source dates，不用当前时间替换它们，不通过全面格式化掩盖差异。
6. 对全部 authority occurrence 检查 provenance，不只检查经过 `A()` 创建的记录：primary/quoted 需 pin，quoted 需明确 quoting source；同时覆盖手写的 jurisdiction overlay，报告具体数据路径。当前 HK overlay 的 Long Year 有 quoted 等级和 pin、但无结构化 source；另一条同案记录有 source 不能自动补足此条。此类已存在问题必须报告并使完整 integrity 状态失败，不补写、不降级、不升级。统计须说明遍历范围，不据此推断 README 的另一口径总数错误。
7. experiment 2 helper 的原始定义、错误旧 key 及归档角色保持不变。仅将输出路径锚定 helper 所在目录，显式使用 UTF-8/LF。它只在可选实验检查组的副本中运行；绝不覆盖原仓库历史 probe 文件。若归档数据本已不等价，报告差异，不“修正”旧结果。

## 有序构建

在副本中按以下顺序逐个运行；任一步失败即报告该阶段，不继续产生全绿结论：

```text
python -B scripts/build_elements.py
python -B scripts/build_registry.py
python -B scripts/build_scored.py
python -B scripts/apply_tiers.py
python -B scripts/build_maintenance.py
python -B scripts/build_persuasive.py
python -B scripts/check_persuasive.py
```

core 之间没有 builder import 依赖：tiers 读取 scored/registry，maintenance 读取 elements/registry/scored，persuasive 独立读取四个本地 source snapshots。不要把中间的 scored/registry 与最终 published 数据比较；先完成 tiers。

对 elements、registry、scored、maintenance、persuasive 五对输出：直接解析 JSON，以及 MJS 的固定 `export default <JSON>;` 表示，不执行 API handler；要求两者数据一致。分别报告与原仓库快照的语义差异、序列化差异，以及 provenance 检查结果。已知 provenance 失败不影响单独报告 deterministic-build 成功，但完整检查不能返回“全部通过”。

第二次完整运行要求最终字节完全一致。再用两个全新副本和 `PYTHONHASHSEED=1/2` 验证最终字节一致。保留输入快照哈希及输出比较结果，不能用刚生成的文件自动重设 baseline。

实验任务/checklist 再生与 validator 属于显式可选检查组。experiment 4 目前字段 schema 不一致；普通验证失败必须保持可见，不能削弱 validator、跳过后报全绿，或修改 keys。它与 core 构建状态分开报告。

## 隔离验收

新增标准库测试；复用 04a 的副本路径守卫，测试 discovery 阶段不导入 builders。测试至少覆盖：

- 原仓库所有受保护 artefact 的路径清单和哈希前后一致；所有目标模块 `__file__`、执行路径、输出路径均在副本内；无网络。
- 正常有序构建、五对 JSON/MJS 相等、tiers 后 band 保留、第二次构建字节一致、不同 hash seed 字节一致。
- 在另一个空 cwd 用绝对副本脚本路径执行，输出仍只落入副本；包括修复后的 experiment 2 helper。
- 副本中注入序列化失败、缺失 tier、缺失 persuasive source；返回非零、不报成功，不截断或替换无关结果。若模拟第二个输出发布失败，必须能报告/检测不一致，不能声称跨文件事务已保证。
- 用合成记录检查手写 overlay 缺 source、primary 缺 pin、同案其他记录有 source 等情况；准确报告，不能借同案匹配自动修复。
- 现有 provenance 缺口、归档漂移、experiment 4 schema 失败：分别报告真实结果。测试可以断言错误被正确报告；检查器本身不能把这些错误算作成功。
- 所有 04a help/import/未知参数无副作用测试继续通过；新增检查器也须满足其 help/import约束。

确认所有目标执行已隔离后，可从原仓库运行测试 harness：

```text
python -B -m unittest discover -s scripts/tests -p "test_builder_entrypoints.py" -v
python -B -m unittest discover -s scripts/tests -p "test_build_reproducibility.py" -v
```

报告修改文件、完整 core 构建结果、重复与 hash-seed 比较、provenance/可选实验组结果和原仓库不变证据。不得为获取绿灯修改现有生成数据。完成后停下交给 Codex 验收。
