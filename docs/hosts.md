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

提供 `package --host chatgpt` 生成的自包含技能包。根据账号和工作区当前支持的技能／插件导入入口安装，再配置 mali-story 远程 MCP。开发者模式和发布流程受账号／工作区策略影响，本仓库未发布公共 ChatGPT 插件。

普通网页会话不能因为导入技能获得本机终端和夸克客户端控制权限。若会话有代码执行，可在该环境运行随包检查，但它仍不等于获得用户电脑访问权。若无执行能力且未连接远程检查工具，则只进行有明确标注的模型审阅。

云端接续需依赖 mali-story 已部署的项目、候选与采用契约，不能依赖某台电脑的 PROJECT.md。缺少远端能力时显示未同步，不能声称跨设备完整接续。视频可由用户在 mali-story 中上传后继续。

## 官方依据

2026-09-21 阅读核对；安装时应以目标产品版本为准：

- [OpenAI Skills：目录与触发方式](https://learn.chatgpt.com/docs/build-skills)
- [OpenAI 插件架构：Skills、MCP 与界面](https://developers.openai.com/plugins/concepts/plugins)
- [ChatGPT 插件连接与测试](https://developers.openai.com/plugins/deploy/connect-chatgpt)
- [Claude Code Skills](https://code.claude.com/docs/en/skills)
- [WorkBuddy 技能规范](https://open.workbuddy.cn/docs/skill)
- [WorkBuddy 连接器规范](https://open.workbuddy.cn/docs/connector)
