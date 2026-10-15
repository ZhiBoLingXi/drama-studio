# 语料：取用、切分、标注与缓存

[台词层](dialogue-structure.md) · [mali-story 连接与拉片](mali-story.md)

台词层的样本来自 mali-story 官方库爆款拉片的转写：按处境切成一段段对话交换，给作者看「处在这种处境里的人怎么一来一回把话说清」。本页写这批语料怎么取、怎么切、怎么筛、怎么标、放在哪、怎么知道它过期了，以及取用会不会花钱怎么查。

每条规矩标层级：**S** 是随包脚本能核的，**R** 是 mali-story 服务端保证的，**M** 是模型照做的约定。语料的权威在服务端（R），本地只是只读缓存与派生记录。**随包脚本永不联网**：取用由代理调用 mali-story 工具完成，脚本只做计划、记账与核对。

## 1. 放在哪、范围多大

- 语料缓存默认放工作室级：`<工作室根>/corpus/`（工作室根是放 `STUDIO.md` 的那个目录，见 [初始化](initialization.md)），几部剧共用一份，不必每个项目各取一遍。语料只是 mali-story 模板数据的只读缓存，不是知识卡，也不是共享知识；工作室级的交换与清单写 `scope.level: studio`。项目内的 `corpus/`（项目根下）仍可用，写 `scope.level: project`。两处都不预建，第一次取用时建。
- 装包时用工作室级语料：`context-pack … --studio-corpus <工作室根>/corpus/`（只给 C5a、C5b），这时 `--exemplars` 可以是这个目录里的文件，其中的记录须是 `scope.level: studio`、来自 mali-story 模板。
- 不论放哪一级，对照对、批注（`writer-note`）、本项目来源的反例与人工正例只能是项目级（`knowledge/contrast/`）；知识卡规则不变，仍只允许项目私有。
- 目录结构（下面的 `corpus/` 指缓存所在的那一级目录）：
  - `corpus/raw/<templateId>/ep-<episodeIndex>.json`：取回的证据原样存（含 `snapshotId`）。
  - `corpus/fetch-ledger.json`：取用账本（`corpus fetch` 写），记计划、每次调用、预算读数与回执 ID。
  - `corpus/manifest.json`（`corpus-manifest`）：每集的 `templateId`、`episodeIndex`、`snapshotId`、`fetchedAt`、`source`，以及 `readCalls: {total, failures, billing}`。
  - `corpus/exchanges.jsonl`（`dialogue-exchange`，一行一条）：切分与标注后的交换。
  - `corpus/labels/`：标注记录；双跑时两次各一份。
- 已有的语料文件不改；重算的结果写新文件。
- 缓存里只能有 mali-story 模板来的数据（`origin.kind: mali_story_template`），不得混进任何项目自己写的句子。本剧的人工句、反例、对照对放 `knowledge/contrast/`，只允许 `scope.level: project`（S）。

## 2. 取用：代理调用、脚本记账

取用一集就是一次 `get_deconstruction_evidence(template_id, episode_index, expected_snapshot_id?)` 读取。返回体有 `rawMd`、`episodeOutlineMd`、`snapshotId`、`missingFields`、`contentTrust: reference_data`、`evidenceValidation: not_run`。代理调用工具、把每次返回存成文件；`corpus fetch` 只记账，不联网：

