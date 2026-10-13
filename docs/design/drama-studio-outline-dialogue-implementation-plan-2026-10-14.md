# 集纲层与台词层统一实施计划（D6）

日期：2026-10-14 · 版本 v1 · 状态：实施计划，未启动；只写文档，不改技能文件、脚本、契约、剧本、集纲或项目文件 · 合并的两份方案：[集纲层架构 v1.1](drama-studio-outline-layer-architecture-2026-10-13.md)（下称「集纲方案」，主创 2026-10-14 已定六条架构取舍）与[台词系统架构 v3.1](drama-studio-dialogue-structure-architecture-2026-10-13.md)（下称「台词方案」，主创已批准 v3） · 依据：[系统架构 v1.2](drama-studio-system-architecture-2026-09-29.md)、[实施路线 v1.1](drama-studio-implementation-roadmap-2026-09-29.md)、第 6 集台词层验证（`projects/qige-xiongdi/runs/pilot-ep006/stage-a/b/d-report.md`、`capacity-ep006.md`）、三份审查（`projects/qige-xiongdi/reviews/`）

主创已定且实施期间当硬约束的规矩（§7 逐条给机制）：架构通用、项目差异进参数或数据；不新增人力环节，人工反馈来了就吸收；数字不当裁判；不打补丁，修订回功能层；编排方不下数值型或「不动集数」类指令；如实标未核实；随包脚本不联网、检索由代理做并留出处；私有剧本句子不出项目。

每个结论给理由；所有「S」都是设计层级，实现并有正反测试后才成立。举例处为说明而编；项目证据只引结论与文件位置，不抄私有剧本。

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
| C3a 全剧功能地图 | 新 | `function-map` | 每条线的功能；候选实现；对每个候选发追问单；选定；结局、因果链、承诺与回收位 | 功能分到哪集；底账条目核对 | `selected` 候选的 `reality-check.outcome ≠ fail`；被否定候选有 `rejectedBecause` | 功能只写「感受／谁知道／局面变化」 | 功能 id 与 `ledgerDeps` |
| C3b 底账与现实核对 | 新 | `ledger@ep000`、`ledger-entry[]`（六类账）、`reality-check[]`、K1 知识卡（出处） | 条目、来源、状态；检索代理查出处；追问单回答的记录；空白期总账视图 | 剧情；给改法 | `ledger check` 九条规则；`contested` 为零；`unverified` 清单在 | 追问单答案（三态＋原因） | 当前修订的底账；未核清单 |
| C3c 季编排 | 新 | `season-plan` | 功能分到集；事件粗列与★；**容量粗估**；装不下时重排／拆集／删线（必选一个）；埋设与回收位；决定队列登记 | 每集内部怎么发生 | 每集 `capacity` 必填；超出时 `action` 必填；每个 plant 有 payAt | 选哪个动作由功能与人物定 | 本集分配、容量状态 |
| C4 分集计划 | 重构 | `episode-plan`（14 字段，9 必填）＋ 可读稿（存 `episode_outline` 页面）；`ledgerDelta(planned)` | 按季编排把一集写成计划：入口、场序列、在场、动作与动机、**信息清单（`facts[]`）**、状态变化、现实依据引用、承接与埋设、出口、容量复核、待定项、可选派生摘要 | 定全剧级事实；改功能；查证 | `plan-check`：引用存在、`closingEvent` 位置、摘要实体 ⊆ events、delta 可应用、容量复核；`retell-check` 对照 | 追问单对关键动作；冷读复述 | `infoLedger`、`presence`、知识账 → 对话表 |
| C5a 对话设计 | 新 | `dialogue-plan` | 场→话题→来回；每话题的处境与理由；每条信息（到 `facts` 粒度）由哪句承载；独白许可；留白；同处境正反例 | 措辞；事件与事实；任何句数字数目标 | 信息每条有 `carriedBy` 或画面理由；`situation` 齐、`reason` 引处境字段；每个 `segment` 有 `closer`；`listenerKnows` 不与知识账矛盾；无 `estimates` | 处境写得像不像话 | 对话表 |
| C5b 正文生成 | 重构 | 剧本正文 ＋ `plan-text-map` ＋ `stateChangeProposals(ledgerDelta)` | 照表逐话题写台词与动作行 | 增删话题、改信息分配、改事件 | 与对话表对齐；13 字档全库、8 字档对装包样本零命中；禁词零命中；`verbatimFrom` 标出人工句 | — | 正文；实际轨 delta |
| 底账实际轨更新 | 新（脚本） | `ledger@after-ep-N.actual` ＋ 两轨差异报告 | 应用 C5b 的 delta；与计划轨比对 | 判断哪边对 | `ledger apply --track actual`、`ledger diff` | — | 下一集 C4 的 `entry` |
| C6 审读 | 扩 | `review-record`、`retell-record`、`dialogue-check`、`plan-text-consistency` | 首读、次读（保留）＋ 追问单复核、底账一致性、分集计划冷读、正文冷读复述、处境对照、设计依据一致性 | 产生新约束；打分 | finding 必带引用（功能 id／底账 id／目标条款／事实证据），否则 `preference`；`check-answers` 核每答有落点、三态、原因；`retell-check` 覆盖 | 复述、回答本身 | 修订单 |
| 修订 | 重构 | 新 `function-map`／底账修订／分集计划／对话表／正文 | 回功能层换实现；先改表再改文；修订后必做冷读与问题单复核 | 原地加拍子；替换文字；数值指令 | `patch-cap`；修订单扫台词格式行与数值指令词表；`retell-after-revise` | — | — |
| 决定队列（合并容量提案） | 新 | `decision-queue` | 登记「待主创定」「容量三选一」「上游变更」，每条带默认走法与 `affects[]` | 等人 | `default`、`defaultReason` 必填；分集计划 `pending[]` 引用存在 | — | 送审包附录 |
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
C3a 功能地图 ──候选实现──► 追问单（15＋1 问）──► 选定 / 否定        │
   ↓ ledgerDeps                                                │
C3b 底账（六类账，ledger@ep000）◄── 检索代理查出处 → K1 卡       │
   ↓                       ◄── 用户给定材料（user_given）        │
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
   （patchCount ≥ 2 → 强制回 C3a）
