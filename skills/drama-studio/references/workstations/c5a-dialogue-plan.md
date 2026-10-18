# C5a 对话设计

[工位契约](README.md) · 契约 v0.1 · 方法见 [台词层](../dialogue-structure.md#3-对话表话题交换listenerknowscarriescloseroneitemperline)

| 项 | 内容 |
| --- | --- |
| 必读本剧依据 | 本集分集计划（`infoLedger`、`events`、`presence`）、按场的知识账导出（`listenerKnows` 的初值，见下文）、前一集的入口状态记录 `runs/state/after-ep-<NNN>.md`（第 1 集的入口见 [整季分批 §1](season-run.md#1-开工前)）、台词目标 `planning/dialogue-target.json`、媒介档案 |
| 主要知识 | 按处境检索的语料正例与对照对（`dialogue-exchange`、`contrast-pair`）；K2、K5 只作人物索引，不是装包必需；没有本项目语料时照常进行，交接 `unknowns` 记“本次无样本” |
| 产出 | 对话表 `planning/dialogue/dialogue-plan-<NNN>.json`（schema `dialogue-plan`）：场 → 话题 → 段与交换；每话题的处境（`situation`）、由处境推出的走法（`shape` 与引用处境的 `reason`）、每个交换承载哪条信息（`carries`）、每段的收尾（`closer`）、引用的样本（`exemplars`）；不写措辞 |
| 交接 | `run-handoff`（`workstation: C5`，任务 `layer: C5a`，装包角色 `dialogue_designer`，任务引用 `dialogueTarget`）；某条信息没有对话对象、又没有独白理由，或装不下，提 `changeProposals`（`targetLayer: C4`，或 `C3` 并在正文写明 C3c），不自己凑 |

## 方法要点

- 装包前分集计划的 `capacity.status` 须为 `fits`，或为 `proposal:<id>` 且那条提案带默认；否则 `context-pack` 拒绝装包。
- 先把信息清单每条分给一个话题；分不下去的回 C4。按容量提案的默认拆到后段的信息，在对话表的 `infoLedger` 条目里写 `deferredTo: <容量提案 id>`，不写 `carriedBy`。每个话题先写处境（此刻想要什么、听的人已知什么、关系、双方情绪、观众要明白什么），再从处境推走法，再写一句理由，理由必须引用处境字段。
- 一个话题讲完再换下一个，一个人聊完才换对象：每段有 `closer`，切换前先收尾。
- `listenerKnows` 的初值由 `ledger knows <入口底账修订> --episode-plan <分集计划> > .drama/checks/knows-ep<NNN>.json` 按场、按人导出（单查一人用 `--who <人> --at <集>`，那种输出不能给 `dialogue-plan-check`），只能收窄，不能与知识账相反；说话人 `carries` 的事实在账里他此前要“知道”。
- 样本按处境检索：装包时 `context-pack <项目> --task <task.json> --selection <selection.json> --role dialogue_designer --budget <字数> --annotations-only --exemplars <已标注、过了 corpus filter 的交换.jsonl>`（工作室语料另加 `--studio-corpus <工作室根>/corpus/`）。这时还没有对话表，必须加 `--annotations-only`（不加退出 1），工具只装标注字段（处境、结构说明、骨架），不装原句；非 dry-run 时另写一份视图 `.drama/packs/annotations/<sha>.jsonl`。选定后由作者把遮蔽句写进对话表 `exemplars.positives`，每个话题最多两条正例、一条对照对，见 [样本怎么用](../dialogue-structure.md#4-样本怎么用处境检索遮蔽每话题上限verbatimfrom)；样本是选走法的依据，不是待抄的句子。本剧编剧的原句可以逐字用，标 `verbatimFrom`；语料原句永不逐字。
- 不写任何句数、字数、换人数目标；节奏由处境推出。

## 停止与边界

不改事件与事实（C4）、不写台词措辞（C5b）。放行条件：信息清单每条有承载的交换或登记了画面承载理由；每话题处境字段齐、理由非空；每次切换前有收尾。`dialogue-plan-check <对话表> --episode-plan <分集计划> --knows .drama/checks/knows-ep<NNN>.json` 与 `contract-check dialogue-plan` 核结构项，不评走法好坏。修订预算算对话表的修订次数，默认 1；本层提给 C4 的变更按默认要改分集计划时，由编排方开一次 C4 运行去改，不在本层改。修订预算用完后怎么办（含选了「再改一次」时另开一次运行），见 [修订预算按运行层解释](README.md#修订预算按运行层解释)。
