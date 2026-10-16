# Drama Studio · 短剧创作工作室

把这个仓库交给 AI，让它安装短剧创作工作流。复用 Codex、Claude Code、ChatGPT 或 WorkBuddy 的模型与工具，通过 mali-story MCP 使用已有拉片和项目能力。

各版本的变化见 [CHANGELOG.md](CHANGELOG.md)。

## 让 AI 安装

在有文件／命令权限的 AI 工具中，发送仓库地址并说：

> 请浏览 https://github.com/ZhiBoLingXi/drama-studio ，阅读 README.md 和 INSTALL.md，按我当前的 AI 工具安装 Drama Studio。先检查环境和已有安装，保留我的配置与修改，安装后引导我初始化工作目录、数据更新方式与常用偏好；询问是否开启定时采集，开启时确认时间和时区。验证技能发现，并按选择验证 mali-story MCP 连接。需要我登录时给出授权入口，不要启动创作或付费任务。

仓库目前为私有：用户的 GitHub 账号需具有读取权限，AI 所在环境也需能通过该账号访问。仅将链接粘贴到未授权的网页聊天中，无法读取仓库；可改为导入已获授权下载的技能包。

AI 的操作入口是 **[INSTALL.md](INSTALL.md)**。安装脚本只需要 Python 3.10+，不用安装 Python 包，不修改模型配置。用户无需手写 YAML、JSON 或复制个人密钥。

当前源码版本 `0.7.2` 提供自包含 Skill、离线安装／升级／校验、技能包导出及本地检查工具。0.3.0 起内容以 mali-story 带版本的页面保存（像飞书文档：新版本立即生效，验收打标签，回退用恢复），需要 mali-story v0.20.0 及以上；旧版存的候选仍可读取。它不是已发布到各平台市场的应用；完整创作、视频上传、桌面操作和宿主真实验收的状态见 [支持范围](docs/hosts.md)。

## 让 AI 升级

已经装过 Drama Studio 的，对 AI 说：

> 按 drama-studio 仓库里 INSTALL.md 的“升级已有安装”一节，把我当前 AI 工具里的 Drama Studio 升级到最新版本。先检查已有安装和仓库状态，保留我的修改；升级后验证技能文件，并确认 mali-story MCP 连的是 story-api 服务、能看到页面工具。不要启动创作或付费任务。

AI 会自己拉取最新代码、升级并校验；安装器会拒绝覆盖你手动改过的文件，旧版本留作备份。

## 初始化工作室

安装后由 AI 检查已有环境和配置，分步询问必要选择，不要求用户手写配置。可直接说“初始化工作室”“把榜单采集改到每天北京时间9点”或“检查自动更新状态”。更改时间只修改已授权任务；没有已开启任务时先询问是否开启。

[初始化模块](skills/drama-studio/references/initialization.md)涵盖工作目录、数据入口、定时更新、账号连接、创作偏好、交付、费用和数据维护；选择与实际验证状态保存为工作目录中的 `STUDIO.md`。默认不开定时采集、付费任务、自动上传或对外通知。完整方案与尚未实现的执行器能力见[初始化设计](docs/initialization-design.md)。

## 装好后怎么用

> 帮我研究近期适合低成本漫剧的女频复仇题材，推荐三部对标，先给依据。

> 使用已有拉片模板，给我三个原创选题，选定后出全剧蓝图。

> 继续这个项目，读取编剧修订后的集纲，再写下一批正文。

> 按已审集纲写第 31–40 集正文。

