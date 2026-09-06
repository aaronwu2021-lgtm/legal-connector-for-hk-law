# OpenCode task 04a：入口安全，不运行实际构建

状态：免费模型挂起后由 Codex 实现，原 57 项隔离入口测试通过；04b 加入检查器后扩为 61 项。完整验收记录见 `task04b-acceptance-2026-09-05.md`。下文保留原分派规格。

仅在 Codex 明确分派后执行。使用已选定的 Muse Spark 1.3 Free，不切换付费模型。先读 `CLAUDE.md`。保留现有未提交修改、API、测试和独立审计材料。本任务只重构入口并增加安全测试；完成后停下交给 Codex 验收，不能自行继续 04b。

## 范围

允许修改以下入口的参数处理、主程序包裹与有副作用的顶层调用位置，保留源数据对象、正文、数值和正常运行语义：

- `scripts/build_elements.py`、`build_registry.py`、`build_scored.py`、`build_maintenance.py`、`build_persuasive.py`、`apply_tiers.py`、`check_persuasive.py`。
- `experiments/exp3-hk-matter/` 与 `experiments/exp4-cfa/` 各自的 `build_tasks.py`、`build_reader_checklist.py`、`validate_tasks.py`。
- `experiments/exp2-probe/build_probe.py`：本轮仅包裹入口、处理参数；其 UTF-8、路径及归档输出检查留给 04b。
- 可新增 `scripts/tests/test_builder_entrypoints.py`。`scripts/_paths.py` 是测试依赖，本轮不改其输出逻辑。

禁止修改所有生成数据、实验任务、matter、reader checklist、模型回答、评分及法源验证等级。禁止网络、服务、commit、push、部署。**禁止执行或导入原仓库的 builder，包括 `--help`；禁止运行任何完整构建。** 所有目标入口的 import/help/错误参数测试必须在独立临时副本中完成。

## 已知原因与最小修改

`build_elements/registry/scored/maintenance` 在模块顶层写文件；`apply_tiers` 顶层重写两个数据集；experiment 2 helper 顶层写入当前目录。其他 builder 虽有 main guard，却没有参数解析，`--help` 仍会运行。`check_persuasive` 导入即读数据、输出并可能退出。experiment 3 validator 将 `--help` 当文件名，experiment 4 validator 忽略参数。

1. 每个入口使用 `main(argv=None)`、`argparse` 和 `if __name__ == '__main__': raise SystemExit(main())`。先解析参数，再读数据或做任何构建工作。`--help`/`-h` 返回 0；未知选项返回非零 usage 错误，均不得创建或改写文件。
2. 将读取数据、执行构建、调用 `emit/apply`、生成摘要、打印和 `sys.exit` 移入显式运行路径。保留纯函数及数据定义；导入不读取数据、不生成输出、不打印、不退出。不要借此次包裹重新整理法律内容、改权重、改验证豁免或重新格式化整个文件。
3. 保留现有无参数命令的用途，以及 experiment 3 validator 的可选 positional tasks-path。`build_scored.py` 仍是产生中间数据的入口；本轮不把它改成完整构建器。
4. 实际交叉依赖仅为：core builders/tiers 使用 `_paths`；maintenance 读取 elements/registry/scored；两个 reader builder 使用各自 sibling `validate_tasks.match/norm`。不要为了取得常量新增 builder 互相导入。测试用独立子进程避免两个同名 `validate_tasks` 的缓存混用。
5. 不修 `emit` 原子性、tier 处理、确定性排序、provenance 或 experiment 4 的旧 schema。它们属于 04b 或后续实验任务。experiment 4 的正常校验失败不得被改成成功；本轮只要求 help/import 安全。

## 隔离测试与验收

测试模块发现阶段不得导入任何目标 builder。只用标准库。每个目标在新子进程和独立普通文件副本中测试，不用 symlink、junction、hardlink，也不导入原仓库模块。

启动子进程前检查：解析后的目标脚本、依赖、输出路径均位于临时副本内且不在原仓库内；清除继承的 `PYTHONPATH`；仅添加副本的 sibling 路径；启用 `-B`、`PYTHONUTF8=1`。验证目标模块及目标依赖的 `__file__` 均属于副本。禁止子进程联网。

对上述全部 14 个入口分别执行以下测试，另覆盖 `_paths` 的 import：

- **help**：在没有生成数据的副本中执行 `--help` 和 `-h`；退出 0、有 usage；不能读所需数据、不能新增路径，既有文件字节和 mtime 不变。
- **未知参数**：执行 `--definitely-unsupported-option`；非零 usage 错误，同样不读数据、不写文件。把参数当成文件路径打开不算通过。
- **import**：仅导入副本中的目标，不调用 `main()`；没有 stdout/stderr、`SystemExit`、数据读取或文件写入。可用审计钩子限制数据/输出路径的访问，同时允许读取 Python 源码；禁用 pyc。不能靠恰好没有输入而让导入失败来“防止写入”。
- **原仓库不变**：测试前后比较原仓库生成数据和实验 artefact 的路径清单与哈希；必须完全一致。

完成隔离实现并确认测试代码未在 discovery 阶段执行目标后，可从原仓库运行的唯一验收入口为：

```text
python -B -m unittest discover -s scripts/tests -p "test_builder_entrypoints.py" -v
```

本轮不运行任何 builder 的正常无参数路径，哪怕在副本中；不运行 validators 的正常检查，也不运行 04b。报告修改文件、14 个入口的矩阵结果和原仓库 artefact 哈希一致性。不能宣称完整构建已通过；正常运行等价性由 04b 验证。
