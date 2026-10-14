# D6-0 对照报告：重开（D6-0 续）后的验收、对照与 schema 修正点

日期：2026-10-14。依据：[统一实施计划](../design/drama-studio-outline-dialogue-implementation-plan-2026-10-14.md) §4.1「D6-0 续」、§2.6、§2.8；[中期报告](d6-0-interim.md)（第一轮停在任务 9 的事实与成因，本报告不重复，只引用）。

本页只有编号与统计，不含项目的剧本句子、集纲原文、台词或人物设定细节；人物只用角色名或条目编号指代。产物在项目目录 `projects/qige-xiongdi/runs/pilot-v2/`（下文记作 `V/`，不随仓库分发）；上一轮第 6 集台词验证在 `runs/pilot-ep006/`（记作 `E/`）。

**复现约定。** 下文命令都在 `V/` 目录下运行（`cd projects/qige-xiongdi/runs/pilot-v2`），解释器为 Python 3.11 标准库，脚本是 `V/tools/` 下的临时脚本，不是技能脚本。收尾修正（第十节）的产物在 `V/r15/`；`bash r15/rerun-all.sh` 一次重跑 27 条命令（清单在 `r15/reproduce-commands.json` 的 `current`，结果汇总在 `r15/rerun-all.json`：26 条 ok，唯一不 ok 的是全账不带范围的描述性运行）。第一节每行写的命令都在 2026-10-14 收尾之后对现行文件重跑过；标「报告方补跑」的是 `rerun-all.sh` 没有覆盖、由写报告的核对代理另跑的。

## 结论

- 第一版报告（收尾修正之前）的判定是：S 项 33 条，满足 26、部分 6、不满足 1。主创要求补齐后复核。补齐之后逐条重判，**33 条全部满足**（第一节）；补的是什么、补的过程中查出的工具 bug、还没定的事，写在第十节。
- 按 §4.1，退出条件是 S 项全过，且对照报告写明「哪些 schema 要改」（第九节）。**两条都已满足。**几处需要读报告的人知道的保留，各在对应行写明：事实级行号是事后由核对代理补的，不是冷读者自填；第 93 行的复读是单人定向复读；退役条目里有一条靠「定口径」而不是决定队列说明去处；存档的三集计划轨底账仍建在旧版底账上，换到新版底账链上才全过。
- 范围是实施计划给的默认：只收敛第 1–12 集用到的前提与功能（23 个功能；其余 26 个标「未重核」），台词层只做了新第 6 集的前一半（6A）。**这不是「四条线已收敛」。**

## 一、验收逐项（S 项；M 项只写记录位置）

### 1.1 功能地图

| # | 验收项 | 判定 | 证据与复现 |
| --- | --- | --- | --- |
| F1 | 范围内每个功能有 `selected` 实现或已登记保留 | 满足 | 23 个 `selected`，`functionsDropped` 0。`rerun-all` 02：`python3 -B tools/check_function_map.py r15/function-map-v1.2.json --stage v1 --rc-dir r5rc --rc-extra-dir r5rc/r2 --decisions r6/decisions.v1.1.json --ledger r6/ledger-ep000.v1.1.json --scope r1/scope-ep001-012.json --records-base .` → `ok: true`，exit 0。把 `--decisions`、`--ledger` 换成 `r15/decisions-merged.v2.json`、`r15/ledger-ep000.v1.2.json` 同样过（报告方补跑） |
| F2 | 承重 `notHolds` 都带 `disposition`，引用对象存在且状态相符 | 满足 | 同上命令：`loadBearingNotHoldsChecked` 21、`MissingDisposition` 0 |
| F3 | 没有 `losesFunctions[]` 非空而被标 `selected` 的候选 | 满足 | 同上命令（脚本 `--stage v1` 规则 1） |
| F4 | `closes[]` 每一项有核对记录引用 | 满足（收尾前：部分） | `r15/function-map-v1.2.json` 的选定候选补了 `closes[]`：14 个候选共 45 项，每项 `{defectId, confirmedBy: "文件#record"}`；另 9 个候选没有关掉的缺口。同上命令现在逐项回到 `closes-confirm` 记录核 `verdict == confirmed`。报告方做了一次破坏测试：把一项改指向一条 `still_there` 的记录，脚本 exit 2 并点名那一项 |
| F5 | 被否定的候选有 `rejectedBecause` | 满足 | 同 F1 命令（`candidatesRejected` 23） |
| F6 | 范围外功能标「未重核」 | 满足 | 同 F1 命令：`functionsOutOfScope` 26，每个带 `outOfScope: true` 与说明 |

### 1.2 前提

| # | 验收项 | 判定 | 证据与复现 |
| --- | --- | --- | --- |
| P1 | 每个前提问题有默认与决定队列条目 | 满足 | `r2/premises-v4.json` 六个问题各有 `default`；`r6/decisions.v1.1.json` 中 `kind: premise` 6 条。`python3 -B tools/decision_queue.py check r6/decisions.v1.1.json` → `ok: true` |
| P2 | 跨前提一致性表无空格 | 满足 | `r2/premises-v4.json` 的 `consistency`（时间线、钱表、谁知道什么三张表）叶子格 396 个、空格 0（报告方补跑：`python3 -c "import json;c=json.load(open('r2/premises-v4.json'))['consistency'];f=lambda o:[x for v in (o.values() if isinstance(o,dict) else o) for x in f(v)] if isinstance(o,(dict,list)) else [o];v=f(c);print(len(v),sum(x in (None,'') for x in v))"`）。没有正式脚本；「无空格」不等于「无冲突」，v3 那一轮核对方在同类表里找出过 7 处跨前提相顶（`r4/r4-summary.json` `crossPremiseConflicts`） |
| P3 | 功能地图勘误清零 | 满足（收尾前：部分） | `rerun-all` 23：`python3 -B tools/maperrata_count.py r5/fm-v1-scope.json r5/fm-v1-scope.r2.json --rc-dir r5rc` → `mapErrataTotal` 16、`mapErrataAppliedInR2` 16、`NotChangedInR2` 0、`NotParsed` 0（`r15/maperrata-count.json`）。脚本只核「登记的勘误在下一版里改没改」，不核「改得对不对」；后者仍是 M，增量核对是同一上下文做的（`r5rc/r2/r5rc-r2-summary.json` `checkedBy`） |

### 1.3 底账

