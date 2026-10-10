# 创作工位契约 v0.1

写正文、续写和改稿默认按这些工位走，步骤见 [工位流程](../writing.md#工位流程)；一次写多批时按 [整季分批](season-run.md) 编排。

六个工位是六种创作责任，不是六个 Agent 或六次人审。每次工位运行都用同一组对象交接，对象格式见 `../../schemas/`，每种对象在 `../../schemas/examples/` 有一份可通过的示例；用 `scripts/drama_tools.py contract-check <对象> <文件>` 校验。无法确知的内容写进 `unknowns`（每种对象都有这个字段），不要在 ID 字段里编造。

引用（`ref`）的 `id` 不能为空。mali-story 页面写 `{"kind": "remote_page", "id": "<pageId>", "revision": <n>}`（架构 v1.2：pageId 跨修订不变，revision 每次写入递增）；迁移前的历史候选仍按 `remote_artifact` 引用。还不存在的页面没有 pageId，写入范围里写 `slot:<名称>`（如 `slot:episode-21`）作占位；完全不知道身份的材料写 `unknown:<简述>`，并在 `unknowns` 说明。

两个快照 ID 不要混淆：`context-snapshot.projectBase.sourceSnapshotId` 是读取 mali-story 写作上下文（源码工具 `get_writing_context`）时得到的来源快照；写页面时的 `input_snapshot_id`（历史候选保存时的 `inputSnapshotId`）填写同一个来源快照，表示这一版依据哪份上下文写成。没有连接时两者都为 null，回执记 `not_sent`。

## 每次运行的固定协议

1. **任务**（`task`）：目标、非目标、读取范围、写入范围、授权来源、返修上限。读取范围可以大于写入范围；授权为 `none` 时不写任何东西。
2. **上下文**（`context-snapshot`）：本次实际给了哪些版本、原文区间和知识卡，各自理由，以及遗漏项。必需材料缺失时 `completeness` 只能是 `incomplete`；超出预算就缩小工作单元，不静默截断。宿主（模型）先写选材清单（`selection`，格式见 `../../schemas/selection.schema.json`），再用 `scripts/drama_tools.py context-pack <项目> --task <task.json> --selection <selection.json> --role <角色> --budget <字数>` 从 `.drama/cache/`、`knowledge/cards/` 以及项目 `.drama/`、`runs/` 内的本地文件（`local_file`，见 [定向修订单独装包](#定向修订单独装包)）组装快照：工具按实际截取文本计算 `chars` 与 sha256，核对缓存指纹，按角色过滤用途，超预算退出码 2 且不写文件。选什么由模型判断，工具不做相关性排序。
3. **产出**：完整可读的作品材料。联网时写成 mali-story 页面：新页面 `create_page`，已有页面 `update_page`（`expected_revision` 取读到的当前修订）；写入的新修订立即成为当前内容。实际工具名以当前会话可用工具为准（源码为 mali-story v0.20.0，见 [页面读写、版本标签与恢复](../mali-story.md#页面读写版本标签与恢复)）。写的是产出，不是上下文快照。主创验收用 `label_page_revision` 给修订打标签（如“主创通过”）；**标签不等于制作采用**，交接里不要把打了标签写成已采用。回退用 `restore_page`，它追加新修订，不改历史。写完用 `read_page` 读回全文，`drama_tools.py receipt cache` 落到本地缓存（`.drama/cache/<pageId>@r<revision>.md`）。迁移前的历史候选只读，见 [候选保存与对账](../mali-story.md#候选保存与对账)。
4. **交接**（`run-handoff`）：输出引用、状态变化提案、上游变更提案、未完成项和下一动作。只写本层的页面；涉及上游决定时提出 `changeProposals`，不静默改写。两个可选字段：`finishedAt` 写运行结束时间（ISO 8601，带时区，如 `2026-10-07T16:30:00+08:00`），`status` 判断“最近运行”时优先用它，缺失才回落到文件修改时间；一次运行读了不止一个上下文包（如 C6 首读、次读）时，第一个填 `contextSnapshotId`，其余写进 `additionalSnapshotIds`，`impact` 对其中任一快照失效都把运行标为 `stale`。旧记录不写这两个字段也照样有效。
5. **远端回执**（`remote-receipt`）：每次页面写入（`create_page`、`update_page`、`restore_page`、`label_page_revision`）与读取都记录 `requestId` 与输入指纹，成功时 `remote` 记 `pageId` 与 `revision`。`update_page` 返回 409 记 `rejected_conflict`：先 `read_page` 读最新修订，合并后用新 requestId 再写。结果未知时先对账，不盲目重试：mali-story 的修订列表不带 requestId，`receipt pending` 给出两条路——用 `list_page_revisions` 按正文指纹与 producer 找 `expected_revision` 之后的修订（宿主判断），或用原 request_id 原样重发（服务端重放，可按 request_id 核实）。只有确认过的写入才算写入；`unchanged: true`、`replayed: true` 都不是新写入。没有连接或未获授权时记 `outcome: not_sent`，`pageId`（新页面）与 `revision` 必须为 null。回执用 `drama_tools.py receipt record` 生成，方法见 [页面读写、版本标签与恢复](../mali-story.md#页面读写版本标签与恢复)；迁移前历史候选的回执与对账仍按 [候选保存与对账](../mali-story.md#候选保存与对账)。

## 执行层级

| 约束 | 层级 | 说明 |
| --- | --- | --- |
| 快照不超声明的预算、同一来源不混用多个修订、不带入评估材料、列入 `omitted` 的必需材料使包不完整、区间合法 | S | `contract-check context-snapshot` 拒绝；用 `context-pack` 装包时 `chars` 与 sha256 由工具从本地缓存／知识卡实际截取计算，缺失的引用自动列入 `omitted`；单独运行 `contract-check` 仍只看字段，不核对实际字数，手写快照里没列入 `omitted` 的缺失无法发现（M） |
| 观众效果（`reader_effect`）包和台词读（`dialogue_read`）包不含作者计划分区 | S | 同上 |
| 知识卡首版只允许项目私有 | S | `contract-check knowledge-card` 拒绝 studio／public |
| 变更提案只能指向上游工位 | S | `contract-check run-handoff` 拒绝 |
| 本地字段不能宣称已采用 | S | `contract-check task` 要求 `adoptionEvidence` 为 `remote_receipt` 引用；回执内容真假由服务端核对（R） |
| 其他脚本规则：回执未发送／未知／已确认的字段要求、事实问题需引文、串行自评不得称独立、估算用量不得写 token、非合成知识需来源 | S | 完整列表见 `scripts/checks/contract_check.py` 与 `schemas/` |
| 页面修订冲突（409 VERSION_CONFLICT）、request_id 幂等重放、标签与恢复 | R | mali-story 服务端；标签不是采用 |
| 首读不看作者解释（`context-pack` 只按分区拦 `current_plan`；放进其他分区的作者说明工具不识别）、状态变化如实上报、不越权改稿、远端 ID 不编造 | M | 本文件约定；只能靠审读抽查发现违反 |

S 通过只说明格式与脚本规则满足，不说明引用在远端存在、引文支持结论或创作质量达标。

## 定向修订单独装包

按审读意见定向修订一集时，单独装一个包，不沿用写初稿时的快照：

- 被修订稿列为 `current_plan`（要在它上面改）或 `project_facts`（只作事实依据）；已写成页面的按 `remote_page` 引用其 pageId 与修订号，迁移前的历史候选按 `remote_artifact`。
- 审读记录、修改单等本地文件以 `local_file` 列入：`ref.id` 写项目内的相对路径，只能在 `.drama/`（不含 `.drama/cache/`，缓存一律按 `remote_artifact` 经 manifest 装入）或 `runs/` 之内，如 `.drama/reviews/rev-ep45-1.json`、`runs/ep45/fix-list.md`；绝对路径、`..`、反斜杠和解析到这两个目录之外的符号链接都被拒绝（退出码 1 或 2）。`revision` 写 `null`，或写希望钉住的 `sha256:<hex>`（与文件不符时退出码 2）；工具读取原字节，把实际 sha256 同时写进快照的 `revision` 与 `sha256`。文件不存在时列入 `omitted`。
- 这样修订的输入都留在快照里，换会话也能知道这次修订依据的是哪一版审读意见。`impact` 只评估 `remote_page`（`--page`）、`remote_artifact`（`--slot`／`--artifact`）与知识卡依赖：快照里的 `local_file`（任务文件除外）一律报 `unknown`（“该引用类型的依赖未评估”），本地文件改动后需要人判断是否重跑。

## 并行子代理的临时文件

几个子代理同时跑工位（如分批精修）时，每个子代理用自己的临时文件名（带 runId 或集号，如 `tmp-ep45-c5-save.json`），不共用 scratchpad 里的辅助脚本或日志文件，也不改别人的文件。共用一个辅助脚本时，后启动的会覆盖先启动的，记录可能写进别人的日志。需要共享的只读材料先由编排方写好，再交给各子代理读取；各子代理的产出各写各的文件，由编排方汇总。

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

- `<项目>/knowledge/cards/<cardId>@r<revision>.json`：一个修订一个文件，新修订写新文件；不递归子目录，非 `.json` 文件列入 `ignored`；以 `.json` 结尾却不是普通文件（目录、断开的符号链接）计为无效卡。文件名按最后一个 `@r` 切分，revision 必须是正整数，且须与卡片内容中的 `cardId`、`revision` 一致。
- `<项目>/knowledge/sources/<sourceId>/…`：本地原始证据。卡片 `evidence.sources[].location` 以 `knowledge/sources/<sourceId>/` 开头时视为本地文件，可带 `#<位置>` 后缀（如 `knowledge/sources/src-a/notes.md#L12-L20`）；其他位置标记为 `external_not_checked`，不声称已核验。

```sh
python3 -B scripts/drama_tools.py knowledge validate <项目>
python3 -B scripts/drama_tools.py knowledge search <项目> [--type K1..K9] [--workstation C1..C6] [--usage creative_reference|comparison_only|evaluation_only] [--text 关键词] [--include-retired]
python3 -B scripts/drama_tools.py knowledge show <项目> <cardId> [--revision N]
```

- `validate`：对全部卡片运行 knowledge-card 契约校验（含 studio／public 范围拒绝），并核对文件名。JSON 损坏、读取失败或非法编码的卡片计为无效卡，不中断其余卡片的处理；每条 `invalid` 记录带 `path`、`cardId`、`revision`（文件名解析不出时为 `null`）与 `errors`。
- `search`：每个 cardId 只看最新的**有效**修订，默认排除 `processing: retired`；`--text` 对 cardId、`content` 与 `transfer.transferable`／`transfer.notTransferable` 文本做不区分大小写的子串匹配（不匹配工位代码列表）。每条结果带 `line`（如 `kc-a@r2  K3  C2,C4,C5  creative_reference  同源:src-x(kc-b)`，无共享来源时写 `无同源`）、`sameSource` 与 `newerInvalidRevisions`（该 cardId 比当前结果更新但无效的修订号；非空时 `line` 末尾追加 `[newer-invalid:r2]`，多个逗号分隔）。遇到无效卡时仍输出结果，无效卡列入 `invalid` 且不参与检索。
- `show`：默认最新修订（即使该修订无效也会打开，不隐藏坏的新修订），`--revision N` 取指定修订；打印完整卡片与每个来源的位置。本地来源须解析在 `knowledge/sources/<sourceId>/` 内（文件夹名须与 sourceId 在磁盘上逐字一致，大小写或末尾 `/` 不同都不算）且文件存在，否则报 `missing`（含来源目录本身或任意目录）、`outside_source_dir`（含 `../` 越界与逃逸符号链接）或 `unresolvable`（如符号链接循环、路径含空字节，随 `error` 字段说明）。结果带 `local_sources_checked`：本次检查的本地来源数量；为 0（全部是外部来源或没有来源）时 `passed: null`，不声称证据已核验。`#<位置>` 只原样回显，不核对位置是否在文件范围内（`position_checked: false`）。

**同源**：在参与检索的卡集合（每卡最新有效修订；默认不含退役卡）中，两张以上的卡共享同一 `sourceId` 即同源，先算同源、再应用类型／工位／用途／关键词过滤。同源只说明来源重复，用来发现“同一来源拆成多张卡冒充多源支持”；它不说明内容重复，也不说明来源可靠。

退出码：`0` 完成（`knowledge/` 不存在时返回空结果、`store_status: "no_store"` 与目录约定提示；有 `knowledge/` 但无 `cards/` 时为 `no_cards`）；`1` 输入或执行错误（项目路径不存在、卡片或指定修订不存在）；`2` validate／search 发现无效卡，或 show 的卡无效、本地来源缺失、越界或无法解析（`unresolvable`）。所有命令只读，输出带 `network_used: false`、`models_called: false`、`read_only: true`；不做向量检索、候选版本库或跨项目知识。

## 三种“kind”不要混用

- `task.kind`：本次任务类型（draft、outline、review…）。
- 工位文件中“产出”后的 kind：产出的内容类型。写成页面时对应 `create_page` 的 `semantic`（episode、episode_outline、outline…）；历史候选是保存时的 `kind`（episode_draft、episode_outline、review…）。
- `ref.kind`：引用对象的来源类型（remote_page、remote_artifact、knowledge_card…）。

## 工位索引

| 工位 | 决定 | 文件 |
| --- | --- | --- |
| C1 创作定位 | 写谁的什么困境、提供什么体验、独特性在哪 | [c1-positioning.md](c1-positioning.md) |
| C2 人物与世界 | 人物如何争取、如何冲突，规则怎样产生代价 | [c2-characters-world.md](c2-characters-world.md) |
| C3 全剧与段落结构 | 选择如何造成下一段，结局怎样由前文生成 | [c3-structure.md](c3-structure.md) |
| C4 分集集纲 | 本集谁怎样改变局面，留下什么后果 | [c4-episode-outline.md](c4-episode-outline.md) |
| C5 正文 | 人物此刻怎样做、怎样说、怎样影响对方 | [c5-screenplay.md](c5-screenplay.md) |
| C6 审读与整合 | 哪些成立、哪里不足、应修哪一层 | [c6-review.md](c6-review.md) |
| 整季分批 | 多批之间怎样分、怎样交接、怎样对账 | [season-run.md](season-run.md) |

新剧的两个人审点（选题确认、送审包审批）见 [两次审批与接续](../approval-flow.md)，工位完成不等于用户选择或正式采用。
