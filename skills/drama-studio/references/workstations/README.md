# 创作工位契约 v0.1

六个工位是六种创作责任，不是六个 Agent 或六次人审。每次工位运行都用同一组对象交接，对象格式见 `../../schemas/`，每种对象在 `../../schemas/examples/` 有一份可通过的示例；用 `scripts/drama_tools.py contract-check <对象> <文件>` 校验。无法确知的内容写进 `unknowns`（每种对象都有这个字段），不要在 ID 字段里编造。

引用（`ref`）的 `id` 不能为空。还不存在的远端候选位置写 `slot:<名称>`（如 `slot:episode-21`，对应保存时的 `slot`）；完全不知道身份的材料写 `unknown:<简述>`，并在 `unknowns` 说明。

两个快照 ID 不要混淆：`context-snapshot.projectBase.sourceSnapshotId` 是读取 mali-story 写作上下文（源码工具 `get_writing_context`）时得到的来源快照；保存候选时的 `inputSnapshotId` 必须填写同一个来源快照，表示候选依据哪一版写成。没有连接时两者都为 null，回执记 `not_sent`。

## 每次运行的固定协议

1. **任务**（`task`）：目标、非目标、读取范围、写入范围、授权来源、返修上限。读取范围可以大于写入范围；授权为 `none` 时不写任何东西。
2. **上下文**（`context-snapshot`）：本次实际给了哪些版本、原文区间和知识卡，各自理由，以及遗漏项。必需材料缺失时 `completeness` 只能是 `incomplete`；超出预算就缩小工作单元，不静默截断。宿主（模型）先写选材清单（`selection`，格式见 `../../schemas/selection.schema.json`），再用 `scripts/drama_tools.py context-pack <项目> --task <task.json> --selection <selection.json> --role <角色> --budget <字数>` 从 `.drama/cache/` 与 `knowledge/cards/` 组装快照：工具按实际截取文本计算 `chars` 与 sha256，核对缓存指纹，按角色过滤用途，超预算退出码 2 且不写文件。选什么由模型判断，工具不做相关性排序。
3. **产出**：完整可读的作品材料。联网时作为 mali-story 候选保存，保存不等于采用。源码中的保存工具为 `save_story_artifact`，实际名称以当前会话可用工具为准（见 [资料与拉片](../mali-story.md)）。保存的是产出，不是上下文快照。
4. **交接**（`run-handoff`）：输出引用、状态变化提案、上游变更提案、未完成项和下一动作。只写本层候选；涉及上游决定时提出 `changeProposals`，不静默改写。
5. **远端回执**（`remote-receipt`）：每次保存记录 `requestId` 与输入指纹。结果未知时先按 `requestId` 对账，不盲目重试；没有连接或未获授权时记 `outcome: not_sent`，`artifactId` 与 `revision` 必须为 null。

## 执行层级

| 约束 | 层级 | 说明 |
| --- | --- | --- |
| 快照不超声明的预算、同一来源不混用多个修订、不带入评估材料、列入 `omitted` 的必需材料使包不完整、区间合法 | S | `contract-check context-snapshot` 拒绝；用 `context-pack` 装包时 `chars` 与 sha256 由工具从本地缓存／知识卡实际截取计算，缺失的引用自动列入 `omitted`；单独运行 `contract-check` 仍只看字段，不核对实际字数，手写快照里没列入 `omitted` 的缺失无法发现（M） |
| 观众效果（`reader_effect`）包不含作者计划分区 | S | 同上 |
| 知识卡首版只允许项目私有 | S | `contract-check knowledge-card` 拒绝 studio／public |
| 变更提案只能指向上游工位 | S | `contract-check run-handoff` 拒绝 |
| 本地字段不能宣称已采用 | S | `contract-check task` 要求 `adoptionEvidence` 为 `remote_receipt` 引用；回执内容真假由服务端核对（R） |
| 其他脚本规则：回执未发送／未知／已确认的字段要求、事实问题需引文、串行自评不得称独立、估算用量不得写 token、非合成知识需来源 | S | 完整列表见 `scripts/checks/contract_check.py` 与 `schemas/` |
| 候选版本冲突、幂等重放、正式采用 | R | mali-story 服务端 |
| 首读不看作者解释（`context-pack` 只按分区拦 `current_plan`；放进其他分区的作者说明工具不识别）、状态变化如实上报、不越权改稿、远端 ID 不编造 | M | 本文件约定；只能靠审读抽查发现违反 |

S 通过只说明格式与脚本规则满足，不说明引用在远端存在、引文支持结论或创作质量达标。

## 知识类型 K1–K9

| 编号 | 内容 |
| --- | --- |
| K1 | 生活、职业与文化材料 |
| K2 | 人物行为与关系策略 |
| K3 | 戏剧与叙事方法 |
| K4 | 分层作品案例 |
| K5 | 语言、身体与视听表达 |
| K6 | 类型、观众与市场证据 |
| K7 | 媒介与制作经验 |
| K8 | 相似结构与自我重复 |
| K9 | 修改、失败与反馈经验 |

