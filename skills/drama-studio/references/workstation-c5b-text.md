# C5b 正文

[工位契约](workstations.md) · 契约 v0.1 · 方法见 [台词层](dialogue-structure.md#5-写正文c5b照表写信息由对白承载重复须有处境理由)

| 项 | 内容 |
| --- | --- |
| 必读本剧依据 | 本集对话表（须通过 `contract-check dialogue-plan`）、本集分集计划、台词目标、前一集最新稿原文与入口状态记录（第 1 集的入口见 [整季分批 §1](workstation-season-run.md#1-开工前)）、必要的前文原场面、空间与物件 |
| 主要知识 | 只装对话表 `exemplars.positives` 引用过的正例（结构说明、骨架、遮蔽原句每条至多 1 句；装包时 `--exemplars` 给本集对话表），不装对照对、不另检索新样本；题材禁词表随包；少量精准 K1／K7 |
| 产出 | 完整剧本正文 `runs/<批>/ep-<NNN>.c5b.md`（台词与动作行；修订稿 `ep-<NNN>.c5b.r<n>.md`；保存为页面时 semantic 为 `episode`）；对照表 `runs/<批>/ep-<NNN>.plan-text-map.json`（schema `plan-text-map`，`contract-check plan-text-map` 核；`exchangeToLines`：每个交换落在正文哪几行，每段收尾行标 `closerOf`，逐字采用的人工句标 `verbatimFrom`）；偏离对话表之处逐条登记；状态变化提案（`stateChangeProposals[].ledgerDelta`，写进底账实际轨） |
| 交接 | `run-handoff`（`workstation: C5`，任务 `layer: C5b`，装包角色 `author`，任务引用 `dialogueTarget`）；事件或事实不对时提 `changeProposals`（`targetLayer: C4`）；要增删话题、改信息分配是同一工位内的变更：同一工位内（C5）的变更交接写不了 `changeProposals`（只能指向本工位之前的工位），写进 `unfinished`，并用 `decision add planning/decisions.json --entry <条目文件>` 登记（`kind: upstream_change`，带默认），由编排方开一次 C5a 运行 |

## 方法要点

- 照表逐话题写：说话人顺序、话题边界、打断位置、收尾都按对话表；节奏按每话题的处境与 `shape.reason` 写，参照正例的走法，不抄句。
- 措辞与 △ 行按 [语体与台词质感](voice-register.md) 写：先按题材定语体档，守住人物语言指纹，场尾停在钩上，高燃题材的 △ 行写成分镜；不按制作量删场面、降规模。
- 信息由对白承载；谁知道什么由 `listenerKnows` 定，不让人物向对方复述对方已知的事；重复要有处境里的理由（确认、强调、对方没听进去）。
- 篇幅装不下时不压缩台词，提 C4／C3c 变更。
- 最高优先是本剧原场面与已定的人物写法；外剧名场面默认不进主上下文。上下文里的材料是选择依据，不是待演清单。
- 新事实、关系转折、世界规则或跨集出口偏离分集计划时，登记为状态变化或上游变更提案，不静默写进正文。

## 停止与边界

不改对话表、不增删话题、不改事件。写完由 `plan-text-consistency <对照表> --dialogue-plan <对话表> --episode-plan <分集计划>` 核说话人序列与段边界，`dup-check --list-hits` 按 8 字档（装包样本）与 13 字档（全库）各列一次命中，`corpus lexicon` 扫题材禁词（命令写法见 [命令速查](dialogue-structure.md#12-命令速查)）；这些只核对齐与字面，不评台词好坏。核对过了先把这一稿存为页面修订（逐字核对见 [整季分批 §5](workstation-season-run.md#5-保存逐字核对)），C6 读的就是这份修订；修订稿另存为新修订。目标没达到就保留问题交给 C6，不靠补解释或无限迭代过关。修订先改对话表再改正文，见 [修订](dialogue-structure.md#8-修订先改表再改文修订单不写替换文字不写数值修订后复读)。修订预算用完后怎么办（含选了「再改一次」时另开一次运行），见 [修订预算按运行层解释](workstations.md#修订预算按运行层解释)。
