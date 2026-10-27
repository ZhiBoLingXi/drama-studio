# 集纲层与台词层统一实施计划（D6）

日期：2026-10-14 · 版本 v1.1 · 状态：实施计划；D6-0 已执行一轮并停在 0.5 步（见 §4.1 与[中期报告](../d6/d6-0-interim.md)），D6-0 续与 D6-1 至 D6-5 未启动；本文档只是计划，写它与修订它都不改技能文件、脚本、契约、剧本、集纲 · 合并的两份方案：[集纲层架构 v1.2](drama-studio-outline-layer-architecture-2026-10-13.md)（下称「集纲方案」，主创 2026-10-14 已定六条架构取舍）与[台词系统架构 v3.2](drama-studio-dialogue-structure-architecture-2026-10-13.md)（下称「台词方案」，主创已批准 v3） · 依据：[系统架构 v1.2](drama-studio-system-architecture-2026-09-29.md)、[实施路线 v1.1](drama-studio-implementation-roadmap-2026-09-29.md)、第 6 集台词层验证（`projects/qige-xiongdi/runs/pilot-ep006/stage-a/b/d-report.md`、`capacity-ep006.md`）、三份审查（`projects/qige-xiongdi/reviews/`）

主创已定且实施期间当硬约束的规矩（§7 逐条给机制）：架构通用、项目差异进参数或数据；不新增人力环节，人工反馈来了就吸收；数字不当裁判；不打补丁，修订回功能层；编排方不下数值型或「不动集数」类指令；如实标未核实；随包脚本不联网、检索由代理做并留出处；私有剧本句子不出项目。

每个结论给理由；所有「S」都是设计层级，实现并有正反测试后才成立。举例处为说明而编；项目证据只引结论与文件位置，不抄私有剧本。

## 修订记录

**v1（2026-10-14）→ v1.1（2026-10-14，依据 [D6-0 中期报告](../d6/d6-0-interim.md)）。** D6-0 执行了一轮：任务 1–8 完成，任务 9（候选 B）在前提层两轮没有通过追问单后停下，任务 10–17 没有开始。主创 2026-10-14 原话：「停在这里先改方案」。这一轮暴露的修正点共 70 条（项目目录 `runs/pilot-v2/schema-findings.md`；逐条去处在同目录 `schema-findings-disposition.json`；中期报告成文时记 66 条）。v1.1 就地改了下列各节，被取代的说法不并排保留：

- **§1**：链路表的 C3a、C3b、修订、决定队列四行与图按新顺序、前提层、新交接条件改；送审包附录由三份改为四份（加戏剧假定清单）。
- **§2.1、§2.2、§2.3、§2.4**：对象、命令、文档改动清单按 D6-0 暴露的字段与规则同步。
- **§2.5**：新增五条定法（#15–#19：验收写法、用户给定设定与删功能、回路预算、追问与检索的先后及前提层、追问单的标准答案）；#6、#10 补一句。
- **§2.6**：#3（第 16 问两份问题单各写题干）、#6（「三处改法」改为「两处文案改法＋一条装包约束」）；新增 #15–#26，记 D6-0 修正点写进了两份方案的哪些节。
- **新 §2.8**：留给 D6-1 的设计决定（九项）。
- **§4.1**：改写为「已执行一轮，停在 0.5」，原步骤表保留并逐步标状态；新增「D6-0 续」（范围两个选项与默认、步骤、按新分判写的验收、退出条件、按实际重估的工作量）。被取代的是 v1 的验收第一条（「回答记录无 `notHolds`」）与 0.2 步「把审查结论当标准答案」。
- **§4.2、§4.3**：夹具来源与附录份数同步。
- **§5**：只补事实（D6-0 产出了什么、停在哪、主创给了什么输入）。
- **§6、§7、§8、§9**：风险表补 C3a 内部回路等六行并改三行；不变量补四行；等主创确认的事项加 #7–#9；任务清单标状态并给续做的顺序。
- **文末声明**：改为如实的现状。

---

## 0. 与现行路线图的关系

- **编号**：现行路线图 D0–D5 是唯一的阶段编号（[D0 记录](../d0/README.md)、[D2 门槛](../d2/knowledge-gate-report.md)、[D3 收尾](../d3/closure-report.md)、[D4-5 决定](../d4/shared-knowledge.md)、[D5 验证](../d5/release.md)）。本计划是**接在 D5 之后的新批次 D6「集纲层与台词层重构」**，内部分 D6-0 至 D6-5；证据页放 `docs/d6/`，写法同 `docs/d3/`、`docs/d4/`（只有编号、场号、统计与结论，不含私有正文）。
- **不重开 D0–D5**。但 D6 改的是它们交付的三样东西：D2 的「C4 集纲 → C5 正文 → C6 审读」闭环（变成 C4 分集计划 → C5a 对话设计 → C5b 正文 → C6 五读）；D3 的 C3（拆成 C3a 功能地图／C3b 底账与现实核对／C3c 季编排）；D4 的连续性记录（`runs/state/after-ep-NNN.md` 变成底账实际轨）。两份方案各自要求在路线图 D2／D3／D4 上「加注」，这一节就是那条注；路线图文件本身在 D6-5 加一行状态指到这里。
- **R0–R7 任务包不动**（两份方案 §18／§20 都这么写）。
- **技能版本**：现为 0.3.6。集纲方案写「0.5.0（0.4.0 留给台词方案）」，台词方案写「0.4.0」，但合并后的顺序是上游先于下游，所以改为按阶段递增：D6-1 → 0.4.0（只加对象与只读工具，旧流程可用），D6-2 → 0.5.0（切集纲层），D6-3 → 0.6.0（切台词层），D6-4 → 0.7.0（语料库与回流），D6-5 → 0.7.x。两份方案的版本号在 D6-5 回写。

## 1. 目标与范围

### 1.1 实施完成后的链路（一张表）

| 层 | 工位／运行 | 产物（对象，首版本地） | 负责 | 不负责 | S 核 | M 核 | 交给下游什么 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 语料库（工作室级或项目级，离线） | `corpus` 命令 ＋ 标注运行 | `dialogue-exchange`（带 `situation`、`walkthrough`）、`corpus-manifest`、`media-profile` 物理量默认值、`genre-lexicon` | 切交换、过滤、按处境标注、写结构说明；量语速与停顿比 | 判「适合本剧」；给任何分布区间 | 来源 `templateId@snapshotId`（缺时本地指纹并标明）；无 `walkthrough` 不入库；studio 级记录不含项目句子 | 双跑比对、反向预测 | 同类处境的正反例；媒介档案默认值 |
| C1 创作定位 | 不变 | 选题候选／创作简报 | 不变 | — | — | — | 类型承诺、核心矛盾 |
| C2 人物与世界 | 收窄 | 人物与世界包、声音探针 | 只写人：欲望、顾虑、策略、关系、能力边界 | 钱、程序、空白期各方做了什么（进底账） | 小传里的前史事件须有时间线账条目（`plan-check --characters`，报不拦） | — | 人物包 |
| C3a 全剧功能地图 | 新 | `function-map`（含 `premises[]`） | 每条线的功能；候选实现；跨线的前提问题（候选、默认、决定）；对每个候选与默认前提发追问单；选定；结局、因果链、承诺与回收位 | 功能分到哪集；底账条目核对；决定哪个功能可以不要 | 选定候选的回答记录里没有承重且未登记的 `notHolds`；`losesFunctions[]` 非空的候选未被系统选定；跨前提一致性表无空格；勘误清零；被否定候选有 `rejectedBecause` | 功能只写「感受／谁知道／局面变化」；缺口承不承重的判断 | 功能 id、`ledgerDeps`、检索题目 |
| C3b 底账与现实核对 | 新 | `ledger@ep000`、`ledger-entry[]`（六类账）、`reality-check[]`、K1 知识卡（出处） | 条目、来源、状态；检索代理查出处；追问单回答的记录；空白期总账视图 | 剧情；给改法 | `ledger check` 的规则（集纲方案 §10.2）；选定候选后 `contested` 为零（此前是 `pre-select` 阶段，只报）；`unverified` 清单与戏剧假定清单在 | 追问单答案（三态＋原因） | 当前修订的底账；未核清单 |
| C3c 季编排 | 新 | `season-plan` | 功能分到集；事件粗列与★；**容量粗估**；装不下时重排／拆集／删线（必选一个）；埋设与回收位；决定队列登记 | 每集内部怎么发生 | 每集 `capacity` 必填；超出时 `action` 必填；每个 plant 有 payAt | 选哪个动作由功能与人物定 | 本集分配、容量状态 |
| C4 分集计划 | 重构 | `episode-plan`（14 字段，9 必填）＋ 可读稿（存 `episode_outline` 页面）；`ledgerDelta(planned)` | 按季编排把一集写成计划：入口、场序列、在场、动作与动机、**信息清单（`facts[]`）**、状态变化、现实依据引用、承接与埋设、出口、容量复核、待定项、可选派生摘要 | 定全剧级事实；改功能；查证 | `plan-check`：引用存在、`closingEvent` 位置、摘要实体 ⊆ events、delta 可应用、容量复核；`retell-check` 对照 | 追问单对关键动作；冷读复述 | `infoLedger`、`presence`、知识账 → 对话表 |
| C5a 对话设计 | 新 | `dialogue-plan` | 场→话题→来回；每话题的处境与理由；每条信息（到 `facts` 粒度）由哪句承载；独白许可；留白；同处境正反例 | 措辞；事件与事实；任何句数字数目标 | 信息每条有 `carriedBy` 或画面理由；`situation` 齐、`reason` 引处境字段；每个 `segment` 有 `closer`；`listenerKnows` 不与知识账矛盾；无 `estimates` | 处境写得像不像话 | 对话表 |
| C5b 正文生成 | 重构 | 剧本正文 ＋ `plan-text-map` ＋ `stateChangeProposals(ledgerDelta)` | 照表逐话题写台词与动作行 | 增删话题、改信息分配、改事件 | 与对话表对齐；13 字档全库、8 字档对装包样本零命中；禁词零命中；`verbatimFrom` 标出人工句 | — | 正文；实际轨 delta |
| 底账实际轨更新 | 新（脚本） | `ledger@after-ep-N.actual` ＋ 两轨差异报告 | 应用 C5b 的 delta；与计划轨比对 | 判断哪边对 | `ledger apply --track actual`、`ledger diff` | — | 下一集 C4 的 `entry` |
| C6 审读 | 扩 | `review-record`、`retell-record`、`dialogue-check`、`plan-text-consistency` | 首读、次读（保留）＋ 追问单复核、底账一致性、分集计划冷读、正文冷读复述、处境对照、设计依据一致性 | 产生新约束；打分 | finding 必带引用（功能 id／底账 id／目标条款／事实证据），否则 `preference`；`check-answers` 核每答有落点、三态、原因；`retell-check` 覆盖 | 复述、回答本身 | 修订单 |
| 修订 | 重构 | 新 `function-map`／底账修订／分集计划／对话表／正文 | 回功能层换实现；先改表再改文；修订后必做冷读与问题单复核 | 原地加拍子；拿掉实现而让功能句落空；替换文字；数值指令 | `patch-cap`；换实现预算（C3a 默认 2）到顶后承重缺口登记、流程继续；修订单扫台词格式行与数值指令词表；`retell-after-revise` | — | — |
| 决定队列（合并容量提案） | 新 | `decision-queue` | 登记「待主创定」「容量三选一」「上游变更」「前提一级的取舍」「按现实改掉还是作为戏剧假定保留」，每条带默认走法与 `affects[]` | 等人 | `default`、`defaultReason` 必填；分集计划 `pending[]` 引用存在 | — | 送审包附录 |
| 人工反馈（可选，随时） | `feedback-ingest` | `writer-note` → 底账修订提案／K1 卡草稿／决定 `decided`／反例／对照对／`drafted` 约定与新问 | 来了就吸收 | 不是流程环节 | 无来源不入库；派生物带 note id | `whyNotHere` | 下次装包就用 |

### 1.2 一张图

```text
语料库（离线，只读）────────────────────────────────────────┐
  官方库拉片转写 → 交换 → 过滤 → 处境标注 → walkthrough          │
  本系统被否定的稿 / 人工反馈 → 反例 → 对照对                      │
  物理量默认值（speechRate、pauseShare）→ media-profile          │
                                                               │
C1 定位 → C2 人物与世界（只写人）                                │
   ↓                                                           │
C3a 功能地图：候选 A 登记 ──ledgerDeps 的程序类断言──► 检索题目    │
   ↓        ◄── K1 卡 ◄── 检索代理查出处（迭代）                  │
   追问单（16 问）──► 前提问题（候选＋默认＋决定）──► 分线候选     │
   ──► 追问 ──► 选定 / 登记为戏剧假定 / 进决定队列（带默认）       │
   ↓ ledgerDeps                                                │
C3b 底账（六类账，ledger@ep000）◄── 用户给定材料（user_given）    │
   ↓                                                           │
C3c 季编排：功能→集；容量粗估（media-profile）；超了必选动作；    │
           埋设/回收位；决定队列                                 │
   ↓ 本集分配 + 底账当前修订 + 前集实际轨                          │
C4 分集计划：events 自足；infoLedger(facts[])；presence；         │
            ledgerDelta(planned)；容量复核；pending[]            │
   ↓ plan-check / 冷读（只读 events）                            │
C5a 对话设计：infoLedger → carriedBy；知识账 → listenerKnows；    │
             situation → shape → reason；装同处境正反例 ◄────────┘
   │  装不下 / 没对象 → changeProposal(targetLayer: C4|C3c) → 决定队列（带默认）
   ↓
C5b 正文：照表写；plan-text-map；stateChangeProposals(ledgerDelta)
   ↓
ledger apply --track actual → ledger diff（两轨差异 → 下一集 C4 入口）
   ↓
C6：首读 · 次读 · 追问单复核 · 底账一致性 · 冷读复述 · 处境对照 · 设计依据一致性
   ↓
修订：回功能层换实现 → 重核受影响线 → 更新底账 → 重写受影响集 → 改表再改文 → 复读
   （patchCount ≥ 2 → 强制回 C3a；换实现预算到顶 → 登记并继续）
（随时）编剧／主创／顾问一句话 → feedback-ingest → 底账修订 / K1 / 决定 / 反例 / 约定
```

### 1.3 不做什么

- 不新增人审点：选题确认、送审包审批两处不动（[两次审批](../../skills/drama-studio/references/approval-flow.md)）。送审包只多四份附录：设定核对报告、戏剧假定清单、未核清单、决定队列（集纲方案 §9.3）。
- 不做 mali-story 服务端改动（R 级无新增）；功能地图、底账、季编排、分集计划、对话表首版都是本地文件（主创 2026-10-14 已定）。
- 随包脚本不联网、不调模型、不加供应商凭据（CLAUDE.md、AGENTS.md）。检索由宿主模型的代理做并留出处。
- 不设任何数值通过条件、不打分、不建自动优质裁判（架构 §11）。
- 不建工作室共享知识卡（D4-5 决定不重开）；语料缓存是另一类对象，是否工作室级等主创确认（§8）。
- 不训练或微调模型、不建向量库。
- 不替主创决定本项目的内容方向（重写多少、哪条线换实现、集数）。§5 只给事实与选项。
- 不在 D6 内做「第二部剧」验证（两份方案的阶段 3）；它是 D7 的候选，列在 §4.7。
- 不动 R0–R7 任务表、不动已迁移的《渊心锁》项目（`season-check` 对它走旧规则，§4.2）。

## 2. 合并后的对象与工具清单

### 2.1 对象（schema）

「来源」O＝集纲方案 §12，D＝台词方案 §17。层级按架构 §4.1。

