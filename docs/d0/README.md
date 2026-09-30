# D0 执行记录（2026-09-29）

依据：[实施路线 v1.1](../design/drama-studio-implementation-roadmap-2026-09-29.md) §3 D0、[系统架构 v1.1](../design/drama-studio-system-architecture-2026-09-29.md)。本目录是证据记录，不是新的设计文档。

## 结论

D0 的本地交付已完成。线上能力发现：2026-09-29 本宿主未连接；**2026-09-30 已连接并鉴权成功，但线上部署没有候选相关路由**（见能力发现）。按路线 §8 的前置阻塞规则，首批仍停在 D0，不改为本地版本库。

| D0 交付 | 状态 | 证据 |
| --- | --- | --- |
| 基线回执 | 完成 | [baseline.md](baseline.md) |
| 线上能力发现（只读） | 完成，结论：已连接、可读；候选接口未部署 | [capability-discovery.md](capability-discovery.md) |
| 公共对象 JSON Schema＋正反测试 | 完成 | `skills/drama-studio/schemas/`（6 个）、`tests/test_contracts.py`、`skills/drama-studio/schemas/examples/` |
| 六工位薄契约 | 完成（v0.1，实验性） | `skills/drama-studio/references/workstations/` |
| S／R／M 层级标注 | 完成 | [工位契约 · 执行层级](../../skills/drama-studio/references/workstations/README.md) |
| 首轮目标、样例划分、来源与权限清单 | 完成（2026-09-30 已确认；保留题暂无） | [first-round.md](first-round.md) |
| 旧任务表写回取消／收窄 | 完成 | R1、R2、R5、R6 任务表下方的 v1.1 注记 |

## D1 进入条件核对

| 条件 | 结果 |
| --- | --- |
| Schema 测试通过 | 是：`python3 -B -m unittest discover -s tests -v` |
| 每个对象有生产者与消费者 | 是：见下表 |
| 事实、计划、候选、采用可区分 | 是：`context-snapshot.partition`、`task.status.adoption`、`remote-receipt` 分开表达 |
| 候选保存／回读在获准测试项目上可用 | **本地部署：是**（REST 层 7 项检查全部符合预期，见能力发现）；**生产：否**（v0.18.0 部署因 GitHub 账单未启动）；MCP 工具层待验证 |

| 对象 | 生产者 | 消费者 |
| --- | --- | --- |
| task | 任务与依赖协调（宿主按用户消息填写） | 各工位、上下文构建器 |
| knowledge-card | 知识编辑（D1） | 上下文构建器 |
| context-snapshot | 上下文构建器（D1 装包工具） | 工位运行、审读、恢复 |
| run-handoff | C1–C6 工位运行 | 协调、下游工位、C6 |
| review-record | C6 | 协调、返修工位 |
| remote-receipt | mali-story 适配（D1） | 恢复与对账 |

## 解除阻塞需要

1. ~~连接 mali-story MCP 并授权~~（2026-09-30 已完成）。
2. 部署含候选服务（StoryArtifactService、WritingContextService）的 mali-story 版本，或确认可用的替代接口。
3. 指定一个允许写入候选的测试项目（不用《镇渊君》正式项目）。
4. 重新执行 [capability-discovery.md](capability-discovery.md) 的检查清单并把结果追加到该文件。