| # | 验收项 | 判定 | 证据与复现 |
| --- | --- | --- | --- |
| L1 | 范围内依赖的条目齐 | 满足 | `rerun-all` 01：`python3 -B tools/ledger.py check r15/ledger-ep000.v1.2.json --cards knowledge/cards --function-map r15/function-map-v1.2.json --scope r1/scope-ep001-012.json --decisions r15/decisions-merged.v2.json` → `ok: true`，`refs-exist` pass。v1.1 底账用原参数仍过 |
| L2 | 默认阶段 `contested` 为零 | 满足 | 同上命令 `contested-zero` pass（范围内 0）。`rerun-all` 01b 不带 `--scope` 跑全账，exit 2：范围外 `contested` 10 条、`money-closed` 8 条，只作描述，不计入判定 |
| L3 | `unverified` 清单与戏剧假定清单存在并注明依赖的集 | 满足 | `r6/unverified-list.v1.1.json` 46 条（程序 45、钱 1），全部带 `dependents[].episodes`；`r6/license-list.v1.1.json` 6 条，范围内 5 条带依赖集，范围外的 LP-C4 无依赖记录 |
| L4 | `accepted_license` 的条目都有 `humanWords` | 满足（空集） | 底账里 `accepted_license` 0 条，`license_pending` 5 条；同 L1 命令 `license-has-words` pass |
| L5 | §10.2 规则对 `ledger@ep000` 与三集 planned delta 全过 | 满足（附一处保留） | ep000：同 L1。三集 planned delta 由报告方补跑（`rerun-all.sh` 没有这一条）。先在新版底账链上逐段过：`python3 -B tools/ledger.py check r15/ledger-ep000.v1.2.json --scope r1/scope-ep001-012.json --cards knowledge/cards --function-map r15/function-map-v1.2.json --decisions r15/decisions-merged.v2.json --delta r8/ledger-005.planned-delta.json`。另两段先 `ledger.py apply r15/ledger-ep000.v1.2.json --delta r8/ledger-005.planned-delta.json --out <p5>`，再 `apply <p5> --delta r8/ledger-006A.planned-delta.json --out <p6A>`，然后对 `<p5>`＋006A delta、`<p6A>`＋006B delta 用同样参数各跑一次 `check`。三次都 `ok: true`。**保留**：存档的 `r8/ledger-ep005.planned.json`、`r8/ledger-ep006A.planned.json` 仍建在 v1.1 底账上，拿它们当底再跑会 exit 2；挂的是新规则 `retired-user-given-justified`，原因是 v1.1 里 L-obj-acc-013 没有退役去处。另外，三个 `--delta` 一次传入时脚本仍会崩（整数集号与字符串集号比大小） |

### 1.4 季编排与分集计划

| # | 验收项 | 判定 | 证据与复现 |
| --- | --- | --- | --- |
| S1 | 受影响的集每集有 `capacity` 记录 | 满足 | `rerun-all` 04：`python3 -B tools/check_season_plan.py r7/season-plan-v0.json --function-map r6/function-map-v1.1.json --media ../pilot-ep006/media-profile-v0.json --corpus ../pilot-ep006/corpus/exchanges.jsonl --decisions r7/decisions-r7.json --decisions r6/decisions.v1.1.json` → `ok: true`，`items` 空 |
| S2 | 超出的有 `action`，没有「待定」 | 满足 | 同上。12 集里 7 集超出：拆 4（第 6、9、10、12 集）、重排 3（第 1、7、8 集），第 1–12 集成 16 集。第 1 集动作后口径甲 121.0 秒，比目标多约 1 秒，脚本不报 |
| S3 | 没有系统默认选的删线 | 满足 | `drop_function` 0；季编排的 5 条决定（DQ-S0–S4）默认都是 `add-4`／`split`，带 `losesFunctions` 的只出现在非默认选项里 |
| E1 | 三集 `plan-check` 全过 | 满足 | `python3 -B tools/plan_check.py r8/episode-plan-005.json --ledger r6/ledger-ep000.v1.1.json --season r7/season-plan-v0.json --function-map r6/function-map-v1.1.json --decisions r8/decisions-merged.json`；6A 用 `--ledger r8/ledger-ep005.planned.json`，6B 用 `--ledger r8/ledger-ep006A.planned.json`。`rerun-all` 03 只含 6A；005、6B 由报告方补跑，三次 exit 0，14 条规则 12 pass、2 report。分集计划在收尾时重生成过（补按拍时点），以上是对重生成后的文件跑的 |
| E2 | 冷读只读 `events`，`facts` 与 `closingEvent` 的 `missing` 为零 | 满足 | `rerun-all` 06、07：`python3 -B tools/retell_check.py r15/retell-plan-005.json --plan r8/episode-plan-005.json`（006A 同）；6B 由报告方补跑（换 `r15/retell-plan-006B.json`、`r8/episode-plan-006B.json`）。missing 0／0／0；按事实判（C1）也是 0。6B 的 `closingEvent` 脚本判 partial（关键词零命中），读者复述的停点就是该拍（schema 修正点 #82） |

### 1.5 对话表与正文（第 6A 集）

| # | 验收项 | 判定 | 证据与复现 |
| --- | --- | --- | --- |
| D1 | 每个 fact 有承载句或画面理由 | 满足 | `python3 -B tools/check_dialogue_plan.py r11/dialogue-plan-ep006A-v2.1.json --episode-plan r8/episode-plan-006A.json --knows r8/knows-ep006A.json` → `ok: true`，`info-ledger` pass（v2 同样过）。9 个 fact：对白承载 8（其中 3 个另有画面）、只靠画面 1 |
| D2 | 每个 `segment` 有 `closer` | 满足 | 同上 `topics-segments` pass（6 话题、12 段、37 个交换） |
| D3 | `listenerKnows` 与知识账无矛盾 | 满足 | 同上 `listener-knows` report、无条目（`rerun-all` 05，对收尾后重导的 `r8/knows-ep006A.json`；`speaker-knows` 的 8 条豁免现在都走 `withinScene` 按拍那一路，收尾前是同场退回那一路）。注意：v2 的初值是对着旧导出写的，脚本没报，是两位问题单核对者都指出后才在 v2.1 重写（RV-4） |
| D4 | 对齐无未登记偏离 | 满足 | `python3 -B tools/plan_text_consistency.py r12/plan-text-map-ep006A-v2.json --dialogue-plan r11/dialogue-plan-ep006A-v2.json --episode-plan r8/episode-plan-006A.json` → `ok: true`（g2 用 `r12/plan-text-map-ep006A-v2.g2.json` 与 v2.1，同样过）；37 个交换全部落到正文、顺序一致；偏离 5 处都已登记 |
| D5 | 两档 `dup-check` 零命中 | 满足 | `python3 -B tools/dup_check_hits.py r12/ep-006A.g1.md --k 8 --source-dialogue-plan r11/dialogue-plan-ep006A-v2.json --exclude-verbatim r12/plan-text-map-ep006A-v2.json`；13 字档换成 `--k 13 --source-corpus-jsonl ../pilot-ep006/corpus/exchanges.jsonl`。g1、g2 四次命中 0。8 字档的来源只有装包样本遮蔽句共 76 个汉字 |
| D6 | 禁词零命中 | 满足 | `python3 -B tools/genre_lexicon_scan.py r12/ep-006A.g1.md --lexicon tools/genre_lexicon.json`（g2 同）命中 0。词表是人工列的候选（`assumed`），不是方案要求的跨题材词频对照算出来的 |
| D7 | C5a 若有退回，`changeProposal` 记录在且带默认 | 满足 | 对话表 v2.1 `changeProposals` 7 条全部有 `default`（D1 命令 `change-proposals` pass）；正文退回 `r12/change-proposals-c5b.json` 1 条，有 `default` |

### 1.6 冷读与问题单（S 记录在；内容 M）