| # | 对象 | 来源 | 共用／独有 | 层级 | 生产者 → 消费者 | 合并说明 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `function-map` | O#1 | 独有 | S | C3a → C3b、C3c、C4、修订 | 每候选 `inquiryRef` 必填。D6-0 后（集纲方案 §12 #1）：顶层 `premises[]`；候选 `requiresPremise[]`、`dependsOnCandidates[]`、`losesFunctions[]`；`ledgerDeps[]` 的 `depId` 必填、`assertion ∈ stated / required_unstated / absence`、`conflictsWith[]`；功能 `alsoServes[]`、`droppedCost`；`origin` 第三值与步骤级 `origin`。`selected` 的条件由「`outcome ≠ fail`」改为「回答记录里没有承重且未登记的 `notHolds`」；`losesFunctions[]` 非空的候选不得 `selected` |
| 2 | `ledger-entry`、`ledger-delta` | O#2 | **共用**：知识账是对话表 `listenerKnows` 的来源；实际轨由 C5b 的 `stateChangeProposals` 写 | S | C3b、C4（planned）、C5b（actual）→ C4、C5a、C6 | `run-handoff.stateChangeProposals` 增可选 `ledgerDelta`（O#10），旧 claim/evidence 仍有效。D6-0 后：`status` 加 `license_pending`、`accepted_license`（后者须 `humanWords`）；`contested` 带 `conflictKind`（四类）；理由缺失、空字段、`unstated`、`notAsked`、`tension` 等登记字段；必填项以 D6-0 的三段真实底账作夹具反推（集纲方案 §3.8） |
| 3 | `question-set` ＋ 两个实例 `reality-check-questions.json`（15＋1 问）、`dialogue-check-questions.json`（15＋2 问） | O#3、D#6 | **共用 schema**，两份数据 | S | 技能随包；项目可增问不可删，增问带来源 | 两份方案各有一张「版本化、可增不可删、增问带来源」的问题单，结构相同，合并为一个 schema。两份问题单各增第 16 问，来源相同（stage-d §十 2、4），**题干各写各的，不共用一句**：追问单问「行动者凭什么知道他据以行动的事实」（它的对象是候选实现与关键动作，没有句子可引）；对话问题单问「说话人凭什么知道」并把「为问而问」并入。对话问题单另增第 17 问「这条信息观众之前从哪句知道了，重说在处境里有理由吗」（stage-d §十 3）。D6-0 后：每问带 `answerKind ∈ tristate / informational`，追问单第 14、15 问是信息题、不参与 `outcome`；追问单的对象类型加 `premise` |
| 4 | `answers`（`reality-check` 与 `dialogue-check` 的回答记录） | O#3、D#6 | **共用 schema**：每答有落点／引用、三态、原因、可选出处 | S | C3a、C4、C6 → 修订 | 三态词统一为 `holds / notHolds / not_evaluable`（台词方案的 `not_evaluable` 与集纲方案的 `unverified` 语义不同：前者「答不了」，后者「查过没查到」——`unverified` 保留给底账条目状态，回答用 `not_evaluable`，并带 `because ∈ no_card / card_says_not_found / cannot_answer` 与可选 `leaning`）。落点字段按问题单类型二选一：追问单用 `landsOn`（步骤、断言、集场或底账 id），对话问题单用 `quoteRef: {line, quote}`。D6-0 后追问单回答另加 `defectKey`、`defectKind`、`loadBearing` 与依据、`inheritedFrom`／`inheritedAt`、`patch`、`disposition`、`cardRevisions`、`closes／retiresWith／leavesOpen`、`mapErrata[]`；`outcome` 加 `fail_inherited`，保留但不作排序或通过依据（集纲方案 §6.4） |
| 5 | `season-plan` | O#4 | 独有 | S | C3c → C4、`capacity season` | 每集 `capacity` 必填，超出时 `action` 必填 |
| 6 | `episode-plan` | O#5 | **共用**：第 7 栏 `infoLedger` 是对话表的输入 | S | C4 → C5a、C6、`ledger apply` | `infoLedger[]` 每条带 `facts[]`（一条一事实），`knownByInStory[]` 引用知识账。D6-0 后：`events` 结构化为 `scenes[].beats[]`；`closingEvent: {beatRef}`；`ledgerDelta.writes[].supportedBy` 为场或拍的引用；`facts[].keywords[]`（这几项只经过合成夹具的自测，没有在真实分集计划上跑过） |
| 7 | `decision-queue` | O#6 ＋ D §3.5「提案队列」 | **合并为一个对象** | S | 任何层 → 送审包附录、`pending[]` | 两份方案各有一个「等人但流程不等、必须带默认走法」的队列：集纲方案的决定队列（待主创定）、台词方案的容量提案队列（三选一）。合为 `decision-queue`，条目 `kind ∈ setting_conflict / premise / license / capacity / upstream_change / other`（`premise`、`license` 为 D6-0 后加；选项可带 `losesFunctions[]`）；`changeProposal`（架构 §9.1）仍是运行里**提出**的形式，`decision add --from-handoff` 把它登记进队列并要求 `default`。理由：主创只看一处；两者的字段（问题、选项、默认、默认理由、影响范围、状态）完全重合 |
| 8 | `media-profile` | D#1 | **共用**：C3c 粗估、C4 复核、C5b 精估都读它 | S | `corpus rate` → `capacity` | 只含物理量；拒绝任何句数／换人／话题数字段。按 stage-a §5 增 `grossCharsPerMinute`（每集每分钟台词汉字，含停顿）作对照口径；公式仍用 `speechRate ÷ (1 − pauseShare)`，两口径同时报直到 `project_measured`。画面拍的时长语料量不出来，量出来之前标 `pictureBeatSec: assumed`（D6-4 从原始转写的时间码量） |
| 9 | `dialogue-exchange`、`corpus-manifest` | D#2 | 独有 | S | `corpus` → C5a、C6 | 增 `speakerAttributionSuspect: bool`（stage-a §8.1）；`exchangeRef` 在 `snapshotId` 为 null 时允许 `localSha256` 并标 `refKind: local_fingerprint`（stage-a §8.5）；`scope.level: studio` 仅当 `origin.kind == mali_story_template`（等主创确认 §8.1，确认前只用 `project`） |
| 10 | `contrast-pair` | D#3 | 独有，只允许 `project` | S | `corpus`／`feedback-ingest` → C5a、C6 | `whyNotHere` 必填 |
| 11 | `dialogue-plan` | D#4 | **共用**：`infoLedger` 只引用 `episode-plan` 的 id 与 `facts` id 并加 `carriedBy`，不重新声明内容；`listenerKnows` 初值由 `ledger knows` 生成 | S | C5a → C5b、C6 | `topics[].segments[]` 取代 `between` 链，每段 `between: [a,b]` 与 `closer`（stage-d §十 5）；`exchanges[]` 增可选 `oneItemPerLine`、`givesReason`（诊断用，stage-d §十 6）；`exemplars.positives[].source ∈ corpus / human / project`（stage-d §十 12）；无 `estimates` |
| 12 | `dialogue-target` | D#5 | 独有 | S | 项目级 → C5a、C5b、C6 | 无 `acceptedBand`／`hardRules`／`softRules`；`conventions[]` 增 `conflictsWith[]`（stage-d §十 10） |
| 13 | `writer-note` | D#7 | **共用**：`feedback-ingest` 的统一入口；按 `level` 路由到台词侧（反例、约定）或集纲侧（底账修订提案、K1 草稿、决定 `decided`） | S | `feedback-ingest` → 两侧 | `level` 词表加 `procedure / fact / decision`（O#16）；增 `conflictsWith[]` |
| 14 | `retell-record` | D#8 ＋ O#15 | **共用**：`target.kind ∈ episode_text / episode_plan_events` | S | 冷读运行 → `retell-check` | `readingScope` 只允许一项且与 `target` 一致；提示词按 stage-d §十 9 的两处文案改（标明「连续剧第 N 集、前集已交代不列 unclear」；「△ 标画面约两秒并另估看成片能否拿到」），外加一条装包约束，即前面的 `readingScope` 只允许一项。提示词随包并版本化，`retell-record` 记 `promptVersion`；提示词版本不同的两次冷读不直接比（上一轮验证没有保存喂给冷读者的提示词原文，D6-0 是按产出结构重写的） |
| 15 | `plan-text-consistency` | D#9 | 独有 | S | C6 → 修订 | — |
| 16 | `knowledge-card` | O#7 | 不改 schema | S（现有） | 检索代理 → C3b | K1 作现实出处：`usage ∈ comparison_only / creative_reference`，`evidence.sources[]` 必有，外部 URL 标 `external_not_checked`。集纲方案 §6.2 的写法约定（内容按条标 `sourced／inferred／not_found`、空卡、来源分级、个案差异）是文档约定；是否升为字段见 §2.8 |
| 17 | `task` | O#8、D#10 | **合并**：一份 `constraint-blocklist.json` 数据文件，两类词表（「不动集数／标题／★／只改一次且不拆集」与「字数／行数／句数／换人数」数值型台词约束） | S | 编排方 → `contract-check task` | `constraints[] {text, origin, cite}`；命中任一词表即拒，不论 `origin`；`dialogueTarget` 引用必填（C5a/C5b/C6/修订任务）；`revisionBudget` 的单位按任务所属层解释（C3a 算换实现次数，默认 2，到顶后承重缺口登记、流程继续；C5a 算对话表修订次数），写进 README 工位索引 |
| 18 | `review-record` | O#9、D#11 | **合并**：`finding.cites ∈ {functionId, ledgerId, targetClause, factEvidence}`，一个都没有 → `kind: preference`；加 `adjudications[]` | S | C6 → 修订 | 旧记录（无 `cites`）仍通过，但 `season-check` 新规则只认带 `cites` 的 finding 进修订单 |
| 19 | `context-snapshot` / `selection` 角色 | O#18、D#12 | **合并**：`function_mapper`、`ledger_keeper`、`season_planner`、`dialogue_designer`、`situation_checker`、**`cold_reader`**（两份方案的 `plan_cold_reader` 与 `cold_reader` 合为一个角色，`target.kind` 区分；包只允许一个 `project_facts` 项且为本集 `events` 或本集正文） | S | `context-pack` | 多装被拒（退出码 2） |
| 20 | `run-handoff` | O#10 | 共用 | S | 各运行 | `stateChangeProposals[].ledgerDelta` 可选；`unknowns` 记「本次无检索」；D6-0 后加可选 `readScope`（这次运行实际读到了哪些材料；是自报，供核对方知道哪里要补核） |

### 2.2 命令

| # | 命令 | 来源 | 合并说明 | 层级 |
| --- | --- | --- | --- | --- |
| 1 | `ledger {init|merge|apply|replay|check|diff|knows|view}` | O#11 | 加 `knows --who <人> --at <ep>`：从知识账输出某人在某集的 `knows / notKnows`，供 C5a 填 `listenerKnows` 初值（S 生成，M 只能收窄不能相反）。D6-0 后：`merge`（分段合并，支持 `amendments`，校验同名字段类型）；`view --blank-period`（总账视图，C3a 阶段可从 `ledgerDeps` 生成）；`check --stage pre-select`（矛盾、理由缺失、钱的空字段只报不拦）与集纲方案 §10.2 增加的规则 | S |
| 2 | `plan-check <episode-plan> [--characters <人物包>]` | O#12 | 增 `--characters`：小传里的前史事件是否有时间线账条目（报不拦） | S |
| 3 | `capacity {season|episode|text}` | O#13 `season-capacity` ＋ D#18 `outline-capacity` ＋ D#19 `episode-check` 加估时 | **三个入口一个命令、一套公式**：`season` 对 `season-plan` 粗估（信息条数 × 同类处境语料交换中位时长 ＋ 画面拍）；`episode` 对 `episode-plan` 复核（同公式）；`text` 对正文精估（口播量 ÷ speechRate ÷ (1 − pauseShare)，两口径同时报）。超出时写 `decision-queue` 条目占位并**退出码 0**（提案不是失败）；`episode-check` 只加口播量统计，不算估时（避免两处算） | S |
| 4 | `check-answers <回答文件>` | O#14 `inquiry-format` ＋ D#16 `check-format` | 一个命令按 `questionsVersion` 引用的问题单核格式：每答有落点或引用、三态、原因；涉出处的有 `realityRef`。D6-0 后对追问单回答另核：承重的 `notHolds` 有 `disposition` 且引用存在；并出两份只报不拦的报告——覆盖（每个步骤与 `procedure`／`object`／`money` 类断言是否至少被一条回答落到）与 `--cross` 跨记录一致性（同一步骤或断言在不同记录里三态不一致） | S |
| 5 | `retell-check <复述> --plan <episode-plan|dialogue-plan>` | O#15 `plan-retell-check` ＋ D#16 `retell-check` | 一个命令按 `target.kind` 对照 `infoLedger`（到 `facts` 粒度）与 `exit.closingEvent`；输出 `retold / partial / missing` | S |
| 6 | `plan-text-consistency <正文> --plan <dialogue-plan>` | D#16 | S 对齐部分：说话人序列、话题与段边界、打断位置、`closer` 在切换前、`carries` 关键词在该来回；另列 `verbatimFrom` 行 | S |
| 7 | `dialogue-diagnose <正文> --plan <dialogue-plan>` | D#15 | 增信号 `INFO_REPEATED`（同一 `facts` 项第几个话题第几次出口，stage-d §十 3）、`ONE_ITEM_PER_LINE_MISMATCH`（`oneItemPerLine: true` 的来回里一行多个动词）；输出信号＋位置＋处境；无 `within/outside` | S |
| 8 | `corpus {fetch|segment|label|walkthrough|filter|lexicon|rate}` | D#14 | `fetch` 带重试、断点、`expected_snapshot_id`，取前后记预算与回执（计费观察，§6）；`label` 词表按 stage-a §8.4 收：功能近义项合并、关系「同时成立取更具体」；`segment` 输出 `speakerAttributionSuspect` | S（label／walkthrough 的 M 部分除外） |
| 9 | `feedback-ingest <文件>` | O#16 ＋ D#17 | 一个命令：输入飞书评论 JSON／改稿 md／原话记录 → `writer-note`；按 `level` 派生：句／来回／话题／信息承载 → 反例、对照对、`drafted` 约定、`drafted` 问；程序／事实 → 底账修订提案或 K1 卡草稿；决定 → `decision-queue` 条目 `decided`。同类 ≥2 次自动起草；标 `conflictsWith` | S |
| 10 | `decision {add|list|decide}` | 新（合并 §2.1 #7） | `add --from-handoff <run-handoff>` 把 `changeProposals` 登记进队列并要求 `default`；`decide` 只接受带 `humanWords` 的记录 | S |
| 11 | `dup-check --list-hits --k 8` | D#21 | 对装包样本 8 字档 | S |
| 12 | `season-check` 新规则 | O#17、D#20 | 集纲侧：`outline-ledger-delta`、`outline-capacity`、`outline-reality-refs`、`outline-patch-cap`、`outline-retell`、`outline-decision-default`、`outline-season-assigned`；正文侧：`dialogue-plan`、`plan-text-align`、`cold-retell`、`situation-check`、`consistency-record`、`retell-after-revise`、`target-ref`、`constraint-origin`、`no-numeric-dialogue-constraint`、`fixlist-no-lines`、`dup-two-tier`、`genre-lexicon`；删除 `voice-card`、`dialogue-pass`、`dialogue-read`（`--legacy-dialogue` 可查历史）。新旧并存见 §4.2 | S |
| 13 | `context-pack` | O#18、D#13 | 新角色（§2.1 #19）；C5b 装包要求对话表带通过的 `contract-check`；样本按处境＋说明＋骨架＋遮蔽原句装入并记装包历史；禁词表随包；C5a 装包要求 `episode-plan.capacity.status` 为 `fits` 或 `proposal:<id>` 且该提案有 `default`（§2.5 冲突 1） | S |
| 14 | `contract-check` | 两份 | 新对象的 schema 子集校验与跨字段规则；知识卡规则不改 | S |
| 15 | `impact --card <K1 id>`（现有 `impact` 的扩展） | D6-0 | 按回答记录的 `cardRevisions` 列出按旧卡作答、需要重答的回答 | S |
| 16 | 检索题目归并（独立子命令还是 `contract-check function-map` 的输出，见 §2.8） | D6-0 | 从 `ledgerDeps` 里 `kind: procedure` 的断言归并出检索题目清单；只归并，不检索、不联网 | S |

### 2.3 文档改动

