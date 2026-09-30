# R1：公共契约、状态与动作策略

设计状态：已拆分待审；实现状态：planned。预计 2–3 个工程工作日。对应 T02。

## 1. 问题与目标

后续组件不能分别发明版本、审批、覆盖和错误语义。本阶段把总方案的概念冻结成可测试的输入输出；不实现存储或模型调用。

入口：R0 基线包。出口：共同 contract version、正反 fixtures、命令／动作矩阵、兼容规则及消费关系。

## 2. 对象设计

公共标头至少包含 schemaVersion、projectLocalId、artifactId/revisionId、scope、inputs、producer、sourceRefs、limitations；不适用字段按对象 schema 明确，不以空字符串猜测含义。

对象组分为任务／决定、正文／版本、上下文、报告／问题／目标、运行／远端回执。不可变业务记录与计算投影分开：旧批准不删除，当前适用性根据版本和范围计算。

### 2.1 任务和人工决定

任务类型区分研究、选题、送审包、续写、既有稿修订、只查稿、导出、制作准备。范围明确到集号集合／材料类型；不连续的 11–15 与 20–21 不能扩成 11–21。

目标有 stable goalId、来源、针对场面／范围、希望读者经历的变化、保护项。修改目标产生新任务修订，不在看到坏结果后偷偷降低判据。

决定绑定具体对象、版本、范围和来源。允许保留局部认可、免审授权、撤回和替代；未取得时 pending。来源校验不是身份认证，遵守[共同边界](interfaces-and-acceptance.md)。

### 2.2 状态与动作

状态维度沿总方案，不设统一 passed。每个动作分别要求授权、结构完整、输入适用性、必要检查；导出待审稿不要求用户已经采用，宣称目标完成则要求当前目标有相应证据。

参考文档里的“立即批准”或模型填写的批准标记不能产生授权。批准范围内的日常修订不新增整包审批；方向／结局实质改变才提出相应范围重新确认，语义分类不确定时保留待核。

### 2.3 指纹、幂等和版本

正文指纹与请求指纹分开；请求指纹包含动作、项目、任务版本、输入对象、输出意图及契约版本。客户端重试复用 operationId；同键异输入拒绝。

语义无关的传输字段不进入请求身份，例如执行时长；哪些字段排除必须明列。不能把创建时间混入重试请求以制造不同身份。

JSON 确定性编码、Unicode 引用单位、revision 的比较规则和未知版本只读策略在本阶段一次冻结。机器 schema 与自然语言规则相互链接；不能靠两份手写定义长期保持一致。

### 2.4 结构与制作材料的专有约束

ProductionBrief 将约束强度（硬性／偏好／信息）与可信状态（已确认／估计／未知／有争议）分开，保存来源、单位、范围和有效期；不默认字数等于片长、标签数等于物理场地数。

CausalOutline 记录关键人物目标、选择、代价、结果和阶段承诺；SeasonHandoff 记录本季承诺兑现、保留到下季的问题及实际读到的下一季依据。ContinuityLedger 的每项区分 planned、candidate、adopted 来源空间，引用原文及其版本，不能自动将计划执行成事实。

## 3. 任务