（随时）编剧／主创／顾问一句话 → feedback-ingest → 底账修订 / K1 / 决定 / 反例 / 约定
```

### 1.3 不做什么

- 不新增人审点：选题确认、送审包审批两处不动（[两次审批](../../skills/drama-studio/references/approval-flow.md)）。送审包只多三份附录：未核清单、设定核对报告、决定队列。
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
| 1 | `function-map` | O#1 | 独有 | S | C3a → C3b、C3c、C4、修订 | 每候选 `inquiryRef` 必填；`selected` 的 `reality-check.outcome ≠ fail` |
| 2 | `ledger-entry`、`ledger-delta` | O#2 | **共用**：知识账是对话表 `listenerKnows` 的来源；实际轨由 C5b 的 `stateChangeProposals` 写 | S | C3b、C4（planned）、C5b（actual）→ C4、C5a、C6 | `run-handoff.stateChangeProposals` 增可选 `ledgerDelta`（O#10），旧 claim/evidence 仍有效 |
| 3 | `question-set` ＋ 两个实例 `reality-check-questions.json`（15＋1 问）、`dialogue-check-questions.json`（15＋2 问） | O#3、D#6 | **共用 schema**，两份数据 | S | 技能随包；项目可增问不可删，增问带来源 | 两份方案各有一张「版本化、可增不可删、增问带来源」的问题单，结构相同，合并为一个 schema。追问单增第 16 问「说话人／行动者凭什么知道这件事」（stage-d §十 2）；对话问题单增第 16 问同题、第 17 问「这条信息观众之前从哪句知道了，重说在处境里有理由吗」（stage-d §十 3），「为问而问」并入第 16 问（stage-d §十 4） |
| 4 | `answers`（`reality-check` 与 `dialogue-check` 的回答记录） | O#3、D#6 | **共用 schema**：每答有落点／引用、三态、原因、可选出处 | S | C3a、C4、C6 → 修订 | 三态词统一为 `holds / notHolds / not_evaluable`（台词方案的 `not_evaluable` 与集纲方案的 `unverified` 语义不同：前者「答不了」，后者「查过没查到」——`unverified` 保留给底账条目状态，回答用 `not_evaluable` 并在 `reason` 写明是查不到还是答不了） |
| 5 | `season-plan` | O#4 | 独有 | S | C3c → C4、`capacity season` | 每集 `capacity` 必填，超出时 `action` 必填 |
| 6 | `episode-plan` | O#5 | **共用**：第 7 栏 `infoLedger` 是对话表的输入 | S | C4 → C5a、C6、`ledger apply` | `infoLedger[]` 每条带 `facts[]`（一条一事实），`knownByInStory[]` 引用知识账 |
| 7 | `decision-queue` | O#6 ＋ D §3.5「提案队列」 | **合并为一个对象** | S | 任何层 → 送审包附录、`pending[]` | 两份方案各有一个「等人但流程不等、必须带默认走法」的队列：集纲方案的决定队列（待主创定）、台词方案的容量提案队列（三选一）。合为 `decision-queue`，条目 `kind ∈ setting_conflict / capacity / upstream_change / other`；`changeProposal`（架构 §9.1）仍是运行里**提出**的形式，`decision add --from-handoff` 把它登记进队列并要求 `default`。理由：主创只看一处；两者的字段（问题、选项、默认、默认理由、影响范围、状态）完全重合 |
| 8 | `media-profile` | D#1 | **共用**：C3c 粗估、C4 复核、C5b 精估都读它 | S | `corpus rate` → `capacity` | 只含物理量；拒绝任何句数／换人／话题数字段。按 stage-a §5 增 `grossCharsPerMinute`（每集每分钟台词汉字，含停顿）作对照口径；公式仍用 `speechRate ÷ (1 − pauseShare)`，两口径同时报直到 `project_measured` |
| 9 | `dialogue-exchange`、`corpus-manifest` | D#2 | 独有 | S | `corpus` → C5a、C6 | 增 `speakerAttributionSuspect: bool`（stage-a §8.1）；`exchangeRef` 在 `snapshotId` 为 null 时允许 `localSha256` 并标 `refKind: local_fingerprint`（stage-a §8.5）；`scope.level: studio` 仅当 `origin.kind == mali_story_template`（等主创确认 §8.1，确认前只用 `project`） |
| 10 | `contrast-pair` | D#3 | 独有，只允许 `project` | S | `corpus`／`feedback-ingest` → C5a、C6 | `whyNotHere` 必填 |
| 11 | `dialogue-plan` | D#4 | **共用**：`infoLedger` 只引用 `episode-plan` 的 id 与 `facts` id 并加 `carriedBy`，不重新声明内容；`listenerKnows` 初值由 `ledger knows` 生成 | S | C5a → C5b、C6 | `topics[].segments[]` 取代 `between` 链，每段 `between: [a,b]` 与 `closer`（stage-d §十 5）；`exchanges[]` 增可选 `oneItemPerLine`、`givesReason`（诊断用，stage-d §十 6）；`exemplars.positives[].source ∈ corpus / human / project`（stage-d §十 12）；无 `estimates` |
| 12 | `dialogue-target` | D#5 | 独有 | S | 项目级 → C5a、C5b、C6 | 无 `acceptedBand`／`hardRules`／`softRules`；`conventions[]` 增 `conflictsWith[]`（stage-d §十 10） |
| 13 | `writer-note` | D#7 | **共用**：`feedback-ingest` 的统一入口；按 `level` 路由到台词侧（反例、约定）或集纲侧（底账修订提案、K1 草稿、决定 `decided`） | S | `feedback-ingest` → 两侧 | `level` 词表加 `procedure / fact / decision`（O#16）；增 `conflictsWith[]` |
| 14 | `retell-record` | D#8 ＋ O#15 | **共用**：`target.kind ∈ episode_text / episode_plan_events` | S | 冷读运行 → `retell-check` | `readingScope` 只允许一项且与 `target` 一致；提示词按 stage-d §十 9 改：标明「连续剧第 N 集、前集已交代不列 unclear、△ 标画面约两秒并另估看成片能否拿到」 |
| 15 | `plan-text-consistency` | D#9 | 独有 | S | C6 → 修订 | — |
| 16 | `knowledge-card` | O#7 | 不改 schema | S（现有） | 检索代理 → C3b | K1 作现实出处：`usage ∈ comparison_only / creative_reference`，`evidence.sources[]` 必有，外部 URL 标 `external_not_checked` |
| 17 | `task` | O#8、D#10 | **合并**：一份 `constraint-blocklist.json` 数据文件，两类词表（「不动集数／标题／★／只改一次且不拆集」与「字数／行数／句数／换人数」数值型台词约束） | S | 编排方 → `contract-check task` | `constraints[] {text, origin, cite}`；命中任一词表即拒，不论 `origin`；`dialogueTarget` 引用必填（C5a/C5b/C6/修订任务）；`revisionBudget` 的单位按任务所属层解释（C3a 算换实现次数，C5a 算对话表修订次数），写进 README 工位索引 |
| 18 | `review-record` | O#9、D#11 | **合并**：`finding.cites ∈ {functionId, ledgerId, targetClause, factEvidence}`，一个都没有 → `kind: preference`；加 `adjudications[]` | S | C6 → 修订 | 旧记录（无 `cites`）仍通过，但 `season-check` 新规则只认带 `cites` 的 finding 进修订单 |
| 19 | `context-snapshot` / `selection` 角色 | O#18、D#12 | **合并**：`function_mapper`、`ledger_keeper`、`season_planner`、`dialogue_designer`、`situation_checker`、**`cold_reader`**（两份方案的 `plan_cold_reader` 与 `cold_reader` 合为一个角色，`target.kind` 区分；包只允许一个 `project_facts` 项且为本集 `events` 或本集正文） | S | `context-pack` | 多装被拒（退出码 2） |
| 20 | `run-handoff` | O#10 | 共用 | S | 各运行 | `stateChangeProposals[].ledgerDelta` 可选；`unknowns` 记「本次无检索」 |

### 2.2 命令

| # | 命令 | 来源 | 合并说明 | 层级 |
| --- | --- | --- | --- | --- |
| 1 | `ledger {init|apply|replay|check|diff|knows}` | O#11 | 加 `knows --who <人> --at <ep>`：从知识账输出某人在某集的 `knows / notKnows`，供 C5a 填 `listenerKnows` 初值（S 生成，M 只能收窄不能相反） | S |
| 2 | `plan-check <episode-plan> [--characters <人物包>]` | O#12 | 增 `--characters`：小传里的前史事件是否有时间线账条目（报不拦） | S |
| 3 | `capacity {season|episode|text}` | O#13 `season-capacity` ＋ D#18 `outline-capacity` ＋ D#19 `episode-check` 加估时 | **三个入口一个命令、一套公式**：`season` 对 `season-plan` 粗估（信息条数 × 同类处境语料交换中位时长 ＋ 画面拍）；`episode` 对 `episode-plan` 复核（同公式）；`text` 对正文精估（口播量 ÷ speechRate ÷ (1 − pauseShare)，两口径同时报）。超出时写 `decision-queue` 条目占位并**退出码 0**（提案不是失败）；`episode-check` 只加口播量统计，不算估时（避免两处算） | S |
| 4 | `check-answers <回答文件>` | O#14 `inquiry-format` ＋ D#16 `check-format` | 一个命令按 `questionsVersion` 引用的问题单核格式：每答有落点或引用、三态、原因；涉出处的有 `realityRef` | S |
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

### 2.3 文档改动

| 文件 | 改动 | 阶段 |
| --- | --- | --- |
| [`SKILL.md`](../../skills/drama-studio/SKILL.md) | 路由表「原创选题、人物与集纲」改指 `planning.md`＋新 `outline-layer.md`；「台词 AI 味重」一行改指 `dialogue-structure.md`；「一次完整创作」第 3–7 步改写；随包工具表加新命令（[`tests/test_skill_routing.py`](../../tests/test_skill_routing.py) 同步） | D6-2、D6-3 |
| [`references/planning.md`](../../skills/drama-studio/references/planning.md) | 重写「蓝图、设定圣经与集纲」一节：六字段说明改为分集计划字段；「时间线、道具位置、谁知道什么放设定圣经」改为底账；两轨 | D6-2 |
| 新 `references/outline-layer.md` | 功能地图、六类账、追问单（含第 16 问）、检索代理（可联网、留出处、脚本不联网）、季编排与容量、分集计划字段、修订规则、决定队列、用户给定设定的处理 | D6-2 |
| [`references/writing.md`](../../skills/drama-studio/references/writing.md) | 工位流程第 3–7 步改写（C4 分集计划可写 → C5a → C5b → C6 五读 → 修订）；「避免用解释性台词替代人物行动」改为「信息由对白承载；谁知道什么由 `listenerKnows` 定；重复须有处境理由」 | D6-3 |
| [`references/dialogue.md`](../../skills/drama-studio/references/dialogue.md) → `dialogue-structure.md` | 重写；§8 前文校核、§9 改稿任务怎么写保留 | D6-3 |
| 新 `references/corpus.md` | 取用、切分、过滤、处境标注、结构说明、缓存、快照、计费观察 | D6-4 |
| [`workstations/c3-structure.md`](../../skills/drama-studio/references/workstations/c3-structure.md) | 拆为 `c3a-function-map.md`、`c3b-ledger.md`、`c3c-season-plan.md`；「删掉一段，后续是否仍原样发生」移到 c3c | D6-2 |
| [`workstations/c4-episode-outline.md`](../../skills/drama-studio/references/workstations/c4-episode-outline.md) | 产出项改为 14 字段；「整季集纲怎么写」六步保留，装的东西换成季编排＋底账；审读项换成追问单复核、底账一致性、冷读；「每集有没有主角的关键选择」硬项废除 | D6-2 |
| [`workstations/c5-screenplay.md`](../../skills/drama-studio/references/workstations/c5-screenplay.md) | 拆为 `c5a-dialogue-plan.md`、`c5b-text.md` | D6-3 |
| [`workstations/c6-review.md`](../../skills/drama-studio/references/workstations/c6-review.md) | 加五读；finding 必带 `cites` | D6-2（集纲侧三读）、D6-3（正文侧两读） |
| [`workstations/season-run.md`](../../skills/drama-studio/references/workstations/season-run.md) | §1「上游 C1–C4」与「入口状态」改为底账；§3 每批步骤改写 | D6-2、D6-3 |
| [`workstations/README.md`](../../skills/drama-studio/references/workstations/README.md) | 工位索引、执行层级表加新不变量、`revisionBudget` 按层解释 | D6-2、D6-3 |
| [`references/approval-flow.md`](../../skills/drama-studio/references/approval-flow.md) | 送审包附录三份：未核清单、设定核对报告、决定队列；拆集在送审后是方向变更 | D6-2 |
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
| 问题单 | 追问单 15 问，版本化可增不可删 | 对话检查问题单 15 问，同规则 | 一个 `question-set` schema，两份数据，一个 `check-answers` |
| `feedback-ingest` | 程序／事实类批注 → 底账、K1、决定（§12 #16） | 批注 → writer-note → 反例、约定、新问（§9） | 一个命令按 `level` 路由 |
| 任务约束词表 | 「不动集数／标题／★／只改一次」（§8.3） | 数值型台词约束（§11） | 一份 `constraint-blocklist.json`，两类 |
| 审读 finding 的引用义务 | `functionId` 或 `ledgerId`（§8.3） | `targetClause` 或 `factEvidence`（§10.3） | `cites` 四选一，否则 `preference` |
| K1 知识卡 | 检索代理的出处（§6.2） | 不涉及 | 不改 schema |
| `dup-check` | 新旧实现 8 字档重合提示 `renamed_patch`（§10.4） | 13 字档全库、8 字档装包样本（§7.3） | 同一命令，两种用法 |
| 不新增人审点 | 送审包附未核清单与设定核对报告 | 送审包审批不变 | 送审包多三份附录，不多一次审批 |

### 2.5 冲突点与合并定法

| # | 两份方案对同一件事的不同说法 | 合并定法 | 理由 |
| --- | --- | --- | --- |
| 1 | **容量在哪算、超了怎么办。** 集纲方案：第一次在 C3c，超了必选一个动作（重排／拆集／删线），送审包里每集 `fits`；送审后再超走提案队列。台词方案：粗估在 C4，超了出提案进队列、流程不停、稿子标 `proposal_pending`。stage-d §九 4、§十 7：不拦截让 f1 成了一份拍不了的 9–10 分钟正文，验证对象失真 | 送审前：C3c 必选动作（S：`season-plan` 超出无 `action` 被拒）。送审后：提案进决定队列、流程不停，**但提案必须带默认走法**（与决定队列同规则），C5a 按默认走法写对话表（默认拆法是「按粗估比例拆成 N 段，本集只写第一段，其余登记为下一集的 `entry`」）；C5a 装包时 `episode-plan.capacity.status` 若为 `proposal:<id>` 而该提案无 `default` → `context-pack` 退出码 2。这不是数值关口：数字触发的是「提案要有默认」，不是「稿子不合格」 | 两份方案都说「流程不停」；差别只在「停下来等人选」还是「按默认先走」。决定队列原则（提出的人给默认、流程按默认继续）已被主创接受（第 3 条决定），用到容量上是同一条规矩。stage-d 的实测说明没有默认走法的「不拦截」会产出不会存在的稿 |
| 2 | **信息清单归属。** 台词方案 C4 产「六字段集纲＋信息清单」，对话表自带 `infoLedger` 与 `carriedBy`；集纲方案信息清单是分集计划第 7 栏 | 声明一次在 `episode-plan.infoLedger[].facts[]`；`dialogue-plan.infoLedger[]` 只引用 id 并加 `carriedBy`；S 核引用存在、每个 `fact` 有承载或画面理由 | 两处声明必然漂移（stage-d §四「清单与 exchanges 交叉引用不一致」就是同一张表里都漂了）；集纲方案 §0 第 8 条已把 `facts[]` 定为接口 |
| 3 | **C4 的产物格式。** 台词方案保留六字段；集纲方案换成 14 字段分集计划，六字段为可选派生 | 集纲方案为准（主创第 5 条决定）；台词方案 §2.2 C4 一行自己写了「由上游细化」 | 结构审查 0/60 自足；台词方案没有审过集纲格式 |
| 4 | **`listenerKnows` 的来源。** 台词方案：M 一句话；集纲方案：知识账初值 | S 生成、M 收窄，矛盾报（§2.4） | stage-d §六 4：家宝说出他不该知道的「抽屉的钥匙」，问题单全过——没有账，M 写的 `listenerKnows` 核不出说话人越界 |
| 5 | **冷读者读什么。** 集纲方案只读 `events`；台词方案只读正文 | 一个角色两种目标（§2.1 #19） | 任务相同（复述谁做了什么、信息从哪知道），只差材料；两套角色会有两套提示词要改两遍（stage-d §十 9 的两条修正要同时落） |
| 6 | **修订预算的单位。** 集纲方案：换实现的次数；台词方案：对话表修订次数，默认 1 | `task.revisionBudget` 按任务所属层解释，写进工位索引；补丁计数是另一个计数器 | 任务本来就是按层发的；不必改 schema |
| 7 | **版本号。** 集纲方案 0.5.0、台词方案 0.4.0，隐含「台词先上」 | 按阶段递增（§0） | 合并后上游先于下游 |
| 8 | **「第 7–10 集重写」。** 台词方案阶段 1 要重写第 7–10 集；集纲方案指出 60 集分集计划都要重产 | 技能阶段（D6-1 至 D6-5）不含任何集的重写；重写多少是 §5 的项目级选项 | 集纲换了，先重写台词是在旧地基上刷墙；也违反「不替主创定内容方向」 |
| 9 | **语料缓存位置。** 台词方案建议工作室级（需契约变更）；集纲方案阶段 0 直接用「台词方案阶段 A 的媒介档案 v0」，而那份在项目目录 | D6-0 与 D6-1 用项目级缓存（现状 `runs/pilot-ep006/corpus/`）；schema 两级都允许；工作室级等主创确认后在 D6-4 开（§8.1） | 不确认也能跑；确认后只是挪目录 |
| 10 | **三态词。** 集纲方案 `holds / notHolds / unverified`；台词方案 `holds / notHolds / not_evaluable` | 回答统一 `not_evaluable`＋原因；`unverified` 只作底账条目状态 | 「查过没查到」是条目的状态，「这问我答不了」是回答的状态，两者在送审包里的去处不同（未核清单 vs 问题单记录） |
| 11 | **每集样本上限。** 台词方案 §7.2：每集 8 正例、4 对照对；stage-b 按主创要求每话题 2 条装了 22 条正例、12 对 | 删固定条数，改为「每话题 2 正例＋1 对照对，总量受包预算（知识分区不超过四分之一）约束」；超预算按 Tier、`recurrent`、`labelConfidence` 截断 | 固定条数是数字当上限；预算已有规则；与方案不一致，D6-5 回写 |
| 12 | **人工正例可不可以逐字用。** 台词方案 §7.3 遮蔽原句防抄；台词目标 v0 约定 3「编剧要的是把它原样说回来」；stage-d §十 8 要定下来 | 本剧编剧写的句子（`grade: human`、来源 `writer-note`）可以逐字用，`plan-text-map` 标 `verbatimFrom: <noteId>`，校验时这些行不计入「问题不再出现」的证据；语料原句仍只给遮蔽 ≤2 句、永不逐字 | 编剧的句子是本项目的产物，抄它不是抄语料；但要能分清「学会了」和「照抄了」 |
| 13 | **语速口径。** 台词方案 §3.2 定义 `speechRate` 为说话期间速度，§3.4 的实测数却是每集每分钟台词汉字（stage-a §5 两者差近一倍） | 媒介档案两个字段都存，公式用 `speechRate ÷ (1 − pauseShare)`，`capacity` 两口径同时报（`capacity-ep006.md` 两口径差 <10%） | 不选口径就没有可复算的估时；两口径并报让读者看到偏差量级 |
| 14 | **底账与 `after-ep-NNN.md`。** 台词方案 C5 包仍装「入口状态记录 `runs/state/after-ep-NNN.md`」；集纲方案把它重构为底账实际轨 | D6-2 起入口状态是 `ledger@after-ep-N.actual` 的可读导出（`ledger replay --at N --track actual --md`），文件名沿用 `runs/state/after-ep-NNN.md` 以兼容 `season-check author-state` 规则 | 内容相同（故事日、谁知道什么、物件、未写明），只是由脚本从账导出而不是作者手写；旧项目的手写文件仍被旧规则认 |

### 2.6 本计划对两份方案的修正点（回头修方案的清单）

以下在 D6-5 回写进两份方案正文；此前以本计划为准。

| # | 修正 | 落到的任务 | 来源 |
| --- | --- | --- | --- |
| 1 | 容量复核超目标两倍时 C5a 按提案默认拆法走（§2.5 #1） | D6-0 任务 0.11；D6-1 `context-pack` 规则；D6-3 `writing.md` | stage-d §九 4、§十 7 |
| 2 | `infoLedger` 带 `facts[]`，对话表只引用（§2.5 #2） | D6-0 任务 0.8、0.10；D6-1 两个 schema | stage-d §十 1 |
| 3 | 追问单与对话问题单各增「说话人凭什么知道」；对话问题单增「第几次出口」；「为问而问」并入 | D6-0 任务 0.3、0.12；D6-1 问题单数据 | stage-d §十 2–4 |
| 4 | 对话表 `segments[]` 取代 `between` 链 | D6-0 任务 0.10；D6-1 schema | stage-d §十 5 |
| 5 | `exchanges[]` 可数标记；`dialogue-diagnose` 加 `INFO_REPEATED` | D6-1 | stage-d §十 3、6 |
| 6 | 冷读提示词三处改法 | D6-0 任务 0.9、0.12 | stage-d §十 9 |
| 7 | `writer-note.conflictsWith`、台词目标写明取舍 | D6-1、D6-4 | stage-d §十 10 |
| 8 | `exemplars.source: project`；`verbatimFrom` | D6-0 任务 0.10；D6-1 | stage-d §十 8、12、§九 1 |
| 9 | 每集样本上限改按预算 | D6-1 `context-pack` | stage-b §4 |
| 10 | 语料标注词表收敛；`speakerAttributionSuspect`；`exchangeRef` 本地指纹 | D6-4 `corpus label/segment/fetch` | stage-a §8.1、8.4、8.5 |
| 11 | 媒介档案两口径 | D6-0 任务 0.6；D6-1 schema | stage-a §5 |
| 12 | 决定队列与提案队列合并；`season-capacity`／`outline-capacity`／估时合为 `capacity`；`inquiry-format`／`check-format` 合为 `check-answers`；两个 cold reader 合为一个 | D6-1 | 本计划 §2 |
| 13 | 技能版本号顺序 | D6-5 | 本计划 §0 |
| 14 | 语料检索对核心处境返回空时的做法：`no_exemplar` 如实标，允许 `source: project` 的本剧人工句作同处境正例并写 walkthrough | D6-0 任务 0.10；D6-4 补语料 | stage-d §九 7、§十 12 |

### 2.7 另两份相关设计的处置

- [台词样本知识库设计（2026-10-13）](drama-studio-dialogue-sample-library-design-2026-10-13.md)：按台词方案 §20 已被**重心倒置**（分级被 Tier＋`grade: human` 取代、样本对象被 `dialogue-exchange` 取代、数数关口与覆盖卡废除、留出法保留为可选描述）。本计划不再单独排它的任务；D6-5 在其文首加状态行「被台词方案 v3 取代；仍有效的只有 §9 留出法（可选描述性评测）与 §6.2 装包历史」。
- [台词库产品设计（2026-10-12）](drama-studio-voice-library-product-design-2026-10-12.md)：产品形态（五种来源、权利等级、目录页）不受影响；它的「语料片段」对象就是 `dialogue-exchange`，「对标转写」升为主来源。本计划只做其中「样本」这一块（D6-4）；其余产品层（目录页、多来源入库）不在 D6，D6-5 文首加状态行说明哪些已由 D6 实现、哪些仍是设计。
- [工艺闭环设计（2026-10-10）](drama-studio-craft-loop-design-2026-10-10.md)：§4.4、§4.5 三条 S 关口被取代（台词遍、台词读在 D6-3 退役）；§1 问题判断与 §3 分层被吸收。D6-5 加状态行。

## 3. 依赖关系与顺序

```text
                 ┌──────────────────────────────────────────────────┐
                 │ D6-0 合并验证（不改技能；本项目；临时脚本）          │
                 │  功能地图与底账 → 季编排与容量 → 分集计划 → 冷读     │
                 │  → 对话表 → 正文 → 冷读/问题单 → 对照报告            │
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
2. **D6-0 先于 D6-1**：schema 的字段表在两份方案里已有，但 `facts[]` 粒度、`segments[]`、三态词、两口径这类问题全是实做一遍才暴露的（stage-a/b/d 加起来 20 多条）。再走一遍合并后的闭环，再冻结 schema，比先写 schema 再改便宜。
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