| 文件 | 改动 | 阶段 |
| --- | --- | --- |
| [`SKILL.md`](../../skills/drama-studio/SKILL.md) | 路由表「原创选题、人物与集纲」改指 `planning.md`＋新 `outline-layer.md`；「台词 AI 味重」一行改指 `dialogue-structure.md`；「一次完整创作」第 3–7 步改写；随包工具表加新命令（[`tests/test_skill_routing.py`](../../tests/test_skill_routing.py) 同步） | D6-2、D6-3 |
| [`references/planning.md`](../../skills/drama-studio/references/planning.md) | 重写「蓝图、设定圣经与集纲」一节：六字段说明改为分集计划字段；「时间线、道具位置、谁知道什么放设定圣经」改为底账；两轨 | D6-2 |
| 新 `references/outline-layer.md` | 功能地图、C3a 内的顺序与前提层、六类账与条目状态（含戏剧假定）、追问单（含第 16 问、信息题、承重缺口的三个去处）、检索代理（可联网、留出处、脚本不联网；K1 卡写法约定）、季编排与容量、分集计划字段、修订规则、决定队列、用户给定设定的处理 | D6-2 |
| [`references/writing.md`](../../skills/drama-studio/references/writing.md) | 工位流程第 3–7 步改写（C4 分集计划可写 → C5a → C5b → C6 五读 → 修订）；「避免用解释性台词替代人物行动」改为「信息由对白承载；谁知道什么由 `listenerKnows` 定；重复须有处境理由」 | D6-3 |
| `references/dialogue.md`（D6-3 已改名为 [`dialogue-structure.md`](../../skills/drama-studio/references/dialogue-structure.md)） → `dialogue-structure.md` | 重写；§8 前文校核、§9 改稿任务怎么写保留 | D6-3 |
| 新 `references/corpus.md` | 取用、切分、过滤、处境标注、结构说明、缓存、快照、计费观察 | D6-4 |
| `workstation-c3-structure.md`（D6-2 已拆，原文件删除） | 拆为 `c3a-function-map.md`、`c3b-ledger.md`、`c3c-season-plan.md`；「删掉一段，后续是否仍原样发生」移到 c3c；c3a 带写作任务书的随包条款（四种不允许的修法、三条规矩、预算到顶后的动作，集纲方案 §8.1、§8.3） | D6-2 |
| [`workstation-c4-episode-outline.md`](../../skills/drama-studio/references/workstation-c4-episode-outline.md) | 产出项改为 14 字段；「整季集纲怎么写」六步保留，装的东西换成季编排＋底账；审读项换成追问单复核、底账一致性、冷读；「每集有没有主角的关键选择」硬项废除 | D6-2 |
| `workstation-c5-screenplay.md`（D6-3 已拆，原文件删除） | 拆为 `c5a-dialogue-plan.md`、`c5b-text.md` | D6-3 |
| [`workstation-c6-review.md`](../../skills/drama-studio/references/workstation-c6-review.md) | 加五读；finding 必带 `cites` | D6-2（集纲侧三读）、D6-3（正文侧两读） |
| [`workstation-season-run.md`](../../skills/drama-studio/references/workstation-season-run.md) | §1「上游 C1–C4」与「入口状态」改为底账；§3 每批步骤改写 | D6-2、D6-3 |
| [`workstations.md`](../../skills/drama-studio/references/workstations.md) | 工位索引、执行层级表加新不变量、`revisionBudget` 按层解释 | D6-2、D6-3 |
| [`references/approval-flow.md`](../../skills/drama-studio/references/approval-flow.md) | 送审包附录四份：设定核对报告、戏剧假定清单、未核清单、决定队列；拆集在送审后是方向变更 | D6-2 |
| [`references/recovery.md`](../../skills/drama-studio/references/recovery.md) | 恢复顺序加底账当前修订、季编排、决定队列 | D6-2 |
| [`references/mali-story.md`](../../skills/drama-studio/references/mali-story.md) | 语料读取的回执与计费观察 | D6-4 |
| [系统架构 v1.2](drama-studio-system-architecture-2026-09-29.md) → v1.3 | §5.1 C3/C4/C5/C6 交接对象；§6.1 主数据加功能地图与底账；§6.4 加两轨；§8.5 语料缓存条款（等 §8.1 确认，确认前写「待定」）；§11 证据类别加冷读复述、处境对照、设计依据一致性 | D6-5 |
| [实施路线 v1.1](drama-studio-implementation-roadmap-2026-09-29.md) | 加一行状态指到本计划 | D6-5 |
| [工艺闭环](drama-studio-craft-loop-design-2026-10-10.md)、[样本库设计](drama-studio-dialogue-sample-library-design-2026-10-13.md)、[台词库产品设计](drama-studio-voice-library-product-design-2026-10-12.md) | 文首加状态行（见 §2.7） | D6-5 |
| [D4-5](../d4/shared-knowledge.md) | 加注「语料缓存不属此决定」 | D6-5 |
| [`README.md`](../../README.md) | 记新命令 | 每阶段 |

### 2.4 共用项（两份方案说的是同一件东西）

| 共用项 | 集纲方案的说法 | 台词方案的说法 | 合并后 |
| --- | --- | --- | --- |
| 知识账 ↔ `listenerKnows` | 知识账 `notKnows[]` 是 `listenerKnows` 的来源（§3.5） | `listenerKnows` 一句话，M 写（§6.1） | `ledger knows` 生成初值，M 收窄；S 核对话表不与账矛盾；说话人 `carries` 的事实在账里他此前「知道」（第 16 问的 S 版） |
| 信息清单 | 分集计划第 7 栏，一条一事实或 `facts[]` | 对话表 `infoLedger` 带 `carriedBy` | 声明一次在分集计划；对话表引用 id＋`facts` id 加 `carriedBy`；`retell-check`、`dialogue-diagnose` 都按 `facts` 粒度核 |
| 媒介档案 | 共用台词方案 §3.2（§7.1） | 项目级对象，只含物理量 | 一个对象；两口径同时报 |
| 容量算术 | 季编排粗估、分集复核、正文精估（§7.1） | 粗估（C4）、精估（C5b 后）（§3.5） | 一个 `capacity` 命令三个入口；第一次在 C3c（§2.5 冲突 1） |
| 决定队列 ／ 提案队列 | `decision-queue`（§8.4） | 容量提案进「项目的提案队列」（§3.5） | 合并（§2.1 #7） |
| 冷读者 | 只读分集计划 `events`（§10.3） | 只读本集正文（§8.2） | 一个角色 `cold_reader`，两种 `target.kind`，同一提示词骨架 |
| 问题单 | 追问单 15 问，版本化可增不可删 | 对话检查问题单 15 问，同规则 | 一个 `question-set` schema，两份数据（现各 16 问、17 问；第 16 问各写各的题干），一个 `check-answers` |
| `feedback-ingest` | 程序／事实类批注 → 底账、K1、决定（§12 #16） | 批注 → writer-note → 反例、约定、新问（§9） | 一个命令按 `level` 路由 |
| 任务约束词表 | 「不动集数／标题／★／只改一次」（§8.3） | 数值型台词约束（§11） | 一份 `constraint-blocklist.json`，两类 |
| 审读 finding 的引用义务 | `functionId` 或 `ledgerId`（§8.3） | `targetClause` 或 `factEvidence`（§10.3） | `cites` 四选一，否则 `preference` |
| K1 知识卡 | 检索代理的出处（§6.2） | 不涉及 | 不改 schema |
| `dup-check` | 新旧实现 8 字档重合提示 `renamed_patch`（§10.4） | 13 字档全库、8 字档装包样本（§7.3） | 同一命令，两种用法 |
| 不新增人审点 | 送审包附未核清单与设定核对报告 | 送审包审批不变 | 送审包多四份附录（D6-0 后加戏剧假定清单），不多一次审批 |

### 2.5 冲突点与合并定法

| # | 两份方案对同一件事的不同说法 | 合并定法 | 理由 |
| --- | --- | --- | --- |
| 1 | **容量在哪算、超了怎么办。** 集纲方案：第一次在 C3c，超了必选一个动作（重排／拆集／删线），送审包里每集 `fits`；送审后再超走提案队列。台词方案：粗估在 C4，超了出提案进队列、流程不停、稿子标 `proposal_pending`。stage-d §九 4、§十 7：不拦截让 f1 成了一份拍不了的 9–10 分钟正文，验证对象失真 | 送审前：C3c 必选动作（S：`season-plan` 超出无 `action` 被拒）。送审后：提案进决定队列、流程不停，**但提案必须带默认走法**（与决定队列同规则），C5a 按默认走法写对话表（默认拆法是「按粗估比例拆成 N 段，本集只写第一段，其余登记为下一集的 `entry`」）；C5a 装包时 `episode-plan.capacity.status` 若为 `proposal:<id>` 而该提案无 `default` → `context-pack` 退出码 2。这不是数值关口：数字触发的是「提案要有默认」，不是「稿子不合格」 | 两份方案都说「流程不停」；差别只在「停下来等人选」还是「按默认先走」。决定队列原则（提出的人给默认、流程按默认继续）已被主创接受（第 3 条决定），用到容量上是同一条规矩。stage-d 的实测说明没有默认走法的「不拦截」会产出不会存在的稿 |
| 2 | **信息清单归属。** 台词方案 C4 产「六字段集纲＋信息清单」，对话表自带 `infoLedger` 与 `carriedBy`；集纲方案信息清单是分集计划第 7 栏 | 声明一次在 `episode-plan.infoLedger[].facts[]`；`dialogue-plan.infoLedger[]` 只引用 id 并加 `carriedBy`；S 核引用存在、每个 `fact` 有承载或画面理由 | 两处声明必然漂移（stage-d §四「清单与 exchanges 交叉引用不一致」就是同一张表里都漂了）；集纲方案 §0 第 8 条已把 `facts[]` 定为接口 |
| 3 | **C4 的产物格式。** 台词方案保留六字段；集纲方案换成 14 字段分集计划，六字段为可选派生 | 集纲方案为准（主创第 5 条决定）；台词方案 §2.2 C4 一行自己写了「由上游细化」 | 结构审查 0/60 自足；台词方案没有审过集纲格式 |
| 4 | **`listenerKnows` 的来源。** 台词方案：M 一句话；集纲方案：知识账初值 | S 生成、M 收窄，矛盾报（§2.4） | stage-d §六 4：家宝说出他不该知道的「抽屉的钥匙」，问题单全过——没有账，M 写的 `listenerKnows` 核不出说话人越界 |
| 5 | **冷读者读什么。** 集纲方案只读 `events`；台词方案只读正文 | 一个角色两种目标（§2.1 #19） | 任务相同（复述谁做了什么、信息从哪知道），只差材料；两套角色会有两套提示词要改两遍（stage-d §十 9 的两条修正要同时落） |
| 6 | **修订预算的单位。** 集纲方案：换实现的次数；台词方案：对话表修订次数，默认 1 | `task.revisionBudget` 按任务所属层解释，写进工位索引；补丁计数是另一个计数器。C3a 的默认值与到顶后的动作见 #17 | 任务本来就是按层发的；不必改 schema |
| 7 | **版本号。** 集纲方案 0.5.0、台词方案 0.4.0，隐含「台词先上」 | 按阶段递增（§0） | 合并后上游先于下游 |
| 8 | **「第 7–10 集重写」。** 台词方案阶段 1 要重写第 7–10 集；集纲方案指出 60 集分集计划都要重产 | 技能阶段（D6-1 至 D6-5）不含任何集的重写；重写多少是 §5 的项目级选项 | 集纲换了，先重写台词是在旧地基上刷墙；也违反「不替主创定内容方向」 |
| 9 | **语料缓存位置。** 台词方案建议工作室级（需契约变更）；集纲方案阶段 0 直接用「台词方案阶段 A 的媒介档案 v0」，而那份在项目目录 | D6-0 与 D6-1 用项目级缓存（现状 `runs/pilot-ep006/corpus/`）；schema 两级都允许；工作室级等主创确认后在 D6-4 开（§8.1） | 不确认也能跑；确认后只是挪目录 |
| 10 | **三态词。** 集纲方案 `holds / notHolds / unverified`；台词方案 `holds / notHolds / not_evaluable` | 回答统一 `not_evaluable`，原因分 `no_card / card_says_not_found / cannot_answer`；`unverified` 只作底账条目状态 | 「查过没查到」是条目的状态，「这问我答不了」是回答的状态，两者在送审包里的去处不同（未核清单 vs 问题单记录） |
| 11 | **每集样本上限。** 台词方案 §7.2：每集 8 正例、4 对照对；stage-b 按主创要求每话题 2 条装了 22 条正例、12 对 | 删固定条数，改为「每话题 2 正例＋1 对照对，总量受包预算（知识分区不超过四分之一）约束」；超预算按 Tier、`recurrent`、`labelConfidence` 截断 | 固定条数是数字当上限；预算已有规则；与方案不一致，D6-5 回写 |
| 12 | **人工正例可不可以逐字用。** 台词方案 §7.3 遮蔽原句防抄；台词目标 v0 约定 3「编剧要的是把它原样说回来」；stage-d §十 8 要定下来 | 本剧编剧写的句子（`grade: human`、来源 `writer-note`）可以逐字用，`plan-text-map` 标 `verbatimFrom: <noteId>`，校验时这些行不计入「问题不再出现」的证据；语料原句仍只给遮蔽 ≤2 句、永不逐字 | 编剧的句子是本项目的产物，抄它不是抄语料；但要能分清「学会了」和「照抄了」 |
| 13 | **语速口径。** 台词方案 §3.2 定义 `speechRate` 为说话期间速度，§3.4 的实测数却是每集每分钟台词汉字（stage-a §5 两者差近一倍） | 媒介档案两个字段都存，公式用 `speechRate ÷ (1 − pauseShare)`，`capacity` 两口径同时报（`capacity-ep006.md` 两口径差 <10%） | 不选口径就没有可复算的估时；两口径并报让读者看到偏差量级 |
| 14 | **底账与 `after-ep-NNN.md`。** 台词方案 C5 包仍装「入口状态记录 `runs/state/after-ep-NNN.md`」；集纲方案把它重构为底账实际轨 | D6-2 起入口状态是 `ledger@after-ep-N.actual` 的可读导出（`ledger replay --at N --track actual --md`），文件名沿用 `runs/state/after-ep-NNN.md` 以兼容 `season-check author-state` 规则 | 内容相同（故事日、谁知道什么、物件、未写明），只是由脚本从账导出而不是作者手写；旧项目的手写文件仍被旧规则认 |
| 15 | **C3a 的验收写法与两条规矩。** 集纲方案 v1.1 与本计划 v1 都把交接写成「`selected` 实现的回答记录无 `notHolds`」，同时守着「不打补丁」与「现实只认卡」。D6-0：63 份记录里零 `notHolds` 的只有 3 份；两条规矩合起来把写作推向删功能 | 交接条件改为「没有承重且未登记的 `notHolds`」。承重的只有三个去处：换实现后经新上下文的核对记录确认消失；登记为戏剧假定；进决定队列并带默认。不承重的留 `leavesOpen`，进送审包附录，不拦。`outcome` 保留但不作排序或通过依据 | 16 问逐方逐人地问，零容忍不可达；没有「留着并登记」的去处时，剩下的出路只有打补丁或删 |
| 16 | **用户给定设定不成立时的默认，与「删功能归谁定」。** 主创第 3 条决定：按通过核对的候选先走并标 `pending`。本计划 §5：哪个功能可以 `dropped` 是主创的事。D6-0 第二轮里，通过核对的路是把实现拿掉 | 第 3 条不变，限定前提：存在通过核对、且不让任何功能句落空的候选。否则系统默认保留用户给定的实现并标 `license_pending`，把「按现实改掉（列出哪些功能句落空）对 作为戏剧假定保留」登记进决定队列，流程按「保留」继续。前提一级的决定同规则。**这是对第 3 条决定的细化，待主创确认（§8 #7）** | 既守「流程不等、不新增人审点」，又守「哪个功能可以不要是主创的事」。D6-0 第二轮：8 处靠拿掉，功能句落空 14 条 |
| 17 | **C3a 内部回路的预算。** 两份方案与本计划 v1 都没有为「写 → 追问 → 换 → 再追问」留量，也没有写到顶之后做什么 | `task.revisionBudget` 在 C3a 是换实现的次数，默认 2；到顶后仍在的承重缺口按 #15 的后两个去处登记，流程继续，不再换。**待主创确认（§8 #9）** | D6-0 两轮不收敛后只能停。有预算而没有到顶动作，等于没有预算 |
| 18 | **追问与检索谁先；各线分写还是先归并前提。** 两份方案与本计划 §9 v1 都是追问在前、检索在后，候选 B「每线一到多个」 | 顺序：功能地图（候选 A 登记）→ 由 `ledgerDeps` 里程序类断言自动归并检索题目 → 检索写卡 → 追问 → 前提问题 → 再检索 → 默认前提追问 → 分线候选。检索是迭代的（集纲方案 §2.4） | D6-0：28 条未核规则在追问之后才有卡；检索题目预估漏了整块；20 处跨线缺口同根，分线各写会互顶 |
| 19 | **追问单的标准答案是什么。** 本计划 v1 的 0.2 步与 §6 把两份审查的结论当标准答案核追问单 | 标准是 K1 卡；与审查的对照只作旁证 | D6-0：卡与审查有出入的至少 5 处；审查自身有无出处的说法 |

### 2.6 本计划对两份方案的修正点（回头修方案的清单）

#1–#14 来自第 6 集台词验证，在 D6-5 回写进两份方案正文，此前以本计划为准（其中 #3、#6 已随 v1.1 改过说法，并已写进两份方案）。#15 起来自 D6-0，已于 2026-10-14 就地写进两份方案，不等 D6-5；「来源」一栏的编号是 D6-0 修正点清单的序号。70 条逐条的去处在项目目录 `runs/pilot-v2/schema-findings-disposition.json`。