本版知识卡只允许项目私有范围（`scope.level: project`）。

### 知识库目录与命令

目录约定（由知识编辑或宿主创建，工具不会创建）：

- `<项目>/knowledge/cards/<cardId>@r<revision>.json`：一个修订一个文件，新修订写新文件；不递归子目录，非 `.json` 文件列入 `ignored`。文件名按最后一个 `@r` 切分，revision 必须是正整数，且须与卡片内容中的 `cardId`、`revision` 一致。
- `<项目>/knowledge/sources/<sourceId>/…`：本地原始证据。卡片 `evidence.sources[].location` 以 `knowledge/sources/<sourceId>/` 开头时视为本地文件，可带 `#<位置>` 后缀（如 `knowledge/sources/src-a/notes.md#L12-L20`）；其他位置标记为 `external_not_checked`，不声称已核验。

```sh
python3 -B scripts/drama_tools.py knowledge validate <项目>
python3 -B scripts/drama_tools.py knowledge search <项目> [--type K1..K9] [--workstation C1..C6] [--usage creative_reference|comparison_only|evaluation_only] [--text 关键词] [--include-retired]
python3 -B scripts/drama_tools.py knowledge show <项目> <cardId> [--revision N]
```

- `validate`：对全部卡片运行 knowledge-card 契约校验（含 studio／public 范围拒绝），并核对文件名。JSON 损坏、读取失败或非法编码的卡片计为无效卡，不中断其余卡片的处理；每条 `invalid` 记录带 `path`、`cardId`、`revision`（文件名解析不出时为 `null`）与 `errors`。
- `search`：每个 cardId 只看最新的**有效**修订，默认排除 `processing: retired`；`--text` 对 cardId、`content` 与 `transfer.transferable`／`transfer.notTransferable` 文本做不区分大小写的子串匹配（不匹配工位代码列表）。每条结果带 `line`（如 `kc-a@r2  K3  C2,C4,C5  creative_reference  同源:src-x(kc-b)`，无共享来源时写 `无同源`）、`sameSource` 与 `newerInvalidRevisions`（该 cardId 比当前结果更新但无效的修订号；非空时 `line` 末尾追加 `[newer-invalid:r2]`，多个逗号分隔）。遇到无效卡时仍输出结果，无效卡列入 `invalid` 且不参与检索。
- `show`：默认最新修订（即使该修订无效也会打开，不隐藏坏的新修订），`--revision N` 取指定修订；打印完整卡片与每个来源的位置。本地来源须解析在 `knowledge/sources/<sourceId>/` 内且文件存在，否则报 `missing`（含来源目录本身或任意目录）、`outside_source_dir`（含 `../` 越界与逃逸符号链接）或 `unresolvable`（如符号链接循环、路径含空字节，随 `error` 字段说明）。结果带 `local_sources_checked`：本次检查的本地来源数量。

**同源**：在参与检索的卡集合（每卡最新有效修订；默认不含退役卡）中，两张以上的卡共享同一 `sourceId` 即同源，先算同源、再应用类型／工位／用途／关键词过滤。同源只说明来源重复，用来发现“同一来源拆成多张卡冒充多源支持”；它不说明内容重复，也不说明来源可靠。

退出码：`0` 完成（`knowledge/` 不存在时返回空结果、`store_status: "no_store"` 与目录约定提示）；`1` 输入或执行错误（项目路径不存在、卡片或指定修订不存在）；`2` validate／search 发现无效卡，或 show 的卡无效、本地来源缺失、越界或无法解析（`unresolvable`）。所有命令只读，输出带 `network_used: false`、`models_called: false`、`read_only: true`；不做向量检索、候选版本库或跨项目知识。

## 三种“kind”不要混用

- `task.kind`：本次任务类型（draft、outline、review…）。
- 工位文件中“产出”后的 kind：mali-story 候选类型，即保存候选时的 `kind`（episode_draft、episode_outline、review…）。
- `ref.kind`：引用对象的来源类型（remote_artifact、knowledge_card…）。

## 工位索引

| 工位 | 决定 | 文件 |
| --- | --- | --- |
| C1 创作定位 | 写谁的什么困境、提供什么体验、独特性在哪 | [c1-positioning.md](c1-positioning.md) |
| C2 人物与世界 | 人物如何争取、如何冲突，规则怎样产生代价 | [c2-characters-world.md](c2-characters-world.md) |
| C3 全剧与段落结构 | 选择如何造成下一段，结局怎样由前文生成 | [c3-structure.md](c3-structure.md) |
| C4 分集集纲 | 本集谁怎样改变局面，留下什么后果 | [c4-episode-outline.md](c4-episode-outline.md) |
| C5 正文 | 人物此刻怎样做、怎样说、怎样影响对方 | [c5-screenplay.md](c5-screenplay.md) |
| C6 审读与整合 | 哪些成立、哪里不足、应修哪一层 | [c6-review.md](c6-review.md) |

新剧的两个人审点（选题确认、送审包审批）见 [两次审批与接续](../approval-flow.md)，工位完成不等于用户选择或正式采用。
