# D6-3 报告：切换台词层并退役台词遍／台词读（0.6.0）

依据：[统一实施计划](../design/drama-studio-outline-dialogue-implementation-plan-2026-10-14.md) §4.4；[D6-3 共用决定](d6-3-decisions.md)。日期 2026-10-15。分支 `feat/d6-3-dialogue-layer`。

本页只放编号与统计，不含任何项目的剧情、人物、台词或卡片原文。本地验收用的真实产物在项目目录里，不随仓库分发。

## 结论

§4.4 的 S 验收 8 项全部满足（见第一节）。退出条件也满足：0.6.0 可安装，`writing.md` 的工位流程不再以「台词遍」「台词读」作步骤。M 项证据有 D6-0 第 6A 集的 g1 冷读与问题单记录，以及走通演示一份：阻断 1、绕过了 7、小 13，按决定 §6 处置，工具流的 15 条都已实施（见第六节）。

- 全量 unittest：904 项全过。D6-2 结束时是 830 项，本阶段新增 74 项。改了期望的旧测试有 8 项，各改一处，原因见第三节。
- 本地验收总表：342 行，没有未解释的不一致（第四节）。
- 《渊心锁》与本项目旧记录：
  - 带 `--legacy-dialogue` 时，`season-check` 输出与 0.3.6 字面逐字节一致（12 组参数）。
  - 不带时，旧三条不出现，也没有新失败（10 组参数）。
- `validate.py`：剩 9 条错误，都是 docs 里指向 mali-story 仓库的既有外链，随包检查通过。

## 一、§4.4 验收逐条

复现命令都在仓库根目录运行。本地验收的总入口是 `python3 -B scripts/d6_acceptance/run.py`，D6-3 段是 `scripts/d6_acceptance/d63.py`。

| # | 验收项 | 层级 | 结果 | 复现 |
| --- | --- | --- | --- | --- |
| 1 | `validate.py` | S | 满足：9 条既有外链错误，没有新增 | `python3 -B scripts/validate.py` |
| 2 | `test_skill_routing` | S | 满足：12 项。原有 1 项的 needle 按退出条件改了（第三节），新增 2 项：`writing.md` 工位流程的步骤里不再出现台词遍、台词读；工具表的 `season-check` 行写明 `--legacy-dialogue` | `python3 -B -m unittest tests.test_skill_routing` |
| 3 | `season-check --episodes` 对 D6-0 第 6 集记录（搬成项目记录形态）全过 | S | 满足：`episodeRuleSet: dialogue-layer`。13 条台词层规则里，有记录可核的 9 条全部 passed；按运行判的 3 条在没有运行交接时为 not_evaluated；`preserved-human-source` 没有审读记录可核，也是 not_evaluated。另做 6 个变异，每个只触发对应的一条规则。旧的工位交接规则（upstream、c4、author）不过，记为有解释的差异：D6-0 没有留运行交接，没有补造 | `run.py` 的 d63 段 |
| 4a | 本项目第 1–10 集旧记录在 `--legacy-dialogue` 下与 0.3.6 一致 | S | 满足：两个项目，凡带 `--episodes` 的参数都加上 `--legacy-dialogue`，与 `git archive main`（0.3.6）逐字节比对，共 12 组都相同 | `run.py` 的 legacy lock |
| 4b | 不带该参数时旧三条不出现、没有新失败 | S | 满足：10 组都满足。本项目比 0.3.6 少了 `voice-card` 的 10 条失败，是有意的 | `run.py` 的 legacy no-flag |
| 5 | `contract-check task` 拒绝「少 40 字」「不超过 3 行」 | S | 满足（`constraint-blocklist` v3） | `python3 -B -m unittest tests.test_d63_tools` |
| 6 | 修订单扫描拒绝 SPEAKER 格式行 | S | 满足：新对象 `revision-list`。`contract-check revision-list` 拒替换台词与数值指令；`season-check` 的 `fixlist-no-lines` 用同一个扫描。D6-0 第 6A 集修订单能过 | `tests.test_d63_tools`；`run.py` 的 d63 段 |
| 7 | `context-pack --role author`（C5b）在对话表没过 `contract-check` 时退出码 2 | S | 满足：合成夹具上测过；用真实对话表去掉 `infoLedger` 后也测过 | 同上 |
| 8 | `retell-after-revise` 在修订后缺复述记录时失败 | S | 满足：有冷读运行时按运行先后判；只有记录时，正文复述的 `target.file` 不是最终稿就失败 | `tests.test_d63_tools`、`tests.test_season_check_d6` |
| M | D6-0 的 g1 冷读与问题单记录 | M | 证据：项目目录 `runs/pilot-v2/r15/retell-ep006A-g1-a.json`、`retell-ep006A-g1-b.json`、`check-ep006A-g1-a.json`、`check-ep006A-g1-b.json`。d63 段把它们搬进项目后，`cold-retell`、`situation-check`、`consistency-record` 都 passed。走通演示：[d6-3-walkthrough.md](d6-3-walkthrough.md)（第 1 集，C5a → C5b → 五读 → 修订 → 关口），处置见第六节 | `run.py` 的 d63 段 |
| 退出 | 0.6.0 可安装；`writing.md` 不再以台词遍、台词读作步骤 | S | 满足：`install.py install/verify --skills-dir <临时目录>` 核过 131 个文件；步骤由 `test_skill_routing` 核 | `run.py` 的 release 行 |