| # | 修正 | 落到的任务 | 来源 |
| --- | --- | --- | --- |
| 1 | 容量复核超目标两倍时 C5a 按提案默认拆法走（§2.5 #1） | D6-0 任务 0.11；D6-1 `context-pack` 规则；D6-3 `writing.md` | stage-d §九 4、§十 7 |
| 2 | `infoLedger` 带 `facts[]`，对话表只引用（§2.5 #2） | D6-0 任务 0.8、0.10；D6-1 两个 schema | stage-d §十 1 |
| 3 | 追问单与对话问题单各增第 16 问（同一来源，各写各的题干：追问单问行动者凭什么知道他据以行动的事实；对话问题单问说话人凭什么知道，并入「为问而问」）；对话问题单增「第几次出口」 | D6-0 任务 0.3、0.12；D6-1 问题单数据 | stage-d §十 2–4 |
| 4 | 对话表 `segments[]` 取代 `between` 链 | D6-0 任务 0.10；D6-1 schema | stage-d §十 5 |
| 5 | `exchanges[]` 可数标记；`dialogue-diagnose` 加 `INFO_REPEATED` | D6-1 | stage-d §十 3、6 |
| 6 | 冷读提示词两处文案改法＋一条装包约束（`readingScope` 只允许一项）；提示词随包并版本化，`retell-record` 记 `promptVersion` | D6-0 任务 0.9、0.12；D6-1 | stage-d §十 9；D6-0 #4、#5 |
| 7 | `writer-note.conflictsWith`、台词目标写明取舍 | D6-1、D6-4 | stage-d §十 10 |
| 8 | `exemplars.source: project`；`verbatimFrom` | D6-0 任务 0.10；D6-1 | stage-d §十 8、12、§九 1 |
| 9 | 每集样本上限改按预算 | D6-1 `context-pack` | stage-b §4 |
| 10 | 语料标注词表收敛；`speakerAttributionSuspect`；`exchangeRef` 本地指纹 | D6-4 `corpus label/segment/fetch` | stage-a §8.1、8.4、8.5 |
| 11 | 媒介档案两口径 | D6-0 任务 0.6；D6-1 schema | stage-a §5 |
| 12 | 决定队列与提案队列合并；`season-capacity`／`outline-capacity`／估时合为 `capacity`；`inquiry-format`／`check-format` 合为 `check-answers`；两个 cold reader 合为一个 | D6-1 | 本计划 §2 |
| 13 | 技能版本号顺序 | D6-5 | 本计划 §0 |
| 14 | 语料检索对核心处境返回空时的做法：`no_exemplar` 如实标，允许 `source: project` 的本剧人工句作同处境正例并写 walkthrough | D6-0 任务 0.10；D6-4 补语料 | stage-d §九 7、§十 12 |
| 15 | 验收与状态：C3a 交接条件、回答记录的字段、`outcome` 的地位、缺口结局三态、自报不算数（§2.5 #15） | 已写入集纲方案 §2.2、§6.4 | D6-0 #17、21、22、25、35–38、51、56、67、68 |
| 16 | 戏剧假定：两个条目状态与送审包清单 | 已写入集纲方案 §3.8、§9.2、§9.3 | D6-0 #66 |
| 17 | 用户给定设定的默认走法；`losesFunctions[]`（§2.5 #16） | 已写入集纲方案 §9.1、§7.2 | D6-0 #65、69 |
| 18 | 修订规则：四种不允许的修法、预算与到顶后的动作、写作任务书三条、修订范围四种情形（§2.5 #17） | 已写入集纲方案 §8.1–§8.4 | D6-0 #10、52、61、64、65 |
| 19 | 前提层与 C3a 内的顺序；检索题目归并与迭代；卡晚到（§2.5 #18） | 已写入集纲方案 §2.4、§6.2、§6.5 | D6-0 #9、22、32、34、47、55、57 |
| 20 | 追问单：信息题、第 16 问题干、主力三组、追问单不管的三类断言、覆盖与跨记录一致性、标准是卡（§2.5 #19） | 已写入集纲方案 §6.1、§6.3、§6.4；台词方案 §8.3 | D6-0 #1、15、16、20、29、33、39、50、54、62 |
| 21 | 底账：字段与规则按真实数据、`conflictKind`、阶段、分段合并、新增规则 | 已写入集纲方案 §3.1–§3.8、§10.2 | D6-0 #23、24、28、31、40、44、46、48、49 |
| 22 | 功能地图字段 | 已写入集纲方案 §12 #1 | D6-0 #2、6、7、8、11、12、17、30、37、53 |
| 23 | 分集计划与容量的结构化；画面拍时长标 `assumed` | 已写入集纲方案 §4、§7.1 | D6-0 #41、42、43 |
| 24 | 冷读提示词版本化；`answers` 的落点字段；`check-answers` 的名字 | 已写入台词方案 §8.2、§17 | D6-0 #3、4、5 |
| 25 | K1 卡的写法约定 | 已写入集纲方案 §6.2（约定）；升字段见 §2.8 | D6-0 #13、14、59、60 |
| 26 | 运行留下「读到了什么」；「没写」类结论写查的范围 | 已写入集纲方案 §6.4、§10.4；本计划 §2.1 #20 | D6-0 #26、58、70 |

### 2.7 另两份相关设计的处置

- [台词样本知识库设计（2026-10-13）](drama-studio-dialogue-sample-library-design-2026-10-13.md)：按台词方案 §20 已被**重心倒置**（分级被 Tier＋`grade: human` 取代、样本对象被 `dialogue-exchange` 取代、数数关口与覆盖卡废除、留出法保留为可选描述）。本计划不再单独排它的任务；D6-5 在其文首加状态行「被台词方案 v3 取代；仍有效的只有 §9 留出法（可选描述性评测）与 §6.2 装包历史」。
- [台词库产品设计（2026-10-12）](drama-studio-voice-library-product-design-2026-10-12.md)：产品形态（五种来源、权利等级、目录页）不受影响；它的「语料片段」对象就是 `dialogue-exchange`，「对标转写」升为主来源。本计划只做其中「样本」这一块（D6-4）；其余产品层（目录页、多来源入库）不在 D6，D6-5 文首加状态行说明哪些已由 D6 实现、哪些仍是设计。
- [工艺闭环设计（2026-10-10）](drama-studio-craft-loop-design-2026-10-10.md)：§4.4、§4.5 三条 S 关口被取代（台词遍、台词读在 D6-3 退役）；§1 问题判断与 §3 分层被吸收。D6-5 加状态行。

### 2.8 留给 D6-1 的设计决定（D6-0 暴露，本次不定）

下面各项在 D6-1 开头定，定之前不冻结对应的 schema。它们是设计上的取舍，不需要主创点头（需要主创确认的在 §8）。

| # | 要定的事 | 选项 | D6-0 的临时做法 | 来自修正点 |
| --- | --- | --- | --- | --- |
| 1 | 状态性断言（法律、人身、关系状态，带起止时间）放在哪 | 加第七类账 `status`；或在时间线账下加子型 | 放时间线账并标 `whyNotApplicable` | #45 |
| 2 | 追问单 v1 → v2 的题干 | 合并在候选层常答成同一件事的问（第 1 与 2、4 与 9、5 与 6、7 与 16）；第 10 问补实；第 5 问补「知情人为什么没说」；第 13 问拆成两问；第 3、13 问题干是否补「做法与小传里的性子相不相合」「空白期之前的关系」；第 4 问是否并入「机构作为行动者的动机」；第 16 问是否只对「关键动作」对象保留。本次定稿不改题干 | 照 v1 作答，重合处照记 | #18、19、24、27 |
| 3 | K1 卡的写法约定是否升为 schema 字段 | 条目级 `support`；卡级 `coverage ∈ sourced / partial / empty`；`evidence.sources[].sourceTier`；个案的 `caseFacts` 与 `distanceFromOurs` | 写在卡的内容、`versionOrDate`、`limits` 里；空卡在回报里点名 | #13、14、59、60 |
| 4 | `origin` 怎么表达「用户给了大意、后来改了关键细节」 | 值域加 `user_given_modified`；或步骤级与候选级的 `origin` 分开；或两样都要（集纲方案 §12 #1 暂按两样都写） | 标 `designed` 并括注 | #7 |
| 5 | 各 schema 的必填项 | 以 D6-0 的三段真实底账、49＋14 份回答记录、四条线的功能地图作夹具，逐字段定必填与可选 | 临时脚本按真实数据放宽了七处 | #40、48 |
| 6 | 检索题目的归并放在哪个命令 | 独立子命令；或 `contract-check function-map` 的输出 | 编排方手工归并 | #34 |
| 7 | 「材料全程没写」类结论的证据 | 由 `ledger` 或事实索引的检索给出查的范围（S）；或保持为核对方自述（M） | 核对方自述 | #26 |
| 8 | `loadBearing` 的依据怎么记 | 自由文本；或枚举（记录原话／有下游转引／落在功能句直接要的那一步）加一句说明 | 事后推，记了三种依据 | #51 |
| 9 | 承重缺口的去处记在哪 | 回答记录里的 `disposition` 字段（集纲方案 §6.4 暂按这样写）；或单独的缺口登记对象，回答只引用 | 单独的缺口登记表，由临时脚本从回答记录合并 | #17、67 |

## 3. 依赖关系与顺序

```text
                 ┌──────────────────────────────────────────────────┐
                 │ D6-0 合并验证（不改技能；本项目；临时脚本）          │
                 │  功能地图与底账 → 季编排与容量 → 分集计划 → 冷读     │
                 │  → 对话表 → 正文 → 冷读/问题单 → 对照报告            │
                 │  已执行一轮，停在候选 B 的前提层；续做见 §4.1        │
                 └───────────────┬──────────────────────────────────┘
                                 │ 产物作夹具；暴露的格式问题定 schema
                                 ▼
   ┌──────────────── D6-1 对象与只读工具（旧流程可用，0.4.0）────────────────┐
   │  schema×20 ＋ 命令（ledger / plan-check / capacity / check-answers /     │
   │  retell-check / plan-text-consistency / dialogue-diagnose / decision /   │
   │  feedback-ingest 骨架 / context-pack 角色 / season-check 新规则不启用）  │
   │  语料命令 corpus{segment,label,filter,rate}（fetch 可晚）—— 与底账工具互不依赖，可并行 │
   └──────────┬──────────────────────────────────────────┬───────────────────┘
              ▼                                          │
   D6-2 切换集纲层（0.5.0）                                │
     outline-layer.md、c3a/b/c、c4、planning、approval、    │
     recovery、season-check --outline 新规则按项目自动选集  │
              ▼                                          │
   D6-3 切换台词层并退役台词遍/台词读（0.6.0）◄───────────────┘（需要 D6-1 的语料对象与 C5a 规则）
     writing.md、dialogue-structure.md、c5a/c5b、c6、season-run、
     season-check 正文侧新规则 + --legacy-dialogue
              ▼
   D6-4 语料库与反馈回流（0.7.0）
     corpus fetch 全库（计费确认后）、工作室缓存（确认后）、feedback-ingest 全路由、
     禁词表、台词目标升版
              ▼
   D6-5 清理与文档（0.7.x）
     架构 v1.3、路线图加注、三份旧设计状态行、两份方案回写 §2.6、退役表收尾、页面化评估
```

**为什么是这个顺序。**

1. **上游先于下游**：对话表的输入（信息清单、在场、知识状态、容量状态）全来自分集计划，分集计划的输入来自季编排与底账。先切台词层等于在旧集纲上做对话设计，stage-d 已经做过一次，结论是「第 6 集的事件是 3.5–4 集的量，不是写法问题」。
2. **D6-0 先于 D6-1**：schema 的字段表在两份方案里已有，但 `facts[]` 粒度、`segments[]`、三态词、两口径这类问题全是实做一遍才暴露的（stage-a/b/d 加起来 20 多条）。再走一遍合并后的闭环，再冻结 schema，比先写 schema 再改便宜。D6-0 第一轮印证了这一条：只走到前史底账就暴露了 70 条修正点，其中一条是按方案字段表写的规则对第一份真实底账报了 108 条假阳性。
3. **D6-1 只加不改**：新对象与只读工具不碰现有流程，旧项目（含《渊心锁》）照常通过全部测试，这一阶段可以独立回滚。
4. **可以并行的**：D6-1 里语料命令与底账工具互不依赖；D6-2 的文档改写与 D6-1 的测试互不依赖（但发布要等测试过）；D6-4 的 `corpus fetch` 全库取用只依赖计费确认（§8.1 之外的事实核查），可以在 D6-2、D6-3 期间后台跑。
5. **D6-3 依赖 D6-1 的语料对象**：C5a 装包要装样本，样本 schema 与 `context-pack` 的装包规则在 D6-1；但不依赖 D6-4 的全库——D6-0 的 138 条就够 D6-3 验收用。

## 4. 分阶段计划

每阶段：目的、交付物、验收证据（只用 S／R；M 项附证据不作通过条件）、退出条件、估计工作量（代理工作日，不含人力）、回滚办法。所有阶段结束都要：`python3 -B -m unittest discover -s tests -v` 全过、`python3 -B scripts/validate.py` 通过、`season-check` 对《渊心锁》与本项目旧记录结果不变。

### 4.1 D6-0：合并验证（不改技能，只在本项目上）

**目的**：把两份方案各自的阶段 0 并成一个闭环，在真实材料上从「地基不成立的线」走到「一集正文的冷读与问题单」，拿到可比的证据，并暴露 schema 要改的地方。不写正式代码（脚本放 `runs/pilot-v2/tools/`，与 `pilot-ep006/tools/` 同性质）。

**与第 6 集台词验证（`runs/pilot-ep006/`）的关系**

| 已有产出 | 处置 | 理由 |
| --- | --- | --- |
| 语料 40 集原始响应、138 条交换、索引、分布、`LABEL_GUIDE.md`、双跑自检 | **复用**，不重切 | 语料与集纲无关；覆盖缺口（险情、孩子指挥大人、偷偷示好）记在案，D6-4 补 |
| 媒介档案 v0（两口径、两形态） | **复用**，加 `grossCharsPerMinute` 字段名对齐 §2.5 #13 | 物理量不随集纲变 |
| 反例 8 条、对照对 23 对（含 9 对人工对照对） | **复用** | 它们来自编剧批注与 e2，仍是本系统的失败形态 |
| 台词目标 v0（四条 `drafted` 约定） | **复用**，加 `conflictsWith`（c6 与 c4/c5 的矛盾） | stage-d §十 10 |
| 冷读提示词、问题单 15 问、`check_ep006.py` 等脚本 | **复用并改**：提示词按 §2.6 #6，问题单加两问 | — |
| 第 6 集对话表、f1 正文、`plan-text-map`、两份 retell、`dialogue-check-f1.json`、`capacity-ep006.md` | **保留作对照组，不复用为输入**；第 6 集按新分集计划重做 | 集纲换了（礼物线换实现后第 6 集没有仓库一场；容量在季编排层处理后第 6 集不再是 19 条信息） |
| stage-a/b/d 三份报告 | 作为 D6-0 的「上一轮」证据，对照报告引用 | — |

**状态（2026-10-14）：已执行一轮，停在 0.5。** 事实见[中期报告](../d6/d6-0-interim.md)，这里只列与计划有关的。

- **0.1–0.4 完成**，各有临时脚本可复算的证据：功能地图 v0（四条线 49 个功能、49 个候选 A；世界断言 487 条，其中程序类 183 条）；候选 A 的追问 49 份（46 份判不成立；`notHolds` 320 条，去重为 137 处缺口，承重 89，跨线 20）；检索四批 50 张 K1 卡（空卡 5 张；`contract-check knowledge-card` 全过；外部来源全部 `external_not_checked`）；前史底账 400 条（`ledger check --stage pre-select` 通过；矛盾 23 对，缺理由 94 条）。
- **0.5 没有完成。** 实际做的是 v1 计划里没有的一步：先把跨线的根缺口归并成 7 个前提问题（各 3 个候选加默认），让新上下文追问默认前提。第一轮 7 个全不成立（60 处，承重 45；被判为补丁 22 处；逐题求解后互相顶 13 处）。换候选后的第二轮仍 7 个全不成立（45 处，承重 39；上一轮承重 45 处的去向：确认消失 18、仍在 10、换了地方 9、靠拿掉实现 8；功能句落空 14 条）。按「第二轮仍不收敛即停」处理。分线的候选 B、设定核对报告、决定队列都没有产出。
- **0.6–0.13 没有开始。** 季编排、分集计划、冷读对照的临时脚本已经写了，只过了合成夹具的自测（13 个临时脚本，自测 100 项通过）。
- **没有动的东西。** 没有改技能文件、脚本、schema、测试；没有读写 mali-story（当次会话 MCP 连接超时）；没有改项目的集纲、正文与原有知识卡。
- **为什么停**（中期报告第四节）：v1 的验收写法不可达（§2.5 #15）；两条规矩合起来把写作推向删功能，而系统没有「明知不合常规仍保留」的状态（#16）；根在故事前提一级，每个成立的版本都要换掉一样用户给定或已改定的东西；回路没有预算（#17）。对策已写进两份方案（§2.6 #15–#19）。前提一级怎么取舍仍是主创的事。
- **实际用量。** 全部在 2026-10-14 一天之内；编排方之外约 19 路子代理：功能地图写作 2、候选 A 核对 6、检索 2（四批怎样分给这两路没有核）、对账 1、底账分三段 3、临时脚本与问题单 2、前提写作 1（写了两轮）、前提核对 2。前提层的「写 → 核」走了两整轮，每轮都要读全量材料。路数是按编排会话的代理名册数的，没有逐路核工时；把握：中。v1 给 0.1–0.5 估的是「功能地图与底账 3–4 个代理工作日、检索 1–2」，没有为回路留量。

**步骤**（原表保留，逐步标状态；谁做见 §9 任务清单）