| # | 验收项 | 判定 | 证据与复现 |
| --- | --- | --- | --- |
| C1 | 复述每条 fact 有行号 | 满足（收尾前：部分；附保留） | `r15/factrefs-retell-*.json` 六份（三份计划冷读、三份正文冷读）共 57 个 fact，每个都带 `retellRefs`（复述里的第几条事件）和 `lines`（正文行号；计划冷读是 `beatId`）。报告方补跑了引用存在性：57 条的行号都在正文行数以内或是存在的 `beatId`，`retellRefs` 都指向复述里存在的事件（Python 一段，逐份读 `source` 与 `lineBasis` 核对；`rerun-all.sh` 无此条，也没有正式脚本）。**保留**：这些对应是收尾时由核对代理事后补的，不是冷读者自填（schema 修正点 #82 要的是读者自填）。按事实判，合计 retold 54／partial 3／missing 0；关键词判定是 46／11／0，差异全部是关键词判得偏严（`r15/factrefs-summary.json`） |
| C2 | 17 问每问有引用与原因 | 满足 | `rerun-all` 10、11：`python3 -B tools/check_answers.py r15/check-ep006A-g1-a.json --questions questions/dialogue-check-questions-v1.json`（`-g1-b` 同）→ `ok: true`。两份分别 87、70 答，都覆盖 17 问，每答有 `quoteRef` 与 `reason` |
| C3 | 双跑一致性记录在 | 满足（收尾前：部分） | `rerun-all` 18：`python3 -B tools/consistency_check.py r13/check-ep006A-g1-a.json r13/check-ep006A-g1-b.json`，输出存为 `r15/consistency-g1-a-b.json`（报告方重跑与存档一致）。可比 58 处，一致 56、不一致 2；只有 a 答的落点 29 处，只有 b 答的 12 处。脚本只报不拦 |
| C4 | 「不成立」项已回修并复读 | 满足（收尾前：部分；附保留） | b 跑 2 条 `notHolds`。称呼那条（不承重）在 g2 改掉，复读成立（`r15/check-ep006A-g2-b-delta.json`）。第 93 行那条（承重）成因在 `ledger knows` 的导出：收尾时底账补了按拍的知情时点（`knownToSince`／`visibleToSince`），导出改为按部分、另列本场内才得知的部分（`withinScene`）。之后 b 只重判第 16 问三处（第 7、10、93 行），三处都成立（`r15/check-ep006A-g2-b-rv5.json`；`python3 -B tools/check_answers.py r15/check-ep006A-g2-b-rv5.json --questions questions/dialogue-check-questions-v1.json` → `ok: true`，报告方补跑）。**保留**：改动落在底账与导出，没有落在对话表——对话表按退回提案的默认，本来就把那一问写成真问；复读是单人定向复读；这份复读写于导出的最终版之前（`r8/knows-ep006A.v1.json` 之后还有三次重导，见第十节），核对者在记录里写明是直接按底账的按拍时点判的。最终导出给提问的人记的只有部分知情，与复读的前提一致 |
| C5 | 记录带 `promptVersion` | 满足（收尾前：不满足） | `r15/` 下 6 份冷读记录、4 份问题单记录都带 `promptVersion: {files: [{path, sha256}]}`。指向的提示词文件，修改时间都早于各自那次运行；报告方核对过，现行文件的哈希与记录一致。`check_answers.py` 缺版本即报错：拿原 `r13/check-ep006A-g1-a.json` 跑，exit 2，报「记录没有 promptVersion」。`retell_check.py` 缺版本只提示、不拦。版本是事后按文件哈希补记的，不是运行时写入的 |

### 1.7 设定核对报告、决定队列、对照报告

| # | 验收项 | 判定 | 证据与复现 |
| --- | --- | --- | --- |
| R1 | 每条 `user_given` 的不成立项都有默认 | 满足（收尾前：部分；附保留） | `rerun-all` 24：`python3 -B tools/decision_queue.py check r15/decisions-merged.v2.json` → `ok: true`，27 条。DQ-S0 的 `kind` 由 `season` 改为 `capacity`；旧的 `r8/decisions-merged.json` 仍报那一错，已被 v2 取代。底账 v1.2 给退役的用户给定条目补了去处：L-proc-001 补 `decisionRef: DQ-B2`（已有 `retiresInto`），L-obj-acc-013 补 `retiredBy: layer_choice`，L-tl-guard-002 原有 DQ-C4。新规则 `retired-user-given-justified` 在 L1 命令里 pass（`r15/build-r15-decisions-ledger-log.json` 记了这三处改动）。**保留**：L-obj-acc-013 的去处是「两层材料定口径」，不是决定队列条目——按集纲方案 §3.8，`layer_variant` 由系统内定，不进决定队列；`license_pending` 的范围内条目都挂了决定（`r6/license-list.v1.1.json`）。`setting-check-report` 本身没有按 v1.2 重生成 |
| O1 | 对照报告在 `docs/d6/`，不含私有句子；分开数 `closes`、`retiresWith`、`leavesOpen`，报两份清单的条数 | 满足 | 本页；数在第八节 |

### 1.8 M 项（不作通过条件，只写记录位置）

- 缺口承不承重的判断：各核对记录的 `loadBearing` 与 `loadBearingWhy`（`r4/RC-P3-*.json`、`r4b/RC-P4-*.json`、`r5rc/RC-B-*.json`、`r5rc/r2/RC-B2-F-gift-3.json`）；写作方与核对方判法不一时以核对方为准（schema 修正点 #72、#74）。
- 缺口是否真的消失：`r4/closes-confirm.json`、`r4b/closes-confirm.json`、`r5rc/closes-confirm.json`。
- 戏剧假定是否只豁免它自己那一处：`r4/license-audit.json`（v3：不合规 9）、`r4b/license-audit.json`、`r5rc/registrations-audit.json`、`r5rc/r2/registrations-audit-r2.json`（最终 license 6 条不合规 0）。

## 二、新第 6 集（6A）估时对目标

**口径先说清。** 季编排把旧第 6 集拆成 6A、6B 两集（拆后的新第 6、7 集），6A 自己的目标是 120 秒；它的内容约是旧第 6 集的前一半（物流仓、抽屉、漏气处置、消防确认，集末两名办事人员到门口），所以它对 120 秒是同口径，对旧第 6 集的 f1、e2 只能并排看、不能直接比。计划层与正文层各有「两口径」，**不是同一对量**：计划层的甲＝信息条数 × 语料交换中位时长＋画面拍，乙＝去掉画面承载的事实再算；正文层的 A＝口播汉字 ÷ 说话期间语速 ÷（1 − 停顿比），B＝口播汉字 ÷ 每集每分钟台词汉字。正文估时只算台词，不含△行的画面时间。

| 对象 | 内容范围 | 口播汉字 | 正文口径 A（秒） | 正文口径 B（秒） | 对 120 秒 |
| --- | --- | --- | --- | --- | --- |
| 6A g1 | 新第 6 集 | 538 | 142.6 | 155.0 | 1.19／1.29 倍 |
| 6A g2 | 同上（改 5 行） | 544 | 144.2 | 156.7 | 1.20／1.31 倍 |
| f1（上一轮） | 旧第 6 集全集，按旧集纲不拦截地写 | 2063 | 546.9 | 594.2 | 4.6／5.0 倍 |
| e2（编剧批注对象） | 旧第 6 集全集 | 490 | 129.9 | 141.1 | 1.08／1.18 倍 |
| 编剧第 5 集定稿 w1 | 第 5 集 | 588 | 155.9 | 169.4 | 1.30／1.41 倍 |

