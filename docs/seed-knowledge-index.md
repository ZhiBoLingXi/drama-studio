# 首轮种子知识索引（#7）

卡片正文与原证据都在项目私有目录 `projects/zhenyuan-d2/knowledge/`（不进仓库、不入包）。本页只列卡片 ID、类型、服务的首轮目标与工位，不含私有正文。

**状态：** 2026-10-06 由 Claude Code（`external_ai`）起草，`processing: pending`。材料取舍与使用权**待主创确认**；确认前不得当作已审定知识。

**校验：** `drama_tools.py knowledge validate projects/zhenyuan-d2` 退出码 0（6 张卡，逐卡 contract-check 与文件名一致性通过）；`knowledge show` 对每张卡都能定位到 `knowledge/sources/` 下的原证据文件。

## 卡片

| 卡片 ID | 类型 | 首轮目标 | 适用工位 | 证据性质 | 来源剧目 | 来源 ID | D2 可能装入的步骤 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `kc-zy-choice-from-knowing` | K2 | 人物行动 | C4、C5 | observation | 镇渊君 | `src-zy-ep40-44` | #8 C4 正式包 |
| `kc-zy-voice-by-listener` | K5 | 对白语感 | C5 | observation | 镇渊君 | `src-zy-ep40-44` | #9 C5 正式包 |
| `kc-zy-emotion-leaves-trace` | K3 | 情绪承接 | C4、C5 | observation | 镇渊君 | `src-zy-ep40-44` | #8 C4、#9 C5 正式包 |
| `kc-zy-entry-from-last-exit` | K4 | 集纲因果 | C3、C4 | observation | 镇渊君 | `src-zy-ep40-44`、`src-zy-rescue-report` | #8 C4 正式包 |
| `kc-zy-win-must-accumulate` | K8 | 结构重复 | C3、C4、C6 | source_statement | 镇渊君 | `src-zy-rescue-report` | #8 C4 正式包 |
| `kc-zy-cost-not-reset` | K9 | 情绪承接、结构重复 | C4、C5 | source_statement | 镇渊君 | `src-zy-rescue-report`、`src-zy-ep40-44` | #8 C4、#9 C5 正式包 |

五项首轮目标每项至少 1 张卡；C4 主要知识类型 K3、K4、K8、K9 与 C5 主要类型 K2、K5 均有覆盖。每张卡都写了反例与失效条件。

## 来源

| 来源 ID | 内容 | 权利与允许用途 |
| --- | --- | --- |
| `src-zy-ep40-44` | 第 40–44 集修订候选正文（与生产试点项目候选逐字一致） | 团队自有改稿；项目私有；creative_reference |
| `src-zy-rescue-report` | 2026-09-25 停产根因与修订说明（团队自有改稿记录） | 团队自有；项目私有；creative_reference |

## 缺口与限制

- **来源单一：** 6 张卡只来自 2 个来源，`knowledge search` 已标出同源。这不是多源互证，结论强度按单一来源看待。
- **防泄露：** 证据只取第 40–44 集与根因报告的方法部分。根因报告中引用的第 45 集以后的例子没有写进卡片内容（`limits.unverified` 已注明），以免知识条件比对照条件多知道后续情节。
- **未做：** 没有收集外部生活／职业材料（K1），也没有市场证据（K6）或制作经验（K7）；首轮目标不需要它们。
- **K8、K9 两张卡是团队判断**（`source_statement`），未经观众或制作数据验证。
