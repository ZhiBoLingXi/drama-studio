# C5a 对话设计

[工位通用协议](README.md) · 契约 v0.1 · 方法见 [台词层](../dialogue-structure.md#3-对话表话题交换listenerknowscarriescloseroneitemperline)

| 项 | 内容 |
| --- | --- |
| 必读本剧依据 | 本集分集计划（`infoLedger`、`events`、`presence`）、知识账导出（`ledger knows`，`listenerKnows` 的初值）、入口状态 `runs/state/after-ep-<前一集三位数>.md`（第 1 集没有前一集：前文一项装 `planning/ledger/ledger-ep000.json`，入口状态装 `ledger replay planning/ledger/ledger-ep000.json --at 0 --track actual --md` 导出的 `runs/state/after-ep-000.md`。）、台词目标 `planning/dialogue-target.json`、媒介档案 |
| 主要知识 | 按处境检索的语料正例与对照对（`dialogue-exchange`、`contrast-pair`）；K2、K5 只作人物索引，不是装包必需；没有本项目语料时照常进行，交接 `unknowns` 记“本次无样本” |
| 产出 | 对话表 `planning/dialogue/dialogue-plan-<NNN>.json`（schema `dialogue-plan`）：场 → 话题 → 段与交换；每话题的处境（`situation`）、由处境推出的走法（`shape` 与引用处境的 `reason`）、每个交换承载哪条信息（`carries`）、每段的收尾（`closer`）、引用的样本（`exemplars`）；不写措辞 |
| 交接 | `run-handoff`（`workstation: C5`，任务 `layer: C5a`，装包角色 `dialogue_designer`，任务引用 `dialogueTarget`）；某条信息没有对话对象、又没有独白理由，或装不下，提 `changeProposals` 给 C4／C3c，不自己凑 |

## 方法要点

- 装包前分集计划的 `capacity.status` 须为 `fits`，或为 `proposal:<id>` 且那条提案带默认；否则 `context-pack` 拒绝装包。
- 先把信息清单每条分给一个话题；分不下去的回 C4。每个话题先写处境（此刻想要什么、听的人已知什么、关系、双方情绪、观众要明白什么），再从处境推走法，再写一句理由，理由必须引用处境字段。
- 一个话题讲完再换下一个，一个人聊完才换对象：每段有 `closer`，切换前先收尾。
- `listenerKnows` 的初值由 `ledger knows <入口修订> --episode-plan <分集计划>` 按场、按人导出（单查一人用 `--who <人> --at <集>`），只能收窄，不能与知识账相反；说话人 `carries` 的事实在账里他此前要“知道”。
- 样本按处境检索，每个话题最多两条正例、一条对照对，原句遮蔽后进包，见 [样本怎么用](../dialogue-structure.md#4-样本怎么用处境检索遮蔽每话题上限verbatimfrom)；样本是选走法的依据，不是待抄的句子。本剧编剧的原句可以逐字用，标 `verbatimFrom`；语料原句永不逐字。
- 不写任何句数、字数、换人数目标；节奏由处境推出。

## 停止与边界

不改事件与事实（C4）、不写台词措辞（C5b）。交接条件：信息清单每条有承载的交换或登记了画面承载理由；每话题处境字段齐、理由非空；每次切换前有收尾。`dialogue-plan-check <对话表> --episode-plan <分集计划> --knows <按场的 ledger knows 导出>` 与 `contract-check dialogue-plan` 核结构项，不评走法好坏。`task.revisionBudget` 算对话表的修订次数，默认 1；触顶后的处理见 [返修上限按层解释](README.md#返修上限按层解释)；决定队列的默认是“按现稿交付”时不再改；主创或默认选了“再改一次”时，由编排方开一次新的 C5a 运行，这次修订另计预算 1 次，交接的 `decisionRefs[]` 写该决定的队列 id（`contract-check run-handoff <交接> --decisions planning/decisions.json` 核它存在）。本层提给 C4 的变更按默认要改分集计划时，由编排方开一次 C4 运行去改，不在本层改。
