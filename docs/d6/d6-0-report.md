# D6-0 对照报告：重开（D6-0 续）后的验收、对照与 schema 修正点

日期：2026-10-14。依据：[统一实施计划](../design/drama-studio-outline-dialogue-implementation-plan-2026-10-14.md) §4.1「D6-0 续」、§2.6、§2.8；[中期报告](d6-0-interim.md)（第一轮停在任务 9 的事实与成因，本报告不重复，只引用）。

本页只有编号与统计，不含项目的剧本句子、集纲原文、台词或人物设定细节；人物只用角色名或条目编号指代。产物在项目目录 `projects/qige-xiongdi/runs/pilot-v2/`（下文记作 `V/`，不随仓库分发）；上一轮第 6 集台词验证在 `runs/pilot-ep006/`（记作 `E/`）。

**复现约定。** 下文命令都在 `V/` 目录下运行（`cd projects/qige-xiongdi/runs/pilot-v2`），解释器为 Python 3.11 标准库，脚本是 `V/tools/` 下的临时脚本，不是技能脚本。标「R14 补跑」的命令是写本报告时补跑的，原步骤的产物里没有对应输出；其余命令取自各步 summary 的 `reproduceCommand` 或 `V/README.md`，本报告写作时逐条重跑过，结果与原记录一致。

## 结论

- 「D6-0 续」验收的 S 项拆成 33 条逐条判：**满足 26、部分 6、不满足 1**（第一节）。不满足的是「冷读与问题单记录带 `promptVersion`」；部分的六条是：功能地图 `closes[]` 的核对记录引用、功能地图勘误清零、复述每条 fact 有行号、双跑一致性记录、「不成立」项回修并复读、用户给定不成立项都有默认。
- 按 §4.1 的退出条件（「S 项全过；任一方不过，停在 D6-0 重看成因，不进 D6-1」），**本轮不满足退出条件，停在 D6-0**。七条里五条是内容在、但 S 可核的载体缺（字段没有、记录没有结构化）；一条是合并后的决定队列有一个 `kind` 不在词表、两条退役的用户给定条目没有决定引用；一条是正文问题单里仍有一条承重的「不成立」，成因在知识导出口径，本轮按默认走法写正文、未修导出（RV-5）。是补齐记录后复核再判，还是把这几条作为 D6-1 的 schema 输入，由读报告的人定。
- 范围是实施计划给的默认：只收敛第 1–12 集用到的前提与功能（23 个功能；其余 26 个标「未重核」），台词层只做了新第 6 集的前一半（6A）。**这不是「四条线已收敛」。**

## 一、验收逐项（S 项；M 项只写记录位置）

### 1.1 功能地图

| # | 验收项 | 判定 | 证据与复现 |
| --- | --- | --- | --- |
| F1 | 范围内每个功能有 `selected` 实现或已登记保留 | 满足 | 23 个 `selected`，`functionsDropped` 0。`python3 -B tools/check_function_map.py r6/function-map-v1.1.json --stage v1 --rc-dir r5rc --rc-extra-dir r5rc/r2 --decisions r6/decisions.v1.1.json --ledger r6/ledger-ep000.v1.1.json --scope r1/scope-ep001-012.json` → `ok: true`，exit 0 |
| F2 | 承重 `notHolds` 都带 `disposition`，引用对象存在且状态相符 | 满足 | 同上命令：`loadBearingNotHoldsChecked` 21、`MissingDisposition` 0 |
| F3 | 没有 `losesFunctions[]` 非空而被标 `selected` 的候选 | 满足 | 同上命令（脚本 `--stage v1` 规则 1） |
| F4 | `closes[]` 每一项有核对记录引用 | **部分** | 功能地图 v1.1 的选定候选**没有 `closes[]` 字段**，脚本不核。关掉的缺口记在核对方的 `r4/closes-confirm.json`（13 项）、`r4b/closes-confirm.json`（17 项）、`r5rc/closes-confirm.json`（68 项），每项都有 `record` 引用；两边没有字段连接 |
| F5 | 被否定的候选有 `rejectedBecause` | 满足 | 同 F1 命令（`candidatesRejected` 23） |
| F6 | 范围外功能标「未重核」 | 满足 | 同 F1 命令：`functionsOutOfScope` 26，每个带 `outOfScope: true` 与说明 |

