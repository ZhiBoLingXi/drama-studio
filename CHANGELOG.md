# 更新记录

技能 `skills/drama-studio/` 与随包工具的变化，按版本倒序。写法参照 Keep a Changelog，分「新增／变更／退役／修正」。只记技能与工具本身，不记任何项目的剧情、人物或台词。各阶段的验收证据见 [docs/d6/](docs/d6/README.md)。

## 0.7.1 — 2026-10-15（工作室级语料缓存）

### 变更

- 语料缓存可以放工作室级：默认 `<工作室根>/corpus/`，几个项目共用一份；项目内的 `corpus/` 仍可用。工作室级的 `dialogue-exchange`、`corpus-manifest` 写 `scope.level: studio`。知识卡规则不动；对照对、编剧批注、本项目反例与人工正例仍只允许项目级。依据：主创 2026-10-15 确认实施计划 §8 #1（原话「语料缓存能放工作室级」），[系统架构 v1.3](docs/design/drama-studio-system-architecture-2026-09-29.md) §8.5 已改为条款；方法见 [`references/corpus.md`](skills/drama-studio/references/corpus.md)。

## 0.7.0 — 2026-10-15（D6-4，#81）

语料库与人工反馈回流。本阶段没有 mali-story 连接，全库取用与计费确认列为待办，以现有小样本（3 部）结束，见 [D6-4 报告](docs/d6/d6-4-report.md)。

### 新增

- `corpus fetch {plan|record|budget|resume|verify}`：语料取用记账，不联网。代理调用 mali-story 工具、存下每次返回；脚本列取用计划（默认 3 部、每部 10 集）、记每次调用与快照核对（`match`／`snapshot_mismatch`／`not_evaluable`）、记预算读数与回执 ID、列断点清单，并判计费（`deduction_seen`／`no_change_seen`／`unconfirmed`）。看到扣费或快照不符时退出码 2。
- `corpus agree`：双跑标注比对的脚本部分，词表 `schemas/data/corpus-label-vocabulary.json`；不一致的交换记 `labelConfidence: low`。
- `corpus defaults`：从语料重算媒介档案默认值、按形态的交换中位时长与禁词表统计，都带样本量 `n`；候选新词只写进 `--out`，不进随包数据。
- `feedback-ingest` 全路由：新认分节批注、修改对照表（`--section`）、追问单回答记录三种输入；`--out <空目录>` 按层级写派生物（反例、人写正例、对照对草稿、约定草稿、问题草稿、底账修订提案、K1 卡草稿、决定队列条目），每条带 `fromNotes`、`status: drafted`、`scope.level: project`；`--target` 写升版的台词目标（带 changelog）；`--purge <noteId>` 按来源清掉派生物。
- 方法文档 [`references/corpus.md`](skills/drama-studio/references/corpus.md)：取用、计费观察、快照与失效、切分、过滤、处境标注与双跑、媒介档案与禁词表；`mali-story.md` 加「语料读取的回执与计费观察」一节。

### 变更

- `corpus filter` 加排除原因 `label_low`：双跑不一致的交换不进通过名单。
- 随包数据：`default-media-profile.json` 各形态加 `n`，交换中位时长按形态记；`genre-lexicon.json` 每张表加实测统计。两份只放统计量与词表，不放语料原句。
- `context-pack`：没有来源（`provenance` 或 `fromNotes`）的对照对拒装；样本文件可以放在项目根下的 `corpus/`。
- `contract-check dialogue-target`：升版时 changelog 里要有本版一条。
- 方案回写（D6-5）：集纲方案 v1.3、台词方案 v3.3 写入实施计划 §2.6 的修正点；三份旧设计、实施路线、D4-5 页加状态行或注；页面化评估见 [d6-5-pages](docs/d6/d6-5-pages.md)。

## 0.6.0 — 2026-10-15（D6-3，#81）

台词层切换为 C5a 对话表 → C5b 照表写正文 → C6 五读 → 先改表再改文；台词遍、台词读退役。见 [D6-3 报告](docs/d6/d6-3-report.md)。

### 新增

- 新方法文档 [`references/dialogue-structure.md`](skills/drama-studio/references/dialogue-structure.md)（由 `dialogue.md` 改名重写）：对话表、样本用法、写正文、冷读复述、处境对照、设计依据一致性与诊断信号、修订、人工反馈吸收。
- 新对象 `revision-list`（修订单：不写替换台词、不下数值指令）与 `plan-text-map`（C5b 的对照表：交换落在哪几行、逐字采用的人工句）。
- `season-check --legacy-dialogue`：只在带它时跑旧三条（`voice-card`、`dialogue-pass`、`dialogue-read`），输出与 0.3.6 相同。
- 台词层规则 13 条，启用台词层的项目输出 `episodeRuleSet: dialogue-layer` 与 `dialogueLayerRules`，新增 `preserved-human-source`。
- `context-pack` 的 `samples` 分区与 `--quotes-per-topic`（每个话题遮蔽原句合计上限，默认 2）；`--exemplars` 可以直接给对话表；装包历史写 `.drama/packs/history.json`；题材禁词表可按 id 进包（`lexicon:genre-lexicon@v1`）。
- `capacity text` 加 `--episode-plan`、`--target-sec`，目标秒数取「显式 ＞ 分集计划 ＞ 媒介档案」。

