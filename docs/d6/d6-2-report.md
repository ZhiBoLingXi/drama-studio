# D6-2 报告：切换集纲层（0.5.0）

依据：[统一实施计划](../design/drama-studio-outline-dialogue-implementation-plan-2026-10-14.md) §4.3；[D6-2 共用决定](d6-2-decisions.md)；[走通演示](d6-2-walkthrough.md)。日期 2026-10-15。分支 `feat/d6-2-outline-layer`。

本页只放编号与统计，不含任何项目的剧情、人物、台词或卡片原文。本地验收用的真实产物在项目目录里，不随仓库分发。

## 结论

§4.3 的 S 验收 5 项全部满足（见第一节）。退出条件中的「0.5.0 可安装」也满足。M 项证据有走通演示与文档修订后的复走各一份：复走时原 13 条「绕过了」全部按新文档走通，原 12 条「小」全部消失，另有新的小发现 9 条（见第五节之二）。

- 全量 unittest：830 项全过。D6-1 结束时是 731 项，本阶段新增 99 项。改了期望的旧测试有 5 项，各改一处，原因见第三节。
- 本地验收总表：310 行，没有未解释的不一致（第四节）。
- 《渊心锁》与本项目旧记录：`season-check` 输出与 0.3.6 字面逐字节一致（12 组参数）。
- `validate.py`：剩 9 条错误，都是 docs 里指向 mali-story 仓库的既有外链，随包检查通过。

## 一、§4.3 验收逐条

复现命令都在仓库根目录运行。本地验收的总入口是 `python3 -B scripts/d6_acceptance/run.py`，D6-2 段是 `scripts/d6_acceptance/d62.py`。

| # | 验收项 | 层级 | 结果 | 复现 |
| --- | --- | --- | --- | --- |
| 1 | `validate.py` | S | 满足：9 条既有外链错误，没有新增 | `python3 -B scripts/validate.py` |
| 2 | `test_skill_routing`（路由行、命令表） | S | 满足：10 项（原 6 项不动，新增 4 项：路由行指向 `planning.md` 与 `outline-layer.md`；「一次完整创作」第 6 步按 C3a→C3b→C3c→C4 排列；c3a／c3b／c3c 三个文件都在且被工位索引链到，`c3-structure.md` 已删且没有任何链接指向它；`writing.md` 第 3 步不再出现「关键选择」） | `python3 -B -m unittest tests.test_skill_routing` |
| 3a | `season-check --outline` 对 D6-0 产物（搬成项目记录形态）全过 | S | 满足：集纲层七条在第 5、6、5-6 集上零失败，`ruleSet: outline-layer`。另做 3 个变异，每个只触发对应的一条规则。旧的工位交接规则只有 `outline-run` 不过，记为有解释的差异：D6-0 没有留 C4 运行交接，记录缺失，不是数据或规则问题，没有补造 | `run.py` 的 d62 段 |
| 3b | 对《渊心锁》仍 `legacy`，结果不变 | S | 满足：两个项目各跑 6 组参数，标准输出与退出码都与 `git archive main`（0.3.6）逐字节一致 | `run.py` 的 legacy lock |
| 4 | `contract-check task` 拒绝「不动集数」类约束的正反用例 | S | 满足：`constraint-blocklist` v3。结构冻结类所有词条 × 四种 origin 都拒，另有 11 条改写说法也拒；数值型台词约束类 13 条拒；近似说法 26 条放行 | `python3 -B -m unittest tests.test_d62_tools` |
| 5 | `context-pack --role author`（C4）缺季编排时退出码 2 | S | 满足。C4 清单是季编排、底账修订、功能地图三件，缺任何一件都退出码 2；合成夹具与搬好的真实产物都测过。只对「已启用集纲层」的项目生效（判据见 [决定 §1](d6-2-decisions.md)）；0.3.6 时代的项目输出与删掉整个 `planning/` 时相同 | `tests.test_d62_tools`；`run.py` 的 d62 段 |
| M | 在新建空项目上，按新文档从 C1 走到第 1 集分集计划 | M | 证据：[d6-2-walkthrough.md](d6-2-walkthrough.md)。首走：阻断 0、绕过了 13、小 12，处置见第五节。复走（同一文件末节「复走（文档修订后）」）：13 条全部按新文档走通，12 条全部消失；关口 `season-check --outline 1` 的 `outlineLayerRules` 七条都是 passed；新发现小 9 条，见第五节之二。离线：加 `--allow-offline`，「只交本地稿」的同意来自编排方，不是真人，复走记录里已注明 | 复走记录逐条列了命令与退出码 |
| 退出 | 0.5.0 可安装 | S | 满足：`install.py install/verify --host claude-code --skills-dir <临时目录>` 核过 126 个文件；`plan` 只读 | `run.py` 的 release 行 |

