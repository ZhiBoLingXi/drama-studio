# D5 发布前验证记录（#51）

2026-10-08。只做验证与记录，不改任何代码。所有安装/升级都用 `--skills-dir` 指向会话临时目录（`/private/tmp/.../scratchpad/d5-install/`），没有碰 `~/.claude/skills` 等用户真实安装目录；`package` 输出也写到同一临时目录，没有写入仓库 `dist/`。当前源码版本 `0.2.0`（`VERSION`），HEAD 为 `db5e8e5`。

## 1. 回归：测试与 validate.py

```sh
python3 -B -m unittest discover -s tests -v
python3 -B scripts/validate.py
```

- 单元测试：340 个全部通过，退出码 0（跑在 `main`@`db5e8e5`）。
- `validate.py`：第一次在本仓库工作目录里实跑返回退出码 1，错误全部是 `Missing link: .claude/worktrees/agent-a7e1ca5e8b834e7b9/docs/...`。排查确认：这是会话里另一个并发 agent（分支 `feat/52-import-project`）在仓库内留下的、未纳入 git 跟踪的本地 worktree（`.claude/` 不在 `.gitignore` 里），与本次验证和 `drama-studio` 的发布内容无关；用 `git worktree add` 在干净的 HEAD 检出上单独跑同一脚本，错误条数与路径一一对应，确认是该 worktree 嵌套层级导致的相对路径误判，仓库真实顶层文档（`docs/design/*.md`、`docs/refactor-plan-2026-09-28.md`）里指向 `../mali-story/...` 的链接本身都能解析到本机已有的 `mali-story` 仓库。**判断：测试通过；`validate.py` 对仓库实际交付内容无新增失败，第一次失败是环境污染（另一 agent 的并发 worktree），不是代码缺陷。** 附带发现：`validate.py` 用 `ROOT.rglob` 扫描整个文件系统子树而不管 git 跟踪状态，容易被这类未跟踪目录污染而误报——这与 AC-4 本身无关，但值得记一笔。
- **会话期间的环境异常**：写完本文档后再跑一次 `validate.py` 确认本文件本身不引入新错误，发现此时 `git worktree list` 只剩一条记录，且**主工作目录本身的分支已经从 `main`（`db5e8e5`）变成了 `feat/52-import-project`（`673cade`）**——这不是本次验证任务做的任何操作（本任务全程没有 `git checkout`/`git switch`），而是会话里另一个并发 agent 对共享工作目录做了分支切换。在该状态下 `validate.py` 返回 `ok: true`（0 错误，`bundle_files: 55`，比之前多 1 个文件，说明那个分支已经合入了新内容）。记录在此作为提醒：本文档第 1～4 节的全部命令与判断，都是在 `main`@`db5e8e5`（或我自建的 `git worktree` 固定到具体 commit）上做的，不受这次分支切换影响；但如果有人要复核，应先确认自己仓库工作目录当前在哪个分支/commit。

## 2. 四个 host 的全新安装 + verify（AC-1）

```sh
python3 -B scripts/install.py plan    --host <h> --skills-dir <tmp>/<h>/skills
python3 -B scripts/install.py install --host <h> --skills-dir <tmp>/<h>/skills
python3 -B scripts/install.py verify  --host <h> --skills-dir <tmp>/<h>/skills
```

| host | plan/install/verify | 结果 |
| --- | --- | --- |
| codex | 全新目录，`--skills-dir` 正常接受 | 三步全部 `ok: true`，54 个文件，`doctor` 自检 `ok: true` |
| claude-code | 同上 | 同上 |
| workbuddy | 同上（README 要求"确认目录后"，用 `--skills-dir` 正是这个确认动作） | 同上，`SKILL.md` 按预期注入 workbuddy frontmatter（打包时验证，见第 4 节） |
| chatgpt | `plan`/`install`/`verify` 全部直接报错退出码 1：`"ChatGPT requires skill import and remote MCP setup; use package and docs/hosts.md"`，即使带 `--skills-dir` 也一样——`destination()` 对 `chatgpt` 无条件拒绝 | **与 README 一致**：README 的入口表写 ChatGPT 是"桌面本地技能指南、Skill ZIP 与远程 MCP 说明"，不支持本地目录安装；这不是 bug，是按设计的行为，照实记录 |

四个 host 均未命中"不支持 `--skills-dir` 或要求别的参数"的情况——唯一的参数差异是 chatgpt 完全不接受 `destination()` 相关参数（包括 `--skills-dir`），其余三个 host 行为一致。

