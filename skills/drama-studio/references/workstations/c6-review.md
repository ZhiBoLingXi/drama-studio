# C6 审读与整合

[工位通用协议](README.md) · 契约 v0.1

| 项 | 内容 |
| --- | --- |
| 必读本剧依据 | 审正文：首读只看待审正文与必要前文，次读再看目标、状态索引、制作限制与知识依据，另三读装的东西见“正文侧”一节；审分集计划：见“集纲侧三读”，每一读装的东西不同 |
| 主要知识 | K8；处境对照装对话表引用的正例与对照对；没有知识缺口时可以不检索 |
| 产出 | 审读记录（`review-record`）：事实／目标／偏好分开的问题、文本证据、引用（`cites`）、审读者看到的长处（写进 `goalAssessments[].evidence`）、损失、返修归属层（kind：`review`）；另有冷读复述（`retell-record`）、问题单回答记录（集纲侧追问单、正文侧对话问题单）与设计依据一致性记录（`plan-text-consistency`） |
| 交接 | `run-handoff`；问题属于上游时提 `changeProposals`（目标层须在本层之前） |

## 方法要点

- 首读只给观众可获得的信息，用 `reader_effect` 角色装包，不含作者计划与解释。
- **每条 finding 必带 `cites`**，四选一或几项并列：`functionId`（功能地图）、`ledgerId`（底账条目）、`targetClause`（目标条款）、`factEvidence`（事实证据）。一项都引不出的写 `kind: preference`，记下但不进修订单。
- 问题回到真正负责的层：没照对话表写回 C5b；处境或走法的理由错了回 C5a（先改表再改文）；分集计划的入口、事件、信息清单回 C4；动作站不住、实现不成立回 C3a 换实现（[修订规则](../outline-layer.md#7-修订规则四种不允许的修法patchcount换实现预算-2-次后登记并继续)），不在原实现上加一拍解释；底账条目写错回 C3b；人物前提回 C2。finding 的 `layer` 写 `C3` 时在 `claim` 里写明是 C3a、C3b 还是 C3c；台词侧写 `C5a` 或 `C5b`（`C5` 只留给旧记录）。
- 审读者认为写得好的地方是模型判断，写进 `goalAssessments[].evidence`，以「审读者看到的长处（模型判断）」开头，不写进 `preserved`。`preserved`（不许动）只放人工来源的项，每项写 `{item, noteId}` 或 `{item, humanWords}`；集纲侧与正文侧同一规则，两侧都由脚本核：集纲侧（审读对象在 `planning/episodes/` 下）由 `contract-check review-record` 核，纯字符串项直接拒；正文侧由 `season-check --episodes` 的 `preserved-human-source` 核。项目启用台词层后，已有审读记录（包括之前写的集纲审读）里的 `preserved` 也按这条核：旧的纯字符串项要迁移，有人工来源的改写成 `{item, noteId}` 或 `{item, humanWords}`，模型判断的挪进 `goalAssessments[].evidence` 并加上述前缀，由原审读方或编排方迁移，迁移时逐项过一遍，不只改报错列出的几项。
- 保留“原稿更好”“各有损失”“材料不足”“审美分歧”；没有独立上下文时 `context` 如实填 `serial_self_review`。

## 集纲侧三读

审分集计划时做这三读，各由没写这段计划的上下文完成（子代理、新会话或真人），各留记录。三读的 `review-record` 由新上下文的审读方写（`context: independent`，真人审读填 `human`），不由写这段计划的作者写或汇总；作者自己汇总的记录只能填 `serial_self_review`，不算这次审读。任务写 `target.kind`（`episode_plan`、`function_map`、`ledger` 或 `season_plan`），这类集纲侧任务不需要 `dialogueTarget`。启用集纲层的项目，审读对象在 `planning/episodes/` 下时，每条 finding 必带 `cites`，标 `kind: preference` 的可以不带。主角与对手的选择都在 `moves[]` 里，由追问单逐条问。

1. **追问单复核**：新上下文，`context-pack --role fact_check`（装进去的 K1 卡 `usage` 不能是 `evaluation_only`；问题单按 id 进包，选材清单写 `{"kind": "local_file", "id": "question-set:reality-check-questions@v1"}`），对本集 `moves[]` 的每个关键动作答 [追问单](../outline-layer.md#5-追问单16-问信息题answerkind承重缺口的三个去处disposition)（回答记录的 `target.kind: move`），每答落到具体的场、拍或底账条目，写三态与原因，涉出处引 K1 卡。承重的 `notHolds` 由作答方标依据（去掉这一步哪个功能句落空），并给出去处（`disposition`）。`check-answers <回答> --function-map … --decisions … --ledger …` 核格式与去处，不核答案对不对。
2. **底账一致性**：脚本读，模型不判。`plan-check <分集计划> --ledger <入口修订> --season planning/season-plan.json --function-map planning/function-map.json --decisions planning/decisions.json` 核引用、在场、说话人知情与 `supportedBy`；`ledger check <入口修订> --delta <本集计划轨 delta>` 核物件单链、知识单调、钱的来去、矛盾等。报出的问题照抄进 finding，`cites.ledgerId` 填条目 id。
3. **分集计划冷读复述**：先用 `plan-events <分集计划> --out .drama/checks/events-ep<NNN>.json` 导出只含 `events` 的版本（去掉 `saysFact` 等设计字段）；新上下文用 `context-pack --role cold_reader` 装包，包里只放这份导出一项（`project_facts`），不放其他字段、前集与底账。装整份分集计划时 `context-pack` 退出码 2。读者复述谁在场、按顺序发生了什么、因为什么、停在哪，并列出「我不知道为什么会这样」。复述存成 `retell-record`（`target.kind: episode_plan_events`），`retell-check <复述> --plan <分集计划>` 对照 `infoLedger` 的 facts 与 `exit.closingEvent`；`missing` 的回 C4。

三读的结论只说明追问单每问成立或标了未核、底账自洽、计划自足；不说明这集好看。

## 正文侧：首读、次读与另三读

审正文（每集）时做五读：首读、次读保留，另加冷读复述、处境对照与设计依据一致性。正文侧任务写 `target.kind: episode_text`，`layer: C6` 的任务引用 `dialogueTarget`。五读各由没写这集的上下文完成，各留记录。方法见 [正文侧两读](../dialogue-structure.md#6-正文侧两读冷读复述处境对照对话问题单) 与 [设计依据一致性](../dialogue-structure.md#7-设计依据一致性与诊断信号数字只诊断不裁判)。

1. **首读**（`reader_effect`）：观众效果，装包见下面“审读包装什么”。首读记录写完立即封存：去掉 `sealedSha256` 字段后按规范 JSON 算 sha256，写进同一份记录的 `sealedSha256`（旧做法的 `.sha256` 旁注文件照认），之后不再改动。台词层项目里，首读与次读只认审读对象是本集正文的记录；集纲侧审读不算首读，也不需要封存。
2. **次读**：另起上下文，用 `context-pack --role evaluation` 装包；事实与目标条款是否达成；每条 finding 写 `cites.targetClause`（台词目标或任务目标的条款）或 `cites.factEvidence`（事实证据），两者都没有的标 `kind: preference`，不进修订单。审读不改台词目标，认为目标缺了一条就写 `changeProposals`。
3. **冷读复述**：新上下文，`context-pack --role cold_reader`，包里只放本集正文一项，不放前集、分集计划、对话表、作者说明与样本。读者复述发生了什么、谁做了什么为什么，每条关键信息写“从第几行哪句知道的”，说不出就写“不明”。存成 `retell-record`（`target.kind: episode_text`，记 `promptVersion`），`retell-check <复述> --plan <对话表> --episode-plan <分集计划>` 对照信息清单；`missing` 回 C5a。提示词版本不同的两次冷读不直接比。
4. **处境对照**：新上下文，`context-pack --role situation_checker`，装正文、对话表与它引用的正例和对照对；逐个话题答对话问题单（`dialogue-check-questions`），每答引用行号与原句，写成立／不成立与原因，原因回到处境，不打分、不合成总评；`check-answers <回答>` 核格式。同一集做了两份以上时，用 `answers-consistency <甲> <乙>` 记一致性。
5. **设计依据一致性**：脚本先核 `plan-text-consistency <对照表> --dialogue-plan <对话表> --episode-plan <分集计划>`（说话人序列、段边界、打断位置、收尾）；再由模型逐话题对照 `shape` 与 `reason` 答一致／不一致与哪里不一致，不评理由本身对不对。`dialogue-diagnose <正文> --dialogue-plan <对话表> --episode-plan <分集计划>` 给出诊断信号与所在话题，只提示先看哪一段，不与任何区间比，不作判定。

不一致或不成立的项进修订单（`revision-list` 记录，放 `.drama/checks/`，写好先跑 `contract-check revision-list <文件>`）。修订单只引用对话表元素、约定条目或处境对照的句子与原因，不写替换台词，不写“缩短这句”“加一次换人”这类数值指令。修订先改对话表再改正文，修订后再做冷读复述与处境对照；`preserved`（不许动）只认人工来源，每项写 `{item, noteId}` 或 `{item, humanWords}`；模型审读认为好的句子按上面写进 `goalAssessments[].evidence`，不进不许动清单。见 [修订](../dialogue-structure.md#8-修订先改表再改文修订单不写替换文字不写数值修订后复读)。

## 审读包装什么

- **正文引用到的前文场面必须装进审读包。** 待审正文回指、复用或兑现了前文的某个场面（道具、承诺、旧伤、某句台词），就把那一场的原文区间列进选材清单；只装“前一集”不够。缺了它，审读会把正当的回扣误判为“新设事实”或“前后矛盾”（D2 的 f5 误报即由此而来）。拿不准是否引用了前文时宁可多装，超预算就缩小审读单元。
- **首读包里的“前一集”若已精修，装精修稿，不装原稿。** 观众看到的是精修后的前一集；拿原稿当前文，衔接问题会被误报或漏报。选材清单里按 pageId 引用该集最新的已精修修订（`remote_page`，修订号取已缓存的修订；迁移前的历史候选按 slot 引用 `remote_artifact`）；精修稿尚未写成页面、只在本地时，作为 `local_file` 装入（见 [定向修订单独装包](README.md#定向修订单独装包)），并在 `reason` 写明“精修稿”。
- 一次审读覆盖多份候选（按批审读）时，`review-record.target` 填第一份，其余填 `additionalTargets`（同 `ref` 结构），不要塞进 `readingScope`；`readingScope` 只写实际读过的材料。
- 首读与次读各装一个包时，`run-handoff.contextSnapshotId` 填首读包，次读包写进 `additionalSnapshotIds`；任一包里的前文被修订，`impact` 都会把这次审读标为 `stale`。

## 停止与边界

评分不是采用；无硬矛盾不代表本轮修改目标已达成。审读不产生新约束。返修次数不超过 `task.revisionBudget`；触顶后不再改，两处都做：未处理的审读意见写进交接 `unfinished`（`goal` 记 `partially_met`，写明瓶颈），并用 `decision add planning/decisions.json --from-handoff <交接>` 登记进决定队列、带默认，流程按默认继续，不停下等人。审正文后的修订，预算算的是 C5a 的对话表修订次数。
