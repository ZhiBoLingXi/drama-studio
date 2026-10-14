# 集纲层：功能地图、底账、季编排与分集计划

本页是集纲层的操作手册，写给执行的 AI：每一步做什么、产物放哪、跑哪条命令、退出码怎么读。新项目和新写的集纲默认走这里；人物、选题、送审的安排仍按 [策划](planning.md) 与 [两次审批](approval-flow.md)。工位对象的契约见 [创作工位契约](workstations/README.md)。

每条规矩标层级：**S** 是随包脚本能核的，**R** 是 mali-story 服务端保证的，**M** 是模型照做的约定。验收只引用 S／R；M 项写进记录作证据，不作通过条件。随包脚本永不联网、不调模型。

本页的例子都是为说明而编的：小镇上的老陈三年前往老家寄过一个箱子，舅妈王姨签收后没告诉他，镇口小卖部的刘叔知道一点内情。不取自任何真实项目。

## 1. 总览：C3a → C3b → C3c → C4，两处人审不变

| 层 | 做什么 | 产物（项目目录下） | 交接条件 |
| --- | --- | --- | --- |
| C3a 功能地图 | 每条线要完成的功能；每个功能的候选实现；跨线的前提问题；选定实现；全剧结局、因果链、不可逆选择、埋设与回收位 | `planning/function-map.json` | 每个功能有 `selected` 实现或已按 §11 登记保留；选定实现的回答记录里没有承重且未登记的 `notHolds`；`losesFunctions[]` 非空的候选没被选定；勘误清零（S） |
| C3b 底账与现实核对 | 六类账的条目、来源与状态；检索写 K1 卡；追问单回答 | `planning/ledger/ledger-ep000.json`、`knowledge/cards/`、`.drama/checks/` | 功能依赖的条目都在；选定之后 `contested` 为零；未核清单、戏剧假定清单可生成（S） |
| C3c 季编排 | 把功能分到集；每集事件粗列与★；容量粗估；装不下时选动作；埋设与回收位 | `planning/season-plan.json` | 每集有容量记录，超出的集有动作；每个埋设有回收位（S） |
| C4 分集计划 | 按季编排的分配把一集写成计划，声明对底账的读写（计划轨） | `planning/episodes/episode-plan-<NNN>.json`、`planning/ledger/delta-ep<NNN>.planned.json` | `plan-check` 全过；追问单对本集关键动作答完；冷读复述记录在（S＋M） |

决定队列放 `planning/decisions.json`，各层都往里登记。集号一律三位数字，拆出来的半集写 `006A`。

其余产物的位置：任务对象放 `.drama/tasks/`，选材清单放 `.drama/selections/`，媒介档案放 `planning/media-profile.json`，`ledger apply` 写出的新修订放 `planning/ledger/ledger-ep<NNN>.json`，跨前提一致性表放 `planning/premise-consistency.md`（§3）。快照由 `context-pack` 自己写进 `.drama/snapshots/`，不要另存它的标准输出。`init-project` 除 `planning/` 外还建 `runs/`、`knowledge/`、`planning/ledger/`、`planning/episodes/`；`.drama/runs/` 在第一次写交接时建。

**启用了集纲层的判据**：项目里有 `planning/season-plan.json`、`planning/function-map.json`，或 `planning/ledger/`、`planning/episodes/` 下有 JSON 记录，任一项即是。只有 `planning/` 不算（旧项目也有这个目录，里面放旧的框架与集纲文件）；`init-project` 刚建的空目录也不算，写出第一份集纲层记录才算启用。本页凡说「启用了集纲层的项目」都按这条判；C4 装包要季编排与底账、`season-check` 的旧集纲规则是否认 `episode-plan` 记录，都用这条判据。`season-check --outline` 的集纲层七条用的是另一个条件：项目里有 `planning/season-plan.json` 才跑。所以 C3c 写出季编排之前（只有功能地图或底账时）项目已算启用，七条却还不核。

人审点仍是两处：选题确认、送审包审批。前提问题、用户给定设定的去留、容量提案都进决定队列并带默认，流程按默认继续，它们不是人审点。

C1 定位与 C2 人物不变，C2 只写人：欲望、顾虑、策略、关系、能力边界。钱的来路、程序、空白期各方做了什么，进底账，不进人物小传；小传里「他三年里做了 X」这类句子要有对应的时间线账条目，否则写成待定。

**两条轨。** C4 写计划轨 delta；C5 正文写完后，`run-handoff.stateChangeProposals[].ledgerDelta` 写实际轨 delta（`delta-ep<NNN>.actual.json`）。下一集的入口接实际轨；还没有正文时接计划轨并标「待正文对齐」。入口状态记录 `runs/state/after-ep-<NNN>.md` 由 `ledger replay --track actual --md` 从实际轨导出，不再手写。两轨对不上时 `ledger diff` 列出差异，交下一集 C4，不判谁对。

**装包角色与运行记录。** C3a 用 `context-pack --role function_mapper`，C3b 用 `ledger_keeper`，C3c 用 `season_planner`，C4 用 `author`；追问单的作答与复核用 `fact_check`；分集计划冷读用 `cold_reader`（与正文冷读同一角色，靠 `target.kind` 区分）。C3a／C3b／C3c 的运行记录写 `workstation: C3`，另加 `layer: C3a`、`C3b` 或 `C3c`。集纲侧审读的每条 finding 必带 `cites`（§7）。C4 作者包须有三件：季编排（`planning/season-plan.json`）、底账修订（`planning/ledger/ledger-*.json`，是修订文件，不是 delta）、功能地图（`planning/function-map.json`），缺一件不装包（S）。知识卡按选材清单里的卡片项装（不走 `local_file`）；交接里写的 `knowledge/cards/<id>@r<n>.json` 与包里同一张卡同一修订视为同一份。集纲侧审读（C6 读分集计划、功能地图、底账或季编排）的 `task` 填可选字段 `target.kind`（`episode_plan`、`function_map`、`ledger`、`season_plan`；读正文时是 `episode_text`），填了集纲侧的值就不需要 `dialogueTarget`。底账全账不进包，按分集计划的 `reads` 只装引用到的条目。

**审读由新上下文写。** 集纲侧的 `review-record`（读功能地图、底账、季编排或分集计划）由没参与写作的新上下文写，作者不写。作者在自己的交接或汇总里做的 `serial_self_review` 不算审读。