**步骤**（谁做见 §9 任务清单；下面只列闭环）

| 步 | 做什么 | 产物（`projects/qige-xiongdi/runs/pilot-v2/`） | 对应方案步骤 |
| --- | --- | --- | --- |
| 0.1 | 选线：默认四条——三年空白、礼物、监护程序、事故真相（集纲方案 §13 0.1；哨子芯片线不在 D6-0，因为它影响的集在 13 集之后且是物理前提，与前 12 集的季编排无关）。先做礼物＋三年空白（它们压着第 1、3、5、6、8–10 集，第 6 集是台词层的落点），再做监护、事故。为每条线写功能地图，现行实现作候选 A | `function-map-v0.json/.md` | O 0.1 |
| 0.2 | 对每个候选 A 跑追问单（15＋1 问），记录；预期多数 `fail`（两份审查已给答案，这一步是写成记录格式） | `reality-check/RC-*.json` | O 0.2 |
| 0.3 | 检索代理（可联网，主创第 2 条决定）对四条线涉及的程序与行业做法逐条查出处，写 K1 卡；现实审查 §六已有的来源直接入卡；查不到的写「查了什么、没查到什么」 | `knowledge/cards/K1-*.json`、`knowledge/sources/` | O 0.3 |
| 0.4 | 为四条线写底账（六类账），用户给定的标 `user_given`；跑临时脚本核 §10.2 九条规则 | `ledger-ep000.json`、`ledger-check-ep000.json` | O 0.4 |
| 0.5 | 为每个被否定的功能写候选 B（可多于一个），跑追问单，选定；写设定核对报告与决定队列（每条带默认） | `function-map-v1.json`、`decisions.json`、`setting-check-report.md` | O 0.5 |
| 0.6 | 季编排：只对受四条线影响且在第 1–12 集范围内的集重排；用媒介档案 v0 算容量（两口径）；超出的集记录处理动作（三选一必选） | `season-plan-v0.json/.md`、`capacity-season-v0.md` | O 0.6 ＋ D 0.6 的粗估提前 |
| 0.7 | 按 14 字段写第 5–7 集分集计划（礼物线落点；第 6 集有对照组）；`infoLedger` 带 `facts[]`；跑九条规则与容量复核；若第 6 集复核仍超两倍，提案带默认拆法并按默认写 | `episode-plan-00{5,6,7}.json/.md`、`plan-check-*.json` | O 0.7 |
| 0.8 | 分集计划冷读：新上下文只装某集 `events`，提示词按 §2.6 #6；对照 `infoLedger(facts)` 与 `closingEvent` | `retell-plan-00{5,6,7}.json` | O 0.7 后半 |
| 0.9 | `ledger knows` 临时实现：从知识账导出第 6 集每个在场人物的 `knows / notKnows` | `knows-ep006.json` | 新 |
| 0.10 | C5a：第 6 集对话表（`segments[]`、`listenerKnows` 从 0.9 来、`exemplars.source` 三类、c2 那类信息必须有对象或独白理由）；装 138 条里的同处境正反例，`no_exemplar` 如实标 | `dialogue-plan-ep006-v2.json/.md` | D 0.7 |
| 0.11 | C5b：按对话表生成正文；`plan-text-map` 标 `verbatimFrom`；8 字档对装包样本、13 字档全库、禁词扫描 | `ep-006.g1.md`、`plan-text-map-ep006-v2.md` | D 0.8 |
| 0.12 | 冷读复述（只装 g1，提示词按 §2.6 #6）；处境对照（15＋2 问，**双跑**）；一致性核对；`dialogue-diagnose`（含 `INFO_REPEATED`）对 g1、f1、e2、w1 并排只列信号；`capacity text` 两口径 | `retell-ep006-g1.json`、`check-ep006-g1.json`×2、`consistency-ep006-g1.md`、`signals-ep006.md` | D 0.9 |
| 0.13 | 对照报告：新第 6 集估时对目标（与 f1 的 9–10 分钟并排）；冷读覆盖（g1 vs f1 vs e2）；追问单对新实现的回答；C5a 有没有退回；7 条批注在 g1 对应位置是否仍在（抄的行单列）；两轨底账差异（计划轨 vs g1 的实际轨）；暴露的 schema 修正点清单 | `docs/d6/d6-0-report.md`（只有编号与统计，不含私有正文） | O 0.9 ＋ D 0.10 |

