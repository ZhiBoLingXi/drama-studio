# 分集写作、检查与修改

## 工位流程

写正文、续写下一批、查稿后改稿，默认都走这条流程，单集也一样。不能用“一次写完一批、再整体自检一遍”代替。对象格式与命令细节见 [工位契约](workstations.md)；一次要写多批（如“写第 31–80 集”）时，另按 [整季分批](workstation-season-run.md) 编排。开始前先按 [两次审批](approval-flow.md) 确认本次允许写到哪一集。

1. **项目目录**：已有项目先运行 `drama_tools.py status <项目>`，按输出第一行处理；没有项目就运行 `drama_tools.py init-project <项目> --title <剧名>`。用户给的集纲（用户集纲，作输入）、前文、设定（docx 等）转成文本放进项目的 `runs/input/`，不要只放在临时工作区。项目目录不能放在技能安装目录里。
2. **连接与上下文**：先发现当前会话里实际可用的 mali-story 工具。可用时，用 `get_writing_context` 读到 `nextOffset` 为 null 并记回执；要装进包里的前文页面用 `read_page` 读回，再用 `receipt cache` 存进本地缓存。mali-story 是正文的唯一存放处：没有 mali-story 工具或还没有远端项目时，先告诉用户并请用户配置连接或确认建项目，不自行改走离线。只有两种情况走下文 [离线与单代理降级](#离线与单代理降级)：项目从未绑定远端、用户明确同意这次只交本地草稿（把用户原话记进 `PROJECT.md`）；或已绑定远端、暂时断线（连上后补发）。离线也不跳过后面的步骤。
3. **C4 确认分集计划可写**：本集分集计划过了 `plan-check`（S），`capacity.status` 是 `fits` 或带默认的提案（S），`events` 单独读得懂、关键动作带动机与代价（M）；入口按前一集的实际正文（底账实际轨），不按前一集的计划（见 [集纲层](outline-layer.md#9-分集计划字段14-字段summary-可选) 与 [C4](workstation-c4-episode-outline.md)）。计划缺了承重的东西时提 C4 变更，不让正文去补这个空缺。
4. **C5a 对话表**：分集计划的 `capacity.status` 是 `fits`，或是带默认的提案时按默认走。项目第一次做 C5a 之前，先从随包例子 `examples/dialogue-target.json` 起步写好台词目标 `planning/dialogue-target.json`，之后只经 `feedback-ingest --target` 升版。先用 `drama_tools.py ledger knows <入口底账修订> --episode-plan <分集计划> > .drama/checks/knows-ep<NNN>.json` 存下场前谁知道什么，再装 `--role dialogue_designer` 包（分集计划、台词目标、这份 knows 导出；有语料时加 `--exemplars <标注交换文件> --annotations-only`，只装处境与结构说明，见 [样本怎么用](dialogue-structure.md#4-样本怎么用处境检索遮蔽每话题上限verbatimfrom)），写本集对话表 `planning/dialogue/dialogue-plan-<NNN>.json`：每场的话题，每个话题的处境与走法理由，每条信息由哪一来回承载，切换对象前的收尾（见 [对话表](dialogue-structure.md#3-对话表话题交换listenerknowscarriescloseroneitemperline)、[C5a](workstation-c5a-dialogue-plan.md)）。用 `dialogue-plan-check` 与 `contract-check dialogue-plan` 核。某条信息找不到对话对象时写 `changeProposals` 回 C4，带默认，不自己凑。用户给过前文、样集或改稿时，先做 [前文校核](dialogue-structure.md#10-前文校核)。
5. **C5b 装包写正文**：一集一个作者运行，不一次写完一批；前一集正文已保存（有 confirmed 回执，离线时 `not_sent` 回执已写）且入口状态记录已导出，才给下一集装包。作者包至少有：本集分集计划 `planning/episodes/episode-plan-<NNN>.json`、本集对话表（须过 `contract-check`）、台词目标、对话表引用过的正例、前一集已保存的正文原文、入口状态记录 `runs/state/after-ep-<NNN>.md`（`<NNN>` 是前一集；谁知道了什么、承诺与付款到哪一步、关键物件在谁手里、故事第几天；由底账实际轨导出。第 1 集用开播前底账 `ledger-ep000.json` 与 `ledger replay … --at 0 --track actual --md` 导出的 `after-ep-000.md`）。写好 `task`（`layer: C5b`，引用台词目标）和选材清单（selection），运行 `drama_tools.py context-pack <项目> --task <task.json> --selection <selection.json> --role author --budget <字数>` 生成快照，再照对话表写完整正文和对照表 `runs/<批>/ep-<NNN>.plan-text-map.json`（见 [写正文](dialogue-structure.md#5-写正文c5b照表写信息由对白承载重复须有处境理由)、[C5b](workstation-c5b-text.md)）。前文按原场面装，不能只装摘要；超出预算就缩小单元，不静默截断。写完必跑字面重合两档（13 字全库、8 字装包样本）与题材禁词扫描，然后按第 8 步把这一稿存为页面修订，C6 读的就是这份修订。
6. **C6 五读**（读第 5 步已保存的修订；见 [C6](workstation-c6-review.md)）：
   - 首读：按批做，一次不超过 `season-check --batch-size`（默认 10 集）；单集续写时就是本集。在没看过集纲和作者说明的新上下文里做（子代理、新会话，或宿主支持时另起的非交互进程），另装一个 `--role reader_effect` 包，只放观众能看到的正文（本批，加前一集；前一集已经精修过就装精修稿），不放集纲和作者说明。首读记录写完立即算 sha256 并记下，之后不再改动，这叫封存（算法见 [台词层](dialogue-structure.md#1-总览c5a-对话表--c5b-正文--c6-五读--先改表再改文)）。下面四读逐集做。
   - 次读：再装一个 `--role evaluation` 包，加入分集计划、对话表（全稿改稿时是改稿单）、台词目标与入口状态记录，核对目标和事实。次读的结论另写，不回头改首读记录。
   - 冷读复述：新上下文里装 `--role cold_reader` 包，只放本集正文，复述谁做了什么、为什么、每条信息从哪句知道；`retell-check <复述> --plan <对话表> --episode-plan <分集计划>` 对照信息清单（见 [冷读复述与处境对照](dialogue-structure.md#6-冷读复述与处境对照对话问题单)）。
   - 处境对照：新上下文里装 `--role situation_checker` 包，按对话问题单对每个话题逐问作答，引句子、写原因；`check-answers` 核格式。
   - 设计依据一致性：`plan-text-consistency` 核说话人序列与话题边界，再逐话题看正文走法对不对得上对话表的理由（见 [一致性与诊断](dialogue-structure.md#7-设计依据一致性与诊断信号数字只诊断不裁判)）。
   - 审读记录按 `review-record` 写，放 `.drama/reviews/`：问题分事实、目标、偏好三类，每条标明该回到哪个运行层；次读的 finding 带 `cites`，没有可引的归偏好。
7. **先改表再改文**：属于本层的问题，单独装包修订：处境或理由写错了先出对话表新修订再改正文，没照表写就只改正文；修订单只引用对话表元素与审读记录里的句子和原因，不写替换台词、不写数值指令（见 [修订](dialogue-structure.md#8-修订先改表再改文修订单不写替换文字不写数值修订后复读)）。修订者是原 C5a／C5b 作者或同一角色。修订稿按第 8 步存为新的页面修订，再做一次冷读复述与处境对照。修订次数不超过修订预算（`task.revisionBudget`，默认为 1）；用完之后怎么办见 [修订预算按运行层解释](workstations.md#修订预算按运行层解释)。C5b 发现是对话表的问题（同一工位内的上游），写进交接的 `unfinished`，用 `drama_tools.py decision add planning/decisions.json --entry <条目>` 登记（`kind: upstream_change`，带默认），由编排方开一次 C5a 运行；属于分集计划或更上层的问题（跨工位）写进 `run-handoff` 的 `changeProposals`（带默认走法），用 `drama_tools.py decision add planning/decisions.json --from-handoff <交接>` 登记。流程都按默认继续，不在正文里悄悄改上游。
8. **保存为页面修订**（每一稿都存：第 5 步的初稿一次，第 7 步的每次修订各一次）：先确认要保存的正文与本地稿逐字一致，再用 `create_page` 或 `update_page` 保存，`receipt record` 记回执，`read_page` 读回比对指纹后执行 `receipt cache`（见 [页面读写](mali-story.md#页面读写版本标签与恢复)）。用户确认后才用 `label_page_revision` 打标签；标签不等于制作采用。离线时回执记为 `not_sent`。
9. **交接与状态**：把 `run-handoff` 写到 `.drama/runs/<runId>.json`，填写 `finishedAt`、快照 ID、产出、状态变化提案（带 `ledgerDelta`，进底账实际轨 `planning/ledger/delta-ep<NNN>.actual.json`）和 `nextAction`；`host.usage` 按本次实测填，没实测就写 `{"source": "unknown"}`，不从别的运行抄。下一集的入口状态记录 `runs/state/after-ep-<NNN>.md`（本集集号）用 `drama_tools.py ledger replay planning/ledger/ledger-ep000.json --delta planning/ledger --at <本集> --track actual --md` 从实际轨导出，不手写；下一集 C5a 用的入口底账修订，用同一命令把 `--md` 换成 `--out planning/ledger/ledger-ep<NNN>.actual.json` 写出。用 `contract-check` 校验 `task`、`selection`、`dialogue-plan`、`plan-text-map`、`retell-record`、`review-record`、`revision-list`、`run-handoff`、`remote-receipt`。本集已保存、入口状态记录已导出，才给下一集装包。
10. **关口**：每批结束和交付前运行 `drama_tools.py season-check <项目> --episodes <起-止>`（项目从未绑定远端、用户同意只交本地稿时加 `--allow-offline`），写了或改了集纲时加 `--outline <起-止>`；对已有全稿做反馈改稿时加 `--revise`，同一项目改过几版时加 `--since <本版开始时间>`；复查没有对话表的旧记录时加 `--legacy-dialogue`。把结论原样写进交付说明。不通过的集，补齐证据或重做之前不能写“已按流程完成”。

`dup-check` 两档与 `corpus lexicon` 每集必跑（第 5 步，启用台词层后是 `season-check` 的必过规则）；`episode-check`、`capacity text` 按需，见下文 [检查](#检查)。快照 ID、首读 sha256、对话表、审读与核对记录、回执和交接都要留在项目里，换会话时靠它们接续。没做的步骤如实写“未执行”及原因。

## 离线与单代理降级

离线只有两种情况，处理不同：

- 项目从未绑定远端、用户明确同意只交本地稿：保存记 `not_sent`，关口加 `season-check --allow-offline`（`not_sent` 降为警告）。
- 已绑定远端、暂时断线：可以继续写，保存记 `not_sent`，连上后用新的 requestId 补发；补发之前关口按失败算，`--allow-offline` 对已绑定的项目不放行，这是有意的。

没有工具、也没有远端项目时，先问用户（上文第 2 步）。宿主不能开子代理时，流程也照常走，只替换做不到的那一步。装包和五读都不能省。

**没有 mali-story 连接**

- 材料必须是项目里的文件。`context-pack` 的 `local_file` 只读项目 `.drama/`（不含 `.drama/cache/`）、`runs/` 或 `planning/` 下的相对路径；`episodes/` 下的文件、绝对路径、`..` 都会被拒绝。集纲层的功能地图、底账、季编排与分集计划直接从 `planning/` 装。可以这样放：输入 `runs/input/outline-031.md`、`runs/input/ep-030.md`，本批稿件 `runs/b04/ep-031.c5b.md`，修订稿 `runs/b04/ep-031.c5b.r1.md`，审读记录 `.drama/reviews/rev-b04-1.json`。顶层 `reviews/` 只放给人看的阅读记录。交付时再整理到 `episodes/`。
- 选材写 `{"kind": "local_file", "id": "runs/input/ep-030.md", "revision": null}`，工具会把实际 sha256 写进快照。selection 的 `sourceSnapshotId` 和 task 的 `project.remoteProjectId` 都填 null。
- 回执：在本该写页面的地方，先把准备发送的完整输入存成文件（如 `runs/b04/ep-031.create.input.json`），再手写一份回执 `.drama/receipts/<requestId>.json`，文件名必须与 `requestId` 一致。字段这样填：
  - `operation` 写本该调用的操作，如 `create_page`；
  - `requestId` 建议带 `.offline` 后缀，如 `ep031-c5-create-1.offline`；
  - `outcome` 写 `"not_sent"`；
  - `remote` 里的 `projectId`、`pageId`、`revision`、`inputSnapshotId` 全写 null；
  - `inputFingerprint` 写输入文件的 `sha256:<hex>`（如 `shasum -a 256` 的结果），它只作本地标识；
  - `localRef` 指向本地稿；
  - `evidence` 写“宿主没有 mali-story 连接；本地草稿，未写入 mali-story”。

  写完运行 `drama_tools.py contract-check remote-receipt <回执文件>` 校验。`receipt record` 生成不了这种回执：它读的是服务端响应，缺少响应时会记成 `unknown`，意思是结果未知、需要对账，与“未发送”不是一回事。
- 交付说明和回复里写“本地草稿，未写入 mali-story”，不写“已保存”或“已同步”。以后连上了，用新的 requestId 实际写入并照常记回执，不复用 `.offline` 的 ID。补发前先读回远端当前修订：远端没有新修订、补发内容与离线稿 sha256 相同时，已做过的 C6 记录照旧有效，不重做；远端已有别人的新修订时，按 `VERSION_CONFLICT` 处理（[页面读写](mali-story.md#页面读写版本标签与恢复)）。

**不能开子代理**

- C6 照样分开装包：先只读 `reader_effect` 包写首读记录，算 sha256 封存，然后再装次读、冷读、处境对照的包。
- 同一会话的作者已经读过集纲和全文，所以 `review-record.context` 写 `serial_self_review`，`claimsIndependence` 不能为 true（`contract-check` 会拒绝），`firstReadWithoutAuthorNotes` 也只能填 false，这样 `season-check` 会判这一集没有首读。
- 要有真正的首读，就另起一个没看过集纲的上下文：宿主支持时另起非交互进程，只给它 `reader_effect` 包和首读要求；或请用户在新会话里做首读，把记录交回来。这时 `context` 记 `independent`，`firstReadWithoutAuthorNotes` 记 true，交付说明里注明首读者是同一模型家族的新上下文。
- 冷读复述与处境对照同理：同一会话读过对话表和集纲的作者做不了冷读，要另起没看过这些的上下文；做不到就在记录里如实写，`season-check` 会照记录判。
- 没有子代理不是省掉首读、冷读的理由，也不能把整批写完后一次自评充当五读。

**篇幅与时长**

篇幅用容量算术管，不用字数配额管：季编排粗估、分集计划复核、正文精估是 `capacity` 的三个入口，用同一套两口径定义，各自的公式见输出的 `formulas`；`capacity text <正文>` 两口径并报，不判定、退出码 0。估时超出目标时写容量提案、带默认，流程按默认继续；装不下时不压台词，回 C4 或季编排拆集、挪事件（见 [集纲层](outline-layer.md#8-季编排与容量两口径动作-rearrangesplitdrop_function删线不作默认数字不当裁判)）。不给作者下「少多少字」「不超过几行」这类指令，`contract-check task` 会拒绝。项目另有明确制作规格时，`episode-check <文件> --config <规则文件>` 只核已配置的项；默认只做统计，`passed: null` 不代表达标。

## 类型承诺与信息推进

先明确观众等待什么，再审每集新增的体验。悬疑允许观众比人物先知道，但连续几场只确认同一答案时，应发展新选择、证据争夺或后果，不藏掉公平线索硬造意外。爱情中边界清晰不等于有吸引力，检查双方主动靠近和可能失去的东西。逆袭中的合同、证据、支付必须改变权力与处境，后半剧不能只是重复对账。这些是按实际题材选择的审读问题，不是固定公式。

低成本不要求所有故事都写小店、纸张和谈规则。物件须改变行动与关系；保留类型所需的喜悦、欲望、危险和冲突，不将不同题材统一写成说明边界后达成共识。

连续性审读包括相对时间和物件物理状态：把“昨天／明早”对应到故事日；区分正反面、胶带内外面、原件／副本、谁何时取得。引用前后动作并找反证，省略不自动算错。依赖镜面、声音识别等实物条件的解法仍标待验证，文字审读不冒充实拍。奇幻、悬疑等依赖机关或能力解题时，回查条件出现、可见受损、实际使用和代价持续；结尾用到的裂痕不能只在结尾被追认为早已存在。未解释的边界先区分未知与实际矛盾，不为回答所有设定问题堆砌说明。

## 写前

先按 [两次审批](approval-flow.md) 核对本次写作范围：选题确认后可依据当前送审版集纲／设定写前 10 集；送审包审批通过后，才依据获批版本续写剩余正文。读取相应分集计划、设定、与本集相关的有效前文、道具和知识状态，装进 C5a、C5b 的包。已有正文与集纲冲突时列出冲突及影响，按用户决定处理，不默默以其中一份覆盖另一份。

读取当前开发记录中的创作立场、需要保留的动作／人物棱角和取材未知项。只读取当前获选的故事方案，不把其他方案的优势自动拼进正文。仍在探索阶段时按 [创作开发](development-lab.md) 先试场面，片段不得替代完整稿或进入正式连续性。

人物、对白或情绪是本轮重点时，按 [人物与情绪改稿](character-emotion.md) 从有效前文恢复人物在压力下的惯用办法与声音，明确反馈对应的场面目标。先写人物如何尝试、受阻和选择，再写台词；跨批次带入尚未解决的关系后果，不只带入道具与伤势。

每个批次默认不超过 10 集，用户指定了就用用户的值；怎样按因果分批、批与批之间怎样交接，见 [整季分批](workstation-season-run.md)。批次大小只是组织方式，不改变审批范围，也不改变每集都要装包、五读、记回执的要求。前 10 集与剧情框架、人物小传、完整集纲一并送审；写完或模型自检通过都不等于用户审批通过。

## 正文格式与画面

兼容现有检查工具的最小格式：

```text
# 第1集：封住的门
场1-1 修理间 夜 内
人物：许禾、店主
△许禾站在门左侧，手中的断锁压在账本上。店主挡住门口。
许禾（按住账本，压低声音）：你说没收过钱，那这笔是谁签的？
店主（瞥向门外）：先把门关上。
```

写能拍到的动作、空间和反应，角色首次出现给出清晰视觉信息。AIGC 稿中交代站位、光线、关键道具及能力的可视变化，对白括注用于表达可执行情绪／动作。避免比喻代替画面；高燃题材可以写得夸张，但夸张要落在拍得到的规模、速度和反应上。信息由对白承载；谁知道什么由对话表的 `listenerKnows` 定；同一条信息重说要有处境上的理由。

措辞和画面按题材的语体档写：人物语言指纹、反派筹码、台词当证物、一集内埋了就响、场尾钩与高潮递进、△ 行写成分镜，见 [语体与台词质感](voice-register.md)。

字数、场数、场景地点与括注密度按单集时长、真人／漫剧和项目明确配置的规格定，不为凑数切碎场景。用户明确给的制作约束（预算、特效、场景数、演员等）必须遵守：写进任务的 `constraints[]`（`origin: user`），用户原话记进 `PROJECT.md`；C4 排场时就要守（集纲侧审读核，M）；正文里能计数的配进 `episode-check --config`（每集场数上限是 `max_scenes`），不能计数的由次读核对（M）；用户没写下的，不由模型自行加限，不为好做而删场面、降规模。每集应改变处境，主角有行动及后果；不同品类按相应情绪兑现检查。

## 检查

客观检查、C6 审读、人审采用分别报告，互相不能代替。

`episode-check` 默认只报告统计，未配置规格时输出 `constraint_status: not_configured`、`passed: null`。不能要求所有项目达到固定字数、场数或括注密度，也不能以统计执行成功宣布稿件质量通过。

项目已明确制作规格时，用 `--config` 指定记录来源的规则文件，或使用显式命令选项；只核对已配置规则，报告实际值、要求和来源。未配置标准时仍可继续有证据的创作审读。格式错误、空正文、重复集号先修复；格式不完整导致的计数缺口标为无法核验。

历史 AIGC 数值只保留为显式选择的 `--preset legacy-aigc` 示例，不自动套用。说话人交替次数不等于冲突回合；地点标签不等于物理拍摄场地；不通过关键词判断钩子。详细规则与输出见 [剧集检查](episode-check.md)。

`dup-check` 统计汉字连续片段与所给参考语料的重合；默认 5／8／13 字，13 字低于 40% 只是历史字面阈值。输入不足、缺失语料或脚本不可用不能报 0% 通过。另做六维语义检查，不能给出原创认证。

C6 次读引用实际集／场／台词，分别判断事实/约束问题、本轮创作目标缺口和开放偏好：包括钩子与情绪兑现、人物动机与声音、反派策略、前文连续性、六维差异化、语体档与人物语言指纹、空间与画面是否写清（写清不等于写小；用户没给的制作约束不记 finding）。有理由但缺少心理过程、说明完整却没有对抗等创作缺陷可以要求返修，不必先证明为逻辑硬错；也不把安静、直说或不讨喜自动判错。用户要求自主优化时，按 [自主创作迭代](creative-loop.md) 保留基线、比较候选并独立复核。调用额外付费服务仍遵守用户已授权范围。

修订先改对话表再改正文（第 7 步），修订后复核修订全文，不只看改过的句子；修订预算用完后怎么办见 [修订预算按运行层解释](workstations.md#修订预算按运行层解释)，不无限重写。

按 [交稿检查](delivery-readiness.md) 对真实产物做结果验收：角色行为有无动机、跨集是否承接、专业动作能否执行、用户是否能接手改稿。尤其检查“所有数值满足但故事不成立”的情况；没有真人意见时只能形成待审稿。

## 反馈修订

按用户已授权的自主范围采纳经核实的意见；内部候选修订不要求用户逐条批准。超出范围或改变已确认核心方向的意见保留为备选，不覆盖当前正文修订。先对比当前修订和反馈引用的修订；前文改变后检查后续依赖。附位置、修改前后、原因和影响范围。未受影响部分保留；对旧输入产生的检查结果标为过期。反馈修订同样按 [工位流程](#工位流程) 装包、审读、保存并记回执；前文出了新修订后，用 `drama_tools.py impact` 找出受影响的快照和运行。
