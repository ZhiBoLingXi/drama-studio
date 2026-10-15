# D6-1 报告：对象与只读工具（0.4.0）

依据：[统一实施计划](../design/drama-studio-outline-dialogue-implementation-plan-2026-10-14.md) §4.2；[D6-1 九项设计决定](d6-1-decisions.md)。日期 2026-10-15。分支 `feat/d6-1-objects-tools`。本页只放编号与统计，不含任何项目的剧情、人物、台词或卡片原文；本地验收用的真实产物在项目目录（不随仓库分发）。

## 结论

§4.2 的验收 13 项全部满足（见第一节），退出条件「上述全过；0.4.0 可安装（`install.py verify`）」满足。

- 全量 unittest：731 项全过（D6-1 之前 416 项，新增 315 项，旧测试期望一条未改）。
- 本地验收总表：295 行，没有未解释的不一致（第三节）。
- 《渊心锁》与本项目的旧记录：`season-check` 输出与 0.3.6 字面逐字节一致（12 组参数）。
- 正式工具比临时脚本更严，在第 6B 集分集计划上查出 4 条真数据问题，已在数据里修好（第四节）。

## 一、§4.2 验收逐条

复现命令均在仓库根目录运行；`V` 指本项目的 D6-0 运行目录（gitignored）。本地验收的总入口是 `python3 -B scripts/d6_acceptance/run.py`，下表「行数」取它的最终输出。

| # | 验收项 | 结果 | 行数（其中有解释的差异） | 复现 |
| --- | --- | --- | --- | --- |
| 1 | 全部新 schema 正反用例通过 | 满足 | — | `python3 -B -m unittest tests.test_schemas_d6 tests.test_contracts` |
| 2 | 功能地图 v1（v1.2） | 满足 | 7（3） | `run.py`；`drama_tools.py function-map check …`、`contract-check function-map … --records …` |
| 3 | 49＋14 份第一轮回答记录：`contract-check answers` | 满足 | 75（72） | `run.py` 流 A 段 |
| 4 | 同上：`check-answers` | 满足 | 1（0） | `drama_tools.py check-answers …` |
| 5 | 三段底账与合并后的 ep000＋三集 delta | 满足 | 17（3） | `drama_tools.py ledger merge <三段> --out <tmp>`（400 条，id 集合与 D6-0 合并稿相同）；`ledger check …` |
| 6 | `ledger replay` 从 ep000 重放 | 满足 | 2（0） | `drama_tools.py ledger replay <ep000> --at 6B --track planned --delta ×3`。实际到 6B 为止，计划原写「到第 7 集」，D6-0 只写到 6B |
| 7 | 季编排 v0 | 满足 | 6（0） | `drama_tools.py season-plan-check …`；`capacity season …` |
| 8 | 三份分集计划 | 满足 | 25（1） | `drama_tools.py plan-check …`；`capacity episode …`；`retell-check …` |
| 9 | 对话表 v2.1 | 满足 | 3（0） | `drama_tools.py dialogue-plan-check …` |
| 10 | 冷读复述（计划 3 份、正文 3 份） | 满足 | 23（6） | `drama_tools.py retell-check … --plan …` |
| 11 | 对话问题单回答记录 | 满足 | 5（0） | `drama_tools.py check-answers …`；`answers-consistency …` |
| 12 | `capacity` 对 006A 分集计划与 g2 正文，与临时脚本相差不超过 ±1 秒 | 满足 | 2（0） | `drama_tools.py capacity episode|text …` |
| 13 | `season-check` 对《渊心锁》与本项目旧记录与 0.3.6 逐字节一致 | 满足 | 12（0） | `run.py` 的 legacy lock：用 `git archive main` 取 0.3.6，两个项目各跑 6 组参数，比对标准输出与退出码 |
| — | `validate.py`；`test_skill_routing`；`install.py verify` | 满足 | 3（0） | `validate.py` 剩 9 条错误，都是 docs 里指向 mali-story 仓库的既有外链，随包检查通过；`install.py install/verify --host claude-code --skills-dir <临时目录>`，119 个文件；`plan` 只读 |

## 二、各流交付

| 流 | 文件 | 测试 |
| --- | --- | --- |
| A schema 与契约 | 18 个新 schema（含 `defect-register`）、各一份合成例子、`schemas/data/` 的 3 份数据文件与题材词表；`task`、`review-record`、`run-handoff`、`context-snapshot`／`selection`、`knowledge-card` 字段扩展，旧例子仍通过；`contract_check.py` 的新规则、旧写法识别与跨文件上下文；`validate.py` 放宽 `schemas/data/` | `test_schemas_d6` 81，`test_contracts` 增补 |
| B 底账与计划 | `ledger.py`、`plan_check.py`、`season_plan_check.py`、`capacity.py`、`decision.py`、`function_map.py`（含 `topics`、`defects build`） | 100 |
| C 容量与核对 | `answers_check.py`、`retell_check.py`、`consistency.py`、`dialogue_plan_check.py`、`plan_text_consistency.py`、`diagnose.py`、`feedback_ingest.py`、`text_lines.py`；`dup_check --list-hits`；`episode_check` 口播量 | 53＋格式测试增补 |
| D 语料 | `checks/corpus/{segment,label,filter,lexicon,rate,transcript}.py`（fetch 留到 D6-4） | 23 |
| E 集成 | `drama_tools.py` 子命令接线（reproduceCommand 统一改成 drama_tools 形式，`contract-check` 加上下文参数）；`season_check.py` 新旧并存（集纲层 7 条、台词层 12 条）；`context_pack.py` 新角色与装包规则、按话题装样本；SKILL.md 随包工具表；README；VERSION 0.4.0；`scripts/d6_acceptance/run.py` | 50 |