## 3. claude-code：升级 / 拒绝覆盖 / 回退（AC-2）

用 `git worktree` 在旧提交（`2faa236`）上安装出两份"未修改"的基线安装（`claude-code-a`、`claude-code-b`），再切回 HEAD 做以下三步：

**(a) 未修改安装 → `install --upgrade`**

```sh
python3 -B scripts/install.py plan    --host claude-code --skills-dir <tmp>/claude-code-a/skills   # action: upgrade_required
python3 -B scripts/install.py install --host claude-code --skills-dir <tmp>/claude-code-a/skills --upgrade
python3 -B scripts/install.py verify  --host claude-code --skills-dir <tmp>/claude-code-a/skills
```

结果：`action: "upgraded"`，返回 `backup` 路径（`.drama-studio-backup-490cb5e2...`，与安装目录同级的隐藏目录），升级后 `verify` 返回 `ok: true`、`matches_checkout: true`。**通过。**

**(b) 手动改过的安装 → `install --upgrade`**

在 `claude-code-b` 的 `SKILL.md` 末尾手动追加一行后再跑同样的 `plan`/`install --upgrade`：两者都返回退出码 1，错误信息 `"Local skill modifications detected; preserve them: SKILL.md"`，目标目录文件未被覆盖（追加的那行仍在）。**通过，拒绝理由清楚指向被改的文件。**

**(c) 回退演示**

脚本和 README 都没有提供专门的回滚/回退命令（`install.py` 只有 `plan|install|verify|package` 四个子命令），所以按手工方式演示：把 (a) 升级后的当前目录移走，再把 (a) 产生的备份目录改名放回原位（纯文件操作，不是现成命令）：

```sh
mv <tmp>/claude-code-a/skills/drama-studio            <tmp>/claude-code-a/skills/.drama-studio-upgraded-aside
mv <tmp>/claude-code-a/skills/.drama-studio-backup-*  <tmp>/claude-code-a/skills/drama-studio
python3 -B scripts/install.py verify --host claude-code --skills-dir <tmp>/claude-code-a/skills
```

恢复后 `verify` 返回 `ok: true`；因为恢复的是旧提交的内容，`matches_checkout: false`（如实反映"这是旧版本"，不是错误）。**通过，但明确是人工恢复，不是工具内建能力——README 也没有宣称有回滚命令，记录与描述一致。**

## 4. `package --host workbuddy`（AC-3）

```sh
python3 -B scripts/install.py package --host workbuddy --output <tmp>/package/drama-studio-workbuddy.zip
```

ZIP 含 54 个文件，与技能源目录 `skills/drama-studio/` 的清单一一对应（无额外文件）；解压后检查：

- 无 `projects/` 路径/条目。
- 全文搜索 `/Users/`：零命中。
- 全文搜索 `.env`：零命中。
- 全文搜索 `secret`（大小写不敏感）：零命中。
- 全文搜索 `token`（大小写不敏感）：7 处命中，逐一核对均为无害用法——教 AI "不要硬编码分享 token"、schema 里的 LLM 用量字段 `tokens`、代码注释里的"time tokens"（时间词法单元），没有一处是真实凭据或占位凭据。
- 文件名搜索 `*token*`/`*secret*`/`*.env*`：零命中。
- 再次以同一 `--output` 跑 `package`：返回 `action: "unchanged"`，不重复写入——与 README"输出已存在且内容不同时要求新路径，不静默覆盖"一致（内容相同时为幂等 no-op，行为比"拒绝覆盖"更友好，不矛盾）。

**通过，与 README 描述一致。**

## 结论

| AC | 状态 |
| --- | --- |
| AC-1 | 通过（四个 host 的全新安装与 verify，chatgpt 的"不支持本地安装"行为符合 README） |
| AC-2 | 通过（升级成功带备份 / 改过的安装被拒绝并说明原因 / 从备份人工回退后 verify 通过） |
| AC-3 | 通过（workbuddy ZIP 只含随包文件，`projects/`、`/Users/`、`.env`、`token`、`secret` 均无真实命中） |
| AC-4 | 测试 340/340 通过；`validate.py` 在当前会话里因无关并发 worktree 污染报错，经干净检出核实与本次交付内容无关（见第 1 节） |

未发现与 README/INSTALL.md 描述不符的行为。全部安装/升级/打包操作均在会话临时目录内完成，未写入或修改用户真实技能目录，未提交、未推送。
