# D6-4 开头的共用决定

依据：[统一实施计划](../design/drama-studio-outline-dialogue-implementation-plan-2026-10-14.md) §4.5、§8 #1，[D6-3 报告](d6-3-report.md)。日期 2026-10-15。主创当天的指示是「继续，做完开 PR merge」。

## 1. 本阶段不做远端取用，以现有小样本结束

- 本会话里 mali-story 连接超时，没有可用的远端工具；计费确认（`get_shared_creation_budget` 前后读数与回执）是事实核查，没有连接就做不了。按计划 §4.5 退出条件：「全库取用若计费未确认，D6-4 以小样本（≥3 部）结束并把全库列为待办」。
- 现有小样本：本项目 D6-0 阶段 A 的语料缓存，3 部、40 集、138 条交换，manifest 记 11 次读取调用（`readCalls.total`；其中 3 次返回 404。初稿误写为 4，是把该对象的键数当成了次数）。它满足「≥3 部」。全库取用、补三类现实题材缺口语料、计费观察都列为待办，写进 `docs/d6/d6-4-corpus.md`。
- 随包脚本照旧不联网。`corpus fetch` 实现为**取用记账**：由代理调用 mali-story 工具，脚本只做取用计划、断点续取的清单、`expected_snapshot_id` 核对、回执与预算读数的记录与比对。它可以用编造的回执夹具完整测试。

## 2. 语料缓存的位置（§8 #1 未确认，按默认）

缓存放项目目录（现有 `runs/pilot-ep006/corpus/`）；schema 两级都允许，`contract-check` 在主创确认前只放行 `scope.level: project`。新项目的语料默认放 `corpus/`（项目根下），`init-project` 不预建。

**修订（2026-10-15）**：主创确认计划 §8 #1，原话「语料缓存能放工作室级」。此后缓存默认放 `<工作室根>/corpus/`，`dialogue-exchange`、`corpus-manifest` 允许 `scope.level: studio`；项目内的 `corpus/` 仍可用；对照对、批注、本项目反例与人工正例仍只允许项目级。已有的 D6-0 项目缓存不挪。

## 3. 本阶段在本项目上跑的东西

- `feedback-ingest` 全路由：对本项目编剧第 6 集 7 条批注、`writer-edit-pairs.md` §二、现实审查里程序类意见各跑一次。派生物写进本项目（私有、gitignored），仓库里只留计数（写在 `docs/d6/d6-4-report.md` 第四节）。
- `genre-lexicon` 两张禁词表、`default-media-profile.json` 由脚本从现有小样本重算并标 `n`；随包数据文件里只放统计量与词表，不放语料原句。
- 双跑标注：label／walkthrough 的 M 部分是模型做的，本阶段只做比对与一致性记录的 S 部分；对现有标注若已有两份可比对的就比，没有就在报告里照实写「未双跑」。

## 4. 不动的东西

已有 D6-0 语料文件一律不改，重算结果写新文件；`feedback-ingest` 不改编剧原文件。