### 1.2 前提

| # | 验收项 | 判定 | 证据与复现 |
| --- | --- | --- | --- |
| P1 | 每个前提问题有默认与决定队列条目 | 满足 | `r2/premises-v4.json` 六个问题各有 `default`；`r6/decisions.v1.1.json` 中 `kind: premise` 6 条。`python3 -B tools/decision_queue.py check r6/decisions.v1.1.json` → `ok: true` |
| P2 | 跨前提一致性表无空格 | 满足 | `r2/premises-v4.json` 的 `consistency`（时间线、钱表、谁知道什么三张表）叶子格 396 个、空格 0（R14 补跑：`python3 -c "import json;c=json.load(open('r2/premises-v4.json'))['consistency'];f=lambda o:[x for v in (o.values() if isinstance(o,dict) else o) for x in f(v)] if isinstance(o,(dict,list)) else [o];v=f(c);print(len(v),sum(x in (None,'') for x in v))"`）。没有正式脚本；「无空格」不等于「无冲突」，v3 那一轮核对方在同类表里找出过 7 处跨前提相顶（`r4/r4-summary.json` `crossPremiseConflicts`） |
| P3 | 功能地图勘误清零 | **部分** | 候选 B 第一次核对记了 16 处 `mapErrata`（`r5rc/r5rc-summary.json`）；修正轮把 `rejectedBecause` 按最终去向表重写（`r5/fm-v1-scope.r2.json` 起的 `rejectedBecauseNote`）。没有脚本计数勘误，增量核对是同一上下文做的（`r5rc/r2/r5rc-r2-summary.json` `checkedBy`），只重核了改动部分 |

### 1.3 底账

| # | 验收项 | 判定 | 证据与复现 |
| --- | --- | --- | --- |
| L1 | 范围内依赖的条目齐 | 满足 | `python3 -B tools/ledger.py check r6/ledger-ep000.v1.1.json --stage default --scope r1/scope-ep001-012.json --cards knowledge/cards --function-map r6/function-map-v1.1.json --decisions r6/decisions.v1.1.json` → `ok: true`，`refs-exist` pass |
| L2 | 默认阶段 `contested` 为零 | 满足 | 同上命令 `contested-zero` pass（范围内 0；全账 416 条里 10 条 `contested` 在范围外，只报） |
| L3 | `unverified` 清单与戏剧假定清单存在并注明依赖的集 | 满足 | `r6/unverified-list.v1.1.json` 46 条（程序 45、钱 1），全部带 `dependents[].episodes`；`r6/license-list.v1.1.json` 6 条，范围内 5 条带依赖集，范围外的 LP-C4 无依赖记录 |
| L4 | `accepted_license` 的条目都有 `humanWords` | 满足（空集） | 底账里 `accepted_license` 0 条，`license_pending` 5 条；同 L1 命令 `license-has-words` pass |
| L5 | §10.2 规则对 `ledger@ep000` 与三集 planned delta 全过 | 满足 | ep000：同 L1。三集 planned delta：R8 只跑了 `ledger.py apply`，没有跑 `check`；**R14 补跑**逐段过：`python3 -B tools/ledger.py check r6/ledger-ep000.v1.1.json --stage default --scope r1/scope-ep001-012.json --cards knowledge/cards --function-map r6/function-map-v1.1.json --decisions r8/decisions-merged.json --delta r8/ledger-005.planned-delta.json`，另两段把底账与 delta 换成 `r8/ledger-ep005.planned.json`＋`r8/ledger-006A.planned-delta.json`、`r8/ledger-ep006A.planned.json`＋`r8/ledger-006B.planned-delta.json`，三次 `ok: true`。三个 `--delta` 一次传入时脚本崩溃（`planned-vs-actual` 用整数集号与字符串集号比大小，与 R8 `plan_check` 的同一类 bug） |

### 1.4 季编排与分集计划