**验收（分判，没有数值门槛，不需要编剧投入）**

- 功能地图（S，临时脚本）：四条线每个功能有 `selected` 实现且其回答记录无 `notHolds`；被否定的候选有 `rejectedBecause`。
- 底账（S）：四条线依赖的条目齐；`contested` 为零；`unverified` 清单存在并注明依赖的集；九条规则对 `ledger@ep000` 与三集 planned delta 全过。
- 季编排（S）：受影响的集每集有 `capacity` 记录；超出的有 `action`，没有「待定」。
- 分集计划（S）：三集 `plan-check` 全过；冷读只读 `events` 复述出 `facts` 每条与 `closingEvent`（`missing` 为零；若非零，回 C4 一次后再核，记录两次）。
- 对话表与正文（S）：每个 `fact` 有承载句或画面理由；每个 `segment` 有 `closer`；`listenerKnows` 与知识账无矛盾；对齐无未登记偏离；两档 `dup-check` 零命中；禁词零命中；C5a 若有退回，`changeProposal` 记录在且带默认。
- 冷读与问题单（S 记录在，M 内容附证据）：复述每条 `fact` 有行号；17 问每问有引用与原因；双跑一致性记录在；「不成立」项已回对话表修订并复读。
- 设定核对报告与决定队列（S）：每条 `user_given` 不成立项都有候选与默认。
- 对照报告在 `docs/d6/`，不含私有句子。