## 二、各流交付

| 流 | 交付 | 测试 |
| --- | --- | --- |
| 方法文档流 | 新 `references/outline-layer.md`；重写 `planning.md`；改 `writing.md`、`approval-flow.md`、`recovery.md`、`SKILL.md` 路由与第 6 步。逐条内容见该流回报 | 由 `test_skill_routing` 核路由 |
| 工位文档流 | `c3-structure.md` 拆成 `c3a-function-map.md`、`c3b-ledger.md`、`c3c-season-plan.md`；改写 `c4-episode-outline.md`；`c6-review.md` 加集纲侧三读；改 `c1`、`c2`、`season-run.md`、工位索引。逐条内容见该流回报 | 由 `test_skill_routing` 核索引 |
| 工具流 | 见下表 | `test_d62_tools` 38 项，`test_d62_walkthrough_fixes` 57 项，`test_skill_routing` 新增 4 项 |

工具流的改动：

| 范围 | 改动 |
| --- | --- |
| 目录与装包 | `init-project` 多建 `planning/ledger/`、`planning/episodes/`、`runs/`、`knowledge/`。`context-pack` 的 `local_file` 放行 `planning/`，也能按 id 装随包问题单。C4 作者包按三件套清单核，`fact_check` 包放行 `comparison_only` 的卡。冷读包里对分集计划只收 events 导出 |
| 共用判据 | `season_check.outline_project`，由 `context-pack` 与 `season-check` 共用。`season-check` 的集纲层七条仍只在有 `planning/season-plan.json` 时启用，因为七条按季编排的分配逐集核 |
| season-check | 旧规则（`outline-run`、`outline-review` 等）也认 `planning/` 下按 schema 标记识别的分集计划记录；`outline-structure` 对写分集计划记录的 C4 运行按三件套清单核；输出 `outlineLayerRules`（七条各自的 passed／failed／not_evaluated 与核过的范围）。0.3.6 时代的项目输出不变 |
| 新命令与对象 | `plan-events`（分集计划的 events 导出），新 schema `episode-plan-events`；`plan-check --characters`（前史事件有没有时间线条目，只报不拦）；`ledger replay --delta <目录>`，`--md` 写出 plannedFallback 与应用错误；`ledger view <功能地图> --blank-period` |
| 契约与规则 | `constraint-blocklist` v3。`task.target`：集纲侧 C6 任务不要求 `dialogueTarget`。分集计划的审读记录，每条 finding 要带 `cites`。`run-handoff`：C1、C2 可以不装包，但要写 `noSnapshotReason`。回答记录：不承重的缺口可写 `pass_with_unverified`；加 `subject`、`target.ids`；回填的 `confirmed_gone` 要有效并写 `backfilledBy`；勘误要由复核记录确认，被取代的记录跳过；只确认勘误的复核记录（`target.kind: errata_check`）可以不答题；`check-answers --records <目录>` 只读回答记录，其余文件跳过并列出 |
| 底账与容量 | `ledger check` 的必填与 schema 同源；`money-closed` 接受 `emptyFields` 登记。`capacity` 缺语料或缺媒介档案时用随包默认值，标 `default_unmeasured`。`function-map topics` 只出能检索的题 |
| 读输出 | `status` 把「已结束、留有未完成项」与「未结束」分开。`retell-check` 的收尾拍按换说法判，`readingScope` 写文件路径不再误报。`plan-check` 的 `speaker-knows` 有没法判的行时写 `pass_with_not_evaluable` |
| 其他 | README 有 D6-2 一节；VERSION 改为 0.5.0；`SKILL.md` 随包工具表加了 `plan-events` 一行 |

## 三、改了期望的旧测试（5 项）

规矩是只增测试、不改旧期望。下面 5 项是 D6-2 的决定本身改了行为，每项只改一处，测试里都有注释。

| 测试 | 原期望 | 新期望 | 依据 |
| --- | --- | --- | --- |
| `test_context_pack` 拒绝目录外文件的用例 | `planning/secret.md` 被拒 | 从拒绝名单里删掉这一项；用 `..` 绕进 `planning/` 仍拒 | 计划 §4.3、决定 §1：`local_file` 放行 `planning/` |
| `test_capacity` 缺语料与中位时长的用例 | 输入错误，退出码 1 | 用随包默认值，退出码 0，`basis.status: default_unmeasured` | 决定 §5 #2 |
| `test_ledger` `money-closed` 的 `emptyFields` 用例 | 列进 `emptyFields` 仍判失败 | 算已交代，列在 `registeredEmpty`；没登记的空字段仍失败 | 决定 §5 #6 |
| `test_function_map` 检索题目归并的用例 | knowledge 类断言也出题 | 不出题，计入 `notSearchable` | 决定 §5 #15 |
| `test_plan_check` `speaker-knows` 按 id 判的用例 | 有 `notEvaluable` 时 `pass` | `pass_with_not_evaluable` | 决定 §5 #25 |