| 步 | 做什么 | 产物（`projects/qige-xiongdi/runs/pilot-v2/`） | 对应方案步骤 | 状态（2026-10-14） |
| --- | --- | --- | --- | --- |
| 0.1 | 选线：默认四条——三年空白、礼物、监护程序、事故真相（集纲方案 §13 0.1；哨子芯片线不在 D6-0，因为它影响的集在 13 集之后且是物理前提，与前 12 集的季编排无关）。先做礼物＋三年空白（它们压着第 1、3、5、6、8–10 集，第 6 集是台词层的落点），再做监护、事故。为每条线写功能地图，现行实现作候选 A | `function-map-v0.json/.md` | O 0.1 | 完成（四条线，49 个功能、49 个候选 A） |
| 0.2 | 对每个候选 A 跑追问单（16 问），记录；标准是 K1 卡，与两份审查的对照只作旁证（§2.5 #19） | `reality-check/RC-*.json` | O 0.2 | 完成（49 份记录：46 份不成立、1 份成立、2 份成立但有未核） |
| 0.3 | 检索代理（可联网，主创第 2 条决定）对四条线涉及的程序与行业做法逐条查出处，写 K1 卡；现实审查 §六已有的来源直接入卡；查不到的写「查了什么、没查到什么」 | `knowledge/cards/K1-*.json`、`knowledge/sources/` | O 0.3 | 完成（四批 50 张卡，空卡 5 张；后两批由追问与前提带出） |
| 0.4 | 为四条线写底账（六类账），用户给定的标 `user_given`；跑临时脚本核集纲方案 §10.2 的规则 | `ledger-ep000.json`、`ledger-check-ep000.json` | O 0.4 | 完成到 `pre-select` 阶段（400 条；矛盾 23 对未清零——登记的是候选 A 的世界） |
| 0.5 | 为每个被否定的功能写候选 B（可多于一个），跑追问单，选定；写设定核对报告与决定队列（每条带默认） | `function-map-v1.json`、`decisions.json`、`setting-check-report.md` | O 0.5 | **未完成，停在这里**：前提层两轮未过追问单；分线候选 B、设定核对报告、决定队列未产出 |
| 0.6 | 季编排：只对受四条线影响且在第 1–12 集范围内的集重排；用媒介档案 v0 算容量（两口径）；超出的集记录处理动作（三选一必选） | `season-plan-v0.json/.md`、`capacity-season-v0.md` | O 0.6 ＋ D 0.6 的粗估提前 | 未开始（临时脚本已写，只过合成夹具） |
| 0.7 | 按 14 字段写第 5–7 集分集计划（礼物线落点；第 6 集有对照组）；`infoLedger` 带 `facts[]`；跑 §10.2 的规则与容量复核；若第 6 集复核仍超两倍，提案带默认拆法并按默认写 | `episode-plan-00{5,6,7}.json/.md`、`plan-check-*.json` | O 0.7 | 未开始（临时脚本已写，只过合成夹具） |
| 0.8 | 分集计划冷读：新上下文只装某集 `events`，提示词按 §2.6 #6；对照 `infoLedger(facts)` 与 `closingEvent` | `retell-plan-00{5,6,7}.json` | O 0.7 后半 | 未开始（临时脚本已写，只过合成夹具） |
| 0.9 | `ledger knows` 临时实现：从知识账导出第 6 集每个在场人物的 `knows / notKnows` | `knows-ep006.json` | 新 | 未开始（临时脚本已写） |
| 0.10 | C5a：第 6 集对话表（`segments[]`、`listenerKnows` 从 0.9 来、`exemplars.source` 三类、c2 那类信息必须有对象或独白理由）；装 138 条里的同处境正反例，`no_exemplar` 如实标 | `dialogue-plan-ep006-v2.json/.md` | D 0.7 | 未开始 |
| 0.11 | C5b：按对话表生成正文；`plan-text-map` 标 `verbatimFrom`；8 字档对装包样本、13 字档全库、禁词扫描 | `ep-006.g1.md`、`plan-text-map-ep006-v2.md` | D 0.8 | 未开始 |
| 0.12 | 冷读复述（只装 g1，提示词按 §2.6 #6）；处境对照（15＋2 问，**双跑**）；一致性核对；`dialogue-diagnose`（含 `INFO_REPEATED`）对 g1、f1、e2、w1 并排只列信号；`capacity text` 两口径 | `retell-ep006-g1.json`、`check-ep006-g1.json`×2、`consistency-ep006-g1.md`、`signals-ep006.md` | D 0.9 | 未开始 |
| 0.13 | 对照报告：新第 6 集估时对目标（与 f1 的 9–10 分钟并排）；冷读覆盖（g1 vs f1 vs e2）；追问单对新实现的回答；C5a 有没有退回；7 条批注在 g1 对应位置是否仍在（抄的行单列）；两轨底账差异（计划轨 vs g1 的实际轨）；暴露的 schema 修正点清单 | `docs/d6/d6-0-report.md`（只有编号与统计，不含私有正文） | O 0.9 ＋ D 0.10 | 未开始（已出的是中期报告，不是对照报告） |

顺序上的更正：第一轮先做 0.2（追问）后做 0.3（检索），结果是 28 条未核规则在追问答完之后才有卡。重开时检索在追问之前，题目由功能地图的程序类断言归并（§2.5 #18）。

**v1 验收的逐条状态**见中期报告第二节：功能地图一条不满足（没有一个功能有选定的候选 B）；底账一条不满足（矛盾未清零，因为还没有选定候选）；其余各条未开始；设定核对报告、决定队列、对照报告未产出。

#### D6-0 续：重开的范围、步骤与验收

**重开前要有的输入**

- 空白期前提的方向性倾向：主创已给（记在 §5.1；它是项目级事实，不写进任何技能规则）。
- 哪些场面作为戏剧假定保留：主创还没有答。不阻塞：按 §2.5 #16 的默认，不合常规而又没有合格候选的用户给定场面一律先标 `license_pending`。
- §8 #7–#9 三条：主创 2026-10-14 已确认（「同意按你的，继续做」）。

**范围（两个选项）**

| 选项 | 做什么 | 理由与代价 |
| --- | --- | --- |
| **默认：前 12 集先收敛** | 只把第 1–12 集用到的前提与功能收敛（选定或登记），然后把 0.6–0.13 走完；其余功能保持候选 A，标「未重核」 | 0.6 以后的步骤（季编排第 1–12 集、第 5–7 集分集计划、第 6 集台词层）只依赖前 12 集，这是拿到下游证据的最短路。代价：前提是全剧的，只按前 12 集收敛的前提可能在后段重开缺口——这些登记为 `leavesOpen`，对照报告不得写成「四条线已收敛」 |
| 四条线全做 | 四条线的全部功能选定或登记之后再进 0.6 | 上游证据完整。工作量是默认的一倍半到两倍，而前提层在新规则下能不能收敛本身把握低，先把全部功能压在它上面风险大 |

**步骤**

| 步 | 做什么 | 产物 | 代理 |
| --- | --- | --- | --- |
| R1 | 把第一轮的 49＋14 份回答记录按新字段补标：承重的依据收紧到「记录原话」与「有下游转引」两种，补 `defectKind`、`because`；按范围筛出前 12 集用到的前提与功能 | 缺口登记表 v2、范围清单 | 脚本代理＋核对代理 |
| R2 | 按主创的方向性输入重写范围内的前提：多个前提一起选；每引入一个知情人、一份文书、一个账户先写它按常规接下来会做什么；每个默认候选里一倒全倒的未核假设至多一条；用户给定的前提默认保留 | 前提 v3 | 写作代理 |
| R3 | 前提带出的检索题目归并 → 检索写卡（可与 R4 并行；晚到的卡由 `cardRevisions` 标出要重答的回答） | K1 卡 | 带检索的代理 |
| R4 | 默认前提的组合过追问单（新上下文）；填跨前提一致性表 | 前提追问记录、一致性表 | 核对代理 |
| R5 | 范围内分线写候选 B（引用前提），过追问单；「关掉了哪些缺口」由核对记录确认，不取写作方自报 | `function-map-v1`、候选 B 追问记录 | 写作代理 → 核对代理 |
| R6 | 换实现至多 2 次（R2–R5 算第一次）。到顶后仍在的承重缺口登记：戏剧假定（`license_pending`）或决定队列（带默认）。选定；旧实现的条目标 `retired`；`ledger check` 按默认阶段跑；写设定核对报告、戏剧假定清单、决定队列 | 底账修订、`decisions.json`、`setting-check-report.md`、戏剧假定清单 | 写作代理＋脚本代理 |
| R7–R14 | 原 0.6–0.13，内容不变 | 同上表 | 同 §9 任务 10–17 |

**验收（分判，没有数值门槛，不需要编剧投入；只引 S）**

- 功能地图（S，临时脚本）：范围内每个功能有 `selected` 实现，或已登记为保留用户给定的实现；选定实现的回答记录里，每条 `loadBearing: true` 的 `notHolds` 带 `disposition`，它引用的对象存在且状态相符——核对记录（确认消失）、状态为两种戏剧假定之一的底账条目、或 `default` 非空的决定队列条目；没有 `losesFunctions[]` 非空而被标 `selected` 的候选；`closes[]` 的每一项有核对记录引用；被否定的候选有 `rejectedBecause`；范围外的功能标了「未重核」。
- 前提（S）：每个前提问题有默认与决定队列条目；跨前提一致性表无空格；功能地图勘误清零。
- 底账（S）：范围内依赖的条目齐；默认阶段 `contested` 为零；`unverified` 清单与戏剧假定清单存在并注明依赖的集；`accepted_license` 的条目都有 `humanWords`；集纲方案 §10.2 的规则对 `ledger@ep000` 与三集 planned delta 全过。
- 季编排（S）：受影响的集每集有 `capacity` 记录；超出的有 `action`，没有「待定」；没有系统默认选的删线。
- 分集计划（S）：三集 `plan-check` 全过；冷读只读 `events` 复述出 `facts` 每条与 `closingEvent`（`missing` 为零；若非零，回 C4 一次后再核，记录两次）。
- 对话表与正文（S）：每个 `fact` 有承载句或画面理由；每个 `segment` 有 `closer`；`listenerKnows` 与知识账无矛盾；对齐无未登记偏离；两档 `dup-check` 零命中；禁词零命中；C5a 若有退回，`changeProposal` 记录在且带默认。
- 冷读与问题单（S 记录在，M 内容附证据）：复述每条 `fact` 有行号；17 问每问有引用与原因；双跑一致性记录在；「不成立」项已回对话表修订并复读；记录带 `promptVersion`。
- 设定核对报告与决定队列（S）：每条 `user_given` 的不成立项都有默认（按候选走，或保留并标 `license_pending`）。
- 对照报告在 `docs/d6/`，不含私有句子；分开数 `closes`、`retiresWith`、`leavesOpen`，并报戏剧假定清单与决定队列各有多少条（只描述，不设门槛）。
- 附证据、不作通过条件（M）：缺口承不承重的判断；缺口是否真的消失；戏剧假定是否只豁免了它自己那一处。

**退出条件**：上述 S 项全过；对照报告写明「哪些 schema 要改」。任一方不过，停在 D6-0 重看成因，不进 D6-1。换实现预算到顶不是停的理由——登记之后继续。新规则下 C3a 不会再因为不成立项而停住；它是真的收敛了，还是只把问题挪进了清单，看的是戏剧假定清单与决定队列的长度和内容，这由读对照报告的人判断。
**工作量（按第一轮的实际重估）**：默认范围 10–14 个代理工作日——R1 约 1；R2–R6 两次换实现的回路 4–6（每次：写 1、检索 0.5–1、核 1，另加登记与清单 1）；R7–R14 即原 0.6–0.13，5–7（原估：季编排与分集计划 2–3、台词层一集 2、核对与报告 1–2）。四条线全做约 16–24。把握：低——回路这一段是按第一轮两轮的观察估的，新规则下每轮读多少材料没有实测；R7 以后的步骤没有任何实测。连同已经花掉的第一轮，D6-0 的总量明显超过 v1 的 8–12。
**回滚**：全部产物在 `runs/pilot-v2/` 与 `docs/d6/`，删目录即回滚；不碰技能、mali-story、现有集纲页面。

### 4.2 D6-1：对象与只读工具（旧流程可用，0.4.0）

**目的**：把 §2.1 的 20 个对象与 §2.2 的命令实现成随包工具，用 D6-0 与 D6-0 续的产物做夹具；现有流程一字不改地继续可用。§2.8 的九项设计决定在本阶段开头定；各 schema 的必填项从真实夹具反推，不从方案的字段表照抄。

**交付物**

- `schemas/`：`function-map`、`ledger-entry`、`ledger-delta`、`question-set`、`answers`、`season-plan`、`episode-plan`、`decision-queue`、`media-profile`、`dialogue-exchange`、`corpus-manifest`、`contrast-pair`、`dialogue-plan`、`dialogue-target`、`writer-note`、`retell-record`、`plan-text-consistency` 各一个 `.schema.json`＋`examples/` 一例（`tests/test_contracts.py` 断言每个 schema 一例）；`task`、`review-record`、`run-handoff`、`context-snapshot`／`selection` 的字段扩展（旧例子仍通过）。数据文件：`reality-check-questions.json`、`dialogue-check-questions.json`、`constraint-blocklist.json`（放 `data/`，`validate.py` 对非 schema JSON 的检查要放宽为「允许 `data/` 下的数据文件」，与 `examples/` 同法）。
- `scripts/checks/`：`ledger.py`、`plan_check.py`、`capacity.py`、`answers_check.py`、`retell_check.py`、`consistency.py`、`diagnose.py`、`decision.py`、`feedback_ingest.py`（骨架：writer-note 与路由，派生物在 D6-4 补全）、`corpus/`（`segment`、`label` 的 S 部分、`filter`、`lexicon`、`rate`；`fetch` 放 D6-4）；`context_pack.py` 新角色与装包规则；`season_check.py` 新规则**实现但按项目自动选集**（见下）；`dup_check.py` 的 `--list-hits --k`；`episode_check.py` 口播量统计。
- `drama_tools.py` 子命令；`SKILL.md` 随包工具表同步（`test_skill_routing.py` 要求）；`README.md` 记命令。
- `tests/`：每条 S 规则一个正反用例；`season-check` 的旧测试全部不动且通过。

**新旧并存怎么处理**

- `season-check --outline`：项目有 `planning/season-plan.json` 时跑新七条＋旧八条里仍适用的（`outline-sequential`、`outline-review`、`saved` 等），没有时只跑旧八条；输出 `ruleSet: legacy | outline-layer`。《渊心锁》与本项目现有记录没有季编排 → `legacy`，结果与今天完全一致（测试锁定）。
- `season-check --episodes`：项目有对话表记录时跑正文侧新规则并跳过 `voice-card`／`dialogue-pass`／`dialogue-read`；没有时跑旧规则。D6-1 阶段两套都在；D6-3 才把旧三条改为只在 `--legacy-dialogue` 下跑。
- 其余新命令都是只读、按需调用，不改任何现有产物。

**验收（S）**：全部新 schema 正反用例通过；D6-0（含续）的 `function-map-v1`、49＋14 份第一轮回答记录、三段真实底账与合并后的 `ledger-ep000`＋三集 delta、`season-plan-v0`、三份 `episode-plan`、`dialogue-plan-ep006-v2`、两份 retell、`check-ep006-g1` 作为夹具全部通过对应命令（`ledger replay` 能从 `ep000` 重放到第 7 集）；`capacity` 对 `episode-plan-006` 与 g1 的输出与 D6-0 的临时脚本一致（允许 ±1 秒舍入）；`season-check` 对《渊心锁》与本项目的旧记录输出与 0.3.6 逐字节一致；`validate.py` 通过；`test_skill_routing` 通过。
**退出条件**：上述全过；0.4.0 发布可安装（`install.py verify`）。
**工作量**：10–14 个代理工作日（schema 与契约 3，底账与计划工具 3–4，容量与核对命令 2，语料 S 命令 2，season-check 并存 1–2，测试与文档 2）。语料命令与底账工具并行可压到 8–10 天。
**回滚**：删新文件、还原四个扩展 schema 与 `season_check.py`／`context_pack.py` 的改动；旧流程未被触及，所以回滚不影响任何项目。

### 4.3 D6-2：切换集纲层（0.5.0）

**目的**：新项目和新写的集纲默认走 C3a→C3b→C3c→C4 分集计划；`season-check --outline` 的新规则对新项目生效。

**交付物**

- 文档：新 `references/outline-layer.md`；`planning.md` 重写「蓝图、设定圣经与集纲」；`workstation-c3-structure.md` 拆三份；`c4-episode-outline.md` 改写；`c6-review.md` 加集纲侧三读（追问单复核、底账一致性、分集计划冷读）；`season-run.md` §1；`workstations.md` 索引与执行层级表；`approval-flow.md` 四份附录；`recovery.md` 恢复顺序；`SKILL.md` 路由与「一次完整创作」第 6 步。
- 工具：`season-check --outline` 新规则对有季编排的项目启用（D6-1 已实现）；`context-pack` 对 C4 装包要求季编排与底账在包里（`outline-season-assigned`、`outline-ledger-delta`）。
- 退役（集纲侧）：六字段作为计划格式；「关键选择」字段与审读硬项；260 字上限；`notes-*.md` 段末状态；框架第七节道具表、第九节节拍表；圣经第五节信息阀门表；`open-issues`；分段送审的「只改一次、不动集数」约束（升 S，`constraint-blocklist`）。文档里的对应段落删除或改写，旧项目文件不动。

