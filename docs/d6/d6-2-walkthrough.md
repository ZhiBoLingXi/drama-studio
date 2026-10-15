# D6-2 走通演示：从零按新文档写到第 1 集分集计划

日期：2026-10-15　分支：`feat/d6-2-outline-layer`　性质：M 项证据，不是通过条件。

演示者扮演一个刚装好技能、第一次按新文档写集纲的 AI。说明书只用 [SKILL.md](../../skills/drama-studio/SKILL.md) 及其链接的 references（主要是 [策划](../../skills/drama-studio/references/planning.md)、[集纲层](../../skills/drama-studio/references/outline-layer.md)、[工位契约](../../skills/drama-studio/references/workstations/README.md) 与 C1、C2、C3a、C3b、C3c、C4、C6 工位文件），外加它们指向的 `schemas/` 示例与 `--help`。没有读 `docs/`、`tests/`、`scripts/d6_acceptance/`、真实项目目录，也没有读工具源码。

项目：`projects/d62-walkthrough/`（gitignore，不入库），剧名《旧楼电梯》。材料全部编造：六层老楼一单元 12 户要加装电梯，四楼周敏的母亲困在楼上，一楼独居的孙老师不签字，因为电梯井会挡住她家唯一朝南的窗。人物 4 个（周敏、孙老师、赵建国、社区林晓），10 集，单集 120 秒。下文路径都相对项目目录。

结论先说：走到了第 1 集分集计划，`season-check --outline 1` 不加 `--allow-offline` 退出 2（只剩 `outline-saved`：没有 mali-story，回执是 `not_sent`）；加 `--allow-offline` 退出 0，`ruleSet: outline-layer`，`outline-saved` 降为警告。中途有 18 处要绕过或猜，没有一处真正卡死。

## 谁在哪个上下文里做的

| 环节 | 上下文 |
| --- | --- |
| C1、C2、C3a 写图、C3b 建账、C3c、C4 写计划 | 演示者同一上下文（C3a、C3b 的包是写完后补装的） |
| C3a 追问单（4 份记录） | 新上下文子代理，只读 `fact_check` 包 |
| C4 第 1 集 moves 追问单（两轮） | 新上下文子代理，各读一个 `fact_check` 包 |
| 冷读复述（两次，计划改过一次） | 新上下文子代理，只读抽出来的 events 文件 |
| C6 审读记录 | 第一份由演示者汇总（`serial_self_review`）；第二份由新上下文子代理写（`independent`），见发现 11 |
| K1 检索 | 演示者用宿主 WebSearch 查了一次，按搜索摘要写卡，没打开原文 |

选题确认这个人审点没有真人，由演示者代填，记在 `run-c1` 的 `unfinished`。

## 0. 建项目

读：SKILL.md「一次完整创作」第 1 步；集纲层 §1 末段。

- `init-project projects/d62-walkthrough --title 「旧楼电梯」` → 0。建了 `planning/ledger/`、`planning/episodes/`，没有建 `runs/`、`knowledge/`、`.drama/runs/`，这些后来手建。
- `doctor` → 0，`mali_story: not_checked`。会话里 mali-story MCP 连接超时，全程离线。

## 1. C1 定位

读：c1-positioning.md；planning.md「选题卡」。

- 产出：`planning/brief.md`（类型承诺、核心矛盾、立场、限制、独特性）。用户给定设定（演示中由我扮演用户）：**「一楼孙老师一户不签字，电梯就装不成。」**
- 任务 `.drama/tasks/task-c1.json`、交接 `.drama/runs/run-c1.json`。
- `contract-check task` → 0；`contract-check run-handoff` → 2（`$.contextSnapshotId: expected string`）。C1 没有装包角色，最后填 `unknown:c1-未装包…` → 0（发现 8）。

## 2. C2 人物

读：c2-characters-world.md；dialogue.md §2 声音卡。

- 产出：`planning/characters.md`（四人；「前史」一节先写「待定」，C3b 建账后回填 `L-tl-001`～`003`）；声音卡 `knowledge/cards/vc-zhoumin@r1.json`、`vc-sun@r1.json`、`vc-zhao@r1.json`（K5，`creative_hypothesis`）。
- `knowledge validate .` → 0；task／handoff `contract-check` → 0。

## 3. C3a 功能地图（含用户给定设定与前提）

读：集纲层 §2、§3、§5、§7、§11；c3a-function-map.md。