| # | 验收项 | 判定 | 证据与复现 |
| --- | --- | --- | --- |
| S1 | 受影响的集每集有 `capacity` 记录 | 满足 | `python3 -B tools/check_season_plan.py r7/season-plan-v0.json --function-map r6/function-map-v1.1.json --media ../pilot-ep006/media-profile-v0.json --corpus ../pilot-ep006/corpus/exchanges.jsonl --decisions r7/decisions-r7.json --decisions r6/decisions.v1.1.json` → `ok: true`，`items` 空 |
| S2 | 超出的有 `action`，没有「待定」 | 满足 | 同上。12 集里 7 集超出：拆 4（第 6、9、10、12 集）、重排 3（第 1、7、8 集），第 1–12 集成 16 集。第 1 集动作后口径甲 121.0 秒，比目标多约 1 秒，脚本不报 |
| S3 | 没有系统默认选的删线 | 满足 | `drop_function` 0；季编排的 5 条决定（DQ-S0–S4）默认都是 `add-4`／`split`，带 `losesFunctions` 的只出现在非默认选项里 |
| E1 | 三集 `plan-check` 全过 | 满足 | `python3 -B tools/plan_check.py r8/episode-plan-005.json --ledger r6/ledger-ep000.v1.1.json --season r7/season-plan-v0.json --function-map r6/function-map-v1.1.json --decisions r8/decisions-merged.json`；6A 用 `--ledger r8/ledger-ep005.planned.json`，6B 用 `--ledger r8/ledger-ep006A.planned.json`。三次 exit 0，14 条规则 12 pass、2 report |
| E2 | 冷读只读 `events`，`facts` 与 `closingEvent` 的 `missing` 为零 | 满足 | `r9/retell-check-plan-{005,006A,006B}.json`：missing 0／0／0。6B 的 `closingEvent` 脚本判 partial（关键词零命中），读者复述的停点就是该拍（schema 修正点 #82） |

### 1.5 对话表与正文（第 6A 集）

| # | 验收项 | 判定 | 证据与复现 |
| --- | --- | --- | --- |
| D1 | 每个 fact 有承载句或画面理由 | 满足 | `python3 -B tools/check_dialogue_plan.py r11/dialogue-plan-ep006A-v2.1.json --episode-plan r8/episode-plan-006A.json --knows r8/knows-ep006A.json` → `ok: true`，`info-ledger` pass（v2 同样过）。9 个 fact：对白承载 8（其中 3 个另有画面）、只靠画面 1 |
| D2 | 每个 `segment` 有 `closer` | 满足 | 同上 `topics-segments` pass（6 话题、12 段、37 个交换） |
| D3 | `listenerKnows` 与知识账无矛盾 | 满足 | 同上 `listener-knows` report、无条目。注意：v2 的初值是对着旧导出写的，脚本没报，是两位问题单核对者都指出后才在 v2.1 重写（RV-4） |
| D4 | 对齐无未登记偏离 | 满足 | `python3 -B tools/plan_text_consistency.py r12/plan-text-map-ep006A-v2.json --dialogue-plan r11/dialogue-plan-ep006A-v2.json --episode-plan r8/episode-plan-006A.json` → `ok: true`（g2 用 `r12/plan-text-map-ep006A-v2.g2.json` 与 v2.1，同样过）；37 个交换全部落到正文、顺序一致；偏离 5 处都已登记 |
| D5 | 两档 `dup-check` 零命中 | 满足 | `python3 -B tools/dup_check_hits.py r12/ep-006A.g1.md --k 8 --source-dialogue-plan r11/dialogue-plan-ep006A-v2.json --exclude-verbatim r12/plan-text-map-ep006A-v2.json`；13 字档换成 `--k 13 --source-corpus-jsonl ../pilot-ep006/corpus/exchanges.jsonl`。g1、g2 四次命中 0。8 字档的来源只有装包样本遮蔽句共 76 个汉字 |
| D6 | 禁词零命中 | 满足 | `python3 -B tools/genre_lexicon_scan.py r12/ep-006A.g1.md --lexicon tools/genre_lexicon.json`（g2 同）命中 0。词表是人工列的候选（`assumed`），不是方案要求的跨题材词频对照算出来的 |
| D7 | C5a 若有退回，`changeProposal` 记录在且带默认 | 满足 | 对话表 v2.1 `changeProposals` 7 条全部有 `default`（D1 命令 `change-proposals` pass）；正文退回 `r12/change-proposals-c5b.json` 1 条，有 `default` |

