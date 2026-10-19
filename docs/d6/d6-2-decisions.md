# D6-2 开头的共用决定

依据：[统一实施计划](../design/drama-studio-outline-dialogue-implementation-plan-2026-10-14.md) §4.3 与 [D6-1 报告](d6-1-report.md) 第六节。日期 2026-10-15。三个工作流（方法文档、工位文档、工具）共读本页，写法不一致时以本页为准。

## 1. 项目目录布局（D6-1 先定、D6-2 确认）

集纲层的产物都是本地 JSON，放项目目录下；页面化留到 D7（计划 §4.7）。

| 路径 | 放什么 | 谁写 |
| --- | --- | --- |
| `planning/function-map.json` | 功能地图（C3a，含前提层、候选、`closes[]`） | C3a |
| `planning/ledger/ledger-ep000.json` | 开播前底账（C3b） | C3b |
| `planning/ledger/delta-ep<NNN>.planned.json`、`delta-ep<NNN>.actual.json` | 两轨逐集修订 | C4（计划轨）、C5 之后（实际轨） |
| `planning/ledger/ledger-ep<NNN>.planned.json`、`ledger-ep<NNN>.actual.json` | 两轨各集的底账修订：前者是 `ledger apply` 的输出（计划轨），后者是 `ledger replay --track actual --out` 的输出（下一集的入口底账修订） | 脚本 |
| `planning/season-plan.json` | 季编排（C3c，含容量与动作） | C3c |
| `planning/episodes/episode-plan-<NNN>.json` | 分集计划（C4，14 字段） | C4 |
| `planning/decisions.json` | 决定队列（每条带 `default`） | 各层登记 |
| `.drama/checks/` | 追问单回答记录、冷读复述、缺口登记表（`defects build` 生成）、各命令的输出 | 核对方、脚本 |
| `.drama/tasks/` | 任务对象 | 编排方 |
| `knowledge/cards/` | K1 卡（检索代理产出，现有位置不变） | 检索代理 |
| `runs/state/after-ep-<NNN>.md` | 由 `ledger replay` 从实际轨导出（文件名沿用，退役表 #12） | 脚本 |

**修订（2026-10-18）**：底账修订文件名带轨道后缀，`ledger-ep<NNN>.planned.json`／`ledger-ep<NNN>.actual.json`；除开播前底账 `ledger-ep000.json` 外，不再有无后缀的 `ledger-ep<NNN>.json`。原因：计划轨与实际轨的修订原先同名，下一集的入口会拿错轨。工具认 `planning/ledger/ledger-*.json`，不受影响。

集号一律三位数字，半集或拆集写 `006A`。`season-check` 已按「任意深度＋schema 标记」认记录，布局只是约定，不是新的识别规则。`init-project` 在已有的 `planning/` 之外再建 `planning/ledger/`、`planning/episodes/` 空目录。`context-pack` 的 `local_file` 放行 `planning/`。

**「启用了集纲层」的判据**：项目里有 `planning/season-plan.json`、`planning/function-map.json`，或 `planning/ledger/`、`planning/episodes/` 下有 JSON 记录，任一项即是。不用「有 `planning/`」：0.3.6 的 `init-project` 就建 `planning/`，旧项目里也放着旧的框架与集纲文件。也不用「有空目录」：`init-project` 现在会建这两个空目录，按目录判会拦住刚建、还在走旧式集纲的项目（现有 53 项 season-check 测试的夹具就是这样建的）。按新流程走的项目到 C4 时已有 C3a、C3b 的产出，所以满足判据；旧项目不满足，行为不变。（2026-10-15 修订两次，原因如上。）

## 2. `references/outline-layer.md` 的节标题（工位文档按这些标题链接）

1. 总览：C3a → C3b → C3c → C4，两处人审不变
2. 功能地图（功能句、候选、步骤与 `origin`、`losesFunctions`）
3. 前提层与 C3a 内的顺序
4. 六类账与条目状态（含时间线子型 `state`、两轨、戏剧假定 `license_pending`／`accepted_license`）
5. 追问单（16 问、信息题、`answerKind`、承重缺口的三个去处、`disposition`）
6. 检索代理与 K1 卡（可联网、留出处；脚本不联网）
7. 修订规则（四种不允许的修法、`patchCount`、换实现预算 2 次后登记并继续）
8. 季编排与容量（两口径、动作 rearrange／split／drop_function，删线不作默认，数字不当裁判）
9. 分集计划字段（14 字段，`summary` 可选）
10. 决定队列（kind 词表、`default` 必填、`decided` 须 `humanWords`）
11. 用户给定设定的处理（`user_given`／`user_given_modified`、不成立时默认保留并标 `license_pending`）
12. 命令速查（每步跑哪个命令、退出码怎么读）

## 3. 计划 §8 #4（容量提案三选一由谁定）

按计划写的默认做，不另找主创：送审前由季编排层选（系统内的动作，记进 `season-plan.json` 的动作记录）；送审后进决定队列、按默认先走、随送审包一并审。删功能（`drop_function`）永不作默认。

## 4. 本阶段发现、留给 D6-3 的事

- `writing.md` 第 7 步与 `SKILL.md`「一次完整创作」第 4 步仍写「C4 及以上问题写成变更提案交用户决定」：应改为 `decision add --from-handoff` 登记并带默认、流程不停。
- `writing.md` 第 9 步「手写 after-ep」：改为 `ledger replay` 从实际轨导出。
- `season-run.md` §3 第 7 步仍有「关键选择缺失」。
- 正文侧修订预算用完后的审读意见：集纲侧已统一为「写进交接 `unfinished` ＋ `decision add --from-handoff` 带默认登记」，正文侧（C5、c6 正文侧）仍是旧说法，D6-3 统一。
- 复走 N9：出错的 K1 卡修订没有撤回的办法（只能出新修订）。不在 D6-2 修；等重做项目验证时看是否真有需要。