**离线。** 集纲层的离线与正文同法（见 [离线与单代理降级](writing.md#离线与单代理降级)）：只有已有远端项目暂时断线，或用户明确同意只交本地稿（把原话记进 `PROJECT.md`），才走离线；本该存成页面的分集计划可读稿，回执记 `not_sent`；关口跑 `season-check --outline <起-止> --allow-offline`。

**旧项目。** 没有启用集纲层的项目，行为不变：`season-check --outline` 照旧只核旧规则（输出不带 `ruleSet`）；旧文件一律不动、不搬。

## 2. 功能地图（功能句、候选、步骤与 `origin`、`losesFunctions`）

工位的输入、产出与交接见 [C3a 功能地图](workstations/c3a-function-map.md)。

**线与功能。** 一部剧拆成若干线（`threads[]`），每条线若干功能。功能句分三半写，三半都要有：

| 半句 | 字段 | 例 |
| --- | --- | --- |
| 观众感受到什么 | `audienceFeels` | 替老陈着急：他以为东西早到了 |
| 谁知道了什么 | `whoLearnsWhat` | 观众先于老陈知道箱子没到 |
| 局面怎么变 | `situationChange` | 老陈从放心变成起疑 |

功能不写画面和手段。检验办法（M）：把实现整个拿掉，功能句还读得通。功能服务别的线时写 `alsoServes[]`。功能状态 `open／selected／dropped`；`dropped` 必须写 `droppedCost`（哪半句落空、后面哪几集受影响），而且 `dropped` 只能由主创的决定产生，系统不默认删功能。

**候选实现。** 每个功能下若干候选（`candidates[]`），现行或用户给的实现先登记为候选 A。候选写：

- `description`：一两句做法。
- `steps[]`：每步 `stepId`、谁、做了什么、出处（`where: {source, episode}`），可带自己的 `origin`。
- `ledgerDeps[]`：这个实现要世界是什么样，一条一个断言，带 `depId`、`kind`（六类账之一）、`claim`、`assertion`。`assertion` 取 `stated`（材料写了）、`required_unstated`（实现要它成立，材料没写）、`absence`（靠某事没发生才成立）。已有底账条目时填 `entryId`。
- `inquiryRef`：这个候选的追问记录 id。
- `requiresPremise[]`（引用前提，§3）、`dependsOnCandidates[]`（可跨线）。
- `weakensFunctions[]`：选它会削弱哪些功能；`losesFunctions[]`：选它会让哪些功能的哪半句落空。
- `status`：`candidate／selected／rejected`；被否的写 `rejectedBecause[]`。
- `patchCount`：原地修补次数（§7）；迁移时查不到填 `null`。

**来源 `origin`。** 取 `user_given`（用户给的）、`user_given_modified`（用户给了大意、后来改了关键细节）、`designed`（系统设计）、`writer_revised`（编剧改过）。步骤各记各的；候选级取它所有步骤里最「用户」的那个（S）。

**线级。** `threadLevel` 写结局、不可逆选择、埋设与回收位。原剧情框架的「结局与因果链」写在这里；分卷蓝图挪到季编排（§8）。

**选定规则（S）。**

- `losesFunctions[]` 非空的候选不得标 `selected`，只能作决定队列的一个选项。
- 选定候选的回答记录里，每条承重的 `notHolds` 都有去处（§5）。
- 一个 `selected` 功能恰有一个 `selected` 候选。
- 追问时发现的功能地图转述错误记进回答的 `mapErrata[]`，交接前清零。清零要另一份新上下文的复核记录确认：它在 `errataConfirmed` 里写 `{ref: "<checkId>#<序号或 errataId>", fixed: true}`。只为确认勘误的复核记录写 `target.kind: errata_check`，`answers` 可以为空；写了 `errata_check` 却没有 `errataConfirmed`，`check-answers` 报错。`function-map check --stage v1` 逐条核，作者自己确认不算；已被取代的记录里的勘误不要求。

分线并行写时，每条线一个文件（`T-<线>.json`），用 `function-map merge` 合成一份。写作中跑 `function-map check --stage v0`，交接前跑 `--stage v1`。

## 3. 前提层与 C3a 内的顺序

写作任务书的随包条款与装包见 [C3a 功能地图](workstations/c3a-function-map.md)。

C3a 与 C3b 交错进行，按下面的顺序，不是先写完候选再查：

| 步 | 做什么 | 谁 | 层级 |
| --- | --- | --- | --- |
| 1 | 列功能；现行或用户给的实现登记为候选 A，写 `steps` 与 `ledgerDeps` | 写作方 | S：结构；M：拿掉实现功能句仍读得通 |
| 2 | `function-map topics` 归并检索题目：`kind: procedure` 的断言，以及 `money`／`object` 里 `required_unstated` 的断言（标 `realWorldRule: false` 的除外）；`knowledge`、`agenda`、`timeline` 讲的是戏里的人，不出题。检索代理逐题写 K1 卡（§6） | 脚本归并，检索代理写卡 | S：每题有卡（查不到的是空卡）；M：卡的内容 |
| 3 | 候选 A 过追问单；缺口去重，标承重与依据（§5） | 新上下文的核对方 | S：格式、覆盖、跨记录一致性；M：答案 |
| 4 | **前提问题**：把跨线的根缺口归并成若干问题，每题 2–3 个真不同的候选、一个默认、一条决定队列条目（`kind: premise`） | 写作方 | S：有默认、有队列条目、候选不少于两个；M：候选真不同 |
| 5 | 前提靠着的未核假设是新检索题目；标了 `collapseIfFalse` 的先查 | 同第 2 步 | 同第 2 步 |
| 6 | 默认前提的组合过追问单（对象类型 `premise`）；填跨前提一致性表 | 新上下文的核对方 | S：回答记录的格式；M：答案与表的内容、表有没有空格 |
| 7 | 分线写候选实现，用 `requiresPremise[]` 引用前提；过追问单；选定或按 §11 登记 | 写作方 → 核对方 | §1 的交接条件 |

**前提对象**（`function-map.premises[]`）：`premiseId`、`question`、`candidates[]`（每个带 `description`、`origin`、`unverifiedAssumptions[]: {claim, collapseIfFalse}`、`weakensFunctions[]`、`losesFunctions[]`）、`default`、`defaultReason`、`decisionRef`、`inquiryRef`。例：「王姨为什么三年没告诉老陈箱子被退了」是礼物线、空白期线、婚事线共同的根，先定它，再分线写。

**跨前提一致性表**有三张，写在 `planning/premise-consistency.md`：逐方的总时间线（每一方每个时段做了什么、没做什么、为什么）、钱的总表（每笔的来路、去向、谁能动、留痕）、谁知道什么。每格要么有内容，要么写明登记（`unstated`、`whyMissing`）。这张表是 M：没有命令核它，由核对方对着它作答时看有没有空格。总时间线对应 `ledger view --blank-period` 的总账视图：C3a 阶段对功能地图跑（`ledger view planning/function-map.json --blank-period --md`），视图按线列出 `ledgerDeps`；C3b 写出底账之后对底账跑，才按方列（每一方每个时段）。项目特有的表由断言决定要不要，不进技能规则。

**检索是迭代的。** 功能地图 → 检索 → 追问 → 前提 → 再检索 → 再追问，通常不止一趟。卡比追问晚到时，按 §6 的 `impact --card` 找出要重答的回答。

## 4. 六类账与条目状态（含时间线子型 `state`、两轨、戏剧假定 `license_pending`／`accepted_license`）

底账是功能地图、季编排、分集计划、正文共用的状态对象。工位的输入、产出与交接见 [C3b 底账](workstations/c3b-ledger.md)。全剧级事实只在这里定：分段作者读它、引用它、提议改它（`changeProposal` 到 C3b），不自己写。

**通用字段**：`id`（稳定，如 `L-obj-003`）、`kind`、`title`、`origin`（另有 `derived_from_text`：正文写出来后登记的）、`status`、`introducedAt`（`pre` 或集号）、`realityRef[]`（K1 卡，引到条）、`inquiryRef[]`、`notAsked`、`tension`（不互斥但别扭，只登记）、`dependents[]`（功能与集）、`patchCount`、`history[]`。

**六类账：**

| `kind` | 专有字段 | 管什么 |
| --- | --- | --- |
| `timeline` | `when`、`who`、`where`、`did`／`didNot`（至少一个）、`why`、`unstated`、`knownTo[]` | 谁在何时何地做了什么；在场核对读它 |
| `money` | `amount`（量级）、`from`、`to`、`account`、`whoCanMove`、`trace`、`procedureRef`、`emptyFields[]` | 每笔钱的来路、去向、谁有权动、留痕 |
| `object` | `object`、`holder`、`location`、`howItGotThere`、`state`、`visibleTo[]` | 东西在谁手里；同一修订里一件东西只在一处 |
| `knowledge` | `who`、`knows`（一条一事实）、`since`（可细到拍）、`how`、`notKnows[]` | 谁知道什么；观众记为 `who: 观众`；对话表 `listenerKnows` 的来源 |
| `procedure` | `name`、`realWorldRule`、`currentClaim`、`claimVsRule`、`nextNecessaryMove: {mandated, customary}`、`state`、`usedIn[]` | 程序与行业做法；`mandated` 须引卡，`customary` 无出处、按未核对待 |
| `agenda` | `party`、`goal`、`means`、`constraints`、`nextMove`、`validFrom`／`validTo` | 各方此刻图什么；被程序或时间线条目引用的图谋必须登记 |

**时间线子型 `state`。** 带起止时间的法律、人身、关系状态（谁是谁的监护人、某人是否在押、两人是否已离婚）写成 `kind: timeline` 加 `subtype: state`，字段 `stateOf`、`state`、`validFrom`、`validTo`。不另立第七类。

**材料没给的，登记不编。** 某一方在某段时间材料什么都没写，登一条 `unstated`，不省略。`ledger check` 与 `contract-check ledger-entry` 用同一套必填项，另有下面七条：

1. 时间线的 `did` 与 `didNot` 至少一个非空。
2. 没有 `why` 时须标 `whyMissing`（缺，脚本报）、`whyNotApplicable`（这条不需要理由）或 `whyPartial`（只给了一半）之一；标了 `whyNotApplicable` 就不要再写 `why`。
3. `state` 子型的 `stateOf`、`state`、`validFrom`、`validTo` 四个键都在，前两个非空；不要求 `knownTo`。
4. 程序账的 `realWorldRule` 为空，只能是 `status: unverified` 并带 `notFound`。
5. 钱的六个字段（`amount`、`from`、`to`、`account`、`whoCanMove`、`trace`）为空，只认列进 `emptyFields[]`。
6. 知识账只记 `notKnows` 时，`knows`、`how` 可以空。
7. 其余字段写 `null` 要登记：把字段名列进 `emptyFields[]`，或写 `whyMissing`／`whyNotApplicable` 任一，即算登记。

图谋的 `validTo` 为 `null` 表示仍在生效。`money-closed`：空字段列进 `emptyFields[]` 就算交代了，不必另写；`trace` 写 `no_trace` 时仍要写理由。

**条目状态：**

| `status` | 意思 | 追问时 | 进哪份清单 |
| --- | --- | --- | --- |
| `asserted` | 设计中，还没核 | 照常问 | — |
| `verified` | 有出处，或落到它的各问都成立；`notAsked` 的条目不得标（S） | — | — |
| `unverified` | 查过，没查到出处 | 引用它的回答记 `not_evaluable` | 未核清单 |
| `contested` | 与另一条互斥，带 `conflictKind` | 照常问 | 选定之后须清零 |
| `license_pending` | 不合常规或没有出处，系统按 §11 的默认先保留 | 已登记，不再拦交接 | 戏剧假定清单（标「待确认」）＋决定队列 |
| `accepted_license` | 主创明知不合常规仍保留；须有 `humanWords`（S） | 同上 | 戏剧假定清单 |
| `retired` | 换实现后退役 | — | — |

`unverified` 是不知道对不对；两种戏剧假定是知道不合常规、仍然留着。三者在送审包里分开列，不互相代替。一条戏剧假定只豁免它自己那一处，由它带出的知情、动机、后果照常问。

**矛盾分类 `conflictKind`**：`world`（同一世界里只能成立一头，回 C3a 换实现或登记决定）；`source_variant`（用户给的写法与现行材料不同，进决定队列，默认按 §11）；`layer_variant`（两层现行材料写法并存，系统内定以哪层为准，不进队列）；`rule_implied`（字面不相顶，互斥来自卡上的规则；记所依据的卡，卡修订时重判）。同一方重叠时段两条图谋手段互斥，由 `agenda-exclusive` 报。

**阶段。** 选定候选、旧实现的条目标 `retired` 之前叫 `pre-select`：底账登记的是候选 A 的世界，矛盾本来就该在。这时跑 `ledger check --stage pre-select`，矛盾、`why` 缺失、钱的空字段只报不拦。选定之后跑默认阶段，它们拦交接。

**分段写账。** 三段以上并行写时，先定好 schema 再分段；跨段补充写 `amendments[]`；用 `ledger merge` 合并，它校验同名字段类型一致。

**两轨文件。** `ledger-ep000.json` 是前史账（C3b）。`delta-ep<NNN>.planned.json` 由 C4 写，`delta-ep<NNN>.actual.json` 由 C5 之后写，各带 `episode`、`track`、`reads[]`、`writes[]`（`entryId` 或新条目、`change`、`reason`、`supportedBy`：本集的 `sceneId` 或 `beatId`）。`ledger replay --at <集> --track planned|actual` 从 ep000 按集序重放出任一集的账；`ledger apply` 写新修订（放 `planning/ledger/ledger-ep<NNN>.json`）。

## 5. 追问单（16 问、信息题、`answerKind`、承重缺口的三个去处、`disposition`）

**对象。** 一个候选实现（`candidate`）、一个前提（`premise`）、一个关键动作（`move`，C4 与修订时）或一条底账条目（`ledgerEntry`）。**作答的是新上下文的核对方（`--role fact_check` 装包；包里的 K1 卡 `usage` 不能是 `evaluation_only`），不是写作方。** 标准是 K1 卡；以往审查的结论只作旁证。

**问题单**是随包数据 `schemas/data/reality-check-questions.json`（当前 v1），题干以数据文件为准。题干合并为 v2、「材料全程没写」的自动检索，都推迟到用正式工具重做项目验证那一轮再定（D6-1 设计决定的修订行）；在那之前照 v1 作答，「没写」类结论照写 `searchScope`。

| 组 | 问 | 要点 |
| --- | --- | --- |
| A 动作与动机 | 1 更省事的做法 | 他为什么没做？答案要是具体障碍，「没想到」不算 |
| | 2 图什么 | 做成得到什么、做不成失去什么；对手每一步必问 |
| | 3 心理前提 | 这个年龄、这种处境的人会这样想、这样做吗 |
| B 机构与他人 | 4 机构的必然动作 | 对着程序账的 `nextNecessaryMove` 答 |
| | 5 其他知情人 | 逐个列他们会做什么 |
| | 6 多久被发现 | 谁最先发现，为什么到现在没被发现 |
| C 信息与物 | 7 怎么知道的 | 信息链每一环 |
| | 8 怎么到这儿的 | 东西或钱经过谁的手、留什么痕、谁有权动 |
| | 9 名目后面的实体规则 | 谁有资格、几天、什么条件、出处 |
| | 10 物理与技术前提 | 成立吗，出处 |
| D 巧合与后果 | 11 巧合 | 开场可以有一个；解难题的不行 |
| | 12 后果 | 按现实的后果写了没有 |
| E 总账与前提 | 13 空白期总账 | 对着 `ledger view --blank-period` 答 |
| | 14 去掉实现功能还成不成 | **信息题** |
| | 15 是不是用户给定 | **信息题** |
| F 知情 | 16 凭什么知道他据以行动的事实 | 信息来源是哪一环 |

每问带 `answerKind`：第 14、15 问是 `informational`，照答，不参与 `outcome`；其余是 `tristate`。项目可以增问（带 `source`），不能删问（`contract-check question-set --base-questions` 核，S）。本轮只问部分题时在记录里写 `askedSubset`。问题单不必复制进项目，装包时选材写 `{"kind": "local_file", "id": "question-set:reality-check-questions@v1"}`，`context-pack` 从随包 `schemas/data/` 按 id 读。

真正问得出东西的是 A、B、E 三组（动机、他人与机构、总账）；C 组多半只查出「没有出处」。知识、图谋、时间线三类断言不靠追问逐条落，由底账脚本管（`knowledge-monotonic`、`speaker-knows`、`why-missing`、`agenda-exclusive`）；`assertion: absence` 的断言由总账视图与 `why-missing` 核。

**回答记录**（`answers`，放 `.drama/checks/`）：`checkId`、`target: {kind, id}`、`questionsVersion`、`promptVersion`（必填，由 `check-answers` 把关，缺了报错；`contract-check answers` 不查它）、`cardRevisions`（作答时读到的卡修订）。一份记录覆盖多个对象时，`target.ids` 列出它们，每答须写 `subject`（取 `ids` 里的一个：动作 id 或候选 id）。每答：

- `q`、`landsOn`（步骤、断言、`<集> 场 <场号>` 或底账 id）、三态 `holds／notHolds／not_evaluable`（不适用写 `n/a`）、非空 `reason`；涉出处的 `realityRef` 引到卡里的条。
- `not_evaluable` 带 `because`，可带 `leaning ∈ against／for／none`。`because` 三个值这样分：`no_card`＝没有覆盖这个题目的卡；`card_says_not_found`＝有卡，卡上这一条写明查无出处（卡 `coverage: empty`，或这条 `support: not_found`）；`cannot_answer`＝有卡，但卡不涉及这一问。
- `notHolds` 带 `defectKey`（同一处缺口同一个键）、`defectKind`（如 `contradicts_reality`、`missing`、`internal_conflict`、`motive`、`knowledge_gap`、`consequence_unwritten`）、`loadBearing`。
- `loadBearing: true` 的另带 `loadBearingBasis ∈ stated_in_record／has_downstream／function_sentence_step` 与一句 `loadBearingWhy`（去掉这一步，哪个功能句落空）。承重由核对方作答时填，不事后推。
- 缺口其实在上游实现的，写 `inheritedFrom`／`inheritedAt`；对换过的实现认出补丁修法的，写 `patch`（§7）。
- 「材料全程没写」类回答（`defectKind` 含 `missing`）写 `searchScope: {files[], method}`：查了哪些集、怎么查的。没写只报不拦。

**承重缺口的三个去处**，记在 `disposition: {to, ref}`，它是唯一来源：

| `to` | 条件 | `ref` 引什么 |
| --- | --- | --- |
| `confirmed_gone` | 换实现后，**新上下文的核对记录**确认它不再出现；写作方自报不算 | 那份核对记录 |
| `license` | 登记为戏剧假定：底账条目 `license_pending` 或 `accepted_license` | 底账条目 id |
| `decision` | 进决定队列且带默认 | 队列条目 id |

不承重的 `notHolds` 写 `to: leaves_open`，进送审包的未核附录，不拦。承重的不能 `leaves_open`。

**作者自己写错的承重缺口。** 缺口出在作者的写法上、不需要换实现时，作者在修订预算内改，交新上下文复核；复核确认消失后，编排方回填原回答记录的 `disposition`（`to: confirmed_gone`，`ref` 引复核记录）。回填只动 `disposition`，原回答的三态与原因不改；`disposition` 为 `confirmed_gone` 且引用的是别的复核记录时，一律要写 `backfilledBy`（谁回填的；脚本分不出是不是回填，所以只要引的是别的记录就要求），`decision`、`license` 两种去处不要求；`ref` 不能指向本记录，被引的复核记录对同一 `defectKey` 不能仍判 `notHolds`（`check-answers` 核，S）。

**缺口在新实现下的结局**：`closes[]`（核对记录确认之后才计入）、`retiresWith[]`（所在实现整段退役，不算修好）、`leavesOpen[]`。

**`outcome`** 取 `pass／fail／fail_inherited／pass_with_unverified`，只是一眼看有没有不成立项，不作排序或通过依据。只有不承重的 `notHolds` 时可以写 `pass_with_unverified`。交接看的是「没有承重且未登记的 `notHolds`」。

缺口登记表不手写：`defects build --records .drama/checks/` 从回答记录生成。

## 6. 检索代理与 K1 卡（可联网、留出处；脚本不联网）

**检索代理可以联网检索**，这是技能的正式做法：有检索能力的宿主查公开资料（法规、部门规定、行业报道、技术文献）并留出处。边界是随包脚本永不联网；检索是宿主模型的能力，不是本地工具的功能。宿主没有检索能力时，涉及的条目标 `unverified`，`run-handoff.unknowns` 写「本次无检索」。

**输入**：`function-map topics <功能地图>` 归并出的题目（只出 `procedure`，及 `money`／`object` 里涉及现实规则的 `required_unstated`，见 §3；一题可对多条断言，带依赖它的功能、候选与集；不出题的数目列在 `notSearchable`），底账写出后再加程序账里 `asserted` 且 `realityRef` 为空的条目。题目不由编排方按线预估。

**产出**：一张 K1 知识卡，放 `knowledge/cards/`，原文片段放 `knowledge/sources/<sourceId>/`。卡上写查到的规则、与条目当前写法的出入、适用条件、来源日期。写法：

- 卡级 `coverage ∈ sourced／partial／empty`；`content.rules[]` 每条带 `support ∈ sourced／inferred／not_found`，`realityRef` 引到条。
- `evidence.sources[]` 必有，每条带 `sourceTier ∈ official／transcribed／superseded／commercial／news`；外部 URL 标 `external_not_checked`，不声称已核验。
- `usage` 取 `comparison_only` 或 `creative_reference`。
- 引公开个案时写 `caseFacts` 与 `distanceFromOurs`（它与本剧情形哪里不同构）；追问单引个案时带上这些差异。

**空卡**（`coverage: empty`）不能支持任何「通常怎样」：`contract-check answers --cards knowledge/cards/` 拒绝把空卡当 `holds` 的出处（S）。

**不做**：不改剧情、不给改法、不判这段戏成不成立；成不成立由追问单答。查不到不编造，条目标 `unverified`，卡上写查了什么、没查到什么。

**卡修订后**：`impact <项目> --card <cardId>` 列出装过旧修订的快照与运行；回答记录里的 `cardRevisions` 让你知道哪些回答按旧卡答过、要重答。主创或顾问哪天给了出处或说「不是这样」，经 `feedback-ingest` 回流成卡的草稿或条目修订。

[创作开发](development-lab.md#1-补充会改变选择的生活材料) 的生活材料要求（带来源、分清事实／陈述／推断／虚构）照旧；检索代理的 K1 卡就是这条要求在现实核对上的产物。

## 7. 修订规则（四种不允许的修法、`patchCount`、换实现预算 2 次后登记并继续）

**修订动作只有一种**：审读指出承重问题 → 定位到功能 id 与底账条目 → 在 C3a 为这个功能换实现 → 新实现过追问单 → 更新底账（`dependents` 列出受影响的集）→ 重写受影响的分集计划 → 重核受影响的线。

**不允许的修法**，核对方对换过的实现作答时记在 `patch`：

| `patch` | 是什么 |
| --- | --- |
| `added_explanation` | 在原实现上加一拍解释 |
| `layered_on_same_spot` | 在原处再叠一层（换了程序名目而实体规则不查也算） |
| `moved_elsewhere_or_coincidence` | 把不可信挪到别处，或挪到巧合上 |
| `removed_instead_of_solved` | 把实现拿掉，功能句落空 |

带 `patch` 的缺口不计入 `closes[]`（S）。

**C3a 写作任务书的三条**（M）：多个前提、相互依赖的功能一起选，不逐个求解再拼；每引入一个知情人、一份文书、一个账户，先写出它按常规接下来会做什么；每个默认候选里，标了 `collapseIfFalse` 的未核假设至多一条。

**`patchCount`。** 实现 id 不变、只改描述或加条目，计数 +1；换实现（新 id）归零。到 2 之后不能再原地修订，必须回 C3a 换实现（`season-check` 的 `outline-patch-cap`，S）。查不到历史时为 `null`，不触发。换了 id 而内容只改一句的，`dup-check --list-hits --k 8` 对新旧描述的重合可作提示，不拦。

**预算。** C3a 任务的 `task.revisionBudget` 是换实现的次数，默认 2。到顶后仍在的承重缺口登记为戏剧假定（`to: license`）或进决定队列（`to: decision`），流程继续，不再换，也不停下等人。

**修订范围按四种情形定**：自身没有缺口、只被上游拖累的，保留实现、换上游；自身有缺口但都不承重的，原地补并计 `patchCount`；自身有承重缺口的，回 C3a 换实现；没有缺口的不动。

**审读意见要有落点。** `review-record` 的 finding 带 `cites`（`functionId`、`ledgerId`、`targetClause`、`factEvidence` 之一）；一个都没有的归 `kind: preference`，不进修订单。对启用了集纲层的项目，集纲侧审读的 finding 必带 `cites`。

**编排方不下这类约束**：「不动集数」「不动标题」「不动★」「只改一次且不拆集」。`contract-check task` 按随包 `constraint-blocklist.json` 扫 `constraints[]`，命中即拒，不论 `origin`（S）。

## 8. 季编排与容量（两口径、动作 rearrange／split／drop_function，删线不作默认，数字不当裁判）

工位的输入、产出与交接见 [C3c 季编排](workstations/c3c-season-plan.md)。

**季编排对象**（`planning/season-plan.json`）：`revision`、`basedOn: {functionMap, ledgerRev, mediaProfile}`、`episodes[]`（每集 `episode`、`functions[]`、`eventsRough[]`、`star`、`capacity`）、`threads[]`（`plantId`、`plantedAt`、`payAt`）、`decisions[]`。原剧情框架的分卷蓝图（每卷戏核、压力源、代价、兑现、进出状态）保留为季编排的卷级视图；原框架的分集节拍表不再写。

**「这集为什么存在」**（M）：删掉这一集分到的那段，后续是否仍原样发生？仍原样发生的，这段要么挪走，要么说明它推进了哪个功能。

**容量怎么算。** 媒介档案（`media-profile`）只含物理量：目标时长、语速、停顿比；画面拍时长在量出来之前标 `pictureBeatSec: assumed`。粗估 = 信息条数 × 同类处境语料交换中位时长 ＋ 画面拍 × 画面拍时长。`capacity` 同时报两个口径（A：每条信息都按一次交换算；B：只算靠对白承载的信息，画面承载的按画面拍算），不给区间判定，退出码恒为 0（输入读不出时为 1）。

**没有项目档案或语料时**：不给 `--media` 就用随包默认档案 `schemas/data/default-media-profile.json`；不给 `--corpus`、`--exchange-median-sec` 时交换中位时长取默认 10.8 秒（真人剧语料 138 条量出）。漫剧没量过这个数，`--format anime` 又没有语料时要自己给 `--exchange-median-sec`。用了默认值的输出标 `basis.status: default_unmeasured`，`basis.defaults` 列出用到的默认项，退出码仍是 0。这些是别的剧量出的统计，不是本项目的测量；有了项目语料或项目档案（`planning/media-profile.json`）就换掉。

**超出时必须选一个动作**，记在该集 `capacity.action` 与 `actionDetail`（S：`exceeds` 而无 `action` 被拒）：

| 动作 | 做什么 | 代价登记 |
| --- | --- | --- |
| `rearrange` | 把功能挪到相邻集，或把一集的两个功能分给两集 | 受影响的埋设与回收位重登 |
| `split` | 一集拆成两集（`004A`、`004B`），总集数变 | 送审前自由；送审后是方向变更（[两次审批](approval-flow.md) §4） |
| `drop_function` | 某个功能不实现 | 功能地图标 `dropped` 并写 `droppedCost` |

**谁来选。** 送审前由季编排层在 `rearrange` 与 `split` 之间选，选择记进季编排的动作记录，不另找主创。`drop_function` 永不作默认：它只能作为决定队列里的一个选项；只有主创已经定了（条目 `decided` 且有原话），季编排才能记 `drop_function`，并在该集 `capacity.decisionRef` 引用这条决定（S）。送审后任何一层再超（分集计划复核、正文精估），登记为决定队列的 `capacity` 提案并带默认，流程按默认继续；默认拆法是按粗估比例拆成 N 段、本集只写第一段，其余登记为下一集的入口。

**数字不当裁判。** 数字只触发「必须选一个动作」或「提案要有默认」，不判这集合不合格；选哪个动作由哪个功能非在这一集完成不可决定。对标单集的事件数、场景数只作描述，不是配额。

## 9. 分集计划字段（14 字段，`summary` 可选）

C4 按季编排的分配把一集写成计划。输入：季编排本集条目、底账当前修订、前一集的实际出口（有正文时）、人物包。按顺序分段写，一段默认不超过 15 集、一个运行，前一段存好再给下一段装包，不并行。C4 不定任何全剧级事实、不改功能、不查证；需要时写 `changeProposal` 回 C3b 或 C3a。

| # | 字段 | 装什么 | 不装什么 | 必填 |
| --- | --- | --- | --- | --- |
| 1 | `episode`、`title` | 集号；标题（派生，可改） | — | ● |
| 2 | `entry` | `ledgerRev`（上一集实际轨，没有正文时计划轨）；一两句：故事日、谁在哪、手里有什么、知道什么 | 上一集钩子的复述；作者解释 | ● |
| 3 | `functions[]` | `functionId` 与本集推进到哪一步 | 新功能、新线 | ● |
| 4 | `events` | **自足**：`scenes[]`（`sceneId`、时间、地点、`present`：该场在场的人物，含不说话的，不含只被提到的）→ `beats[]`（`beatId`、谁做了什么、因为什么、结果；幕后事标 `offscreen`；必要的台词原话写 `quote`）；含集末最后发生的事 | 镜头指示、「留给正文」、跨集呼应说明、人物辩护、心理解释 | ● |
| 5 | `presence` | 每场在场；主要人物不在的理由（引时间线账） | 「在场：」后的作者说明 | 场数 ≥2 或涉机构时 |
| 6 | `moves[]` | 每个改变局面的动作：`who`、`did`、`wants`、`easierOption`、`whyNot`、`cost`；对手的动作必有，主角的选择也写在这里 | 复述事件、心理旁白 | ● |
| 7 | `infoLedger[]` | 观众本集必须拿到的事实：`infoId`、`facts[]`（一事实一条，`factId`、`carrierBeat`、`keywords[]`）、`whyAudienceNeeds`、`laterDependents[]`、`knownByInStory[]`（引知识账） | 情绪、氛围 | ● |
| 8 | `ledgerDelta` | 计划轨 `reads[]`、`writes[]`，每条 `writes` 的 `supportedBy` 是本集的场或拍 | 不引底账的自由文本 | ● |
| 9 | `realityRefs[]` | 本集用到的程序账条目 | 新的查证、「凭常识写」 | 涉机构、程序、技术时 |
| 10 | `threads` | `pays[]`、`plants[]`（季编排里预定的回收集） | 「第 N 集要用」类散句 | 有埋设或兑现时 |
| 11 | `exit` | `ledgerRev`（计划轨）；一两句状态；`closingEvent: {beatRef}` 指向最后一场最后一拍 | 下一集的事、悬念说法 | ● |
| 12 | `capacity` | `infoCount`、`sceneCount`、`pictureBeats`、`estimateSec`、`targetSec`、`basis`、`status: fits` 或 `proposal:<决定 id>` | 字数上限 | ● |
| 13 | `pending[]` | 决定队列条目 id 与本集采用的默认走法 | 没有默认走法的「待主创定」 | 有待定时 |
| 14 | `summary` | 可选：看点、情绪、爽点各一两句，给页面与拉片对照用 | `events` 里没有的人、物、事、台词 | 可选 |

旧集纲的写法去向：剧情框架 → `events`（自足，不设字数上限）；单列的「关键选择」→ `moves[]`；情绪铺垫、核心爽点、核心看点 → `summary`（`plan-check` 粗核它不含新实体，只报不拦）；结尾钩子 → `exit.closingEvent`（是事件，不是说法）。六字段不再是计划格式，也不再按「有没有关键选择」审集纲。

**例**（压缩，只示意结构）：第 3 集 `events` 两场：3-1 上午镇口小卖部，刘叔提起仓库在清退三年没人取的件；3-2 中午镇仓库柜台，仓管翻登记簿，签收人是王姨。`moves`：老陈去仓库问，`easierOption` 在家问王姨，`whyNot` 他还没疑心王姨。`infoLedger` 一条：箱子三年前已退回、签收人是王姨（承载拍 3-2.b1）。`ledgerDelta` 写箱子位置，`supportedBy: 3-2.b1`。`exit.closingEvent` 指 3-2.b1。

**本集要过的核对。** `plan-check`（引用存在、`closingEvent` 在末拍、在场、说话人在说话那一拍之前已知情、delta 有场拍支撑；`speaker-knows` 有核不了的说话人时状态是 `pass_with_not_evaluable`，看 `notEvaluable` 列表补底账）；`capacity episode` 复核；追问单对本集 `moves` 作答（对象 `move`）；冷读复述：先用 `plan-events <分集计划> --out .drama/checks/events-ep<NNN>.json` 导出只含 `events` 的版本（场留 `sceneId`、时间、地点、在场，拍留 `beatId`、`who`、`text`、`quote`、`offscreen`，`saysFact` 等设计字段去掉）；新上下文用 `--role cold_reader` 只装这份导出（包里只许一项本集材料，装整份分集计划退出码 2），复述谁在场、按顺序发生了什么、为什么、停在哪，记成 `retell-record`（`target.kind: episode_plan_events`，放 `.drama/checks/`），`retell-check` 对照 `infoLedger` 每个 fact 与 `closingEvent` 给出 `retold／partial／missing`；`missing` 回 C4。可读稿存为 `episode_outline` 页面（R）。

## 10. 决定队列（kind 词表、`default` 必填、`decided` 须 `humanWords`）

「待主创定」不再滞留：每件等人定的事登记进 `planning/decisions.json`（`{"entries": [...]}`），流程按默认继续，没有「等主创」这个状态。

每条字段：`id`、`kind`、`raisedAt: {layer, runId}`、`question`、`options[]`（每项 `optionId`、`text`、可带 `cost` 与 `losesFunctions`）、`default`（一个 `optionId`）、`defaultReason`、`affects[]`（功能、底账条目、集）、`status ∈ pending／decided`。`default` 与 `defaultReason` 必填（S）。

| `kind` | 用在 |
| --- | --- |
| `setting_conflict` | 用户给定实现与通过核对的候选实现之间 |
| `premise` | 前提问题的取舍（§3） |
| `license` | 「按现实改掉」对「作为戏剧假定保留」（§11） |
| `capacity` | 送审后的容量提案（§8） |
| `upstream_change` | 下游运行提出的上游变更（C5 的 `changeProposals`） |
| `other` | 以上都不是 |

规则：

- 提出决定的一方必须给默认；受影响的分集计划在 `pending[]` 引用条目并写本集采用的默认。
- 删功能永远只是选项，不作默认；默认是「保留用户给定的」时，按默认走不会替主创删掉任何功能。
- 运行交接里的 `changeProposals` 用 `decision add --from-handoff <run-handoff>` 登记，缺默认就登记不进去。
- 主创说了话才能改成 `decided`：`decision decide --id <id> --option <optionId> --human-words "<原话>"`，原话照记。之后 `affects[]` 列出要重写的集，按 §7 修订。
- 修订预算用完后，审读意见仍在的，两处都做：写进该运行交接的 `unfinished`（任务 `goal` 记 `partially_met`），并用 `decision add --from-handoff` 登记进队列、带默认（通常默认「按现稿交付」，另一选项是追加一次修订）；受影响的分集计划在 `pending[]` 引用这条。选了「再改一次」时，由编排方在预算用完的那一层（集纲侧通常是 C4）另开一次运行，另计预算 1 次，交接的 `decisionRefs[]` 写这条决定的 id（`contract-check run-handoff <交接> --decisions planning/decisions.json` 核引用存在，S）。不在预算之外悄悄再改。
- 编剧、顾问的意见经 `feedback-ingest` 记成 `writer-note`，决定类的回流成 `decided` 条目，同样带原话。

## 11. 用户给定设定的处理（`user_given`／`user_given_modified`、不成立时默认保留并标 `license_pending`）

用户给的设定圣经、梗概、前文进系统时拆成两样：功能（这条设定要完成什么，进功能地图）与底账条目（它断言世界是什么样），都标 `origin: user_given`；用户给了大意、后来改了关键细节的标 `user_given_modified`。设定圣经从此是输入材料，不再是另记时间线、道具位置、谁知道什么的地方：这些进底账。

追问单对用户给定的一字不少地问（第 15 问就是为此设的）。答不成立的，不改用户的条目，按下表走：

| 情形 | 系统默认 | 登记什么 |
| --- | --- | --- |
| 追问后有通过核对、且不让任何功能句落空的候选 | 按该候选继续 | 决定队列 `setting_conflict`：用户给定实现对候选实现，默认为候选；分集计划 `pending[]` 引用 |
| 预算内每个通过核对的候选都让某个功能句落空，或没有候选通过 | **保留用户给定的实现**，底账条目标 `license_pending`，流程按「保留」继续 | 决定队列 `license`：「按现实改掉」（逐项列哪些功能句落空）对「作为戏剧假定保留」，默认为保留 |
| 前提一级的取舍 | 追问之前一律保留用户给定的前提并标 `license_pending`；追问之后若出现不让功能句落空的合格候选，再按候选走（同第一行） | 决定队列 `premise` |

主创接受某条戏剧假定后，条目改为 `accepted_license` 并记 `humanWords`；没有原话不得标（S）。主创事后选「按现实改掉」时，`affects[]` 列出的集按 §7 重写。

这些都如实写进送审包：**设定核对报告**（每条 `user_given` 与 `user_given_modified` 条目的追问结果、候选实现、默认走法）放首页，紧接着是**戏剧假定清单**，其后是未核清单与决定队列。四份附录的位置见 [两次审批](approval-flow.md#2-一次提交四项材料)。这不是向主创提项目级问题，是把矛盾摆出来，而不是埋进补丁。

## 12. 命令速查（每步跑哪个命令、退出码怎么读）

命令都用 `python3 -B scripts/drama_tools.py <命令>` 运行（路径相对于技能目录），`--help` 看全部参数。输出是 JSON；**读结构化字段（`passed`、`errors`、各项 `status`），不要只看退出码**。通用约定：`0` 完成且规则成立；`1` 输入读不出或执行错误；`2` 有规则不成立。

| 步 | 命令 | 退出码怎么读 |
| --- | --- | --- |
| 建目录 | `init-project <项目> --title <剧名>` | 0 建好；建 `runs/`、`knowledge/`、`planning/ledger/`、`planning/episodes/`；不建远端项目 |
| C3a 合并分线 | `function-map merge <T-*.json 或目录> --out planning/function-map.json` | 2 合并被拒（同名冲突等） |
| C3a 检索题目 | `function-map topics planning/function-map.json` | 只归并，不检索；0；不出题的类与数目在 `notSearchable` |
| C3a 核功能地图 | `function-map check planning/function-map.json --stage v0｜v1 --rc-dir .drama/checks --decisions planning/decisions.json --ledger planning/ledger/ledger-ep000.json` | 写作中用 `v0`，交接用 `v1`；2 有结构错误或承重缺口没去处 |
| C3b 建账 | `ledger init --out planning/ledger/ledger-ep000.json` | 不覆盖已有文件 |
| C3b 合并分段 | `ledger merge <各段> --out planning/ledger/ledger-ep000.json` | 2 同名字段类型不一致等 |
| C3b 核账 | `ledger check planning/ledger/ledger-ep000.json --stage pre-select --cards knowledge/cards --function-map planning/function-map.json --decisions planning/decisions.json` | `pre-select` 下矛盾、`why` 缺失、钱的空字段只报；选定之后去掉 `--stage`，它们变成 2 |
| 总账视图 | `ledger view <底账> --blank-period --md`（C3a 阶段给功能地图，按线列；有底账后给底账，按方列） | 0；追问单第 13 问对着它答 |
| 某人知道什么 | `ledger knows <底账> --who <人> --at <集>` | 0；C5a 的 `listenerKnows` 初值 |
| 统计 | `ledger stats <底账>` | 0；未核、戏剧假定条数等 |
| 追问记录 | `check-answers <回答记录…> --function-map … --decisions … --ledger … --records …` | 2 格式错、承重缺口无去处、`confirmed_gone` 引别的记录却没有 `backfilledBy`、`errata_check` 没有 `errataConfirmed`；覆盖报告与 `--cross` 只报。`--records` 可给目录：只读其中的回答记录，其余文件跳过并列在 `recordsSkipped` |
| 两次作答对齐 | `answers-consistency <记录甲> <记录乙>` | 只报 |
| 缺口登记表 | `defects build --records .drama/checks --out .drama/checks/defects.json` | 从回答记录生成，不手写 |
| 回答与卡 | `contract-check answers <记录> --cards knowledge/cards` | 2 空卡被当作 `holds` 的出处等 |
| C3c 粗估 | `capacity season planning/season-plan.json [--media planning/media-profile.json] [--corpus <exchanges.jsonl>｜--exchange-median-sec <秒>] [--format live｜anime]` | 恒为 0（读不出为 1）；`basis.status: default_unmeasured` 表示用了随包默认值；超出时看输出里的提案占位 |
| C3c 核季编排 | `season-plan-check planning/season-plan.json --function-map planning/function-map.json --decisions planning/decisions.json [--media planning/media-profile.json]` | 2 超出无动作、功能没分到等 |
| C4 应用 delta | `ledger apply <入口修订> --delta planning/ledger/delta-ep<NNN>.planned.json --out planning/ledger/ledger-ep<NNN>.json` | 2 delta 应用出错（引用的条目不存在等）。规则另核：核本集 delta 用 `ledger check <入口修订> --delta <delta>`；核新修订本身用 `ledger check <新修订>`，**不带** `--delta`（带了会把 delta 再应用一次，`delta-applies` 报错） |
| C4 核计划 | `plan-check planning/episodes/episode-plan-<NNN>.json --ledger <入口修订> --season planning/season-plan.json --function-map planning/function-map.json --decisions planning/decisions.json` | 2 有规则不成立；`speaker-knows` 为 `pass_with_not_evaluable` 时不拦，补底账；`--characters <人物包>` 核小传里的前史有没有时间线账条目，只报不拦 |
| C4 复核容量 | `capacity episode <分集计划> [--media planning/media-profile.json]` | 恒为 0；同上看 `basis` |
| 冷读导出 | `plan-events <分集计划> --out .drama/checks/events-ep<NNN>.json` | 0；冷读包只装这份 |
| 冷读对照 | `retell-check <复述> --plan <分集计划>` | 恒为 0；看每个 fact 的 `retold／partial／missing` |
| 对象格式 | `contract-check {function-map｜ledger-entry｜ledger-delta｜season-plan｜episode-plan｜decision-queue｜answers｜task} <文件>` | 2 违反 schema 或跨字段规则 |
| 决定队列 | `decision add planning/decisions.json --entry <条目.json>`／`--from-handoff <交接>`；`decision list`；`decision decide … --human-words …`；`decision check` | 2 缺默认、缺原话 |
| 两轨 | `ledger replay planning/ledger/ledger-ep000.json --delta planning/ledger --at <集> --track actual --md`（`--delta` 可给目录，按集序重放，也可逐个给文件）；`ledger diff <甲> <乙>` | 0；`--md` 输出就是 `runs/state/after-ep-<NNN>.md`；`--md` 下 delta 应用出错时退出 2，错误写在「重放说明」一节 |
| 卡修订 | `impact <项目> --card <cardId>` | 列出要重装包、重答的 |
| 关口 | `season-check <项目> --outline <起-止>` | 有 `planning/season-plan.json` 的项目另核集纲层七条（`outline-season-assigned`、`outline-ledger-delta`、`outline-capacity`、`outline-reality-refs`、`outline-retell`、`outline-decision-default`、`outline-patch-cap`），输出 `ruleSet: outline-layer` 与 `outlineLayerRules`（七条各 `passed／failed／not_evaluated` 及 `evaluatedOn`）；2 不通过，不能写「已按流程完成」 |

这些命令核的是记录在不在、字段与引用对不对、规则成不成立，不判计划写得好不好。承不承重、答案对不对、复述得好不好是模型的判断，写进记录作证据。
