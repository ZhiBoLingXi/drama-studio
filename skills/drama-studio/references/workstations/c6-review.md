# C6 审读与整合

[工位通用协议](README.md) · 契约 v0.1

| 项 | 内容 |
| --- | --- |
| 必读本剧依据 | 审正文：待审正文与必要前文，第二轮才看目标、状态索引、制作限制与知识依据；审分集计划：见下面的集纲侧三读，每一读装的东西不同 |
| 主要知识 | K8、K9 与相应方法和反例；没有知识缺口时可以不检索 |
| 产出 | 审读记录（`review-record`）：事实／目标／偏好分开的问题、文本证据、引用（`cites`）、保留价值、损失、返修归属层（kind：`review`）；集纲侧另有追问单回答记录与冷读复述（`retell-record`） |
| 交接 | `run-handoff`；问题属于上游时提 `changeProposals`（目标层须在本层之前） |

## 方法要点

- 首读只给观众可获得的信息，用 `reader_effect` 角色装包，不含作者计划与解释。
- 台词遍之后另做一次台词读（`dialogue_read` 包，只放正文），逐句标出不像这个人会说的话，见 [台词读](../dialogue.md#6-台词读)。
- **每条 finding 必带 `cites`**，四选一或几项并列：`functionId`（功能地图）、`ledgerId`（底账条目）、`targetClause`（目标条款）、`factEvidence`（事实证据）。一项都引不出的写 `kind: preference`，记下但不进修订单。
- 问题回到真正负责的层：台词实现回 C5；分集计划的入口、事件、信息清单回 C4；动作站不住、实现不成立回 C3a 换实现（[修订规则](../outline-layer.md#7-修订规则四种不允许的修法patchcount换实现预算-2-次后登记并继续)），不在原实现上加一拍解释；底账条目写错回 C3b；人物前提回 C2。finding 的 `layer` 写 `C3` 时在 `claim` 里写明是 C3a、C3b 还是 C3c。
- 保留“原稿更好”“各有损失”“材料不足”“审美分歧”；没有独立上下文时 `context` 如实填 `serial_self_review`。

## 集纲侧三读

审分集计划时做这三读，各由没写这段计划的上下文完成（子代理、新会话或真人），各留记录。三读的 `review-record` 由新上下文的审读方写（`context: independent`，真人审读填 `human`），不由写这段计划的作者写或汇总；作者自己汇总的记录只能填 `serial_self_review`，不算这次审读。任务写 `target.kind`（`episode_plan`、`function_map`、`ledger` 或 `season_plan`），这类集纲侧任务不需要 `dialogueTarget`。启用集纲层的项目，审读对象在 `planning/episodes/` 下时，每条 finding 必带 `cites`，标 `kind: preference` 的可以不带。主角与对手的选择都在 `moves[]` 里，由追问单逐条问。

1. **追问单复核**：新上下文，`context-pack --role fact_check`（装进去的 K1 卡 `usage` 不能是 `evaluation_only`；问题单按 id 进包，选材清单写 `{"kind": "local_file", "id": "question-set:reality-check-questions@v1"}`），对本集 `moves[]` 的每个关键动作答 [追问单](../outline-layer.md#5-追问单16-问信息题answerkind承重缺口的三个去处disposition)（回答记录的 `target.kind: move`），每答落到具体的场、拍或底账条目，写三态与原因，涉出处引 K1 卡。承重的 `notHolds` 由作答方标依据（去掉这一步哪个功能句落空），并给出去处（`disposition`）。`check-answers <回答> --function-map … --decisions … --ledger …` 核格式与去处，不核答案对不对。
2. **底账一致性**：脚本读，模型不判。`plan-check <分集计划> --ledger <入口修订> --season planning/season-plan.json --function-map planning/function-map.json --decisions planning/decisions.json` 核引用、在场、说话人知情与 `supportedBy`；`ledger check <入口修订> --delta <本集计划轨 delta>` 核物件单链、知识单调、钱的来去、矛盾等。报出的问题照抄进 finding，`cites.ledgerId` 填条目 id。
3. **分集计划冷读复述**：先用 `plan-events <分集计划> --out .drama/checks/events-ep<NNN>.json` 导出只含 `events` 的版本（去掉 `saysFact` 等设计字段）；新上下文用 `context-pack --role cold_reader` 装包，包里只放这份导出一项（`project_facts`），不放其他字段、前集与底账。装整份分集计划时 `context-pack` 退出码 2。读者复述谁在场、按顺序发生了什么、因为什么、停在哪，并列出「我不知道为什么会这样」。复述存成 `retell-record`（`target.kind: episode_plan_events`），`retell-check <复述> --plan <分集计划>` 对照 `infoLedger` 的 facts 与 `exit.closingEvent`；`missing` 的回 C4。

三读的结论只说明追问单每问成立或标了未核、底账自洽、计划自足；不说明这集好看。

## 审读包装什么

- **正文引用到的前文场面必须装进审读包。** 待审正文回指、复用或兑现了前文的某个场面（道具、承诺、旧伤、某句台词），就把那一场的原文区间列进选材清单；只装“前一集”不够。缺了它，审读会把正当的回扣误判为“新设事实”或“前后矛盾”（D2 的 f5 误报即由此而来）。拿不准是否引用了前文时宁可多装，超预算就缩小审读单元。
- **首读包里的“前一集”若已精修，装精修稿，不装原稿。** 观众看到的是精修后的前一集；拿原稿当前文，衔接问题会被误报或漏报。选材清单里按 pageId 引用该集最新的已精修修订（`remote_page`，修订号取已缓存的修订；迁移前的历史候选按 slot 引用 `remote_artifact`）；精修稿尚未写成页面、只在本地时，作为 `local_file` 装入（见 [定向修订单独装包](README.md#定向修订单独装包)），并在 `reason` 写明“精修稿”。
- 一次审读覆盖多份候选（按批审读）时，`review-record.target` 填第一份，其余填 `additionalTargets`（同 `ref` 结构），不要塞进 `readingScope`；`readingScope` 只写实际读过的材料。
- 首读与次读各装一个包时，`run-handoff.contextSnapshotId` 填首读包，次读包写进 `additionalSnapshotIds`；任一包里的前文被修订，`impact` 都会把这次审读标为 `stale`。

## 停止与边界

评分不是采用；无硬矛盾不代表本轮修改目标已达成。审读不产生新约束。集纲侧审读的返修次数不超过 `task.revisionBudget`；触顶后不再改，两处都做：未处理的审读意见写进交接 `unfinished`（`goal` 记 `partially_met`，写明瓶颈），并用 `decision add planning/decisions.json --from-handoff <交接>` 登记进决定队列、带默认，流程按默认继续，不停下等人。审正文时，返修次数同样不超过 `task.revisionBudget`，触顶就交付未达标候选并写明瓶颈。