## 5. 走通演示（[d6-2-walkthrough](d6-2-walkthrough.md)）发现的处置

编号同演示报告「发现」。T＝工具流，M＝方法文档流（含 `writing.md`），W＝工位文档流。

| # | 裁定 | 谁 |
| --- | --- | --- |
| 1 | `fact_check` 装包放行 `comparison_only` 的 K1 卡（核现实就是拿来比对）；只拒 `evaluation_only` | T |
| 2 | `capacity` 没有语料时用随包默认媒介档案，输出标 `basis: default_unmeasured`、退出码 0；默认值写进文档 | T＋M |
| 3 | `ledger view --blank-period` 可直接读功能地图的 `ledgerDeps`（C3a 阶段），不必先有底账 | T |
| 4 | `promptVersion`：`check-answers` 要求它；随包 `answers.json` 例子补上；文档写明必填 | T＋M |
| 5 | `ledger check` 的 schema 基本项与 `contract-check ledger-entry` 用同一套必填；`whyNotApplicable` 代替 `why`（不再两个都要）；保留下来的额外规则（如 `state` 子型要 `knownTo`）逐条写进 §4 | T＋M |
| 6 | `money-closed`：列进 `emptyFields` 即算交代，`no_trace` 不再是唯一写法；文档写明两种 | T＋M |
| 7 | `check-answers --records` 接受目录 | T |
| 8 | C1、C2 没有装包：`run-handoff` 允许 `contextSnapshotId: null` 并要求 `noSnapshotReason`；其他工位照旧必填 | T＋W |
| 9 | 新增分集计划的 events 导出（只含 events，不含 `saysFact` 等设计字段）；`cold_reader` 包对分集计划只收这份导出，整份计划被拒（退出码 2） | T＋M＋W |
| 10 | C4 包的内容以一张清单为准，c4 文档、`season-check` 的 `outline-structure`／`outline-characters` 与之对齐；知识卡按选材清单的卡片项装（不走 `local_file`），媒介档案放 `planning/media-profile.json` | T＋W |
| 11 | 集纲侧 `review-record` 由新上下文的审读方写，作者不写；作者汇总里的 `serial_self_review` 不算审读 | W＋M |
| 12 | 集纲侧离线：与正文离线同法（用户明确同意只交本地稿 → 回执记 `not_sent` → `season-check --allow-offline`），写进 c4 与 §1 | W＋M |
| 13 | 作者自己写错的承重缺口：作者在修订预算内改，新上下文复核得到 `confirmed_gone`；编排方回填原回答记录的 `disposition`（`to: confirmed_gone`，引用复核记录）。回填只动 `disposition`，不动三态与原因 | M＋T（`check-answers` 接受回填） |
| 14 | 跨前提一致性表是 M：放 `planning/premise-consistency.md`，没有命令核，文档不再写成 S | M |
| 15 | `function-map topics` 只归并能检索的类（`procedure`，以及 `money`／`object` 里涉及现实规则的 `required_unstated`）；`knowledge`／`agenda` 不出题 | T＋M |
| 16 | `writing.md` 离线一节改为允许 `planning/` | M |
| 17 | §11 前提一级：追问前的默认一律「保留用户给定、标 `license_pending`」；追问后若有不让功能句落空的合格候选，再按候选走 | M |
| 18 | 勘误清零：由复核记录确认（新上下文的复核回答把该勘误判为已改），`function-map check --stage v1` 核「每条勘误有后续复核记录」 | T＋M |
| 19 | `outcome`：只有不承重的 `notHolds` 时允许 `pass_with_unverified` | T＋M |
| 20 | 回答记录每答可带可选 `subject`（`move` id 或候选 id），一份记录覆盖多个动作时必填 | T＋M |
| 21 | `because`：`no_card`＝没有覆盖这个题目的卡；`card_says_not_found`＝有卡、卡上这条写明查无出处（`coverage: empty` 或 `support: not_found`）；`cannot_answer`＝有卡但卡不涉及这一问 | M |
| 22 | 问题单可进包：`context-pack` 允许装随包 `schemas/data/` 下的问题单（只读、按 id），不必复制进项目 | T＋M |
| 23 | 产物位置：任务 `.drama/tasks/`、选材 `.drama/selections/`、媒介档案 `planning/media-profile.json`、`ledger apply` 的新修订 `planning/ledger/ledger-ep<NNN>.json`；快照由 `context-pack` 自己写进 `.drama/snapshots/`，不要存标准输出；`init-project` 补建 `runs/`、`knowledge/`；`.drama/runs/` 在第一份交接写入时再建（现有测试锁定「空项目的 `.drama/` 只有 `project.json`」，不为一个空目录改它） | T＋M |
| 24 | `status` 不把已交接的运行标成未结束；`blank-period` 把 `state` 子型按 `stateOf` 归人；`retell-check` 收尾拍判法与「readingScope 只应一项」的误报修掉 | T |
| 25 | `season-check` 在 `ruleSet: outline-layer` 下列出跑过且通过的规则（旧输出不变）；`plan-check` 的 `speaker-knows` 有 `notEvaluable` 时状态写 `pass_with_not_evaluable` | T＋M |

## 6. 不动的东西

旧项目文件一律不动；《渊心锁》与本项目旧记录的 `season-check` 输出仍与 0.3.6 逐字节一致。文档里退役的段落删除或改写，不保留「旧做法」并列。台词侧（C5、台词遍、台词读、声音卡）是 D6-3 的事，本阶段不改。