### 变更

- 「启用了台词层」按记录判：`planning/` 或 `.drama/` 下有带 `dialogue-plan` 标记的 JSON。
- `writing.md` 工位流程第 4–10 步改写；`SKILL.md` 路由与「一次完整创作」第 4 步改写；篇幅改用容量算术。
- `review-record.preserved` 的项写成 `{item, noteId|humanWords}`；启用台词层的项目里纯字符串写法判失败。
- 首读封存写进首读记录的 `sealedSha256`；`run-handoff` 可写 `decisionRefs[]`，`contract-check run-handoff --decisions` 核引用存在。

### 退役

- 台词遍（`dialogue_author`）、台词读（`dialogue_read`）作为步骤；「盖住名字猜人」；「另一模型家族做台词读」。
- 声音卡 K5 降为索引（`knowledge search --type K5` 仍可查，不再是装包必需与判据）；对照卡 K9 不再新建，已有的保留可读。
- 修订单写替换台词、数值型台词约束（升为脚本拒绝）。

## 0.5.0 — 2026-10-15（D6-2，#81）

集纲层切换为 C3a 功能地图 → C3b 底账 → C3c 季编排 → C4 分集计划。见 [D6-2 报告](docs/d6/d6-2-report.md)。

### 新增

- 新方法文档 [`references/outline-layer.md`](skills/drama-studio/references/outline-layer.md)：功能地图、前提层、六类账与条目状态、追问单、检索代理与 K1 卡、修订规则、季编排与容量、分集计划 14 字段、决定队列、用户给定设定的处理、命令速查。
- `plan-events`（分集计划的 events 导出，冷读只装它）与 schema `episode-plan-events`；`plan-check --characters`（只报不拦）；`ledger replay --delta <目录>`；`ledger view <功能地图> --blank-period`。
- `season-check --outline` 在有 `planning/season-plan.json` 的项目上另核集纲层七条，输出 `ruleSet: outline-layer` 与 `outlineLayerRules`。
- 送审包加四份附录：设定核对报告、戏剧假定清单、未核清单、决定队列。

### 变更

- 「启用了集纲层」按记录判：有 `planning/season-plan.json`、`planning/function-map.json`，或 `planning/ledger/`、`planning/episodes/` 下有 JSON 记录。
- `init-project` 多建 `planning/ledger/`、`planning/episodes/`、`runs/`、`knowledge/`；`context-pack` 的 `local_file` 放行 `planning/`，可按 id 装随包问题单；C4 作者包要求季编排、底账修订、功能地图三件。
- `capacity` 没有语料或媒介档案时用随包默认值，标 `basis.status: default_unmeasured`。
- `planning.md`「蓝图、底账与集纲」一节重写；`approval-flow.md`、`recovery.md`、`SKILL.md` 第 6 步改写。
- `constraint-blocklist` v3：拒绝「不动集数／标题／★」「只改一次」类约束与数值型台词约束。

### 退役

- 六字段集纲作为计划格式（看点、情绪、爽点改为可选摘要）；「关键选择」字段与审读硬项；剧情框架 260 字上限。
- `notes-*.md` 段末「给后段」、框架第七节道具表与第九节节拍表、圣经第五节信息阀门表、`open-issues`（分别由底账与决定队列取代）。
- 手写的 `runs/state/after-ep-NNN.md`：改由 `ledger replay --track actual --md` 从实际轨导出，文件名沿用。

## 0.4.0 — 2026-10-15（D6-1，#81）

集纲层与台词层的对象与只读工具；旧流程一字不改地继续可用。见 [D6-1 报告](docs/d6/d6-1-report.md)。

### 新增

- 18 个新 schema（功能地图、底账条目与 delta、问题单、回答记录、季编排、分集计划、决定队列、媒介档案、语料交换与清单、对照对、对话表、台词目标、批注、冷读复述、设计依据一致性、缺口登记表等），各带一份合成例子；`schemas/data/` 下的问题单、约束词表、题材禁词表数据文件。
- 命令：`ledger`、`plan-check`、`season-plan-check`、`capacity`、`decision`、`function-map`、`defects build`、`check-answers`、`retell-check`、`answers-consistency`、`dialogue-plan-check`、`plan-text-consistency`、`dialogue-diagnose`、`feedback-ingest`（骨架）、`corpus {segment|label|filter|lexicon|rate}`。
- `contract-check` 的跨文件规则（`--records`、`--defects`、`--cards`、`--questions`、`--base-questions`）；`dup-check --list-hits --k`；`episode-check --speech`（口播量）。
- `context-pack` 新角色：`function_mapper`、`ledger_keeper`、`season_planner`、`dialogue_designer`、`situation_checker`、`cold_reader`。

### 变更

- `task`、`review-record`、`run-handoff`、`context-snapshot`／`selection`、`knowledge-card` 加可选字段；旧例子仍通过。
- `season-check` 新旧规则并存，按项目自动选；旧项目输出与 0.3.6 逐字节一致（测试锁定）。

## 0.3.6 及更早

见 git 历史与 [README](README.md)。

设计文档：集纲层与台词层两份方案及统一实施计划（#79），按 D6-0 修订（#80）。
