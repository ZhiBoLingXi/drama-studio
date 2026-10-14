# D6-3 开头的共用决定

依据：[统一实施计划](../design/drama-studio-outline-dialogue-implementation-plan-2026-10-14.md) §4.4、§4.8（退役表 #23–#45）、§8，[D6-1 报告](d6-1-report.md) 第六节，[D6-2 决定](d6-2-decisions.md) §4。日期 2026-10-15。三个工作流（方法文档、工位文档、工具）共读本页，写法不一致时以本页为准。

## 1. 计划 §8 里 D6-3 之前要定的三项：按默认做

三项都写明「不确认也能实施」且可逆，按计划写的默认做，不另找主创。

| §8 | 事项 | 采用的默认 |
| --- | --- | --- |
| #2 | 语料原句进包的边界 | 遮蔽后原句每个话题最多 2 句进包，配 `dup-check --list-hits --k 8` 核对；`context-pack` 留参数可改为 0 |
| #3 | 旧步骤退役时点 | D6-3 起新运行直接不做台词遍、台词读；`season-check --legacy-dialogue` 保证旧记录仍可核 |
| #6 | 人工改句可否逐字用 | 本剧编剧的句子可以逐字用，必须标 `verbatimFrom`；语料原句永不逐字 |

## 2. 「启用了台词层」的判据

与集纲层同法，按记录判，不按目录：项目里有对话表记录（带 `dialogue-plan` 标记的 JSON，任意深度于 `planning/`、`.drama/`）即启用。旧项目没有，`season-check --episodes` 不带 `--legacy-dialogue` 时：旧三条（`voice-card`、`dialogue-pass`、`dialogue-read`）不再出现，新规则按「有对话表才核」，所以旧项目没有新失败。带 `--legacy-dialogue` 时输出与 0.3.6 逐字节一致（测试锁定）。判据做成一个函数，与 `outline_project` 并列共用。

## 3. 产物位置（接 D6-2 §1）

| 路径 | 放什么 |
| --- | --- |
| `planning/dialogue/dialogue-plan-<NNN>.json` | 对话表（C5a） |
| `planning/dialogue-target.json` | 项目台词目标（版本化，`revision` 字段，与 schema 一致） |
| `runs/<批>/ep-<NNN>.c5b.md` | 正文稿（C5b），沿用现有 `runs/` 写法 |
| `.drama/checks/` | 冷读复述、处境对照（对话问题单回答）、设计依据一致性、诊断输出 |
| `.drama/packs/history.json` | 装包历史（哪条样本在哪集装过；`context-pack` 写） |

样本没有本项目语料时（新项目在 D6-4 之前都是这样）C5a 照常进行：样本是可选输入，缺了在交接 `unknowns` 记「本次无样本」，不阻断。

## 4. `references/dialogue-structure.md` 的节标题（工位文档按这些标题链接）

1. 总览：C5a 对话表 → C5b 正文 → C6 五读 → 先改表再改文
2. 台词目标与裁决顺序
3. 对话表（话题、交换、`listenerKnows`、`carries`、`closer`、`oneItemPerLine`）
4. 样本怎么用（处境检索、遮蔽、每话题上限、`verbatimFrom`）
5. 写正文（C5b）：照表写，信息由对白承载，重复须有处境理由
6. 正文侧两读：冷读复述、处境对照（对话问题单）
7. 设计依据一致性与诊断信号（数字只诊断不裁判）
8. 修订：先改表再改文；修订单不写替换文字、不写数值；修订后复读
9. 人工反馈的吸收（`writer-note`、`verbatimFrom`、`preserved` 只认人工来源）
10. 前文校核（原 `dialogue.md` §8，保留）
11. 改稿任务怎么写（原 `dialogue.md` §9，保留）
12. 命令速查

## 5. 带进 D6-3 的遗留

- 装包历史（§3 的 `history.json`），用来核同一条样本不连续两集出现。
- 样本分区：`context-snapshot`／`selection` 加 `samples` 分区，样本不再借 `current_plan`。
- 旧三条只在 `--legacy-dialogue` 下跑（§2）。
- 修订单扫描接进修订流程：修订单含替换文字（SPEAKER 格式行）或数值指令即拒。
- [D6-2 决定](d6-2-decisions.md) §4 的四条：`writing.md` 第 7 步与 `SKILL.md` 第 4 步改为 `decision add --from-handoff` 登记带默认；`writing.md` 第 9 步改为 `ledger replay` 导出；`season-run.md` §3 去掉「关键选择缺失」；正文侧修订预算用完后的处理与集纲侧统一（写进交接 `unfinished` ＋ 决定队列带默认）。

