# Drama Studio · 短剧创作工作室

把这个仓库交给 AI，让它安装短剧创作工作流。复用 Codex、Claude Code、ChatGPT 或 WorkBuddy 的模型与工具，通过 mali-story MCP 使用已有拉片和项目能力。

## 让 AI 安装

在有文件／命令权限的 AI 工具中，发送仓库地址并说：

> 请浏览 https://github.com/ZhiBoLingXi/drama-studio ，阅读 README.md 和 INSTALL.md，按我当前的 AI 工具安装 Drama Studio。先检查环境和已有安装，保留我的配置与修改，安装后引导我初始化工作目录、数据更新方式与常用偏好；询问是否开启定时采集，开启时确认时间和时区。验证技能发现，并按选择验证 mali-story MCP 连接。需要我登录时给出授权入口，不要启动创作或付费任务。

仓库目前为私有：用户的 GitHub 账号需具有读取权限，AI 所在环境也需能通过该账号访问。仅将链接粘贴到未授权的网页聊天中，无法读取仓库；可改为导入已获授权下载的技能包。

AI 的操作入口是 **[INSTALL.md](INSTALL.md)**。安装脚本只需要 Python 3.10+，不用安装 Python 包，不修改模型配置。用户无需手写 YAML、JSON 或复制个人密钥。

当前源码版本 `0.2.0` 提供自包含 Skill、离线安装／升级／校验、技能包导出及本地检查工具。它不是已发布到各平台市场的应用；完整创作、视频上传、桌面操作和宿主真实验收的状态见 [支持范围](docs/hosts.md)。

## 初始化工作室

安装后由 AI 检查已有环境和配置，分步询问必要选择，不要求用户手写配置。可直接说“初始化工作室”“把榜单采集改到每天北京时间9点”或“检查自动更新状态”。更改时间只修改已授权任务；没有已开启任务时先询问是否开启。

[初始化模块](skills/drama-studio/references/initialization.md)涵盖工作目录、数据入口、定时更新、账号连接、创作偏好、交付、费用和数据维护；选择与实际验证状态保存为工作目录中的 `STUDIO.md`。默认不开定时采集、付费任务、自动上传或对外通知。完整方案与尚未实现的执行器能力见[初始化设计](docs/initialization-design.md)。

## 装好后怎么用

> 帮我研究近期适合低成本漫剧的女频复仇题材，推荐三部对标，先给依据。

> 使用已有拉片模板，给我三个原创选题，选定后出全剧蓝图。

> 继续这个项目，读取编剧修订后的集纲，再写下一批正文。

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

项目级：在上述命令加 `--scope project --project /absolute/path/to/workspace`。升级加 `--upgrade`；只有原安装未被修改才替换，旧版本保存在返回的 backup 路径。

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

`contract-check <对象> <文件>` 校验[创作工位契约](skills/drama-studio/references/workstations/README.md)的交接对象（task、knowledge-card、context-snapshot、review-record、run-handoff、remote-receipt），Schema 在 `skills/drama-studio/schemas/`，示例在 `skills/drama-studio/schemas/examples/`。它拒绝超预算快照、混入评估材料、必需材料缺失却标完整、非上游变更提案、本地自称已采用等情况，退出码 2 表示违反；通过不代表远端引用存在或创作达标。首版知识卡只接受项目私有范围。

`context-pack` 按任务和宿主给出的选材清单（`selection`，格式见 `skills/drama-studio/schemas/selection.schema.json` 与示例）确定性地组装 `context-snapshot`。选材是模型的判断，装包只做读取、截取、计数、过滤和写出：

```sh
python3 -B skills/drama-studio/scripts/drama_tools.py context-pack ../my-drama --task task.json --selection selection.json --role author --budget 20000
python3 -B skills/drama-studio/scripts/drama_tools.py context-pack ../my-drama --task task.json --selection selection.json --role reader_effect --budget 20000 --dry-run
```

