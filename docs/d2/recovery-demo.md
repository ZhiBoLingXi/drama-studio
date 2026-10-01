# D2 恢复与失效演示记录（合成夹具）

**本记录用的是合成夹具（`tests/fixtures/mcp-synthetic/`），不是 #9 的真实产物。** 夹具是按 mali-story 源码手写的 MCP 响应，没有连接 mali-story，没有调用模型，也没有真人创作内容。
用 #9 真实产物重做这次演示的部分待 #9 完成后补录，见文末“待 #9 真实产物补录”。在那之前 #10 的 AC-6 不勾选，issue 保持打开。

记录日期：2026-10-01。工具代码：分支 `feat/status-impact-commands` 的提交 `ae3440b`（`status` 加入失效提示之后重跑了全部步骤）。Python 3.11.8。

## 这份记录证明什么，不证明什么

证明：

- 一条真实的 CLI 命令链（`init-project` → `receipt record` → `receipt cache` → `context-pack` → `contract-check` → `status` → `impact`）能从保存的响应文件走到“下一步是什么”和“哪些记录因前文修订而失效”。
- `status` 的第一行是下一步动作；有结果未知的保存回执时，第一行是对账。
- 前文有了更新的可信修订并缓存后，`status` 的第一行改为要先运行的 `impact` 命令，原先记录的下一步退到第二行。
- `impact` 把引用旧修订的快照和依赖它的运行标为 `stale`，并写明是哪条引用。
- `status`、`impact` 运行前后 `.drama/` 下每个文件的 sha256 相同。

不证明：

- 不证明 mali-story 线上有这些候选，也不证明任何候选被采用。所有输出都带 `remote_verified: false`。
- 不证明真实创作项目上的恢复效果。夹具只有一集集纲的两个修订，运行记录是手写的。
- 不证明内容层面的依赖。`impact` 只看记录在案的执行依赖（快照 `items` 里的引用）。

## 环境与输入

所有命令在仓库根目录执行。`<proj>` 是临时目录下的演示项目，`<inputs>` 是同一临时目录下放手写输入的文件夹；下文输出里的绝对路径已替换成这两个记号，其余内容是原样输出，标了“（节选）”的只删去无关字段，没有改动留下的任何一行。

```sh
T="python3 -B skills/drama-studio/scripts/drama_tools.py"
F=tests/fixtures/mcp-synthetic
```

手写输入有三份，都通过了 `contract-check`：

`<inputs>/task.json`（授权来源写 `none`，因为没有真实用户授权）：

```json
{
  "schemaVersion": "drama-studio/task/v0",
  "taskId": "task-ep04-outline",
  "kind": "outline",
  "workstation": "C4",
  "project": {"localId": "local-recovery-demo", "remoteProjectId": "2f70c1e9fad74f35ae27f"},
  "goal": "承接第3集集纲的结尾钩子，写第4集集纲",
  "nonGoals": ["不改第3集集纲"],
  "readScope": [{"kind": "remote_artifact", "id": "9e3f6a2c-4b1d-4c8e-9a57-2d6b1f0c8e41", "revision": 1}],
  "writeScope": [],
  "authorization": {"source": "none", "scope": "合成演示：没有真实用户授权，不写入任何远端"},
  "revisionBudget": 1,
  "status": {"run": "planned", "goal": "not_assessed", "adoption": "none"}
}
```

`<inputs>/selection.json`：

```json
{
  "schemaVersion": "drama-studio/selection/v0",
  "sourceSnapshotId": "sha256:23c10720efd4880fd3b431374bbc44cfd0552ceb18a2be6f7e67aa9b20894225",
  "items": [
    {"ref": {"kind": "remote_artifact", "id": "9e3f6a2c-4b1d-4c8e-9a57-2d6b1f0c8e41", "revision": 1},
     "partition": "current_plan", "required": true, "reason": "第3集集纲候选（未采用）：第4集要承接它的结尾钩子"}
  ],
  "unknowns": ["合成演示：未调用模型，未连接 mali-story"]
}
```