## 6. 走通演示（[d6-3-walkthrough](d6-3-walkthrough.md)）发现的处置

编号同演示报告「发现」。T＝工具流，M＝方法文档流，W＝工位文档流。

| # | 裁定 | 谁 |
| --- | --- | --- |
| 1 | 没有语料的项目：`dup-two-tier` 的 13 字全库档记 `not_evaluable`（原因「本项目无语料」），不算失败；8 字装包档没有样本时通过。这正是 §3「无样本不阻断」的原意 | T＋M |
| 2 | 台词目标的 `corpusManifest` 可为 `null`，此时必须写 `noCorpusReason` | T＋M |
| 3 | 图谋账条目的主人（`who`）算知道该图谋的内容，`speaker-knows` 照此判；不必回 C4 删 `ledgerRef` | T |
| 4 | 预算用完后决定队列的默认是「按现稿交付」时不改；主创（或默认）选了「再改一次」时，由编排方在预算用完的那一层（集纲侧 C4，台词侧 C5a 或 C5b）另开一次运行，这次修订另计预算 1 次，交接引用该决定 | M＋W |
| 5 | 第 1 集的入口是 `ledger-ep000.json` 与 `ledger replay --at 0 --md` 导出的 `after-ep-000.md`，文档写明 | M＋W |
| 6 | `consistency-record` 按 `target.file` 分组：对不同稿的处境对照不算同一稿两次 | T |
| 7 | 启用台词层后，已有审读记录里的 `preserved` 也按新规则核——这是有意的；文档写明启用后要把旧记录的 `preserved` 迁成 `{item, noteId|humanWords}` 或挪进 `goalAssessments[].evidence` | M＋W |
| 8 | 修订单的台词行识别优先用本集人物名单（对话表的说话人或对照表的 `speaker`）：只有「人物名：」开头才算台词；没有名单时退回启发式，并把「照表」「按表」加进标签词 | T |
| 9 | 题材禁词表按 id 进包，写法同问题单：`{"kind":"local_file","id":"lexicon:<表 id>@<版本>"}` | T＋M |
| 10 | 次读用 `evaluation` 角色 | M＋W |
| 11 | `review-record` 的 `layer` 加 `C5a`、`C5b`（`C5` 保留给旧记录） | T＋W |
| 12 | 打断位置字段定为对话表交换上的 `interruptedAt`（被打断的交换 id），工具读它；随包 `plan-text-consistency` 例子的命令行与状态词改成与工具一致 | T＋M |
| 13 | 首读封存：sha256 记在首读那份 `review-record` 的现有字段（工具流选定并写清；没有合适字段就加可选 `sealedSha256`）；`first-read-sealed` 只看正文侧审读 | T＋M＋W |
| 14 | 处境对照：一答可同时有 `landsOn` 与 `quoteRef`；`n/a` 不必引句；`defectKind` 词表加对话问题单用的类；`target.kind` 加 `topic`；无样本时第 15 问写 `n/a`（不影响 `outcome`） | T＋M |
| 15 | 冷读记录每条复述可带可选 `sourceLine`（行号＋原句）；人物表、场头里的信息算「正文」来源，`sourceKind: heading` | T＋M |
| 16 | 账外的人物间已知（叮嘱、约定）要登记成知识账条目（开 C3b 运行），`listenerKnows` 仍只从账来——单一来源 | M |
| 17 | 台词目标 `mediaProfile` 为 `null` 时用随包默认档案；版本字段是 `revision`（本页 §3 已改） | T＋M |
| 18 | 对照表 `lineToPlan[].kind` 定为 `title`／`scene`／`cast`／`action`／`dialogue`／`other`，`contract-check plan-text-map` 核 | T＋M |
| 19 | `episode-check` 场头里「次日晚」「次日晚稍后」这类时间词不再判为地点识别不全 | T |
| 20 | `capacity text` 不给 `--media` 时用随包默认档案（与 `capacity season`／`episode` 一致），报出 `targetSec` | T |
| 21 | 模型判断的长处写进 `goalAssessments[].evidence`，前缀「审读者看到的长处（模型判断）」，不新增字段；`preserved` 只放人工来源项，集纲侧与正文侧同一规则（`c6-review.md` 已改，「保留价值」产出项已删）；集纲侧的 S 核对由工具流加 | W（已做）＋T |

## 7. 不动的东西

旧项目文件一律不动；`dialogue.md` 改名后旧链接全部改到新文件，不留重定向文件。退役的段落删除或改写，不并列旧做法。K5 声音卡降为索引（`knowledge search --type K5` 仍可用），已有 K9 对照卡保留可读。
