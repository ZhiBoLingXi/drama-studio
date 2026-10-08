# mali-story 连接与拉片

默认服务地址为 `https://story-api.maliai.art/mcp`，用户指定部署时优先使用指定地址。先通过宿主的 MCP 管理入口配置 OAuth 并发现工具。授权由用户完成；禁止从其他应用凭据文件获取令牌。读取只需适用的读权限，写入／拉片需适用的写权限。

## 能力发现与模板复用

发现当前 mali-story 工具；连接名称可不同。若只有 `list_api_endpoints`、`api_get`、`api_mutate`，先查真实路由，再核对参数契约。`list_api_endpoints` 每页最多 200，按返回分页；不要仅因本地代码或本说明出现某能力就认为线上支持。

优先查询个人／官方模板，核对标题、版本、集数、覆盖和权限。常见已发现路径为 `/api/v1/user-templates` 和 `/api/v1/user-templates/official`，但仍以当前目录为准。记录匹配的 templateId、版本和缺项；完整模板可直接进入原创策划，不重复下载和收费分析。

从榜单进入时读取项目的[对标交接卡](../templates/benchmark-research.md)，分别核对外部作品ID与内部templateId、季数、演员和集段。标题一致不足以确认同作品；源剧总集数与模板已分析集数分开保存。未知匹配不得自动挂接或据此创建收费任务。

`ready` 只表示服务任务状态，不保证内容正确。进入策划前交叉检查顶层集数、分集索引与正文范围；合并有证据的角色别名，筛查情绪词等误识别角色；区分省略的摘要和完整正文。发现相互矛盾时保留问题与原出处，按实际可读的逐集证据修正研究笔记；缺证据的部分不能作为确定设定传播。只有模板、没有热度数据时，不称其为已验证爆款。

按集读取证据；大结果使用服务实际支持的分块／导出。传输失败不等于全文自动保存到本地，部分结果不能冒充完整拉片。保存原片事实、分析推断和未辨识内容；关键桥段有实际时间码才引用，分析字段齐全不等于已核验原片。

## 新视频路径

保存详情后可执行 [资料覆盖检查](reference-check.md)，再处理语义问题。模板总集数可能只是本次上传槽位数，不能替代源剧总集数。详情摘要可能省略或截断，即使列表 `ready`、任务 `completed`，仍须核对所需集的证据、版本、`missingFields` 和 `evidenceValidation`。`not_run` 不得改述成“已对原片核验”。

发现路由只证明入口存在；还要检查响应中的 `available`、业务状态与原因。HTTP 200 且 `available: false` 是数据源不可用，不是空榜单，也不是市场查询成功。缺少费用预览时，不把源码中尚未部署的预算接口当作可调用报价。

1. 核验用户指定目录中的视频文件、集序、缺集、重复、合集区间和可读性，保存素材清单。下载队列状态不等于文件已就绪。
2. 查询当前项目与已有任务；需要创建草稿时先保存固定请求标识和输入，再提交，保存返回 taskId／templateId。
3. 视频字节需要上传通道，不能把本地路径当作远程可读文件。优先复用用户已经安装的 mali-story 上传工具，或用户在 mali-story 页面上传后继续。本包不包含独立 OAuth 上传客户端。
4. 上传回执记录 fileId、文件摘要和有效期。只有契约确认是该用户的可用视频 ID，才挂到对应分集槽位。
5. 挂接可能启动付费分析。查询已部署的费用预览，沿用已有授权；预览缺失或金额未知时说明缺口，不凭估计发起收费操作。
6. 查询原任务、各集结果和提交回执。响应未知时先核对，不创建新任务绕过未知状态；重试仅用已明确支持的幂等／版本契约。
7. 区分上传完成、单集分析完成、全剧汇总完成和模板 ready。条件满足后按当前契约 finalize；这只是参考模板定稿，不是采用新剧正文。

常见路由（仅导航，使用前需发现并核对参数）：