1. 写 `planning/function-map.json` v0：三条线（T-lift 电梯能不能装、T-sun 孙老师为什么不签、T-money 钱怎么分），各一个功能、一个候选 A。F-lift-1.A 标 `user_given`，依赖断言 `D-lift-p01`「须全体业主同意」。`contract-check function-map` → 0；`function-map check --stage v0` → 0。
2. `function-map topics` → 0，归并出 7 题。检索代理写 K1 卡 3 张（`K1-lift-vote`、`K1-lift-process`、`K1-lift-cost`）。查到的事实：民法典第 278 条是「双三分之二参与、参与者双四分之三同意」，一户反对不构成否决。原始摘要存 `knowledge/sources/src-lift-search/notes.md`。Q-003、Q-004 是人物知情与图谋，没有可检索的对象，没写卡（发现 15）。
3. 前提：把「一户不签为什么就办不下去」归并成 PQ-1，三个候选：a 用户给定（全体同意）、b 门槛已够但公示期书面异议使协调期卡住、c 参与人数不足（`losesFunctions` 非空）。按 §11 第三行默认保留 a（发现 17）。`decision add planning/decisions.json --entry …D-001.entry.json` → 0（`kind: premise`）；`decision check` → 0。跨前提一致性表手写在 `planning/premise-consistency.md`（发现 14）。
4. 追问单（新上下文）：`context-pack --role fact_check` 第一次 → 2，三张卡 `comparison_only` 被拒（发现 1）。出 r2 改成 `creative_reference` 后 → 0（`ctx-41e7ea3491170b57`）。子代理写了 `.drama/checks/RC-lift-1A.json`、`RC-PQ-1.json`、`RC-sun-1A.json`、`RC-money-1A.json`，`contract-check answers --cards knowledge/cards` 都是 0。承重缺口：PQ-1.a 与民法典不符，去处是 `decision → D-001`；F-lift-1.A 的同一缺口 `inheritedFrom: RC-PQ-1`。
5. 选定：三个功能各标 `selected`，补上 `ledgerDeps[].entryId`（核对方记的勘误）。`L-proc-001` 标 `license_pending`。`function-map check --stage v1 --rc-dir .drama/checks --decisions … --ledger …` → 0。
6. `check-answers RC-*.json … --records .drama/checks` → 1，`--records` 不收目录（发现 7）；改成逐个列文件 → 2，四份都缺 `promptVersion`（发现 4）。补上之后 → 0。`defects build --records .drama/checks` → 0（9 项，承重 2，无去处 0）。

## 4. C3b 底账

读：集纲层 §4、§6；c3b-ledger.md。

- 为了让追问单第 13 问有总账视图，C3b 提前到追问之前（发现 3）：`ledger init` → 0，写 14 条（程序 4、钱 1、物件 2、知识 2、图谋 2、时间线 3，其中一条是 `state` 子型）。
- `contract-check ledger-entry` → 0；但 `ledger check --stage pre-select` → 2，`schema-basic` 报缺 `didNot`、缺 `why`、`state` 子型缺 `knownTo`、图谋 `validTo` 为空（发现 5）。补字段后 → 0。
- `ledger view --blank-period --md` → 0，存 `.drama/checks/blank-period-ep000.md`。`state` 条目被归到「（未写 who）」（小）。
- 选定后去掉 `--stage` 跑 → 2，`money-closed: account 为空且未标 no_trace`（发现 6）。补上 account → 0。`ledger stats` → 0（`license_pending` 1、`unverified` 2）。
- `context-pack --role function_mapper` → 0（`ctx-d79c08856292a56c`），`--role ledger_keeper` → 0（`ctx-a357d2e8f08e4b04`），都是事后补装。交接 `run-c3a-1`、`run-c3b-1` → 0。

## 5. C3c 季编排（含容量）

读：集纲层 §8；c3c-season-plan.md。

- 产出 `planning/season-plan.json`：10 集的功能、事件粗列、★，埋设 P-window-1（茉莉，第 1 集埋、第 10 集收）。媒介档案没有规定位置，复制随包示例到 `planning/media-profile.json`。
- `capacity season … --media planning/media-profile.json` → 1：「要 --corpus 或 --exchange-median-sec」（发现 2）。假定 `--exchange-median-sec 8` → 0，每集都 `fits`（50–78 秒，目标 120 秒）。
- `season-plan-check … --function-map … --decisions … --media …` → 0（`final-sequence` 只报）；`contract-check season-plan` → 0。`context-pack --role season_planner` → 0；交接 `run-c3c-1` → 0。
- 卷级视图在 schema 里没有字段，没写（小）。功能地图只有三个功能，第 5–10 集是复用，这是演示材料薄，不是文档问题。

## 6. C4 第 1 集分集计划

读：集纲层 §9、§12；c4-episode-outline.md（含「整季集纲怎么写」）。

