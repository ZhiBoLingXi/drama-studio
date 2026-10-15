# D6-4 报告：语料库与反馈回流（0.7.0）

依据：[统一实施计划](../design/drama-studio-outline-dialogue-implementation-plan-2026-10-14.md) §4.5、§7；[D6-4 共用决定](d6-4-decisions.md)。日期 2026-10-15。分支 `feat/d6-4-corpus-feedback`。

本页只放编号与统计，不含任何项目的剧情、人物、台词、批注或语料原文。本地验收用的真实产物在项目目录里，不随仓库分发。

## 结论

§4.5 的 S 验收全部满足（见第一节）。退出条件按小样本那一支满足：0.7.0 可安装；计费没有确认（本阶段没有 mali-story 连接），D6-4 以现有小样本（3 部）结束，全库、补语料、计费确认列为待办，见 [d6-4-corpus.md](d6-4-corpus.md)。

- 全量 unittest：922 项全过。D6-3 结束时是 904 项，本阶段新增 18 项（`tests/test_d64_tools.py`）。改了期望的旧测试有 3 项，各改一处，原因见第三节。
- 本地验收总表：350 行，没有未解释的不一致（第四节）。
- `validate.py`：剩 9 条错误，都是 docs 里指向 mali-story 仓库的既有外链，随包检查通过。
- `install.py install/verify --skills-dir <临时目录>`：0.7.0，核过 136 个文件。

## 一、§4.5 验收逐条

复现命令都在仓库根目录运行。本地验收的总入口是 `python3 -B scripts/d6_acceptance/run.py`，D6-4 段是 `scripts/d6_acceptance/d64.py`。

| # | 验收项 | 层级 | 结果 | 复现 |
| --- | --- | --- | --- | --- |
| 1 | `corpus` 各子命令夹具可复算 | S | 满足：新子命令 `agree`、`defaults`、`fetch` 各有夹具测试；d64 段在 D6-0 小样本上复算 `agree` 与 `defaults`，结果与随包数据和 D6-0 盲标记录相同；`fetch` 在编造台账上走完 plan → budget → record → budget → verify | `python3 -B -m unittest tests.test_d64_tools`；`run.py` 的 d64 段 |
| 2 | 双跑不一致记 `low`，`low` 不进检索结果 | S | 满足：`corpus agree --out` 给不一致的交换写 `labelConfidence: low` 与 `quality.label: low`；`corpus filter` 新加原因 `label_low`，这些交换不进通过名单 | `tests.test_d64_tools` 的 `CorpusAgree` |
| 3 | 带项目句子的 studio 记录被拒 | S | 满足：`origin.kind` 不是 `mali_story_template` 的 studio 交换（D6-1 已有）、`feedback-ingest` 派生的 studio 对照对、studio 的编剧批注都被 `contract-check` 拒 | `FeedbackRouting.test_contrast_pair_drafts_pass_contract_check_and_studio_ones_do_not` |
| 4 | 编造的批注与编造的「这个程序不是这样走的」各有正确去向 | S | 满足：前者进反例（`negatives.jsonl`），后者判为程序／事实类，进底账修订提案（`ledger-proposals.jsonl`）与 K1 草稿；现实审查里判不成立的程序类回答走同一路 | `FeedbackRouting` 前三项 |
| 5 | 无来源条目不进包 | S | 满足：`context-pack` 遇到没有 `provenance` 也没有 `fromNotes` 的对照对，按输入错误拒装 | `UnsourcedNotPacked` |
| 6 | `dialogue-target` 升版有 changelog，引用旧版的 `task` 仍通过 | S | 满足：`feedback-ingest --target` 写新版（如 v0.1 → v0.2），新约定 `status: drafted`，changelog 记 `from`、`by`、`noteIds`；`contract-check dialogue-target` 要求 changelog 里有本版一条（新旧顺序都认，D6-0 的记录是新的在前）；引用 v0.1 的 task 仍过 | `TargetRevision` |
| 7 | 计费观察记在 `d6-4-corpus.md`，只有调用次数、预算读数、回执 ID | S | 满足：[d6-4-corpus.md](d6-4-corpus.md)。本阶段远端调用 0 次；D6-0 小样本 11 次读取（失败 3），预算 `unconfigured`／`null`，回执无，计费未确认 | — |
| 退出 | 0.7.0 可安装；计费未确认时以小样本结束并列待办 | S | 满足：见结论 | `run.py` 的 release 行 |

