# Drama Studio · 短剧创作工作室

把这个仓库交给 AI，让它安装短剧创作工作流。复用 Codex、Claude Code、ChatGPT 或 WorkBuddy 的模型与工具，通过 mali-story MCP 使用已有拉片和项目能力。

## 让 AI 安装

在有文件／命令权限的 AI 工具中，发送仓库地址并说：

> 请浏览 https://github.com/ZhiBoLingXi/drama-studio ，阅读 README.md 和 INSTALL.md，按我当前的 AI 工具安装 Drama Studio。先检查环境和已有安装，保留我的配置与修改，安装后验证技能发现和 mali-story MCP 连接。需要我登录时给出授权入口，不要启动创作或付费任务。

仓库目前为私有：用户的 GitHub 账号需具有读取权限，AI 所在环境也需能通过该账号访问。仅将链接粘贴到未授权的网页聊天中，无法读取仓库；可改为导入已获授权下载的技能包。

AI 的操作入口是 **[INSTALL.md](INSTALL.md)**。安装脚本只需要 Python 3.10+，不用安装 Python 包，不修改模型配置。用户无需手写 YAML、JSON 或复制个人密钥。

当前源码版本 `0.2.0` 提供自包含 Skill、离线安装／升级／校验、技能包导出及本地检查工具。它不是已发布到各平台市场的应用；完整创作、视频上传、桌面操作和宿主真实验收的状态见 [支持范围](docs/hosts.md)。

## 装好后怎么用

> 帮我研究近期适合低成本漫剧的女频复仇题材，推荐三部对标，先给依据。

> 使用已有拉片模板，给我三个原创选题，选定后出全剧蓝图。

> 继续这个项目，读取编剧修订后的集纲，再写下一批正文。

> 在现有方向和制作条件内自主优化。保留当前完整稿，补充有来源的生活材料，探索不同因果的方案，先试关键场面再决定是否扩写；分别报告可编辑性、辨识度和阅读反馈。

工作流：市场研究 → 对标确认 → 优先复用模板／必要时获取视频并调用 mali-story 拉片 → 生活材料与创作立场 → 不同因果选题与场面试写 → 蓝图与集纲 → 方向样稿 → 全剧正文 → 审查、交付和反馈修订。已有阶段成果可直接接续。

按需加载方法参考，不依赖用户另装 DramaRewrite、DramaContinuation 等个人技能目录。模型负责判断与创作，脚本负责能客观计算的检查，编剧决定关键方向和稿件采用。

[创作开发方法](skills/drama-studio/references/development-lab.md) 随技能分发，附开发记录和分阶段阅读模板，由 AI 按需填写。当前完整稿与探索片段分别保存，避免失败探索覆盖可用版本。评审分别判断因果底线、辨识度和阅读偏好，不以字面低重合或平均高分宣称优质；无独立上下文时如实使用串行自评。

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
```

逐集检查默认只统计，返回 `constraint_status: not_configured`、`passed: null`；退出码 0 仅表示统计已完成。它不会因示例短而判剧本不合格，也不评价创作质量。

项目已有明确制作规格时，由 AI 按约定填写配置并显式使用；配置不会自动发现或自动启用。以下配置仅演示格式：

```sh
python3 -B skills/drama-studio/scripts/drama_tools.py episode-check examples/sample-episode.md --config examples/episode-constraints.json
python3 -B skills/drama-studio/scripts/drama_tools.py episode-check examples/sample-episode.md --min-chars 1200
python3 -B skills/drama-studio/scripts/drama_tools.py episode-check examples/sample-episode.md --preset legacy-aigc
```

第二条只检查显式指定的字数约束，示例应返回退出码 2。第三条显式启用历史 AIGC 示例规格，不代表行业标准。规则格式、来源、优先级及结果解释见 [剧集检查说明](skills/drama-studio/references/episode-check.md)。

`doctor` 只证明离线工具可加载，不能证明 MCP 已连接。项目初始化只建立本地工作目录，不创建远端项目。完整命令参数使用 `--help` 查看。

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