- `context-pack --role author` → 0（`ctx-59fe44bf4db8d6ab`）。后来按 season-check 的报错重装成 `ctx-9726a6ea87ce6f92`，加了媒介档案（发现 10）。
- 产出 `planning/episodes/episode-plan-001.json`，三场九拍：1-1 母亲在三楼歇第三次，周敏背她上楼；1-2 周敏挨家收同意书，十一户签了；1-3 孙老师说「小周，我不同意」后关门，门缝里是南窗台的茉莉（`closingEvent: 1-3.b3`）。计划轨 delta 写在 `planning/ledger/delta-ep001.planned.json`。`pending` 引 D-001 的默认。
- `contract-check episode-plan` → 2（`quote: expected string`，拍上不能写 `null`，要删掉这个键）→ 改后 0。`contract-check ledger-delta` → 0。
- `ledger apply … --out planning/ledger/rev/ledger-ep001.planned.json` → 0；`ledger check <ep000> --delta <本集 delta>` → 0。
- `capacity episode` → 0（A 口径 30 秒，B 口径 14 秒）。
- `plan-check … --ledger ledger-ep000.json --season … --function-map … --decisions … --characters planning/characters.md` → 0。`speaker-knows` 是 pass，但孙老师那句列为 `notEvaluable`（自己的表态也要知识账条目）；`summary` 只报。
- 追问单（新上下文，`ctx-d26ae2434c4c8e86`）：`RC-ep001-moves.json` 查出一个**真缺口**。一楼有 101、102，1-2 场只敲了二到六楼，所以「十一户签了，只缺 101」算不平。核对方找不到合适的去处，填了 `license → L-obj-002`，被 `check-answers` 拒（发现 13）。在同一个 C4 运行里改成从 102 敲起（r1 存在 `runs/ep001/episode-plan-001.r1.json`），新上下文复核 `RC-ep001-moves-2.json` 确认缺口不再出现。第一份记录的 `disposition` 由编排方改成 `confirmed_gone → RC-ep001-moves-2`，之后 `check-answers` → 0，`defects build` → 0（12 项，承重 4，无去处 0）。
- 冷读：文档没说怎么只装 events，我手抽成 `.drama/checks/ep001-events.json`（发现 9）。第一次抽出的文件带着 `saysFact`，冷读者自己指出这会泄露 factId。r2 去掉后重做冷读，得到 `retell-ep001-r2.json`。`retell-check … --plan …` → 0，结果是 retold 2、partial 1（I1-f1「第三次」）、missing 0，`closingEvent` partial（关键词判法，复述里其实有关门和茉莉）。
- 可读稿 `runs/ep001/episode-outline-001.md`；离线回执按 writing.md「没有 mali-story 连接」一节手写成 `.drama/receipts/ep001-c4-outline-create-1.offline.json`（`not_sent`），`contract-check remote-receipt` → 0。交接 `run-c4-ep001`（`goal: partially_met`）→ 0。

## 7. C6 集纲侧三读与关口

读：c6-review.md「集纲侧三读」；集纲层 §12「关口」。

- 第一份审读记录 `.drama/reviews/rev-ep001-outline-1.json` 由我汇总，`context: serial_self_review`。
- 第一次 `season-check . --outline 1` → 2，五条失败：`usage-copied`（我抄了同一份用量，是我的错，改成 `source: unknown`）、`outline-characters`、`outline-structure`（发现 10）、`outline-review`（发现 11）、`outline-saved`（发现 12）。
- 重装 C4 包、把 `run-c2` 产出里的声音卡改成 `knowledge_card` 引用后，前三条清掉。另开新上下文写第二份审读 `rev-ep001-outline-2.json`（`independent`），后 `outline-review` 清掉。它又查出两个 C4 问题：母亲「基本不下楼」却自己去买菜（f3），以及 r2 引入的「101 先跳过」没交代原因（f4）。返修预算 1 次已用完，记进 `run-c6-ep001` 的 `unfinished`。
- **最终**：`season-check . --outline 1` → 2，`ruleSet: outline-layer`，只剩 `outline-saved`；`season-check . --outline 1 --allow-offline` → 0，`passed: true`，`outline-saved` 为警告。输出只列失败的规则，七条集纲层规则是否都跑了，从输出看不出来。我把冷读复述移走后再跑，`outline-retell` 失败；移回后又通过，可见规则是在跑的。
- 按 SKILL.md 第 7 步，交付说明里不能写「已按流程完成」：没有真人确认选题，回执是离线 `not_sent`，审读 f3、f4 也没修。

## 发现

