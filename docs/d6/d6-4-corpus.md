# D6-4 语料取用记录

依据：[统一实施计划](../design/drama-studio-outline-dialogue-implementation-plan-2026-10-14.md) §4.5；[D6-4 共用决定](d6-4-decisions.md) §1。日期 2026-10-15。

本页只有调用次数、预算读数、回执 ID 与待办，不含任何语料台词、剧名或项目内容。

## 结论

D6-4 没有做远端取用：本阶段 mali-story 连接超时，计费确认做不了。按计划 §4.5 退出条件，D6-4 以现有小样本（D6-0 阶段 A 的语料缓存，3 部）结束，全库列为待办。`corpus fetch` 只在编造的台账上跑过（`run.py` 的 d64 段）。

## 一、调用次数

D6-4 本身：远端调用 0 次。

现有小样本是 D6-0 阶段 A 取的，数字抄自项目里语料缓存的 `manifest.json`（`readCalls`）：

| 工具 | 次数 | 失败 |
| --- | --- | --- |
| `search_deconstruction_templates` | 1 | 0 |
| `get_deconstruction_evidence` | 3 | 2（v1 模板返回 404） |
| `get_deconstruction_template` | 5 | 1（整部响应过大，未重试） |
| `get_shared_creation_budget` | 1 | 0 |
| `list_shared_creation_budget_receipts` | 1 | 0 |
| 合计 | 11 | 3 |

小样本规模：3 部用于标注（直人 2 部 32 集、漫剧 1 部 8 集），138 条交换，其中 40 条有双跑标注。

## 二、预算读数

| 时点 | budgetMode | availableCredits |
| --- | --- | --- |
| D6-0 取用后 | `unconfigured` | `null` |
| D6-4 | 未读（无连接） | — |

只有一次读数，而且不可比。按 `corpus fetch verify` 的判法是 `unconfirmed`：看不出扣费，也不能证明没扣。

## 三、回执 ID

无。`list_shared_creation_budget_receipts` 返回空列表。

## 四、待办

1. **全库取用。**先用 `corpus fetch plan` 建台账（3 部各 10 集），取用前后各读一次预算与回执（`corpus fetch budget --label before|after`）。`corpus fetch verify` 为 `no_change_seen` 后才扩到全库（估计约 695 次读取调用）；为 `deduction_seen` 或有快照不符就停下记录。
2. **补语料。**补三类现实题材缺口：险情处置、孩子指挥大人、偷偷示好。补完后重跑 `corpus defaults`；仍是 not_evaluable 的那张题材禁词表（霸总／都市言情）也要补对应题材。
3. **计费确认。**要在有预算配置（`budgetMode` 不是 `unconfigured`）的账户上读到可比的前后读数，并核对回执。确认前，本页的计费结论都是「未确认」。
