# D4-2 并行写入冲突探测（#45）

2026-10-08。在 D2 试点项目（`c1c04a99f1ec4e4d8f963`）里专设的 slot `d4-conflict-probe` 上做，正文是标注“冲突探测”的短文本，不碰任何创作内容。

## 步骤与结果

| 步骤 | 请求 | expected_revision | 结果 | 本地回执 |
| --- | --- | --- | --- | --- |
| 基线 | `d4-probe-base-r1` | 0 | 200，r1（`b319115a…`） | `confirmed` |
| 运行 X（基于 r1） | `d4-probe-run-x` | 1 | 200，r2（`4468111d…`） | `confirmed` |
| 运行 Y（也基于 r1） | `d4-probe-run-y` | 1 | **409 `VERSION_CONFLICT`**，“Candidate slot revision is stale.”，`retryable: false` | `rejected_conflict` |

冲突之后重新列举 slot：服务端只有 r1 和 r2（运行 X），**没有运行 Y 的任何修订**，没有一方被静默覆盖。运行 Y 的正文留在本地（`responses/d4-probe/run-y.body.txt`），三次请求和响应、冲突后的列举都存在项目私有目录 `projects/zhenyuan-d2/responses/d4-probe/`，回执在 `.drama/receipts/d4-probe-*.json`。

## 结论

- 并行运行写同一 slot 时，后到者由 mali-story 的版本比较拒绝；本地只报告，不合并、不重试同一请求。
- 处理方式写进了 [recovery.md](../../skills/drama-studio/references/recovery.md)：收到 `VERSION_CONFLICT` 后重新读取 slot 的当前修订，由作者或主创决定是基于新修订重做，还是放弃；被拒的产物保留在本地供比对。
- D3 的分批是按因果依赖切的（每批 10 集，前一批保存后下一批才审读），没有出现两个运行写同一 slot 的情况；这次探测补上了“如果出现会怎样”的证据。