## 二、各流交付

| 流 | 交付 | 测试 |
| --- | --- | --- |
| 方法文档流 | `dialogue.md` 改名为 `dialogue-structure.md`（按决定 §4 的十二节）；`writing.md` 工位流程第 4–7 步、第 10 步与离线一节；`approval-flow.md`、`character-emotion.md`、`creative-loop.md` 的引用。逐条内容见该流回报 | 由 `test_skill_routing` 核步骤 |
| 工位文档流 | `c5-screenplay.md` 拆成 `c5a-dialogue-plan.md`、`c5b-text.md`；`c6-review.md` 加正文侧两读与设计依据一致性；`season-run.md`、`c2-characters-world.md`、工位索引。逐条内容见该流回报 | 由 `test_skill_routing` 核索引 |
| 工具流 | 见下表 | `test_d63_tools` 37 项，`test_d63_walkthrough_fixes` 35 项，`test_skill_routing` 新增 2 项 |

工具流的改动：

| 范围 | 改动 |
| --- | --- |
| 共用判据 | `season_check.dialogue_project`：`planning/` 或 `.drama/` 下任意深度有带 `dialogue-plan` 标记的 JSON（`.drama/cache`、`.drama/snapshots` 不算）。它与 `outline_project` 并列，`season-check` 也用同一次扫描读对话表 |
| season-check | 新增 `--legacy-dialogue`：旧三条只在带它时跑，这时输出与 0.3.6 相同；不带时输出记 `legacyDialogueRules: not_run …`。台词层规则共 13 条，列在 `dialogueLayerRules`，比 D6-1 多了 `preserved-human-source`。没有 C5 运行交接的集也按记录核台词层规则。`retell-after-revise` 能按记录判。`record_episode` 认字符串形式的 `target` |
| context-pack | 样本进单独的 `samples` 分区（`context-snapshot`、`selection` 的枚举都加了）；只收遮蔽后的样本记录，带原始 `lines` 的转写行或没有 `maskedLines` 的行是输入错误。`--exemplars` 可以给单独的 JSONL，也可以直接给对话表：这时读其中 `exemplars.positives` 的遮蔽样本记录，按各自在文件里的字符区间装包，同样只收这四类字段、同样按句数上限。`--quotes-per-topic`：一个话题所有样本的 `maskedLines` 合计上限，默认 2，可设 0；会超出的样本整条不装，列进 `omitted`（`reason: quote_cap`，枚举新加）。装包历史写进 `.drama/packs/history.json`，相邻两集装了同一条样本时只报不拦。`samples` 分区只能出现在 C5a、C5b 的包里。C5a、C5b 的装包门槛 D6-1 已有 |
| 新对象 | `revision-list`（修订单：不写替换台词、不下数值指令；`where`、`cites` 等定位字段不扫，「本轮不改：…」这类说明标签不算台词行）。`plan-text-map`（C5b 的对照表：`exchangeToLines` 指到的行要标同一个交换，逐字采用的行要进 `verbatimFrom` 汇总） |
| 契约 | `review-record.preserved` 的项可以写成对象 `{item, noteId|humanWords}`，对象项没有来源就拒；纯字符串是旧写法，`contract-check` 仍放行，台词层项目由 `preserved-human-source` 判失败。集纲侧同一规则：审读对象在 `planning/episodes/` 下的 review-record（即分集计划的审读），`contract-check review-record` 直接拒纯字符串项，与「finding 须带 cites」那条放在一起；旧项目的审读对象不在这个目录，不受影响 |
| 其他 | README 有 D6-3 一节；第 247 行旧三条改写；VERSION 改为 0.6.0；`SKILL.md` 工具表的 `season-check` 行 |