| 动作 | `/api/v1/user-templates` 下路径 |
| --- | --- |
| 建草稿 | `POST /deconstruct/draft` |
| 挂接已上传视频 | `POST /deconstruct/:taskId/uploads` |
| 查任务 | `GET /deconstruct/:taskId` |
| 查单集 | `GET /deconstruct/:taskId/episodes/:index` |
| 重试／取消 | `POST /deconstruct/:taskId/retry`、`POST /deconstruct/:taskId/cancel` |
| 读模板证据 | `GET /:id/episodes/:index/evidence` |
| 模板定稿 | `POST /:id/finalize` |

单集任务对象不一定包含完整拉片正文。费用预览、源视频保留、专业候选保存等扩展可能尚未部署。不能把当前账号余额当作本次总价，也不能把单次视频估算当整剧成本。

## 剧本保存

工位产出按下文 [页面读写、版本标签与恢复](#页面读写版本标签与恢复) 写成 mali-story 页面。Brief 使用专用 get/save/approve，save 带读取到的 expected_revision；通过当前会话可用工具确认具体名称。不能用通用块写入绕过这些工具。

连接的部署没有页面工具（v0.20.0 之前的部署，或授权里没有写权限）时，继续保留本地草稿，明确“未同步到 mali-story”，不宣布服务端接续成功。检查工具不存在时也不虚构已调用。

## 页面读写、版本标签与恢复

架构 v1.2 起，所有内容都是 mali-story 的页面，像飞书文档一样每个页面有版本（mali-story v0.20.0 起，见 [mali-story#2336](https://github.com/ZhiBoLingXi/mali-story/issues/2336)）。工具名与参数取自 v0.20.0 源码；源码不是部署证据，先在当前会话发现工具，没有就按上一节保留本地稿。

- **版本即生效**：`create_page` 建页面，正文立即成为 r1；`update_page` 写入的新修订立即成为当前内容。没有“候选”与“正文”两套对象，也没有单独的采用动作。
- **验收即标签**：`label_page_revision` 给某个修订起名，如“主创通过”“导演粗搭版”。每个修订只有一个标签，后写覆盖；不建新修订、不改正文。标签只是名字（mali-story 工具说明原文：a label is not an approval），**不等于制作采用**；回执、缓存、`impact` 都不把标签当作采用证据，也不要在交接里这样写。
- **恢复即回退**：`restore_page` 追加一个新修订，内容取自所选旧修订（响应带 `restoredFromRevision`），历史不改写。
- **身份**：`pageId` 跨修订不变，`revision` 每次写入递增。本地判断新旧一律按 `pageId@r<revision>`，不再经 slot 解析。
- **不声称没有发生的写入**：`unchanged: true`（正文与当前修订相同）没有写新修订；`replayed: true` 是原结果的重放，不是第二次写入；结果未知的写入在对账前不算写入。

**producer**：`codex`、`human`、`external_ai` 三选一（`mali_story` 为服务端保留值）。只有宿主是 Codex 时写 `codex`；Claude Code、WorkBuddy、ChatGPT 等其他 AI 宿主一律写 `external_ai`；用户本人写的文字写 `human`。它只是来源标记，不授予任何权限。宿主与模型名记在本地 `run-handoff`。

**工位产出 → 页面**：`create_page` 必填 `title` 与 `semantic`。源码接受的 `semantic` 只有 `synopsis`、`outline`、`characters`、`episode_outline`、`episode`、`setting`；带 `episode_ref` 时同一集同一 semantic 只能有一个页面，重复创建返回 `PAGE_ALREADY_EXISTS`（details 带 `existingPageId`），改为对那个页面 `update_page`。

| 工位 | semantic | episode_ref |
| --- | --- | --- |
| C2 | `characters`、`setting` | 不填 |
| C3 | `outline`（全剧结构）、`synopsis` | 不填 |
| C4 | `episode_outline` | 必填，如 `ep-03` |
| C5 | `episode` | 必填 |

C1 的定位研究与 C6 的审读记录在源码里没有对应的 semantic，不要硬套别的类型：留在本地（如 `.drama/reviews/`），按 `local_file` 装包。

**步骤**：

1. 读上下文：同下文历史候选的第 1 步，`get_writing_context` 读到 `nextOffset` 为 null 并记回执。页面写入的 `input_snapshot_id` 可选，填上就能看出这一版依据哪份上下文写成。
2. 写入：先把完整输入（含固定的 `request_id`）写成文件，再调用。新页面用 `create_page`；已有页面用 `update_page`，`expected_revision` 取刚读到的当前修订号（没有历史的页面为 0）。正文上限是 JSON 编码后 900,000 字节，超出就拆成多个页面。正文须逐字保真，见 [保存正文逐字保真](#保存正文逐字保真)（读回时用 `read_page`）。响应原样保存，丢失就不存。
3. 记录：`receipt record <项目> <响应> --operation create_page|update_page|restore_page|label_page_revision --request-id <ID> --input <输入>`，写入 `.drama/receipts/<requestId>.json`，`remote` 记 `pageId` 与 `revision`。`label_page_revision` 没有 `request_id` 参数，`--request-id` 只是本地回执的名字。HTTP 409 记 `rejected_conflict`，`notes.conflict` 记服务端的 code 与 details：
   - `VERSION_CONFLICT`：页面已被其他来源更新（details 为 `currentRevision`、`currentFingerprint`）。先 `read_page` 读最新修订，合并后用新的 `request_id`、新的 `expected_revision` 再写。
   - `IDEMPOTENCY_CONFLICT`：同一 `request_id` 配了不同输入（同一项目内唯一；details 是原请求落成的 `pageId`、`revision`）。说明 ID 被误复用，查清原请求再决定，不要改输入重发。

   响应缺失、无法解析、`MCP_OUTCOME_UNKNOWN` 或 5xx 记 `unknown`，`retryAllowed` 恒为 false。
4. 读回与缓存：`read_page` 从 offset 0 读到 `nextOffset` 为 null（offset 按 Unicode 码点计，每块最多 8000）。第二块起每次都带上第一块返回的 `revision` 与 `fingerprint`，正文在读取中途变了服务端会返回 `VERSION_CONFLICT`，从 0 重读。保存每块响应，执行 `receipt cache <项目> <全部分块> [--title <标题>]`：全文写入 `.drama/cache/<pageId>@r<revision>.md`（原样 UTF-8），全文 sha256 必须等于服务端 `fingerprint`，缺块、断档、末块缺失或内容被改都拒绝（退出码 2）。manifest v1 条目记 `pageId`、`revision`、`title`、`labels`、`producer`、`sha256`、`serverFingerprint`、`verified`、`operation`（`read_page`）、`readAt`。页面工具都不返回标题：`title` 取 `--title`，没给时取本地 confirmed `create_page` 回执里的标题，都没有就记 null。`labels` 是读取时看到的标签，之后可能被改写。还没有历史的页面读到的是 r0，不缓存。
5. 对账 unknown：`receipt pending <项目>` 列出未决的页面写入与步骤。mali-story v0.20.0 的 `list_page_revisions` 每行只有 `revision`、`op`、`producer`、`submittedBy`、`inputSnapshotId`、`createdAt`、`label`、`fingerprint`、`restoredFromRevision`，**不带 requestId**，所以无法直接按 request_id 查到修订。两种方式，对账结果另记一份回执，用 `--reconciles <原 requestId>` 指向原回执：
   - 列表：`list_page_revisions(project_id, page_id)` 存成文件，`receipt record <项目> <列表响应> --operation list_page_revisions --request-id <新读取ID> --input <列表输入> --reconciles <原 requestId>`。工具在 `expected_revision` 之后找：`update_page` 要 `op: update`、`fingerprint` 等于输入正文的 sha256、`producer` 相同；`restore_page` 要 `op: restore`、`restoredFromRevision` 等于 `to_revision`、`producer` 相同；找到的修订号记入 notes。这仍是宿主判断（M），`pending` 记为 `resolved_host_judged`。`label_page_revision` 看该修订的 `label` 是否已是所求值，这就是要的状态，记为 `resolved_verified`。列表的 `currentRevision` 不超过 `expected_revision` 时拒绝记录：写入没有落地；列表没列到 `expected_revision` 时用 `before_revision` 继续列。
   - 原样重发（S＋R）：用原 `request_id` 与完全相同的输入再调一次。服务端先按 request_id 查，落地过的直接重放（`replayed: true`），没落地的这次写入。记为 `receipt record <项目> <响应> --operation <原操作> --request-id <原 requestId>.resend-1 --input <原输入> --reconciles <原 requestId>`，工具核对输入指纹与原回执相同，`pending` 记为 `resolved_verified`。`create_page` 的 unknown 还不知道 pageId，只能这样对账。例外：`unchanged: true` 的更新没有记下 request_id，页面之后被改过时重发会得到 `VERSION_CONFLICT`。

   对账前不换新 requestId 重试，以免重复写入。
6. 验收与回退：主创确认某个修订后，用 `label_page_revision(project_id, page_id, revision, label)` 打标签，`label: null` 清除。回退用 `restore_page(project_id, page_id, expected_revision, to_revision, producer, request_id)`，得到的新修订号以回执为准。两者都按第 3 步记回执。

**装包与失效**：`context-pack` 的选材写 `{"kind": "remote_page", "id": "<pageId>", "revision": <n>}`，从缓存按 `pageId@r<n>` 装入；同一页面的两个修订进同一个包时退出码 2。页面出了新修订后运行 `impact <项目> --page <pageId> --revision <n>`，引用该页旧修订的快照与运行标 `stale`。

**批量导入**：`import_pages` 一次最多 20 页、正文合计 900,000 字节，每页独立提交并返回逐页结果，重发同一批会重放已落地的页面。`receipt` 目前不记录批量响应：逐页回执按 `create_page`／`update_page` 单独调用记录，或在运行记录里注明批量结果未入回执。

## 候选保存与对账

本节是迁移前的历史候选（story-artifacts）流程，保留为**只读兼容**：已有候选迁成页面后只读，新的产出按上一节写成页面。下面的 `get_story_artifact`、`list_story_artifacts`、`read_story_artifact` 与 `receipt cache`（带 slot）仍可用来读取迁移前的候选；`impact --slot`／`--artifact` 继续按 slot 判断这些候选的新旧。

工位产出保存为 mali-story 候选时按本节执行。MCP 由宿主调用，响应原样存成 JSON 文件；`scripts/drama_tools.py receipt` 只读这些文件，不联网、不调用 MCP，不能证明响应真实。保存不等于采用：回执 `confirmed` 只说明服务端收下了候选。本地缓存和 save／get／list／read 回执都不是采用证据，采用只认 mali-story 的正式采用结果。

**producer**：`save_story_artifact` 的 `producer` 接受 `codex`、`human`、`external_ai`（mali-story v0.19.0 起，见 [mali-story#2332](https://github.com/ZhiBoLingXi/mali-story/issues/2332)）。只有宿主是 Codex 时写 `codex`；Claude Code、WorkBuddy、ChatGPT 等其他 AI 宿主一律写 `external_ai`；用户本人写的文字写 `human`。不得借用别的值。宿主与模型名记在本地 `run-handoff`，不写进 `producer`。连接的是 v0.19.0 之前的部署、工具里没有 `external_ai` 时，非 Codex 宿主不保存，保留本地稿并注明“未同步到 mali-story”。

**工位产出 → 候选字段**：

| 工位 | kind | slot 示例 | episodeRef |
| --- | --- | --- | --- |
| C1 | `research`、`adaptation_options` | `positioning` | null |
| C2 | `characters` | `characters` | null |
| C3 | `series_outline` | `series-outline` | null |
| C4 | `episode_outline` | `ep-03-outline` | 必填，如 `ep-03` |
| C5 | `episode_draft` | `ep-03-draft` | 必填 |
| C6 | `review` | `ep-03-review` | 针对单集时填写 |

slot 是跨修订的稳定身份：同一产出的每次修订用同一 slot，`revision` 按 slot 递增。artifactId 每次保存都新生成，只用作缓存文件名；本地判断新旧修订一律按 slot。`episode_outline`／`episode_draft` 缺 episodeRef 会被服务端拒绝。

**步骤**：

1. 读上下文：`get_writing_context` 读到 `nextOffset` 为 null，保存响应，`receipt record <项目> <响应> --operation get_writing_context --request-id <读取ID> --input <输入>`。保存时的 `input_snapshot_id` 取其 `snapshotId`；与本地已确认的上下文回执不符时 record 会给出警告。
2. 保存：先把完整输入（含固定的 `request_id`）写成文件，再调用 `save_story_artifact`；`expected_revision` 取该 slot 当前最高修订，新 slot 为 0。响应原样保存，丢失就不存。正文须逐字保真，见下文 [保存正文逐字保真](#保存正文逐字保真)。
3. 记录：`receipt record <项目> <响应> --operation save_story_artifact --request-id <ID> --input <输入>`，写入 `.drama/receipts/<requestId>.json`。成功得到 artifactId、revision；HTTP 409／`VERSION_CONFLICT` 记 `rejected_conflict`，有两种原因：`expected_revision 已过期`，或服务端发现同一 requestId 配了不同输入。前者重新读取后按新修订号用新 requestId 保存；后者说明 requestId 被误复用，先查清原请求再决定，不要改输入重发。响应缺失、无法解析、`MCP_OUTCOME_UNKNOWN` 或 5xx 记 `unknown`，`retryAllowed` 恒为 false。同一 requestId 再次记录相同输入视为重放；输入不同则退出码 2，原回执不变。
4. 缓存：`read_story_artifact` 从 offset 0 连续读到 `nextOffset` 为 null，保存每块响应，执行 `receipt cache <项目> <全部分块> [get 响应]`。全文写入 `.drama/cache/<artifactId>@r<revision>.md`（原样 UTF-8，不加换行），manifest 只追加。全文 sha256 必须等于服务端 `fingerprint`；缺块、断档、末块缺失或内容被改都拒绝（退出码 2）。没有 get 响应时须给 `--slot`、`--kind`（分集还要 `--episode-ref`）。这样给的值只是宿主声明（`slotSource: host`；本地有 slot 一致的 confirmed 保存回执时为 `receipt`，经对账确认的重发回执也算：它的 `localRef` 指向原 unknown 回执、`notes` 记有 `slotCheck`，slot 取原回执的 slot），写错了带 get 响应重新缓存即可纠正：同一产物修订的条目以最强来源为准（`record` > `receipt` > `host`），工具追加一条纠正 slot、kind、episodeRef 的条目，旧条目不改不删；来源相同或更弱而取值不同的调用被拒绝（退出码 2）。保存回执只担保 slot：靠回执的调用只能纠正宿主声明的 slot，kind 或 episodeRef 与已有条目不同时也被拒绝，须带 get 响应。宿主只通过 `receipt` 工具写 manifest，条目不手工修改。只有 `get_story_artifact` 响应时记 `verified: false`，装包默认不用未验证缓存。
5. 对账 unknown：`receipt pending <项目>` 在 `pending` 列出未决的保存，读操作的 unknown 单列在 `read_only_unknown`（重读即可，没有写入需要对账）。`prepare_story_context` 没有按 requestId 查询的办法，其 unknown 列在 `unreconcilable_unknown`：重试前先用 `get_writing_context` 重读上下文状态。回执只追加，对账结果另记一份回执，用 `--reconciles <原 requestId>` 指向原回执；只有 confirmed 的响应能了结 unknown。三种方式：
   - get（S）：`list_story_artifacts(project_id, slot)` → 对高于 expectedRevision 的修订逐个 `get_story_artifact`，比对 `record.requestId` → 找到后 `receipt record <项目> <get 响应> --operation get_story_artifact --request-id <新读取ID> --input <get 输入> --reconciles <原 requestId>`，工具核对 `record.requestId`。
   - list（M）：只凭列表判断时用 list 响应记录；输入须按原保存的 slot 过滤，项目也须一致，且列表中至少有一行同 slot、修订号大于原 expectedRevision、inputSnapshotId 相同，匹配行记入 notes。列表行不带 requestId，这是宿主判断，`pending` 记为 `resolved_host_judged`，不是 `resolved_verified`。列表为空或没有这样的行时拒绝记录：保存多半没有落地，改用重发。
   - 重发（S）：对账后仍未找到时先告知用户；重发只能用原 `request_id` 与完全相同的输入（服务端精确重放幂等，R），响应记为 `receipt record <项目> <响应> --operation save_story_artifact --request-id <原 requestId>.resend-1 --input <原输入> --reconciles <原 requestId>`。工具核对输入指纹与原回执相同、`record.requestId` 等于原 requestId。非 confirmed 的重发（403、unknown 等）照样记为回执，但不了结原 unknown，`pending` 在该项的 `unconfirmedAttempts` 列出；下次重发改用 `.resend-2`。

   get 与重发记为 `resolved_verified`。直接用原 requestId 记录重发响应会被拒绝（`outcome_differs`，退出码 2），因为原回执不会被改写。对账前不换新 requestId 重试，以免重复候选或重复计费。

**旧本地项目导入**：已有本地稿件要成批存成候选时，先 `list_story_artifacts(project_id)`（不过滤，翻完所有页）存成文件，运行 `drama_tools.py import-project preview <项目> --listing <各页响应>` 给主创看计划（将建项、远端已有修订的冲突、跳过原因）；主创确认后再 `import-project apply ... --out <请求目录> --producer <值> --input-snapshot-id <snapshotId>` 生成逐条保存输入，按上面第 2、3、4 步逐条保存、记录、读回核对。映射规则见仓库 README。冲突项不生成请求，安装或计划都不等于保存授权。

`inputFingerprint` 是 `--input` 规范 JSON（键排序、UTF-8、紧凑分隔；忽略以 `_` 开头的顶层注释键）的 sha256，只用于本地冲突判断，与服务端 `requestFingerprint` 算法不同，不能相互比较。

### 保存正文逐字保真

模型转写长正文时会悄悄改字：D3 出现过两次，直引号变弯引号、省略号变破折号，保存的候选与本地稿不再一致。保存正文时：

1. 先把要传的正文写成文件，与源文件用 `cmp` 比对一致后，才把这个文件的内容放进保存输入；不要凭记忆或重新输入一遍正文。
2. 保存后按步骤 4 读回全文（页面用 `read_page`，历史候选用 `read_story_artifact`），比对服务端 `fingerprint` 与本地源文件的 sha256（`sha256:<hex>`）。一致才算保存的是这份稿。页面写入的响应本身就带 `fingerprint`，可以先比一次。
3. 不一致时只做一次纠错重存：用新的 `request_id`（原 ID 加 `-fix`，如 `ep45-draft-save-1-fix`），`expected_revision` 取刚才那个错误修订号，正文按第 1 条重新准备。错误的修订保留在远端（页面上它已是当前内容，纠错后的修订接替它），不删除、不打验收标签，在运行日志（`run-handoff` 的 `unknowns` 或 `unfinished`）注明它的修订号与错在哪里。纠错后仍不一致就停下，告知用户，不再重试。