严重度：**阻断**＝按文档走不下去；**绕过了**＝按文档走不通，靠猜或改法过去；**小**＝不清楚或不一致，但没挡路。本次阻断 0 条、绕过了 13 条、小 12 条。

### 绕过了

1. **K1 卡用途与 fact_check 装包矛盾。** 集纲层 §6 说 K1 卡 `usage` 取 `comparison_only` 或 `creative_reference`；§5 与 c3a 只说 fact_check 包里的卡不能是 `evaluation_only`。`context-pack --role fact_check` 却拒收 `comparison_only`（「limited to similarity_review/evaluation」）。我只好出 r2 改成 `creative_reference`。位置：outline-layer.md §5、§6；c3a-function-map.md 方法要点第 4 条。
2. **容量命令要语料，新项目没有。** `capacity season`／`episode` 必须给 `--corpus` 或 `--exchange-median-sec`。文档写的是「同类处境语料交换中位时长」，没说新项目从哪拿语料、也没有默认值，我假定了 8 秒。位置：outline-layer.md §8、§12；c3c-season-plan.md。
3. **总账视图不能从 ledgerDeps 生成。** §3 说逐方总时间线「底账写出之前就能从 `ledgerDeps` 生成」，但 `ledger view` 只认带 `entries` 的底账文件（喂功能地图 → 1）。我把 C3b 建账提前到追问之前。位置：outline-layer.md §3「跨前提一致性表」段。
4. **`promptVersion` 的要求前后不一。** `check-answers` 要求回答记录有 `promptVersion`；`contract-check answers` 不要求，随包示例 `answers.json` 也没有，核对方照示例写就过不了。我作为编排方补上。位置：outline-layer.md §5「回答记录」；schemas/examples/answers.json。
5. **`ledger check` 的字段要求比文档和 contract-check 严。** `schema-basic` 要求时间线条目一定有 `didNot` 键（§4 说 `did`／`didNot` 至少一个）；有 `whyNotApplicable` 也还要 `why` 键；`state` 子型要 `knownTo`（§4 子型字段只列 `stateOf`、`state`、`validFrom`、`validTo`）；图谋 `validTo` 为空要登记。`contract-check ledger-entry` 对同一文件是 0。我补了 `null` 值和 `emptyFields`。位置：outline-layer.md §4。
6. **`money-closed` 要一个文档没提的标记。** 报「account 为空且未标 no_trace」。文档只说空字段列进 `emptyFields[]`、照报到有人补上，没有提 `no_trace`。我编了一个 account 值（标「设计，未核」）。位置：outline-layer.md §4「材料没给的，登记不编」。
7. **`--records` 一处收目录、一处不收。** `check-answers --records .drama/checks` → 1（Is a directory）；`defects build --records .drama/checks` 和 `function-map check --rc-dir` 都收目录。§12 两处都写成目录形式。位置：outline-layer.md §12「追问记录」行。
8. **C1、C2 没有装包角色。** `run-handoff.contextSnapshotId` 必须是字符串，但 `context-pack` 的角色表里没有给 C1、C2 的，文档也没说这两个工位怎么装包。我填了 `unknown:…`。位置：workstations/README.md「每次运行的固定协议」第 2 条；c1、c2 工位文件。
9. **冷读包「只装 events」做不到，工具也拦不住。** 文档说冷读包只放本集 `events` 一项，却没说怎么从分集计划里只取 events。`context-pack --role cold_reader` 实测接受整份分集计划（含 `moves`、`infoLedger`、`summary`），它只数项数。我手抽成单独文件，第一次还漏删了拍上的 `saysFact`，等于把 factId 泄露给冷读者。位置：outline-layer.md §9「本集要过的核对」；c6-review.md 三读第 3 条；workstations/README.md 执行层级「冷读包只装一项」。
10. **C4 包要装什么，文档和 season-check 说的不一样。** c4「整季集纲怎么写」第 3 条列的是季编排、底账、功能地图、人物包、前一集计划；`season-check` 的 `outline-structure` 还要 C3 最新运行的全部产出（这里包括媒介档案）。`outline-characters` 要 `run-c2` 的产出与包里的引用一致：我在交接里把声音卡写成 `local_file` 路径，包里却只能按 `knowledge_card` 装（`knowledge/` 不在 `local_file` 允许的目录里），于是对不上。文档没说交接里怎么引用知识卡。位置：c4-episode-outline.md「整季集纲怎么写」第 3 条；workstations/README.md「定向修订单独装包」。
11. **审读记录该由谁写，文档没说。** 三读都由新上下文做了，各留了记录，但 `season-check` 的 `outline-review` 只看 `review-record.context`。由作者汇总的记录只能如实填 `serial_self_review`，于是判「只有作者自审」。我另开了一个新上下文来写审读记录。文档没说集纲侧的 review-record 由三读者之一写、还是由编排方汇总。位置：c6-review.md「集纲侧三读」。
12. **集纲侧的离线做法没写。** writing.md 的离线一节只讲正文。集纲侧没有 mali-story 时，`outline-saved` 必然失败，只有 `--allow-offline` 能过，而这个参数要「用户同意」。这里用户就是演示者自己。位置：outline-layer.md §12「关口」行；c4-episode-outline.md 第 5、6 条。
13. **C4 自己写错的承重缺口没有合适去处。** 三个去处（`confirmed_gone`／`license`／`decision`）都是按 C3a 实现层设计的。分集计划自己写错（102 户没敲门）时，核对方只能在作答当时乱填一个（`license → L-obj-002`），被 `check-answers` 拒。合理的走法是先改计划、再由新上下文复核、回头把去处填成 `confirmed_gone`，但文档没说回答记录的 `disposition` 事后由谁改。位置：outline-layer.md §5「承重缺口的三个去处」、§7。