复现：`python3 -B tools/capacity.py text --media ../pilot-ep006/media-profile-v0.json r12/ep-006A.g1.md`（换成 `r12/ep-006A.g2.md`、`../pilot-ep006/ep-006.f1.md`、`../b01/ep-006.e2.md`、`../input/writer-ep-005.md`）；原输出 `r13/capacity-text-{g1,f1,e2,w1}.json`，g2 为 报告方补跑。

对计划的复核：6A 在季编排里估甲 101.4／乙 74.9 秒，分集计划复核甲 109.4／乙 76.9 秒（`r8/episode-plan-006A.json` `capacity`，`status: fits`）。g1 正文口径 A 是计划复核甲的 1.30 倍，超目标 19%；没到两倍，未触发容量提案（schema 修正点 #90）。编剧定稿第 1–5 集在同一计数下口径 A 为 108.2、89.1、136.3、153.5、155.9 秒（`r7/capacity-writer-text-ep001-005.json`），第 3–5 集同样超 120 秒；g1 落在编剧定稿第 3–5 集的范围内。季编排对这三集按条数粗估都判「未超」——按条数估数不到「同样的事实说了更多话」，g1 对计划的偏差与此同向（#78）。

两处计数差异照实写：上一轮 `E/capacity-ep006.md` 给 f1 计 2087 字、给编剧第 5 集计 543 字，本轮脚本计 2063、588 字，是两套行计数规则的差别，没有逐行对过；这影响各行的秒数，不改变量级。

## 三、冷读覆盖

| 读什么 | 读者 | 清单条数 | 关键词判 retold／partial／missing | 按事实判（收尾补） | 停点（`closingEvent`） | unclear |
| --- | --- | --- | --- | --- | --- | --- |
| 第 5 集分集计划 `events` | 1 | 12 | 9／3／0 | 10／2／0 | retold | 4 |
| 6A 分集计划 `events` | 1 | 9 | 8／1／0 | 9／0／0 | retold | 2 |
| 6B 分集计划 `events` | 1 | 9 | 9／0／0 | 9／0／0 | partial（关键词；停点是该拍） | 6 |
| 6A 正文 g1 | a | 9 | 7／2／0 | 9／0／0 | partial（同上） | 5 |
| 6A 正文 g1 | b | 9 | 7／2／0 | 9／0／0 | partial（同上） | 8 |
| 6A 正文 g2 | 1 | 9 | 6／3／0 | 8／1／0 | partial（同上） | 6 |
| 上一轮 f1 正文 | 1 | 19 | 19／0／0（核对者判 covered） | — | — | 18 |
| 上一轮 e2 正文 | 1 | 19 | 6／9／2（同上） | — | — | 18（另 1 条 e2 无此拍） |

来源：关键词判在 `r9/retell-check-plan-*.json`、`r13/retell-check-g1-{a,b}.json`、`r13/retell-check-g2.json`（对 `r15/` 下补了版本的记录重跑，计数不变）；按事实判在 `r15/factrefs-retell-*.json`，由收尾时的核对代理事后判、带行号，同义改写算 retold。两种判法的差异全部是关键词判得偏严：8 处关键词判 partial 的，按事实判为 retold；没有反方向的。g2 的 6A-I7 两种判法都判 partial，因为 g2 正文确实改了那个动作。上一轮见 `E/stage-d-report.md` §二（`E/retell-f1.json`、`E/retell-e2.json`）；上一轮见 `E/stage-d-report.md` §二（`E/retell-f1.json`、`E/retell-e2.json`）。正文 partial 的是 fact 6A-I7、6A-I9（g1 两位都是），g2 另加 6A-I5；计划冷读 partial 的是 6A-I5。6A-I7 的 partial 有一部分是关键词问题：g2 改了处置动作的写法之后，分集计划里那条 fact 的原文已与正文不符，要回 C4 改写（`r12/ledger-006A.actual-delta.g2.json` 对应条目的 `reason`）。两位冷读者都没拿到一处人物藏东西的动机，对话表把它登记为有意不交代（RV-6）：这是「有意悬置被冷读判为不明」的一例，脚本分不开两者。计划冷读里有一处 unclear 的原因写在 `moves[].whyNot`、不在 `events`（#83）。

**可比性的限度。** 两轮的信息清单不同：上一轮 19 条覆盖旧第 6 集全集，本轮 9 条只覆盖 6A。提示词不同：上一轮喂给冷读者的提示词原文没有保存，本轮按产出结构重写并改了字段名（#5）。判法不同：上一轮由核对者读复述逐条判 covered／partial／missing，本轮由脚本按关键词判，再人工旁注。读者不同：按编排方的说明，本轮冷读者用了两种模型，哪一位用哪种没有记在记录里。上一轮 f1 的 19 条全覆盖是在 9–10 分钟的篇幅上拿到的。所以这张表能说的只是「本轮三份计划、三份正文冷读都没有 missing」，不能说新流程比上一轮好或差多少。

## 四、问题单

**g1 双跑。** a 跑 87 答：成立 85、`not_evaluable` 2（第 16 问两处，说话人的依据在底账上没有条目）、不成立 0，结论 `pass_with_unverified`。b 跑 70 答：成立 67、不成立 2、`not_evaluable` 1，结论 `fail`。两跑落到同一（问号，行号）的 58 处里 56 处一致；只有 a 答的落点 29 处，只有 b 答的 12 处（`r15/consistency-g1-a-b.json`）。也就是说，两位核对者在「答哪些行」上的分歧比在「答案是否一致」上大。2 处答案分歧正是 b 的两条不成立：

| 处 | 问 | 承重 | b 的判法 | a 为什么判成立 | 根因 |
| --- | --- | --- | --- | --- | --- |
| g1 第 89 行 | 13 | 否 | 办事人员对店主的称呼与编剧 c4 改句的称呼相反 | 没有拿编剧改句对照 | 核对者是否引反例与对照对，提示词没有规定 |
| g1 第 93 行 | 16 | 是 | 照知识账，提问的人此刻已经知道答案，这一问成了为问而问 | 照正文：提问的人不在场，问是真问 | `ledger knows` 按场头导出，把本场才发生的事整条挂到在场者名下；时间线条目只有一个 `knownTo`，表达不了「知道结果、不知道是谁做的」（RV-5、CP-c5b-01） |

**g2 定向复读。** 只由 b 复读改动的 5 行及前后各两行，另重判第 93 行与消防确认那一句：27 答，成立 26、不成立 1。改动的 5 行全部成立；消防确认处置「每一步都对」在 g2 对卡成立（g1 里不成立，见下）；剩下的一条不成立仍是第 93 行，成因不变。

**收尾后的第 93 行（RV-5）。** 底账补了按拍的知情时点，导出改为按部分、并另列本场内才得知的部分。之后 b 只对第 16 问重判第 7、10、93 行，三处都成立（`r15/check-ep006A-g2-b-rv5.json`）：按新导出，提问的人到场时只知道结果，不知道是谁做的，这一问是真问；第 7、10 行的说话人，场前知道的部分也不含他说出的那件事。这份记录里第 1–15、17 问的 16 条回答只为满足「每问至少一条」的格式，内容沿用前两轮、没有重判（记录 `formatNotes` 自己写明）。g1-a、g1-b 里第 73 行第 16 问的 `not_evaluable`（说话人凭什么知道一个设施的位置，底账无出处，CP-01）不在本轮范围，仍然悬着。

**问题单没抓到的两处真错误。**

