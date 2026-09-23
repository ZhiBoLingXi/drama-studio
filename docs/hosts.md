# 宿主接入与验证边界

这些是当前发行包的安装路径与产品能力边界。安装器测试不替代宿主真实发现或远端业务验证。

## Codex

安装器使用用户级 `~/.agents/skills/drama-studio` 或项目级 `.agents/skills/drama-studio`。可用宿主内置 skill-installer 安装同一技能目录，但本仓库的升级回执只管理通过本仓库安装器安装的副本。

先检查已有 mali-story 连接。不存在时，可按当前 CLI 帮助执行：

```sh
codex mcp add mali-story --url https://story-api.maliai.art/mcp
codex mcp login mali-story --scopes story:read --oauth-client-registration dcr
```

上述命令在维护环境通过 `--help` 核实；目标版本仍应先查帮助。连接名冲突时先核对现有 URL，不能覆盖其他服务。只读授权用于安装验证；后续写操作按需要补充 `story:write`。不要为续期或扩 scope 删除用户无关配置。

## Claude Code

安装器使用 `~/.claude/skills/drama-studio` 或项目级 `.claude/skills/drama-studio`。安装后通过当前宿主技能发现机制确认可见。

MCP 使用当前 CLI 的 HTTP 连接入口；先读取 `claude mcp add --help`，确定 scope、参数及已有连接，再添加上述服务 URL，通过 `/mcp` 完成认证。项目级技能不会自动成为所有云端／桌面产品中的技能。

## WorkBuddy

优先使用 `package --host workbuddy` 生成的技能 ZIP，通过当前版本的技能导入／创建入口接入。若已有明确本地技能目录，可使用安装器 `--skills-dir` 路径。

远程 mali-story 使用 MCP＋Skill 连接方式。WorkBuddy 官方也提供 CLI＋Skill，但一个连接器只选择一种；不要把独立上传工具配置与 MCP 连接器清单混写。当前包未创建 WorkBuddy 连接器商店条目或 Buddy 应用。

本地检查依赖宿主能执行 Python；夸克依赖实际可用的桌面操作工具。需要时用户手动下载／上传后，AI 从远端任务或模板继续。MCP 支持不等于具有所有桌面控制工具。

## ChatGPT

先区分桌面本地技能与网页／云端插件。ChatGPT 桌面端支持独立技能，可在 Skills 中查看并用 `@` 选择；本地 Codex 技能目录可用本仓库 `--host codex` 路径安装，但文件安装成功后仍须在实际使用的桌面模式、新会话中验证发现，不能据此宣称网页账号已安装。

`package --host chatgpt` 只生成自包含技能 ZIP，不会自动注册账号或连接 MCP。网页／云端通过插件分发的接入与本地技能不同；本仓库尚未发布跨端 ChatGPT 插件。只有实际界面提供兼容的导入入口时才使用该 ZIP，普通聊天附件上传不算持久安装。`install --host chatgpt` 不会写入猜测的宿主目录。登录和 mali-story MCP 连接另行验证。

普通网页会话不能因为导入技能获得本机终端和夸克客户端控制权限。若会话有代码执行，可在该环境运行随包检查，但它仍不等于获得用户电脑访问权。若无执行能力且未连接远程检查工具，则只进行有明确标注的模型审阅。

云端接续需依赖 mali-story 已部署的项目、候选与采用契约，不能依赖某台电脑的 PROJECT.md。缺少远端能力时显示未同步，不能声称跨设备完整接续。视频可由用户在 mali-story 中上传后继续。

## 可选 Yoki 红果榜单

上游[红果组件](https://github.com/yokichen9149-byte/yoki-data-analysis/tree/main/mcp/hongguo-rank)目前以本地 SQLite 加 stdio MCP 提供查询，采集独立执行。支持本地命令型 MCP 的宿主可复用既有部署；先确认实际路径、依赖与连接，不因安装本技能启动第二套服务或日更任务。查询不会自动采集，新用户没有历史数据时不能获得过去多日趋势。

只有用户需要新接入时，按宿主实际界面或CLI帮助配置。命令使用该组件现有虚拟环境的 Python，参数为该部署的 `server.py` 绝对路径；不得复制其他机器的虚拟环境。新环境依赖以其锁文件为准，留在可选组件环境中，不加入 Drama Studio 运行依赖。

本地stdio配置示例仅供已确认路径后适配宿主，不能整段覆盖用户配置：

```toml
[mcp_servers.hongguo_local]
command = "/absolute/path/to/existing/hongguo-rank/.venv/bin/python"
args = ["/absolute/path/to/existing/hongguo-rank/server.py"]
```

ChatGPT网页等不能启动本地进程的环境使用用户提供的导出文件，或由用户另行提供已部署的远程服务；本项目不附带远程榜单地址。实际查询与文件格式见[可选数据源](../skills/drama-studio/references/hongguo-rank.md)。Yoki拉片和采购审核仍为独立可选能力，不随此接入安装。

## 官方依据

OpenAI Skills 文档于2026-09-23再次核对，其余依据为2026-09-21；安装时以目标产品版本及实际界面为准：

- [OpenAI Skills：目录与触发方式](https://learn.chatgpt.com/docs/build-skills)
- [OpenAI 插件架构：Skills、MCP 与界面](https://developers.openai.com/plugins/concepts/plugins)
- [ChatGPT 插件连接与测试](https://developers.openai.com/plugins/deploy/connect-chatgpt)
- [Claude Code Skills](https://code.claude.com/docs/en/skills)
- [WorkBuddy 技能规范](https://open.workbuddy.cn/docs/skill)
- [WorkBuddy 连接器规范](https://open.workbuddy.cn/docs/connector)
