# C3a 全剧功能地图

[工位契约](workstations.md) · 契约 v0.1 · 方法见 [集纲层](outline-layer.md#2-功能地图功能句候选步骤与-originlosesfunctions)

| 项 | 内容 |
| --- | --- |
| 必读本剧依据 | C1 简报与类型承诺、C2 人物包、用户给定材料（梗概、设定、前文；进来时拆成功能与条目，标 `origin: user_given`）、已有 K1 卡 |
| 主要知识 | K1 现实出处（由检索代理写卡）、K3、K4、K8；没有知识缺口时可以不检索 |
| 产出 | 功能地图 `planning/function-map.json`（schema `function-map`）：每条线的功能、每个功能的候选实现（`steps`、`ledgerDeps`、`inquiryRef`）、跨线前提 `premises[]`、选定实现；全剧结局、因果链、不可逆选择、承诺与回收位 |
| 交接 | `run-handoff`（`workstation: C3`，任务 `layer: C3a`，装包角色 `function_mapper`）；被否定的候选留 `rejectedBecause`；前提与取舍登记进决定队列（`planning/decisions.json`），每条带 `default`；方向问题提 `changeProposals` 给 C1／C2 |

## 方法要点

- 功能句写「观众感受／谁知道／局面变化」，不写画面。把实现整个拿掉，功能句还要读得通；读不通说明写的是实现，不是功能。
- 现行或用户给定的实现登记为候选 A，`ledgerDeps` 一条一个断言（`depId` 必填）。程序类断言的检索题目由 `function-map topics` 归并，不由人按线预估。
- 顺序按 [前提层与 C3a 内的顺序](outline-layer.md#3-前提层与-c3a-内的顺序)：候选 A → 检索 → 新上下文追问 → 跨线根缺口归并成前提问题（每题 2–3 个真不同的候选、一个默认）→ 再检索 → 默认前提过追问 → 分线写候选并引用前提 → 追问 → 选定。检索与追问会来回几趟，不是一趟。
- 追问由没写这份地图的新上下文（核对方）作答，见 [追问单](outline-layer.md#5-追问单16-问信息题answerkind承重缺口的三个去处disposition)：装包角色用 `fact_check`，K1 卡的 `usage` 不能是 `evaluation_only`，问题单按 id 进包（选材清单写 `{"kind": "local_file", "id": "question-set:reality-check-questions@v1"}`，不复制进项目）。作者的自报不算核对；`closes[]` 每项要引用新上下文的核对记录。
- `losesFunctions[]` 非空的候选不能标 `selected`，只能作为决定队列的选项。用户给定实现不成立又没有合格候选时，默认保留并标 `license_pending`，见 [用户给定设定的处理](outline-layer.md#11-用户给定设定的处理user_givenuser_given_modified不成立时默认保留并标-license_pending)。

## 写作任务书的随包条款

下面这些随 C3a 的写作任务一起发给作者（M：作者照做；S：核对记录里 `patch` 字段在，带 `patch` 的缺口不计入 `closes[]`）。依据见 [修订规则](outline-layer.md#7-修订规则四种不允许的修法patchcount换实现预算-2-次后登记并继续)。

**四种不允许的修法**（核对方认出时记进回答的 `patch`）：

| `patch` 值 | 是什么 |
| --- | --- |
| `added_explanation` | 在原实现上加一拍解释 |
| `layered_on_same_spot` | 在原处再叠一层；换了程序名目而不查实体规则也算 |
| `moved_elsewhere_or_coincidence` | 把不可信挪到别处，或挪到巧合上 |
| `removed_instead_of_solved` | 把实现拿掉，让功能句落空 |

**三条规矩**：

1. 多个前提、多个相互依赖的功能一起选，不逐个求解之后再拼。
2. 每引入一个知情人、一份文书、一个账户，先写出它按常规接下来会做什么。
3. 每个默认候选里，标了 `collapseIfFalse` 的未核假设至多一条。

**修订预算用完后的动作**：C3a 的修订预算（`task.revisionBudget`）算换实现的次数，默认 2。用完后不再换；仍在的承重缺口按 `disposition.to: license`（底账条目标 `license_pending`，即戏剧假定）或 `to: decision`（进决定队列并带默认）登记，流程继续，不停下等人。

## 停止与边界

不分集（C3c）、不核底账条目本身（C3b）、不写人物（C2），不决定哪个功能可以不要（那是用户的事，只能作为决定队列的选项）。放行条件：每个功能有一个 `selected` 实现或已登记为保留用户给定的实现；选定实现的回答记录里没有承重且未登记的 `notHolds`；跨前提一致性表无空格（M，没有命令核）；功能地图勘误（`mapErrata`）清零。`function-map check` 与 `check-answers` 核格式和去处，不核答案对不对。
