# C5b 正文

[工位通用协议](README.md) · 契约 v0.1 · 方法见 [台词层](../dialogue-structure.md#5-写正文c5b照表写信息由对白承载重复须有处境理由)

| 项 | 内容 |
| --- | --- |
| 必读本剧依据 | 本集对话表（须通过 `contract-check dialogue-plan`）、本集分集计划、台词目标、前一集最新稿原文与入口状态（第 1 集没有前一集：前文一项装 `planning/ledger/ledger-ep000.json`，入口状态装 `ledger replay planning/ledger/ledger-ep000.json --at 0 --track actual --md` 导出的 `runs/state/after-ep-000.md`。）、必要的前文原场面、空间与物件 |
| 主要知识 | 只装对话表 `exemplars.positives` 引用过的正例（结构说明、骨架、遮蔽原句每条至多 1 句），不装对照对、不另检索新样本；题材禁词表随包；少量精准 K1／K7 |
| 产出 | 完整剧本正文 `runs/<批>/ep-<NNN>.c5b.md`（台词与动作行，kind：`episode_draft`）；对照表（schema `plan-text-map`，`contract-check plan-text-map` 核；`exchangeToLines`：每个交换落在正文哪几行，每段收尾行标 `closerOf`，逐字采用的人工句标 `verbatimFrom`）；偏离对话表之处逐条登记；状态变化提案（`stateChangeProposals[].ledgerDelta`，写进底账实际轨） |
| 交接 | `run-handoff`（`workstation: C5`，任务 `layer: C5b`，装包角色 `author`，任务引用 `dialogueTarget`）；要增删话题、改信息分配时提 `changeProposals` 给 C5a，事件或事实不对给 C4 |

## 方法要点

- 照表逐话题写：说话人顺序、话题边界、打断位置、收尾都按对话表；节奏按每话题的处境与 `shape.reason` 写，参照正例的走法，不抄句。
- 信息由对白承载；谁知道什么由 `listenerKnows` 定，不让人物向对方复述对方已知的事；重复要有处境里的理由（确认、强调、对方没听进去）。
- 篇幅装不下时不压缩台词，提 C4／C3c 变更。
- 最高优先是本剧原场面与已定的人物写法；外剧名场面默认不进主上下文。上下文里的材料是选择依据，不是待演清单。
- 新事实、关系转折、世界规则或跨集出口偏离分集计划时，登记为状态变化或上游变更提案，不静默写进正文。

## 停止与边界

不改对话表、不增删话题、不改事件。写完由 `plan-text-consistency <对照表> --dialogue-plan <对话表> --episode-plan <分集计划>` 核说话人序列与段边界，`dup-check --list-hits` 按 8 字档（装包样本）与 13 字档（全库）各列一次命中，`corpus lexicon` 扫题材禁词；这些只核对齐与字面，不评台词好坏。目标没达到就保留问题交给 C6，不靠补解释或无限迭代过关。修订先改对话表再改正文，见 [修订](../dialogue-structure.md#8-修订先改表再改文修订单不写替换文字不写数值修订后复读)。返修预算用完后的处理见 [返修上限按层解释](README.md#返修上限按层解释)；选了“再改一次”时，由编排方另开一次 C5b 运行，另计预算 1 次，交接的 `decisionRefs[]` 写该决定的队列 id（`contract-check run-handoff <交接> --decisions planning/decisions.json` 核它存在）。