1. **物件状态与底账不符**（RV-1）：g1 第 44 行把一件拒收凭证上的退回原因写成了底账物件条目 L-obj-gb-003 里没有的说法。两位问题单核对者都没发现；编排方顺着冷读者 b 的一条 unclear 回查底账才发现。问题单 17 问没有一问对物件状态。
2. **人物示范的处置做法与现实相反**（RV-2）：g1 第 59、62、63 行，孩子在燃气泄漏处置里下的一条身体姿势指令属于火场防烟做法，不是燃气泄漏处置；而本集紧接着让消防员确认她每一步都对。核对者 b 在问题单范围之外记在 `formatNotes`，检索卡 `knowledge/cards/K1-ranqi-xielou-chuzhi@r1.json` 证实官方处置材料里没有这一项。问题单没有一问问「人物示范的做法有没有出处」。

两处都在 g2 改掉（`diff r12/ep-006A.g1.md r12/ep-006A.g2.md` 只有第 44、59、62、63、89 行）。对策见 schema 修正点 #88。

## 五、C5a／C5b 有没有退回

有，两层都退回过，全部带默认，流程按默认继续。写正文期间 C4 没有据此改分集计划。收尾时分集计划与计划轨 delta 重生成过一次，给 6A 补了按拍、按部分的知情时点，等于在计划轨上回应了 CP-c5b-01（提问的人在第 6A-4 场只知道结果，第 6A-5 场才知道是谁做的）与 CP-03 的一部分；其余提案的分集计划文字没有改。

| 来源 | 编号 | 退给 | 类别 | 默认（只描述） |
| --- | --- | --- | --- | --- |
| 对话表 | CP-01、CP-02 | C4 | 说话人在底账上不知道 | 照写，按场内所得写知情，不补前集知识 |
| 对话表 | CP-03 | C4 | 计划与底账的知识冲突 | 后到的人不对先走的人开口、不认出他 |
| 对话表 | CP-04 | C3b（`ledger knows` 导出） | 导出缺项 | 初值照导出；状态 `partly_resolved`：物件 `visibleTo`、时间线 `knownTo` 已并入，程序条目仍不在 |
| 对话表 | CP-05 | C4 | 凭职业规矩知道 | 照写，只说规矩不引条文 |
| 对话表 | CP-06 | C4／C5a（第 6B 集） | 承载交给下一集 | 本集按画面写 |
| 对话表 | CP-07（v2.1 新增） | C4 | 计划与正文的写法差 | 对话表按正文改形状说明，承载与编号不变，计划轨不动 |
| 正文 | CP-c5b-01 | C4 | 计划与底账的知识冲突 | 第 93 行写成真问，提问的人在被告知之前不说出是谁做的 |

回路记录：对话表 v2 → 问题单与冷读 → 修订清单 `r13/revision-list-g1.json`（RV-1–3 改正文出 g2，RV-4 改对话表出 v2.1 并重核，RV-5、RV-6 不改、进本报告）→ g2 定向复读 → 收尾：RV-5 改底账与导出，再定向复读（第四节）。正文退回的那一条与问题单第 93 行的分歧是同一处。RV-6 仍不改。

## 六、编剧 7 条批注在 g1／g2 对应位置是否仍在

批注文件 `runs/input/feedback/writer-feedback-ep006-2026-10-13.md` 针对的是旧第 6 集 e2。6A 的场面结构变了，旧第 6 集后一半的场面在 6B，6B 的正文没有写。依实施计划 §2.5 #12，逐字（或近乎逐字）照用编剧句子的行单列，不算「不在了」的证据。

| 批注 | 6A 有无对应位置 | g1 | g2 | 依据 |
| --- | --- | --- | --- | --- |
| c1 | 有（漏气处置里喝止按开关的一句，第 70 行） | 不在 | 不在 | 该行宾语与后果都在台词里；两跑问题单落到第 70 行的回答都成立。该行措辞取自分集计划示意句与编剧第 1 集定稿句，不是 c1（c1 没有给句子） |
| c2 | 有（交代烧什么的一段，第 33–37 行） | 不在 | 不在 | 要烧的东西由台词说出，对方逐项反问并说出不烧的理由；两跑问题单落到第 33 行的回答都成立 |
| c3 | 无对应位置 | — | — | 相应场面在 6B |
| c4 | 主体无对应位置；称呼这一子项有 | 称呼仍在（第 89 行，b 跑第 13 问不成立） | 已改 | 社区评估的一来一回在 6B；6A 只写到两人到门口（第 104–105 行）。g2 第 89 行的称呼照用了 c4 改句里的称呼，列入下面的照用清单 |
| c5 | 有（消防确认与敬礼，第 97–103 行） | 不在 | 不在 | 先夸、再敬礼、敬礼后不跳对象（他与店主的话放在前面，第 89–93 行）。但夸的那一句（第 100 行）几乎照用了批注里的说明文字，`plan-text-map` 没有登记为 `verbatimFrom`，列入照用清单；本条判定把握低 |
| c6 | 有（第 97 行） | 逐字照用 | 逐字照用 | `plan-text-map` 登记 `verbatimFrom: NEG-c6.humanExpected`。不计入「不在了」。g1 里这句对孩子处置的确认与前面的错误示范相顶，g2 改掉示范后成立 |
| c7 | 无对应位置 | — | — | 夜里取钥匙在 6B；6A 只有一行画面（第 48 行） |

照用清单：第 97 行（c6，逐字，已登记）；第 100 行（c5 说明文字，近乎逐字，未登记）；g2 第 89 行的称呼（c4，单词照用，未登记）。`verbatimFrom` 的其余条目（g1 11 处、g2 10 处）取自编剧第 1、5 集定稿或分集计划示意句（`r12/plan-text-map-ep006A-v2*.json`），不涉 7 条批注。

计数：可判的 3 条（c1、c2、c5）在 g1、g2 对应位置都不在，其中 c5 有一行近乎照用；c6 是逐字照用，不能作证据；c3、c7 与 c4 的主体在 6A 没有对应位置；c4 的称呼子项在 g1 仍在，靠问题单抓出后在 g2 改掉。上一轮 f1 的判定（6 处不在、c6 部分，其中 c3、c4 部分照用）见 `E/stage-d-report.md` §五。

## 七、两轨底账差异（第 6A 集）

| 比较 | 新增 | 改动（收尾前计划轨） | 改动（收尾后计划轨） | 删除 | 复现 |
| --- | --- | --- | --- | --- | --- |
| 计划轨 vs g1 实际轨 | 8（知识 6、物件 1、时间线 1） | 16（知识 8、物件 4、时间线 4） | 19（知识 9、物件 5、时间线 5） | 0 | 收尾前：`r13/ledger-diff-ep006A.json`。现行：`python3 -B tools/ledger.py diff r8/ledger-ep006A.planned.json r13/ledger-ep006A.actual.json`（报告方补跑） |
| 计划轨 vs g2 实际轨 | 8（同上） | 19（知识 11、物件 4、时间线 4） | 22（知识 12、物件 5、时间线 5） | 0 | 报告方补跑：`python3 -B tools/ledger.py apply r8/ledger-ep005.planned.json --delta r12/ledger-006A.actual-delta.g2.json --out <输出>`，再 `ledger.py diff r8/ledger-ep006A.planned.json <输出>` |

