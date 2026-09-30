# D0 基线回执（2026-09-29）

| 项 | 值 |
| --- | --- |
| drama-studio HEAD | `0e8b6be`，D0 开始前工作区 29 个已修改／未跟踪条目，`git diff` 摘要 `sha256:061d842e431bfe46…`（前 16 位） |
| mali-story HEAD | `a397db7e`；未跟踪：`.codex-tmp/`、`_doc/creative/huangquan-script/`、`_doc/creative/zhenyuan-rescue-2026-09-25/`、两个 `draft_*_folder/` |
| Python | 3.11.8 |
| 已安装技能 | Claude Code 用户级、Codex 用户级均未安装（`install.py verify --host claude-code` 返回未安装） |
| D0 前测试 | 50 项通过 |
| D0 后测试 | 72 项通过（新增 22 项契约测试） |
| D0 后 validate | ok；随包文件 35 个（新增 6 个 Schema、`contract_check.py`） |

## 保护范围

- 用户在 D0 前已有的未提交修改（README、SKILL.md、references 等）保留原样；D0 只在 README 与 SKILL.md 追加 `contract-check` 说明和工位入口行。
- mali-story 仓库只读，未修改任何文件。
- 私有剧本、《镇渊君》材料、视频与凭据不进入技能包；`validate.py` 继续拒绝随包出现 `/Users/` 路径，并新增“随包 JSON 必须是 Schema”检查。

本回执不是 R0 全部任务的完成证据；R0-02（能力矩阵）的联网部分随 D1 解除阻塞后补齐。