## 三、改了期望的旧测试（8 项）

规矩是只增测试、不改旧期望。下面 8 项是 D6-3 的决定本身改了行为，每项只改一处，测试里都有注释。

| 测试 | 原期望 | 新期望 | 依据 |
| --- | --- | --- | --- |
| `test_season_check` 声音卡用例 | 不带参数就报 `voice-card` | 加 `--legacy-dialogue` 才报 | 决定 §2 |
| `test_season_check` 台词遍用例 | 不带参数就报 `dialogue-pass` | 加 `--legacy-dialogue` | 决定 §2 |
| `test_season_check` 台词读用例 | 不带参数就报 `dialogue-read`；`--skip-dialogue` 记 `dialogueChecked: false` | 都加 `--legacy-dialogue` | 决定 §2 |
| `test_season_check_d6` 没有对话表时跑旧三条的用例 | 默认跑旧三条 | 加 `--legacy-dialogue` | 决定 §2 |
| `test_skill_routing` 工位流程的 needle | `dialogue_author`、`dialogue_read` | `dialogue_designer`、`cold_reader`、`situation_checker` | 计划 §4.4 退出条件 |
| `test_d62_tools` 分集计划审读的 cites 用例夹具 | 随包例子的 `preserved` 是纯字符串 | 改成带 `noteId` 的对象；原有断言不变 | 集纲侧 preserved 同一规则（工位文档裁定） |
| `test_season_check_d6` 修订单写台词的用例夹具 | 修订单里写「大凤：…」判 `fixlist-no-lines` | 改成对话表里的说话人「老陈：…」 | 决定 §6 #8：有本集人物名单时只认名单里的名字 |
| `test_context_pack_d6` 样本夹具 | 样本行是带 `lines` 的转写 | 改成遮蔽后的样本记录（每条一句 `maskedLines`）；原有断言不变 | 决定 §1（计划 §8 #2） |

## 四、本地验收总表（run.py 最终输出）

| 段 | 通过 | 有解释的差异 | 跳过 | 不一致 |
| --- | --- | --- | --- | --- |
| A schema（209 行） | 97 | 110 | 2 | 0 |
| B 底账与计划（25 行） | 21 | 4 | 0 | 0 |
| C 容量与核对（27 行） | 25 | 2 | 0 | 0 |
| D 语料（9 行） | 9 | 0 | 0 | 0 |
| d62 集纲层产物搬运（15 行） | 12 | 3 | 0 | 0 |
| d63 台词层记录搬运（22 行） | 21 | 1 | 0 | 0 |
| E 集成（35 行） | 35 | 0 | 0 | 0 |

和 D6-2 报告的差别：

- **d63 段是新加的。**
  - 搬了 17 个文件：12 个逐字节复制。
  - 另 5 个是重跑转换：这 5 份是 D6-0 临时脚本的输出，正式命令认不出（`reproduceCommand` 指向临时脚本，或没有集号字段）。我用正式命令按相同输入重跑，每份都与 D6-0 记录比过，结果都相同。
  - 唯一 1 行差异是旧的工位交接规则，见第一节 #3。
  - 有 1 行用第 6A 集对话表 v2.1 直接作 `--exemplars` 给 C5b 装包：装了 5 条样本，1 条因句数上限整条不装（这一话题两条正例的遮蔽句合计会超过 2 句），各话题装进的遮蔽句都不超过 2 句。