收尾后多出的 3 条改动（L-kn-r8-06A-30、L-obj-r6-002、L-tl-r8-005-01），以及另 3 条多出的差异字段，都只是按拍时点字段（`since` 的嵌套形态、`knownToSince`、`visibleToSince`）：计划轨在收尾时补了这些字段，实际轨的 delta 写在收尾之前，没有。内容上的差异仍是 g1 16 条、g2 19 条。实际轨也要补同样的时点字段，第十节列为未决。

实际轨 delta 写 52 条，与计划轨不同的 g1 23 条、g2 26 条（`r12/ledger-006A.actual-delta*.json` 的 `summary`）。按原因归类（g1 的 16 条改动与 8 条新增）：计划轨的幕后一拍正文不写，交接与地点只能从台词推（改 4）；按对话表默认，后到的人不认出先走的人（改 2）；知情的来源由「在场」改为「被告知」或「没看见」（改 3）；提问的人的知识按退回提案拆开（改 1、增 2）；比计划知道得多或说的先后不同（改 3）；一位人物出门的去处正文没交代（改 1）；物件状态细化（改 2、增 1）；对话表新加的交换带出的知情（增 4）；集末到门口一拍（增 1，`knownTo` 留空）。g2 另因处置动作改写多改 3 条知识条目。

影响下一集（6B 及以后）的几处：

1. 实际轨上，后到的人不知道柜台上那人是谁；后面任何以「他认出了」为前提的场面要先在正文里建立。
2. 店主到本集结束不知道漏气的起因；6B 里谁被怪、谁替谁说话要按这一条写。
3. 一位人物出门去做什么，实际轨上谁都不知道（计划轨写了去处）。
4. 新增的物件条目记了两道阀与接头的状态，供 6B 与后面报警器一节对照。
5. 6A-I7 那条 fact 的原文与 g2 的处置写法不符，C4 要改写；集末到门口的两人 `knownTo` 为空，6B 的入口状态要定谁看见了谁。

## 八、上游在新规则下的收敛情况

**承重缺口的去向。** 第一轮两轮前提在全剧范围内各 7/7 不成立（中期报告第一节），第三、四轮只对第 1–12 集。范围口径不同，前两行与后几行不能直接相减。

| 轮 | 对象 | 范围内承重缺口 | 确认关掉 | 合规 license | 决定队列 | 仍在 | 换了地方 | 随实现退役 | 靠拿掉／功能句落空 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 前提 v1→v2（第一轮） | 全剧 | 45 | 18 | — | — | 10 | 9 | — | 8／14 |
| 前提 v3（R4） | 第 1–12 集 | 27 | 8 | 1 | 0 | 14 | 2 | 2 | 0／0 |
| 前提 v4（R4b，换实现第二次即最后一次） | 第 1–12 集 | 32 | 19 | 1 | 3 | 4 | 2 | 3 | 0／0 |
| 候选 B＋登记（R5 及增量） | 第 1–12 集 | 33 | 19 | 1 | 8 | 0 | 2（均已落进决定队列） | 3 | 0／0 |

来源：`r4/r4-summary.json` `scopeLoadBearing27.counts`、`r4b/r4b-summary.json` `finalDestinationTable.countsAll32`、`r5rc/r2/r5rc-r2-summary.json` `finalDestinationTable.counts`。v3 这一轮另有 9 条戏剧假定登记不合规（用到了动机、自相顶、巧合上），被审核退回（#71）。v4 这一轮核对方新判承重 2 处（其一是一位人物三年里几件程序上的事每件只走一步，`P4-秦峥总账`），候选 B 核对又新判 1 处（X-035）；换实现预算已到顶，三处都按规则进了决定队列，没有再换。

**范围内功能（23 个）。** 沿用候选 A 12 个、换实现 11 个；候选 B 第一次核对 3 pass、2 pass_with_unverified、18 fail（`outcome` 不作依据）；功能句落空 0（`r5rc/losses.json`），另有 2 处「削弱而未自报」记在同一文件。第 5–7 集用到的 12 个功能最终全部 ready（`r5rc/r2/r5rc-r2-summary.json`）。

**按验收要求分开数。** `closes`（核对确认关掉）19；`retiresWith` 3；`leavesOpen` 29 条记录、去重后 23 处，全部不承重（`r6/leaves-open.v1.1.json`）。

**两份清单的条数（只描述，不设门槛）。**

- 决定队列 27 条，全部 `pending`、全部有默认：底账与前提层 22 条（其他 10、前提 6、戏剧假定 5、设定冲突 1），季编排 5 条（容量 4、季 1）。默认都不让功能句落空。
- 戏剧假定清单 6 条（`license_pending`；其中 1 条在范围外），`accepted_license` 0 条——没有一条有主创原话。
- 未核清单 46 条（程序 45、钱 1）。

新规则下 C3a 没有再停住。它是真的收敛了，还是把问题挪进了上面三份清单，**由读报告的人判断**；按实施计划，这看的是清单的长度与内容，不是本报告能下的结论。

## 九、哪些 schema 要改（修正点第 71–90 条）

第 1–70 条已在中期报告第五节归组，并已写进两份方案（实施计划 §2.6 #15–#26，逐条去处在 `V/schema-findings-disposition.json`）。下面是 D6-0 续新增的 20 条，全文在 `V/schema-findings.md`。

**对象（字段）**

| # | 一句话 | 建议落到 |
| --- | --- | --- |
| 73 | 沿用的候选只答部分问时，「本轮不问」与 `n/a`（无可问之物）混用 | `answers` 加 `notAsked`；`check-answers` 按任务声明的问题子集核覆盖 |
| 74 | 同一缺口的承重判断换了前提或候选后会翻转 | `loadBearing` 绑定 `judgedAgainst: {candidateId, premiseRev}`，上游变了即失效重判（连 §2.8 #8） |
| 75 | 写作方的底账改动是自由文本，脚本不能安全落账；功能地图收敛了底账没跟上 | `ledger-delta.writes[]` 只收字段级改动；C3a→C3b 交接加 `selected-deps-not-contested` |
| 76 | 多轮核对后，旧记录的 `disposition` 指向已拆分或改挂的条目 | `answers.supersedes`；条目拆分时 `retiredInto[]`（连 §2.8 #9） |
| 79 | 季编排只出一个估时、只核动作前那一层 | `capacity season` 原生两口径；`season-plan` 分 `episodesBeforeAction` 与 `episodes` |
| 80 | 底账明文写「交给分集计划定」与任务书「上游没给的不补」相顶 | 底账条目加 `decidedAt`；`plan-check` 报出该落定而未落定的 |
| 84 | 信息清单的「戏内谁知道」存人名、fact 没有知识条目 id | `episode-plan` 的 `facts[].ledgerRef[]` 必填（可空须写原因）；`knownByInStory` 改为知识条目 id |

**命令**

| # | 一句话 | 建议落到 |
| --- | --- | --- |
| 82 | 冷读核对按关键词子串命中，同义改写判 partial | `retell-check` 加读者自填 `factRefs`，脚本核引用，关键词降为旁证 |
| 85 | `ledger knows` 只导出知识账，漏了物件可见与时间线知情两类 | `knows` 初值来源写明三类；或写物件、时间线条目时同步写知识条目并 S 核一致 |
| 89 | 两个诊断信号在中文口语上误报多（按句末标点数、书面关键词对口语对白） | `dialogue-diagnose`、`plan-text-consistency` 这两条只作提示，输出标 `signalQuality: low` |