## 三、本地验收总表（run.py 最终输出）

| 段 | 通过 | 有解释的差异 | 跳过 | 不一致 |
| --- | --- | --- | --- | --- |
| A schema（209 行） | 97 | 110 | 2 | 0 |
| B 底账与计划（25 行） | 22 | 3 | 0 | 0 |
| C 容量与核对（27 行） | 26 | 1 | 0 | 0 |
| D 语料（9 行） | 9 | 0 | 0 | 0 |
| E 集成（25 行） | 25 | 0 | 0 | 0 |

A 段那 110 行差异分四类：

- 83 行只因 D6-0 的旧写法而不过，schema 取规范写法，`contract-check` 会点名旧写法。
- 24 行是规则出现之前的记录，当时的汇总已判为不合规。
- 2 行在后一版文件里已修。
- 1 行已被取代。

B 段的 3 行：

- 一次传入三个 delta 不再崩溃。
- `knows` 不再把已退役的条目算作「还知道」。
- 功能地图检查里两条写死的重映射，改为按底账字段推出，或由参数传入。

C 段的 1 行：分集计划的拍号前缀为「数字＋字母」时，`episode-check` 不认这样的集标题。这是旧行为，不改；口播量与 `capacity text` 是同一口径。

## 四、正式工具查出的真数据问题

`plan-check` 的 `speaker-knows` 改成按底账 id 与拍序判断后，在第 6B 集报出说话人在说话的那一拍之前还不知道他说的事。临时脚本只核说话人在不在知情名单里，所以当时没有报。

- 分集计划代理复核后，同集共有 4 条知识条目的 `since` 把不同时候得知的几件事捆成了一条，现已按部分拆开。
- 其中 1 条是内容错：条目让一个人物「知道」了他在场时看不见的事。已改。
- 拆开之后 6B 仍报 1 条，根因在工具：`since` 的值写成「pre」再加括注、括注里提到本集拍号时，`ledger.parse_beat_ref` 读到了括注里的拍号。已在 D6-1 内修正：以「pre」开头的值一律按本集之前处理，其余值只认开头的拍号，括注不读（`tests/test_ledger.py` 正反各一）。扫描验证目录全部底账、delta 与分集计划写入的 `since`／`knownToSince`／`visibleToSince`，判定因此改变的只有这 1 个值。
- 数据与工具都修好后，6B 的 delta 应用与 `plan-check` 通过，与临时脚本 14 条规则逐条相同。另有 3 处说话人没有底账 id，记为 `notEvaluable`，只报不拦。
- 那 3 处 `notEvaluable` 的说话人是同一人物，底账里没有他知道这三件事的知识条目，依据只有物件持有与知情名单为空的时间线。持有物件不等于知道内容，其中 1 处还与一条既有知识条目可能冲突，所以没有补登，留到用正式工具重做项目验证时裁定。

## 五、与 §2.2 命名的差异

- `plan-text-consistency`：位置参数是正文对照表，另加 `--dialogue-plan`、`--episode-plan`，不是「<正文> --plan」。`dialogue-diagnose` 用 `--plan-text-map`／`--dialogue-plan`。
- 计划表外新增的命令：
  - `season-plan-check`
  - `answers-consistency`
  - `dialogue-plan-check`
  - `defects build`（决定 #6、#9）
  - `ledger stats`
  - `decision check`
- `episode-check` 的口播量用 `--speech` 显式开启，不给时输出不变。`contract-check` 的跨文件规则由 `--records`、`--defects`、`--cards`、`--questions`、`--base-questions` 提供上下文，不给时在 `notEvaluated` 里写明没核。
- `season-check`：只有启用了新规则的一侧才输出 `ruleSet: outline-layer`／`episodeRuleSet: dialogue-layer`。旧项目不加任何键，输出与 0.3.6 字面逐字节一致。

## 六、遗留到 D6-2／D6-3 的事

**D6-2**

- 定项目目录布局。`season-check` 的新规则目前从 `planning/`、`.drama/checks/`、`.drama/tasks/` 读记录，靠 schema 标记或 `reproduceCommand` 里的子命令认出记录类型。这是 D6-1 为了能核记录先定下的，要在 `references/outline-layer.md` 里确认或改掉。
- `context-pack` 的 `local_file` 目前只能取 `.drama/`、`runs/` 下的文件，`planning/` 下的计划还不能直接装包。
- 追问单 v2 的题干（决定 #2）。
- 「材料全程没写」的自动检索（决定 #7）。

**D6-3**

- 记录装包历史，用来核同一条样本不连续两集出现。
- 样本分区：schema 里没有样本分区，样本暂时以 `local_file` 加字符区间放在 `current_plan` 分区。
- 旧三条（声音卡、台词遍、台词读）改为只在 `--legacy-dialogue` 下跑。
- 修订单扫描接进修订流程。

**重做项目验证时裁定**

- 第 6B 集 3 处 `notEvaluable`（见第四节，已知遗留，有意未补登）。

## 七、局限

- 冷读包只核「恰好一项 `project_facts`，且不含计划与知识」。这一项是不是本集的正文或 events，靠约定，不靠脚本。
- `season-check` 的新规则核的是记录存不存在、字段在不在，不判计划或正文写得好不好。认集号先看记录自己的字段，再看所核文件的文件名，最后才看记录的文件名。
- `outline-patch-cap` 只能从静态文件推断：`selected` 候选或未退役的底账条目 `patchCount` 不小于 3，就视为到 2 之后又原地修订过；被否候选的计数是历史，不查。
- 本地验收只在一个项目的 D6-0 产物上跑过；新规则的正反例都来自合成夹具，没有在一个按 D6 布局建的真实项目上走完整一季。