- **E 段多了 10 行：**锁定段拆成带参数与不带参数两种。
- **B 段 knows 那行的解释多了一类：**图谋账的主人现在算知道自己的图谋（决定 §6 #3）。

## 五、D6-3 期间修的两处规则问题

都是在 D6-0 真实记录上发现的，带测试修好：

1. `fixlist-no-lines` 原来扫修订单里所有字符串，`where` 字段的「g1:L44」被当成台词行。改为不扫定位字段，并把「本轮不改：…」这类说明标签排除在台词行之外。
2. `record_episode` 不认字符串形式的 `target`，D6-0 修订单的 `target` 是文件路径。现在也认。

## 六、走通演示

证据：[d6-3-walkthrough.md](d6-3-walkthrough.md)（同一项目接 D6-2 演示，第 1 集，C5a 对话表 → C5b 正文 → 五读 → 修订 → 关口）。发现 21 条：阻断 1、绕过了 7、小 13。裁定在 [决定 §6](d6-3-decisions.md)；下表只列去向与本流（T）的做法，M、W 项的落实见两流回报，本页不逐条核。各 T 项都在 `tests/test_d63_walkthrough_fixes.py` 里有正反测试。

| # | 去向 | 本流实施（T） |
| --- | --- | --- |
| 1 | T＋M | 台词目标 `corpusManifest: null` 时，`dup-two-tier` 的 13 字全库档记 not_evaluable（`perEpisode.<n>.dupTwoTier`），不算失败；8 字档只在对话表引用了语料正例时才要 |
| 2 | T＋M | `dialogue-target.corpusManifest` 可为 `null`，此时必须写 `noCorpusReason`（契约规则） |
| 3 | T | `ledger knows`（含按场的 `--episode-plan`）把图谋账算作其主人（`party`，或 `who`）知道；`validFrom` 晚于所查集的不算。验收段 knows 行因此多出图谋条目，记为有解释的差异 |
| 4 | M＋W | — |
| 5 | M＋W | — |
| 6 | T | `consistency-record` 按处境对照的 `target.file` 分组：只有同一稿有两份以上时才要一致性记录 |
| 7 | M＋W | —（有意：启用台词层后旧审读记录照新规则核） |
| 8 | T | 修订单扫描在 `season-check` 里用本集人物名单（对话表交换的 `speaker`、对照表的 `speaker`），只有「名单里的人名：」开头才算台词；没有名单时（`contract-check revision-list`）退回启发式，标签词加「照表」「按表」 |
| 9 | T＋M | 题材禁词表按 id 进包：`{"kind":"local_file","id":"lexicon:genre-lexicon@v1"}`（`genre-lexicon.json` 补了 `id`、`version`） |
| 10 | M＋W | — |
| 11 | T＋W | `review-record` 的 finding `layer` 加 `C5a`、`C5b`，`C5` 保留 |
| 12 | T＋M | 对话表交换上的 `interruptedAt`（被打断的交换 id），`plan-text-consistency` 的 `interrupted-by` 读它（旧写法 `interruptedBy.at` 照读）；随包 `plan-text-consistency` 例子改为 `--dialogue-plan` 与 pass／fail |
| 13 | T＋M＋W | 首读封存可写在记录自己的 `sealedSha256`（去掉该字段后的规范 JSON 的 sha256），`.sha256` 旁注文件照认；台词层项目里首读、次读只认审读对象（`target`／`additionalTargets`）是本集正文的记录，集纲侧审读不再被当成未封存的首读 |
| 14 | T＋M | 处境对照：一答可同时有 `landsOn` 与 `quoteRef`，判了三态的答要有 `quoteRef`，`n/a` 不必引句；对话问题单加 `defectKinds` 词表，`check-answers` 对词表外的类只报不拦；`target.kind` 本来就不限值，`topic` 可用 |
| 15 | T＋M | `retell-record.events[]` 可带 `sourceLine`（`{line, quote}` 或字符串）与 `sourceKind`（`dialogue`／`action`／`heading`） |
| 16 | M | — |
| 17 | T＋M | `dialogue-target.mediaProfile` 可为 `null`（用随包默认档案）；版本字段是 `revision` |
| 18 | T＋M | 对照表 `lineToPlan[].kind` 限定为 `title`／`scene`／`cast`／`action`／`dialogue`／`other`；D6-0 的两份对照表仍过 |
| 19 | T | `episode-check` 场头的时间词可带日期前缀与先后后缀（「次日晚」「次日晚稍后」「当天傍晚」） |
| 20 | T | `capacity text` 输出 `targetSec` 与 `targetSecSource`，优先级：`--target-sec`（argument）＞ `--episode-plan` 的 `capacity.targetSec`（episode_plan）＞ 媒介档案的 `targetSecondsDefault`（media_profile；不给 `--media` 时是随包默认档案，default_media_profile） |
| 21 | W＋T | 集纲侧同一规则：审读对象在 `planning/episodes/` 下的审读记录，`contract-check review-record` 拒纯字符串 `preserved` 项 |