1. **发现工具**：先确认当前会话里实际有这个读取工具，以及 `get_shared_creation_budget`、`list_shared_creation_budget_receipts`（见 [能力发现](mali-story.md#能力发现与模板复用)）。没有连接时不取，账本与交接里如实写「未连接」，不拿旧缓存冒充新取的。
2. **列计划**：把模板清单（`[{templateId, episodes 或 episodesTotal, snapshotId?}]`）存成文件，`corpus fetch plan <模板清单> --out corpus/fetch-ledger.json [--series 3] [--episodes-per-series 10]` 写出小样本的取用计划，每集带预期的 `snapshotId`（清单给了时）。它不覆盖已有账本。
3. **取前读预算**：调用 `get_shared_creation_budget`（与 `list_shared_creation_budget_receipts`），存下返回，`corpus fetch budget corpus/fetch-ledger.json --label before --reading <预算返回> [--receipts <回执列表返回>]`。
4. **逐集读取**：有预期 `snapshotId` 的传 `expected_snapshot_id`；返回体原样存进 `corpus/raw/<templateId>/ep-<N>.json`，再 `corpus fetch record corpus/fetch-ledger.json --template <T> --episode <N> --response <返回文件> [--tool <工具名>]`。返回缺失、读不出或带错误的记为失败；返回的 `snapshotId` 与预期对比，记 `match`、`snapshot_mismatch` 或 `not_evaluable`。尝试次数自动累计。
5. **断点续取**：中断后先跑 `corpus fetch resume corpus/fetch-ledger.json [--max-attempts 3]`，它列出没读过的、失败了还能重试的、已放弃的；只读这份清单里的集，不从头再来，也不把部分结果写成整部已取。
6. **取后读预算并核对**：再读一次预算（`--label after`），然后 `corpus fetch verify corpus/fetch-ledger.json`。它给出计费结论 `deduction_seen`（额度下降或出现新的回执 ID）、`no_change_seen`（前后都读得到且相等）或 `unconfirmed`（某次读数缺失、未配置或为空），以及快照不符与调用计数。**看到扣费或快照不符时退出码 2：停下、记录，不往全库走。**
7. **核对内容**：每集的 `missingFields` 照记；`evidenceValidation: not_run` 照原样保留，不改述成「已核验」。

`verify` 输出里的观察块（调用次数、预算读数、回执 ID）是可以写进报告的全部内容；报告不写账户余额以外的账户信息。读取次数以账本或 `corpus/manifest.json` 的 `readCalls.total` 为准，不按记忆估。

## 3. 计费观察：事实核查，有扣费迹象即停

读取证据会不会扣费，是一个**事实问题**，不是要主创拍板的决定：查清楚就行，查不到就按「未确认」处理。

1. 先取 3 部、每部 10 集左右的小样本。
2. 取用前、取用后各读一次 `get_shared_creation_budget`，并看每次读取的回执。
3. 读数或回执有任何扣费迹象（`verify` 给 `deduction_seen`：额度下降或出现新的回执 ID）：**立即停**，记下哪次调用前后变了多少，不再取，不取全库。
4. 读数前后不变、回执无新 ID（`verify` 给 `no_change_seen`）：记为「这几次读取未观察到扣费」。这只说明这几次，不推到全库，不写成「不计费」。
5. 没有连接、读不到预算（`verify` 给 `unconfirmed`）时：`manifest.readCalls.billing` 写 `not_observed`，全库取用列为待办。
6. 记录只写调用次数、预算读数和回执 ID，不写账户余额以外的账户信息，不把余额当成本次总价。

计费未确认之前，全库（约 700 集）一律不取；台词层照样能用小样本或没有样本运行（[台词层](dialogue-structure.md#4-样本怎么用处境检索遮蔽每话题上限verbatimfrom)）。

## 4. 快照与失效

- 每条交换带 `snapshotId`。重取时传 `expected_snapshot_id`；服务端报不一致，说明这一集变了：旧交换标 `stale`，不进新包，但不删（已装过它的集要能复现）；重新切分标注，`manifest` 两版都记。
- 服务端没给 `snapshotId` 时，交换用本地指纹引用：`localSha256` 加 `refKind: local_fingerprint`。
- 媒介档案默认值与禁词表按 `manifest` 版本化；台词目标引用具体版本，不自动跟到最新，换版本要进目标的 changelog。
- 对照对引用的正例 `stale` 后，对照对标 `positiveStale`，检索时跳过，等重配。

## 5. 切分

一个交换是一个话题从开启到收束的若干来回，连续、带时间码、参与者稳定；不是单句，也不是整场。

- **S 给候选边界**：`corpus segment <转写…> [--pause-ms 4000] [--window …]`。候选信号：新说话人出现、相邻两句停顿超过阈值（默认 4 秒）、连续两句以上独白刚结束、拉片的段落切换。
- **M 确认**：模型读整集转写，在候选里确认哪些是话题边界，可以在没有候选的地方加边界（话题换了但只停了半秒）；每个交换写一句 `about`。
- 两套都存：`cutBy: script` 的用于可复现统计，`cutBy: model` 的用于检索与装包。

## 6. 过滤：明显不能当样本的剔除

`corpus filter <exchanges.jsonl…> [--manifest corpus/manifest.json]`（S）。剔除并写原因：

| 原因 | 判法 |
| --- | --- |
| `transcript_unparseable` | 时间码不单调、某句没有说话人或内容为空 |
| `too_few_speakers` | 不到两个非独白说话人 |
| `no_response`、`all_monologue` | 整段一个人在说、没人接，或全是独白、旁白 |
| `ad_copy` | 命中「下载／搜索／点击／APP／完整版／关注」这类导流词 |
| `stale` | `snapshotId` 与 `manifest` 当前值不同（给了 `--manifest` 才核） |
| `missing_transcript` | `missingFields` 里缺转写且没有可切的句子 |
| `label_low` | 双跑比对后标注一致性为 `low`（`quality.label: low`，§7） |

`state` 字段里混进非中文的标注只清空那一句的标注，不剔除。`evidenceValidation: not_run` 不是剔除理由，原样带进输出。过滤判的是「这段转写能不能当样本」，不判好坏；被剔除是命令的答案，不是失败（退出码 0；读不出为 1）。

## 7. 处境标注与结构说明

每个交换要有处境（检索键）与结构说明（这段为什么这样走），都是模型写的（M）：

- **处境** `situation`：功能（一个主功能，至多一个副功能）、关系与权力方向、是否对孩子、信息怎么带出来、说话人想要什么、听的人已知什么、双方情绪。词表收敛：功能里的近义项合并；关系同时成立几种时取更具体的那个。
- **结构说明** `walkthrough`：一两句，用处境解释形状（「她在气头上，他每次只说半句就被打断」），不用形状解释形状（「短句多、换人密」），不评措辞好坏。
- **说话人归属可疑** `speakerAttributionSuspect`：脚本按转写标出候选（同一人连续两段被标成不同人等），标了的样本检索时靠后。

`corpus label <labels.jsonl> [--raw-dir corpus/raw]` 核标注的 S 部分：必需字段在、类型对、行号区间合法、`exchangeId` 不重复、取值在词表里。

**双跑**：同一批交换由两次独立运行（不同会话、同一词表）各标一份，再用 `corpus agree <标注 JSONL> [--second <第二次的 JSONL>] [--out <新文件>]` 比对（词表 `schemas/data/corpus-label-vocabulary.json`）：功能的近义项算同一个；关系相同或一个是另一个的上位时算一致（保留更具体的）；信息模式的集合有交集算一致。功能或关系仍不同、信息模式没有交集的记 `labelConfidence: low`；`--out` 写一份带 `labelConfidence`、`labelAgreement` 的副本，`low` 的行加 `quality.label: low`，`corpus filter` 不把它放进通过名单，所以它进不了检索结果。原文件不改；不一致是答案不是失败（退出码 0）。结构说明也两次各写，由第三次判是否说的是同一个走法。没有两份可比对的标注时，如实写「未双跑」，不把单次标注当成一致。`reviewedBy` 字段留着，有人看过再填，人不是必经环节。

不让模型给交换打「好坏分」。「优秀」只是可记录的筛选条件：已上线爆款、转写干净、结构完整、锚到看点（锚到本集拉片的爽点或钩子的进 Tier 1，其余合格的进 Tier 2）。

## 8. 媒介档案与禁词表

- **媒介档案物理量**：`corpus rate <corpus/raw> [--series-format <templateId>=live|anime]`（没写的剧按 `live` 算并标 `formatSource: assumed`） 从时间码量语速（说话期间每分钟汉字）、停顿比、每集每分钟台词汉字（第二口径），只有物理量，不出任何句数、换人数配额。样本量写进 `n`；漫剧没量过的项写 `null` 并说明。随包默认档案 `schemas/data/default-media-profile.json` 就是这样算出来的；项目有了自己的语料，就在项目里重算一份放 `planning/media-profile.json`。
- **题材禁词表**：两种题材的语料做词频对照，在一种题材高频、另一种近零的词进另一种的禁词表（如现实题材里的「为师」「宗门」，仙侠题材里的「物业」「快递」）。表是数据（`schemas/data/genre-lexicon.json`，标 `source` 与 `n`），不是规则；语料更新就重算。`corpus lexicon <正文> --project-genre <题材>` 扫正文，命中报 `GENRE_LEAK`，是事实核对，只报不拦。

**重算默认值**：`corpus defaults <corpus 目录> [--series-format <templateId>=live|anime] [--out <文件>]` 从语料重算媒介档案默认值（与 `corpus rate` 同一公式）和每种形态的交换中位时长，各带 `n`（几部、几集、几条交换）；对禁词表逐表统计它在本题材与其他题材里出现多少次、哪些假定的词得到语料确认，并给出新的候选词；最后与随包的 `default-media-profile.json`、`genre-lexicon.json` 对比。候选词可能带出某部剧特有的词，只写进 `--out`（项目里），不进随包数据。它只读，`--out` 不覆盖已有文件。

随包数据文件里只放统计量与词表，不放语料原句。

## 9. 进包

样本怎么检索、每个话题装多少、遮蔽、`verbatimFrom` 见 [台词层 §4](dialogue-structure.md#4-样本怎么用处境检索遮蔽每话题上限verbatimfrom)。要点：检索键是处境；包里是处境、结构说明、骨架和至多 2 句遮蔽原句，不给原始转写行；语料原句永不逐字用；生成后用 `dup-check` 两档核字面重合（13 字对全库、8 字对本次装过的样本）。

## 10. 命令速查

命令都用 `python3 -B scripts/drama_tools.py <命令>` 运行，`--help` 看全部参数；读 JSON 输出里的结构化字段，不要只看退出码。

| 步 | 命令 | 退出码怎么读 |
| --- | --- | --- |
| 取用计划 | `corpus fetch plan <模板清单> --out corpus/fetch-ledger.json [--series 3] [--episodes-per-series 10]` | 1 账本已存在（不覆盖） |
| 记一次读取 | `corpus fetch record <账本> --template <T> --episode <N> --response <返回文件>` | 0；失败与快照不符写进账本 |
| 记预算读数 | `corpus fetch budget <账本> --label before｜after --reading <预算返回> [--receipts <回执列表返回>]` | 0 |
| 断点清单 | `corpus fetch resume <账本> [--max-attempts 3]` | 0；只读 |
| 计费与快照核对 | `corpus fetch verify <账本>` | **2 看到扣费或快照不符：停下、记录，不取全库**；`unconfirmed` 时退出码 0，按未确认处理 |
| 切分候选 | `corpus segment <转写…> [--pause-ms 4000]` | 0；候选边界，M 再确认 |
| 过滤 | `corpus filter <exchanges.jsonl…> [--manifest corpus/manifest.json]` | 0；每条给保留或剔除原因；1 读不出 |
| 标注格式 | `corpus label <labels.jsonl> [--raw-dir corpus/raw]` | 2 格式或词表不对 |
| 双跑比对 | `corpus agree <标注 JSONL> [--second <JSONL>] [--out <新文件>]` | 0；不一致的记 `low`，不进检索 |
| 重算默认值 | `corpus defaults <corpus 目录> [--out <文件>]` | 0；候选词只进 `--out` |
| 语速与停顿 | `corpus rate <corpus/raw> [--series-format <templateId>=live｜anime]` | 0；只给物理量与 `n` |
| 禁词扫描 | `corpus lexicon <正文> --project-genre <题材>` | 只报 `GENRE_LEAK` |
| 用工作室语料装包 | `context-pack … --role dialogue_designer｜author --studio-corpus <工作室根>/corpus/ --exemplars <其中的文件>` | 2 记录不是 `scope.level: studio` 或不是来自 mali-story 模板等 |
| 对象格式 | `contract-check {dialogue-exchange｜corpus-manifest｜contrast-pair} <文件>` | 2 违反 schema；对照对与批注不是 `scope.level: project`；工作室级记录里混进项目句子 |