### 1.6 冷读与问题单（S 记录在；内容 M）

| # | 验收项 | 判定 | 证据与复现 |
| --- | --- | --- | --- |
| C1 | 复述每条 fact 有行号 | **部分** | 冷读记录的每条事件都有 `sourceLine`（g1 两位 18／13 条、g2 46 条，全部带）；但 `retell-check` 对 fact 的判定按关键词命中，fact 一级不带行号 |
| C2 | 17 问每问有引用与原因 | 满足 | `r13/check-ep006A-g1-a.json`（87 答）、`-g1-b.json`（70 答）都覆盖 17 问，每答有 `quoteRef` 与 `reason` |
| C3 | 双跑一致性记录在 | **部分** | 没有结构化的一致性记录；分歧只写在 `r13/revision-list-g1.json` RV-5 的文字里。R14 补算：两跑落到同一（问号，行号）的 58 处里 56 处一致，2 处不一致（`python3 -c "import json;L=lambda f:{(str(x['q']),x['quoteRef']['line']):x['holds'] for x in json.load(open(f))['answers']};a=L('r13/check-ep006A-g1-a.json');b=L('r13/check-ep006A-g1-b.json');c=set(a)&set(b);print(len(c),sum(a[k]==b[k] for k in c))"`） |
| C4 | 「不成立」项已回对话表修订并复读 | **部分** | b 跑 2 条 `notHolds`：一条（称呼，不承重）在 g2 改掉，复读成立；一条（第 16 问，承重）成因在知识导出口径，本轮不修（RV-5），g2 复读仍是 `notHolds`（`r13/check-ep006A-g2-b-delta.json`） |
| C5 | 记录带 `promptVersion` | **不满足** | 冷读记录（`r9/retell-plan-*.json`、`r13/retell-ep006A-*.json`）与问题单记录都没有 `promptVersion` 字段（问题单有 `questionsVersion`）。填好的提示词原文另存为文件（`r9/cold-read-prompt-*.md`、`r13/cold-read-text-prompt-g{1,2}.md`），可以追溯，但不是记录字段 |

### 1.7 设定核对报告、决定队列、对照报告

| # | 验收项 | 判定 | 证据与复现 |
| --- | --- | --- | --- |
| R1 | 每条 `user_given` 的不成立项都有默认 | **部分** | `r6/setting-check-report.v1.1.json` 范围内用户给定 90 条：asserted 51、verified 24、unverified 11、retired 3、license_pending 1、contested 0；12 条带决定或前提引用。缺口：①退役的 3 条里 2 条（L-proc-001、L-obj-acc-013）没有 `decisionRef`（前者拆出 L-proc-001a 挂 DQ-B2，后者是框架与圣经口径统一），人读有去处，没有字段；②合并后的决定队列 `python3 -B tools/decision_queue.py check r8/decisions-merged.json` → `ok: false`：DQ-S0 的 `kind: season` 不在词表（`r7/decisions-r7.json` 单跑同错；`r6/decisions.v1.1.json` 单跑过）。没有脚本逐条核「不成立项有默认」 |
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

复现：`python3 -B tools/capacity.py text --media ../pilot-ep006/media-profile-v0.json r12/ep-006A.g1.md`（换成 `r12/ep-006A.g2.md`、`../pilot-ep006/ep-006.f1.md`、`../b01/ep-006.e2.md`、`../input/writer-ep-005.md`）；原输出 `r13/capacity-text-{g1,f1,e2,w1}.json`，g2 为 R14 补跑。

对计划的复核：6A 在季编排里估甲 101.4／乙 74.9 秒，分集计划复核甲 109.4／乙 76.9 秒（`r8/episode-plan-006A.json` `capacity`，`status: fits`）。g1 正文口径 A 是计划复核甲的 1.30 倍，超目标 19%；没到两倍，未触发容量提案（schema 修正点 #90）。编剧定稿第 1–5 集在同一计数下口径 A 为 108.2、89.1、136.3、153.5、155.9 秒（`r7/capacity-writer-text-ep001-005.json`），第 3–5 集同样超 120 秒；g1 落在编剧定稿第 3–5 集的范围内。季编排对这三集按条数粗估都判「未超」——按条数估数不到「同样的事实说了更多话」，g1 对计划的偏差与此同向（#78）。

