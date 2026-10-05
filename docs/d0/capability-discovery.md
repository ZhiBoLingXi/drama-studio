# mali-story 线上能力发现（只读）

源码存在不等于部署可用。本文件分开记录源码证据、宿主连接、鉴权与业务读写。

## 2026-09-29 · Claude Code（本机）

| 层 | 结果 | 证据 |
| --- | --- | --- |
| 宿主连接 | **未连接** | `claude mcp list` 只有 Claude Docs、Google Drive、Gmail、Google Calendar；无 mali-story；两个仓库都没有 `.mcp.json` |
| 鉴权 | 未检查 | 无连接 |
| 业务读取 | 未检查 | 无连接 |
| 候选写入 | 未检查 | 无连接，也没有获准的测试项目 |

结论：D1 的远端适配无法开始。

## 2026-09-30 · Claude Code（本机），用户级连接 `https://story-api.maliai.art/mcp`

| 层 | 结果 | 证据 |
| --- | --- | --- |
| 宿主连接 | 已连接 | `claude mcp add --scope user` 后经 `/mcp` 完成 OAuth |
| 暴露的 MCP 工具 | 只有 6 个 | `list_api_endpoints`、`api_get`、`api_mutate`、`get_story_brief`、`save_story_brief`、`approve_story_brief` |
| 鉴权 | 成功 | `GET /api/v1/me` → 200，role `admin` |
| 业务读取 | 成功 | `GET /api/v1/projects` → 200，返回 11 个项目（`limit=3` 未生效） |
| 候选相关路由 | **线上不存在** | `list_api_endpoints` 共 251 条，全部翻页核对：没有 `story-artifacts`、`writing-context`、`creative-context`、`story-catalog` 任何路由；也没有 `save_story_artifact`／`get_writing_context`／`prepare_story_context` 等专用工具 |
| 候选写入 | 未尝试 | 路由不存在；且未指定测试项目 |

线上存在、可能相关但不等价的路由：`/projects/:projectId/blocks`（带 revisions／restore）、`/projects/:projectId/facts`、`/episode-drafts/:runId/candidates/:candidateId`、`/continuation-workflows`、`/projects/:projectId/milestones/:milestoneId/approve`。它们的契约没有核对，不能直接当作 StoryArtifactService 的替代。

**结论**：连接与鉴权问题已解决，但线上部署落后于源码（源码 `a397db7e` 有候选服务，线上未挂载）。D1 的阻塞从“未连接”变为“候选接口未部署”。按路线 §8，不改为本地版本库；可选路径：

1. 部署含 StoryArtifactService／WritingContextService 路由与 MCP 工具的 mali-story 版本（推荐，与架构一致）。
2. 评估 `blocks` 的修订接口能否满足候选契约（请求身份、expectedRevision、输入快照绑定）；这需要读其契约并在测试项目上验证，且 blocks 可能直接是正式正文，风险更高。

## 2026-09-30 · 生产发版 v0.18.0

为部署候选接口，从 main `c6aebcf3` 发布 v0.18.0（含 mali-common 鉴权修复 `ae0f087`）。GitHub Actions 部署任务未启动：“recent account payments have failed or your spending limit needs to be increased”。**生产仍为 v0.17.11，候选接口未上线。** 账单处理后重跑 run `36668448821`。

## 2026-10-05 · 生产 v0.18.1

账单恢复后，2026-10-01 重跑 run `36668448821`（第 2 次尝试）：任务启动，但在“Build script-server”失败，`bun build` 无法解析 `proxy-agent`。原因是 mali-common `fb4fd8f` 在 `storage/oss.ts` 静态引入 `ali-oss`，其依赖 urllib 有一处惰性的 `require('proxy-agent')`，该可选依赖未安装。构建在传输镜像与迁移之前失败，生产未被改动。v0.18.0 按标签无法部署。

修复：mali-story#2333 给服务端 `bun build` 加 `--external proxy-agent`（urllib 只在显式启用代理时才加载它）。修复拣选到 `release/v0.18.x`（`1156b278`，代码与 main `de0c9d11` 一致），发布 v0.18.1。

| 层 | 调用成功 | 业务结果符合预期 | 证据 |
| --- | --- | --- | --- |
| 部署 | 是 | 是 | run `37263555141`，结论 `success`，2026-10-05 04:26–04:32 UTC，构建、传输、迁移、重启全部通过 |
| 数据库迁移 | 是 | 是 | 迁移日志共 43 条 `Applied`，从 `0085_story_artifact_candidates` 到 `0127_uncapped_shared_creation_budget`，无错误 |
| 候选路由 | 是 | 是 | `list_api_endpoints(prefix=/api/v1/projects/:projectId/story-artifacts)` 共 7 条，含 `GET`／`POST …/story-artifacts`、`GET …/:artifactId`、`GET …/:artifactId/text`；`prefix=…/writing-context` 返回 `GET /api/v1/projects/:projectId/writing-context` |
| MCP 候选工具 | 未检查 | 未检查 | 本次会话的连接建立于部署前，工具列表未刷新；由 #3 在重新连接后核对 |
| 注册／登录 `emailVerified` | 未检查 | 未检查 | 只读抽查不可行：经 MCP 调用 `GET /api/v1/me` 返回 `MCP_ROUTE_NOT_ALLOWED`（2026-09-30 时可用），且不为抽查新注册账号；需人工登录核对 |