`<inputs>/run-ep04-c4-1.json`（`contextSnapshotId` 填的是第 3 步 `context-pack` 实际产出的快照 ID）：

```json
{
  "schemaVersion": "drama-studio/run-handoff/v0",
  "runId": "run-ep04-c4-1",
  "taskId": "task-ep04-outline",
  "workstation": "C4",
  "methodVersion": "c4@0.1",
  "contextSnapshotId": "ctx-5b73bed85580707d",
  "host": {"name": "claude-code", "model": null, "usage": {"source": "unknown"}},
  "outputs": [],
  "stateChangeProposals": [],
  "changeProposals": [],
  "status": {"run": "interrupted", "goal": "not_assessed"},
  "unfinished": ["第4集集纲只写到中段，结尾钩子未定"],
  "nextAction": "续写第4集集纲后半并定结尾钩子，写完后保存为 ep-04-outline 候选",
  "unknowns": ["合成演示：未调用模型，未连接 mali-story"]
}
```

## 步骤与输出

每一步的退出码都是 0，标准错误为空。

### 1. 建项目，记下读上下文和第一次保存的回执

```sh
$T init-project <proj> --title "恢复演示（合成夹具）"
$T receipt record <proj> $F/01-writing-context.response.json --operation get_writing_context --request-id d1-ctx-1 --input $F/01-writing-context.input.json
$T receipt record <proj> $F/02-save.response.json --operation save_story_artifact --request-id d1-save-2 --input $F/02-save.input.json
```

`init-project` 输出（节选）：`"status": "local_workspace_only"`、`"remoteVerification": "not_checked"`、`"remoteProjectId": null`。两份回执都写入 `.drama/receipts/`，`d1-save-2` 为 `confirmed`，对应 slot `ep-03-outline` 的修订 1。

### 2. 缓存第 3 集集纲修订 1

```sh
$T receipt cache <proj> $F/08-read-chunk-1.response.json $F/08-read-chunk-2.response.json $F/08-read-chunk-3.response.json $F/08-read-chunk-4.response.json $F/03-get.response.json
```

完整输出：

```json
{
  "ok": true,
  "passed": true,
  "status": "written",
  "path": "<proj>/.drama/cache/9e3f6a2c-4b1d-4c8e-9a57-2d6b1f0c8e41@r1.md",
  "entry": {
    "path": ".drama/cache/9e3f6a2c-4b1d-4c8e-9a57-2d6b1f0c8e41@r1.md",
    "artifactId": "9e3f6a2c-4b1d-4c8e-9a57-2d6b1f0c8e41",
    "slot": "ep-03-outline",
    "kind": "episode_outline",
    "episodeRef": "ep-03",
    "revision": 1,
    "sha256": "sha256:fe0f26908f9b8a1e25e4a1ec189d3b706a212865bd846fd8a8d674f97b2c0147",
    "serverFingerprint": "sha256:fe0f26908f9b8a1e25e4a1ec189d3b706a212865bd846fd8a8d674f97b2c0147",
    "verified": true,
    "operation": "read_story_artifact",
    "readAt": "2026-10-01T10:56:49+08:00",
    "slotSource": "record"
  },
  "manifestAppended": true,
  "verified": true,
  "warnings": [],
  "remote_verified": false,
  "adoption_verified": false
}
```

带了 `get_story_artifact` 响应，所以 `slotSource` 是 `record`。

### 3. 装包，得到快照

```sh
$T contract-check task <inputs>/task.json
$T context-pack <proj> --task <inputs>/task.json --selection <inputs>/selection.json --role author --budget 20000
```

`context-pack` 输出（节选）：