两处计数差异照实写：上一轮 `E/capacity-ep006.md` 给 f1 计 2087 字、给编剧第 5 集计 543 字，本轮脚本计 2063、588 字，是两套行计数规则的差别，没有逐行对过；这影响各行的秒数，不改变量级。

## 三、冷读覆盖

| 读什么 | 读者 | 清单条数 | retold | partial | missing | 停点（`closingEvent`） | unclear |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 第 5 集分集计划 `events` | 1 | 12 | 9 | 3 | 0 | retold | 4 |
| 6A 分集计划 `events` | 1 | 9 | 8 | 1 | 0 | retold | 2 |
| 6B 分集计划 `events` | 1 | 9 | 9 | 0 | 0 | partial（关键词；停点是该拍） | 6 |
| 6A 正文 g1 | a | 9 | 7 | 2 | 0 | partial（同上） | 5 |
| 6A 正文 g1 | b | 9 | 7 | 2 | 0 | partial（同上） | 8 |
| 6A 正文 g2 | 1 | 9 | 6 | 3 | 0 | partial（同上） | 6 |
| 上一轮 f1 正文 | 1 | 19 | 19 | 0 | 0 | — | 18 |
| 上一轮 e2 正文 | 1 | 19 | 6 | 9 | 2 | — | 18（另 1 条 e2 无此拍） |

来源：`r9/retell-check-plan-*.json`、`r13/retell-check-g1-{a,b}.json`、`r13/retell-check-g2.json`；上一轮见 `E/stage-d-report.md` §二（`E/retell-f1.json`、`E/retell-e2.json`）。正文 partial 的是 fact 6A-I7、6A-I9（g1 两位都是），g2 另加 6A-I5；计划冷读 partial 的是 6A-I5。6A-I7 的 partial 有一部分是关键词问题：g2 改了处置动作的写法之后，分集计划里那条 fact 的原文已与正文不符，要回 C4 改写（`r12/ledger-006A.actual-delta.g2.json` 对应条目的 `reason`）。两位冷读者都没拿到一处人物藏东西的动机，对话表把它登记为有意不交代（RV-6）：这是「有意悬置被冷读判为不明」的一例，脚本分不开两者。计划冷读里有一处 unclear 的原因写在 `moves[].whyNot`、不在 `events`（#83）。

**可比性的限度。** 两轮的信息清单不同：上一轮 19 条覆盖旧第 6 集全集，本轮 9 条只覆盖 6A。提示词不同：上一轮喂给冷读者的提示词原文没有保存，本轮按产出结构重写并改了字段名（#5）。判法不同：上一轮由核对者读复述逐条判 covered／partial／missing，本轮由脚本按关键词判，再人工旁注。读者不同：按编排方的说明，本轮冷读者用了两种模型，哪一位用哪种没有记在记录里。上一轮 f1 的 19 条全覆盖是在 9–10 分钟的篇幅上拿到的。所以这张表能说的只是「本轮三份计划、三份正文冷读都没有 missing」，不能说新流程比上一轮好或差多少。

## 四、问题单

**g1 双跑。** a 跑 87 答：成立 85、`not_evaluable` 2（第 16 问两处，说话人的依据在底账上没有条目）、不成立 0，结论 `pass_with_unverified`。b 跑 70 答：成立 67、不成立 2、`not_evaluable` 1，结论 `fail`。两跑落到同一（问号，行号）的 58 处里 56 处一致；2 处分歧正是 b 的两条不成立：

| 处 | 问 | 承重 | b 的判法 | a 为什么判成立 | 根因 |
| --- | --- | --- | --- | --- | --- |
| g1 第 89 行 | 13 | 否 | 办事人员对店主的称呼与编剧 c4 改句的称呼相反 | 没有拿编剧改句对照 | 核对者是否引反例与对照对，提示词没有规定 |
| g1 第 93 行 | 16 | 是 | 照知识账，提问的人此刻已经知道答案，这一问成了为问而问 | 照正文：提问的人不在场，问是真问 | `ledger knows` 按场头导出，把本场才发生的事整条挂到在场者名下；时间线条目只有一个 `knownTo`，表达不了「知道结果、不知道是谁做的」（RV-5、CP-c5b-01） |