### 小

14. **跨前提一致性表没有落点。** 没有 schema、没有存放位置，也没有命令核它（§3 说「脚本只核每格有内容」）。我手写成 md，没有任何命令读它。位置：outline-layer.md §3。
15. **`function-map topics` 会出检索不了的题。** 它也归并 `knowledge`、`agenda` 类的 `required_unstated` 断言（如「周敏起初以为多数人同意就行」），但这些没有可检索的对象。§3 第 2 步却要求「每题有卡（查不到的是空卡）」，不清楚这类题要不要写空卡。位置：outline-layer.md §3 第 2 步、§6「输入」。
16. **writing.md 与 README 说的允许目录不一致。** writing.md 离线一节说 `local_file` 只读 `.drama/`、`runs/`，`planning/` 下的文件会被拒；workstations/README.md 和实际工具都允许 `planning/`。位置：writing.md「没有 mali-story 连接」第 1 条。
17. **§11 表第三行「同上」有歧义。** 前提一级的用户给定设定不成立时，「同上」可以读成「按第二行保留并标 `license_pending`」，也可以读成「先看有没有通过核对的候选（第一行）」。而且第 4 步要在追问前定默认，这时还不知道哪个候选能过。我按「保留」走。位置：outline-layer.md §11 表。
18. **勘误「清零」做不到也没人核。** 交接条件写「勘误清零（S）」，但勘误记在核对方的回答记录里，作者改了地图之后记录照旧，`function-map check --stage v1` 也照样通过。不清楚该怎么清零、由谁清。位置：outline-layer.md §1 表、§2「选定规则」。
19. **回答记录的 `outcome` 没什么信息量。** 只要有一条没继承来源的 `notHolds`，不论承不承重，脚本都要求 `fail`，所以只有不承重缺口的候选也拿不到 `pass_with_unverified`（核对方报告）。位置：outline-layer.md §5「`outcome`」。
20. **`move` 对象的记录分不出是哪个动作。** 一份记录覆盖多个 moves 时没有字段指明某一答属于哪个动作，核对方借用了 `targetClause`。同样，前提记录也没有字段说明答的是哪个默认候选。位置：outline-layer.md §5「对象」。
21. **`because` 三个值的边界没定义。** 卡在、但卡上没有这一问的条时，填 `no_card`、`card_says_not_found` 还是 `cannot_answer`，文档没说。位置：outline-layer.md §5。
22. **问题单装不进包。** 问题单在技能目录，不在项目内，没法作为 `local_file` 进 `fact_check` 包，子代理只能另读。位置：outline-layer.md §5；workstations/README.md「定向修订单独装包」。
23. **几个产物没有规定位置。** task、selection、媒介档案、ledger apply 的新修订放哪都没写（我分别用了 `.drama/tasks/`、`.drama/selections/`、`planning/media-profile.json`、`planning/ledger/rev/`）。另外，`init-project` 不建 `runs/`、`knowledge/`、`.drama/runs/`。位置：outline-layer.md §1、§12。
24. **读输出时容易误会。** `status` 把已完成的旧运行标成「未结束」；`ledger view --blank-period` 把 `state` 子型条目放在「（未写 who）」下；`retell-check` 对已复述到的收尾拍判 `partial`，还会提示「readingScope 应只有一项」，可当时本来就只有一项。位置：outline-layer.md §12。
25. **`season-check` 只列失败。** 七条集纲层规则通过时输出里不列出来，要靠反证才能确认它们跑了。`plan-check` 的 `speaker-knows` 在有 `notEvaluable` 时仍报 pass（人物说自己的表态也要一条知识账）。位置：outline-layer.md §12「关口」行。