```json
{
  "ok": true,
  "command": "context-pack",
  "project": "<proj>",
  "role": "author",
  "dry_run": false,
  "budget": 20000,
  "total_chars": 656,
  "omitted_count": 0,
  "omitted": [],
  "completeness": "complete",
  "written": true,
  "existing": false,
  "network_used": false,
  "models_called": false,
  "remote_verified": false,
  "snapshot_id": "ctx-5b73bed85580707d",
  "snapshot_sha256": "sha256:4851df63b17e502c02d3fd3c91c87922ae91301145955d5a5cb32b552b8cd95b",
  "snapshot_path": "<proj>/.drama/snapshots/ctx-5b73bed85580707d.json",
  "sha256_path": "<proj>/.drama/snapshots/ctx-5b73bed85580707d.sha256",
  "passed": true,
  "errors": []
}
```

快照的 `items[1]` 引用 `9e3f6a2c-4b1d-4c8e-9a57-2d6b1f0c8e41@r1`，即 slot `ep-03-outline` 的修订 1。

### 4. 放入一份手写的运行记录，再记一次结果未知的保存

运行记录由宿主写入，工具不生成它。这里先校验再复制到 `.drama/runs/`：

```sh
$T contract-check run-handoff <inputs>/run-ep04-c4-1.json
mkdir -p <proj>/.drama/runs && cp <inputs>/run-ep04-c4-1.json <proj>/.drama/runs/run-ep04-c4-1.json
$T receipt record <proj> $F/05-unknown.response.json --operation save_story_artifact --request-id d1-save-3 --input $F/05-unknown.input.json
```

`contract-check` 输出：

```json
{
  "ok": true,
  "contract": "run-handoff",
  "path": "<inputs>/run-ep04-c4-1.json",
  "passed": true,
  "errors": [],
  "enforcement": "S",
  "remote_verified": false,
  "adoption_verified": false
}
```

`d1-save-3` 是第 3 集集纲修订 2 的保存请求，夹具里它的响应是 `MCP_OUTCOME_UNKNOWN`。回执（节选）：`"outcome": "unknown"`、`"retryAllowed": false`、`"artifactId": null`、`"revision": null`。

到这里，现场是：一次中断的 C4 运行，加一次不知道有没有落地的保存。

### 5. `status`：第一行是对账

```sh
$T status <proj>
```

完整输出：

```text
下一步：对账结果未知的保存回执 d1-save-3（slot ep-03-outline）：先用 list_story_artifacts 查该 slot 的新修订，再用 get_story_artifact 核对 record.requestId，然后 receipt record … --reconciles d1-save-3；对账前不要换新 requestId 重试
依据：有结果未知、尚未对账的保存回执（.drama/receipts/d1-save-3.json）。只读取 .drama/ 下的本地记录，不读聊天记录；不证明远端状态、采用或质量。最近运行按文件修改时间判定，复制或检出后可能不准。失效提示只比较本地缓存 manifest 里的可信条目，不说明远端有没有更新的修订。

未决回执（1）
- d1-save-3：save_story_artifact，slot ep-03-outline，expectedRevision 1；不可重试，先对账
    list_story_artifacts {"project_id": "2f70c1e9fad74f35ae27f", "slot": "ep-03-outline"}
    get_story_artifact {"project_id": "2f70c1e9fad74f35ae27f", "artifact_id": "<id of revision > 1>"}；核对 record.requestId == 'd1-save-3'
    drama_tools.py receipt record <project> <get-response.json> --operation get_story_artifact --request-id <new-read-id> --input <get-input.json> --reconciles d1-save-3

运行（1 份；最近一次按文件修改时间判定，recencyBasis: file_mtime）
- 最近：run-ep04-c4-1（C4，interrupted/not_assessed，任务 task-ep04-outline，快照 ctx-5b73bed85580707d，修改于 2026-10-01T02:56:50+00:00）
    下一步：续写第4集集纲后半并定结尾钩子，写完后保存为 ep-04-outline 候选
    未完成：第4集集纲只写到中段，结尾钩子未定
    本地缓存中没有它所引用 slot 的更新修订；这不说明远端没有

快照（1）
- ctx-5b73bed85580707d：完好，completeness: complete
```