这类请求默认走[工位流程](skills/drama-studio/references/writing.md#工位流程)，不再一次写完一批再整体自检：先 `status` 找到项目，没有项目就 `init-project`，把集纲和前文转成文本放进 `runs/input/`；按因果依赖分批（[整季分批](skills/drama-studio/references/workstations/season-run.md)），每集一个页面、一个写者；每集用 `context-pack --role author` 装包，C5 写正文，C6 先用 `reader_effect` 包首读并封存记录，再次读；C5 层的问题定向修订一次，C4 及以上的问题写成变更提案交编剧决定；正文逐字核对后存为 mali-story 页面修订，`receipt record`／`receipt cache` 记回执，`run-handoff` 写进 `.drama/runs/`；前一批存好后才给下一批装包。

保存页面需要已授权的 mali-story 连接。没有连接时走[离线降级](skills/drama-studio/references/writing.md#离线与单代理降级)：装包与两读照做，材料放在项目 `runs/` 或 `.drama/` 下按 `local_file` 装入，回执记 `not_sent`，交付标“本地草稿，未写入 mali-story”；宿主不能开子代理时，审读记录如实写 `serial_self_review`。单集篇幅按项目规格核对，没有规格先问。

> 在现有方向和制作条件内自主优化。保留当前完整稿，补充有来源的生活材料，探索不同因果的方案，先试关键场面再决定是否扩写；分别报告可编辑性、辨识度和阅读反馈。

工作流：市场研究 → 对标确认 → 优先复用模板／必要时获取视频并调用 mali-story 拉片 → 生活材料与创作立场 → 不同因果选题 → 用户确认选题 → 剧情框架、人物小传、完整集纲和前 10 集正文 → 用户审批通过 → 完成全剧正文 → 审查、交付和反馈修订。已有阶段成果可直接接续。

按需加载方法参考，不依赖用户另装 DramaRewrite、DramaContinuation 等个人技能目录。模型负责判断与创作，脚本负责能客观计算的检查，编剧决定关键方向和稿件采用。

[创作开发方法](skills/drama-studio/references/development-lab.md) 随技能分发，附开发记录和分阶段阅读模板，由 AI 按需填写。当前完整稿与探索片段分别保存，避免失败探索覆盖可用版本。评审分别判断因果底线、辨识度和阅读偏好，不以字面低重合或平均高分宣称优质；无独立上下文时如实使用串行自评。

## 可选榜单数据

可直接运行已有 Yoki 红果部署的采集／查询脚本，无需启动 MCP；已有红果 MCP 或 JSON／Markdown 导出也可复用。安装器本身不创建数据库或定时任务。安装后的[初始化引导](skills/drama-studio/references/initialization.md)让用户选择是否采集、是否定时，以及时间、时区和范围；未选择不启用。详见[接入与数据边界](skills/drama-studio/references/hongguo-rank.md)及[候选交接模板](skills/drama-studio/templates/benchmark-research.md)。榜单辅助选研究对象，实际拉片继续复用 mali-story。

试用：“用已有红果榜单资料，筛选适合两人两室的家庭悬疑漫剧对标，说明持续性证据与缺口；我选定后再核对 mali-story 模板。” [合成场景验收](evals/market-research/README.md)覆盖文件降级与片段模板交接。

## 各入口的安装方式

| 入口 | 本仓库提供 | 实际使用前还需确认 |
| --- | --- | --- |
| Codex | 复制到标准技能目录，支持用户级／项目级 | 宿主发现技能、mali-story 授权 |
| Claude Code | 复制到标准技能目录，支持用户级／项目级 | 宿主发现技能、mali-story 授权 |
| WorkBuddy | 带所需元数据的 ZIP；确认目录后也可本地安装 | 当前版本导入、MCP 连接、本地命令能力 |
| ChatGPT | 桌面本地技能指南、Skill ZIP 与远程 MCP 说明 | 桌面技能发现；网页插件尚未发布，ZIP不等于云端安装 |

纯网页聊天不能因为读了仓库就自动获得本机文件和桌面操作权限。无命令权限时先确认是否存在兼容的技能／插件入口与远程连接；缺少可用远程检查服务时如实标注“客观检查未执行”。

## 开发者与手动安装命令

以下在仓库根目录执行；`--host` 可换为 `claude-code`。默认安装当前宿主的用户级技能，不覆盖已有本地修改。

先用 `python3 --version` 确认至少 3.10；若默认解释器过旧，使用已有的 `python3.10` 或更新版本执行以下命令。

```sh
python3 -B scripts/install.py plan --host codex
python3 -B scripts/install.py install --host codex
python3 -B scripts/install.py verify --host codex
```

项目级：在上述命令加 `--scope project --project /absolute/path/to/workspace`。升级加 `--upgrade`；只有原安装未被修改才替换，旧版本移到技能目录旁边的 `.drama-studio-backups/`（返回的 backup 路径），不留在技能目录里。0.3.3 及更早版本把备份放在技能目录内的 `.drama-studio-backup-*`，宿主会把它列成第二个技能，可以移走或删除。

导出技能包：

```sh
python3 -B scripts/install.py package --host workbuddy
python3 -B scripts/install.py package --host chatgpt
```

生成 `dist/drama-studio-workbuddy.zip` 或 `dist/drama-studio-chatgpt.zip`。内容只有自包含技能，不包括仓库工作资料、视频或账号。输出已存在且内容不同时要求新路径，不静默覆盖。

已发布的包从 [GitHub Releases](https://github.com/ZhiBoLingXi/drama-studio/releases) 获取，同样需要仓库读取权限。Release 不自动跟随 main 更新；测试当前改动请克隆 main 后安装或重新打包，不能用旧版附件替代。

本地工具（安装后使用安装目录中的同名脚本）：

```sh
python3 -B skills/drama-studio/scripts/drama_tools.py doctor
python3 -B skills/drama-studio/scripts/drama_tools.py init-project ../my-drama --title '我的新剧'
python3 -B skills/drama-studio/scripts/drama_tools.py episode-check examples/sample-episode.md
python3 -B skills/drama-studio/scripts/drama_tools.py dup-check --new examples/sample-episode.md --source examples/sample-reference.md
python3 -B skills/drama-studio/scripts/drama_tools.py reference-check /absolute/path/to/template-detail.json
python3 -B skills/drama-studio/scripts/drama_tools.py contract-check context-snapshot skills/drama-studio/schemas/examples/context-snapshot.json
python3 -B skills/drama-studio/scripts/drama_tools.py knowledge validate ../my-drama
python3 -B skills/drama-studio/scripts/drama_tools.py knowledge search ../my-drama --workstation C5 --type K3
python3 -B skills/drama-studio/scripts/drama_tools.py knowledge show ../my-drama kc-apology-cost --revision 1
```

逐集检查默认只统计，返回 `constraint_status: not_configured`、`passed: null`；退出码 0 仅表示统计已完成。它不会因示例短而判剧本不合格，也不评价创作质量。

场标题支持传统 `场11-1 ...` 和 Markdown `### 11-1 ...`，新增逐集解析覆盖；跨集/重复场号报输入错误，未知标题或正文不用于证明地点上限。代码围栏中的示例不作为实际剧本解析，完整说明见 [剧集检查](skills/drama-studio/references/episode-check.md)。

制作停滞时可用 [手工试点指南](skills/drama-studio/references/production-pilot.md) 和 [交接模板](skills/drama-studio/templates/production-pilot.md) 先验证具体场面；真实反馈缺失时只完成离线准备。当前没有 workflow-check、自动资源预约或制作放行引擎；这些记录由宿主协助维护，不因模板填完而通过。

人物不贴人设、台词同质或情绪平时，使用 [人物与情绪改稿](skills/drama-studio/references/character-emotion.md)：从前文恢复人物写法，先改关键选择与心理过程，再写对白并比较完整样段。事实下限、明确修改目标和开放偏好分别裁决；无硬矛盾不能代替本轮意见已解决。这是写作与评审方法，不是自动创作评分器，也不保证每次质量达成。

项目已有明确制作规格时，由 AI 按约定填写配置并显式使用；配置不会自动发现或自动启用。以下配置仅演示格式：

```sh
python3 -B skills/drama-studio/scripts/drama_tools.py episode-check examples/sample-episode.md --config examples/episode-constraints.json
python3 -B skills/drama-studio/scripts/drama_tools.py episode-check examples/sample-episode.md --min-chars 1200
python3 -B skills/drama-studio/scripts/drama_tools.py episode-check examples/sample-episode.md --preset legacy-aigc
```

第二条只检查显式指定的字数约束，示例应返回退出码 2。第三条显式启用历史 AIGC 示例规格，不代表行业标准。规则格式、来源、优先级及结果解释见 [剧集检查说明](skills/drama-studio/references/episode-check.md)。

`doctor` 只证明离线工具可加载，不能证明 MCP 已连接。项目初始化只建立本地工作目录，不创建远端项目。完整命令参数使用 `--help` 查看。

`contract-check <对象> <文件>` 校验[创作工位契约](skills/drama-studio/references/workstations/README.md)的交接对象（task、knowledge-card、context-snapshot、review-record、run-handoff、remote-receipt），Schema 在 `skills/drama-studio/schemas/`，示例在 `skills/drama-studio/schemas/examples/`。它拒绝超预算快照、混入评估材料、必需材料缺失却标完整、非上游变更提案、本地自称已采用等情况，退出码 2 表示违反；通过不代表远端引用存在或创作达标。首版知识卡只接受项目私有范围。`run-handoff` 有两个可选字段 `finishedAt`、`additionalSnapshotIds`，`review-record` 有可选字段 `additionalTargets`（按批审读时的其余目标）；不写这些字段的旧记录照样通过。

D2／D3 试点后补充的工位方法：[定向修订单独装包](skills/drama-studio/references/workstations/README.md#定向修订单独装包)、[并行子代理的临时文件](skills/drama-studio/references/workstations/README.md#并行子代理的临时文件)、[C6 审读包装什么](skills/drama-studio/references/workstations/c6-review.md#审读包装什么)（正文引用到的前文场面、已精修的前一集）、[保存正文逐字保真](skills/drama-studio/references/mali-story.md#保存正文逐字保真)。

`context-pack` 按任务和宿主给出的选材清单（`selection`，格式见 `skills/drama-studio/schemas/selection.schema.json` 与示例）确定性地组装 `context-snapshot`。选材是模型的判断，装包只做读取、截取、计数、过滤和写出：

```sh
python3 -B skills/drama-studio/scripts/drama_tools.py context-pack ../my-drama --task task.json --selection selection.json --role author --budget 20000
python3 -B skills/drama-studio/scripts/drama_tools.py context-pack ../my-drama --task task.json --selection selection.json --role reader_effect --budget 20000 --dry-run
```

- 只读 `--task`、`--selection`、`.drama/cache/manifest.json` 指向的缓存文件（路径必须在 `.drama/cache/` 内）、`knowledge/cards/<cardId>@r<修订>.json`，以及选材清单里 `local_file` 项指向的项目内文件；只写 `.drama/snapshots/<snapshotId>.json` 与 `.sha256`。不联网、不调用模型，也不代表远端已核验。
- 第 0 项总是任务本身（`task` 分区，由工具按 `--task` 填入，选材清单里不能写 `task` 分区）。选材清单为空时输出只含任务的最小快照；任务字数计入 `--budget`。
- `range` 是按 Unicode 码点截取（`text[start:end]`，中文一字计 1），不是字节。`chars` 与各项 `sha256` 由工具按实际截取文本计算；清单里宿主估算的 `chars` 被忽略。知识卡按卡片 JSON 文件原文计数和截取（含 JSON 标点），不是只算正文字段。
- 快照 ID 为 `ctx-` 加内容哈希前 16 位，不含时间戳；同一输入重跑产出逐字节相同的文件，已存在且相同时报告 `existing: true`，内容不同则拒绝，绝不覆盖。
- 缓存或知识卡不存在 → 记入 `omitted`（reason `missing`），必需项缺失时 `completeness: incomplete`，退出码仍为 0；退役知识卡记为 `not_relevant`。
- 页面（架构 v1.2）用 `{"kind": "remote_page", "id": "<pageId>", "revision": <n>}` 引用，按 manifest 里 `pageId` 与 `revision` 都相同的条目读取 `.drama/cache/<pageId>@r<n>.md`；revision 必须是整数，否则退出码 1。迁移前的历史候选仍按 `remote_artifact` 引用。manifest 的 v0 与 v1 都能读。
- 退出码 2（不写任何文件，错误指出选材序号与引用）：超预算（按分区报告字数与超出量，不截断）、缓存字节与 manifest 的 sha256 不符、manifest 标 `verified: false`、同一页面出现两个修订、同一 slot 出现两个修订（slot 取该产物修订来源最强的 manifest 条目，见下文 `slotSource`）或同一知识卡两个修订、`evaluation_only`／`comparison_only` 进入不允许的角色、`reader_effect` 带 `current_plan`、最终快照未通过 `contract-check`。退出码 1：输入错误，如区间越界（指出引用与文本长度）、引用类型不是 `remote_page`／`remote_artifact`／`knowledge_card`／`local_file`、修订为空、任务未指定工位。
- `local_file` 用于定向修订时装入审读记录、修改单等本地文件：`ref.id` 写项目内相对路径，只能在 `.drama/`（不含 `.drama/cache/`）、`runs/` 或 `planning/`（0.5.0 起）之内，例如 `{"kind": "local_file", "id": ".drama/reviews/rev-ep45-1.json", "revision": null}`；绝对路径、`..`、反斜杠退出码 1，符号链接解析到目录之外退出码 2。`revision` 为 `null` 或钉住的 `sha256:<hex>`（与文件不符退出码 2）；工具把文件的实际 sha256 写进快照的 `revision` 与 `sha256`，文件不存在时列入 `omitted`。`impact` 不评估这类依赖，报 `unknown`。方法见 [定向修订单独装包](skills/drama-studio/references/workstations/README.md#定向修订单独装包)。
- `.drama/cache/`、`knowledge/cards/`、`.drama/snapshots/` 若是指向项目外的符号链接，退出码 1；知识卡的 `scope.projectId` 必须等于任务的 `project.localId`，否则退出码 2。写入先落临时文件再硬链接到位，中断不会留下半截快照。
- `--dry-run` 执行全部检查（含已存在快照的冲突检查）并打印将装入的项、字数与遗漏，输出 `would_write` 而非 `snapshot_path`，不写文件。`--allow-unverified` 允许装入服务端指纹未核验的缓存，并在快照 `unknowns` 写明 `服务端指纹未核验：<artifactId>@r<修订>`。

`knowledge {validate,search,show} <项目>` 只读管理项目私有知识卡：卡片放在 `knowledge/cards/<cardId>@r<revision>.json`，本地证据放在 `knowledge/sources/<sourceId>/`。validate 逐卡运行契约校验并核对文件名；search 只返回每卡最新有效修订，默认排除退役卡（`--include-retired` 可纳入），按类型、工位、用途、关键词过滤，并标注共享 sourceId 的同源卡（只说明来源重复，不说明可靠）；show 打印卡片与来源位置并核对本地证据文件存在。无效卡、来源缺失或越界时退出码 2；`knowledge/` 不存在时返回空结果与目录提示、退出码 0。详见[知识库目录与命令](skills/drama-studio/references/workstations/README.md#知识库目录与命令)。

`receipt` 把宿主保存的 mali-story MCP 响应记成回执（`.drama/receipts/`），把完整读到的页面（或迁移前候选）正文写入本地缓存（`.drama/cache/`），工具本身不联网、不调用 MCP。页面操作（架构 v1.2，mali-story v0.20.0 源码）以合成夹具演示（`tests/fixtures/mcp-pages-synthetic/`，按源码手写，不是真实响应）：

```sh
python3 -B skills/drama-studio/scripts/drama_tools.py receipt record ../my-drama tests/fixtures/mcp-pages-synthetic/01-create.response.json --operation create_page --request-id pg-create-1 --input tests/fixtures/mcp-pages-synthetic/01-create.input.json
python3 -B skills/drama-studio/scripts/drama_tools.py receipt record ../my-drama tests/fixtures/mcp-pages-synthetic/03-update-conflict.response.json --operation update_page --request-id pg-update-3 --input tests/fixtures/mcp-pages-synthetic/03-update-conflict.input.json
python3 -B skills/drama-studio/scripts/drama_tools.py receipt record ../my-drama tests/fixtures/mcp-pages-synthetic/04-update-unknown.response.json --operation update_page --request-id pg-update-4 --input tests/fixtures/mcp-pages-synthetic/04-update-unknown.input.json
python3 -B skills/drama-studio/scripts/drama_tools.py receipt pending ../my-drama
python3 -B skills/drama-studio/scripts/drama_tools.py receipt record ../my-drama tests/fixtures/mcp-pages-synthetic/06-resend.response.json --operation update_page --request-id pg-update-4.resend-1 --input tests/fixtures/mcp-pages-synthetic/04-update-unknown.input.json --reconciles pg-update-4
python3 -B skills/drama-studio/scripts/drama_tools.py receipt cache ../my-drama tests/fixtures/mcp-pages-synthetic/07-read-r2-chunk-*.response.json --title '第3集 集纲'
python3 -B skills/drama-studio/scripts/drama_tools.py receipt record ../my-drama tests/fixtures/mcp-pages-synthetic/08-label.response.json --operation label_page_revision --request-id pg-label-1 --input tests/fixtures/mcp-pages-synthetic/08-label.input.json
```

- `--operation` 新增 `create_page`、`update_page`、`read_page`、`list_page_revisions`、`label_page_revision`、`restore_page`；回执的 `remote.pageId` 记页面 ID（新页面确认前为 null），`remote.artifactId` 为 null。`label_page_revision` 没有 `request_id` 参数，`--request-id` 只是本地回执名。
- `update_page` 的 409 记 `rejected_conflict`，`notes.conflict` 记服务端 code 与 details（`VERSION_CONFLICT` 的 `currentRevision`、`currentFingerprint`；`IDEMPOTENCY_CONFLICT` 的原 `pageId`、`revision`），`warnings` 写明下一步。`unchanged: true` 与 `replayed: true` 都有警告，说明不是新写入。
- 结果未知时 `receipt pending` 给出对账步骤。mali-story v0.20.0 的 `list_page_revisions` 行不带 requestId，所以分两条路：用 `list_page_revisions` 响应加 `--reconciles <原 requestId>` 记录，工具在 `expected_revision` 之后找正文指纹（输入 `body` 的 sha256）与 producer 都相同的 `update`（`restore` 比 `restoredFromRevision`），找到记 `resolved_host_judged`，`currentRevision` 不超过 `expected_revision` 时拒绝（退出码 2，写入没有落地）；或用原 request_id、原输入原样重发，响应记为 `--request-id <原ID>.resend-1 --reconciles <原ID>`，工具核对输入指纹，记 `resolved_verified`。标签的列表比对直接看该修订的 `label`，记 `resolved_verified`。`create_page` 的 unknown 只能原样重发。
- `receipt cache` 收到 `read_page` 分块时按页面缓存：`.drama/cache/<pageId>@r<revision>.md`，全文 sha256 必须等于服务端 `fingerprint`，manifest 追加 v1 条目（`pageId`、`revision`、`title`、`labels`、`producer`、`sha256`、`serverFingerprint`、`verified`、`operation`、`readAt`）。`--title` 是新参数：页面工具不返回标题，不给时取本地 confirmed `create_page` 回执的标题，都没有记 null。页面分块不能和 `--slot`／`--kind`／`--episode-ref` 或候选响应一起给（退出码 1）。已有的 v0 manifest 在第一次写入时改为 v1，原条目不变。
- 版本标签不等于制作采用：标签回执与带标签的缓存都附警告，输出 `adoption_verified: false`。

迁移前的历史候选（story-artifacts）保留只读兼容，命令照旧：

```sh
python3 -B skills/drama-studio/scripts/drama_tools.py receipt record ../my-drama tests/fixtures/mcp-synthetic/02-save.response.json --operation save_story_artifact --request-id d1-save-2 --input tests/fixtures/mcp-synthetic/02-save.input.json
python3 -B skills/drama-studio/scripts/drama_tools.py receipt pending ../my-drama
python3 -B skills/drama-studio/scripts/drama_tools.py receipt cache ../my-drama tests/fixtures/mcp-synthetic/08-read-chunk-*.response.json tests/fixtures/mcp-synthetic/03-get.response.json
python3 -B skills/drama-studio/scripts/drama_tools.py receipt show ../my-drama d1-save-2
```

同一 requestId 输入不同、缓存分块不完整或全文哈希与服务端 `fingerprint` 不符时退出码 2，已有文件不变；响应缺失记 `unknown` 且不允许重试。回执和缓存都不是采用证据。方法见 [候选保存与对账](skills/drama-studio/references/mali-story.md#候选保存与对账)。

`import-project` 把旧本地项目里的稿件整理成 mali-story 候选的保存请求。工具不联网、不调用 MCP；远端现状由宿主事先取回存成文件。**安装不等于授权**：对真实项目执行保存，需要主创逐项确认计划后才可进行。

```sh
python3 -B skills/drama-studio/scripts/drama_tools.py import-project preview ../my-drama --listing list-page1.json
python3 -B skills/drama-studio/scripts/drama_tools.py import-project apply ../my-drama --listing list-page1.json --out ../import-requests --producer external_ai --input-snapshot-id sha256:<get_writing_context 的 snapshotId>
```

完整流程：

1. 宿主用 MCP `list_story_artifacts(project_id)` 列出该项目全部候选，**不带 kind／slot 过滤**，响应原样存成文件；有 `nextCursorId` 时用 `cursor_id` 继续列，每页一个文件，都用 `--listing` 传入（只有最后一页的 `nextCursorId` 为 null，否则退出码 1）。
2. `preview`：只读，不写任何文件。输出 JSON 计划：`create`（将创建的项，含来源文件、slot、kind、episodeRef、正文 `bodySha256`、字数）、`conflicts`（远端同 slot 已有修订，带最高远端修订号 `remoteRevision`）、`skipped`（跳过的文件与原因）。
3. 主创确认计划。冲突项先读远端稿，由主创决定怎么处理；工具不为它们生成请求。
4. `apply`：为每个 `create` 项在 `--out` 写一个 `<request_id>.json`，内容就是 `save_story_artifact` 的参数（`project_id`、`slot`、`kind`、`episode_ref`（分集类）、`expected_revision`、`body`、`producer`、`input_snapshot_id`、`request_id`），项目目录里其他地方不写。`project_id` 取 `.drama/project.json` 的 `remoteProjectId`，没有就退出码 1，不猜。`expected_revision` 恒为 0，因为只有远端没有的 slot 才会生成请求。`--producer`（`codex`／`human`／`external_ai`，规则见 [候选保存与对账](skills/drama-studio/references/mali-story.md#候选保存与对账)）与 `--input-snapshot-id`（先 `get_writing_context` 读到的 `snapshotId`）必须显式给出。`request_id` 为 `import-<slot>-<16 位哈希>`，哈希取除 `request_id` 外整份输入（含正文）的规范 JSON 的 sha256，同样输入重跑得到同一 ID 和逐字节相同的文件；已存在且相同的文件记 `existing: true`，内容不同则退出码 2，什么都不写。`--out` 不能是项目根目录、`.drama/` 或稿件目录本身。
5. 宿主逐条把请求文件的内容传给 MCP `save_story_artifact`，响应原样存成文件；保存前列举到保存之间若有人写了同一 slot，服务端会以 409 拒绝，按 [候选保存与对账](skills/drama-studio/references/mali-story.md#候选保存与对账) 处理。
6. 记录回执：`receipt record <项目> <响应> --operation save_story_artifact --request-id <request_id> --input <请求文件>`；再按逐字保真要求 `read_story_artifact` 读回全文，`receipt cache` 缓存并核对服务端 `fingerprint` 等于计划里的 `bodySha256`。

映射规则（只按文件名判断，拿不准的一律跳过并写明原因）：

| 本地文件 | kind | slot | episode_ref |
| --- | --- | --- | --- |
| `episodes/<N>.md`、`<N>-draft.md`、`<N>正文.md` | `episode_draft` | `ep-NN-draft` | `ep-NN` |
| `planning/<N>-outline.md`、`<N>集纲.md` | `episode_outline` | `ep-NN-outline` | `ep-NN` |
| `reviews/<N>-review.md`、`<N>评审.md` | `review` | `ep-NN-review` | `ep-NN` |
| `planning/characters.md`、`人物.md`、`人物小传.md` | `characters` | `characters` | null |
| `planning/series-outline.md`、`大纲.md`、`全剧大纲.md` | `series_outline` | `series-outline` | null |
| `research/positioning.md` | `research` | `positioning` | null |

- 集号 `<N>` 可写成 `ep03`、`ep-003`、`第3集` 或 `3`，统一成至少两位的 `ep-03`（与上面 mali-story 说明的示例一致）。
- 跳过：版本后缀或多集合并（如 `characters-v1.md`、`01-10-v1.md`）、稿件目录的子目录（如 `planning/experiments/`）、`reference/`（对标资料）、`deliveries/`（交付汇编）、项目根目录文件（如 `PROJECT.md`）、其他目录、符号链接、非 Markdown、空文件、非 UTF-8、超过 500000 字的文件；多个文件映射到同一 slot 时全部跳过。隐藏目录（`.drama/` 等）不扫描。
- 判断冲突时，远端形如 `ep-<数字>` 或 `ep-<数字>-<后缀>` 的 slot 按集号整数比较：远端 `ep-003-draft` 与本地 `ep-03-draft` 视为同一 slot，判为冲突，冲突项的 `remoteSlots` 带远端原始 slot 名。生成的 slot 仍是两位补零。
- 正文按文件原始字节解码，不改换行或标点，`bodySha256` 是文件字节的 sha256。

计划和请求文件都不是保存结果，更不是采用；输出带 `remote_verified: false`、`adoption_verified: false`。

`status` 与 `impact` 只读项目的 `.drama/`（回执、缓存 manifest、快照、运行记录；`impact` 另读 `knowledge/cards/` 判定知识卡），用于换会话或前文修订后恢复现场；不读聊天记录、不联网、不写任何文件（不建目录，不留锁文件）：

```sh
python3 -B skills/drama-studio/scripts/drama_tools.py status ../my-drama
python3 -B skills/drama-studio/scripts/drama_tools.py status ../my-drama --json
python3 -B skills/drama-studio/scripts/drama_tools.py impact ../my-drama --slot ep-03-outline --revision 2
python3 -B skills/drama-studio/scripts/drama_tools.py impact ../my-drama --artifact c41d2b7a-8e5f-4a3b-b6d9-0f1e2a3b4c5d
python3 -B skills/drama-studio/scripts/drama_tools.py impact ../my-drama --card kc-apology-cost
python3 -B skills/drama-studio/scripts/drama_tools.py impact ../my-drama --page 5b0d6c1e-8f3a-4e2b-9c47-1a2b3c4d5e6f --revision 2
```

- `impact --page <pageId> --revision <n>`（架构 v1.2）：页面的 pageId 跨修订不变，不经 manifest 解析。只列出 `items` 中（含经 `context_snapshot` 嵌套）引用了这个页面的快照与依赖它们的运行：引用的修订低于 n 为 `stale`，不低于 n 为 `current`，修订不是不小于 1 的整数为 `unknown`；快照或运行记录损坏、缺失而无法确认时也列出，标 `unknown`。运行的 `outputs` 列出了从所引用修订之后到 n 的每一个修订（`remote_page` 同一 pageId）时，视为它自己的产出，运行标 `current`（只是运行记录的说法，工具不核实）；`planned`／`failed` 的运行不适用。`--page` 必须配 `--revision`，与 `--slot`、`--artifact`、`--card` 互斥，否则退出码 1；没有记录引用该页面时 `warnings` 提示。输出的 `target` 为 `{"page", "revision", "resolvedFrom"}`，`note` 注明版本标签不是制作采用，也不影响判定。按 `--slot`／`--artifact` 判定时，快照里的 `remote_page` 引用报 `unknown`（提示改用 `--page`）。
- `status` 的失效提示也看页面：快照引用的页面修订低于本地缓存 manifest 里该页面的最高修订时为 `newer_revision_cached`，`newerRevisions` 项带 `page` 与 `impact --page=<pageId> --revision <n>` 命令；manifest 里没有该页面的条目时为 `unknown`。页面写入的未知回执排在第一行，文字给出 `list_page_revisions` 与原样重发两条对账路。

- `status` 默认输出中文文本，第一行是下一步动作；`--json` 输出同一内容的 JSON。下一步按固定顺序取：结果未知且未对账的保存回执（沿用 `receipt pending`）→ 无效或损坏的记录 → 最近一次运行的快照引用了旧修订时，先运行给出的 `impact` 命令（该运行原先记录的 `nextAction` 列在第二行，注明是按旧修订的上下文记录的）→ 最近一次运行的 `nextAction` → 没有运行记录时的提示。失效提示沿用 `impact` 的判定规则，只比较本地缓存 manifest：每个列出的运行带 `stalenessCheck`，快照引用的修订低于同一 slot 已缓存的最新可信修订时为 `newer_revision_cached` 并标 `possiblyStale: true`（附 slot、所引用修订、最新可信修订和完整的 `impact` 命令）；引用解析不出可信 slot、缺 revision、manifest 或快照不可读时为 `unknown` 并附原因，不占第一行，也不说它新或旧；更新的修订按上面的规则全部由运行记录声称为自身产出、且证据完整时为 `newer_revision_is_own_output`，不占第一行；证据不完整（包括自身产出之上还有不可信条目声称属于同一 slot）时为 `unknown`；其中有不是它产出的修订时仍是 `newer_revision_cached`，`staleAgainstRevision` 与给出的命令指向不是它产出的最高修订；否则为 `no_newer_revision_cached`，只表示本地缓存里没有更新的可信修订，不说明远端有没有。给出的命令写成 `--slot=<slot>`，slot 以 `-` 开头也能照抄执行。缓存 manifest 损坏或不是 v0／v1 结构时计入无效记录（kind 为 `manifest`），每条无效记录附一句按类型写的处理办法。文本输出把多行的 `nextAction`、`unfinished` 压成一行，JSON 保留原值；slot 含换行类字符时文本里转义显示且不打印命令，完整命令在 `--json` 的 `impactCommand` 里。它同时列出所有未结束（`planned`／`running`／`interrupted`）或 `unfinished` 非空的运行，以及每个快照的完整性：契约校验、文件名与 `snapshotId` 是否一致、`.sha256` 旁车与文件字节是否一致、`completeness`。“最近”优先按运行记录的可选字段 `finishedAt`（ISO 8601，带时区）判定（输出 `recencyBasis: finishedAt`）；没有该字段的旧记录按文件修改时间判定（输出 `recencyBasis: file_mtime`），复制或检出后可能不准；两种记录混在一起时按各自的时间比较，`note` 写明混比可能不准。每个运行另带自己的 `recencyBasis` 与 `finishedAt`（没有则为 null）。只读调用的未知结果（`read_only_unknown`、`unreconcilable_unknown`）会列出，但不排在第一行。
- `impact` 输出 JSON，把每个快照和运行标为 `stale`、`unknown` 或 `current`。mali-story 每个修订的 artifactId 都不同，新旧一律按 slot 判断：快照 `items` 中引用了目标 slot 较旧修订的为 `stale`，依赖该快照的运行（`contextSnapshotId`）随之为 `stale`，并写明是哪条引用。例外是运行记录声称自己产出了这些修订的运行，这条例外只在证据完整、可信、无歧义时成立。同一 slot 的修订号每保存一次加 1，所以从快照所引用的修订 P 到目标修订 T，中间每一个修订号（P+1 到 T）都必须是 manifest 里可信的缓存条目，并且都列在这次运行的 `outputs` 里；其中任何一个修订号不能同时有两个可信的 artifactId；manifest 里也不能有不可信或互相冲突的条目声称属于这个 slot，除非它的修订号确定不高于 P。全部满足时，快照对旧修订的引用不使这次运行失效，运行标 `current` 并写明“运行记录声称产出了…”，快照本身仍是 `stale`。运行记录可用可选字段 `additionalSnapshotIds` 登记它还读过的快照（如 C6 首读、次读两个包）：`impact` 对 `contextSnapshotId` 与其中每个快照分别判定，任一为 `stale` 运行即为 `stale`，找不到的为 `unknown`；`status` 的失效提示同样覆盖这些快照，引用前缀写明来自哪个快照。不满足时分两种：P+1 到 T 之间有可信的修订不是它产出的（例如从 r1 直接产出 r3，而缓存里另有别人的 r2），照常标 `stale`；其余情况（中间有修订号没缓存、有宿主声明或冲突的条目、同一修订号有两个可信产物）标 `unknown`，原因里写明是哪个修订或哪条条目。`outputs` 是运行记录自己的说法，工具不核实；状态为 `planned` 或 `failed` 的运行不适用这条例外，在这段修订里没有自身产出的运行按没有这条例外处理，其他 slot 的旧引用照常计入。快照里的 `context_snapshot` 引用继承被引用快照的结论（找不到、损坏或成环为 `unknown`）；任务文件（`task` 分区里的 `local_file`，即 `context-pack` 写入的那一项）不算依赖；知识卡（`knowledge_card` 引用）不算 slot 依赖，按本地 `knowledge/cards/<cardId>@r<rev>.json` 单独判定：该卡最新的有效修订（与 `knowledge search` 的取法相同）`processing` 为 `retired` 时为 `stale`，原因写“卡 X 已退役”，快照引用的就是这个修订也一样；有比快照所引用的更高的有效修订时为 `stale`，原因写“卡 X 已有 rN”；本地找不到该卡、快照引用的修订在本地不存在或未通过校验、或比它高的修订文件未通过校验时为 `unknown`；其余为 `current`。依赖这些快照的运行照上面的规则随之变化，运行记录声称的自身产出不覆盖知识卡。`status` 的失效提示目前不看知识卡。嵌套超过 50 层不再展开，按 `unknown` 处理；其余引用类型（其他 `local_file`、`remote_snapshot`、`remote_brief`、`remote_receipt`）一律 `unknown`，原因写“该引用类型的依赖未评估”。输出的 `target` 带 `slotInManifest`（manifest 里有没有任何条目属于目标 slot）和 `newestTrustedRevision`（该 slot 已缓存的最新可信修订，没有则为 null）；目标 slot 在 manifest 里从未出现时 `warnings` 提示可能是拼写错误，此时全部 `current` 只覆盖记录在案的引用。目标修订低于该 slot 已缓存的最新可信修订时也有一条 `warnings`，提示结论只针对所给的修订。小于 1 的修订号无效，带这种修订的条目或引用一律 `unknown`。`--artifact` 经 manifest 解析出 slot 与 revision，与 `--slot`／`--revision` 互斥。`--card <cardId>` 是第三种互斥的目标：与 `--slot`／`--revision`、`--artifact` 同时给出时退出码 1；它不读缓存 manifest，只列出 `items` 中（含经 `context_snapshot` 引用嵌套）装入了这张卡的快照，以及依赖这些快照的运行，并且只按这张卡判定 `stale`／`current`（规则同上），不看 slot 修订与其他引用；快照或运行记录损坏、缺失、成环而无法确认是否装入了这张卡时也列出，标 `unknown`。输出的 `target` 为 `{"card", "resolvedFrom", "cardInStore", "latestRevision", "retired"}`；本地找不到该卡，或没有任何记录引用它时，`warnings` 各有一条提示。
- 不确定一律标 `unknown`，附原因和“扩大阅读”建议：artifactId 不在 manifest、slot 只是宿主声明、同一 artifactId 最强来源的条目互相矛盾或修订号不一致、引用缺 revision 或与 manifest 不一致、快照损坏、运行找不到所依赖的快照。`current` 只表示没有记录在案的执行依赖指向该 slot 的旧修订；内容层面的隐含依赖未评估。工具不自动重跑，也不改写正文。
- slot 的可信度记在 manifest 条目的可选字段 `slotSource`：`receipt cache` 带 `get_story_artifact` 响应时为 `record`；只给分块、但本地有该 artifactId 的 confirmed 保存回执且 slot 一致时为 `receipt`（与 `--slot` 不一致则拒绝写入，退出码 2）；经对账确认的重发回执（`localRef.kind` 为 `remote_receipt`，`notes` 记有 `slotCheck` 且 `observedRequestId` 等于原 requestId，原 unknown 回执同项目、同输入指纹）也算，slot 取原回执的 slot；否则为 `host`。`receipt record` 遇到 confirmed 的保存响应且响应里带 `record.slot` 时，会把它与 `--input` 的 slot 比对：不一致即拒绝写回执（退出码 1），一致则在回执 `notes` 里记 `slotCheck`。只有带这条记录的回执才能让缓存条目记为 `receipt`；响应不带 slot 的回执、以及这项检查加入之前写的回执，slot 仍只是输入文件的说法，不算数。工具不联网，这项比对只说明两份保存下来的文件互相一致。`host` 或没有该字段的条目在 `impact` 中按 `unknown` 处理；用 get 响应重新缓存会追加一条 `record` 条目，manifest 只追加，旧条目不改不删。同一产物修订（同一 artifactId 与 revision）有多条条目时以最强来源为准：`record` > `receipt` > `host`，没有 `slotSource` 或取值不在这三者内的按 `host` 算；`receipt cache` 拿这次调用的 `slot`、`kind`、`episodeRef` 三项与来源最强的条目比较；`context-pack`、`impact`、`status` 只从来源最强的条目读 `slot`，不看 kind 与 episodeRef。所以宿主声明的 slot（或 kind、episodeRef）写错了，带 get 响应重新缓存即可纠正：这次调用的来源强于该产物修订已有的全部条目时，工具追加一条纠正条目，并在 `warnings` 里写明改了哪一项；此前已核验的全文照旧算已核验。写错的旧条目留在原处；该产物的 slot 与修订能由更强来源唯一确定时，它不再算作它所写 slot 的条目（条目互相矛盾或修订号不一致时，每条条目所写的 slot 照旧算数，疑点不会因此消失），`context-pack` 的“同一 slot 不能混两个修订”也按纠正后的 slot 判断（纠正之前装好的快照是按旧值检查的）。来源相同或更弱而取值不同的调用被拒绝、不写入（退出码 2），错误信息写明已有条目的来源与取值：宿主声明不能纠正 `receipt` 或 `record`，`receipt` 不能纠正 `record`。保存回执只担保 slot：`receipt` 来源的调用带的 kind 与 episodeRef 仍是宿主给的值，所以它只能纠正宿主声明的 slot；它的 kind 或 episodeRef 与已有条目不同时同样被拒绝、不写入（退出码 2），这两项要带 get 响应才能纠正。`record` 可以纠正 `host` 与 `receipt` 条目的全部三项；它纠正的是 `receipt` 条目的 slot 时，`warnings` 另有一条，写明两份保存下来的服务端响应互相矛盾和该保存回执的 requestId。`impact` 的目标 slot 只被已纠正的条目写过时，`slotInManifest` 为 false，`warnings` 写明那条条目被哪种来源纠正到了哪个 slot，不提示拼写错误。只有最强来源的条目之间互相矛盾才算冲突（`receipt cache` 自己不会写出这种条目）：此时来源相同或更弱的 `receipt cache` 调用被拒绝（来源更强的调用照常纠正），`context-pack` 报条目冲突，`impact` 把对该产物的引用标为 `unknown`。修订号不在纠正之列，同一 artifactId 的条目修订号不一致仍按冲突处理。
- 退出码 0 表示分析完成，结论读输出里的状态；退出码 1 是输入或执行错误，例如项目没有 `.drama/`、`impact` 的目标参数不成组或 `--card` 与其他目标同时给出、`--revision` 不是不小于 1 的整数、`--slot` 为空、`--artifact` 解析不出可信的 slot。两个命令的 JSON 输出都带 `read_only: true`、`remote_verified: false`，不证明远端状态或采用。合成夹具上的完整命令链、输出与前后 sha256 见 [恢复与失效演示记录](docs/d2/recovery-demo.md)；它不是真实创作产物上的验证。

`season-check` 在每批结束和交付前逐集核对整季流程的证据，只读 `.drama/`（运行、快照、审读、回执）和 `project.json`，不读正文含义、不联网：

```sh
python3 -B skills/drama-studio/scripts/drama_tools.py season-check ../my-drama --episodes 31-80
python3 -B skills/drama-studio/scripts/drama_tools.py season-check ../my-drama --episodes 31-40 --batch-size 10 --allow-offline
python3 -B skills/drama-studio/scripts/drama_tools.py season-check ../my-drama --outline 11-60 --outline-batch 15
```

- 逐集查：有 C1、C2、C3 的交接（早于第一个作者运行），有覆盖本集的 C4 交接；本集的第一个 C5 运行只写这一集，快照是 `author` 包，装了本集集纲、前一集当时的最新稿和入口状态记录 `runs/state/after-ep-<前一集三位数>.md`；前一集有状态变化提案时，入口状态记录必须与上一集用的不同；有封存（`.sha256` 与字节一致）且 `firstReadWithoutAuthorNotes: true` 的首读和另一份次读，一次首读不超过 `--batch-size` 集；有装了本集正文的 `reader_effect` 首读包；最终稿有 confirmed 保存回执。另查快照封存、各记录的契约，以及几次运行的用量完全相同（抄的，不是实测）。
- 集号从文件名（`ep-031`、`outline-031`、`第31集`）或页面写入回执里的 `episodeRef`、`semantic` 认出；`current_plan` 分区的是集纲，其余是正文。范围第一集缺前一集正文只记警告。
- `--outline <起-止>` 查集纲（可与 `--episodes` 同用，至少给一个）：每集集纲有 C4 运行产出；一个 C4 运行不超过 `--outline-batch` 集（默认 15）；集纲包装了此前最近一次 C2、C3 运行的全部产出；一段的第一集装了前一集集纲的最新稿，前一集集纲若由更晚的运行写出则判并行（`outline-sequential`）；此前已有正文时装了 `runs/state/after-ep-<已写到的集>.md`；有 `context` 为 `independent` 或 `human` 的审读记录指向该集集纲；集纲最终稿有 confirmed 保存回执。文件名含 `outline` 的本地文件一律认作集纲。结果在 `perOutline`、`failedOutlines`。
- 旧的台词三条（0.6.0 起只在加 `--legacy-dialogue` 时查，用来复查没有对话表的旧记录；加了它输出与 0.3.6 逐字节相同，不加时输出记 `legacyDialogueRules: not_run …`；`--skip-dialogue` 在加了 `--legacy-dialogue` 时关掉它们并记 `dialogueChecked: false`）：`voice-card`，最终稿里台词达到 3 句的每个说话人，名字出现在作者包装入的某张 K5 知识卡里；`dialogue-pass`，作者运行之后有一次 `dialogue_author` 运行，包里有 K5 卡，且它前后两稿的集标题和场头行逐行相同（台词、括注和动作行可以改）；`dialogue-read`，台词遍之后有一次装了本集正文的 `dialogue_read` 运行。台词行指“人物：话”（名字不超过 10 个字，可带括注）；稿子从本地文件或 `.drama/cache/<pageId>@r<n>.md` 读，读不到判不通过。方法见 [台词](skills/drama-studio/references/dialogue-structure.md)。脚本不判断台词自不自然。
- `context-pack --role` 有 `dialogue_author`、`dialogue_read`（台词遍、台词读用；0.6.0 起新运行不再做这两步，角色留着读旧记录）；`dialogue_read` 包和 `reader_effect` 一样不能含 `current_plan`。
- `--revise`：对已有全稿做反馈改稿时用。不查“一集一个作者运行”、前一集正文、入口状态与状态更新；C4 只要求第一个作者运行之前有一次 C4 运行（修改单），作者包只要求有 `current_plan` 分区的材料。其余照查。
- `--since <ISO 时间>`：只把这个时间及之后完成的 C4–C6 运行算进来，用于同一项目改过几版；C1–C3 仍在全部历史里找。审读记录没有时间，不受它过滤。
- 首读有多份时，至少一份封存即可，其余未封存的记警告。
- 只有 `not_sent` 回执时判不通过；用户明确同意只交本地草稿、且项目没绑定远端时加 `--allow-offline`，改记警告。
- 退出码 0 为全部通过，2 为有失败（看 `failures`、`failuresByRule`、`failedEpisodes`），1 为输入错误。输出带 `remote_verified: false`：通过只说明记录齐全、彼此一致，不说明正文写得好，也不证明远端已保存。
- 新旧规则并存（0.4.0）：启用了新规则的一侧在输出里写明——集纲侧 `ruleSet: outline-layer`，正文侧 `episodeRuleSet: dialogue-layer`；没启用的一侧不加这个键。没有 `planning/season-plan.json`、也没有对话表记录的项目只跑上面的旧规则，输出与 0.3.6 逐字节相同。新规则读 `planning/`、`.drama/checks/`、`.drama/tasks/` 下的 JSON 记录（任意层级），按 `schemaVersion`／`schema` 标记或 `reproduceCommand` 里的 drama_tools 子命令认出是什么记录，集号取记录自己的 `episode`／`target.episode`、所核文件名或记录文件名。
- 集纲层（项目有 `planning/season-plan.json`）：旧集纲规则照查，另加 `outline-season-assigned`（本集在季编排里）、`outline-ledger-delta`（有本集分集计划，`ledgerDelta` 有 reads／writes，`writes[].supportedBy` 是本集的场或拍）、`outline-capacity`（`capacity.status` 为 `fits`，或 `proposal:<id>` 且决定队列里该条有 `default`）、`outline-reality-refs`（`realityRefs` 都在底账里且不是 `contested`；`unverified` 只计数，记在 `perOutline` 的 `unverifiedRealityRefs`）、`outline-retell`（有 `target.kind: episode_plan_events` 的冷读复述）；全项目查一次 `outline-decision-default`（未定的决定都有 `default`）与 `outline-patch-cap`（功能地图里 `selected` 的候选或未退役的底账条目 `patchCount` 到 3 及以上，即到 2 之后又原地修订；被否的旧候选的计数是历史，不查）。
- 台词层（项目有对话表记录）：不再查 `voice-card`、`dialogue-pass`、`dialogue-read`，改查 `dialogue-plan`（有本集对话表且过 `contract-check`）、`target-ref`（对话表 `basedOn.target` 引用项目里的台词目标）、`plan-text-align`、`cold-retell`（`target.kind: episode_text` 的复述）、`situation-check`（对话问题单的回答记录）、`consistency-record`（两份以上处境核对时要有 `answers-consistency` 记录）、`retell-after-revise`（冷读运行之后又有 C5 运行时，最后一次 C5 之后要再有冷读运行）、`constraint-origin`、`no-numeric-dialogue-constraint`（`.drama/tasks/` 里本集作者运行的任务约束；找不到任务记录只记警告）、`fixlist-no-lines`（修订单不写“人物：台词”格式的行）、`dup-two-tier`（8 字与 13 字两档 `dup-check --list-hits` 记录）、`genre-lexicon`（`corpus lexicon` 记录）。

### 集纲层与台词层的只读工具（0.4.0）

这些命令都只读本地文件、不联网、不调模型，输出 JSON 并带可直接运行的 `reproduceCommand`（drama_tools 子命令形式，文件参数为绝对路径）；`--help` 看参数。退出码同上：0 完成（含只报不拦的报告与容量提案），1 输入错误，2 显式规则不满足。对象的 Schema 与合成示例在 `skills/drama-studio/schemas/`，问题单、禁词表、题材词表在 `schemas/data/`。

```sh
T=skills/drama-studio/scripts/drama_tools.py
python3 -B $T ledger check planning/ledger/ledger-ep000.json            # 底账规则；另有 init/merge/apply/replay/diff/knows/view/stats
python3 -B $T ledger replay planning/ledger/ledger-ep000.json --delta d5.json --delta d6.json --at 6
python3 -B $T function-map check planning/function-map.json --records .drama/checks/*.json
python3 -B $T function-map topics planning/function-map.json           # 检索题目归并，只归并不检索
python3 -B $T defects build --records .drama/checks/*.json    # 缺口登记表由回答记录生成
python3 -B $T check-answers .drama/checks/RC-1.json --cross
python3 -B $T season-plan-check planning/season-plan.json --function-map planning/function-map.json --media planning/media-profile.json
python3 -B $T plan-check planning/episodes/episode-plan-006.json --ledger planning/ledger/ledger-ep005.json
python3 -B $T capacity episode planning/episodes/episode-plan-006.json --media planning/media-profile.json --corpus corpus/exchanges.jsonl
python3 -B $T capacity text episodes/ep-006.md --media planning/media-profile.json
python3 -B $T decision check planning/decisions.json                     # 另有 add/list/decide
python3 -B $T retell-check .drama/checks/retell-plan-006.json --plan planning/episodes/episode-plan-006.json
python3 -B $T dialogue-plan-check planning/dialogue-plans/ep-006.json --episode-plan planning/episodes/episode-plan-006.json --knows knows-ep006.json
python3 -B $T plan-text-consistency plan-text-map-006.json --dialogue-plan planning/dialogue-plans/ep-006.json --episode-plan planning/episodes/episode-plan-006.json
python3 -B $T dialogue-diagnose episodes/ep-006.md --plan-text-map plan-text-map-006.json
python3 -B $T answers-consistency .drama/checks/check-006-a.json .drama/checks/check-006-b.json
python3 -B $T feedback-ingest feedback/comments.json
python3 -B $T corpus segment raw/*.md                                   # 另有 label/filter/lexicon/rate；fetch 在 D6-4
python3 -B $T dup-check --list-hits --k 8 --new episodes/ep-006.md --source-dialogue-plan planning/dialogue-plans/ep-006.json
python3 -B $T episode-check episodes/ep-006.md --speech                 # 口播汉字数，不估时
python3 -B $T contract-check function-map planning/function-map.json --records .drama/checks/*.json
python3 -B $T contract-check answers .drama/checks/RC-1.json --cards knowledge/cards
```

- `contract-check` 的跨文件规则要给上下文才核，没给时在 `notEvaluated` 里写明：`--records`（功能地图选定候选引用的回答记录里不能有没有去处的承重缺口）、`--defects`（回答记录或缺口登记表，供底账戏剧假定条目查缺口类型）、`--cards`（知识卡文件或目录，空卡不能当 `holds` 的出处）、`--questions`（项目问题单）、`--base-questions`（项目问题单只能增问不能删问）。
- `capacity` 超出时写决定队列的提案占位，退出码仍是 0；所有输出没有 within／outside 一类的区间判定字段。
- `context-pack --role` 新增 `function_mapper`、`ledger_keeper`、`season_planner`、`dialogue_designer`（C5a）、`situation_checker`、`cold_reader`。`cold_reader` 包只能有一项 `project_facts`（本集正文或本集分集计划的 events），不能有 `current_plan` 与知识卡；`dialogue_designer` 包要装本集分集计划，其 `capacity.status` 为 `fits`，或 `proposal:<id>` 且该提案（装入的或 `planning/` 下的决定队列）有 `default`；任务 `layer` 为 `C5b` 时包里要有通过 `contract-check dialogue-plan` 的对话表。违反都是退出码 2。
- `context-pack --exemplars <exchanges.jsonl> --contrast-pairs <contrast-pairs.jsonl>`（只用于 C5a 与 C5b，文件须在项目的 `.drama/`、`runs/` 或 `knowledge/` 里）：按装入的对话表各话题引用的样本装包，每话题至多 2 个语料正例和 1 个对照对；先装各话题第一个正例，再装对照对，再装第二个正例，装到预算为止，装不下的整条记入 `omitted`（`reason: budget`），从不截断单条。样本以 `local_file` 加字符区间进 `current_plan` 分区；输出 `samples` 记装了几条、因预算留下几条、对话表引用了却在文件里找不到的样本。

### 切换集纲层（0.5.0）

新项目默认走 C3a 功能地图 → C3b 底账 → C3c 季编排 → C4 分集计划，记录都是本地 JSON，按下面的目录放（[D6-2 决定 §1](docs/d6/d6-2-decisions.md)）：`planning/function-map.json`、`planning/ledger/ledger-ep000.json` 与 `delta-ep<NNN>.planned.json`／`.actual.json`、`planning/season-plan.json`、`planning/episodes/episode-plan-<NNN>.json`、`planning/decisions.json`；回答记录、冷读复述与命令输出放 `.drama/checks/`。集号三位数字，拆集写 `006A`。

```sh
T=skills/drama-studio/scripts/drama_tools.py
python3 -B $T init-project ../my-drama --title '我的新剧'      # 另建空的 planning/ledger/、planning/episodes/
python3 -B $T context-pack ../my-drama --task c4-task.json --selection c4-selection.json --role author --budget 200000
python3 -B $T season-check ../my-drama --outline 1-10
python3 -B $T contract-check task c4-task.json
```

- `init-project` 多建 `planning/ledger/` 与 `planning/episodes/` 两个空目录；`status` 不看它们，旧项目没有也不报错。
- `context-pack` 的 `local_file` 可以取 `planning/` 下的文件（同样拒绝绝对路径、`..` 与指向目录外的符号链接）。
- `context-pack --role author` 给 C4 装包（任务 `workstation` 或 `layer` 为 `C4`）时，如果项目已经开始用集纲层，包里必须有季编排（`season-plan` 记录）和底账（`ledger-entry` 记录：`ledger-ep000` 或 `ledger replay --out` 写出的修订），缺一项退出码 2，对应 `season-check` 的 `outline-season-assigned` 与 `outline-ledger-delta`。「已经开始用集纲层」指有 `planning/season-plan.json` 或 `planning/function-map.json`，或者 `planning/ledger/`、`planning/episodes/` 下有 JSON 记录；`init-project` 刚建的空目录不算。0.3.6 时代的项目一项都没有，C4 包的行为不变。
- `contract-check task` 逐条扫描 `constraints[].text`，命中 `schemas/data/constraint-blocklist.json`（v3）的任一类就拒绝，不论 `origin`，退出码 2。一类是「不动集数／标题／★、只改一次、不拆集」：v2 起也认「不要改集数」「别动标题」「禁止改★」「只能修改一次」「不要拆成两集」这类说法。另一类是数值型台词约束：带数字的（「少40字」「删两句」「台词压到五行」「每句不超过十个字」），把度量当目标的（「控制字数」「压缩台词量」「精简句数」），以及「换人数」「换人次数」。v3 起「字数」「行数」「句数」「台词量」不再按裸词拦，「字数统计仅供参考」「行数按正文实际统计」放行。说集数与拆集由季编排决定的约束不受影响。
- `season-check --outline`：有 `planning/season-plan.json` 的项目跑集纲层七条（0.4.0 已实现），旧的工位交接规则照旧；没有季编排的项目输出与 0.3.6 逐字节相同。七条只看季编排，因为它们按季编排的分配核每一集，C3c 之前没法跑。旧规则（`outline-run`、`outline-review`、`outline-saved` 等）在已经开始用集纲层的项目里（判据同上，与 `context-pack` 共用一个函数）也认 `planning/` 下带 `episode-plan` 标记的 JSON 分集计划：C4 运行产出它、审读记录以它为对象、回执保存它，都算本集集纲。旧项目没有这类记录，结果不变。
- `plan-check --characters <人物包>`：小传里的前史事件有没有时间线账条目，只报不拦（`rules.characters-prehistory`，不影响 `passed` 与退出码）。人物包两种最小格式：JSON `{"characters": [{"name", "prehistory": [{"text", "ledgerRef", "pending"}]}]}`；Markdown 里标题含「前史」的一节，每个列表项或段落行算一件事，`L-…` 是底账 id，写「待定」的标为待定。列出没有底账 id 的事件（待定的作提示）、入口底账里没有的 id、不是时间线条目的 id。
- `ledger replay --delta <目录>`：目录代表其中的 `delta-*.json`，按集序重放（与逐个给文件结果相同）；目录里没有 delta 时退出码 1。`--md` 导出时，实际轨借用计划轨的集（`plannedFallback`）和应用错误写在开头的「重放说明」一节；有错误时另把错误以 JSON 打到 stderr，退出码 2。
- `task` 新增可选字段 `target`（`kind`：`episode_text`、`episode_plan`、`function_map`、`ledger`、`season_plan`；可带 `episode`）。`layer: C6` 的任务审的是集纲侧（`target.kind` 为后四者之一）时不要求 `dialogueTarget`；审正文或没写 `target` 的 C6 任务照旧要求。
- `contract-check review-record`：审读对象（`target` 或 `additionalTargets`）是 `planning/episodes/` 下的分集计划时，每条不是 `kind: preference` 的 finding 都要有 `cites`，否则退出码 2。审读其他对象的记录照旧。
- 走通演示之后（[D6-2 决定 §5](docs/d6/d6-2-decisions.md)）：
  - `plan-events <分集计划> --out .drama/checks/events-ep<NNN>.json`：新命令，只导出 events（每拍留 beatId、who、text、quote、offscreen，去掉 saysFact、picture 等设计字段）。`context-pack --role cold_reader` 只收这份导出，整份分集计划退出码 2。
  - `capacity` 不给 `--media` 用随包 `schemas/data/default-media-profile.json`，不给 `--corpus`／`--exchange-median-sec` 用其中的交换中位时长（真人剧 10.8 秒，D6-0 语料 138 条；漫剧没量过，要自己给）；输出 `basis.status: default_unmeasured`，退出码 0。
  - `ledger view <功能地图> --blank-period`：C3a 阶段底账还没写时，按线列各候选的 ledgerDeps（procedure 除外）；状态子型条目按 `stateOf` 归人。
  - `ledger check` 的 `schema-basic` 与 `contract-check ledger-entry` 用同一套必填（读 schema）；`whyNotApplicable` 可以代替 `why`；`money-closed` 里列进 `emptyFields` 的空字段算已交代，列在 `registeredEmpty`。
  - `check-answers --records` 收目录（目录里只读回答记录，其余文件跳过并列在 `recordsSkipped`）；回填的 `confirmed_gone` 要写 `backfilledBy`、不能引用本记录，被引用的复核记录对同一 `defectKey` 不能仍判 `notHolds`；只有不承重的 `notHolds` 时 `outcome` 也可以写 `pass_with_unverified`；`target.ids` 列了两个以上对象时，每答要写 `subject`。
  - `function-map check --stage v1`：每条 `mapErrata` 要有另一份记录的 `errataConfirmed`（`{ref: "<checkId>#<序号>", fixed: true}`）确认已改，被取代的记录不要求（`skippedSuperseded`）；只做勘误复核的记录写 `target.kind: errata_check`，可以不答题；`function-map topics` 只出能检索的题（procedure，以及 money／object 的 required_unstated）。
  - `context-pack`：`fact_check` 包可以装 `comparison_only` 的卡；随包问题单按 id 装（`{"kind": "local_file", "id": "question-set:reality-check-questions@v1"}`）；C4 作者包的清单是季编排、底账、功能地图，`season-check` 的 `outline-structure` 对写 episode-plan 记录的 C4 运行按同一张清单核。
  - `run-handoff`：C1、C2 可以 `contextSnapshotId: null`，同时写 `noSnapshotReason`。`init-project` 另建 `runs/`、`knowledge/`。
  - `season-check` 在 `ruleSet: outline-layer` 下输出 `outlineLayerRules`（每条集纲层规则 passed／failed／not_evaluated 与核过的范围）；`plan-check` 的 `speaker-knows` 有 `notEvaluable` 时写 `pass_with_not_evaluable`；`status` 把已结束、留有未完成项的运行与未结束的分开。

### 切换台词层（0.6.0）

正文默认走 C5a 对话表 → C5b 照表写正文 → C6 五读（首读、次读、冷读复述、处境对照、设计依据一致性）→ 先改表再改文；台词遍、台词读不再是步骤（[D6-3 决定](docs/d6/d6-3-decisions.md)）。产物位置：对话表 `planning/dialogue/dialogue-plan-<NNN>.json`，台词目标 `planning/dialogue-target.json`，复述、处境对照、对照表核对与修订单放 `.drama/checks/`，装包历史 `.drama/packs/history.json`。

```sh
T=skills/drama-studio/scripts/drama_tools.py
python3 -B $T season-check ../my-drama --episodes 1-10                      # 有对话表时核台词层规则，列在 dialogueLayerRules
python3 -B $T season-check ../my-drama --episodes 1-10 --legacy-dialogue    # 复查旧记录：另跑声音卡、台词遍、台词读三条
python3 -B $T context-pack ../my-drama --task c5a.json --selection sel.json --role dialogue_designer --budget 60000 --exemplars runs/samples/masked-ep006.jsonl --quotes-per-topic 2
python3 -B $T contract-check revision-list .drama/checks/revision-list-ep006.json
python3 -B $T contract-check plan-text-map runs/b6/plan-text-map-006.json
```

- 「启用了台词层」按记录判：`planning/` 或 `.drama/` 下任意深度有带 `dialogue-plan` 标记的 JSON（`.drama/cache`、`.drama/snapshots` 不算），与集纲层的判据并列。没有对话表的旧项目不带 `--legacy-dialogue` 时，旧三条不出现，也没有新失败。
- `season-check --episodes` 的台词层规则：`dialogue-plan`、`target-ref`、`plan-text-align`、`cold-retell`、`situation-check`、`consistency-record`、`retell-after-revise`、`constraint-origin`、`no-numeric-dialogue-constraint`、`fixlist-no-lines`、`dup-two-tier`、`genre-lexicon`、`preserved-human-source`，每条的 passed／failed／not_evaluated 与核过的集列在 `dialogueLayerRules`。没有 C5 运行交接的集也按记录核这些规则（按运行判的几条记 not_evaluated）。
  - `retell-after-revise`：有冷读运行时按运行先后判；只有记录时，正文改过（C5 运行不止一个）而正文复述的 `target.file` 不是最终稿，判失败。
  - `preserved-human-source`：审读记录的 `preserved` 每项要写成 `{item, noteId}` 或 `{item, humanWords}`（人要求保留的东西）；纯字符串是 0.6.0 之前的写法，旧项目照旧能过 `contract-check`，台词层项目判失败。
- `context-pack`：C5b 作者包（任务 `layer: C5b`）里的对话表要过 `contract-check dialogue-plan`，C5a 包的分集计划 `capacity.status` 要是 `fits` 或带默认的提案，否则退出码 2。样本进单独的 `samples` 分区，只收遮蔽后的样本记录（处境、说明、骨架、`maskedLines`），带原始 `lines` 的转写行或没有 `maskedLines` 的行是输入错误（退出码 1）；`--exemplars` 可以给这种记录的 JSONL，也可以直接给对话表（读其中 `exemplars.positives` 的遮蔽样本记录）；`--quotes-per-topic` 设一个话题所有样本的 `maskedLines` 合计最多几句（默认 2，可设 0），会超出的样本整条不装，列进 `omitted`（`reason: quote_cap`）；写出快照时把装了的样本追加进 `.drama/packs/history.json`，同一条样本上一集的包也装过时列在 `samples.repeatedFromPreviousEpisode`（只报不拦）。
- `contract-check revision-list`（新对象）：修订单每项指问题、引依据，不写替换台词（SPEAKER 格式行）、不下数值指令（`constraint-blocklist` 的数值类），退出码 2；`where`、`cites` 等定位字段不扫，「本轮不改：…」这类说明标签不算台词行。`season-check` 的 `fixlist-no-lines` 用同一个扫描核 `.drama/checks/` 里的修订单。
- 走通演示之后（[D6-3 决定 §6](docs/d6/d6-3-decisions.md)）：台词目标 `corpusManifest` 可为 `null`（须写 `noCorpusReason`），这时 `dup-two-tier` 的 13 字全库档记 not_evaluable，8 字档只在对话表引用了语料正例时才要；`mediaProfile` 可为 `null`（用随包默认档案）；`ledger knows` 把图谋账算作其主人知道；`consistency-record` 只在同一稿有两份处境对照时才要；修订单扫描在 `season-check` 里按本集人物名单认台词行；题材禁词表按 `lexicon:genre-lexicon@v1` 进包；`review-record` 的 `layer` 有 `C5a`、`C5b`，首读封存可写进记录的 `sealedSha256`，台词层项目的首读、次读只认审读对象是正文的记录；对话表交换上的 `interruptedAt` 由 `plan-text-consistency` 核；处境对照一答可同时有 `landsOn` 与 `quoteRef`，`n/a` 不必引句；冷读复述每条可带 `sourceLine`、`sourceKind`；对照表 `lineToPlan[].kind` 限定六种；`episode-check` 认「次日晚」这类场头时间词；`run-handoff` 可带 `decisionRefs[]`（`contract-check run-handoff --decisions` 核引用存在）；无语料时 `dialogueLayerRules` 的 `dup-two-tier` 另写 `notEvaluatedTiers`；`interrupted-by` 按被打断交换上的 `interruptedAt` 与话题 `interruptedBy.by` 核，被打断的人不必说完；`capacity text` 输出 `targetSec` 与 `targetSecSource`（`--target-sec` ＞ `--episode-plan` 的 `capacity.targetSec` ＞ 媒介档案，不给 `--media` 时是随包默认档案）。
- `contract-check plan-text-map`（新对象）：C5b 的对照表（`exchangeToLines`、`lineToPlan` 的 `closerOf`／`carries`／`verbatimFrom`，`plan-text-consistency` 的输入）；核 `exchangeToLines` 指到的行在 `lineToPlan` 里标了同一个交换、逐字采用的行在 `verbatimFrom` 汇总里有出处。

### 语料库与反馈回流（0.7.0）

依据：[D6-4 决定](docs/d6/d6-4-decisions.md)。本阶段没有 mali-story 连接，不做远端取用，以现有小样本（3 部、40 集、138 条交换）结束；全库取用、补语料、计费确认是待办（[语料记录](docs/d6/d6-4-corpus.md)）。

```sh
T=skills/drama-studio/scripts/drama_tools.py
python3 -B $T corpus fetch plan templates.json --out corpus/fetch-ledger.json      # 先取 3 部各 10 集
python3 -B $T corpus fetch budget corpus/fetch-ledger.json --label before --reading budget.json --receipts receipts.json
python3 -B $T corpus fetch record corpus/fetch-ledger.json --template <id> --episode 1 --response resp.json
python3 -B $T corpus fetch resume corpus/fetch-ledger.json                          # 断点清单
python3 -B $T corpus fetch verify corpus/fetch-ledger.json                          # 有扣费迹象或快照不符退出 2
python3 -B $T corpus agree corpus/exchanges.jsonl --out corpus/exchanges.agreed.jsonl
python3 -B $T corpus defaults corpus --series-format <id>=anime --out corpus/defaults.json
python3 -B $T feedback-ingest notes.md --out feedback/ep006 --target planning/dialogue-target.json
python3 -B $T feedback-ingest --purge WN-xxxxxxxxxx --out feedback/ep006
```

- `corpus fetch`：取用记账，不联网。`plan` 按模板清单排出前 3 部各 10 集（带期望的 `snapshotId`）；`record` 记一次调用的结果（响应读不出或带 error 记 failed，`snapshotId` 与期望不符记 `snapshot_mismatch`），尝试次数自动计；`budget` 记预算读数与当时的回执 id；`resume` 列未取、待重试（不到 3 次）与放弃的；`verify` 比第一次与最后一次读数：额度下降或出现新回执为 `deduction_seen`、都可读且相同为 `no_change_seen`、读数缺或 `unconfigured` 为 `unconfirmed`（看不出扣费，也不能证明没扣），有扣费迹象或快照不符退出码 2。输出的 `observation` 只有调用次数、预算读数与回执 id。
- `corpus agree`：双跑标注比对（S 部分）。先按 `schemas/data/corpus-label-vocabulary.json` 收敛词表（function 近义项合并，relation 同时成立时取更具体的），再比 function、relation、infoMode（有交集算一致）；任一项不一致记 `labelConfidence: low`。`--out` 写一份带 `labelConfidence` 的副本，low 的 `quality.label` 记 `low`；`corpus filter` 把 low 的列为 `label_low`，不进通过名单。
- `corpus defaults`：从语料重算随包统计——各形态的语速、停顿占比、单集时长、交换中位时长（都带 n），以及每张题材禁词表在本题材与别的题材里各出现多少、哪些词得到语料印证。候选新词可能带系列专有词，只写进 `--out`（项目目录）；随包数据文件只放统计量与原有词表。
- `feedback-ingest --out <空目录>`：全路由派生。句级、来回级、话题级、场结构、信息承载 → 反例；带改法的句级 → 人工正例；来回／话题级 → 对照对草稿；信息承载、对象约定、独白与同类 ≥2 次 → 约定草稿，同类 ≥2 次另起草新问；程序、事实 → 底账修订提案与 K1 卡草稿；决定 → 决定队列条目（`decided`，`humanWords` 是原话）。每个派生物带 `fromNotes` 与 `status: drafted`，`--purge <noteId>` 按 id 清掉。输入另认 `### ` 分节的批注记录、`--section <标题>` 指定的 md 一节（表格每行一条）、追问单回答记录（文件或目录；落在程序依赖上、或 `defectKind` 为 `contradicts_reality` 的 notHolds）。`--target <台词目标>` 时，起草的约定写进升版的台词目标（新 `revision`，`changelog` 记一条，原文件不动）。
- `contract-check dialogue-target`：有 `changelog` 时要有本修订的一条（新的在前、在后都认）；引用旧修订的任务照旧能过。`context-pack` 不装没有来源（`provenance` 或 `fromNotes`）的对照对。
- 工作室级语料（计划 §8 #1，2026-10-15 确认）：语料缓存可以放 `<工作室根>/corpus/`（工作室根是 `STUDIO.md` 所在目录）。`context-pack --studio-corpus <工作室根>/corpus` 时，`--exemplars` 可以是这个目录里的文件（按解析后的路径判断，`..` 与指向目录外的符号链接都拒）；装入的记录要是 `scope.level: studio` 且 `origin.kind: mali_story_template`，否则输入错误；对照对与对话表仍只能取自项目。`corpus label`／`agree`／`defaults` 对这个目录里的文件照同一条件核，`corpus fetch plan` 把台账写在这里时记 `scope.level: studio`。`contract-check corpus-manifest` 与 `dialogue-exchange` 放行 studio，条件相同；对照对、批注与知识卡仍只放行项目级。不给 `--studio-corpus` 时行为不变。
- 随包数据：`default-media-profile.json` 各形态带 `n`，交换中位时长按形态重算（真人剧 10.7 秒，n=107；漫剧 12.0 秒，n=31）；`genre-lexicon.json` 每张表带 `measured`（n 与语料印证的词）。

`reference-check` 核对实际保存的 mali-story 模板详情，默认沿用其声明集数，也支持显式 `--expected-episodes N`。退出码 2 表示资料声明或覆盖需要复核；字段齐全不证明原片真实、原剧完整或创作质量。见 [资料覆盖检查](skills/drama-studio/references/reference-check.md)。

## 成果与状态

每部剧输出市场依据、拉片资料索引、原创策划、设定与集纲、分集正文、检查和修订记录。Markdown 本地交付可直接使用；DOCX／飞书依赖宿主实际可用的转换工具或连接器。

项目和作品应保存在技能安装目录之外。mali-story 维护远端任务与正式版本，本地未同步稿明确标注。本版本支持按说明串行切换宿主，未实现本地多写者事务、自动后台调度或跨设备同步。

## 维护与验证

```sh
python3 -B -m unittest discover -s tests -v
python3 -B scripts/validate.py
```

- [AI 安装协议](INSTALL.md)
- [宿主接入与验证边界](docs/hosts.md)
- [验证记录与下一步](docs/verification.md)
- [模拟新用户安装与创作测试](docs/manual-test.md)
- [剧本结果验收方法](evals/screenplay-outcomes/README.md)与[首轮开发者试跑](evals/screenplay-outcomes/run-2026-09-22.md)：已有六集待审稿，尚无真实编剧采用结论。
- [防同质化行为用例](evals/screenplay-outcomes/diversity-regression.md)与[方法接入自查](evals/screenplay-outcomes/diversity-run-2026-09-22.md)：校准候选与证据判断，不等同于优质剧本验收。
- [来源说明](docs/provenance.md)
- [多场景结果验收矩阵](evals/screenplay-outcomes/scenario-matrix.md)：按创作、接续、阅读、资料与宿主分别记录，未测试项目不计入成功率。

依赖资料与工具规则持续版本化；不承诺剧本必成爆款，不将字面查重称为原创认证。