另记两条演示者自己的错（不算文档问题）：交接用量一律抄成同一个值，被 `usage-copied` 抓到，已改成 `unknown`；把 `context-pack` 的标准输出存进了 `.drama/snapshots/`，`status` 判它是坏快照，已移走。重做冷读包时我还删掉了一个没有被任何交接引用的旧快照，这不合「快照写入后不改」的习惯。

## 复走（文档修订后）

日期：2026-10-15。还是同一个项目 `projects/d62-walkthrough/`，还是只按随包文档（SKILL.md、references/、schema 例子与 `--help`）走。先重读了 [集纲层](../../skills/drama-studio/references/outline-layer.md) 全文、c1／c2／c4／c6 工位文件和 [writing.md](../../skills/drama-studio/references/writing.md) 的离线一节。走完以后才读 [d6-2-decisions](d6-2-decisions.md) §5，拿来对照「原意要修成什么」。

### 结论

- 13 条「绕过了」全部按新文档走通，不再需要原来的绕法。有 4 条留下了小尾巴，记在下面的新发现里（N1、N2、N4、N5）。
- 12 条「小」都已消失。第 18 条要多跑一次新上下文复核才清得掉，复核时又碰到一个格式问题（N3）。
- 关口 `season-check --outline 1`：
  - 不加 `--allow-offline` 时退出 2，只剩 `outline-saved` 一条失败；
  - 加 `--allow-offline` 时退出 0，`ruleSet: outline-layer`，`outline-saved` 降为警告。
  - 两次的 `outlineLayerRules` 七条都是 `passed`，`evaluatedOn` 分别是：`outline-season-assigned`、`outline-ledger-delta`、`outline-capacity`、`outline-reality-refs`、`outline-retell` 为「集纲第1集」，`outline-decision-default` 为「决定队列」，`outline-patch-cap` 为「功能地图与底账」。
- 离线授权的来源要说清：没有远端项目，「只交本地稿」的原话来自编排方（team-lead 代理）的任务消息，不是真人用户。我把它照录进项目的 `PROJECT.md`，并注明了来源。

### 原 13 条「绕过了」逐条

