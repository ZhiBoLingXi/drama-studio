# D6-1 开头的九项设计决定

依据：[统一实施计划](../design/drama-studio-outline-dialogue-implementation-plan-2026-10-14.md) §2.8（「在 D6-1 开头定，定之前不冻结对应的 schema；是设计上的取舍，不需要主创点头」）与 [D6-0 对照报告](d6-0-report.md)。日期 2026-10-15。主创当天的原话是「新流程做完再重做测试」：先做完技能改造，再用正式工具对项目重做验证。

| # | 要定的事 | 决定 | 理由 |
| --- | --- | --- | --- |
| 1 | 状态性断言（法律、人身、关系状态）放哪 | 时间线账加子型：`kind: timeline` ＋ `subtype: state`，字段 `stateOf`、`state`、`validFrom`、`validTo` | 不新增第七类账，九条底账规则与两轨不用改；D6-0 的临时做法已经放在时间线账里，迁移成本最低 |
| 2 | 追问单 v1 → v2 的题干 | D6-1 不改题干。问题单 schema 支持 `answerKind ∈ tristate / informational`，数据文件 v1 把第 14、15 问标 `informational`；两份问题单的第 16 问各写各的题干（D6-0 已是如此）。题干合并与补问在 D6-2 写 `references/outline-layer.md` 时一并定为 v2 | 题干改动要配新的真实作答才能评估，D6-1 没有新的作答；schema 先能装下 v2 |
| 3 | K1 卡的写法约定是否升为字段 | 升为 `knowledge-card` 的**可选**字段：卡级 `coverage ∈ sourced / partial / empty`；`content.rules[]` 每条带 `support ∈ sourced / inferred / not_found`；`evidence.sources[].sourceTier ∈ official / transcribed / superseded / commercial / news`；个案 `caseFacts`、`distanceFromOurs`。`contract-check` 规则：`coverage: empty` 的卡不得被回答记录当作 `holds` 的出处 | D6-0 的 60 张卡里有 5 张空卡、多张把推断与条文混写；可选字段不破坏既有卡 |
| 4 | 「用户给了大意、后来改了关键细节」的 `origin` | 两样都要：值域加 `user_given_modified`；功能地图的 `steps[]` 有自己的 `origin`，候选级 `origin` 取其中最「用户」的那个 | D6-0 两轮都遇到同一候选里既有圣经原样也有后来改动的步骤 |
| 5 | 各 schema 的必填项 | 以 D6-0 的真实产物作夹具反推：每个 schema 的必填项必须让对应的真实文件通过（真实文件只在本地验收脚本里用，不进仓库）；仓库里的例子与测试夹具用合成的中性内容 | 方案字段表照抄时第一份真实底账报了 108 条假阳性（修正点 #40） |
| 6 | 检索题目归并放哪 | 独立子命令 `function-map topics <function-map>`：从 `ledgerDeps` 里 `kind: procedure` 与 `assertion` 为 `required_unstated` 的断言归并出题目清单，带依赖它的功能与集 | 检索清单由断言生成、不由编排方预估（修正点 #34）；单独命令便于在追问前调用 |
| 7 | 「材料全程没写」类结论的证据 | 回答记录可选字段 `searchScope: {files[], method}`；`check-answers` 对 `defectKind` 含 `missing` 而没有 `searchScope` 的回答报出（只报不拦） | 让「没写」的把握可以事后复核；全自动的 S 检索需要事实索引，留到 D6-2 |
| 8 | `loadBearing` 的依据 | 枚举 `loadBearingBasis ∈ stated_in_record / has_downstream / function_sentence_step` ＋ 一句 `loadBearingWhy`，由核对方作答时填 | D6-0 事后推的三种依据，其中「落在可换实现上」口径太宽已被弃用（修正点 #51） |
| 9 | 承重缺口的去处记在哪 | 回答记录里的 `disposition`（`to ∈ confirmed_gone / license / decision / leaves_open`，加引用）是唯一来源；缺口登记表由命令 `defects build` 从回答记录生成，不手写 | 单一来源，避免登记表与回答记录漂移；D6-0 的登记表本来就是脚本合并出来的 |

这些决定会写进各 schema 的说明与 D6-2 的文档。若实现中发现某项走不通，在本页追加一行修订并写原因。

## 修订

| 日期 | 决定 | 修订 | 原因 |
| --- | --- | --- | --- |
| 2026-10-15 | #2 | 追问单 v2 题干不在 D6-2 定，推迟到「新流程做完后用正式工具重做项目验证」那一轮：用那一轮的真实作答比较 v1 与候选 v2，再定 v2 并改 `data/`。D6-2 的 `outline-layer.md` 以数据文件 v1 为准 | 题干改动要配新的真实作答才能评估（本决定原有的理由）；D6-2 的走通演示用的是编造材料，不能当评估依据 |
| 2026-10-15 | #7 | 「材料全程没写」的自动 S 检索同样推迟到那一轮之后；D6-2 仍只「报出缺 `searchScope`」 | 需要事实索引，D6-2 没有新增；先看重做验证里这类结论有多少、错多少 |