- 只读 `--task`、`--selection`、`.drama/cache/manifest.json` 指向的缓存文件（路径必须在 `.drama/cache/` 内）和 `knowledge/cards/<cardId>@r<修订>.json`；只写 `.drama/snapshots/<snapshotId>.json` 与 `.sha256`。不联网、不调用模型，也不代表远端已核验。
- 第 0 项总是任务本身（`task` 分区，由工具按 `--task` 填入，选材清单里不能写 `task` 分区）。选材清单为空时输出只含任务的最小快照；任务字数计入 `--budget`。
- `range` 是按 Unicode 码点截取（`text[start:end]`，中文一字计 1），不是字节。`chars` 与各项 `sha256` 由工具按实际截取文本计算；清单里宿主估算的 `chars` 被忽略。知识卡按卡片 JSON 文件原文计数和截取（含 JSON 标点），不是只算正文字段。
- 快照 ID 为 `ctx-` 加内容哈希前 16 位，不含时间戳；同一输入重跑产出逐字节相同的文件，已存在且相同时报告 `existing: true`，内容不同则拒绝，绝不覆盖。
- 缓存或知识卡不存在 → 记入 `omitted`（reason `missing`），必需项缺失时 `completeness: incomplete`，退出码仍为 0；退役知识卡记为 `not_relevant`。
- 退出码 2（不写任何文件，错误指出选材序号与引用）：超预算（按分区报告字数与超出量，不截断）、缓存字节与 manifest 的 sha256 不符、manifest 标 `verified: false`、同一 slot 出现两个修订或同一知识卡两个修订、`evaluation_only`／`comparison_only` 进入不允许的角色、`reader_effect` 带 `current_plan`、最终快照未通过 `contract-check`。退出码 1：输入错误，如区间越界（指出引用与文本长度）、引用类型不是 `remote_artifact`／`knowledge_card`、修订为空、任务未指定工位。
- `.drama/cache/`、`knowledge/cards/`、`.drama/snapshots/` 若是指向项目外的符号链接，退出码 1；知识卡的 `scope.projectId` 必须等于任务的 `project.localId`，否则退出码 2。写入先落临时文件再硬链接到位，中断不会留下半截快照。
- `--dry-run` 执行全部检查（含已存在快照的冲突检查）并打印将装入的项、字数与遗漏，输出 `would_write` 而非 `snapshot_path`，不写文件。`--allow-unverified` 允许装入服务端指纹未核验的缓存，并在快照 `unknowns` 写明 `服务端指纹未核验：<artifactId>@r<修订>`。

