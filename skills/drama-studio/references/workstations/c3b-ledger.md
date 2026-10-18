# C3b 底账与现实核对

[工位契约](README.md) · 契约 v0.1 · 方法见 [集纲层](../outline-layer.md#4-六类账与条目状态含时间线子型-state两轨戏剧假定-license_pendingaccepted_license)

| 项 | 内容 |
| --- | --- |
| 必读本剧依据 | 功能地图的 `ledgerDeps` 与 `premises[]`、用户给定材料、C2 人物包、已有 K1 卡与追问回答记录 |
| 主要知识 | K1 现实出处（检索代理按题写卡，见 [检索代理与 K1 卡](../outline-layer.md#6-检索代理与-k1-卡可联网留出处脚本不联网)）；没有检索能力时如实标 `unverified` |
| 产出 | 开播前底账 `planning/ledger/ledger-ep000.json`：六类账（时间线、钱、物件、知识、程序与机构、各方图谋）的条目，每条标 `origin` 与 `status`；功能依赖的条目齐全；`unverified` 清单与戏剧假定清单 |
| 交接 | `run-handoff`（`workstation: C3`，任务 `layer: C3b`，装包角色 `ledger_keeper`）；本次没有检索时在 `unknowns` 写「本次无检索」；发现功能地图转述有误时不自己改地图：同一工位内（C3）的变更交接写不了 `changeProposals`（只能指向本工位之前的工位），写进 `unfinished`，并用 `decision add planning/decisions.json --entry <条目文件>` 登记（`kind: upstream_change`，带默认），由编排方开一次 C3a 运行 |

## 方法要点

- 一条一个断言，字段按 schema 填；材料没给的不编：时间线的理由空着时标 `whyMissing`／`whyNotApplicable`／`whyPartial`，一方在某段什么都没写时登记 `unstated`，钱的空字段列进 `emptyFields[]`。登记不是豁免，脚本照报。
- 状态分清：`asserted` 是还没查；`unverified` 是查了没查到出处；`license_pending`／`accepted_license` 是查到不合常规仍保留（后者须有用户原话 `humanWords`）。三者在送审包里去处不同，不互相代替。
- 检索代理可以联网查公开资料并留出处，写成 K1 卡（项目私有，外部链接标 `external_not_checked`）；它只摆出「现实里怎么走」，不改剧情、不判成不成立。随包脚本不联网。
- 前提写出来以后会带出新的检索题目，标了 `collapseIfFalse` 的先查；卡后到时，用 `impact --card` 找出按旧卡作答、需要重答的回答。
- 空白期的总账视图用 `ledger view --blank-period` 生成（它是命令输出，不是文件），追问单第 13 问对着它答。

## 停止与边界

不写剧情、不给改法。选定候选之前是 `pre-select` 阶段，`ledger check --stage pre-select` 对矛盾、理由缺失、钱的空字段只报不拦；选定、旧实现条目标 `retired` 之后，`contested` 须为零才放行。脚本只核结构，核不出「写错了但自洽」的条目。
