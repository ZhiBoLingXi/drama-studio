# C3c 季编排

[工位契约](workstations.md) · 契约 v0.1 · 方法见 [集纲层](outline-layer.md#8-季编排与容量两口径动作-rearrangesplitdrop_function删线不作默认数字不当裁判)

| 项 | 内容 |
| --- | --- |
| 必读本剧依据 | 功能地图（选定实现）、开播前底账（或最新底账修订）、媒介档案（`media-profile`）、约定集数与单集时长 |
| 主要知识 | K3、K4、K8；没有知识缺口时可以不检索 |
| 产出 | 季编排 `planning/season-plan.json`（schema `season-plan`）：每集分到的功能、事件粗列、★；每集容量粗估（`estimateSec` 对 `targetSec`）；超出的集写处理动作；埋设与回收位（`threads[]`）；登记的决定（`decisions[]`） |
| 交接 | `run-handoff`（`workstation: C3`，任务 `layer: C3c`，装包角色 `season_planner`）；分配时发现功能地图有缺口不自己加功能：同一工位内（C3）的变更交接写不了 `changeProposals`（只能指向本工位之前的工位），写进 `unfinished`，并用 `decision add planning/decisions.json --entry <条目文件>` 登记（`kind: upstream_change`，带默认），由编排方开一次 C3a 运行 |

## 方法要点

- 先把功能分到集，再算容量：`capacity season` 粗估（信息条数 × 同类处境语料交换中位时长 ＋ 画面拍），同时报两个口径（A、B，定义见 [季编排与容量](outline-layer.md#8-季编排与容量两口径动作-rearrangesplitdrop_function删线不作默认数字不当裁判)）；各入口的公式以 `capacity` 输出的 `formulas` 为准。画面拍时长没有实测时是假定值，粗估里这一项把握低，写明。
- 装不下时三选一，必须选一个，不登记「待定」：重排（`rearrange`，把功能挪到相邻集或拆给两集）、拆集（`split`，送审前自由；送审后（不论是否已批准）按下文登记）、删线（`drop_function`，写 `droppedCost`：哪条功能落空、后面哪集受影响）。系统的默认只在重排与拆集之间选；删线不作默认，只能作为决定队列里的选项（`decisionRef`）。送审前由本层选定并记进动作记录；送审后（不论是否已批准）再超，登记进决定队列、按默认先走，随下一次送审包一并复审，见 [保存与恢复](approval-flow.md#4-保存与恢复)；`drop_function` 不作默认，也不自动执行。
- 用户主动要拆某一集时，用户原话就是决定：用 `decision add planning/decisions.json --entry <条目文件>` 登记，`status: decided`，`humanWords` 写原话；编排方开一次 C3c 运行重排，再开 C4 写新集（见 [C4](workstation-c4-episode-outline.md#方法要点)）。
- 数字不当裁判：估时只触发「必须选一个动作」，不判这集不合格；选哪个由功能与人物决定（哪个功能这一集非完成不可、哪个可以等）。
- 删掉一段，后续是否仍原样发生？若是，判断它是有意停顿、关系积累，还是可替代的填充；填充段的功能挪给别集或合并，不拿事件去凑时长。
- 每个埋设登记回收位；回收前要有埋设。

## 停止与边界

不写一集内部怎么发生（C4），不改功能与实现（C3a）。放行条件：每集估时对目标的差记录在；超出的集有处理动作（不是「待定」）；每个埋设有回收位；登记的决定每条带 `default`。`season-plan-check` 只核记录与算术，不评编排好坏。