运行记录的 `nextAction` 也在输出里，但排在对账之后。这时缓存里只有修订 1，所以运行下方写的是“本地缓存中没有它所引用 slot 的更新修订；这不说明远端没有”：结果未知的那次保存可能已经在远端生成了修订 2，本地缓存看不到。这次 `status` 前后 `.drama/` 的 9 个文件哈希逐一相同（`cmp` 两份 `shasum` 清单无差异）。

### 6. 对账后再看 `status`

夹具 `07-reconcile-get` 是按 `list` 找到的修订 2 再 `get` 的响应，它的 `record.requestId` 是 `d1-save-3`：

```sh
$T receipt record <proj> $F/07-reconcile-get.response.json --operation get_story_artifact --request-id d1-reconcile-3 --input $F/07-reconcile-get.input.json --reconciles d1-save-3
$T status <proj>
```

回执（节选）：`"outcome": "confirmed"`、`"artifactId": "c41d2b7a-8e5f-4a3b-b6d9-0f1e2a3b4c5d"`、`"revision": 2`、`notes` 里 `"check": "record.requestId matched (S)"`。

`status` 完整输出：

```text
下一步：续写第4集集纲后半并定结尾钩子，写完后保存为 ep-04-outline 候选
依据：最近一次运行记录的 nextAction（.drama/runs/run-ep04-c4-1.json）。只读取 .drama/ 下的本地记录，不读聊天记录；不证明远端状态、采用或质量。最近运行按文件修改时间判定，复制或检出后可能不准。失效提示只比较本地缓存 manifest 里的可信条目，不说明远端有没有更新的修订。

未决回执（0）

运行（1 份；最近一次按文件修改时间判定，recencyBasis: file_mtime）
- 最近：run-ep04-c4-1（C4，interrupted/not_assessed，任务 task-ep04-outline，快照 ctx-5b73bed85580707d，修改于 2026-10-01T02:56:50+00:00）
    下一步：续写第4集集纲后半并定结尾钩子，写完后保存为 ep-04-outline 候选
    未完成：第4集集纲只写到中段，结尾钩子未定
    本地缓存中没有它所引用 slot 的更新修订；这不说明远端没有

快照（1）
- ctx-5b73bed85580707d：完好，completeness: complete
```

对账回执已经说明修订 2 存在，但修订 2 的正文还没有缓存，manifest 里没有它的条目。`status` 的失效提示只比较缓存 manifest，所以这一步第一行仍是运行记录的 `nextAction`。这是它如实能说的范围：对账之后要把新修订缓存下来，提示才会出现。

### 7. 缓存新修订后，`status` 第一行变成 `impact` 命令

```sh
$T receipt cache <proj> $F/07-reconcile-get.response.json
$T status <proj>
```

`receipt cache` 输出（节选）：`"path": "<proj>/.drama/cache/c41d2b7a-8e5f-4a3b-b6d9-0f1e2a3b4c5d@r2.md"`、`"slot": "ep-03-outline"`、`"revision": 2`、`"slotSource": "record"`、`"verified": false`、`"serverFingerprint": null`，并带一条警告：只有 get 响应时没有全文指纹，要用 `read_story_artifact` 读完整才能核验。失效判定只需要可信的 slot 与 revision，不要求全文已核验。

`status` 完整输出：

