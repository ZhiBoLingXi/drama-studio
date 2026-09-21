# 给 AI 的安装协议

目标：将当前仓库的 Drama Studio 安装到用户正在使用的宿主，并给出逐层验证结果。用户已要求安装时，继续必要的本地步骤；只在确实缺少目标环境、目录选择或用户登录时询问。安装不包括启动创作、视频上传和付费分析。

## 1. 识别环境与获取项目

先识别宿主、操作系统、文件／命令权限、Python 3.10+。不要从浏览器 user-agent 猜本机工具权限。用户已提供仓库目录时复用；提供 URL 时，在其工作目录克隆到新的子目录，使用具体真实 URL，不创建虚构仓库地址。

执行 `python3 --version` 检查实际版本。macOS 的 `python3` 可能仍指向系统 3.9；此时优先查找已安装的 `python3.10`、`python3.11`、`python3.12` 等，并用满足要求的解释器替换本文所有 `python3`，不要修改系统软链接。

已有 checkout 时先看状态和版本，不执行会覆盖修改的拉取。只有浏览权限时读取本说明与 [宿主指南](docs/hosts.md)，转到宿主支持的导入方式；不能声称已经执行了安装。Python 缺失时给出当前系统适用安装途径，不擅自修改系统环境。

## 2. 本地安装

在仓库根目录运行对应命令。Codex 用 `codex`，Claude Code 用 `claude-code`：

```sh
python3 -B scripts/install.py plan --host codex
python3 -B scripts/install.py install --host codex
python3 -B scripts/install.py verify --host codex
```

默认用户级；用户只要当前项目时三条命令都加 `--scope project --project <真实工作目录>`。WorkBuddy 本地目录需从当前产品实际配置确认，再传 `--host workbuddy --skills-dir <已确认技能目录>`；不硬编码一个未经验证的目录。

安装只写一个 `drama-studio` 技能目录与安装回执，不改 AGENTS.md、CLAUDE.md、模型密钥或整个 MCP 配置。相同内容重复运行不修改。不同版本要升级时用 `--upgrade`；安装器检查原回执、拒绝覆盖用户修改，并保留旧目录。遇到无回执的同名目录或修改冲突时，说明具体位置，保留内容，不能删掉或强制覆盖。

## 3. ChatGPT／WorkBuddy 技能导入

```sh
python3 -B scripts/install.py package --host chatgpt
python3 -B scripts/install.py package --host workbuddy
```

选择与当前宿主匹配的一个。ZIP 根目录是 SKILL.md，附带 references 和 scripts；WorkBuddy 版本增加其要求的双语描述、版本和作者字段。导入入口和账号支持按当前宿主实际界面确认。这是技能包，不是已经审核上架的商店应用。

如果当前 AI 不能运行打包命令，从仓库维护者提供的真实 release 附件获取相应包；没有发布附件时明确这一缺口，不编造下载链接。可以临时让宿主读取技能说明辅助工作，但不得把临时阅读当作持久安装成功。

## 4. 连接 mali-story

读取 [宿主指南](docs/hosts.md) 和技能内 [mali-story 指南](skills/drama-studio/references/mali-story.md)。默认 URL 为 `https://story-api.maliai.art/mcp`，用户已有其他部署时保留其选择。

优先复用当前宿主已有且指向正确服务的连接。需要新建时使用宿主原生 MCP 管理命令／界面，保留其他连接。用户完成 OAuth；不提取宿主私有令牌、不把密钥放入仓库或聊天。

安装默认先进行只读验证：发现工具、列出实际 API 目录、读取当前账号可访问的一页模板列表。未来要新建任务时，再按既有授权与操作所需权限推进；不要为了验证安装发起付费写入。

## 5. 验收回执

分开报告以下状态，不将其中一项通过扩写为全部通过：

1. 技能文件和版本：安装位置、校验结果。
2. 离线工具：`doctor` 返回结果；示例检查按预期失败，不能改示例凑通过。
3. 宿主发现：当前宿主能列出／调用 `drama-studio`。需新会话刷新时说明。
4. MCP 授权与工具发现：成功、待登录或具体失败。
5. 真实业务读取：个人／官方模板列表实际可读；没有模板也是有效空结果。
6. 尚未验证：真实上传、收费拉片、夸克完整下载、全剧创作验收。

成功后给一句启动示例：“帮我研究近期适合我的制作条件的短剧，先推荐对标。” 不自动继续这个示例。
