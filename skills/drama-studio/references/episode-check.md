# 剧集统计与项目规格核对

此工具读取约定格式的剧本文本，统计数量，并核对显式制作规格。它不判断冲突强度、悬念效果、情绪兑现或稿件采用。创作评审需另行引用正文完成。

## 默认统计

`episode-check 剧本.md` 不启用任何质量阈值。结构可读时输出 `mode: measurements`、`constraint_status: not_configured`、`passed: null`、`review_status: not_run`。

输入必须有 `# 第X集` 标题；同义集号（例如第一集／第01集）、空正文会报错。场标题、人物清单、自检块不算正文。正文汉字数包含台词中的角色名和括注，不是对白字数或时长估算。格式示例见 [写作指南](writing.md)。

场标题数、动作行数、台词行数和括注率只是文本统计。说话人交替在每个场标题处重新计数，不称为冲突回合；地点按完整标签去重，不自动合并子场景，不声称等于物理场地数。动作行／台词行比可大于 1；无台词时两个比例为 null，不能当作 0。比例比较用未舍入数值。

未识别的场标题或正文会附警告。格式依赖的统计不完整时，相关约束标为 `not_evaluable`，不以较低计数证明满足预算。即使格式完整，物理场地预算仍需核对实际场地清单。

## 显式项目规格

编剧／制片已给出要求时，AI 可以整理为项目目录中的 JSON；不要求编剧手写。每个文件必须记录规格来源，例如“制作 Brief 第 3 版”。本工具不验证该来源是否已获批准，宿主应先核对实际约定。

```json
{
  "schemaVersion": 1,
  "source": "制作 Brief 第 3 版：每集最多两个地点标签",
  "constraints": {
    "max_locations": 2
  }
}
```

执行 `episode-check 剧本.md --config 项目规格.json`。支持的键为 `min_chars`、`min_scenes`、`min_speaker_changes`、`min_delta_ratio`、`max_locations`、`min_paren_ratio`。只配置项目确实有要求的项；空 constraints 仍表示未配置。未知键、非法数值、缺失来源或文件读取失败均报错，不能静默退回默认值。

临时明确要求可用 `--min-chars`、`--min-scenes`、`--min-speaker-changes`、`--min-delta-ratio`、`--max-locations`、`--min-paren-ratio`。只传一个选项只核对一条规则。旧 `--min-rounds` 作为弃用别名保留并警告，不能与新名称同时使用。

历史预设 `--preset legacy-aigc` 显式启用六项旧规则：1200 汉字、10 场标题、6 次说话人交替、动作／台词行比 0.2、最多 3 个地点标签、括注率 0.6。它仅供复用旧规格，不是推荐的默认配置。

合并优先级：显式命令参数 > 项目配置 > 显式预设。只有指定预设才有预设值；配置未列出的规则保持原状，若不需要历史规则则不要选择预设。报告记录每条最终规则的来源、实际值与要求。不要为了让结果变绿而擅自降低要求。

## 输出契约与升级

当前输出 `schema_version: 2`，`ok` 只表示本次解析与核对成功执行。

| constraint_status | passed | 退出码 | 含义 |
| --- | --- | --- | --- |
| not_configured | null | 0 | 已统计，尚未配置验收标准 |
| met | true | 0 | 所有显式数值约束满足，创作质量仍未评审 |
| unmet | false | 2 | 至少一个显式约束不满足 |
| not_evaluable | null | 2 | 没有已知不满足项，但至少一项因数据不足无法核验 |

输入或执行错误为 `ok: false`、退出码 1。当不满足项与无法核验项同时存在，总状态为 unmet；调用方还需检查每集 checks 的逐项状态。每个 check 包含规则名、指标、方向、实际值、要求、来源及状态。

相较 0.1.0：移除默认硬阈值；`rounds` 改为 `speaker_changes`；移除 `ending_hook`、隐式 SLOT 次数政策、`fails` 与“全部过闸”结论；用 `checks` 逐项记录规格偏差。`thresholds` 仅包含显式生效规则。旧调用方必须允许 `passed` 为 null，不能将退出码 0 或 `ok: true` 解读为质量通过。
