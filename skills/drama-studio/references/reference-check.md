# 拉片资料覆盖检查

AI 将实际读取的 mali-story 模板详情保存为 JSON，用户不需要手工整理。支持详情对象或 `mali-tool-result/v1` 结构化结果，要求包含 `template` 和 `content.episodeOutlines`。列表行或任务回执不足以检查覆盖。

```sh
python3 scripts/drama_tools.py reference-check /absolute/path/to/template-detail.json
```

默认使用 `template.episodesTotal`，不硬编码剧集数。已确认其他范围时加 `--expected-episodes N`，不为消除问题而降低 N。报告列出缺行、缺集纲／原始分析、重复／越界集号、`hasOutline` 与正文冲突、可识别的 `episodesTotal:` 汇总计数矛盾，并附输入 SHA-256 和模板版本。

- 退出码 0：`coverage_status: consistent_present`，所检查字段存在且声明一致。
- 退出码 2：`coverage_status: needs_review`，按集读取证据核实并保留问题。
- 退出码 1：输入或执行错误，不能推出资料完整或缺失。

`passed` 始终为 null。非空文本仍可能截断、误识别或与原片不符；工具不检查角色语义、时间码真伪、原创性或质量。五集模板字段齐全也不证明原剧只有五集，另核对源剧版本与总集数。

摘要与逐集证据冲突时整理独立研究笔记，不修改远端模板来消除警告。只研究开场时可以用明确标注的片段，完整走势研究需要对应覆盖。模型说明资料是否足以支持本次目标。