```text
下一步：先运行 drama_tools.py impact <proj> --slot ep-03-outline --revision 2 确认失效范围，再决定是否重新装包、重跑：最近运行 run-ep04-c4-1 的快照引用了 slot ep-03-outline 的 r1，本地缓存已有可信的 r2
该运行按旧修订 r1 的上下文记录的下一步（先看 impact 结果，不要直接照做）：续写第4集集纲后半并定结尾钩子，写完后保存为 ep-04-outline 候选
依据：最近一次运行的快照引用了旧修订，本地缓存已有更新的可信修订（.drama/runs/run-ep04-c4-1.json）。只读取 .drama/ 下的本地记录，不读聊天记录；不证明远端状态、采用或质量。最近运行按文件修改时间判定，复制或检出后可能不准。失效提示只比较本地缓存 manifest 里的可信条目，不说明远端有没有更新的修订。

未决回执（0）

运行（1 份；最近一次按文件修改时间判定，recencyBasis: file_mtime）
- 最近：run-ep04-c4-1（C4，interrupted/not_assessed，任务 task-ep04-outline，快照 ctx-5b73bed85580707d，修改于 2026-10-01T02:56:50+00:00）
    下一步：续写第4集集纲后半并定结尾钩子，写完后保存为 ep-04-outline 候选
    未完成：第4集集纲只写到中段，结尾钩子未定
    可能已失效：快照引用 slot ep-03-outline 的 r1，本地缓存已有可信的 r2；先运行 drama_tools.py impact <proj> --slot ep-03-outline --revision 2

快照（1）
- ctx-5b73bed85580707d：完好，completeness: complete
```

第一行不再是“续写第 4 集集纲”，而是先运行 `impact`；原先记录的下一步在第二行，并注明它是按旧修订 r1 的上下文记录的。输出里的命令带的是项目的实际路径，这里替换成了 `<proj>`。

### 8. 按第一行运行 `impact`

```sh
$T impact <proj> --slot ep-03-outline --revision 2
$T impact <proj> --artifact c41d2b7a-8e5f-4a3b-b6d9-0f1e2a3b4c5d
```

第一条的完整输出：

```json
{
  "ok": true,
  "command": "impact",
  "project": "<proj>",
  "target": {
    "slot": "ep-03-outline",
    "revision": 2,
    "resolvedFrom": "--slot/--revision"
  },
  "snapshots": [
    {
      "snapshotId": "ctx-5b73bed85580707d",
      "path": ".drama/snapshots/ctx-5b73bed85580707d.json",
      "status": "stale",
      "reasons": [
        {
          "ref": "items[1] 9e3f6a2c-4b1d-4c8e-9a57-2d6b1f0c8e41@r1",
          "status": "stale",
          "reason": "引用了 slot ep-03-outline 的旧修订 r1，目标修订为 r2"
        }
      ]
    }
  ],
  "runs": [
    {
      "runId": "run-ep04-c4-1",
      "path": ".drama/runs/run-ep04-c4-1.json",
      "contextSnapshotId": "ctx-5b73bed85580707d",
      "status": "stale",
      "reasons": [
        {
          "ref": "context_snapshot ctx-5b73bed85580707d",
          "status": "stale",
          "reason": "所依赖的快照为 stale"
        },
        {
          "ref": "items[1] 9e3f6a2c-4b1d-4c8e-9a57-2d6b1f0c8e41@r1",
          "status": "stale",
          "reason": "引用了 slot ep-03-outline 的旧修订 r1，目标修订为 r2"
        }
      ]
    }
  ],
  "summary": {
    "snapshots": {
      "stale": 1,
      "unknown": 0,
      "current": 0
    },
    "runs": {
      "stale": 1,
      "unknown": 0,
      "current": 0
    }
  },
  "note": "current 只表示没有记录在案的执行依赖指向该 slot 的旧修订；内容层面的隐含依赖未评估。工具只读，不自动重跑运行，也不改写正文。",
  "read_only": true,
  "remote_verified": false
}
```

第二条的输出与第一条只差一行：`"resolvedFrom": "--artifact c41d2b7a-8e5f-4a3b-b6d9-0f1e2a3b4c5d"`（两份输出做过 `diff`）。

修订 1 和修订 2 的 artifactId 不同（`9e3f6a2c…` 与 `c41d2b7a…`），判定靠的是 manifest 里它们同属 slot `ep-03-outline`。

### 9. `status --json`

```sh
$T status <proj> --json
```

输出可解析。节选（只保留下列顶层字段，各字段内容原样）：

