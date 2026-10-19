# 台词层：对话表、正文与五读

[工位契约](workstations/README.md) · [单集工位流程](writing.md#工位流程) · [集纲层](outline-layer.md)

本页是台词层的操作手册，写给执行的 AI：每一步做什么、产物放哪、跑哪条命令、退出码怎么读。前提是一个判断：短剧的一集是几段靠对白承载信息的对话交换，每段对话几个来回、话长话短，要由处境推出来。处境就是谁对谁说、想要什么、对方已知什么、两人什么关系、此刻什么情绪、观众要明白什么。所以先写对话表，再照表写正文；质量靠冷读复述、处境对照、设计依据一致性三件事判，加上原有的首读、次读。数字只做容量算术、诊断提示和描述，不作通过条件。

每条规矩标层级：**S** 是随包脚本能核的，**R** 是 mali-story 服务端保证的，**M** 是模型照做的约定。验收只引用 S／R。随包脚本永不联网、不调模型。

例子都是为说明而编的：小镇上的老陈三年前往老家寄过一个箱子，舅妈王姨签收后没告诉他；仓库的仓管、镇口小卖部的刘叔各知道一点。不取自任何真实项目。

## 1. 总览：C5a 对话表 → C5b 正文 → C6 五读 → 先改表再改文

| 步 | 做什么 | 装包角色 | 产物（项目目录下） |
| --- | --- | --- | --- |
| C5a 对话设计 | 每场的话题、每个话题的处境与走法理由、每条信息由哪一来回承载、收尾、样本 | `dialogue_designer` | `planning/dialogue/dialogue-plan-<NNN>.json` |
| C5b 正文 | 照表逐话题写台词与动作行；写对照表；提出实际轨的状态变化 | `author`（任务 `layer: C5b`） | `runs/<批>/ep-<NNN>.c5b.md`、对照表 `runs/<批>/ep-<NNN>.plan-text-map.json`、交接里的 `stateChangeProposals[].ledgerDelta` |
| C6 首读 | 观众效果；只读正文，按批做（一次不超过 `season-check --batch-size`，默认 10 集），记录写完封存 sha256 | `reader_effect` | `review-record`（`.drama/reviews/`） |
| C6 次读 | 事实与台词目标条款，逐集做；finding 带 `cites` | `evaluation` | `review-record`（`.drama/reviews/`） |
| C6 冷读复述 | 只读本集正文，复述谁做了什么、为什么、每条信息从哪句知道 | `cold_reader` | `retell-record`（`.drama/checks/`） |
| C6 处境对照 | 对每个话题按对话问题单逐问作答，引句子、写原因 | `situation_checker` | 对话问题单的回答记录（`.drama/checks/`） |
| C6 设计依据一致性 | 正文走法与对话表写的处境、理由对不对得上 | 脚本＋审读方 | `plan-text-consistency` 记录（`.drama/checks/`） |
| 修订 | 先改对话表，再改正文；修订稿存为新的页面修订，改后再冷读、再处境对照 | 原 C5a／C5b 角色 | 新对话表修订、新正文修订 |

五读是首读、次读、冷读复述、处境对照、设计依据一致性，读的都是 C5b 写完后已存为页面修订的那一稿。首读按批，其余四读逐集；冷读复述、处境对照、设计依据一致性取代原来的台词遍与台词读（各读的装包与记录见 [C6](workstations/c6-review.md)）。首读封存：首读那份 `review-record` 写 `sealedSha256`，值是去掉这个字段之后、按规范 JSON（键排序、无空格）算的 sha256；旧做法的 `.sha256` 旁注文件照样认。`season-check` 的首读、次读规则只认审读对象是本集正文的记录。

**输入从集纲层来。** 分集计划的 `infoLedger[].facts[]`（观众本集必须拿到的事实）、`events`（场与拍）、`capacity.status`；底账知识账给出谁此刻知道什么。台词层不重新声明信息，只引用（[集纲层](outline-layer.md#9-分集计划字段14-字段summary-可选)）。

**启用了台词层的判据**：项目里有对话表记录（带 `dialogue-plan` 标记的 JSON，在 `planning/` 或 `.drama/` 下任意深度）。启用后 `season-check --episodes` 核台词层规则，输出 `episodeRuleSet: dialogue-layer`。旧项目没有对话表：不带 `--legacy-dialogue` 时旧的三条台词关口不再出现，新规则按「有对话表才核」，旧项目没有新失败；要复查旧记录，加 `--legacy-dialogue`。旧文件一律不动。

**产物位置**：对话表 `planning/dialogue/dialogue-plan-<NNN>.json`；项目台词目标 `planning/dialogue-target.json`；正文稿 `runs/<批>/ep-<NNN>.c5b.md`，修订稿 `ep-<NNN>.c5b.r<n>.md`，对照表 `runs/<批>/ep-<NNN>.plan-text-map.json`（它是 C5b 的产出，不是核对输出）；审读记录 `.drama/reviews/`；冷读复述、处境对照、一致性、诊断、字面重合与禁词扫描的输出放 `.drama/checks/`；装包历史 `.drama/packs/history.json` 由 `context-pack` 写。文件名里的集号写 `<NNN>`（三位补零，拆集如 `006A`）；JSON 的 `episode` 字段按 schema 写整数或 `"6A"`。

人审点不变：选题确认、送审包审批。台词层不新增任何等人的步骤。

## 2. 台词目标与裁决顺序

**台词目标**（`dialogue-target`，项目级、版本化，放 `planning/dialogue-target.json`；项目第一次做 C5a 之前从随包例子 `schemas/examples/dialogue-target.json` 起步建好，之后经 `feedback-ingest --target` 升版）：`targetId`、`revision`（版本字段）、`mediaProfile`（只含物理量；写 `null` 时用随包默认档案）、`corpusManifest`（用的哪版语料；项目没有语料时写 `null`，并必须写 `noCorpusReason`）、`checkQuestions`（对话问题单版本）、`conventions[]`（每条 `text`、`status: confirmed|drafted`、`sourceNotes[]`、`conflictsWith[]`）、`infoCarriageDefault: dialogue`（信息默认由对白承载）、`changelog[]`。目标里没有任何数值区间或「超了不许存」的项；结构项（信息有承载、切换前有收尾）在对话表 schema 里由 `contract-check` 核。

C5a、C5b、C6 次读与修订任务都引用同一个 `targetId@revision`（`task.dialogueTarget`，S）；对话表的 `basedOn.target` 也引它（`season-check` 的 `target-ref`，S）。目标改版只有三个来源：语料快照更新、`feedback-ingest`（新约定、新问）、用户有记录的决定。审读不能改它，认为缺一条就写 `changeProposal`。

**意见冲突时的裁决顺序**（M）：

1. 用户或编剧本次原话（有记录）
2. `confirmed` 约定条目
3. `drafted` 约定条目（来自两次以上同类人工批注）
4. 对照对里的 `whyNotHere`：本系统在同一处境下已被否定过的走法不再现
5. 对话表写明的处境与理由（正文与它不一致时改文，理由错时改表）
6. 技能通用规则（本页、[写作](writing.md)）
7. 审读意见（首读、次读、冷读、处境对照）
8. 编排方自加的约束：只能收窄，不能与 1–6 冲突，不得是数值目标

语料原句不参与裁决（它是数据）；AI 起草的假设不参与；任何数字不参与。

## 3. 对话表（话题、交换、`listenerKnows`、`carries`、`closer`、`oneItemPerLine`）

对话表写结构，不写措辞。一张表对应一集：

- `episode`、`planRevision`、`basedOn: {episodePlan, target}`。
- `infoLedger[]`：只引用分集计划的 `infoId`／`factId`，加 `carriedBy`：`{exchangeIds: [...]}`（由哪几个来回承载），或 `pictureReason`（画面承载，写理由）。分集计划的每个 fact 都要被引用（S）；容量提案拆段时分到后段的 fact 写 `{infoId, factId, deferredTo: <提案 id>}`，不写 `carriedBy`，这时要求这个提案存在、`kind: capacity` 且有默认（`dialogue-plan-check --decisions planning/decisions.json` 核，S）。
- `scenes[]`：`sceneId`、`participants[]`、`observers[]`、`topics[]`、`monologues[]`（每条带 `whyNoAddressee`）。
- `deviationsFromOutline[]`：与分集计划不一致处逐条登记。
- `changeProposals[]`：发现装不下或信息没有对话对象时提给上游，每条有 `targetLayer`（`C4` 或 `C3c`）与非空 `default`（S）。

**话题**（`topics[]`）：

| 字段 | 写什么 |
| --- | --- |
| `topicId`、`about` | 这个话题在聊什么，一句 |
| `situation.speakerWants` | 开启话题的人此刻想从对方那里得到什么 |
| `situation.listenerKnows` | 听的人已经知道什么、不知道什么。初值由底账生成，模型只能收窄、不能与账相反（见下） |
| `situation.relation`、`powerDirection`（`up／down／level`）、`addresseeIsChild` | 关系与权力方向；对孩子说话单标 |
| `situation.emotion` | 双方此刻的情绪 |
| `situation.audienceLearns[]` | 这一段要让观众明白的 `factId` |
| `shape.turns`、`shape.lineLength` | 由处境推出的走法，定性写（「一方问另一方短答」「半句就停」），不写数 |
| `shape.reason`、`citesSituation[]` | 一句理由，必须引用处境里的字段；`citesSituation` 列出引了哪些 |
| `segments[]` | 一个话题对几个人说时拆段：每段 `between: [甲, 乙]`（说话的两个人，不是区间）、`closer: {by, kind, how}`。没有收尾不许换对象（S） |
| `exchanges[]` | 每个来回：`exchangeId`、`segmentId`、`speaker`、`addressee`、`move`（问／答／反问／否认／交代／让步／收尾／打岔／安抚／指令…）、`carries[]`（承载的 `factId`）、可选 `beatRef`、`oneItemPerLine`、`givesReason` |
| `interruptedBy`、交换上的 `interruptedAt` | 话题的 `interruptedBy.by` 写谁打断；被打断的那个交换上写 `interruptedAt`，值是它自己的 id 或打断落在的交换 id。`plan-text-consistency` 核被打断的交换之后、正文第一条对白是打断者说的；被打断的人不必把话说完 |
| `exemplars` | 引用的正例与对照对（§4）；没有就标 `no_exemplar` |

**`listenerKnows` 从底账来。** 先跑 `ledger knows <入口底账修订> --episode-plan <分集计划> > .drama/checks/knows-ep<NNN>.json`，存下按场、按人的「此前已知」导出（`--who <人> --at <集>` 只单查一个人，给不出按场的导出）；`situation.listenerKnows` 写成 `{initial: {knows: [...]}, narrowedOut: [...]}` 时，`initial` 取导出里的 id，`narrowedOut` 只能去掉 `initial` 里有的（S 只报）。只写一句话也行，脚本退回文本粗核并标出来。账外的人物间已知（一句叮嘱、两人的约定）不直接写进 `listenerKnows`：先开一次 C3b 运行把它登记成知识账条目，再从底账里取，谁知道什么只有底账一个来源。

**说话人凭什么知道。** 说话人承载的 fact，按底账 id 核他在这一来回之前知不知道：场前已知、本场按拍已知、本场更早的来回告诉过他，或本集他自己做的、在场的（`dialogue-plan-check` 的 `speaker-knows`，S）。没有可用 id 的记 `notEvaluable`，不按文字猜。图谋账条目的主人（`party`）算知道这条图谋的内容，`ledger knows` 照此导出。

**不写数。** 对话表不许有 `estimates`，也不许有名字像数量配额、值是数字的字段（S）。来回多少、话多长，由处境推出并写理由。

**例**（压缩）。同一条信息「箱子三年前已退回，签收人是王姨」，两种处境：

- 话题甲：老陈在仓库柜台问仓管。`speakerWants`：弄清箱子在不在；`listenerKnows`：仓管知道三年前退过、不知道老陈为什么现在才来；情绪：老陈急、仓管平静。`shape`：一方问、另一方短答，仓管照登记簿一件一件报。`reason`：老陈急（emotion），仓管只按登记簿答（listenerKnows）。
- 话题乙：同一件事由刘叔在小卖部说出来。`speakerWants`：刘叔想劝老陈别回家吵；`listenerKnows`：老陈还不知道签收人是谁；情绪：刘叔犹豫、老陈起疑。`shape`：刘叔绕着说、被老陈追问两次才说出名字。`reason`：刘叔怕得罪王姨（relation），老陈起疑才追问（emotion）。

两张表装的信息相同，来回数和话的长短完全不同，差别全写在 `reason` 里。话题甲写成记录大致是：

```text
topic T1  about: 老陈问箱子的去处
  situation:
    speakerWants: 弄清箱子在不在
    listenerKnows: {initial: {knows: [L-tl-001]}, narrowedOut: []}   # 仓管知道三年前退过
    relation: 办事的对来问的；powerDirection: up；addresseeIsChild: false
    emotion: {老陈: 急, 仓管: 平静}
    audienceLearns: [I1-f1]
  shape:
    turns: 一方问另一方短答
    lineLength: {老陈: 完整句, 仓管: 短}
    reason: 老陈急（emotion），仓管只按登记簿答（listenerKnows）
    citesSituation: [emotion, listenerKnows]
  segments: [{segmentId: T1-s1, between: [老陈, 仓管], closer: {by: 仓管, kind: line, how: 报出签收人}}]
  exchanges:
    X-T1-01 老陈→仓管 问   carries: []
    X-T1-02 仓管→老陈 答   carries: [I1-f1]  oneItemPerLine: true
  exemplars: {positives: [{ref: <模板>#<交换>, source: corpus, maskedLines: [一句遮蔽原句]}], contrast: []}
```

C5b 照它写出来，仓管就是一问一答、一次报一件；正文里如果仓管连说三句，`plan-text-consistency` 与处境对照都有东西可以抓。

**C5a 什么时候能装包。** 分集计划的 `capacity.status` 是 `fits`，或 `proposal:<决定 id>` 且该决定有默认，`context-pack --role dialogue_designer` 才装（S，否则退出码 2）。按提案默认走：默认拆法是按粗估比例拆成几段，本集只写第一段，其余登记为下一集的入口；本段对话表只承载本段的 fact，后段的写 `deferredTo`。某条信息找不到对话对象又没有独白理由时，不自己凑，写 `changeProposal` 回 C4，带默认走法。

## 4. 样本怎么用（处境检索、遮蔽、每话题上限、`verbatimFrom`）

样本告诉作者「处在这种处境里的人怎么一来一回把话说清」，不是要落进去的句数和字数。语料怎么取用、切分、过滤、标注与缓存见 [语料](corpus.md)。

**检索键是处境**：功能（从 `exchanges[].move` 推主功能）＋关系＋是否对孩子＋情绪，可选信息模式。顺序：同题材同形态 Tier 1 → 同题材 Tier 2 → 跨题材 Tier 1（对话表记 `styleIsolation: true`）→ 都没有就标 `no_exemplar`，不拿近似处境充数。

**每个样本在包里**：处境、结构说明（`walkthrough`：这段为什么这样走）、骨架（谁、每句的 `move`、长短档、问答序列、收尾类型）、遮蔽后的原句（人名、地名、机构、专有物件换成占位）。

**数量**：每个话题 2 个正例、1 个对照对（有同处境反例时）；遮蔽原句每个话题合计最多 2 句（S：`dialogue-plan-check` 核 `maskedLines`；装包时 `--quotes-per-topic` 设上限，默认 2，可设 0，超出的样本整条不装，列进 `omitted`，原因 `quote_cap`）；总量受包预算约束，知识分区不超过包的四分之一，超了按 Tier、`recurrent`、`labelConfidence` 截断。同一条样本不连续两集出现（`context-pack` 记 `.drama/packs/history.json`）。

**C5a 装标注，C5b 只装对话表引用过的正例**（`--exemplars`、`--contrast-pairs` 只给 `dialogue_designer` 与 `layer: C5b` 的 `author`）：

1. C5a 装包时对话表还没写：`context-pack … --role dialogue_designer --exemplars <标注交换文件> --annotations-only`。标注交换文件是双跑标注一致、过了 `corpus filter` 的交换（见 [语料](corpus.md)）。包里只装标注字段（`exchangeId`、`templateId`、`episodeIndex`、`about`、`situation`、`walkthrough`、`skeleton`），原始台词行与遮蔽句都剥掉；不是 dry-run 时另写一份派生文件 `.drama/packs/annotations/<sha>.jsonl`。还没有对话表时给标注交换却不加 `--annotations-only`，退出码 1；`--annotations-only` 也不能和 `--contrast-pairs` 一起用。
2. C5a 选定样本后，由模型把每条的遮蔽句写进对话表各话题的 `exemplars.positives[]`：每条写 `situationKey`（或 `situation`）、`walkthrough`、`skeleton`、`maskedLines`，不带原始台词行。
3. C5b 装包时 `--exemplars` 直接给本集对话表 `planning/dialogue/dialogue-plan-<NNN>.json`，从里面装这些正例。样本带原始行或缺 `maskedLines` 时退出码 1。

跨题材样本只给处境、说明和骨架，不给原句。

**样本来源** `source ∈ corpus／human／project`：语料（只遮蔽、永不逐字）；`human` 是本剧编剧写的句子，可以逐字用，正文对照表里那一行标 `verbatimFrom: <noteId>`；`project` 是本剧人工定稿里同处境的段落，语料对这种处境为空时可用。逐字用的人工句在校验时单列，不算「问题不在了」的证据。

**没有语料时**（新项目在本地语料建好之前都是这样）：C5a 照常进行，样本是可选输入；`exemplars` 留空，话题标 `no_exemplar`，交接 `unknowns` 记「本次无样本」。

## 5. 写正文（C5b）：照表写，信息由对白承载，重复须有处境理由

**作者包**（`context-pack --role author`，任务 `layer: C5b`）：本集分集计划 `planning/episodes/episode-plan-<NNN>.json`（`season-check` 的 `author-plan` 要求它在包里）、本集对话表（须过 `contract-check dialogue-plan`，否则退出码 2）、台词目标、对话表引用过的正例、本剧题材的禁词表、入口状态记录、前一集已保存的正文原文。只装本集分集计划；后一集要埋的东西经底账与本集计划的 `ledgerDelta` 进来。第 1 集的入口见 [整季分批](workstations/season-run.md)（开播前底账加 `--at 0 --track actual --md` 导出的 `after-ep-000.md`）。除此之外不装别的设计材料，不装对照对，不装新样本。

**写法**（M）：

- 按对话表逐话题写台词与动作行；一个话题讲完再换下一个，一个人聊完才换对象，切换前有收尾那一句或那一个动作。
- **信息由对白承载。** 对话表分给某个来回的 fact，就在那个来回的对白里说出来；只放在 △ 行或画面里的，必须是对话表登记了 `pictureReason` 的。
- **谁知道什么由 `listenerKnows` 定。** 对方已知的事不再交代；替观众发问必须有一方真不知道。说话人只说他此刻知道的事。
- **重复须有处境理由。** 同一条信息第二次出口，要有确认、强调、对方没听进去这类处境上的理由；没有就删。
- 话的长短照 `shape` 与 `reason`：发火的人一截一截，撒谎的人话多且绕，怕的人短，交代程序的人说全。
- 篇幅装不下时不压台词：写 `changeProposal` 回 C4（拆集或挪事件），带默认，流程按默认继续。
- 与对话表不一致的地方逐条登记，不悄悄改话题或信息分配。

**一起交出的**：

- 对照表（schema `plan-text-map`，放 `runs/<批>/ep-<NNN>.plan-text-map.json`）：`text`（正文路径）、`dialoguePlan`、`exchangeToLines`（每个交换落在正文哪几行）、`lineToPlan[]`（每行一条：`line`、`text`、`kind`（`title`／`scene`／`cast`／`action`／`dialogue`／`other` 六值之一，`contract-check` 核）、`exchangeId`（场头、动作行等不属于任何交换的写 `null`）、`speaker`、`carries`，收尾行标 `closerOf: <segmentId>`，逐字用的人工句标 `verbatimFrom`）、`verbatimFrom[]`（逐字句的汇总：`{line, from}`）、`deviations[]`（与对话表不一致处）。`contract-check plan-text-map <对照表>` 核两条（S）：`exchangeToLines` 指到的每一行，在 `lineToPlan` 里都标了同一个 `exchangeId`；行上标了 `verbatimFrom` 的，汇总里也要有。
- 交接 `run-handoff` 里的 `stateChangeProposals[].ledgerDelta`：正文实际写成的状态变化，进底账实际轨（`planning/ledger/delta-ep<NNN>.actual.json`）。

**写完就跑的客观检查**（结果存 `.drama/checks/`）：

- 字面重合两档：`dup-check --new <正文> --list-hits --k 13 --source-corpus-jsonl <exchanges.jsonl>`（全库，命中必改）；`dup-check --new <正文> --list-hits --k 8 --source-dialogue-plan <对话表> --exclude-verbatim <对照表>`（本次装过的样本，命中必改；逐字用的人工句单列）。带 `--list-hits` 时不要求 `--source`。两档记录都要在（`season-check` 的 `dup-two-tier`）。项目没有语料时（台词目标 `corpusManifest: null`），13 字全库档由 `season-check` 按台词目标自动判 `not_evaluable`（原因「本项目无语料」），不算失败，作者不用另写记录；8 字档只在对话表引用了语料正例时才要。
- 题材禁词：`corpus lexicon <正文> --project-genre <本剧题材>`（写法与禁词表的 `fromGenre` 同一套，如「现实」「仙侠／古装玄幻」；与本剧题材相同的那张表自动跳过），命中报 `GENRE_LEAK`，是事实核对。禁词表要进 C5b 包时，选材写 `{"kind": "local_file", "id": "lexicon:genre-lexicon@v1"}`，`context-pack` 从随包数据按 id 读，不必复制进项目。
- 口播量与估时（按需）：`episode-check <正文> --speech`；`capacity text <正文>`（两口径并报，不判定，超了写容量提案）。

过了这几项就把这一稿存为页面修订（[工位流程](writing.md#工位流程)第 8 步），C6 读的是这份修订。

## 6. 冷读复述与处境对照（对话问题单）

**冷读复述**（取代原台词读）。新上下文，`--role cold_reader`，包里只许一项本集正文，不装前集、集纲、作者说明、样本（S，否则退出码 2）。任务是复述，不是审：这一集发生了什么；逐条写谁做了什么、为什么；每条关键信息「我是从第几行的哪句话知道的」，说不出来写「不明」；列出「我不知道为什么会这样」的地方。提示词随包、带版本：标明这是连续剧第 N 集、前集交代过的不列进「不明」；△ 行是画面、约两秒，另估只看成片能不能拿到。记成 `retell-record`：`target.kind: episode_text`、`readingScope`（只一项）、`promptVersion`、`events[]`、`onlyFromPicture[]`、`unclear[]`、`stopsAt`、`factRefs[]`。`events[]` 每条可带 `sourceLine: {line, quote}`（从哪一行知道的）与 `sourceKind`（`dialogue`、`action` 或 `heading`）；人物表、场头里的信息也算正文来源，记 `sourceKind: heading`。

`retell-check <复述> --plan <对话表> --episode-plan <分集计划>` 对照每个 fact 给出 `retold／partial／missing`，恒为退出码 0。`missing` 的 fact：对话表没给它分配来回的回 C5a；分配了、正文没写出来的回 C5b。提示词版本不同的两次冷读不直接比。

**处境对照**。新上下文，`--role situation_checker`。对正文里每个话题，拿这段正文、该话题的 `situation` 与 `shape.reason`、对话表引用的正例（带 `walkthrough`）与对照对（带 `whyNotHere`），按随包对话问题单 `schemas/data/dialogue-check-questions.json`（当前 v1，17 问，题干以数据文件为准）逐问作答：

| 组 | 问的是什么 |
| --- | --- |
| A 想要与回应（1–3） | 想要的东西要了没有；对方答到点上没有；话题结束时拿到、被拒还是被打断 |
| B 话轮与收尾（4–7） | 收住了没有就换人换题；有没有人替对方把话说完；连说几件事时听的人会不会让他说完；问句没人答成不成立 |
| C 信息与省略（8–10） | 省掉的主语宾语补得出吗；观众从哪句对白知道；是不是交代了对方已知的事 |
| D 对象与说法（11–13） | 对孩子的说法；先接住情绪了没有；称呼口气与关系、权力方向对不对 |
| E 情绪在句子形状里（14–15） | 正文的话是不是那种情绪的人说得出的形状；更像正例还是反例，哪一处像 |
| F 知情与重复（16–17） | 说话人凭什么知道（为问而问并在这里）；这条信息第几次出口、重说有没有处境理由 |

判了三态（`holds／notHolds／not_evaluable`）的答必须引用句子：`quoteRef: {line, quote}`；可以同时写 `landsOn`（落到话题或交换）；答 `n/a` 不必引句，也不计入 `outcome`（比如没有样本时第 15 问写 `n/a`）。一份记录只核一个话题时 `target.kind` 可写 `topic`。原因回到处境；不打分、不合成总评。不成立项的 `defectKind` 取对话问题单数据文件里的 `defectKinds` 词表，词表外的只报。项目可以增问（带来源），不能删问。记录带 `questionsVersion`、`promptVersion`，放 `.drama/checks/`，用 `check-answers` 核格式（S）。同一稿做两次独立作答时，`answers-consistency <甲> <乙>` 的输出也存进 `.drama/checks/`（`season-check` 的 `consistency-record`），答得不稳的问题标出来，仍问。

「不成立」的项回到对应话题，先看是处境写错了（改表）还是没照表写（改文），见 §8；不自动拦截存稿。

## 7. 设计依据一致性与诊断信号（数字只诊断不裁判）

**一致性**：正文每个话题的走法，是否对得上对话表写的处境与理由。

- 脚本部分（S）：`plan-text-consistency <对照表> --dialogue-plan <对话表> --episode-plan <分集计划>`。`speaker-sequence`：每个交换的说话人与正文对应行一致；`topic-boundary`：每段恰有一行 `closerOf`，且按段的顺序靠后；这两条不过退出码 2。`interrupted-by`（打断位置）与 `carries-keywords`（承载行缺了 fact 的哪些关键词，只是「同义改写候选」）只报。另列 `verbatimFrom` 行。
- 模型部分（M）：逐话题读 `shape` 与 `reason`，再读正文，答「一致／不一致＋哪里不一致」（「表写老陈追问两次，正文他一次没追问」）。不评理由本身对不对，那是处境对照的事。

不一致的话题进修订单。

**诊断信号**：`dialogue-diagnose <正文> --dialogue-plan <对话表> --episode-plan <分集计划> --plan-text-map <对照表>` 输出信号、位置、所在话题与处境，恒为退出码 0：

| 信号 | 提示去看什么 |
| --- | --- |
| `ONE_BREATH` | 一个人连说几件事、中间没人接：这个处境里对方会不会让他说完 |
| `ADDRESSEE_JUMP` | 对象切换前没有收尾：和前一个人的话题收住了没有 |
| `IMPERATIVE_CHAIN` | 一串没人应的短宣告：是险情口令，还是对人说话却没人接 |
| `INFO_IN_ACTION_ONLY` | 信息只在 △ 行：只听对白能不能拿到 |
| `QUESTION_UNANSWERED` | 问句后没人接：怕、躲、被打断都可能成立 |
| `MONOLOGUE_FALLBACK` | 信息靠独白承载而对话表没有独白理由：这条信息有没有对话对象 |
| `INFO_REPEATED` | 同一条信息又出口一次：重说有没有处境理由 |
| `ONE_ITEM_PER_LINE_MISMATCH` | 标了一行一件事的来回里，一行塞了几个动作 |
| `UNCHANGED_ACROSS_REVISIONS` | 给 `--compare-with` 另几版时：同一场的换人修订前后没变，修订碰到结构了没有 |
| `OBJECT_MISSING` | 要冷读复述才能判，本命令永远记 `notEvaluable` |

每条信号带 `signalQuality`：`structural`（按行、说话人、对话表结构数出来的）或 `low`（关键词、标点估出来的）。缺输入的信号整条记 `notEvaluable`。信号只说去看哪一段，不出结论，不与任何区间比，不进验收；把一个数和语料比后说「偏离」，或写进验收，都是错用。

## 8. 修订：先改表再改文；修订单不写替换文字、不写数值；修订后复读

**修订对象是对话表与正文，不是句子清单。** 修订单（schema `revision-list`，放 `.drama/checks/`；和对已有全稿改稿时的改稿单不是同一件东西，但两者都受 `fixlist-no-lines` 同一条规则核）：`target`（集与正文）、`basis[]`（依据的冷读、处境对照等记录）、`items[]`（每项 `id`、`layer: C5a｜C5b`、`where`、`cites`（`functionId`、`ledgerId`、`targetClause`、`factEvidence` 之一）、`problem`、`action`）。它只引用对话表元素（`topicId`、`exchangeId`、`factId`）、约定条目与审读记录里的引用句和原因。写好先跑 `contract-check revision-list <修订单>`，再装修订包：

- 是处境或理由写错了：先出对话表新修订，再按新表改正文。
- 是正文没照表写：只改正文。
- 修订单**不写替换台词，也不写数值指令**：含「人物：台词」格式行或「少 40 字」这类指令的，`contract-check revision-list` 退出码 2（S）。定位字段（`id`、`where`、`cites`、`layer`、`target`、`basis`、`ref`）不扫；「本轮不改：…」「原因：…」这类标签行不算台词。收尾时 `season-check` 的 `fixlist-no-lines` 按同一规则再核一遍：它先按本集人物名单（对话表的说话人或对照表的 `speaker`）认台词行，只有「人物名：」开头的才算；没有名单时退回启发式，「照表」「按表」这类写法算标签不算台词。
- 任务也**不写数值指令**：「少 40 字」「不超过 3 行」「加一次换人」这类，`contract-check task` 按随包 `constraint-blocklist.json` 拒绝，不论来源（S）。编排方约束要标来源，`orchestrator` 来源须引用台词目标条款（`season-check` 的 `constraint-origin`）。

**预算**：修订预算（`task.revisionBudget`）在 C5a 算对话表修订次数，在 C5b 算正文修订次数，默认都是 1；用完之后的处理（写进交接 `unfinished`、`status.goal` 记 `partially_met`、用 `decision add --entry` 带默认登记进决定队列、选了「再改一次」怎么另开运行）只写在 [修订预算按运行层解释](workstations/README.md#修订预算按运行层解释)。不在预算外悄悄再改。

**修订后必做**：修订稿存为新的页面修订，再做一次冷读复述与处境对照，记录在才算修订完成（`season-check` 的 `retell-after-revise`：冷读之后又改了正文而没有再冷读，即失败，S）。

**超出本层的问题**：C5b 发现是对话表的问题，属于同一工位内的上游：写进交接 `unfinished`，用 `decision add planning/decisions.json --entry <条目>` 登记 `kind: upstream_change`、带默认，由编排方开一次 C5a 运行。属于分集计划或季编排的（信息没有对象、装不下、事件要挪）是跨工位的：写进交接的 `changeProposals`（`targetLayer: C4` 或 `C3`，带默认；交接只认 C1–C6，是 C3c 的写在提案正文里；对话表自带的 `changeProposals` 另是一个对象，那里写 `C4` 或 `C3c`），用 `decision add planning/decisions.json --from-handoff <交接>` 登记。流程都按默认继续，不在正文里悄悄改上游。

**`preserved`（不许动）只认人工来源**：每项写成 `{item, noteId}`（引人工批注）或 `{item, humanWords}`（人的原话）。模型审读认为的「亮点」写进记录，不进不许动清单。启用了台词层的项目由 `season-check` 的 `preserved-human-source` 核（S），已有审读记录里的 `preserved` 也一并按新规则核，这是有意的：启用台词层后，把旧记录的 `preserved` 迁成 `{item, noteId}` 或 `{item, humanWords}`，查不到人工来源的挪进 `goalAssessments[].evidence`。没有启用台词层的旧项目，纯字符串写法照旧放行。各读怎么记、迁移的细节见 [C6](workstations/c6-review.md)。

## 9. 人工反馈的吸收（`writer-note`、`verbatimFrom`、`preserved` 只认人工来源）

流程里没有任何一步等人。用户、编剧、顾问、导演任何时候给的批注、改稿、一句有记录的话，由 `feedback-ingest` 回流，下一次装包就用：

```text
feedback-ingest <输入> [--text <被批正文>] [--plan-text-map <对照表>] [--author <作者>] [--author-role user|writer|advisor] [--user-name <名字>] [--section <节标题>]
                [--out <空目录>] [--target planning/dialogue-target.json]
feedback-ingest --purge <noteId> --out <目录>
```

`--text` 给批注所指的那一版正文：从批注针对的页面修订读回的文本（飞书等交付副本只是拿批注的地方，不作 `--text`）。

**输入**可以是：飞书评论导出 JSON；改稿 md（配 `--original <原稿>`，逐行比对对白）；原话记录 md／txt；用 `### ` 分节的批注记录（每节一条，`>` 行是被批原文，「人名：台词」行算改法）；md 里的一张修改对照表（`--section <标题开头>` 只读那一节，表格每行一条，「原 → 改」两列加「类别」列）；追问单的回答记录（落在程序或现实规则上的 `notHolds` 各成一条程序或事实类意见）。

它把每条意见记成 `writer-note`（`noteId`、作者、日期、来源、集与场、`quotedText` 被批原句逐字、`humanSuggestion` 给的改法逐字、`humanNote` 批注原文、`level`、`attachesTo`、`conflictsWith[]`）。不给 `--out` 时只列派生物清单、不写文件；给 `--out <空目录>` 时按 `level` 全路由，派生物写进这个目录：

- 句级、来回级、话题级、场结构、信息承载 → 反例（`negatives.jsonl`）；带改法的句级 → 人工正例（`human-positives.jsonl`，`grade: human`，以后逐字用时标 `verbatimFrom: <noteId>`）；来回、话题级 → 对照对草稿（`contrast-pairs.jsonl`，补 `whyNotHere` 后放 `knowledge/contrast/`）。
- 信息承载、对象约定、独白，以及同类意见两次以上 → 约定草稿（`conventions.jsonl`）；同类两次以上且问题单覆盖不到 → 新问草稿（`questions.jsonl`）。
- 程序、事实 → 底账修订提案（`ledger-proposals.jsonl`）与 K1 卡草稿（`k1-drafts.jsonl`），交集纲层处理（[检索代理与 K1 卡](outline-layer.md#6-检索代理与-k1-卡可联网留出处脚本不联网)）。
- 决定 → 决定队列条目（`decisions.json`）。只有来源是用户本人时写 `status: decided`，带 `humanWords`（用户原话）与 `decidedBy`；编剧、顾问来源的写 `status: pending`、带默认，依据的原话记在 `basisWords`（`basisBy` 是谁说的，`basisRole` 是身份），不写 `humanWords`（写了 `contract-check` 会拒），等用户定。来源靠 `--author-role user|writer|advisor` 或 `--user-name <名字>`（可给多次）认；评论项自带 `authorRole` 时以它为准；认不出的算非用户。见 [决定队列](outline-layer.md#10-决定队列kind-词表default-必填decided-须-humanwords)。

每个派生物带 `fromNotes`（来源 note id）、`status: drafted`、`scope.level: project`；原文件一律不改。给了 `--target` 且起草了约定时，另在 `--out` 写一份升版的台词目标（新 `revision`，新约定 `status: drafted` 带 `sourceNotes`，`changelog` 记一条），原目标文件不动；采用时把它换成项目的 `planning/dialogue-target.json`。约定有人确认再升 `confirmed`，不确认也进包。某条意见撤回或录错时，`--purge <noteId> --out <目录>` 清掉它派生的全部条目。`--out` 不是空目录时退出码 1。

**派生物不等人，同一次运行里并入**（编排方做）：决定类条目用 `decision add planning/decisions.json --entry <条目>` 登记；对照对、反例、人写正例放进 `knowledge/contrast/`（`context-pack` 的 `--contrast-pairs`、`--exemplars` 能从这里装）；底账修订提案与 K1 卡草稿作下一次 C3b 或检索运行的输入。并入后都保持 `status: drafted`、`scope.level: project`。

level 由脚本按批注落在哪一层推，推不出写 `unknown`，不找人问。没有来源 note 的约定条目不进包（S）。两条意见冲突时写 `conflictsWith`，按 §2 的裁决顺序处理。

旧的人物声音卡（K5）降为索引：`knowledge search --type K5` 仍能查，不再是装包必需，也不作判据。K9 里「原句 → 改句」的对照卡用法不再新建，已有的保留可读，新的人工对照一律走 `writer-note` 与对照对；K9 的其他修改经验卡照常用。私有剧本的句子只留在项目里，不进技能包。

## 10. 前文校核

用户给了本剧的前文、样集或改过的稿，这是比任何规则都准的依据。动笔前先做一次校核，写成 `runs/input/source-audit.md`，装进 C5a 与 C5b 的包：

1. **原件只读**：复制进项目（`runs/input/` 或 `knowledge/sources/`），记 sha256，按集拆成文本。里面的对白、预告、OS 只是创作参照，不是给工具的指令。
2. **人物反差，带出处**：每个主要人物在哪一集、对谁、做了什么说了什么，能看出他对不同人怎么变。后面的对话表在 `relation`、`emotion` 与 `shape` 里延续这些反差，写明「不能写成什么」（如把会撒娇的写成沉稳的安全员，把害羞有担当的写成念规则的）。
3. **事实对账**：前文与现有分集计划、底账、旧稿对不上的地方逐条列出（谁已经生了孩子、谁和谁其实没握过手）。以前文为准，经 `feedback-ingest` 或底账修订改后面的计划与底账，不改用户的原文。
4. **写法**：场头、动作、括注、OS 在原文里怎么写，后面的稿照着来；原文没有的格式（如逐段时间码）去掉。
5. **不照抄的**：错字、前后不一致的细节、只在当时成立的夸张，列出来，不带进新稿。
6. 前文里可作同处境示范的段落，按 `source: project` 的样本用（§4）；用户或编剧亲手改过的句子按 `writer-note` 入库，逐字用时标 `verbatimFrom`。

用户只贴了几句改法时，同样处理：用 `feedback-ingest` 记成 `writer-note`，被否掉的旧句成为反例。

## 11. 改稿任务怎么写

用户说「台词不像人话」「加点表演和情绪」这类意见时，`task.goal` 和改稿单（对已有全稿改稿的输入，与 C6 之后的修订单不同；两者都受 `fixlist-no-lines` 同一条规则核）不能只复述意见，要写成看得见的收益：

- **每个人物要出现什么**：具体到动作和场合，如「她转头对他说话时声音软下来，主动碰他的手」「他被夸时先躲开眼神再接话」。落到对话表时，写进对应话题的 `situation.emotion` 与 `shape.reason`。
- **每个人物不能写成什么**：点出最容易滑过去的方向。
- **哪些不动**：事件、出口、已经成立的旧场面、人工 `preserved` 的句子；改掉旧稿里有效的动作时写明损失。
- **篇幅**：用户要的是片长时，用容量算术说话：`capacity text` 给出口播估时（两口径），超了写容量提案，不写「少多少字」「不超过几行」这类数值指令（会被拒）。写明估时口径和「未经演员实读校准」。

对已有全稿做这种改稿，入口是固定的，可以一批一个作者运行、几批并行，合稿时对账。关口用 `season-check --revise`，同一项目改过几版时加 `--since <本版开始的时间>` 只看这一版的运行。

## 12. 命令速查

命令都用 `python3 -B scripts/drama_tools.py <命令>` 运行（路径相对于技能目录），`--help` 看全部参数。输出是 JSON；**读结构化字段，不要只看退出码**。退出码约定见 [SKILL.md 随包工具](../SKILL.md#随包工具)：`0` 是执行完成（`capacity`、`retell-check`、`dialogue-diagnose`、`corpus lexicon` 恒为 0，不代表规则成立）。

| 步 | 命令 | 退出码怎么读 |
| --- | --- | --- |
| 场前已知 | `ledger knows <入口底账修订> --episode-plan <分集计划> > .drama/checks/knows-ep<NNN>.json` | 0；`listenerKnows` 的初值 |
| C5a 装包 | `context-pack <项目> --task … --selection … --role dialogue_designer --budget … [--exemplars <标注交换文件> --annotations-only] [--studio-corpus <工作室根>/corpus/]` | 2 分集计划容量不是 `fits` 或带默认的提案、超预算等；`--annotations-only` 只装标注字段 |
| C5a 核对话表 | `dialogue-plan-check <对话表> --episode-plan <分集计划> --knows <knows 文件> [--decisions planning/decisions.json]` | 2 信息没分配、段没有收尾、说话人不知情、有配额字段等；`listener-knows` 只报 |
| 对象格式 | `contract-check dialogue-plan <对话表>`；`contract-check task <任务>` | 2 违反 schema；任务里有数值型台词约束或「不动集数」类约束 |
| C5b 装包 | `context-pack … --role author --budget … [--exemplars planning/dialogue/dialogue-plan-<NNN>.json] [--quotes-per-topic 2]`（任务 `layer: C5b`） | 2 包里没有对话表或对话表不过 `contract-check`；1 样本带原始台词行或缺 `maskedLines`；超出遮蔽句上限的样本列进 `omitted`（`quote_cap`） |
| 字面重合 | `dup-check --new <正文> --list-hits --k 13 --source-corpus-jsonl <exchanges.jsonl>`；`dup-check --new <正文> --list-hits --k 8 --source-dialogue-plan <对话表> --exclude-verbatim <对照表>` | 看命中列表；有命中必改。没有语料时 13 字档由 `season-check` 自动判 `not_evaluable`，8 字档只在引用了语料正例时要 |
| 题材禁词 | `corpus lexicon <正文> --project-genre <题材>`；进包写 `lexicon:genre-lexicon@v1` | 命中报 `GENRE_LEAK`，只报 |
| 口播与估时 | `episode-check <正文> --speech`；`capacity text <正文> [--episode-plan <分集计划>] [--target-sec <秒>] [--media planning/media-profile.json]` | 都只统计；`capacity` 恒为 0。对照的目标秒数取：显式 `--target-sec` ＞ 分集计划的 `capacity.targetSec` ＞ 媒介档案默认值；给 `--episode-plan` 时与季编排、分集计划的估时可直接对照 |
| 冷读装包 | `context-pack … --role cold_reader …` | 2 包里不是恰好一项本集正文 |
| 冷读对照 | `retell-check <复述> --plan <对话表> --episode-plan <分集计划>` | 恒为 0；看每个 fact 的 `retold／partial／missing` |
| 处境对照装包 | `context-pack … --role situation_checker …` | 同其他装包 |
| 处境对照记录 | `check-answers <回答记录…>` | 2 格式错（判了三态却缺 `quoteRef`、缺原因、缺 `promptVersion`）；`n/a` 不要求引句；`defectKind` 在词表外只报 |
| 两次作答对齐 | `answers-consistency <甲> <乙>` | 只报 |
| 对照表与修订单 | `contract-check plan-text-map <对照表>`；`contract-check revision-list <修订单>` | 2 对照表行与交换对不上、`kind` 不在六值里或逐字句没进汇总；修订单含替换台词或数值指令 |
| 一致性 | `plan-text-consistency <对照表> --dialogue-plan <对话表> --episode-plan <分集计划> [--text <正文>]` | 2 说话人序列或话题边界不一致 |
| 诊断 | `dialogue-diagnose <正文> --dialogue-plan … --episode-plan … --plan-text-map … [--compare-with <另几版>]` | 恒为 0；只给信号与位置 |
| 上游变更与决定引用 | `decision add planning/decisions.json --from-handoff <交接>`；`contract-check run-handoff <交接> --decisions planning/decisions.json` | 2 缺默认；交接的 `decisionRefs[]` 指向不存在的决定 |
| 实际轨 | `ledger replay planning/ledger/ledger-ep000.json --delta planning/ledger --at <集> --track actual --md`；要入口底账修订文件时把 `--md` 换成 `--out planning/ledger/ledger-ep<NNN>.actual.json` | `--md` 输出就是下一集的 `runs/state/after-ep-<NNN>.md` |
| 人工反馈 | `feedback-ingest <文件> [--text …] [--plan-text-map …] [--author-role …｜--user-name …] [--section …] [--out <空目录>] [--target planning/dialogue-target.json]`；`feedback-ingest --purge <noteId> --out <目录>` | 0；不给 `--out` 只列清单，给了按 level 写派生物；1 输入错或 `--out` 不是空目录 |
| 关口 | `season-check <项目> --episodes <起-止>` | 启用台词层的项目核 `dialogue-plan`、`target-ref`、`plan-text-align`、`cold-retell`、`situation-check`、`consistency-record`、`retell-after-revise`、`constraint-origin`、`no-numeric-dialogue-constraint`、`fixlist-no-lines`、`dup-two-tier`、`genre-lexicon`，外加 `preserved-human-source`，输出 `episodeRuleSet: dialogue-layer` 与 `dialogueLayerRules`（各条 `passed／failed／not_evaluated`）；`--legacy-dialogue` 另跑旧三条（`voice-card`、`dialogue-pass`、`dialogue-read`）复查旧记录；`--batch-size` 是一次首读最多覆盖的集数（默认 10）；2 不通过，不能写「已按流程完成」 |

这些命令核的是记录在不在、字段与引用对不对、结构规则成不成立，不判台词好不好。可懂、处境上成立、与设计依据一致，三者都成立的对话仍可能平淡；首读判效果，人工反馈随时吸收。