本节只证明部署与路由已上线，不证明候选保存在生产可用：生产写入探测（保存、读取、重放、冲突）由 #3 执行，并依赖 mali-story#2332 提供如实的 `producer` 值 `external_ai`。

## 2026-10-05 · 生产 MCP 工具层（v0.19.0，#3）

宿主：Claude Code，用户级连接 `https://story-api.maliai.art/mcp`。v0.19.0（含 `external_ai`，mali-story#2334）部署后需要在 `/mcp` 重新连接，工具列表才从 6 个刷新为完整列表；一次重连后已运行的会话仍可能沿用旧列表。

测试项目「山门最后一张欠条｜十集试点」`4e6556ac97654bf781977`，slot 以 `d1-probe` 开头，候选正文标明“非创作内容，不得采用”。原始返回与入参见 [tests/fixtures/mcp/](../../tests/fixtures/mcp/)（`submittedByUserId` 已替换为 `<redacted-user-id>`，无凭据）；回执由 `drama_tools.py receipt record` 生成，见 [prod-receipts-2026-10-05](prod-receipts-2026-10-05/)。

| 步骤 | 工具 | 调用成功 | 业务结果符合预期 | 观察 | 回执 |
| --- | --- | --- | --- | --- | --- |
| 01 读写作上下文 | `get_writing_context` | 200 | 是 | 返回 `snapshotId`；`approvedBrief` 为 null，`missingSources: ["approved_brief"]`，`blocks` 为空 | `d1-probe-ctx-1` confirmed |
| 02 保存 | `save_story_artifact` | 200 | 是 | revision 1，`producer: external_ai`，绑定 01 的快照 | `d1-probe-save-1` confirmed |
| 03 读取 | `get_story_artifact` | 200 | 是 | 全文与保存一致；无全文指纹 | `d1-probe-get-1` confirmed |
| 04 列举（按 slot） | `list_story_artifacts` | 200 | 是 | 行不带 `requestId`，带 `characterCount` | `d1-probe-list-1` confirmed |
| 05 同 requestId 重放 | `save_story_artifact` | 200 | 是 | 同一候选 id，`idempotent: true` | 与 02 同键同指纹，工具输出 `replay`，不新增文件 |
| 06 同 requestId 异内容 | `save_story_artifact` | 409 | 是 | `VERSION_CONFLICT`：Request ID already identifies different candidate content | 本地工具先行拒绝（同键异指纹，退出码 2），不写回执 |
| 07 过期 expectedRevision | `save_story_artifact` | 409 | 是 | `VERSION_CONFLICT`：Candidate slot revision is stale | `d1-probe-save-stale-1` rejected_conflict |
| 08 长候选保存（P1） | `save_story_artifact` | 未知 | — | 调用时 MCP 会话过期，无响应 | `d1-probe-save-long-1` unknown |
| 08 对账 | `list_story_artifacts` | 200 | 是 | slot `d1-probe-long` 为空：保存未落库 | — |
| 08 同请求重发 | `save_story_artifact` | 200 | 是 | `idempotent: false`，新候选 `282a6bf6…`，确认首次未落库 | `d1-probe-save-long-1.resend-1` confirmed，`pending` 归入 `resolved_verified` |
| 08 分块读取 | `read_story_artifact` | 200 ×2 | 是 | 4135 码点（含 🎬）：0–4000、4000–4135，末块 `nextOffset: null`；拼接全文 sha256 等于 `fingerprint` | `receipt cache` 写入，manifest `verified: true` |

**MCP 与本地 REST 的差异：**

| 项 | 本地 REST（2026-09-30） | 生产 MCP |
| --- | --- | --- |
| 工具名／路由 | `POST/GET /api/v1/projects/:projectId/story-artifacts`、`…/:artifactId`、`…/:artifactId/text`、`GET …/writing-context` | `save_story_artifact`、`get_story_artifact`、`list_story_artifacts`、`read_story_artifact`、`get_writing_context` |
| 参数命名 | 路径参数 + camelCase 请求体（`expectedRevision`、`inputSnapshotId`、`requestId`、`episodeRef`） | snake_case（`project_id`、`expected_revision`、`input_snapshot_id`、`request_id`、`episode_ref`、`artifact_id`、`cursor_id`）；**例外**：`read_story_artifact` 用 camelCase（`projectId`、`artifactId`） |
| `producer` | 请求体字段 | 必填，`codex｜human｜external_ai`；Claude Code 写 `external_ai` |
| 成功返回包装 | `{requestId, data, error}` | `mali-tool-result/v1`：`{schemaVersion, ok, data, recovery, transport.status}` |
| 失败返回包装 | `{requestId, data: null, error}` + HTTP 状态 | Claude Code 收到的是不带 `mali-tool-result/v1` 的分发信封 `{status, headers, body: {data: null, error: {code, message, retryable}}}` |
| 分块读取 | `GET …/text?offset&limit` | 同字段；Claude Code 在 JSON 前另显示一条资源链接（`mali-story://projects/…/chunks/<offset>`） |
| 冲突错误码 | 409 `VERSION_CONFLICT` | 同 |