```json
{
  "nextAction": {
    "basis": "stale_run",
    "text": "先运行 drama_tools.py impact <proj> --slot ep-03-outline --revision 2 确认失效范围，再决定是否重新装包、重跑：最近运行 run-ep04-c4-1 的快照引用了 slot ep-03-outline 的 r1，本地缓存已有可信的 r2",
    "from": ".drama/runs/run-ep04-c4-1.json",
    "impactCommand": "drama_tools.py impact <proj> --slot ep-03-outline --revision 2",
    "recordedNextAction": "续写第4集集纲后半并定结尾钩子，写完后保存为 ep-04-outline 候选"
  },
  "receipts": {
    "pending": [],
    "read_only_unknown": [],
    "unreconcilable_unknown": [],
    "resolved_verified": [
      "d1-save-3"
    ],
    "resolved_host_judged": []
  },
  "invalid": [],
  "read_only": true,
  "remote_verified": false,
  "adoption_verified": false
}
```

同一输出里 `runs.latest` 的内容（原样）：

```json
{
  "latest": {
    "runId": "run-ep04-c4-1",
    "path": ".drama/runs/run-ep04-c4-1.json",
    "taskId": "task-ep04-outline",
    "workstation": "C4",
    "contextSnapshotId": "ctx-5b73bed85580707d",
    "status": {
      "run": "interrupted",
      "goal": "not_assessed"
    },
    "unfinished": [
      "第4集集纲只写到中段，结尾钩子未定"
    ],
    "nextAction": "续写第4集集纲后半并定结尾钩子，写完后保存为 ep-04-outline 候选",
    "modifiedAt": "2026-10-01T02:56:50+00:00",
    "stalenessCheck": "newer_revision_cached",
    "possiblyStale": true,
    "newerRevisions": [
      {
        "ref": "items[1] 9e3f6a2c-4b1d-4c8e-9a57-2d6b1f0c8e41@r1",
        "slot": "ep-03-outline",
        "pinnedRevision": 1,
        "newestTrustedRevision": 2,
        "impactCommand": "drama_tools.py impact <proj> --slot ep-03-outline --revision 2"
      }
    ],
    "stalenessReasons": []
  }
}
```

## 只读证明：前后 sha256

在第 7 步缓存修订 2 之后取一次哈希，接着依次运行 `status`、`impact --slot --revision`、`impact --artifact`、`status --json`，再取一次：

```sh
(cd <proj> && find .drama -type f | sort | xargs shasum -a 256)
```