计划 §4.5 交付物里的「补语料」本阶段没做（要远端取用），列入 [d6-4-corpus.md](d6-4-corpus.md) 待办。`speakerAttributionSuspect` 是 D6-1 已有的 `corpus label` 标记，本阶段没改。

## 二、各流交付

工具流（本流）的改动：

| 范围 | 改动 |
| --- | --- |
| `corpus fetch` | 新子命令，只记账、不联网：`plan`（取用计划，默认 3 部各 10 集，带 `expectedSnapshotId`；不覆盖已有台账）、`record`（一次调用的结果、尝试次数、快照核对 `match`／`snapshot_mismatch`／`not_evaluable`、响应指纹）、`budget`（预算读数与当时的回执 ID）、`resume`（断点清单：未取、待重试、放弃，默认最多 3 次）、`verify`（计费 `deduction_seen`／`no_change_seen`／`unconfirmed`；有扣费迹象或快照不符退出 2，提示停下、不取全库） |
| `corpus agree` | 新子命令，双跑比对的 S 部分。按 `schemas/data/corpus-label-vocabulary.json`（新数据文件，`source: assumed`）收敛：功能词同组算一致，关系一方是另一方的上位时算一致并取更具体的那个，infoMode 有交集算一致。三项都一致为 `high`，否则 `low`。`--out` 写带 `labelConfidence` 的副本，不改输入 |
| `corpus filter` | 新排除原因 `label_low` |
| `corpus defaults` | 新子命令：从语料重算媒介档案默认值（与 `corpus rate` 同一公式）与按格式的交换中位时长，都标 n；按题材禁词表统计每个词在本题材与其他题材的出现，给出语料确认的词与候选新词，并与随包文件比对。候选词可能含系列专有词，只写进 `--out`，标准输出只报个数 |
| 随包数据 | `default-media-profile.json`：各格式加 n，交换中位时长分格式记（见第五节）；`genre-lexicon.json`：每张表加 `measured` 块（n、确认数、未见数、其他题材出现的词、能否评估）。两份都只放统计量与词表 |
| `feedback-ingest` | 全路由（§2.2 #9）。输入新认三种：按 `###` 分节的批注文件（`--section` 取一节）、带「→」的修改对照表、回答记录目录（判不成立的程序类回答进程序／事实类）。`--out` 写派生物：反例、人写正例、对照对草稿、约定草稿、问题草稿、底账修订提案、K1 草稿、决定队列，每行带 `fromNotes`、`status: drafted`、`scope.level: project`；同一类问题反复出现时出约定与问题草稿。`--target` 写台词目标的新版。`--purge <note id>` 按 note 清除派生物。`--out` 不能是非空目录 |
| `context-pack` | 无来源的对照对拒装（验收 #5）；样本文件可放的目录加项目根下的 `corpus/`（决定 §2），`runs/…/corpus/` 照旧可读 |
| `contract-check` | `dialogue-target` 的 changelog 规则（验收 #6） |
| 其他 | `drama_tools.py` 的 `corpus` 子命令表；README 0.7.0 一节；`SKILL.md` 工具表的 `feedback-ingest`、`corpus` 两行；VERSION 0.7.0 |

方法文档（`references/corpus.md`、`mali-story.md` 等）由文档流交付，逐条内容见该流回报。

## 三、改了期望的旧测试（3 项）

每项只改一处，测试里都有注释。

| 测试 | 原期望 | 新期望 | 依据 |
| --- | --- | --- | --- |
| `test_drama_tools_d6` 未知 corpus 子命令 | `corpus fetch` 是未知子命令 | 改用 `corpus nope`；`fetch` 现在存在 | §4.5 交付 `corpus fetch` |
| `test_d62_walkthrough_fixes` 漫剧没有中位时长 | `--format anime` 输入错误 | `anime` 读到实测 12.0 秒（n=31）退出 0；随包档案里没有的格式（`radio`）仍是输入错误 | 决定 §3：媒介档案由语料重算 |
| `test_context_pack_d6` 对照对夹具 | 对照对不带来源 | 夹具加 `provenance`；原有断言不变 | 验收「无来源条目不进包」 |

## 四、本地验收总表（run.py 最终输出）