**g2 定向复读。** 只由 b 复读改动的 5 行及前后各两行，另重判第 93 行与消防确认那一句：27 答，成立 26、不成立 1。改动的 5 行全部成立；消防确认处置「每一步都对」在 g2 对卡成立（g1 里不成立，见下）；剩下的一条不成立仍是第 93 行，成因不变。

**问题单没抓到的两处真错误。**

1. **物件状态与底账不符**（RV-1）：g1 第 44 行把一件拒收凭证上的退回原因写成了底账物件条目 L-obj-gb-003 里没有的说法。两位问题单核对者都没发现；编排方顺着冷读者 b 的一条 unclear 回查底账才发现。问题单 17 问没有一问对物件状态。
2. **人物示范的处置做法与现实相反**（RV-2）：g1 第 59、62、63 行，孩子在燃气泄漏处置里下的一条身体姿势指令属于火场防烟做法，不是燃气泄漏处置；而本集紧接着让消防员确认她每一步都对。核对者 b 在问题单范围之外记在 `formatNotes`，检索卡 `knowledge/cards/K1-ranqi-xielou-chuzhi@r1.json` 证实官方处置材料里没有这一项。问题单没有一问问「人物示范的做法有没有出处」。

两处都在 g2 改掉（`diff r12/ep-006A.g1.md r12/ep-006A.g2.md` 只有第 44、59、62、63、89 行）。对策见 schema 修正点 #88。

## 五、C5a／C5b 有没有退回

有，两层都退回过，全部带默认，流程按默认继续；本轮 C4 没有据此改分集计划（`r8/episode-plan-006A.json` 在对话表之前写定，之后未改）。

| 来源 | 编号 | 退给 | 类别 | 默认（只描述） |
| --- | --- | --- | --- | --- |
| 对话表 | CP-01、CP-02 | C4 | 说话人在底账上不知道 | 照写，按场内所得写知情，不补前集知识 |
| 对话表 | CP-03 | C4 | 计划与底账的知识冲突 | 后到的人不对先走的人开口、不认出他 |
| 对话表 | CP-04 | C3b（`ledger knows` 导出） | 导出缺项 | 初值照导出；状态 `partly_resolved`：物件 `visibleTo`、时间线 `knownTo` 已并入，程序条目仍不在 |
| 对话表 | CP-05 | C4 | 凭职业规矩知道 | 照写，只说规矩不引条文 |
| 对话表 | CP-06 | C4／C5a（第 6B 集） | 承载交给下一集 | 本集按画面写 |
| 对话表 | CP-07（v2.1 新增） | C4 | 计划与正文的写法差 | 对话表按正文改形状说明，承载与编号不变，计划轨不动 |
| 正文 | CP-c5b-01 | C4 | 计划与底账的知识冲突 | 第 93 行写成真问，提问的人在被告知之前不说出是谁做的 |

回路记录：对话表 v2 → 问题单与冷读 → 修订清单 `r13/revision-list-g1.json`（RV-1–3 改正文出 g2，RV-4 改对话表出 v2.1 并重核，RV-5、RV-6 不改、进本报告）→ g2 定向复读。正文退回的那一条与问题单第 93 行的分歧是同一处。

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

| 比较 | 新增 | 改动 | 删除 | 复现 |
| --- | --- | --- | --- | --- |
| 计划轨 vs g1 实际轨 | 8（知识 6、物件 1、时间线 1） | 16（知识 8、物件 4、时间线 4） | 0 | `r13/ledger-diff-ep006A.json`；`python3 -B tools/ledger.py diff r8/ledger-ep006A.planned.json r13/ledger-ep006A.actual.json` |
| 计划轨 vs g2 实际轨 | 8（同上） | 19（知识 11、物件 4、时间线 4） | 0 | R14 补跑：`python3 -B tools/ledger.py apply r8/ledger-ep005.planned.json --delta r12/ledger-006A.actual-delta.g2.json --out <输出>`，再 `ledger.py diff r8/ledger-ep006A.planned.json <输出>`；对 `<输出>` 跑 L1 的 `check` 命令，`ok: true` |

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