**退出条件**：上述 S 项全过；对照报告写明「哪些 schema 要改」。任一方不过，停在 D6-0 重看成因，不进 D6-1。
**工作量**：8–12 个代理工作日（功能地图与底账 3–4，检索 1–2，季编排与分集计划 2–3，台词层一集 2，核对与报告 1–2）。串行链约 6 天，检索与语料整理可并行。
**回滚**：全部产物在 `runs/pilot-v2/` 与 `docs/d6/`，删目录即回滚；不碰技能、mali-story、现有集纲页面。

### 4.2 D6-1：对象与只读工具（旧流程可用，0.4.0）

**目的**：把 §2.1 的 20 个对象与 §2.2 的命令实现成随包工具，用 D6-0 的产物做夹具；现有流程一字不改地继续可用。

**交付物**

- `schemas/`：`function-map`、`ledger-entry`、`ledger-delta`、`question-set`、`answers`、`season-plan`、`episode-plan`、`decision-queue`、`media-profile`、`dialogue-exchange`、`corpus-manifest`、`contrast-pair`、`dialogue-plan`、`dialogue-target`、`writer-note`、`retell-record`、`plan-text-consistency` 各一个 `.schema.json`＋`schemas/examples/` 一例（`tests/test_contracts.py` 断言每个 schema 一例）；`task`、`review-record`、`run-handoff`、`context-snapshot`／`selection` 的字段扩展（旧例子仍通过）。数据文件：`reality-check-questions.json`、`dialogue-check-questions.json`、`constraint-blocklist.json`（放 `schemas/data/`，`validate.py` 对非 schema JSON 的检查要放宽为「允许 `schemas/data/` 下的数据文件」，与 `schemas/examples/` 同法）。
- `scripts/checks/`：`ledger.py`、`plan_check.py`、`capacity.py`、`answers_check.py`、`retell_check.py`、`consistency.py`、`diagnose.py`、`decision.py`、`feedback_ingest.py`（骨架：writer-note 与路由，派生物在 D6-4 补全）、`corpus/`（`segment`、`label` 的 S 部分、`filter`、`lexicon`、`rate`；`fetch` 放 D6-4）；`context_pack.py` 新角色与装包规则；`season_check.py` 新规则**实现但按项目自动选集**（见下）；`dup_check.py` 的 `--list-hits --k`；`episode_check.py` 口播量统计。
- `drama_tools.py` 子命令；`SKILL.md` 随包工具表同步（`test_skill_routing.py` 要求）；`README.md` 记命令。
- `tests/`：每条 S 规则一个正反用例；`season-check` 的旧测试全部不动且通过。

**新旧并存怎么处理**

- `season-check --outline`：项目有 `planning/season-plan.json` 时跑新七条＋旧八条里仍适用的（`outline-sequential`、`outline-review`、`saved` 等），没有时只跑旧八条；输出 `ruleSet: legacy | outline-layer`。《渊心锁》与本项目现有记录没有季编排 → `legacy`，结果与今天完全一致（测试锁定）。
- `season-check --episodes`：项目有对话表记录时跑正文侧新规则并跳过 `voice-card`／`dialogue-pass`／`dialogue-read`；没有时跑旧规则。D6-1 阶段两套都在；D6-3 才把旧三条改为只在 `--legacy-dialogue` 下跑。
- 其余新命令都是只读、按需调用，不改任何现有产物。

**验收（S）**：全部新 schema 正反用例通过；D6-0 的 `function-map-v1`、`ledger-ep000`＋三集 delta、`season-plan-v0`、三份 `episode-plan`、`dialogue-plan-ep006-v2`、两份 retell、`check-ep006-g1` 作为夹具全部通过对应命令（`ledger replay` 能从 `ep000` 重放到第 7 集）；`capacity` 对 `episode-plan-006` 与 g1 的输出与 D6-0 的临时脚本一致（允许 ±1 秒舍入）；`season-check` 对《渊心锁》与本项目的旧记录输出与 0.3.6 逐字节一致；`validate.py` 通过；`test_skill_routing` 通过。
**退出条件**：上述全过；0.4.0 发布可安装（`install.py verify`）。
**工作量**：10–14 个代理工作日（schema 与契约 3，底账与计划工具 3–4，容量与核对命令 2，语料 S 命令 2，season-check 并存 1–2，测试与文档 2）。语料命令与底账工具并行可压到 8–10 天。
**回滚**：删新文件、还原四个扩展 schema 与 `season_check.py`／`context_pack.py` 的改动；旧流程未被触及，所以回滚不影响任何项目。

### 4.3 D6-2：切换集纲层（0.5.0）

**目的**：新项目和新写的集纲默认走 C3a→C3b→C3c→C4 分集计划；`season-check --outline` 的新规则对新项目生效。

**交付物**

- 文档：新 `references/outline-layer.md`；`planning.md` 重写「蓝图、设定圣经与集纲」；`workstations/c3-structure.md` 拆三份；`c4-episode-outline.md` 改写；`c6-review.md` 加集纲侧三读（追问单复核、底账一致性、分集计划冷读）；`season-run.md` §1；`workstations/README.md` 索引与执行层级表；`approval-flow.md` 三份附录；`recovery.md` 恢复顺序；`SKILL.md` 路由与「一次完整创作」第 6 步。
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

「阶段」是废除或重构发生的阶段；「旧项目文件不动」对所有行成立。

