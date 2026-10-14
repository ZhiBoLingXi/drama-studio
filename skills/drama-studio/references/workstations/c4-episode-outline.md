# C4 分集计划

[工位通用协议](README.md) · 契约 v0.1 · 字段见 [分集计划字段](../outline-layer.md#9-分集计划字段14-字段summary-可选)

| 项 | 内容 |
| --- | --- |
| 必读本剧依据 | 季编排里本集的分配、底账当前修订（已有正文时接上一集**实际轨**）、前一集分集计划、C2 人物包、功能地图里本集涉及的功能 |
| 主要知识 | K3、K4、K8、K9 修改经验，按选材清单的卡片项装；现实依据只引用底账里的程序条目，不在本层查证 |
| 产出 | 分集计划 `planning/episodes/episode-plan-<NNN>.json`（schema `episode-plan`）及其可读稿（存成 `episode_outline` 页面），14 个字段见下表；声明计划轨 `ledgerDelta` |
| 交接 | `run-handoff`（`workstation: C4`，装包角色 `author`）；要新功能、新线或改实现时提 `changeProposals` 给 C3a，装不下、要挪集时给 C3c，不在本层定全剧级事实 |

## 产出的 14 个字段

| 字段 | 装什么 | 必填 |
| --- | --- | --- |
| `episode`、`title` | 集号（拆集写 `6A`）；标题是派生的，不是约束 | 是 |
| `entry` | `ledgerRev`（入口底账修订）与一两句入口状态：故事日、谁在哪、手里有什么、知道什么 | 是 |
| `functions[]` | 季编排分给本集的 `functionId`，各写推进到哪一步（`progress`） | 是 |
| `events` | 自足的 `scenes[].beats[]`：每场 `sceneId`、`time`、`place`、`present`；每拍 `beatId`、`who`、`text`，需要的台词写 `quote`，幕后的事标 `offscreen`；写到集末最后发生的事 | 是 |
| `presence` | 主要人物不在场的理由（`absences[]`，引用时间线账） | 场数 ≥ 2 或涉机构时 |
| `moves[]` | 改变局面的动作：`who`、`did`、`wants`、`easierOption`、`whyNot`、`cost`；对手的动作必有，主角的选择也写在这里 | 是 |
| `infoLedger[]` | 观众本集必须拿到的事实：`infoId`、`whyAudienceNeeds`、`facts[]`（`factId`、`text`、`carrierBeat`、`keywords`）、`knownByInStory`、`laterDependents` | 是 |
| `ledgerDelta` | 计划轨的 `reads`／`writes`；每条 `writes` 的 `supportedBy` 指向本集的 `sceneId` 或 `beatId` | 是 |
| `realityRefs[]` | 本集用到的程序账条目 id | 涉机构／程序／技术时 |
| `threads` | `pays[]`、`plants[]`，引用季编排登记的埋设 | 有埋设或兑现时 |
| `exit` | `ledgerRev`（计划轨）、一两句出口状态、`closingEvent.beatRef`（指向最后一场最后一拍，是事件不是悬念说法） | 是 |
| `capacity` | `capacity episode` 复核的估时；`status` 为 `fits` 或 `proposal:<决定队列 id>`（超出是提案，不是失败） | 是 |
| `pending[]` | 引用的决定队列条目与本集采用的默认（`decisionId`、`defaultUsed`） | 有待定时 |
| `summary` | 可选的看点、情绪、爽点摘要；不许含 `events` 里没有的人、物、事 | 否 |

各栏不装什么：`events` 不写镜头指示、留给正文的话、作者对心理的解释；`moves` 不复述事件、不写心理旁白；`pending` 不写没有默认走法的「待主创定」。

## 方法要点

- 入口读取前一集实际发生的事：已有正文时接底账实际轨（`runs/state/after-ep-<NNN>.md` 由 `ledger replay --track actual --md` 导出），不接前一集计划。
- 动作写出动机与放弃项：此刻要什么、更省事的做法是什么、为什么没做、代价是什么。答不出「为什么没做」的动作回 C3a 换实现，不在本集加一拍解释。
- 「被感动、决定原谅」这类情绪变化要落到拍上的经历与动作，不能留给正文补黑箱。
- 一集装不下时不留给正文压台词：`capacity episode` 超出就登记提案并按默认走，挪集或拆集回 C3c。
- 检查连续几集是否用同一种解法。

## 整季集纲怎么写

写送审用的完整分集计划（如第 11–60 集）也走工位，不能只把季编排分给几个子代理并行扩写。

1. **先有上游，各自留交接**：C2 人物包、C3a 功能地图、C3b 底账、C3c 季编排各写一份 `run-handoff`（后三者 `workstation: C3`）。本次新写的就如实写成新写，只有用户给定的材料才写「采用用户给定」。
2. **按顺序分段**：一段默认不超过 15 集，一段一个 C4 运行，前一段写完、存好，再给下一段装包。不并行：并行的几段互相看不到，同一件物件、同一条知识会被写成两种说法，底账也接不上。
3. **每段的包**（`context-pack --role author`）必装三件：季编排 `planning/season-plan.json`、底账修订 `planning/ledger/ledger-*.json`（`ledger-ep000.json` 或 `ledger apply`／`replay` 写出的入口修订；delta 文件不算）、功能地图 `planning/function-map.json`，缺任一件退出码 2。另装 C2 最新人物包、前一集分集计划的最新稿；已写到第 N 集正文时再装 `runs/state/after-ep-<NNN>.md`（实际轨导出），后面的分集计划从实际轨接。对标、拉片资料按需要装，装了就写清用途；知识卡按选材清单的卡片项装（`knowledge_card`），不当作 `local_file`。
4. **分集计划也要审**：每段写完，由没写这段的上下文做 C6 集纲侧三读（[追问单复核、底账一致性、冷读复述](c6-review.md#集纲侧三读)），记 `review-record`，`target`／`additionalTargets` 指向各集分集计划；冷读复述每集一份 `retell-record`（`target.kind: episode_plan_events`），冷读包只装 `plan-events` 导出的 events。
5. **存成页面**：每集可读稿一个 `episode_outline` 页面（带 `episode_ref`），记回执；`planning/episodes/` 下的 JSON 是同一份计划的结构化本，列进交接的产出，`season-check` 按它认集号。没有 mali-story 连接时与正文离线同法：只有用户明确同意只交本地稿才离线，把原话记进 `PROJECT.md`；可读稿放本地，回执记 `not_sent`（`pageId`、`revision` 为 null），第 6 步的 `season-check` 加 `--allow-offline`，交付说明写明未存成页面。
6. **关口**：`plan-check` 逐集核引用、在场、说话人知情与 `supportedBy`；`drama_tools.py season-check <项目> --outline <起-止>` 核对上面五条，项目有季编排时它跑集纲层规则（`ruleSet: outline-layer`）。不通过不能写「集纲已按流程完成」。


## 停止与边界

不设每场反转配额，不设字数上限；每场能说明它承担什么变化即可。不改功能、不定全剧级事实、不查证。返修次数不超过 `task.revisionBudget`；触顶后不再改，两处都做：未处理的审读意见写进交接 `unfinished`（`goal` 记 `partially_met`，写明瓶颈），并用 `decision add planning/decisions.json --from-handoff <交接>` 登记进决定队列、带默认，流程按默认继续，不停下等人。
