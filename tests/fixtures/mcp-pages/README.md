# 真实页面响应夹具（mali-story v0.20.0）

2026-10-08 在 D2 试点测试项目上实测：create → update → 过期 update（409）→ 分块 read → create 重放 → label → restore → list。`submittedBy` 已脱敏。中途 label、restore 各断线一次：label 重试后 `previousLabel` 为 null，说明第一次没落地；restore 先列举确认未落地，再用同一 request_id 重发成功。

注意：409 等错误响应是裸的 `{status, headers, body}`，没有 `mali-tool-result/v1` 包装。