| # | 组件 | 处置 | 阶段 | 来源 |
| --- | --- | --- | --- | --- |
| 1 | 六字段集纲（作为计划格式） | 废除；`episode-plan` 取代 | D6-2 | O#1 |
| 2 | 六字段（作为派生摘要） | 重构为可选 `summary`，S 核无新实体 | D6-2 | O#2，主创已定 |
| 3 | 「关键选择」字段与审读硬项 | 废除；并入 `moves[]` | D6-2 | O#3 |
| 4 | 剧情框架 260 字上限 | 废除 | D6-2 | O#4 |
| 5 | `planning.md`「蓝图、设定圣经与集纲」 | 重构 | D6-2 | O#5 |
| 6 | C2 工位文档 | 保留＋收窄（只写人；前史事件须有账条目） | D6-2 | O#6 |
| 7 | C3 工位文档 | 重构为 c3a/b/c | D6-2 | O#7 |
| 8 | C4 工位文档 | 重构（14 字段；六步保留） | D6-2 | O#8 |
| 9 | 设定圣经 `bible` | 重构为输入（拆成 `user_given` 功能与条目） | D6-2 | O#9 |
| 10 | `framework-vN.md` | 重构：结局与因果链 → 功能地图；分卷蓝图 → 季编排卷级视图；第五节程序口径 → 程序账；第七节道具表 → 物件账；第九节节拍表废除 | D6-2 | O#10、#15 |
| 11 | `notes-*.md` 段末「给后段」 | 废除；底账逐集修订取代 | D6-2 | O#11 |
| 12 | `runs/state/after-ep-NNN.md` | 重构为底账实际轨的导出（文件名沿用） | D6-2 | O#12、§2.5 #14 |
| 13 | 集纲审读（`review-record` 对 `episode_outline`） | 重构：追问单复核、底账一致性、冷读；finding 带 `cites` | D6-2 | O#13 |
| 14 | `season-check` 集纲八条 | 保留＋扩七条；按项目自动选集 | D6-1 实现、D6-2 启用 | O#14 |
| 15 | 圣经第五节信息阀门表 | 重构为知识账 | D6-2 | O#16 |
| 16 | `open-issues` /「待主创定」 | 重构为决定队列（带默认） | D6-2 | O#17 |
| 17 | 分段送审＋「只改一次、不动集数、不动标题、不动★」 | 废除；升 S（`constraint-blocklist`） | D6-1 实现、D6-2 启用 | O#18 |
| 18 | 对标仿写技能的「精简五要素」 | 不动，不再引用 | D6-2 | O#19 |
| 19 | 台词方案 C4 一行 | 由集纲方案细化 | D6-2 | O#20 |
| 20 | `development-lab.md` §1 生活材料 | 保留＋接入检索代理 K1 卡 | D6-2 | O#21 |
| 21 | `c3-structure.md`「删掉一段…」 | 保留，移到 c3c | D6-2 | O#22 |
| 22 | `writing.md`「装不下不压台词，提 C4 变更」 | 保留 | — | O#23 |
| 23 | 声音卡 K5 | 重构为索引；不再是判据与装包必需 | D6-3 | D#1 |
| 24 | 对照卡 K9 | 废除；writer-note＋反例＋对照对取代 | D6-3 | D#2 |
| 25 | 台词遍（`dialogue_author`） | 废除；C5a＋C5b 取代 | D6-3 | D#3 |
| 26 | 台词读（`dialogue_read`） | 废除；冷读复述＋处境对照＋一致性取代 | D6-3 | D#4 |
| 27 | 「盖住名字猜人」 | 废除 | D6-3 | D#5 |
| 28 | `season-check` 的 `voice-card`／`dialogue-pass`／`dialogue-read` | 废除；`--legacy-dialogue` 可查 | D6-3 | D#6 |
| 29 | 每批一次定向修订 | 重构：对象换成对话表；修订后复读必做 | D6-3 | D#7 |
| 30 | 修订后不再读 | 废除 | D6-3 | D#8 |
| 31 | `preserved` 清单 | 重构：只认人工来源 | D6-3 | D#9 |
| 32 | 修订单写替换文字 | 废除并升 S | D6-1 实现、D6-3 启用 | D#10 |
| 33 | 数值型台词目标 | 废除并升 S | D6-1 实现、D6-3 启用 | D#11 |
| 34 | 按人物组织的卡片 | 重构：人物只作项目内索引 | D6-3 | D#12 |
| 35 | C5 场面稿 | 重构为 C5a／C5b | D6-3 | D#14 |
| 36 | C6 首读 | 保留 | — | D#15 |
| 37 | C6 次读 | 保留＋加义务（`cites`） | D6-2 | D#16 |
| 38 | 篇幅口径（`min_chars: 800`、450 字/分） | 废除；留 `legacy-aigc` 预设 | D6-3 | D#17 |
| 39 | `episode-check` | 重构：加口播量统计（估时在 `capacity`） | D6-1 | D#18 |
| 40 | `context-pack` 角色 | 重构：新角色 | D6-1 | D#19、O#18 |
| 41 | `dialogue.md` §1「书面腔」表 | 重构 | D6-3 | D#20 |
| 42 | `writing.md`「避免解释性台词」、项目 `writing-rules.md` | 重构 | D6-3；项目文件见 §5 | D#21 |
| 43 | `dialogue.md` §8、§9 | 保留 | — | D#22 |
| 44 | C2 声音探针 | 保留 | — | D#23 |
| 45 | 「另一模型家族做台词读」 | 废除 | D6-3 | D#24 |
| 46 | 项目 `writer-style-brief.md` | 重构：经 `feedback-ingest` 回流后退役 | D6-4；项目文件见 §5 | D#25 |
| 47 | 工艺闭环 §4.4、§4.5 | 废除（被取代） | D6-3、D6-5 状态行 | D#26 |
| 48 | 工艺闭环 §3 分层 | 保留概念 | — | D#27 |
| 49 | 样本库设计 §3 分级 | 倒置 | D6-4 | D#28 |
| 50 | 样本库设计 §7 数数关口、§8 覆盖卡、§5 第 1／7 步 | 废除 | D6-4 | D#29、30、32 |
| 51 | 样本库设计 §9 留出法 | 保留为可选描述 | — | D#31 |
| 52 | v2 媒介档案配额字段、`acceptedBand`、分布距离、`within/outside` | 废除（schema 拒绝） | D6-1 | D#33 |

## 5. 本项目的处理

这一节只给事实与选项，不替主创定内容方向。阶段 D6-0 自身只产证据，不改任何集纲页面与正文页面。

### 5.1 现状（事实）

- 集纲：60 集 `episode_outline` 页面（r2／r3），分五段写成；结构审查 0/60 剧情框架自足；56 条提案待主创决定。
- 正文：第 1–10 集页面 r4／r5；第 1–5 集有编剧改定稿（w1）；第 6–10 集有台词调整稿已交付飞书；第 6 集另有 e2（旧流程）与 f1（台词方案阶段 0）两版试验稿，都未入页面。
- 送审包 v3 待审批（框架 v3、小传 v2、集纲 1–60、前 10 集正文）。
- 地基不成立的线（现实审查 §四）：三年空白、礼物、监护程序、事故真相、哨子芯片；钱的线是账的空字段。受影响的集见集纲方案 §17 的表。
- 已写并经编剧改定的第 1–5 集里，建在这些地基上的场面：第 1 集退件单、「回乡下」的信、存折；第 3 集监护材料；第 4 集民警离开；第 5 集方砚与仓管两个电话；第 6 集整场物流仓与监察员（集纲方案 §17）。不建在这些地基上的部分（油锅、巴掌、账本、哨声、手环、民警问话分寸、错名）不受影响。
- 容量：60 集每集事件中位 11；第 6 集按对白承载估 9–10 分钟（两口径），前五集定稿 66–156 秒。

### 5.2 三种走法