**验收（S）**：`validate.py`；`test_skill_routing`（路由行、命令表）；`season-check --outline` 对 D6-0 产物（搬成项目记录形态）全过，对《渊心锁》仍 `legacy` 且结果不变；`contract-check task` 拒绝「不动集数」类约束的正反用例；`context-pack --role author`（C4）在缺季编排时退出码 2。M 项附证据：在一个新建的空项目上，按新文档从 C1 走到第 1 集分集计划（为说明而编的材料），记录运行与交接，附在 `docs/d6/d6-2-walkthrough.md`，不作通过条件。
**退出条件**：上述 S 全过；0.5.0 可安装。
**工作量**：5–7 个代理工作日（文档 3–4，规则启用与测试 1，走通一遍 1–2）。
**回滚**：恢复文档到 0.4.0；`season-check` 新规则仍按项目自动选集，所以已经用新流程写的项目记录不会因回滚而失效（它们只是不再被核）。

### 4.4 D6-3：切换台词层并退役台词遍／台词读（0.6.0）

**目的**：正文默认走 C5a→C5b→C6 五读→先改表再改文；台词遍、台词读、声音卡关口退役。

**交付物**

- 文档：`writing.md` 工位流程第 4–7 步、「篇幅与时长」改为容量算术、「避免用解释性台词」条改写；`dialogue.md` → `dialogue-structure.md`（保留 §8、§9）；`c5-screenplay.md` 拆 `c5a`／`c5b`；`c6-review.md` 加正文侧两读（冷读复述、处境对照）与设计依据一致性；`season-run.md` §3；`SKILL.md` 路由「台词 AI 味重」行、「一次完整创作」第 4 步；`character-emotion.md`、`creative-loop.md` 里引用台词遍的句子改指对话表。
- 工具：`season-check --episodes` 正文侧新规则对有对话表的项目启用；`voice-card`／`dialogue-pass`／`dialogue-read` 只在 `--legacy-dialogue` 下跑（历史记录仍可查）；`context-pack` C5b 装包要求对话表带通过的 `contract-check`，C5a 装包要求容量状态合规（§2.5 #1）。
- 退役（台词侧）：K5 声音卡降为索引（`knowledge search --type K5` 仍可用，不再是装包必需）；K9 对照卡废除（已有卡保留可读）；台词遍、台词读、「盖住名字猜人」；修订后不再读；`preserved` 清单只认人工来源；修订单含替换文字或数值指令被拒；`min_chars: 800`、450 字/分口径（留在 `legacy-aigc` 预设）；项目 `writer-style-brief.md` 的条目经 `feedback-ingest` 回流后文件退役（本项目的事，在 §5）。

**验收（S）**：`validate.py`；`test_skill_routing`；`season-check --episodes` 对 D6-0 的第 6 集记录（搬成项目记录形态）全过；对本项目第 1–10 集旧记录在 `--legacy-dialogue` 下输出与 0.3.6 一致，不带该参数时三条旧规则不出现且无新失败（新规则按「有对话表才核」）；`contract-check task` 拒绝「少 40 字」「不超过 3 行」类约束；修订单扫描拒绝 SPEAKER 格式行；`context-pack --role author`（C5b）在对话表未过 `contract-check` 时退出码 2；`retell-after-revise` 在修订后缺复述记录时失败。M 项附证据：D6-0 的 g1 冷读与问题单记录。
**退出条件**：上述 S 全过；0.6.0 可安装；`writing.md` 里不再出现「台词遍」「台词读」作为步骤（`test_skill_routing` 的 needle 列表同步改）。
**工作量**：5–7 个代理工作日。
**回滚**：恢复文档到 0.5.0；`--legacy-dialogue` 的存在让旧记录永远可核，所以回滚不丢证据。

### 4.5 D6-4：语料库与反馈回流（0.7.0）

**目的**：把 D6-0 的手工语料流程做成可重复的命令；人工反馈的回流全路由打通；台词目标可升版。

**交付物**

- `corpus fetch`（重试、断点、`expected_snapshot_id`、取前后记预算与回执）；取用前先按 §8.1 的默认（项目级）放目录，主创确认工作室级后挪目录并改 `scope.level`。**计费确认是事实核查不是主创决定**：先取 3 部各 10 集，看 `get_shared_creation_budget` 与回执；有扣费迹象即停并记录，未确认前不取全库（台词方案 §12.1）。
- `corpus label/walkthrough` 的双跑比对与一致性记录；词表按 stage-a §8.4 收敛；`speakerAttributionSuspect`。
- 补语料：有险情处置、孩子指挥大人、偷偷示好的现实题材样本（stage-a §8.3 的三类缺口）；覆盖报告只列处境计数。
- `genre-lexicon` 两张禁词表由脚本从语料重算；`media-profile-defaults.json` 重算（标 n）。
- `feedback-ingest` 全路由（§2.2 #9）：对本项目 7 条批注、`writer-edit-pairs.md` §二、现实审查里的程序类意见各跑通一次，派生物可追溯到 note。
- `references/corpus.md`、`mali-story.md` 加语料读取与计费观察；`README.md`。

**验收（S）**：`corpus` 各子命令夹具可复算；双跑不一致记 `low` 且 `low` 不进检索结果；带项目句子的 studio 记录被拒；`feedback-ingest` 对一条编造的批注与一条编造的「这个程序不是这样走的」各产出正确去向（反例／底账修订提案）；无来源条目不进包；`dialogue-target` 升版有 changelog 且 `task` 引用旧版仍通过。计费观察记录在 `docs/d6/d6-4-corpus.md`（只有调用次数、预算读数、回执 ID）。
**退出条件**：上述全过；0.7.0 可安装。全库取用若计费未确认，D6-4 以小样本（≥3 部）结束并把全库列为待办，不阻塞 D6-5。
**工作量**：6–9 个代理工作日（fetch 与断点 1–2，标注与双跑 2，补语料 1–2，feedback-ingest 2，文档 1）；全库取用约 695 次调用按串行 20–30 分钟，标注约 695 集 × 3–4 次模型调用，是时间不是工作日。
**回滚**：语料是只读缓存，删目录即回滚；`feedback-ingest` 的派生物带 note id，可按 id 清除。

### 4.6 D6-5：清理与文档（0.7.x）

**目的**：把架构文档、路线图、三份旧设计、两份方案的修正点收口；评估页面化；关闭退役表。

**交付物**：架构 v1.3（§2.3）；路线图加注；三份旧设计状态行；两份方案按 §2.6 回写；D4-5 加注；退役表（§4.8）每项的处置状态填「已废除／已重构／保留」并指向文件；页面化评估页 `docs/d6/d6-5-pages.md`（功能地图、底账、分集计划是否值得作 mali-story 页面：按 R 级能力发现写，不实现）；`docs/d6/README.md` 汇总 D6-0 至 D6-5 的证据与 D7 候选（第二部剧 N=2、`speechRate` 实读校准、页面化）。
**验收（S）**：`validate.py`（所有链接）；`test_skill_routing`；全部测试通过；`season-check` 对三类项目（旧《渊心锁》、本项目旧记录、D6-0 新记录）结果与 D6-4 一致。
**工作量**：2–3 个代理工作日。
**回滚**：文档改动，`git revert`。

### 4.7 D7 候选（不在 D6 内）

- 第二部剧（不同题材或形态）从 C3a 走一遍，看追问单、六类账、季编排容量、处境词表跨剧够不够用；N=2 报告（两份方案的阶段 3）。
- 本剧有成片或配音实读时校准 `speechRate`、`pauseShare`，档案转 `project_measured`。
- 功能地图、底账、分集计划页面化（R）。

### 4.8 旧组件退役表（两份方案合并）

「阶段」是废除或重构发生的阶段；「旧项目文件不动」对所有行成立。「处置状态」按 D6-1–D6-3 的实际改动核对（D6-5，2026-10-15）：已废除、已重构、保留、待办，D6-4 相关的标「D6-4 进行中」；「实际文件」指向承载它的现行文件，路径相对 `skills/drama-studio/`（`docs/` 开头的除外），只写文件名的在 `references/` 或 `references/workstations/` 下。

| # | 组件 | 处置 | 阶段 | 来源 | 处置状态（2026-10-15） | 实际文件 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 六字段集纲（作为计划格式） | 废除；`episode-plan` 取代 | D6-2 | O#1 | 已废除 | `schemas/episode-plan.schema.json`；`references/outline-layer.md` §9 |
| 2 | 六字段（作为派生摘要） | 重构为可选 `summary`，S 核无新实体 | D6-2 | O#2，主创已定 | 已重构 | `episode-plan.summary`；`plan-check` 的 summary 粗核（只报）；`outline-layer.md` §9 |
| 3 | 「关键选择」字段与审读硬项 | 废除；并入 `moves[]` | D6-2 | O#3 | 已废除 | `references/workstation-c4-episode-outline.md`、`c6-review.md`（集纲侧三读不再设此硬项）；`moves[]` |
| 4 | 剧情框架 260 字上限 | 废除 | D6-2 | O#4 | 已废除 | `c4-episode-outline.md`「停止与边界」（不设字数上限） |
| 5 | `planning.md`「蓝图、设定圣经与集纲」 | 重构 | D6-2 | O#5 | 已重构 | `references/planning.md` |
| 6 | C2 工位文档 | 保留＋收窄（只写人；前史事件须有账条目） | D6-2 | O#6 | 已重构 | `references/workstation-c2-characters-world.md`；`plan-check --characters` |
| 7 | C3 工位文档 | 重构为 c3a/b/c | D6-2 | O#7 | 已重构 | `references/workstation-c3a-function-map.md`、`c3b-ledger.md`、`c3c-season-plan.md`（`c3-structure.md` 已删） |
| 8 | C4 工位文档 | 重构（14 字段；六步保留） | D6-2 | O#8 | 已重构 | `references/workstation-c4-episode-outline.md` |
| 9 | 设定圣经 `bible` | 重构为输入（拆成 `user_given` 功能与条目） | D6-2 | O#9 | 已重构 | `outline-layer.md` §11；`planning.md` |
| 10 | `framework-vN.md` | 重构：结局与因果链 → 功能地图；分卷蓝图 → 季编排卷级视图；第五节程序口径 → 程序账；第七节道具表 → 物件账；第九节节拍表废除 | D6-2 | O#10、#15 | 已重构 | `planning.md`（结局与因果链进功能地图、分卷进季编排卷级视图）；`outline-layer.md` §2、§4、§8；节拍表不再出现 |
| 11 | `notes-*.md` 段末「给后段」 | 废除；底账逐集修订取代 | D6-2 | O#11 | 已废除 | `outline-layer.md` §4（底账两轨逐集修订）；技能文档里已无段末「给后段」 |
| 12 | `runs/state/after-ep-NNN.md` | 重构为底账实际轨的导出（文件名沿用） | D6-2 | O#12、§2.5 #14 | 已重构 | `ledger replay --md`；`references/workstation-season-run.md` §1 |
| 13 | 集纲审读（`review-record` 对 `episode_outline`） | 重构：追问单复核、底账一致性、冷读；finding 带 `cites` | D6-2 | O#13 | 已重构 | `references/workstation-c6-review.md`「集纲侧三读」；`review-record.finding.cites` |
| 14 | `season-check` 集纲八条 | 保留＋扩七条；按项目自动选集 | D6-1 实现、D6-2 启用 | O#14 | 已重构 | `scripts/season_check.py`（`ruleSet: outline-layer`，有季编排时启用） |
| 15 | 圣经第五节信息阀门表 | 重构为知识账 | D6-2 | O#16 | 已重构 | `outline-layer.md` §4 知识账 |
| 16 | `open-issues` /「待主创定」 | 重构为决定队列（带默认） | D6-2 | O#17 | 已重构 | `schemas/decision-queue.schema.json`；`outline-layer.md` §10；`decision` 命令 |
| 17 | 分段送审＋「只改一次、不动集数、不动标题、不动★」 | 废除；升 S（`constraint-blocklist`） | D6-1 实现、D6-2 启用 | O#18 | 已废除 | `data/constraint-blocklist.json`；`contract-check task`；`references/approval-flow.md` |
| 18 | 对标仿写技能的「精简五要素」 | 不动，不再引用 | D6-2 | O#19 | 保留 | 技能包内无引用（对标仿写技能本身不动） |
| 19 | 台词方案 C4 一行 | 由集纲方案细化 | D6-2 | O#20 | 已重构 | `c4-episode-outline.md`；`outline-layer.md` §9 |
| 20 | `development-lab.md` §1 生活材料 | 保留＋接入检索代理 K1 卡 | D6-2 | O#21 | 保留 | `references/development-lab.md` §1（保留，并写明集纲层的程序、行业做法与技术前提由检索代理写成 K1 卡，链到 `outline-layer.md` §6） |
| 21 | `c3-structure.md`「删掉一段…」 | 保留，移到 c3c | D6-2 | O#22 | 保留 | `references/workstation-c3c-season-plan.md` |
| 22 | `writing.md`「装不下不压台词，提 C4 变更」 | 保留 | — | O#23 | 保留 | `references/writing.md`「篇幅与时长」；`c5b-text.md` |
| 23 | 声音卡 K5 | 重构为索引；不再是判据与装包必需 | D6-3 | D#1 | 已重构 | `references/dialogue-structure.md` §9；`c2-characters-world.md`（`knowledge search --type K5` 仍可用） |
| 24 | 对照卡 K9 | 废除；writer-note＋反例＋对照对取代 | D6-3 | D#2 | 已废除 | `dialogue-structure.md` §9（不再新建，已有卡保留可读）；`writer-note`、`contrast-pair` |
| 25 | 台词遍（`dialogue_author`） | 废除；C5a＋C5b 取代 | D6-3 | D#3 | 已废除 | `dialogue-structure.md`；`references/workstation-c5a-dialogue-plan.md`、`c5b-text.md` |
| 26 | 台词读（`dialogue_read`） | 废除；冷读复述＋处境对照＋一致性取代 | D6-3 | D#4 | 已废除 | `references/workstation-c6-review.md`「正文侧」（冷读复述、处境对照、设计依据一致性） |
| 27 | 「盖住名字猜人」 | 废除 | D6-3 | D#5 | 已废除 | 技能包内已无此做法 |
| 28 | `season-check` 的 `voice-card`／`dialogue-pass`／`dialogue-read` | 废除；`--legacy-dialogue` 可查 | D6-3 | D#6 | 已废除 | `season-check --legacy-dialogue`（只查旧记录） |
| 29 | 每批一次定向修订 | 重构：对象换成对话表；修订后复读必做 | D6-3 | D#7 | 已重构 | `references/workstation-season-run.md` §3 第 9 步；`dialogue-structure.md` §8 |
| 30 | 修订后不再读 | 废除 | D6-3 | D#8 | 已废除 | `season-check` 的 `retell-after-revise` |
| 31 | `preserved` 清单 | 重构：只认人工来源 | D6-3 | D#9 | 已重构 | `season-check` 的 `preserved-human-source`；`contract-check review-record`（集纲侧）；`c6-review.md` |
| 32 | 修订单写替换文字 | 废除并升 S | D6-1 实现、D6-3 启用 | D#10 | 已废除 | `schemas/revision-list.schema.json`；`season-check` 的 `fixlist-no-lines` |
| 33 | 数值型台词目标 | 废除并升 S | D6-1 实现、D6-3 启用 | D#11 | 已废除 | `constraint-blocklist.json`；`contract-check task`；`season-check` 的 `no-numeric-dialogue-constraint` |
| 34 | 按人物组织的卡片 | 重构：人物只作项目内索引 | D6-3 | D#12 | 已重构 | `dialogue-structure.md` §9；`c2-characters-world.md`（K5 只作人物索引） |
| 35 | C5 场面稿 | 重构为 C5a／C5b | D6-3 | D#14 | 已重构 | `c5a-dialogue-plan.md`、`c5b-text.md`（`c5-screenplay.md` 已删） |
| 36 | C6 首读 | 保留 | — | D#15 | 保留 | `c6-review.md`「正文侧」第 1 读 |
| 37 | C6 次读 | 保留＋加义务（`cites`） | D6-2 | D#16 | 已重构 | `c6-review.md`「正文侧」第 2 读（`evaluation` 角色、`cites`） |
| 38 | 篇幅口径（`min_chars: 800`、450 字/分） | 废除；留 `legacy-aigc` 预设 | D6-3 | D#17 | 已废除 | `references/episode-check.md`（默认只统计；旧规格只在 `--preset legacy-aigc` 下）；`capacity text` |
| 39 | `episode-check` | 重构：加口播量统计（估时在 `capacity`） | D6-1 | D#18 | 已重构 | `scripts/episode_check.py` 口播量统计；估时在 `capacity text` |
| 40 | `context-pack` 角色 | 重构：新角色 | D6-1 | D#19、O#18 | 已重构 | `scripts/context_pack.py`（`function_mapper`、`ledger_keeper`、`season_planner`、`dialogue_designer`、`situation_checker`、`cold_reader`） |
| 41 | `dialogue.md` §1「书面腔」表 | 重构 | D6-3 | D#20 | 已重构 | `dialogue-structure.md` §5（`dialogue.md` 已改名，旧表不再保留） |
| 42 | `writing.md`「避免解释性台词」、项目 `writing-rules.md` | 重构 | D6-3；项目文件见 §5 | D#21 | 已重构 | 技能部分：`writing.md`；项目 `writing-rules.md` 属本项目的事，见 §5（待办） |
| 43 | `dialogue.md` §8、§9 | 保留 | — | D#22 | 保留 | `dialogue-structure.md` §10、§11 |
| 44 | C2 声音探针 | 保留 | — | D#23 | 保留 | `c2-characters-world.md` |
| 45 | 「另一模型家族做台词读」 | 废除 | D6-3 | D#24 | 已废除 | 技能包内已无此做法 |
| 46 | 项目 `writer-style-brief.md` | 重构：经 `feedback-ingest` 回流后退役 | D6-4；项目文件见 §5 | D#25 | 已重构 | 技能侧：`feedback-ingest --out`（按 `level` 全路由出派生物，`--purge` 按 note 撤回）、`references/dialogue-structure.md` §9；项目的 `writer-style-brief.md` 是项目文件，回流后退役属本项目的事（§5） |
| 47 | 工艺闭环 §4.4、§4.5 | 废除（被取代） | D6-3、D6-5 状态行 | D#26 | 已废除 | 技能侧由 `c5a-dialogue-plan.md`、`c5b-text.md` 取代；`docs/design/drama-studio-craft-loop-design-2026-10-10.md` 文首已加 D6-5 状态行 |
| 48 | 工艺闭环 §3 分层 | 保留概念 | — | D#27 | 保留 | `docs/design/drama-studio-craft-loop-design-2026-10-10.md` §3（概念） |
| 49 | 样本库设计 §3 分级 | 倒置 | D6-4 | D#28 | 已重构 | `references/corpus.md`（Tier 1／Tier 2 按可记录的筛选条件分，`grade: human` 为人工正例）；`corpus agree` 双跑比对，不一致记 `labelConfidence: low`，`corpus filter` 让 low 的维度不进检索；样本库设计文首 D6-5 状态行 |
| 50 | 样本库设计 §7 数数关口、§8 覆盖卡、§5 第 1／7 步 | 废除 | D6-4 | D#29、30、32 | 已废除 | 数数关口与覆盖卡从未进技能；`docs/design/drama-studio-dialogue-sample-library-design-2026-10-13.md` 文首 D6-5 状态行即其处置 |
| 51 | 样本库设计 §9 留出法 | 保留为可选描述 | — | D#31 | 保留 | 样本库设计 §9（可选描述，未接入流程） |
| 52 | v2 媒介档案配额字段、`acceptedBand`、分布距离、`within/outside` | 废除（schema 拒绝） | D6-1 | D#33 | 已废除 | `scripts/contract_check.py` 的配额字段拒绝（`QUOTA_KEYS`） |