**规则**

| # | 一句话 | 建议落到 |
| --- | --- | --- |
| 71 | 戏剧假定被用到了动机、自相顶、巧合上 | `license_pending` 只能挂在 `defectKind: contradicts_reality` 的缺口上（S）；决定条目 `options[].losesFunctions[]`、`affects[]` 必填 |
| 72 | 写作方仍把新开出的缺口判为不承重 | `loadBearing` 只由核对方填；写作方的 `leavesOpen` 只是声明 |
| 77 | 生成脚本另写一套判定，命令行复现不了它的「通过」 | 验收证据规则：每个 S 项的证据是一条可直接运行的命令及其输出 |
| 81 | 分集计划的 `speaker-knows` 核的是同一份计划里自填的名单 | 改查 `ledger knows` 在该拍之前的结果；名单由导出生成初值，模型只能收窄 |
| 87 | 对话表核对首跑 18 条全是脚本模型错误 | 每条 fail 输出原样片段；`speaker-knows` 三条路（场前已知、本场自己做的、本场更早被告知）写进规则；交换加 `beatRef` |
| 88 | 物件状态不符、处置做法与现实相反，问题单双跑都没抓到 | C6 加 `text-ledger-objects`（报不拦）；对话问题单增一问「人物示范的处置与程序做法有出处吗」（引 K1） |

**流程**

| # | 一句话 | 建议落到 |
| --- | --- | --- |
| 78 | 按条数粗估数不到「同样的事实说了更多话」 | 粗估只用于排序与触发动作；有正文的集以正文精估为准，季编排回校一次并升修订号 |
| 83 | 冷读者看不懂的原因有的写在 `moves`、不在 `events` | C5a 装包同时装 `events` 与 `moves`；计划冷读只测 `events` 自足 |
| 86 | 同处境样本检索对本集两个核心处境为空，与上一轮第 6 集相同 | 印证实施计划 §2.6 #14；D6-4 补现实题材险情类语料 |
| 90 | 正文精估对计划复核是 1.30 倍 | 印证 #78，只作描述 |

**哪几条修正或推翻了方案 v1.2 已写下的内容。**

- **推翻**：#82——集纲方案 v1.2 §4 第 7 栏与 §10.3 以 `facts[].keywords[]` 作冷读对照的依据（来自 D6-0 第 43 条）；真实数据上它判错了停点，应降为旁证。
- **修正**：
  - #71 收紧集纲方案 §9.2 与 §6.4 去处 (b)：v1.2 允许「走不通或没有出处」的场面登记戏剧假定，这里限定为与常规相反的缺口，并改为 S 可核。
  - #73、#74 修正 §6.4 的回答记录：`holds` 的 `n/a` 拆出 `notAsked`；「承重由谁标」之外加绑定与失效。
  - #75 修正 §3.1 与 §12 #2 的 `ledger-delta`，以及 §2.2 的 C3a→C3b 交接条件。
  - #78、#79 修正 §7.1、§7.4：季编排在正文出来后回校，`season-plan` 分动作前后两层。
  - #83 修正 §4 第 4、6 栏与 §10.3 的分工：正文写作的输入不止 `events`。
  - #84 把 §4 第 7 栏「引用知识账」从说明改成必填的 id 字段。
  - #85 修正 §3.5：`listenerKnows` 的来源不只是知识账的 `notKnows`。
  - #87 修正 §10.2 `speaker-knows` 的判法。
  - #88、#89 修正台词方案的问题单（在 15＋2 问之外再加一问）与诊断信号表。
- #72、#77、#80、#81、#86、#90 与 v1.2 一致或只是印证，不改已写下的内容（#81 是临时脚本没照 v1.2 §10.2 实现）。

## 十、收尾修正（2026-10-14，主创要求补齐后复核）

第一版报告判为部分或不满足的七条，补齐工作由编排方组织完成，产物在 `V/r15/`。下表是我对着文件逐项核过的事实，不是转述；命令见第一节对应行。

| 条 | 改了什么 | 落在哪 | 我另外核了什么 |
| --- | --- | --- | --- |
| C5 | 10 份记录（冷读 6、问题单 4）补 `promptVersion`（提示词与问题单文件的路径与 sha256）；`check_answers.py` 改为缺版本即报错 | `r15/retell-*.json`、`r15/check-ep006A-*.json`、`tools/check_answers.py`；补记日志 `r15/build-r15-promptversion-log.json` | 哈希与现行文件一致；提示词文件的修改时间都早于对应运行；旧记录跑 `check_answers` 确实 exit 2 |
| F4 | 选定候选补 `closes[]`（14 个候选、45 项），每项 `confirmedBy` 指回核对记录；`check_function_map.py` 回核该记录 `verdict == confirmed` | `r15/function-map-v1.2.json`、`r15/function-map-v1.2-build-log.json`、`tools/check_function_map.py`（`--records-base`） | 破坏测试：指向一条 `still_there` 记录时 exit 2 |
| P3 | 新脚本数登记的勘误是否落进下一版：16／16 | `tools/maperrata_count.py`、`r15/maperrata-count.json` | 只核「改没改」 |
| C1 | 6 份冷读逐 fact 补复述序号与正文行号（计划冷读为拍号），并与关键词判定并排 | `r15/factrefs-retell-*.json`、`r15/factrefs-summary.json` | 57 条引用全部可解析；判定是核对代理事后做的 |
| C3 | 新脚本按（问号，行号）对齐两跑：可比 58、一致 56、只 a 29、只 b 12 | `tools/consistency_check.py`、`r15/consistency-g1-a-b.json` | 重跑与存档一致 |
| C4 | 底账与计划轨 delta 补按拍时点（`knownToSince`／`visibleToSince`，嵌套到部分）；`ledger knows` 按部分导出并另列 `withinScene`；`check_dialogue_plan.py` 认 `withinScene`；b 定向复读第 16 问三处，全部成立 | `r8/ledger-006A.planned-delta.json` 等（重生成）、`r8/knows-ep006A.json`（v1–v4 存档）、`r15/check-ep006A-g2-b-rv5.json`、`r15/dialogue-check-v2.1.json` | 对话表核对的 8 条 `speaker-knows` 豁免现在都走 `withinScene` 按拍那一路 |
| R1 | 合并决定队列 DQ-S0 的 `kind` 由 `season` 改为 `capacity`；底账给退役的用户给定条目补 `decisionRef`／`retiredBy`；`ledger check` 加规则 `retired-user-given-justified` | `r15/decisions-merged.v2.json`、`r15/ledger-ep000.v1.2.json`、`r15/build-r15-decisions-ledger-log.json` | 规则在 v1.2 链上 pass；在旧 v1.1 链上 fail（见下） |

**补齐过程中查出的工具 bug**（依据 `tools/ledger.py` 内的注释与 `r8/knows-ep006A.v1–v4.json` 的差异；每一处都在现行代码里修了）：