| 走法 | 做什么 | 工作量（代理工作日） | 会动到的已改定内容 | 对送审包与页面版本的影响 |
| --- | --- | --- | --- | --- |
| **A 全季重做** | 全剧功能地图与底账（所有线，含哨子、学校消防、庭审、对手中层）→ 60 集季编排与容量 → 60 集分集计划重产 → 第 1–10 集按新计划重写（C5a→C5b）→ 第 11 集起按新流程写 | 功能地图与底账 8–12；季编排 3；分集计划 60 集 12–18（按 15 集一段）；前 10 集重写 10–15；合计 35–50 | 第 1–5 集编剧改定稿里建在五条线上的场面全部重写；不在这些地基上的场面尽量逐字保留（`season-run.md` 的保留场机制） | 送审包 v4 全包重绑（框架→功能地图＋季编排、小传收窄、60 集分集计划、前 10 集新正文）；按 `approval-flow.md` §4 属方向变更，全包复审一次；旧页面修订保留可回看；集数很可能变（容量处理后要么集数增、要么每集事件减到三分之一上下） |
| **B 只重建地基不成立的线** | D6-0 的四条线＋哨子线、钱的账；其余线沿用现集纲的事件（照正文回写的第 1–10 集事实索引多数是对的）；季编排只重排受影响的集；分集计划只重产受影响的集，其余集由脚本把六字段「搬」进 14 字段骨架并标 `migrated: partial`（缺的字段——入口、信息清单、状态变化、现实依据、容量——按集补） | 功能地图与底账 6–9；季编排 2；受影响集的分集计划约 30 集 6–9；其余 30 集搬运与补字段 4–6；受影响正文重写（第 1、3、5、6 集的对应场面）3–5；合计 21–31 | 第 1 集三处、第 3 集一处、第 5 集两个电话、第 6 集仓库与监察员；其余逐字保留 | 送审包 v4 局部重绑：受影响的集纲页面出新修订，其余页面不动；正文第 1、3、5、6 集出新修订；按 §4 仍是方向变更（主要人物关系与全剧结构被动），但复审范围可标明「只看变动集」；集数变不变取决于受影响集的容量处理 |
| **C 以 D6-0 的产出作起点** | D6-0 产出的四条线功能地图、底账、第 1–12 集季编排、第 5–7 集分集计划、第 6 集对话表与正文直接作为本项目新版的 v1；其后按新流程逐段推进（先第 1–12 集补齐分集计划与正文重写，再 13 集起），每段送审 | D6-0 本身 8–12（已算在实施计划里）；之后每段（12 集左右）分集计划 3–4＋受影响正文 2–3；全季约 25–35，但分散在流程里 | 与 B 相同，但按段逐步动，不一次性 | 送审包按段出新版（v4 只含第 1–12 集的新分集计划与第 1、3、5、6 集新正文；13 集起随后续段）；主创每段看一次，但不新增审批点——仍是「送审包审批」这一处，只是分批送 |

**各走法共同的事**：不管选哪条，`writer-style-brief.md`、`writing-rules.md` 的条目经 `feedback-ingest` 回流成 `drafted` 约定与反例（D6-4），文件退役；第 6–10 集的台词调整稿不再作为后续输入（它们建在旧第 6 集集纲上）；56 条待决提案由脚本搬进决定队列并各补一个默认走法；现实审查里「凭常识写、未查法条」的约 60 项成为底账的 `unverified` 清单初值。

**阶段 D6-0 的默认**：选线按 §4.1 0.1（礼物＋三年空白先做，再监护、事故）；重排范围限第 1–12 集；分集计划只写第 5–7 集；台词层只做第 6 集。这些是验证范围，不是项目决定；它们恰好是走法 C 的第一段，也是走法 A、B 的子集，所以无论主创之后选哪条，D6-0 的产出都不浪费。

**不替主创定的事**：选 A／B／C；哪条线的哪个功能可以 `dropped`；拆集后的总集数；第 1–5 集编剧改定稿里受影响场面的重写范围；哨子芯片线是否换实现（它是用户给定设定，按第 3 条决定会先按候选走并标 `pending`，但「要不要保留芯片这个设定」是内容方向）。

## 6. 风险与应对

| 风险 | 触发信号 | 应对 |
| --- | --- | --- |
| 底账维护成本高，写成套话或没人更新 | `ledger check` 报 `why` 为空或与同类条目字面重复；连续两集 `planned` 有 delta 而 `actual` 无 delta | `why` 非空且不重复是 S 规则；实际轨由脚本从 C5b 的 `stateChangeProposals` 应用，不靠人手写；`context-pack` 按 `reads` 只装引用到的条目，全账不进包（预算不涨） |
| 检索出处不可靠、过时或查不到 | K1 卡 `external_not_checked` 比例高；同一程序两张卡结论相反（`contested`） | 卡标日期与地域；查不到就 `unverified` 并带到送审包，不编造；`contested` 为零是 C3b 交接条件，两卡相反时追问单第 9 问重答；主创或顾问任何时候给出处就 `feedback-ingest` |
| 模型做追问单走过场（每问都 `holds`） | 候选 A 的回答里 `notHolds` 为零（两份审查已证明它们不成立）；同一候选双跑答案不一致 | D6-0 任务 0.2 把两份审查的结论当标准答案核一次「追问单能不能答出已知的不成立」；双跑不一致的问标 `unstable`；每答必落到动作、必给原因、涉出处必引卡，错判事后可见 |
| 容量算出来集数大增 | 季编排粗估下 60 集里过半要拆 | 这是现状不是新架构造成的（结构审查 §5.3）；数字触发的是「必选一个动作」，选重排／删线还是拆集由功能与人物定；送审前自由，送审后是方向变更走 `approval-flow.md` §4，主创决定，不是系统拦截 |
| 两层往返不收敛（C5a 退回 C4，C4 退回 C3c，再回来） | 同一集 `changeProposal(targetLayer: C4|C3c)` 计数 ≥2 | 退回必带默认走法，流程按默认继续；第二次退回时 `season-check` 报 `loop-detected`（只报）；根因通常是季编排容量没处理完，回 C3c 重算一次而不是继续在 C4、C5a 之间倒 |
| 语料计费未确认 | 取用前后 `get_shared_creation_budget` 读数或回执有变化 | 先取 3 部各 10 集；有变化即停、记录、不取全库；D6-4 以小样本结束不阻塞 D6-5 |
| MCP 连接不稳（本会话 mali-story 连接超时；stage-a 实测 3 次失败 0 次重试） | `ECONNRESET`、`CONNECT_TIMEOUT`、404 | `corpus fetch` 带重试与断点，按 `manifest.json` 续取；页面写入沿用回执与对账（`receipt pending`）；D6-0 的语料不需要新取；离线时标 `not_sent`，不写「已保存」 |
| 新对象太多，宿主模型不照做 | 装包时缺对象；交接里没有 delta | S 项拦装包与存稿：没有季编排不给 C4 装包、没有对话表不给 C5b 装包、没有复述与问题单记录不算修订完成、没有 delta 不算分集计划 |
| 补丁计数被改 id 绕过 | 新旧实现描述 8 字档重合高 | `renamed_patch` 提示（不拦）；首读仍看效果 |
| 两轨差异没人看 | 差异报告存在但下一集 `entry` 引用的是 `planned` | C4 的 `entry` 必须接实际轨（有正文时），S 核；差异报告进送审包 |
| 冷读者复述得太好或太差（模型读文字比观众多；随机差异） | 同一稿两位冷读者 `unclear` 差异大 | 提示词三处改法（§2.6 #6）；每稿至少两位读者才比较读者差异；△ 行信息另估 |
| 语料对核心处境为空 | `no_exemplar` 比例高 | 如实标，不拿近似当同处境；允许 `source: project` 的本剧人工句；D6-4 补语料 |
| 新旧并存期 `season-check` 误判 | 旧项目被按新规则核 | 按 `planning/season-plan.json`／对话表记录是否存在自动选集，输出 `ruleSet`；测试锁定《渊心锁》与本项目旧记录结果不变 |
| 验收时把 M 项当通过条件 | 验收表里出现「冷读通过」「问题单全成立」作为门 | 每阶段验收只写 S／R；M 项写「记录在」「附证据」 |

## 7. 不变量与守则（实施期间的硬约束）