在演示项目的副本上把台词目标改成 `corpusManifest: null` 并写 `noCorpusReason` 后，`season-check --episodes 1 --allow-offline` 通过，`dup-two-tier` 的 13 字档记 not_evaluable。

**复走（文档修订后，同一文件末节「复走」）。**阻断 1 条与 7 条绕过全部按新文档走通，13 条小发现都消失；关口 `season-check --episodes 1 --allow-offline` 退出 0（离线同意来自编排方，复走记录已注明）。复走另有 4 条小发现：

| # | 去向 | 处置 |
| --- | --- | --- |
| N1 | 工具流 | 无语料时 `dialogueLayerRules` 的 `dup-two-tier` 仍写 `passed`，旁边加 `notEvaluatedTiers: ["13"]`、`notEvaluatedTiersOn`（哪几集）与原因；有语料时没有这些键 |
| N2 | 工具流（文档流随后写） | `run-handoff` 加可选 `decisionRefs[]`（执行的决定队列条目 id）；`contract-check run-handoff --decisions <决定队列>…` 核引用存在，不给 `--decisions` 时记在 `notEvaluated` |
| N3 | 工具流 | `interrupted-by` 改判法：被打断的交换写 `interruptedAt`，话题的 `interruptedBy.by` 写谁打断；该交换之后正文第一条对白是打断者的即可，被打断的人不必说完（没写打断者时，只要求不是被打断的人接着说）。旧写法 `interruptedBy.at`／`atExchange` 照读。演示项目上原来 notEvaluable 的那一处现在核过、无报告 |
| N4 | 方法流（已改）＋工具流 | 方法流已在 §12 命令速查写明 `--episode-plan`；工具侧即 #20：`capacity text` 的目标秒数按 `--target-sec` ＞ `--episode-plan` 的 `capacity.targetSec` ＞ 媒介档案取，输出 `targetSecSource`，演示里给 `--episode-plan` 已报 120 秒 |

## 七、留给 D6-4 的事

见计划 §4.5 与 [决定 §5](d6-3-decisions.md)：

- 语料 `fetch`。
- `feedback-ingest` 的派生物。
- `writer-style-brief.md` 经回流后退役（本项目的事）。
- 遮蔽后样本记录的生成：本阶段 `context-pack` 只收这种记录，生成它们不在本阶段。

## 八、局限

- **走通演示是同一个演示者在同一个编造项目上走的第 1 集，**而且没有语料，样本、8 字装包档、遮蔽句上限都没有在演示里用到。复走只核了原发现与新加的修正，复走后的 N1–N3 修正没有再走一遍。
- **台词层规则只在一集的 D6-0 记录上跑过，**而且没有运行交接，按运行判的 3 条在真实数据上没有被核过；正反例来自合成夹具。
- **「遮蔽原句每话题 ≤2」按样本记录里的 `maskedLines` 计。**遮蔽做没做对、原句有没有逐字进正文，脚本不判（正文侧另有 `dup-check --list-hits` 两档）。
- **说明标签的排除是一张词表，属启发式。**人物名里含「改」「不」这类字时，会漏判为说明标签。
- **`preserved-human-source` 只在台词层项目判。**旧项目的纯字符串 `preserved` 照旧通过 `contract-check`。