| # | 原严重度 | 复走怎么做（命令 → 退出码） | 原绕法留下的产物怎么处理 | 结果 |
| --- | --- | --- | --- | --- |
| 1 | 绕过了 | `context-pack --role fact_check` 装 r1 卡（`comparison_only`）→ 0（dry-run），`usage` 原样保留 | r2 卡（只改了 `usage`）留着：C3a 的四份回答记录 `cardRevisions` 写的是 r2，撤掉会断引用；内容与 r1 相同 | 通了 |
| 2 | 绕过了 | `capacity season planning/season-plan.json`（不给 `--media`、不给中位时长）→ 0，`basis.status: default_unmeasured`，用的是默认 10.8 秒；各集 66.8–103.2 秒，都装得下；`capacity episode` 第 1 集 38.4 秒；`season-plan-check`（不给 `--media`）→ 0 | 删掉从示例复制来的 `planning/media-profile.json`；季编排去掉「假定 8 秒」的注记，`estimateSec` 按新值重填；分集计划只改了 `capacity` 一栏（30→38.4 秒） | 通了 |
| 3 | 绕过了 | `ledger view planning/function-map.json --blank-period --md` → 0，按线列出 `ledgerDeps` | C3b 提前的顺序已成事实，没有重做；下次可以按 §3 原顺序走 | 通了（小尾巴见 N5） |
| 4 | 绕过了 | 文档 §5 写明 `promptVersion` 必填，随包 `answers.json` 例子也补上了；`check-answers … --records .drama/checks` → 0 | 编排方补写的 `promptVersion` 留着（现在本来就该有） | 通了（小尾巴见 N4） |
| 5 | 绕过了 | 用原写法（不写 `didNot`、有 `whyNotApplicable` 不写 `why`、`state` 子型不写 `knownTo`、图谋 `validTo: null`）跑 `contract-check ledger-entry` → 0，`ledger check` → 0 | `ledger-ep000.json` 撤回这几处补丁字段 | 通了 |
| 6 | 绕过了 | `account: null` 并列进 `emptyFields`，`ledger check` → 0，`money-closed` 通过 | 撤回编造的 account 值，`history` 里记了这次撤回 | 通了 |
| 7 | 绕过了 | `check-answers RC-*.json … --records .drama/checks` → 0 | — | 通了 |
| 8 | 绕过了 | `run-c1`、`run-c2` 改成 `contextSnapshotId: null` 并写 `noSnapshotReason`，`contract-check run-handoff` → 0；反证：C3 运行写 `null` → 2 | 撤掉 `unknown:…` 占位 | 通了 |
| 9 | 绕过了 | `plan-events planning/episodes/episode-plan-001.json --out .drama/checks/events-ep001.json` → 0（去掉了 `picture`、`saysFact`）；冷读包装整份计划 → 2；装导出文件 → 0（`ctx-c713325a3d7f81c9`）；新上下文冷读得到 `retell-ep001-v2.json`；`retell-check` 结果是 retold 2、partial 1、missing 0，收尾拍 retold | 删掉手抽的 `ep001-events.json` 和基于它的两份复述 | 通了 |
| 10 | 绕过了 | C4 选材按 §1 三件（季编排、`ledger-ep000.json`、功能地图），声音卡用卡片项装，不再装媒介档案，`context-pack --role author` → 0（`ctx-209da066b15b22ac`）；反证：缺功能地图 → 2；`run-c2` 的产出改回 `knowledge/cards/<id>@r1.json` 路径写法，`outline-characters`、`outline-structure` 都通过 | `run-c4-ep001` 换用新快照，旧快照列进 `additionalSnapshotIds` | 通了 |
| 11 | 绕过了 | 只留新上下文写的 `rev-ep001-outline-2`，`outline-review` 通过 | 删掉作者汇总的 `rev-ep001-outline-1`（按 §1 它不算审读）；`rev-2` 的 `readingScope` 里还引着它，成了悬空引用 | 通了 |
| 12 | 绕过了 | 按 §1「离线」把同意只交本地稿的原话记进 `PROJECT.md`，回执仍是 `not_sent`；`season-check --outline 1 --allow-offline` → 0（警告） | — | 通了（`season-check` 不核 `PROJECT.md` 里有没有原话，这一条是 M） |
| 13 | 绕过了 | 按 §5「作者自己写错的承重缺口」回填：`disposition` 加 `backfilledBy`，`check-answers` → 0；反证：`ref` 指向本记录 → 2，复核记录对同一 `defectKey` 仍判 `notHolds` → 2 | — | 通了（小尾巴见 N2） |

### 原 12 条「小」

全部消失：14、16、17、19、21 改在了文档里；15 现在 `function-map topics` 只出 5 题，另报 `notSearchable: {agenda: 1, knowledge: 1}`；20 的 `target.ids` 与 `subject` 在勘误复核里用上了；22 的问题单能按 `question-set:reality-check-questions@v1` 装包；23 的 `init-project` 现在会建 `runs/`、`knowledge/`，各类产物也都有了规定位置（底账新修订改放 `planning/ledger/ledger-ep001.json`）；24 的 `status` 改标「已结束、留有未完成项」，空白期视图的 `state` 子型归到孙老师名下，`retell-check` 收尾拍判 retold；25 的 `outlineLayerRules` 七条都列出来了，`speaker-knows` 报 `pass_with_not_evaluable`。

第 18 条要做的事比原来多：按 §2，勘误要另一份新上下文的复核记录在 `errataConfirmed` 里确认，作者改了地图不算。于是 `function-map check --stage v1` 先退出 2，列出三条没确认的勘误。另开一个新上下文写了 `RC-errata-1.json`（`ctx-e71b9f6b2dea84d5`），之后 → 0（见 N3）。

### 第 1 集独立审读查出的两个 C4 问题

这两个问题是 f3（母亲「基本不下楼」却自己拎菜爬楼）和 f4（「101 先跳过」没有可见理由）。处理按文档：

1. **不修。** C4 的返修预算 1 次已经用在 102 缺口上，按工位契约 C4 属于「其他层」，触顶后「交付未达标候选并写明瓶颈」。所以计划不改，`run-c4-ep001` 的 `unfinished` 写明瓶颈，`task` 的 `goal` 记 `partially_met`。
2. **登记。** 按 §10「运行交接里的 `changeProposals` 用 `decision add --from-handoff` 登记」，`run-c6-ep001` 的 `changeProposals` 合并成一条：`kind: other`，两个选项是 `deliver_as_is`（默认）和 `extra_revision`（追加 1 次 C4 返修），`needsDecision: true`。`decision add --from-handoff` → 0，登记为 `DQ-run-c6-ep001-1`；`decision check` → 0。
3. **计划引用。** 按 §10「受影响的分集计划在 `pending[]` 引用条目」，第 1 集 `pending` 补引这一条，事件内容不改。`plan-check` → 0。