## 5. 本项目的处理

这一节只给事实与选项，不替主创定内容方向。阶段 D6-0 自身只产证据，不改任何集纲页面与正文页面。

### 5.1 现状（事实）

- 集纲：60 集 `episode_outline` 页面（r2／r3），分五段写成；结构审查 0/60 剧情框架自足；56 条提案待主创决定。
- 正文：第 1–10 集页面 r4／r5；第 1–5 集有编剧改定稿（w1）；第 6–10 集有台词调整稿已交付飞书；第 6 集另有 e2（旧流程）与 f1（台词方案阶段 0）两版试验稿，都未入页面。
- 送审包 v3 待审批（框架 v3、小传 v2、集纲 1–60、前 10 集正文）。
- 地基不成立的线（现实审查 §四）：三年空白、礼物、监护程序、事故真相、哨子芯片；钱的线是账的空字段。受影响的集见集纲方案 §17 的表。
- 已写并经编剧改定的第 1–5 集里，建在这些地基上的场面：第 1 集退件单、「回乡下」的信、存折；第 3 集监护材料；第 4 集民警离开；第 5 集方砚与仓管两个电话；第 6 集整场物流仓与监察员（集纲方案 §17）。不建在这些地基上的部分（油锅、巴掌、账本、哨声、手环、民警问话分寸、错名）不受影响。
- 容量：60 集每集事件中位 11；第 6 集按对白承载估 9–10 分钟（两口径），前五集定稿 66–156 秒。
- D6-0 第一轮（2026-10-14，[中期报告](../d6/d6-0-interim.md)）在四条线上产出了：功能地图 v0（49 个功能，现行实现作候选 A）、候选 A 的追问记录 49 份与缺口登记（137 处，承重 89，跨线 20）、50 张 K1 知识卡、前史底账 400 条。这些都在 `runs/pilot-v2/`；项目的集纲、正文、原有知识卡与 mali-story 页面没有动。
- 它停在候选 B 之前：跨线的 20 处缺口指向同一个前提（空白期里各方的总账），两轮前提各 7 个问题都没有通过追问单。这个前提每个成立的版本都要换掉一样用户给定或已改定的东西。选定的功能地图、设定核对报告、决定队列、季编排、分集计划、第 6 集的新对话表与正文都还不存在。
- 缺口的类型：材料缺写 50、动机 40、内部矛盾 39、知情 26、后果或机构动作没写 21、与现实规则相反 15（一处可多类）。用户给定条目 98 条里，状态为互斥的 12 条、查过没查到出处的 11 条。
- 主创 2026-10-14 给的输入有两条。其一，原话「停在这里先改方案」。其二，对空白期前提的方向性倾向，原话：「她真被送回乡下两年」。后一条是本项目的事实，只记在这里，不进任何技能规则；它是倾向不是定稿，重开时作为写前提的输入。
- 哪些场面作为戏剧假定保留，主创还没有答。

### 5.2 三种走法

| 走法 | 做什么 | 工作量（代理工作日） | 会动到的已改定内容 | 对送审包与页面版本的影响 |
| --- | --- | --- | --- | --- |
| **A 全季重做** | 全剧功能地图与底账（所有线，含哨子、学校消防、庭审、对手中层）→ 60 集季编排与容量 → 60 集分集计划重产 → 第 1–10 集按新计划重写（C5a→C5b）→ 第 11 集起按新流程写 | 功能地图与底账 8–12；季编排 3；分集计划 60 集 12–18（按 15 集一段）；前 10 集重写 10–15；合计 35–50 | 第 1–5 集编剧改定稿里建在五条线上的场面全部重写；不在这些地基上的场面尽量逐字保留（`season-run.md` 的保留场机制） | 送审包 v4 全包重绑（框架→功能地图＋季编排、小传收窄、60 集分集计划、前 10 集新正文）；按 `approval-flow.md` §4 属方向变更，全包复审一次；旧页面修订保留可回看；集数很可能变（容量处理后要么集数增、要么每集事件减到三分之一上下） |
| **B 只重建地基不成立的线** | D6-0 的四条线＋哨子线、钱的账；其余线沿用现集纲的事件（照正文回写的第 1–10 集事实索引多数是对的）；季编排只重排受影响的集；分集计划只重产受影响的集，其余集由脚本把六字段「搬」进 14 字段骨架并标 `migrated: partial`（缺的字段——入口、信息清单、状态变化、现实依据、容量——按集补） | 功能地图与底账 6–9；季编排 2；受影响集的分集计划约 30 集 6–9；其余 30 集搬运与补字段 4–6；受影响正文重写（第 1、3、5、6 集的对应场面）3–5；合计 21–31 | 第 1 集三处、第 3 集一处、第 5 集两个电话、第 6 集仓库与监察员；其余逐字保留 | 送审包 v4 局部重绑：受影响的集纲页面出新修订，其余页面不动；正文第 1、3、5、6 集出新修订；按 §4 仍是方向变更（主要人物关系与全剧结构被动），但复审范围可标明「只看变动集」；集数变不变取决于受影响集的容量处理 |
| **C 以 D6-0 的产出作起点** | D6-0 产出的四条线功能地图、底账、第 1–12 集季编排、第 5–7 集分集计划、第 6 集对话表与正文直接作为本项目新版的 v1；其后按新流程逐段推进（先第 1–12 集补齐分集计划与正文重写，再 13 集起），每段送审 | D6-0 本身 8–12（已算在实施计划里）；之后每段（12 集左右）分集计划 3–4＋受影响正文 2–3；全季约 25–35，但分散在流程里 | 与 B 相同，但按段逐步动，不一次性 | 送审包按段出新版（v4 只含第 1–12 集的新分集计划与第 1、3、5、6 集新正文；13 集起随后续段）；主创每段看一次，但不新增审批点——仍是「送审包审批」这一处，只是分批送 |

**各走法共同的事**：不管选哪条，`writer-style-brief.md`、`writing-rules.md` 的条目经 `feedback-ingest` 回流成 `drafted` 约定与反例（D6-4），文件退役；第 6–10 集的台词调整稿不再作为后续输入（它们建在旧第 6 集集纲上）；56 条待决提案由脚本搬进决定队列并各补一个默认走法；现实审查里「凭常识写、未查法条」的约 60 项成为底账的 `unverified` 清单初值。

**阶段 D6-0 的默认**：选线按 §4.1 0.1（礼物＋三年空白先做，再监护、事故）；重排范围限第 1–12 集；分集计划只写第 5–7 集；台词层只做第 6 集。这些是验证范围，不是项目决定；它们恰好是走法 C 的第一段，也是走法 A、B 的子集，所以无论主创之后选哪条，D6-0 的产出都不浪费。

**上表在 D6-0 第一轮之后要加的两条说明**（事实，不是建议）：走法 C 说的「D6-0 的产出」里，目前存在的只有功能地图 v0、候选 A 的追问记录、前史底账与知识卡；选定的功能地图、季编排、分集计划、对话表与正文要等 D6-0 续。三种走法的工作量是 v1 的估计，没有按第一轮的实际回路成本重估——第一轮说明上游这一段比估的贵，但分集计划之后的步骤还没有实测，现在重估没有依据。

**不替主创定的事**：选 A／B／C；哪条线的哪个功能可以 `dropped`；拆集后的总集数；第 1–5 集编剧改定稿里受影响场面的重写范围；哨子芯片线是否换实现（它是用户给定设定，按第 3 条决定会先按候选走并标 `pending`，但「要不要保留芯片这个设定」是内容方向）；空白期前提最终取哪个版本、为此换掉哪一样用户给定或已改定的东西；哪些不合常规的场面作为戏剧假定保留。后两件在主创定之前，系统按「保留并标 `license_pending`」走。

## 6. 风险与应对

| 风险 | 触发信号 | 应对 |
| --- | --- | --- |
| 底账维护成本高，写成套话或没人更新 | `ledger check` 报 `why` 为空或与同类条目字面重复；连续两集 `planned` 有 delta 而 `actual` 无 delta | `why` 非空且不重复是 S 规则；实际轨由脚本从 C5b 的 `stateChangeProposals` 应用，不靠人手写；`context-pack` 按 `reads` 只装引用到的条目，全账不进包（预算不涨） |
| 检索出处不可靠、过时或查不到 | K1 卡 `external_not_checked` 比例高；同一程序两张卡结论相反（`contested`） | 卡标日期与地域；查不到就 `unverified` 并带到送审包，不编造；`contested` 为零是 C3b 交接条件，两卡相反时追问单第 9 问重答；主创或顾问任何时候给出处就 `feedback-ingest` |
| 模型做追问单走过场（每问都 `holds`） | 候选 A 的回答里 `notHolds` 为零；同一步骤或断言在不同记录里三态不一致 | D6-0 第一轮的情形相反：49 个候选判了 46 个不成立，毛病是不成立太多而且不分轻重（见下两行）。走过场在别的项目仍可能发生，对策：标准是 K1 卡，与两份审查的对照只作旁证（卡与审查有出入的至少 5 处）；`check-answers --cross` 列出判断不一致的；每答必落到动作、必给原因、涉出处必引到卡里的条，错判事后可见 |
| C3a 内部回路不收敛（写 → 追问 → 换 → 再追问） | 换第二次之后承重缺口数不降，或降是靠 `patch: removed_instead_of_solved` | 换实现预算默认 2；到顶后承重缺口登记为戏剧假定或进决定队列并带默认，流程继续；`closes[]` 只认新上下文的核对记录。D6-0 第一轮两轮未收敛（§4.1） |
| 追问单与「不打补丁」合起来把写作推向删功能 | 候选的 `losesFunctions[]` 非空；回答里出现第四种修法 | 这类候选系统不选；用户给定实现不成立而又没有合格候选时默认保留并标 `license_pending`（§2.5 #16）。D6-0 第二轮：8 处靠拿掉，功能句落空 14 条 |
| 戏剧假定清单变成免检通道 | `license_pending` 的条目数逐轮只增不减；清单长度接近承重缺口数 | 系统只能标 `license_pending`，`accepted_license` 须主创原话；清单放送审包前部；一条假定只豁免它自己那一处，其余各问照问；清单与决定队列的条数进对照报告（只描述） |
| 写作方自报「已关掉」「已读全」不可靠 | 自报关掉的数与核对确认的数差得多；`readScope` 缺项 | `closes[]` 须引用核对记录（D6-0：自报 36，确认 18）；运行在交接里留 `readScope`，核对方按缺项补核。后者仍是自报，把握低 |
| 检索题目漏块、卡到得比追问晚 | `because: no_card` 集中在某一类程序；卡修订后有回答没重答 | 题目由程序类断言归并，不由人预估；`impact --card` 列出要重答的回答（D6-0：28 条规则追问后才有卡） |
| 按方案字段表写的规则对真实数据假阳性多 | 新规则第一次对真实对象跑时报错数与条目数同量级 | schema 必填项以真实夹具反推（§2.8 #5）；`pre-select` 阶段只报不拦（D6-0：108 条假阳性，放宽七处） |
| 容量算出来集数大增 | 季编排粗估下 60 集里过半要拆 | 这是现状不是新架构造成的（结构审查 §5.3）；数字触发的是「必选一个动作」，选重排／删线还是拆集由功能与人物定；送审前自由，送审后是方向变更走 `approval-flow.md` §4，主创决定，不是系统拦截 |
| 两层往返不收敛（C5a 退回 C4，C4 退回 C3c，再回来；C3a 内部的回路见上面单列的一行） | 同一集 `changeProposal(targetLayer: C4|C3c)` 计数 ≥2 | 退回必带默认走法，流程按默认继续；第二次退回时 `season-check` 报 `loop-detected`（只报）；根因通常是季编排容量没处理完，回 C3c 重算一次而不是继续在 C4、C5a 之间倒 |
| 语料计费未确认 | 取用前后 `get_shared_creation_budget` 读数或回执有变化 | 先取 3 部各 10 集；有变化即停、记录、不取全库；D6-4 以小样本结束不阻塞 D6-5 |
| MCP 连接不稳（本会话 mali-story 连接超时；stage-a 实测 3 次失败 0 次重试） | `ECONNRESET`、`CONNECT_TIMEOUT`、404 | `corpus fetch` 带重试与断点，按 `manifest.json` 续取；页面写入沿用回执与对账（`receipt pending`）；D6-0 的语料不需要新取；离线时标 `not_sent`，不写「已保存」 |
| 新对象太多，宿主模型不照做 | 装包时缺对象；交接里没有 delta | S 项拦装包与存稿：没有季编排不给 C4 装包、没有对话表不给 C5b 装包、没有复述与问题单记录不算修订完成、没有 delta 不算分集计划 |
| 补丁计数被改 id 绕过 | 新旧实现描述 8 字档重合高 | `renamed_patch` 提示（不拦）；首读仍看效果 |
| 两轨差异没人看 | 差异报告存在但下一集 `entry` 引用的是 `planned` | C4 的 `entry` 必须接实际轨（有正文时），S 核；差异报告进送审包 |
| 冷读者复述得太好或太差（模型读文字比观众多；随机差异） | 同一稿两位冷读者 `unclear` 差异大 | 提示词两处文案改法与一条装包约束（§2.6 #6）；提示词版本不同的结果不直接比；每稿至少两位读者才比较读者差异；△ 行信息另估 |
| 语料对核心处境为空 | `no_exemplar` 比例高 | 如实标，不拿近似当同处境；允许 `source: project` 的本剧人工句；D6-4 补语料 |
| 新旧并存期 `season-check` 误判 | 旧项目被按新规则核 | 按 `planning/season-plan.json`／对话表记录是否存在自动选集，输出 `ruleSet`；测试锁定《渊心锁》与本项目旧记录结果不变 |
| 验收时把 M 项当通过条件 | 验收表里出现「冷读通过」「问题单全成立」作为门 | 每阶段验收只写 S／R；M 项写「记录在」「附证据」 |