## 十、局限

- **全部判断由模型作出，没有人看过。** 追问、承重判断、戏剧假定审核、分集计划、对话表、正文、冷读、问题单、修订都是模型做的；编剧与主创没有看过 g1、g2，也没有确认任何一条决定或戏剧假定（`accepted_license` 0 条）。
- **范围窄。** 上游只收敛了第 1–12 集（23 个功能，26 个未重核）；台词层只做了 6A。6B、第 5 集的正文没有写；6B 的冷读只读了计划。前提是全剧的，只按前 12 集收敛的前提在后段可能重开缺口。
- **冷读者用了两种模型**（按编排方的说明），记录里没写哪位用哪种；问题单只有 g1 双跑，g2 只做了单人定向复读；候选 B 的增量核对是同一上下文做的。
- **核对脚本本身尚不可靠。** 对话表核对首跑报 18 条，全部是脚本模型错误；`plan_check` 与 `ledger check` 都有整数／字符串集号比较的崩溃（前者靠包装脚本跑过、后来修了，后者多 delta 一次传入仍崩）；`why-missing`、`refs-exist` 等规则在真实数据上逐次放宽过（规则内注释写明了日期与理由）；R6 起初由生成脚本另写判定，命令行复现报 48 条错，改后才一致；三集 planned delta 的 `ledger check` 到 R14 才补跑。脚本 pass 能说明的范围以各规则的实现为限，例如分集计划 `speaker-knows` 三集全 pass，核的是自填名单（#81）。
- **中途丢失过一份中间文件。** 按编排方的记录，`ledger knows` 的第一版导出（knows v0）丢失过；现存 `r8/knows-ep006A.v0.json` 与现行版写入时间只差一分钟，是不是原件我没有核实。
- **估时的物理量没有校准。** 媒介档案是两部真人剧的语料默认值（`uncalibrated`）；画面拍 2 秒是约定值（`assumed`）；正文估时不含画面时间；两轮的行计数规则不同（第二节）。
- **样本与禁词的覆盖面小。** 8 字档查重的来源只有 76 个汉字；禁词表是人工候选；本集两个核心处境没有同处境语料，用了本剧编剧定稿句作正例。
- **检索的覆盖面与来源质量。** K1 卡共 60 张（D6-0 续第五批 9 张、正文核对时 1 张），`contract-check knowledge-card` 60/60 通过（R14 补跑：在仓库根目录对 `V/knowledge/cards/` 下每个文件跑 `python3 -B skills/drama-studio/scripts/drama_tools.py contract-check knowledge-card <文件>`）。外部来源全部 `external_not_checked`；多数条文取自转录本；没有访问裁判文书库；「没查到」只指本次没检索到；第五批之后仍有几处程序做法没有出处（`V/README.md` R3 行）。
- **mali-story 没有读写**（本会话 MCP 连接超时）；没有改技能文件、技能脚本、schema、测试，没有改项目的集纲、正文与原有知识卡。

## 十一、结论（按退出条件）

- **S 项是否全过：否。** 33 条里满足 26、部分 6（F4、P3、C1、C3、C4、R1）、不满足 1（C5）。
- **为什么没过：** F4、P3、C1、C3、C5 是内容或证据在、但 S 可核的载体缺——功能地图没有 `closes[]`、勘误没有计数、fact 不带行号、双跑没有一致性记录、记录没有 `promptVersion`；R1 是合并后的决定队列有一个 `kind` 不在词表、两条退役的用户给定条目没有决定引用；C4 是一条承重的「不成立」按默认走法留着，成因在 `ledger knows` 的导出粒度（RV-5、#85），本轮没修。
- **是否构成「停在 D6-0」：是。** 按 §4.1，任一方不过即停在 D6-0 重看成因，不进 D6-1。换实现的预算到顶不是停的理由，本轮也不是因为它停。
- **「哪些 schema 要改」**：见第九节；对照报告的这一项要求已写明。