| 段 | 通过 | 有解释的差异 | 跳过 | 不一致 |
| --- | --- | --- | --- | --- |
| A schema（209 行） | 97 | 110 | 2 | 0 |
| B 底账与计划（25 行） | 21 | 4 | 0 | 0 |
| C 容量与核对（27 行） | 25 | 2 | 0 | 0 |
| D 语料（9 行） | 9 | 0 | 0 | 0 |
| d62 集纲层产物搬运（15 行） | 12 | 3 | 0 | 0 |
| d63 台词层记录搬运（22 行） | 21 | 1 | 0 | 0 |
| d64 语料与反馈（8 行） | 8 | 0 | 0 | 0 |
| E 集成（35 行） | 35 | 0 | 0 | 0 |

和 D6-3 报告的差别：d64 段是新加的，总表多了两条要求，都满足。A 段的 D6-0 台词目标（第 11 轮）照新的 changelog 规则仍通过。

d64 段的计数：

| 行 | 计数 |
| --- | --- |
| `corpus agree` | 比对 40 条（另 98 条未双跑）；未收敛一致率 function 0.825、relation 0.85、infoMode 交集 0.875，与 D6-0 盲标记录相同；收敛后 function 0.85、relation 0.95；low 11 条（D6-0 判不一致的是 15 条） |
| `corpus defaults` 媒介 | 与随包文件无差异：直人 n = 2 部 32 集，漫剧 n = 1 部 8 集 |
| `corpus defaults` 禁词表 | 仙侠／古装玄幻表 37 词：语料确认 10、未见 27、其他题材出现 0，候选新词 14 个（不进随包）；霸总／都市言情表不能评估（小样本里没有这类题材） |
| `corpus fetch` | 编造台账：计划 30 项，完成 3，预算两次读数都是 `unconfigured`，判 `unconfirmed` |
| `feedback-ingest` 第 6 集批注 | 7 条（line 2、topic 2、info_carriage 3）→ 反例 7、人写正例 2、对照对 2、约定草稿 5、问题草稿 2 |
| `feedback-ingest` 修改对照表 §二 | 表 8 行，5 行有「→」成 note（另 3 行是删除或整体说明，跳过）→ 反例 5、人写正例 5、约定草稿 1、问题草稿 1 |
| `feedback-ingest` 现实审查 | 程序类 14 条 → 底账修订提案 14、K1 草稿 14 |
| 原文件 | 语料与三处反馈的输入在运行前后 sha256 相同；派生物在项目 `runs/d64-feedback/` 下写过一次，之后每次与新跑的结果逐字节比对，相同 |

所有派生行都带 `fromNotes`。

## 五、随包数据重算的差异

| 文件 | 字段 | 原值 | 重算 | 说明 |
| --- | --- | --- | --- | --- |
| `default-media-profile.json` | 直人交换中位时长 | 10.8 秒，n=138 | 10.7 秒，n=107 | 原值标的是直人，实际按全部 138 条（含漫剧）算的；重算只算直人 |
| 同上 | 漫剧交换中位时长 | 无 | 12.0 秒，n=31 | 新增；原来 `unknowns` 里「漫剧没有量过」一条删去 |
| 同上 | 各格式语速、停顿占比、毛字速、默认时长 | — | 不变 | 只加了 n（部数、集数） |
| `genre-lexicon.json` | 两张表的词 | — | 不变 | 每张表加 `measured` 块；词表本身没增删，候选词等主创看过语料再定 |

## 六、留给 D6-5 与待办

- 全库取用、补三类缺口语料、计费确认：见 [d6-4-corpus.md](d6-4-corpus.md) 第四节。
- 语料缓存的工作室级目录（计划 §8 #1）仍未确认，`contract-check` 照旧只放行 `scope.level: project`。
- `feedback-ingest` 的派生物都是 `drafted`。哪些约定进台词目标、哪些底账提案采纳，是主创的决定；脚本不改状态。

## 七、局限

- 双跑一致率只有 40 条可比，其余 98 条只有一跑；收敛词表是假定（`source: assumed`），没有拿第二批标注验证过。
- 禁词表只评估了一张，而且只有 1 个题材 8 集的直接样本。「语料确认」只说明这些词在本题材出现、在其他两部里没出现，不说明它们是禁词表该有的词。
- 批注的层级判定靠词表与句式启发式，对照表的层级靠列名；程序类判定只认回答记录里的程序依赖与 `contradicts_reality`。新格式的反馈文件可能认不出，认不出时输出里没有 note，不会乱派。
- `corpus fetch` 没有对真实响应跑过；`_find` 认 `data`／`result`／`structuredContent` 三种包装，真实响应若是别的形态，快照核对会记 `not_evaluable`。
