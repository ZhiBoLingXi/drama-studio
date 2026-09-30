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

如部署提供专业候选、采用与连续性工具，遵循其快照与版本契约。Brief 使用专用 get/save/approve，save 带读取到的 expected_revision；通过当前会话可用工具确认具体名称。不能用通用块写入绕过正式采用规则。

没有候选保存能力时继续保留本地草稿，明确“未同步到 mali-story”，不宣布服务端接续成功。检查工具不存在时也不虚构已调用。

## 候选保存与对账

工位产出保存为 mali-story 候选时按本节执行。MCP 由宿主调用，响应原样存成 JSON 文件；`scripts/drama_tools.py receipt` 只读这些文件，不联网、不调用 MCP，不能证明响应真实。保存不等于采用：回执 `confirmed` 只说明服务端收下了候选。本地缓存和 save／get／list／read 回执都不是采用证据，采用只认 mali-story 的正式采用结果。

**producer**：当前 `save_story_artifact` 的 `producer` 只接受 `codex` 与 `human`（#3／#15 决定）。Codex 宿主写 `codex`，用户本人提交的文字写 `human`。其他宿主不得借用这两个值，也不保存，直到 mali-story 增加代表 AI 宿主的取值（用户 2026-09-30 决定；跟踪 issue 尚未建立）；此前保留本地稿，注明“未同步到 mali-story”。

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
2. 保存：先把完整输入（含固定的 `request_id`）写成文件，再调用 `save_story_artifact`；`expected_revision` 取该 slot 当前最高修订，新 slot 为 0。响应原样保存，丢失就不存。
3. 记录：`receipt record <项目> <响应> --operation save_story_artifact --request-id <ID> --input <输入>`，写入 `.drama/receipts/<requestId>.json`。成功得到 artifactId、revision；HTTP 409／`VERSION_CONFLICT` 记 `rejected_conflict`，有两种原因：`expected_revision 已过期`，或服务端发现同一 requestId 配了不同输入。前者重新读取后按新修订号用新 requestId 保存；后者说明 requestId 被误复用，先查清原请求再决定，不要改输入重发。响应缺失、无法解析、`MCP_OUTCOME_UNKNOWN` 或 5xx 记 `unknown`，`retryAllowed` 恒为 false。同一 requestId 再次记录相同输入视为重放；输入不同则退出码 2，原回执不变。
4. 缓存：`read_story_artifact` 从 offset 0 连续读到 `nextOffset` 为 null，保存每块响应，执行 `receipt cache <项目> <全部分块> [get 响应]`。全文写入 `.drama/cache/<artifactId>@r<revision>.md`（原样 UTF-8，不加换行），manifest 只追加。全文 sha256 必须等于服务端 `fingerprint`；缺块、断档、末块缺失或内容被改都拒绝（退出码 2）。没有 get 响应时须给 `--slot`、`--kind`（分集还要 `--episode-ref`）。只有 `get_story_artifact` 响应时记 `verified: false`，装包默认不用未验证缓存。
5. 对账 unknown：`receipt pending <项目>` 在 `pending` 列出未决的保存，读操作的 unknown 单列在 `read_only_unknown`（重读即可，没有写入需要对账）。`prepare_story_context` 没有按 requestId 查询的办法，其 unknown 列在 `unreconcilable_unknown`：重试前先用 `get_writing_context` 重读上下文状态。回执只追加，对账结果另记一份回执，用 `--reconciles <原 requestId>` 指向原回执；只有 confirmed 的响应能了结 unknown。三种方式：
   - get（S）：`list_story_artifacts(project_id, slot)` → 对高于 expectedRevision 的修订逐个 `get_story_artifact`，比对 `record.requestId` → 找到后 `receipt record <项目> <get 响应> --operation get_story_artifact --request-id <新读取ID> --input <get 输入> --reconciles <原 requestId>`，工具核对 `record.requestId`。
   - list（M）：只凭列表判断时用 list 响应记录；输入须按原保存的 slot 过滤，项目也须一致，且列表中至少有一行同 slot、修订号大于原 expectedRevision、inputSnapshotId 相同，匹配行记入 notes。列表行不带 requestId，这是宿主判断，`pending` 记为 `resolved_host_judged`，不是 `resolved_verified`。列表为空或没有这样的行时拒绝记录：保存多半没有落地，改用重发。
   - 重发（S）：对账后仍未找到时先告知用户；重发只能用原 `request_id` 与完全相同的输入（服务端精确重放幂等，R），响应记为 `receipt record <项目> <响应> --operation save_story_artifact --request-id <原 requestId>.resend-1 --input <原输入> --reconciles <原 requestId>`。工具核对输入指纹与原回执相同、`record.requestId` 等于原 requestId。非 confirmed 的重发（403、unknown 等）照样记为回执，但不了结原 unknown，`pending` 在该项的 `unconfirmedAttempts` 列出；下次重发改用 `.resend-2`。

   get 与重发记为 `resolved_verified`。直接用原 requestId 记录重发响应会被拒绝（`outcome_differs`，退出码 2），因为原回执不会被改写。对账前不换新 requestId 重试，以免重复候选或重复计费。

`inputFingerprint` 是 `--input` 规范 JSON（键排序、UTF-8、紧凑分隔；忽略以 `_` 开头的顶层注释键）的 sha256，只用于本地冲突判断，与服务端 `requestFingerprint` 算法不同，不能相互比较。