## 四、本地验收总表（run.py 最终输出）

| 段 | 通过 | 有解释的差异 | 跳过 | 不一致 |
| --- | --- | --- | --- | --- |
| A schema（209 行） | 97 | 110 | 2 | 0 |
| B 底账与计划（25 行） | 21 | 4 | 0 | 0 |
| C 容量与核对（27 行） | 25 | 2 | 0 | 0 |
| D 语料（9 行） | 9 | 0 | 0 | 0 |
| d62 集纲层产物搬运（15 行） | 12 | 3 | 0 | 0 |
| E 集成（25 行） | 25 | 0 | 0 | 0 |

和 D6-1 报告的差别：

- **d62 段是新加的。**3 行差异都是旧的工位交接规则在 D6-0 产物上不过，见第一节 #3a。
  - 搬运没有做任何格式转换，全部逐字节复制，只改路径。
  - 搬了 121 个文件：10 个进 `planning/`，111 个进 `.drama/checks/`。
- **B 段比 D6-1 多 1 行有解释的差异，少 1 行通过：**
  - 新增的一行：`money-closed` 的 8 条现在算已交代（决定 §5 #6）。
  - 功能地图检查那行在 D6-1 就是有解释的差异，理由换了：现在报 15 条勘误没有复核记录确认（决定 §5 #18）。另有 1 条在被取代的记录里，不要求确认。D6-0 的记录早于 `errataConfirmed` 字段；D6-0 的临时脚本核过，16 条都已改进地图。
- **C 段比 D6-1 多 1 行有解释的差异：**
  - 第 6A 集正文冷读 g1-b 的收尾拍，从 partial 改判 retold（决定 §5 #24），原因是复述换了说法。
  - D6-1 那行（`episode-check` 不认拍号前缀的集标题）不变。

## 五、走通演示 25 条发现的处置

裁定都在 [决定 §5](d6-2-decisions.md)，下表只列编号与去向。T 指工具流，M 指方法文档流，W 指工位文档流。T 项本流都已实施，并有正反测试（`tests/test_d62_walkthrough_fixes.py`）；M、W 项的落实见两流回报，本页不逐条核。

| # | 去向 | 本流实施（T） |
| --- | --- | --- |
| 1 | T | `fact_check` 包放行 `comparison_only` |
| 2 | T＋M | `capacity` 随包默认媒介档案，`default_unmeasured` |
| 3 | T | `ledger view` 可直接读功能地图 |
| 4 | T＋M | 随包 `answers.json` 补 `promptVersion` |
| 5 | T＋M | `ledger check` 必填与 schema 同源；保留的额外规则 7 条交方法流写进 §4 |
| 6 | T＋M | `money-closed` 接受 `emptyFields` |
| 7 | T | `check-answers --records` 收目录 |
| 8 | T＋W | `run-handoff` 的 `contextSnapshotId: null` 加 `noSnapshotReason`，只限 C1、C2 |
| 9 | T＋M＋W | `plan-events` 导出；冷读包拒收整份分集计划 |
| 10 | T＋W | C4 三件套清单（`context-pack` 与 `outline-structure` 同一张）；交接里用文件路径写的知识卡与包里的卡片项视为同一份 |
| 11 | W＋M | — |
| 12 | W＋M | — |
| 13 | M＋T | `check-answers` 核回填的 `confirmed_gone` |
| 14 | M | — |
| 15 | T＋M | `function-map topics` 只出能检索的题；可选字段 `realWorldRule` |
| 16 | M | — |
| 17 | M | — |
| 18 | T＋M | `errataConfirmed`；`function-map check --stage v1` 逐条核，被取代的记录列在 `skippedSuperseded` |
| 19 | T＋M | 不承重的缺口允许 `pass_with_unverified` |
| 20 | T＋M | `subject`、`target.ids` |
| 21 | M | — |
| 22 | T＋M | 随包问题单按 id 装包 |
| 23 | T＋M | `init-project` 建 `runs/`、`knowledge/`；`.drama/runs/` 不建（`status` 把空的 `.drama/` 当新项目，裁定已改） |
| 24 | T | `status` 区分已结束与未结束；总账视图按 `stateOf` 归人；`retell-check` 的收尾拍与 `readingScope` |
| 25 | T＋M | `season-check` 输出 `outlineLayerRules`；`plan-check` 的 `pass_with_not_evaluable` |