`knowledge {validate,search,show} <项目>` 只读管理项目私有知识卡：卡片放在 `knowledge/cards/<cardId>@r<revision>.json`，本地证据放在 `knowledge/sources/<sourceId>/`。validate 逐卡运行契约校验并核对文件名；search 只返回每卡最新有效修订，默认排除退役卡（`--include-retired` 可纳入），按类型、工位、用途、关键词过滤，并标注共享 sourceId 的同源卡（只说明来源重复，不说明可靠）；show 打印卡片与来源位置并核对本地证据文件存在。无效卡、来源缺失或越界时退出码 2；`knowledge/` 不存在时返回空结果与目录提示、退出码 0。详见[知识库目录与命令](skills/drama-studio/references/workstations/README.md#知识库目录与命令)。

`receipt` 把宿主保存的 mali-story MCP 响应记成回执（`.drama/receipts/`），把完整读到的候选正文写入本地缓存（`.drama/cache/`），工具本身不联网、不调用 MCP。以下用合成夹具演示：

```sh
python3 -B skills/drama-studio/scripts/drama_tools.py receipt record ../my-drama tests/fixtures/mcp-synthetic/02-save.response.json --operation save_story_artifact --request-id d1-save-2 --input tests/fixtures/mcp-synthetic/02-save.input.json
python3 -B skills/drama-studio/scripts/drama_tools.py receipt pending ../my-drama
python3 -B skills/drama-studio/scripts/drama_tools.py receipt cache ../my-drama tests/fixtures/mcp-synthetic/08-read-chunk-*.response.json tests/fixtures/mcp-synthetic/03-get.response.json
python3 -B skills/drama-studio/scripts/drama_tools.py receipt show ../my-drama d1-save-2
```

同一 requestId 输入不同、缓存分块不完整或全文哈希与服务端 `fingerprint` 不符时退出码 2，已有文件不变；响应缺失记 `unknown` 且不允许重试。回执和缓存都不是采用证据。方法见 [候选保存与对账](skills/drama-studio/references/mali-story.md#候选保存与对账)。

`status` 与 `impact` 只读项目的 `.drama/`（回执、缓存 manifest、快照、运行记录），用于换会话或前文修订后恢复现场；不读聊天记录、不联网、不写任何文件（不建目录，不留锁文件）：

```sh
python3 -B skills/drama-studio/scripts/drama_tools.py status ../my-drama
python3 -B skills/drama-studio/scripts/drama_tools.py status ../my-drama --json
python3 -B skills/drama-studio/scripts/drama_tools.py impact ../my-drama --slot ep-03-outline --revision 2
python3 -B skills/drama-studio/scripts/drama_tools.py impact ../my-drama --artifact c41d2b7a-8e5f-4a3b-b6d9-0f1e2a3b4c5d
```

- `status` 默认输出中文文本，第一行是下一步动作；`--json` 输出同一内容的 JSON。下一步按固定顺序取：结果未知且未对账的保存回执（沿用 `receipt pending`）→ 无效或损坏的记录 → 最近一次运行的快照引用了旧修订时，先运行给出的 `impact` 命令（该运行原先记录的 `nextAction` 列在第二行，注明是按旧修订的上下文记录的）→ 最近一次运行的 `nextAction` → 没有运行记录时的提示。失效提示沿用 `impact` 的判定规则，只比较本地缓存 manifest：每个列出的运行带 `stalenessCheck`，快照引用的修订低于同一 slot 已缓存的最新可信修订时为 `newer_revision_cached` 并标 `possiblyStale: true`（附 slot、所引用修订、最新可信修订和完整的 `impact` 命令）；引用解析不出可信 slot、缺 revision、manifest 或快照不可读时为 `unknown` 并附原因，不占第一行，也不说它新或旧；更新的修订按上面的规则全部由运行记录声称为自身产出、且证据完整时为 `newer_revision_is_own_output`，不占第一行；证据不完整（包括自身产出之上还有不可信条目声称属于同一 slot）时为 `unknown`；其中有不是它产出的修订时仍是 `newer_revision_cached`，`staleAgainstRevision` 与给出的命令指向不是它产出的最高修订；否则为 `no_newer_revision_cached`，只表示本地缓存里没有更新的可信修订，不说明远端有没有。给出的命令写成 `--slot=<slot>`，slot 以 `-` 开头也能照抄执行。缓存 manifest 损坏或不是 v0 结构时计入无效记录（kind 为 `manifest`），每条无效记录附一句按类型写的处理办法。文本输出把多行的 `nextAction`、`unfinished` 压成一行，JSON 保留原值；slot 含换行类字符时文本里转义显示且不打印命令，完整命令在 `--json` 的 `impactCommand` 里。它同时列出所有未结束（`planned`／`running`／`interrupted`）或 `unfinished` 非空的运行，以及每个快照的完整性：契约校验、文件名与 `snapshotId` 是否一致、`.sha256` 旁车与文件字节是否一致、`completeness`。运行记录没有时间字段，“最近”按文件修改时间判定（输出 `recencyBasis: file_mtime`），复制或检出后可能不准。只读调用的未知结果（`read_only_unknown`、`unreconcilable_unknown`）会列出，但不排在第一行。
- `impact` 输出 JSON，把每个快照和运行标为 `stale`、`unknown` 或 `current`。mali-story 每个修订的 artifactId 都不同，新旧一律按 slot 判断：快照 `items` 中引用了目标 slot 较旧修订的为 `stale`，依赖该快照的运行（`contextSnapshotId`）随之为 `stale`，并写明是哪条引用。例外是运行记录声称自己产出了这些修订的运行，这条例外只在证据完整、可信、无歧义时成立。同一 slot 的修订号每保存一次加 1，所以从快照所引用的修订 P 到目标修订 T，中间每一个修订号（P+1 到 T）都必须是 manifest 里可信的缓存条目，并且都列在这次运行的 `outputs` 里；其中任何一个修订号不能同时有两个可信的 artifactId；manifest 里也不能有不可信或互相冲突的条目声称属于这个 slot，除非它的修订号确定不高于 P。全部满足时，快照对旧修订的引用不使这次运行失效，运行标 `current` 并写明“运行记录声称产出了…”，快照本身仍是 `stale`。不满足时分两种：P+1 到 T 之间有可信的修订不是它产出的（例如从 r1 直接产出 r3，而缓存里另有别人的 r2），照常标 `stale`；其余情况（中间有修订号没缓存、有宿主声明或冲突的条目、同一修订号有两个可信产物）标 `unknown`，原因里写明是哪个修订或哪条条目。`outputs` 是运行记录自己的说法，工具不核实；状态为 `planned` 或 `failed` 的运行不适用这条例外，在这段修订里没有自身产出的运行按没有这条例外处理，其他 slot 的旧引用照常计入。快照里的 `context_snapshot` 引用继承被引用快照的结论（找不到、损坏或成环为 `unknown`）；任务文件（`task` 分区里的 `local_file`，即 `context-pack` 写入的那一项）与知识卡不算 slot 依赖；嵌套超过 50 层不再展开，按 `unknown` 处理；其余引用类型（其他 `local_file`、`remote_snapshot`、`remote_brief`、`remote_receipt`）一律 `unknown`，原因写“该引用类型的依赖未评估”。输出的 `target` 带 `slotInManifest`（manifest 里有没有任何条目属于目标 slot）和 `newestTrustedRevision`（该 slot 已缓存的最新可信修订，没有则为 null）；目标 slot 在 manifest 里从未出现时 `warnings` 提示可能是拼写错误，此时全部 `current` 只覆盖记录在案的引用。目标修订低于该 slot 已缓存的最新可信修订时也有一条 `warnings`，提示结论只针对所给的修订。小于 1 的修订号无效，带这种修订的条目或引用一律 `unknown`。`--artifact` 经 manifest 解析出 slot 与 revision，与 `--slot`／`--revision` 互斥。
- 不确定一律标 `unknown`，附原因和“扩大阅读”建议：artifactId 不在 manifest、slot 只是宿主声明、同一 artifactId 有互相冲突的条目、引用缺 revision 或与 manifest 不一致、快照损坏、运行找不到所依赖的快照。`current` 只表示没有记录在案的执行依赖指向该 slot 的旧修订；内容层面的隐含依赖未评估。工具不自动重跑，也不改写正文。
- slot 的可信度记在 manifest 条目的可选字段 `slotSource`：`receipt cache` 带 `get_story_artifact` 响应时为 `record`；只给分块、但本地有该 artifactId 的 confirmed 保存回执且 slot 一致时为 `receipt`（与 `--slot` 不一致则拒绝写入，退出码 2）；否则为 `host`。`receipt record` 遇到 confirmed 的保存响应且响应里带 `record.slot` 时，会把它与 `--input` 的 slot 比对：不一致即拒绝写回执（退出码 1），一致则在回执 `notes` 里记 `slotCheck`。只有带这条记录的回执才能让缓存条目记为 `receipt`；响应不带 slot 的回执、以及这项检查加入之前写的回执，slot 仍只是输入文件的说法，不算数。工具不联网，这项比对只说明两份保存下来的文件互相一致。`host` 或没有该字段的条目在 `impact` 中按 `unknown` 处理；用 get 响应重新缓存会追加一条 `record` 条目，manifest 只追加，旧条目不改不删。宿主声明的 slot 如果写错了，带 get 响应重新缓存会因 slot 冲突被拒绝：工具改不了那条条目，要由人手工从 `manifest.json` 去掉错误条目后再缓存，在此之前该产物在 `impact` 中一直是 `unknown`。
- 退出码 0 表示分析完成，结论读输出里的状态；退出码 1 是输入或执行错误，例如项目没有 `.drama/`、`impact` 的目标参数不成组、`--revision` 不是不小于 1 的整数、`--slot` 为空、`--artifact` 解析不出可信的 slot。两个命令的 JSON 输出都带 `read_only: true`、`remote_verified: false`，不证明远端状态或采用。合成夹具上的完整命令链、输出与前后 sha256 见 [恢复与失效演示记录](docs/d2/recovery-demo.md)；它不是真实创作产物上的验证。

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