一开始我按 README 理解，以为「交付未达标」只写交接就行，`needsDecision: false` 的提案也被 `from-handoff` 跳过了（`skipped`）。追加预算要不要算「等人定的事」，文档没明说（N7）。

### 复走中的新发现

| # | 严重度 | 发现 | 位置 |
| --- | --- | --- | --- |
| N1 | 小 | §12「C4 应用 delta」一行说规则用 `ledger check <新修订> --delta <delta>` 核，但新修订里已经应用过这份 delta，再应用一次报 `delta-applies` 失败（新条目 id 冲突）。实际能用的是 `ledger check <入口修订> --delta <delta>`（c6 三读的写法），或 `<新修订>` 不带 `--delta` | outline-layer.md §12 |
| N2 | 小 | 文档说回填的 `disposition` 要带 `backfilledBy`，并标为 `check-answers` 核（S）。实测缺 `backfilledBy` 也通过；另外两条（`ref` 不能指本记录、复核不能仍判 `notHolds`）确实会拦 | outline-layer.md §5「作者自己写错的承重缺口」 |
| N3 | 小 | 勘误复核记录至少要有一条 `answers`，而且题号必须在问题单里，可问题单没有「勘误是否已改」这一问。核对方只好借第 14 问（信息题）占位，真实结论写在 `errataConfirmed` 里 | outline-layer.md §2「选定规则」末条；answers schema |
| N4 | 小 | `contract-check answers` 对缺 `promptVersion` 的记录仍是 0，`check-answers` 判错。两个命令对同一份记录结论不一样；照例子写就不会踩到 | outline-layer.md §5「回答记录」 |
| N5 | 小 | §3 说逐方总时间线「就是 `ledger view --blank-period` 的总账视图，底账写出之前就能从 `ledgerDeps` 生成」，但 C3a 阶段的视图是按线列的、不分「方」，工具输出自己也这么说明。文档措辞与输出对不上 | outline-layer.md §3「跨前提一致性表」段 |
| N6 | 小 | `check-answers --records <目录>` 会读目录里所有 `.json`。我把它的输出重定向进同一目录，shell 先把文件清空了，命令读到一个空 JSON 就退出 1。文档没说输出该放哪，也没说目录里放了别的 JSON 会怎样 | outline-layer.md §12「追问记录」行 |
| N7 | 小 | 修订预算用完后的审读意见怎么办，文档说法不统一：工位契约写「交付未达标候选并写明瓶颈」，§10 写交接里的 `changeProposals` 都用 `from-handoff` 登记。追加预算算不算等人定的事（`needsDecision`）、进不进决定队列，没写 | workstations/README.md「返修上限按层解释」；outline-layer.md §10 |
| N8 | 小 | 冷读者问 `present` 指的是有名有姓的出场人，还是所有在场的人（1-2 场敲了十来户门，`present` 只列了两人）。§9 的字段说明没写 | outline-layer.md §9 第 4、5 行 |
| N9 | 小 | 一份为了绕过而出的卡修订（r2 只改了 `usage`）该怎么撤，文档没说。`processing: retired` 会让整张卡退出检索；撤掉 r2 又会让已经引用 r2 的 `cardRevisions` 悬空。我把它留着了 | workstations/README.md「知识库目录与命令」 |

新发现阻断 0 条、绕过了 0 条、小 9 条。

### 对照 d6-2-decisions §5

25 条的裁定都落实了，复走中做出来的效果与原意一致。和原文措辞有出入的几处：

- 第 5 条原定「额外规则（如 `state` 子型要 `knownTo`）逐条写进 §4」，实际做法是取消 `knownTo` 要求，§4 第 3 条写明「不要求 `knownTo`」。两种做法都消除了矛盾。
- 第 13 条原定 `check-answers` 接受回填，这一点做到了；文档另外加的 `backfilledBy` 要求，工具没有核（N2）。
- 第 18 条的复核走的是 `errataConfirmed`，与原意一致；只是复核记录的格式要借题占位（N3）。

### 演示者自己的问题（复走时补记）

- 交接里的 `finishedAt` 都是我拟的时间（如 `2026-10-15T12:00:00+08:00`），比实际运行时刻（本机约 03:30 CST）晚，不是实测值。`status` 按它判「最近运行」，顺序碰巧没错，但这个字段不可信。
- 复走时删了作者汇总的 `rev-ep001-outline-1` 和三份基于手抽 events 的冷读文件。这些都是原绕法的产物，但 `rev-2` 的 `readingScope` 还引着 `rev-1`。