## 五之二、复走新发现 N1–N9 的去向

发现见 [走通演示](d6-2-walkthrough.md) 末节，都是「小」。

| # | 去向 | 处置 |
| --- | --- | --- |
| N1 | 方法流 | 已改文档 |
| N2 | 工具流 | `check-answers`：`confirmed_gone` 引用别的复核记录时，必须写 `backfilledBy`。不给 `--records` 时这个字段照样核。正反测试 2 项 |
| N3 | 工具流 | `target.kind: errata_check` 且有 `errataConfirmed` 的记录可以不答题。`contract-check answers` 与 `check-answers` 都认；别的记录 `answers` 为空仍报错，schema 的 `minItems` 改由契约规则执行。正反测试 2 项 |
| N4 | 方法流 | 已改文档：`check-answers` 是关口，`contract-check answers` 不查 `promptVersion`。工具不改 |
| N5 | 方法流 | 已改文档 |
| N6 | 工具流 | `check-answers --records <目录>` 只读带 `checkId` 与 `answers` 的回答记录，其余文件（含空文件、命令输出）跳过，列在 `recordsSkipped`。直接点名的文件仍按原样严格读。正反测试 2 项 |
| N7 | 方法流＋工位流 | 方法流已改文档，工位流同步了 c4、c6 |
| N8 | 方法流 | 已改文档 |
| N9 | 推迟 | 见 [决定 §4](d6-2-decisions.md) |

N1、N4、N5、N7、N8 的文档改动见两流回报，本页不逐条核。N2、N3、N6 改完后：全量测试 830 项通过；`run.py` 无不一致；在走通演示项目上，`check-answers RC-*.json --records .drama/checks` 退出码 0，跳过 11 个不是回答记录的文件。

## 六、留给 D6-3 的事

见 [决定 §4](d6-2-decisions.md)：

- `writing.md` 第 7 步与 `SKILL.md`「一次完整创作」第 4 步仍写「C4 及以上的问题写成变更提案交用户」。应改为 `decision add --from-handoff` 登记、带默认、流程不停。
- `writing.md` 第 9 步手写 after-ep，应改为 `ledger replay` 从实际轨导出。
- `season-run.md` §3 第 7 步仍有「关键选择缺失」。

D6-1 报告第六节列的 D6-3 事项（装包历史、样本分区、旧三条只在 `--legacy-dialogue` 下跑、修订单扫描接进修订流程）不变。

## 七、局限

- **复走是同一个演示者、同一个项目。**它证明的是原来的绕法不再需要，不是一个新的上下文第一次照文档走也能走通。项目里还留着首走的产物（例如只改了 `usage` 的卡修订 r2，见 N9）。
- **交接的 `finishedAt` 是拟的。**复走者自报：走通演示项目里各交接的 `finishedAt` 都是拟写的时间，比实际运行时刻晚，不是实测值。`status` 按它判最近一次运行，顺序碰巧没错，但这个字段在该项目里不可信。
- **离线授权不是真人给的。**走通演示的「只交本地稿」同意来自编排方，`season-check` 也不核 `PROJECT.md` 里有没有这句原话（M）。
- **集纲层七条只在一个项目的 D6-0 产物上跑过，**而且只有第 5、6 集；新规则的正反例都来自合成夹具。搬过来的产物没有 C4 运行交接，所以旧规则与新规则一起的完整链路，只在合成夹具和走通演示项目上走过。
- **「已启用集纲层」按文件判。**一个项目先按旧法写 C4、后补了集纲层记录，两种规则会同时作用在它身上。`outline-structure` 用「C4 运行是否产出了分集计划记录」区分新旧运行。
- **`ledger check` 保留的额外规则这次没在真实数据上逐条复核。**它们在 D6-1 的源码注释里写明按 D6-0 底账校准；D6-0 底账的 01 行在本阶段放宽后仍全过，只说明放宽后结果没变。
- **默认值与启发式：**
  - 随包默认媒介档案是三部剧的统计，漫剧没有交换中位时长，要自己给。
  - `retell-check` 收尾拍的「过半」是只报不拦的启发式。
  - `function-map topics` 对 money、object 断言默认出题，标 `realWorldRule: false` 才不出，可能多出一些查不到的题。
- **勘误确认在 D6-0 数据上无从验证。**勘误确认要另一份记录写 `errataConfirmed`，D6-0 的记录早于这个字段，所以 B 段那 15 条是新规则下的真实结论，不是工具误报。