`receipt` 的解析器能处理上述两种返回形状（`tests/test_receipt.py` 的 `RealFixtureTests` 用这些真实夹具回归）。

**发现的缺口（另行跟踪，不阻塞 #3）：** 只给分块响应加 `--slot` 缓存时，若该候选的保存是经对账重发确认的，`slotSource` 仍为 `host`：重发回执的 `localRef` 指向被对账的回执而不是 slot，`receipt cache` 认不出它能担保 slot。目前的做法是把重发（或 get）响应一起传给 `receipt cache`，`slotSource` 即为 `record`。

## 2026-09-30 · 本地部署（非生产）

mali-story main `c6aebcf3`，独立库 `mali_story_d1`（先迁移 mali-common，再迁移 script-server 共 122 个），API `http://localhost:3011`，Web `http://localhost:3010`。测试项目为本地新建的「山门最后一张欠条｜十集试点（本地 D1）」，与生产同名项目无关。

| 步骤 | 调用 | 业务结果 | 回执（`contract-check` 通过） |
| --- | --- | --- | --- |
| 读取写作上下文 | 200 | 返回 `snapshotId`（sha256） | `01-writing-context.json` |
| 保存候选（新 slot，expectedRevision 0） | 200 | 返回 id 与 revision 1，绑定 inputSnapshotId | `02-save.json` |
| 读取候选 | 200 | 全文一致；另含 `sourceValidation`、`sourceState` | `03-get.json` |
| 列举候选（按 slot） | 200 | 返回该候选；列表带 `adoptionStatus: not_resolved` | `04-list.json` |
| 同 requestId、同内容重放 | 200 | 返回同一候选 id | — |
| 同 requestId、不同内容 | 409 | `VERSION_CONFLICT`：Request ID already identifies different candidate content | `06-requestid-conflict.json` |
| 过期 expectedRevision | 409 | `VERSION_CONFLICT`：Candidate slot revision is stale | `07-stale-revision.json` |

回执见 [local-receipts-2026-09-30](local-receipts-2026-09-30/)。这些是 REST 层证据；**MCP 工具层尚未在本地验证**：Claude Code 的 HTTP 请求经本机代理（Privoxy）转发，访问 `localhost:3011/mcp` 返回 500，需要让 Claude Code 对 localhost 绕过代理后再授权。

结论：候选契约（快照绑定、幂等重放、请求身份冲突、修订冲突）在当前 main 上按设计工作，满足 D1 远端适配的前提；生产可用性仍待部署。

## 源码证据（mali-story `a397db7e`，仅说明“应当存在”）

`apps/script-server/src/interfaces/mcp/api-mcp-server.ts` 按 scope 与已挂载路由注册以下与 D1 相关的工具：

| 工具 | scope | 用途 | 关键输入 |
| --- | --- | --- | --- |
| `save_story_artifact` | 写 | 保存不可变候选 | slot、kind、expectedRevision（新 slot 为 0）、body、inputSnapshotId、requestId |
| `get_story_artifact` | 读 | 读取候选全文与输入快照 | artifactId |
| `list_story_artifacts` | 读 | 列举候选、按 kind／slot 过滤、分页；断线后对账 | limit、cursorId、kind、slot |
| `read_story_artifact` | 读 | 按码点区间读取长文，返回全文 SHA-256 | projectId、artifactId、offset、limit |
| `get_writing_context` | 读 | 版本化来源快照 | — |
| `prepare_story_context` | 写 | 显式选材、新鲜度、超量拒绝 | — |

候选 kind 枚举：research、adaptation_options、characters、series_outline、episode_outline、episode_draft、review。工位契约的产出 kind 按此对应。

`remote-receipt` Schema 的 `operation` 枚举与上表一致；字段 `requestId`、`inputSnapshotId`、`artifactId`、`revision` 对应源码的输入与返回。

## 解除阻塞后的检查清单

1. `list_projects`：确认身份与可见项目；不为探测新建项目。
2. 在获准测试项目上 `get_writing_context`：记录快照 ID。
3. `save_story_artifact`（新 slot，expectedRevision 0）→ `get_story_artifact` → `list_story_artifacts`：记录三份 `remote-receipt`，用 `contract-check remote-receipt` 校验。
4. 以相同 requestId、相同 body 重放：应返回同一结果；相同 requestId、不同 body：应被拒绝。
5. 以过期 expectedRevision 保存：应返回冲突。

每一步分别记录“调用成功”与“业务结果符合预期”，不合并成一个“已接通”。
