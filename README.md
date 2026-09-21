# Drama Studio · 短剧创作工作室

把这个仓库交给 AI，让它安装短剧创作工作流。复用 Codex、Claude Code、ChatGPT 或 WorkBuddy 的模型与工具，通过 mali-story MCP 使用已有拉片和项目能力。

## 让 AI 安装

在有文件／命令权限的 AI 工具中，发送仓库地址并说：

> 请浏览 https://github.com/ZhiBoLingXi/drama-studio ，阅读 README.md 和 INSTALL.md，按我当前的 AI 工具安装 Drama Studio。先检查环境和已有安装，保留我的配置与修改，安装后验证技能发现和 mali-story MCP 连接。需要我登录时给出授权入口，不要启动创作或付费任务。

仓库目前为私有：用户的 GitHub 账号需具有读取权限，AI 所在环境也需能通过该账号访问。仅将链接粘贴到未授权的网页聊天中，无法读取仓库；可改为导入已获授权下载的技能包。

AI 的操作入口是 **[INSTALL.md](INSTALL.md)**。安装脚本只需要 Python 3.10+，不用安装 Python 包，不修改模型配置。用户无需手写 YAML、JSON 或复制个人密钥。

当前版本 `0.1.0` 提供自包含 Skill、离线安装／升级／校验、技能包导出及本地检查工具。它不是已发布到各平台市场的应用；完整创作、视频上传、桌面操作和宿主真实验收的状态见 [支持范围](docs/hosts.md)。

## 装好后怎么用

> 帮我研究近期适合低成本漫剧的女频复仇题材，推荐三部对标，先给依据。

> 使用已有拉片模板，给我三个原创选题，选定后出全剧蓝图。

> 继续这个项目，读取编剧修订后的集纲，再写下一批正文。

工作流：市场研究 → 对标确认 → 优先复用模板／必要时获取视频并调用 mali-story 拉片 → 原创选题 → 蓝图与集纲 → 方向样稿 → 全剧正文 → 审查、交付和反馈修订。

按需加载方法参考，不依赖用户另装 DramaRewrite、DramaContinuation 等个人技能目录。模型负责判断与创作，脚本负责能客观计算的检查，编剧决定关键方向和稿件采用。

## 各入口的安装方式

| 入口 | 本仓库提供 | 实际使用前还需确认 |
| --- | --- | --- |
| Codex | 复制到标准技能目录，支持用户级／项目级 | 宿主发现技能、mali-story 授权 |
| Claude Code | 复制到标准技能目录，支持用户级／项目级 | 宿主发现技能、mali-story 授权 |
| WorkBuddy | 带所需元数据的 ZIP；确认目录后也可本地安装 | 当前版本导入、MCP 连接、本地命令能力 |
| ChatGPT | Skill ZIP 与远程 MCP 接入说明 | 账号是否支持导入／插件开发、本地与云端执行边界 |

纯网页聊天不能因为读了仓库就自动获得本机文件和桌面操作权限。无命令权限时走技能导入与远程连接；缺少可用远程检查服务时如实标注“客观检查未执行”。

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

已打包的版本从 [GitHub Releases](https://github.com/ZhiBoLingXi/drama-studio/releases) 获取，同样需要仓库读取权限。

本地工具（安装后使用安装目录中的同名脚本）：

```sh
python3 -B skills/drama-studio/scripts/drama_tools.py doctor
python3 -B skills/drama-studio/scripts/drama_tools.py init-project ../my-drama --title '我的新剧'
python3 -B skills/drama-studio/scripts/drama_tools.py episode-check examples/sample-episode.md
python3 -B skills/drama-studio/scripts/drama_tools.py dup-check --new examples/sample-episode.md --source examples/sample-reference.md
```

示例刻意很短，逐集检查应返回退出码 2，用于证明未过检查会真实报告。`doctor` 只证明离线工具可加载，不能证明 MCP 已连接。项目初始化只建立本地工作目录，不创建远端项目。完整命令参数使用 `--help` 查看。

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
- [来源说明](docs/provenance.md)

依赖资料与工具规则持续版本化；不承诺剧本必成爆款，不将字面查重称为原创认证。