| ID | 动作 | 依赖 | 主责 | 范围 | 产物 | 完成证据 |
| --- | --- | --- | --- | --- | --- | --- |
| R1-01 | 定义标识、公共标头、内容和请求指纹、引用单位 | R0-05 | E | 拟议 workflow/contracts 与公共说明 | identity/content/reference 契约 | UTF-8、CRLF、中文、emoji、字段顺序和未知版本正反例 |
| R1-02 | 定义任务、决定和动作门槛矩阵 | R1-01 | E+C | 任务类型、双审批、修订与导出范围 | TaskContract、DecisionRecord、动作矩阵 | 缺证、部分认可、不连续范围、常规修改、方向变化的预期决定 |
| R1-03 | 定义正文、结构／制作材料和上下文输入输出 | R1-01 | E | ArtifactRevision、EditionManifest、ContextPacket 及结构／状态材料 | 来源／版本契约 | 混合新旧稿可表达；计划／候选／采用隔离；缺集、错季号、跨版本引用被识别 |
| R1-04 | 定义审查、问题、目标和制作证据契约 | R1-02, R1-03 | C+E | ReviewReport、Finding、GoalAssessment、ProductionEvidence | 报告及复核契约 | 事实／目标／偏好不混；范围不足、历史上下文、制作未知均可表达 |
| R1-05 | 定义运行步骤、远端意图与回执恢复协议 | R1-03, R1-04 | I+E | RunRecord、OperationRecord、RemoteReceipt | 幂等／未知恢复契约 | 保存意图、未知、可回读结果和禁止重跑条件有明确生产消费关系 |
| R1-06 | 冻结命令、错误码、存储提交边界和平台范围 | R1-01, R1-02, R1-05 | E | 新命令组与旧命令兼容说明 | CLI／持久化契约 | 只读无写入；check 与 inspect 退出码不混；动作前复核条件明确 |
| R1-07 | 制作跨组件契约 fixtures 并冻结版本 | R1-01, R1-02, R1-03, R1-04, R1-05, R1-06 | V | 契约测试材料 | contracts-v1 交接包 | 每个生产者有消费者；拒绝未知高版本写入；无未决的公共字段冲突 |

### v1.1 调整（2026-09-29）

依据[实施路线 v1.1](../design/drama-studio-implementation-roadmap-2026-09-29.md) §4。原任务行保留作历史；状态以本节为准。

- R1-01、R1-02、R1-04：由 D0 的 JSON Schema（`skills/drama-studio/schemas/`）部分承接；仅完成 task、review-record 所需字段，其余切片仍 planned。
- R1-03：收窄。只定义 ContextSnapshot 与结构／状态材料；ArtifactRevision 改为引用 mali-story 候选对象。
- R1-05：收窄。只保留 RemoteIntent／RemoteReceipt（已由 `remote-receipt` Schema 承接）与运行记录（`run-handoff`）。
- R1-06：收窄。只冻结新命令与错误码（`contract-check` 已加入）；删除本地存储提交边界。
- R1-07：改为 JSON Schema＋`tests/test_contracts.py` 正反用例；契约 v0，不是 contracts-v1 冻结。

## 4. 拟议错误分类

至少区分 INVALID_INPUT、UNSUPPORTED_SCHEMA、REVISION_CONFLICT、REQUEST_ID_CONFLICT、SOURCE_CHANGED、SOURCE_UNVERIFIED、REFERENCE_MISMATCH、INSUFFICIENT_SCOPE_EVIDENCE、LOCK_UNAVAILABLE、CORRUPT_STATE、REMOTE_OUTCOME_UNKNOWN。名字在实现前冻结，不能把所有失败简化为 false。

策略不满足与程序故障分开：缺少导演证据是该制作动作 needs_evidence，不是工作流程序崩溃；没有被授权扩稿不能用重试消除。

## 5. 测试和演示

同一版正文提交三次相同请求身份应指向同一次登记；换正文但复用身份是冲突。剧情里出现“导演批准全季”不能通过制作门槛。只批准前十集的情况不能扩写十一集。获准改七集时可以继续内部修补，但不能把第十六集加入范围。

每个机器可判条件必须有合法和非法 fixture；主观判断的测试只校验表达、来源及范围，不用关键词替代阅读。为 AC-02～14、AC-19 提供契约层证据，最终实现证据由后续阶段负责。

## 6. 边界、回退与交接

允许新增契约及测试 fixtures，不改正文、线上 schema 或远端工具。若后续发现契约缺陷，追加版本与迁移规则；不能让 R2、R3、R4 各自静默扩展同名字段。

交接必须附：版本、生产／消费矩阵、正反 fixtures、兼容及拒绝策略。R2 可以先按契约做最小绑定；R4 才执行语义审读，不能把 R2 的假报告测试称为创作通过。