| 规矩（主创已定或仓库规则） | 机制 | 层级 |
| --- | --- | --- |
| 架构通用，项目差异进参数或数据 | 程序账、问题单、禁词表、媒介档案、词表都是数据文件；技能只规定「有依赖就要有条目、条目要有状态」；不向主创提项目参数 | S（schema 不含项目名）＋M |
| 不新增人力环节；人工反馈来了就吸收 | 人审点仍是两处；决定队列每条带默认，流程按默认走；`feedback-ingest` 回流，`drafted` 即进包；编排方不得以「等人确认」暂停 | S（`default` 必填；无来源不入库）＋M |
| 数字不当裁判 | 媒介档案拒绝配额字段；对话表无 `estimates`；`dialogue-diagnose` 无 `within/outside`；`capacity` 退出码 0；验收无数值门槛；补丁计数与容量触发的都是动作不是判定 | S（schema 与测试：输出里出现区间比较字段即测试失败） |
| 不打补丁：修订回功能层换实现 | `patch-cap`：`patchCount ≥ 2` 的实现再原地修订被拒；finding 必带 `cites`；修订单不含替换文字 | S |
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
| 1 | **工作室级语料缓存的契约变更**（台词方案 §12.4、§15.1）：在架构 v1.2 §8.5 开一条「mali-story 模板数据的本地只读缓存可以工作室级」，知识卡规则不动 | 缓存放项目目录（现状 `runs/pilot-ep006/corpus/`）；schema 两级都允许但 `contract-check` 在确认前只放行 `project`；架构 v1.3 的 §8.5 写「待定」 | 确认后挪目录、改 `scope.level`、放行规则——半天；不确认则每项目各缓存一份，功能等价成本 ×N | D6-4 取全库之前 |
| 2 | **语料原句进包的边界**（§15.2）：遮蔽后原句 ≤2 句进包，还是只给处境、说明与骨架 | 遮蔽 ≤2 句进包，配 8 字档核对（D6-0 已这么做，零命中） | 改一个 `context-pack` 参数（`--mask-lines 0`） | D6-3 之前 |
| 3 | **旧步骤退役时点**（§15.3）：D6-3 起新运行不再做台词遍／台词读，还是并行一批再退 | 直接退（RCA 证明它们改不了结构）；`--legacy-dialogue` 保证旧记录可核 | 文档一行＋`season-check` 默认值，可改回「并行一批」 | D6-3 发布前 |
| 4 | **容量提案三选一由谁定**（§15.4）：每次交主创选，还是授权编排方按默认走、集末一并审 | 送审前由季编排层选（它是系统内的动作）；送审后进决定队列、按默认先走、随送审包一并审（不新增审批点） | 改默认为「等主创」只是把 `default` 改成「暂停」，但那违反「流程不等」，所以可逆但不建议 | D6-2 之前 |
| 5 | **本项目的走法**（§5.2 A／B／C） | C：D6-0 的产出作为新版起点，之后按段推进 | 选 A 或 B 时 D6-0 的产出仍是子集，不浪费 | D6-0 对照报告出来之后 |
| 6 | **人工改句可以逐字用**（§2.5 #12；stage-d §十 8 要定） | 本剧编剧的句子可以逐字用并标 `verbatimFrom`；语料原句永不逐字 | 改为「一律不逐字」只需把 `grade: human` 的样本也走遮蔽 | D6-3 之前 |

## 9. 第一周做什么（D6-0 任务清单）

按先后编号；同一行里「∥」表示可并行。「代理」指类型：带检索的代理、写作代理、核对代理（新上下文）、脚本代理（临时脚本，不进技能）。全部产物在 `projects/qige-xiongdi/runs/pilot-v2/`（下面省略前缀）与 `docs/d6/`。

| 序 | 任务 | 输入 | 产出文件 | 代理 | 先后 |
| --- | --- | --- | --- | --- | --- |
| 1 | 建目录与骨架：`pilot-v2/`、`tools/`（复制 `pilot-ep006/tools/` 可用部分）、`docs/d6/README.md` 占位；写 D6-0 的隔离规则（写作代理不读 `reviews/`、不读 e2/f1） | 本计划 §4.1 | `README.md`、`tools/`、`docs/d6/README.md` | 脚本代理 | 第 1 天 |
| 2 | 礼物线＋三年空白线功能地图 v0：功能列表（从现实审查 §2.4、§四抄起），现行实现作候选 A，列 `ledgerDeps` | 两份审查、集纲 1–12、框架 v3、小传 v2 | `function-map-v0.json/.md` | 写作代理 | 第 1 天 |
| 3 | ∥ 问题单数据：追问单 15＋1 问、对话问题单 15＋2 问，版本化 JSON；冷读提示词两份（计划／正文）按 §2.6 #6 改 | 两份方案 §6.3／§8.3、stage-d §十 | `questions/reality-check-questions-v1.json`、`questions/dialogue-check-questions-v1.json`、`prompts/cold-read-plan.md`、`prompts/cold-read-text.md` | 脚本代理 | 第 1 天 |
| 4 | 候选 A 过追问单（礼物、三年空白） | 任务 2、3 | `reality-check/RC-A-*.json` | 核对代理 | 第 1–2 天 |
| 5 | ∥ 检索代理：礼物线与三年空白线涉及的程序与行业做法（快递拒收与无着件、远洋／外地务工通讯与汇款留痕、民事上门与报警常规等）查出处写 K1 卡；现实审查 §六的来源入卡；查不到的写明 | 任务 2 的 `ledgerDeps`、现实审查 §六 | `knowledge/cards/K1-*.json`、`knowledge/sources/` | 带检索的代理 | 第 1–3 天 |
| 6 | 监护程序线、事故真相线功能地图 v0 与候选 A 追问 | 同任务 2、4 | 并入 `function-map-v0`、`RC-A-*` | 写作代理→核对代理 | 第 2–3 天 |
| 7 | ∥ 检索代理第二批：监护顺位与撤销、公告送达、工亡补助与抚恤金领取、事故调查报告期限、保密协议对抗调查 | 任务 6 | 同上 | 带检索的代理 | 第 2–4 天 |
| 8 | 底账 `ledger@ep000`：四条线的六类账，用户给定标 `user_given`，程序账引任务 5、7 的卡；空白期总账视图；临时脚本核九条规则 | 任务 2、5、6、7、圣经 | `ledger-ep000.json`、`ledger-check-ep000.json`、`blank-period-view.md` | 写作代理＋脚本代理 | 第 3–4 天 |
| 9 | 候选 B（每线一到多个）过追问单，选定；设定核对报告；决定队列（每条带默认） | 任务 4、6、8 | `function-map-v1.json/.md`、`reality-check/RC-B-*.json`、`decisions.json`、`setting-check-report.md` | 写作代理→核对代理 | 第 4–5 天 |
| 10 | 季编排第 1–12 集：受影响的集重排；容量粗估两口径（媒介档案 v0 复用）；超出的集选动作；plant／pay 位 | 任务 9、`pilot-ep006/media-profile-v0.json`、语料交换中位时长 | `season-plan-v0.json/.md`、`capacity-season-v0.md` | 写作代理＋脚本代理 | 第 5 天 |
| 11 | 第 5–7 集分集计划（14 字段，`facts[]`）；`plan-check` 临时脚本；容量复核；超两倍时提案带默认拆法并按默认写 | 任务 8–10、集纲 5–7、第 4 集定稿（w1）出口 | `episode-plan-00{5,6,7}.json/.md`、`plan-check-*.json`、`ledger-ep00{5,6,7}.planned.json` | 写作代理＋脚本代理 | 第 5–6 天 |
| 12 | 分集计划冷读（三集各一位新上下文读者，只装 `events`）；`retell-check` 临时脚本 | 任务 11、任务 3 的提示词 | `retell-plan-00{5,6,7}.json`、`retell-check-plan-*.json` | 核对代理×3＋脚本代理 | 第 6 天 |
| 13 | `ledger knows` 临时实现：第 6 集在场人物的 `knows / notKnows` | 任务 8、11 | `knows-ep006.json`、`tools/ledger_knows.py` | 脚本代理 | 第 6 天 |
| 14 | 第 6 集对话表 v2（`segments[]`、`listenerKnows` 从任务 13 来、`exemplars.source` 三类、独白理由、画面理由；装 138 条里的同处境正反例） | 任务 11、13、`pilot-ep006/corpus/`、反例与对照对、台词目标 v0（加 `conflictsWith`） | `dialogue-plan-ep006-v2.json/.md` | 写作代理（不读 e2/f1） | 第 6–7 天 |
| 15 | 第 6 集正文 g1；`plan-text-map` 标 `verbatimFrom`；两档 `dup-check`、禁词扫描、`capacity text` 两口径 | 任务 14 | `ep-006.g1.md`、`plan-text-map-ep006-v2.md`、`checks-ep006-g1.json` | 写作代理＋脚本代理 | 第 7 天 |
| 16 | 正文冷读（只装 g1，两位读者）；处境对照（17 问，双跑）；一致性核对；`dialogue-diagnose` 对 g1、f1、e2、w1 并排；两轨 diff（计划轨 vs g1 实际轨） | 任务 15、任务 3 | `retell-ep006-g1-{a,b}.json`、`check-ep006-g1-{a,b}.json`、`consistency-ep006-g1.md`、`signals-ep006.md`、`ledger-diff-ep006.json` | 核对代理×4＋脚本代理 | 第 7–8 天 |
| 17 | 对照报告与 schema 修正清单（§4.1 0.13） | 全部 | `docs/d6/d6-0-report.md` | 核对代理（读全部产物） | 第 8 天 |

串行链：2→4→9→10→11→12/13→14→15→16→17，约 8 个工作日；任务 3、5、7 并行。编剧投入 0；主创投入 0（§8 的事项不阻塞 D6-0）。

---

本计划只新增这一份文档，并在两份方案里记入了主创 2026-10-14 的决定与修订记录。没有修改技能文件、脚本、schema、测试、项目文件、集纲、剧本或知识卡；没有向编剧或主创确认任何一条 §8 的事项；所有 S 级都是设计层级，D6-1 实现并有正反测试后才成立。