| 文件 | 运行前 sha256 | 运行后 sha256 |
| --- | --- | --- |
| `.drama/cache/9e3f6a2c-4b1d-4c8e-9a57-2d6b1f0c8e41@r1.md` | `fe0f26908f9b8a1e25e4a1ec189d3b706a212865bd846fd8a8d674f97b2c0147` | `fe0f26908f9b8a1e25e4a1ec189d3b706a212865bd846fd8a8d674f97b2c0147` |
| `.drama/cache/c41d2b7a-8e5f-4a3b-b6d9-0f1e2a3b4c5d@r2.md` | `3008ac957c8ca6dd3690e0453e155adf3f15f2f21719a6e69265f6581db30c76` | `3008ac957c8ca6dd3690e0453e155adf3f15f2f21719a6e69265f6581db30c76` |
| `.drama/cache/manifest.json` | `ab43b36ec1cca25de21838d48bd011fedcb37f262e42ddfb05a60be405a732c9` | `ab43b36ec1cca25de21838d48bd011fedcb37f262e42ddfb05a60be405a732c9` |
| `.drama/project.json` | `b81032e6db580479ece2eb56fb38c6c1951f7c2bc5e21f3998397358582c9439` | `b81032e6db580479ece2eb56fb38c6c1951f7c2bc5e21f3998397358582c9439` |
| `.drama/receipts/d1-ctx-1.json` | `1debedaff7f5da8c503e951c4ea4edd8e1b5fd31e733d8431cd292dc4ecf8679` | `1debedaff7f5da8c503e951c4ea4edd8e1b5fd31e733d8431cd292dc4ecf8679` |
| `.drama/receipts/d1-reconcile-3.json` | `89d0b9413044514c837868d8c25b59bdc88e777e076ab279c1d481155ba41805` | `89d0b9413044514c837868d8c25b59bdc88e777e076ab279c1d481155ba41805` |
| `.drama/receipts/d1-save-2.json` | `e5ada017a2cf67c2d7c2ed7b09b8b3009da5209ea5cc0f490cdd869c5bc554e2` | `e5ada017a2cf67c2d7c2ed7b09b8b3009da5209ea5cc0f490cdd869c5bc554e2` |
| `.drama/receipts/d1-save-3.json` | `137d25ff48f71c6350fe39a983df9538f35f32c5d7b4aa3c1467e0e6a06031f4` | `137d25ff48f71c6350fe39a983df9538f35f32c5d7b4aa3c1467e0e6a06031f4` |
| `.drama/runs/run-ep04-c4-1.json` | `51ea4a544ff1747d7b0fe1f32712fc1b2e6b21d1be218948006cfbb65247d473` | `51ea4a544ff1747d7b0fe1f32712fc1b2e6b21d1be218948006cfbb65247d473` |
| `.drama/snapshots/ctx-5b73bed85580707d.json` | `4851df63b17e502c02d3fd3c91c87922ae91301145955d5a5cb32b552b8cd95b` | `4851df63b17e502c02d3fd3c91c87922ae91301145955d5a5cb32b552b8cd95b` |
| `.drama/snapshots/ctx-5b73bed85580707d.sha256` | `f5eacc99c65dba7340146f272d2e9692a4251b8f3d6bfcccae4fd9121e864492` | `f5eacc99c65dba7340146f272d2e9692a4251b8f3d6bfcccae4fd9121e864492` |

11 个文件前后相同，文件数量也没有变化（没有新增锁文件或临时文件）。第 5 步那次 `status` 前后的 9 个文件同样逐一相同。自动化测试 `tests/test_project_status.py` 的 `ReadOnlyTests` 另外比较了整个项目目录的哈希与修改时间，夹具里包含“快照引用旧修订”的情形。

## 演示中看到的限制

- 失效提示只在新修订已经缓存、并且 manifest 条目的 slot 可信时出现。第 6 步对账回执已经记下修订 2，`status` 仍没有提示，直到第 7 步把修订 2 缓存下来。恢复时如果对账发现了新修订，要先缓存它。
- 提示出现后不会自己消失：这次运行的快照一直引用修订 1，所以在用新修订重新装包并写出新的运行记录之前，`status` 的第一行会一直是 `impact` 命令。工具不记录“已经看过 impact 结果”。
- `status` 的提示只回答“这次运行的快照引用的修订，是不是低于本地缓存里同一 slot 的最新可信修订”。受影响的完整范围（其他快照、其他运行）要看 `impact` 的输出。
- “最近运行”按文件修改时间判定。这个演示里只有一份运行记录，没有检验多份运行在复制或检出后的排序。
- 运行记录是手写后复制进去的。真实工位运行怎样写出 `run-handoff`，这次演示没有涉及。

## 全新会话恢复记录

（待编排者补录独立代理的恢复结论）

## 待 #9 真实产物补录

#9（C5 正文 + C6 盲读闭环）完成后，在它的试点项目上重做，并在本节补录：

- [ ] 试点项目的来源、远端 projectId、涉及的 slot 与修订（真实 `receipt cache` 得到的 manifest 条目）
- [ ] 全新会话中运行 `status <试点项目>` 的完整输出，以及据此恢复出的下一步是否与实际一致
- [ ] 把前集正文修订到新 revision 并缓存后，`impact` 的完整输出：哪些快照与运行为 `stale`，原因引用是否正确
- [ ] 运行前后 `.drama/` 的 sha256 对比
- [ ] 与本合成演示不一致的地方

补录完成前，#10 的 AC-6 不勾选。