## 7. 不变量与守则（实施期间的硬约束）

| 规矩（主创已定或仓库规则） | 机制 | 层级 |
| --- | --- | --- |
| 架构通用，项目差异进参数或数据 | 程序账、问题单、禁词表、媒介档案、词表都是数据文件；技能只规定「有依赖就要有条目、条目要有状态」；不向主创提项目参数；项目特有的一致性表（集纲方案 §2.4）是数据，不进技能规则 | S（schema 不含项目名）＋M |
| 不新增人力环节；人工反馈来了就吸收 | 人审点仍是两处；决定队列每条带默认，流程按默认走；`feedback-ingest` 回流，`drafted` 即进包；编排方不得以「等人确认」暂停 | S（`default` 必填；无来源不入库）＋M |
| 数字不当裁判 | 媒介档案拒绝配额字段；对话表无 `estimates`；`dialogue-diagnose` 无 `within/outside`；`capacity` 退出码 0；验收无数值门槛；补丁计数与容量触发的都是动作不是判定 | S（schema 与测试：输出里出现区间比较字段即测试失败） |
| 不打补丁：修订回功能层换实现 | `patch-cap`：`patchCount ≥ 2` 的实现再原地修订被拒；finding 必带 `cites`；修订单不含替换文字 | S |
| 承重的不成立必须有去处（D6-0 后加） | 回答记录里每条 `loadBearing: true` 的 `notHolds` 带 `disposition`，引用存在且状态相符：确认它消失的核对记录、戏剧假定条目、或带默认的决定队列条目 | S（去处在）＋M（承不承重的判断，不进验收） |
| 系统不替主创删功能（D6-0 后加） | `losesFunctions[]` 非空的候选不得被标 `selected`；用户给定实现不成立而没有合格候选时默认保留并标 `license_pending`；季编排的删线不作系统默认 | S |
| 写作方的自报不作证据（D6-0 后加） | `closes[]` 每项须引用新上下文的核对记录；带 `patch` 的缺口不计入 | S |
| 戏剧假定如实标（D6-0 后加） | `accepted_license` 须有 `humanWords`；两种状态的条目全部进送审包的戏剧假定清单 | S |
| 编排方不下数值型或「不动集数」类指令 | `constraint-blocklist.json` 两类词表，`contract-check task` 命中即拒，不论 `origin`；修订单扫 SPEAKER 格式行 | S |
| 如实标未核实 | 底账 `unverified` 状态一路带到分集计划 `realityRefs` 与送审包未核清单；K1 卡 `external_not_checked`；`evidenceValidation: not_run` 不改述；`doctor` 的 `mali_story: not_checked` 不动 | S（字段必填、清单生成）＋M |
| 随包脚本不联网、不调模型；检索由代理做并留出处 | 所有新命令只读本地文件（测试里 monkeypatch `socket` 断网跑一遍）；检索代理的产出是 K1 卡，`evidence.sources[]` 必有 | S |
| 私有剧本句子不出项目 | `contrast-pair`、`writer-note`、本项目来源的反例与人工正例只允许 `scope.level: project`；studio 级记录不得含项目句子（S 拒）；`docs/d6/` 证据页只有编号与统计；`validate.py` 拒绝 `/Users/` 路径入包 | S |
| 候选保存不等于采用；标签不等于采用 | 不变（R） | R |
| 每条不变量标 S／R／M，验收只引用 S／R | 本计划每阶段验收表；工位索引的执行层级表 | 文档约定 |
| 不替主创定项目内容方向 | §5 只给选项；D6-0 的范围是验证范围 | 文档约定 |

## 8. 等主创确认的事项

只列真正需要点头的；每条附默认做法与可逆性。项目级问题不提（§5 的走法选择是唯一例外，因为两份方案都把「本项目下一步」留给了主创）。

| # | 事项 | 默认做法（不确认也能实施） | 可逆性 | 什么时候必须定 |
| --- | --- | --- | --- | --- |
| 1 | **工作室级语料缓存的契约变更**（台词方案 §12.4、§15.1）：在架构 v1.2 §8.5 开一条「mali-story 模板数据的本地只读缓存可以工作室级」，知识卡规则不动 | 缓存放项目目录（现状 `runs/pilot-ep006/corpus/`）；schema 两级都允许但 `contract-check` 在确认前只放行 `project`；架构 v1.3 的 §8.5 写「待定」 | 确认后挪目录、改 `scope.level`、放行规则——半天；不确认则每项目各缓存一份，功能等价成本 ×N | **已确认**（主创 2026-10-15：「语料缓存能放工作室级」）；缓存默认放 `<工作室根>/corpus/`，架构 v1.3 §8.5 改为条款 |
| 2 | **语料原句进包的边界**（§15.2）：遮蔽后原句 ≤2 句进包，还是只给处境、说明与骨架 | 遮蔽 ≤2 句进包，配 8 字档核对（D6-0 已这么做，零命中） | 改一个 `context-pack` 参数（`--mask-lines 0`） | D6-3 之前 |
| 3 | **旧步骤退役时点**（§15.3）：D6-3 起新运行不再做台词遍／台词读，还是并行一批再退 | 直接退（RCA 证明它们改不了结构）；`--legacy-dialogue` 保证旧记录可核 | 文档一行＋`season-check` 默认值，可改回「并行一批」 | D6-3 发布前 |
| 4 | **容量提案三选一由谁定**（§15.4）：每次交主创选，还是授权编排方按默认走、集末一并审 | 送审前由季编排层选（它是系统内的动作）；送审后进决定队列、按默认先走、随送审包一并审（不新增审批点） | 改默认为「等主创」只是把 `default` 改成「暂停」，但那违反「流程不等」，所以可逆但不建议 | D6-2 之前 |
| 5 | **本项目的走法**（§5.2 A／B／C） | C：D6-0 的产出作为新版起点，之后按段推进 | 选 A 或 B 时 D6-0 的产出仍是子集，不浪费 | D6-0 对照报告出来之后 |
| 6 | **人工改句可以逐字用**（§2.5 #12；stage-d §十 8 要定） | 本剧编剧的句子可以逐字用并标 `verbatimFrom`；语料原句永不逐字 | 改为「一律不逐字」只需把 `grade: human` 的样本也走遮蔽 | D6-3 之前 |
| 7 | **用户给定设定不成立时默认走法的细化**（对主创第 3 条决定的细化；§2.5 #16，集纲方案 §9.1）：在修订预算内每个通过核对的候选都让某个功能句落空、或没有候选通过时，系统默认怎么走 | 保留用户给定的实现并标 `license_pending`；把「按现实改掉（列出哪些功能句落空）对 作为戏剧假定保留」登记进决定队列；流程按「保留」继续。前提一级的取舍同规则。存在不让任何功能句落空的合格候选时，仍照第 3 条按候选走 | 改成「仍按候选走」只是换默认选项；已按「保留」写出的集，在主创选「改掉」时按决定条目的 `affects[]` 重写，反过来也一样 | **已确认**（主创 2026-10-14：「同意按你的，继续做」），按默认做 |
| 8 | **「戏剧假定」这个状态**（集纲方案 §9.2）：底账条目加 `accepted_license`（主创明知不合常规仍保留，须原话）与 `license_pending`（系统按 #7 的默认先保留）；送审包加「戏剧假定清单」，放在设定核对报告之后、与未核清单并列 | 启用；系统自己只标 `license_pending`，主创说了话才是 `accepted_license` | 不要这个状态时，这些条目退回为不成立项并全部进决定队列——清单变成队列里的条目，流程不变 | **已确认**（主创 2026-10-14：「同意按你的，继续做」），按默认做 |
| 9 | **换实现预算到顶后的动作**（§2.5 #17，集纲方案 §8.3）：C3a 的换实现次数默认 2；到顶之后是登记并继续，还是停下等人 | 登记（戏剧假定，或决定队列并带默认）并继续，不再换 | 预算是一个数，随时可改；改成「停下等人」违反「流程不等」，可逆但不建议 | **已确认**（主创 2026-10-14：「同意按你的，继续做」），按默认做 |

## 9. D6-0 任务清单：第一轮的状态与续做的顺序

下表是 v1 排的第一轮任务，原样保留并标状态（中期报告按这些序号引用）。按先后编号；同一行里「∥」表示可并行。「代理」指类型：带检索的代理、写作代理、核对代理（新上下文）、脚本代理（临时脚本，不进技能）。全部产物在 `projects/qige-xiongdi/runs/pilot-v2/`（下面省略前缀）与 `docs/d6/`。

| 序 | 任务 | 输入 | 产出文件 | 代理 | 先后 | 状态（2026-10-14） |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 建目录与骨架：`pilot-v2/`、`tools/`（复制 `pilot-ep006/tools/` 可用部分）、`docs/d6/README.md` 占位；写 D6-0 的隔离规则（写作代理不读 `reviews/`、不读 e2/f1） | 本计划 §4.1 | `README.md`、`tools/`、`docs/d6/README.md` | 脚本代理 | 第 1 天 | 完成 |
| 2 | 礼物线＋三年空白线功能地图 v0：功能列表（从现实审查 §2.4、§四抄起），现行实现作候选 A，列 `ledgerDeps` | 两份审查、集纲 1–12、框架 v3、小传 v2 | `function-map-v0.json/.md` | 写作代理 | 第 1 天 | 完成 |
| 3 | ∥ 问题单数据：追问单 15＋1 问、对话问题单 15＋2 问，版本化 JSON；冷读提示词两份（计划／正文）按 §2.6 #6 改 | 两份方案 §6.3／§8.3、stage-d §十 | `questions/reality-check-questions-v1.json`、`questions/dialogue-check-questions-v1.json`、`prompts/cold-read-plan.md`、`prompts/cold-read-text.md` | 脚本代理 | 第 1 天 | 完成 |
| 4 | 候选 A 过追问单（礼物、三年空白） | 任务 2、3 | `reality-check/RC-A-*.json` | 核对代理 | 第 1–2 天 | 完成（排在任务 5 之前是错的，见表后） |
| 5 | ∥ 检索代理：礼物线与三年空白线涉及的程序与行业做法（快递拒收与无着件、远洋／外地务工通讯与汇款留痕、民事上门与报警常规等）查出处写 K1 卡；现实审查 §六的来源入卡；查不到的写明 | 任务 2 的 `ledgerDeps`、现实审查 §六 | `knowledge/cards/K1-*.json`、`knowledge/sources/` | 带检索的代理 | 第 1–3 天 | 完成（第一批） |
| 6 | 监护程序线、事故真相线功能地图 v0 与候选 A 追问 | 同任务 2、4 | 并入 `function-map-v0`、`RC-A-*` | 写作代理→核对代理 | 第 2–3 天 | 完成 |
| 7 | ∥ 检索代理第二批：监护顺位与撤销、公告送达、工亡补助与抚恤金领取、事故调查报告期限、保密协议对抗调查 | 任务 6 | 同上 | 带检索的代理 | 第 2–4 天 | 完成（第二、三批；另有前提带出的第四批） |
| 8 | 底账 `ledger@ep000`：四条线的六类账，用户给定标 `user_given`，程序账引任务 5、7 的卡；空白期总账视图；临时脚本核集纲方案 §10.2 的规则 | 任务 2、5、6、7、圣经 | `ledger-ep000.json`、`ledger-check-ep000.json`、`blank-period-view.md` | 写作代理＋脚本代理 | 第 3–4 天 | 完成到 `pre-select` 阶段 |
| 9 | 候选 B（每线一到多个）过追问单，选定；设定核对报告；决定队列（每条带默认） | 任务 4、6、8 | `function-map-v1.json/.md`、`reality-check/RC-B-*.json`、`decisions.json`、`setting-check-report.md` | 写作代理→核对代理 | 第 4–5 天 | **停**：前提层两轮未过追问单；分线候选 B、设定核对报告、决定队列未产出 |
| 10 | 季编排第 1–12 集：受影响的集重排；容量粗估两口径（媒介档案 v0 复用）；超出的集选动作；plant／pay 位 | 任务 9、`pilot-ep006/media-profile-v0.json`、语料交换中位时长 | `season-plan-v0.json/.md`、`capacity-season-v0.md` | 写作代理＋脚本代理 | 第 5 天 | 未开始 |
| 11 | 第 5–7 集分集计划（14 字段，`facts[]`）；`plan-check` 临时脚本；容量复核；超两倍时提案带默认拆法并按默认写 | 任务 8–10、集纲 5–7、第 4 集定稿（w1）出口 | `episode-plan-00{5,6,7}.json/.md`、`plan-check-*.json`、`ledger-ep00{5,6,7}.planned.json` | 写作代理＋脚本代理 | 第 5–6 天 | 未开始 |
| 12 | 分集计划冷读（三集各一位新上下文读者，只装 `events`）；`retell-check` 临时脚本 | 任务 11、任务 3 的提示词 | `retell-plan-00{5,6,7}.json`、`retell-check-plan-*.json` | 核对代理×3＋脚本代理 | 第 6 天 | 未开始 |
| 13 | `ledger knows` 临时实现：第 6 集在场人物的 `knows / notKnows` | 任务 8、11 | `knows-ep006.json`、`tools/ledger_knows.py` | 脚本代理 | 第 6 天 | 未开始 |
| 14 | 第 6 集对话表 v2（`segments[]`、`listenerKnows` 从任务 13 来、`exemplars.source` 三类、独白理由、画面理由；装 138 条里的同处境正反例） | 任务 11、13、`pilot-ep006/corpus/`、反例与对照对、台词目标 v0（加 `conflictsWith`） | `dialogue-plan-ep006-v2.json/.md` | 写作代理（不读 e2/f1） | 第 6–7 天 | 未开始 |
| 15 | 第 6 集正文 g1；`plan-text-map` 标 `verbatimFrom`；两档 `dup-check`、禁词扫描、`capacity text` 两口径 | 任务 14 | `ep-006.g1.md`、`plan-text-map-ep006-v2.md`、`checks-ep006-g1.json` | 写作代理＋脚本代理 | 第 7 天 | 未开始 |
| 16 | 正文冷读（只装 g1，两位读者）；处境对照（17 问，双跑）；一致性核对；`dialogue-diagnose` 对 g1、f1、e2、w1 并排；两轨 diff（计划轨 vs g1 实际轨） | 任务 15、任务 3 | `retell-ep006-g1-{a,b}.json`、`check-ep006-g1-{a,b}.json`、`consistency-ep006-g1.md`、`signals-ep006.md`、`ledger-diff-ep006.json` | 核对代理×4＋脚本代理 | 第 7–8 天 | 未开始 |
| 17 | 对照报告与 schema 修正清单（§4.1 0.13） | 全部 | `docs/d6/d6-0-report.md` | 核对代理（读全部产物） | 第 8 天 | 未开始 |

第一轮实际走的串行链是 2→4→6→8→9，任务 3、5、7 并行；任务 9 停，10–17 未做。v1 估的「约 8 个工作日走完 17 项」没有成立：前 9 项在一天内由约 19 路代理并行做完，卡在任务 9 的回路上（§4.1）。

**顺序上要改的两处**（已写进 §2.5 #18，续做与以后的项目都照此）：

1. 检索在追问之前。v1 把任务 4（追问）排在任务 5（检索）之前，任务 6 排在任务 7 之前；应当是功能地图写完、候选 A 登记之后，先由程序类断言归并出检索题目并写卡，再追问。检索题目不由编排方按线预估。
2. 任务 9 不是「每线写候选 B」一步，而是：前提问题 → 再检索 → 默认前提追问 → 分线候选 B → 追问 → 选定或登记。检索在这里还要再来一次。

**续做的顺序**（步骤内容见 §4.1「D6-0 续」）：R1 → R2 → R3 ∥ R4 → R5 → R6 → R7（原任务 10）→ R8（11）→ R9 ∥ R10（12、13）→ R11（14）→ R12（15）→ R13（16）→ R14（17）。R2–R5 至多走两遍。编剧投入 0；主创投入 0——§8 的事项与「哪些场面作为戏剧假定保留」都有默认，不阻塞。

---

本计划是一份文档。v1（2026-10-14）新增了本文件，并在两份方案里记入主创当天的决定；v1.1（同日）按 D6-0 中期报告修订了本文件与两份方案，并更新了 `docs/d6/README.md` 的状态行。D6-0 第一轮已经执行：它的产物在项目目录 `runs/pilot-v2/`（不随仓库分发），证据页在 `docs/d6/`；它没有修改技能文件、脚本、schema、测试、mali-story 页面，也没有修改项目的集纲、剧本或原有知识卡。D6-0 续与 D6-1 至 D6-5 都没有开始。§8 的 #7–#9 三条已由主创 2026-10-14 确认（「同意按你的，继续做」），其余六条未确认；主创另给过 §5.1 记的两条输入。没有向编剧确认任何事。所有 S 级都是设计层级，D6-1 实现并有正反测试后才成立；D6-0 的临时脚本是验证用的，不算实现。