1. `ledger knows` 的导出没有分清「场前已有的条目」和「本场写入刚追加了按拍数据的条目」：本场写入先于取数应用，条目有没有按拍数据要看写入顺序的运气，结果按拍数据缺失或误判。修法是记下本场触碰过哪些条目、分开处理。修的过程中又出了一次回归：只改物件状态、没碰知情字段的写入也被当成「本场触碰」，把早就看得见该物件的人挡在场前之外。v4 之后的现行导出修了这一处（现行文件与 v4 相比，多了一位人物在第 6A-3 场的两条物件可见项）。
2. 嵌套形态的 `since`／`knownToSince`（一个条目拆成几件子事实、各在不同拍才知道）被当成字符串解析；现在按部分拆开（`since_value_parts`、`person_since_parts`）。
3. `rerun-all` 最初漏传参数，产生了误报。按 `r15/reproduce-commands.json` 里的说明，底账核对后来改回与 R6 同一套参数，换上 v1.2 文件。这一条我只核了现行脚本的参数，没有看到误报那一版的输出。

**仍未决的事项**（这些不在 S 项里，补齐也没有处理）：

- 第 73 行：说话人凭什么知道一个设施的位置，底账上没有出处（CP-01）。g1 两跑都判 `not_evaluable`，这次的定向复读不在范围内。
- 问题单的定向复读与「17 问每问至少一答」的格式要求冲突：定向复读只重判了第 16 问，其余各问为了过格式沿用旧判。复读记录的 `outcome: pass` 只覆盖它重判的三处。对策可以并入修正点 #73（`notAsked`）。
- 双跑在「答哪些行」上的分歧（只 a 29、只 b 12）大于「答案是否一致」上的分歧（2）。覆盖由答题人自选，两人落点差得多，一致率 96.6% 只代表 58 个共同落点。
- 存档的计划轨底账 `r8/ledger-ep005.planned.json`、`r8/ledger-ep006A.planned.json` 仍建在 v1.1 上，按新规则 exit 2，要在 v1.2 链上重建。实际轨的 delta 没有按拍时点字段，与收尾后的计划轨比，多出 3 条只差时点的改动（第七节）。
- 6A-I7 那条 fact 的原文与 g2 正文不符，C4 还没改；`r6/setting-check-report.v1.1.json` 没有按 v1.2 重生成；`ledger check` 一次传入多个 delta 仍会崩；`retell_check.py` 缺 `promptVersion` 只提示、不拦；C1 的事实级行号不是冷读者自填（#82 要求的形态在 D6-1 做）。
- 第 93 行的复读写在导出最终版之前（复读 21:15，`knows` 最终版 21:27）。核对者在记录里写明是直接按底账的按拍时点判的；最终导出给提问的人记的知情范围与复读的前提相同，导出的修改没有改变这一处的判断依据。

## 十一、局限

- **全部判断由模型作出，没有人看过。** 追问、承重判断、戏剧假定审核、分集计划、对话表、正文、冷读、问题单、修订都是模型做的；编剧与主创没有看过 g1、g2，也没有确认任何一条决定或戏剧假定（`accepted_license` 0 条）。
- **范围窄。** 上游只收敛了第 1–12 集（23 个功能，26 个未重核）；台词层只做了 6A。6B、第 5 集的正文没有写；6B 的冷读只读了计划。前提是全剧的，只按前 12 集收敛的前提在后段可能重开缺口。
- **冷读者用了两种模型**（按编排方的说明），记录里没写哪位用哪种；问题单只有 g1 双跑，g2 只做了单人定向复读；候选 B 的增量核对是同一上下文做的。
- **核对脚本本身尚不可靠。** 对话表核对首跑报 18 条，全部是脚本模型错误；`plan_check` 与 `ledger check` 都有整数／字符串集号比较的崩溃（前者靠包装脚本跑过、后来修了，后者多 delta 一次传入仍崩）；`why-missing`、`refs-exist` 等规则在真实数据上逐次放宽过（规则内注释写明了日期与理由）；R6 起初由生成脚本另写判定，命令行复现报 48 条错，改后才一致；三集 planned delta 的 `ledger check` 到 R14 才补跑。脚本 pass 能说明的范围以各规则的实现为限，例如分集计划 `speaker-knows` 三集全 pass，核的是自填名单（#81）。
- **中途丢失过一份中间文件。** 按编排方的记录，`ledger knows` 的第一版导出（knows v0）丢失过；现存 `r8/knows-ep006A.v0.json` 与现行版写入时间只差一分钟，是不是原件我没有核实。
- **估时的物理量没有校准。** 媒介档案是两部真人剧的语料默认值（`uncalibrated`）；画面拍 2 秒是约定值（`assumed`）；正文估时不含画面时间；两轮的行计数规则不同（第二节）。
- **样本与禁词的覆盖面小。** 8 字档查重的来源只有 76 个汉字；禁词表是人工候选；本集两个核心处境没有同处境语料，用了本剧编剧定稿句作正例。
- **检索的覆盖面与来源质量。** K1 卡共 60 张（D6-0 续第五批 9 张、正文核对时 1 张），`contract-check knowledge-card` 60/60 通过（报告方补跑：在仓库根目录对 `V/knowledge/cards/` 下每个文件跑 `python3 -B skills/drama-studio/scripts/drama_tools.py contract-check knowledge-card <文件>`）。外部来源全部 `external_not_checked`；多数条文取自转录本；没有访问裁判文书库；「没查到」只指本次没检索到；第五批之后仍有几处程序做法没有出处（`V/README.md` R3 行）。
- **mali-story 没有读写**（本会话 MCP 连接超时）；没有改技能文件、技能脚本、schema、测试，没有改项目的集纲、正文与原有知识卡。
- **收尾补齐带来的局限。** 补的多是事后补记：`promptVersion` 按文件哈希补记，不是运行时写入；事实级行号与按事实判定由核对代理补，不是冷读者；`closes[]` 从既有的核对记录搬进功能地图，没有新的核对。临时脚本在收尾中又改了一轮（`check_answers`、`check_function_map`、`ledger`、`check_dialogue_plan`，新增 `maperrata_count`、`consistency_check`），改动本身只经过这次的真实数据与少量破坏测试，没有独立的回归集。第 93 行的复读与第一次 b 跑是同一位核对者。
- **验证脚本另有一处与本报告无关的报错。** 仓库 `python3 -B scripts/validate.py` 报 9 条 Missing link，全部来自两份已提交的旧设计文档（知识台架设计 2026-09-29、工作流设计 2026-09-26）指向本机已不存在的 mali-story 目录；`docs/d6/` 下没有报错。本报告没有改那两份文档。

## 十二、结论（按退出条件）

- **S 项是否全过：是。** 33 条全部满足；其中 7 条是收尾修正后重判的（F4、P3、C1、C3、C4、C5、R1），其余 26 条用收尾后的现行文件重跑，仍然满足。第一版报告的判定（满足 26、部分 6、不满足 1）与成因保留在第一节各行的「收尾前」标注与第十节里。
- **退出条件：满足。** §4.1 的退出条件是 S 项全过、对照报告写明哪些 schema 要改；两条都已做到（第一节、第九节）。
- **读报告的人要看的保留**：几条 S 项是靠事后补记达到的（C1、C5，F4 的搬移）；第 93 行是单人定向复读；第十节的未决事项不在 S 项里，但会影响 D6-1 的 schema 与 6B 的写作。新规则下的 C3a 是真的收敛了，还是把问题挪进了决定队列（27 条）、戏剧假定清单（6 条）与未核清单（46 条），仍由读报告的人判断（第八节）。
- **「哪些 schema 要改」**：见第九节；收尾修正查出的工具 bug 与未决事项（第十节）也是 D6-1 的输入。
