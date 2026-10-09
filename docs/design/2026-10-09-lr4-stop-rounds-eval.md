# lr-4 spike 评估——停点轮语义与 no-reply 契约（零代码评估）

> 2026-10-09 · 对象：lr-4a 现役停点轮（`DEC-OPI-c73dbff3…128`）→ PLAN v2（`PLAN-OPI-c73dbff3…112`）lr-4 两工作项的评估半（eval-conversation-model → no-reply-stop-rounds）· 开工三件：裁决 `DEC-OPI-41a4df20…27` / 任务 `TASK-…29` / 验收 `VAL-…31` · 外评第六轮 MH-1 必答面见 §5.2 · 本文 = 评估文档，零代码改动，唯一仓内写入 = 本文件；读探针全部仓外（`D:\_lr4_spike\`）。

## 0. 结论摘要

1. **契约层（面①）**：转写契约对「无 assistant_turn 的轮」是**一等公民**——`CanonicalTurnSlice.AssistantTurn?`（`docs/DATA_MODEL.md:114-122`）+ 轮终态词 `NO_ASSISTANT_OUTPUT` 且明文「不要求一定存在 AssistantTurn」（`docs/STATE_MACHINES.md:293-303`）。**「永无回信的终态轮」与「暂无回信的非终态轮（parked）」是两类**：前者是已关闭的 transcript 事实（生产先例：守卫作废投递、打断取消——`src/elc/runtime/controller.py:4019-4040`），后者是**故意**停在 GENERATING 的重入材料（`src/elc/runtime/controller.py:1604-1643`）。no-reply 设计必须走前者（显式关闭），悬挂不可取（恢复扫描语义，§1.3）。
2. **消费面（面②）**：**除一处外全部已容**。历史/交错/usage/教学/recorder/episode/persona 历史读/inbox 计数对 `assistant_turn is None` 已被 lr-4a 与 cs-0/cs-3 的现役代码覆盖（每面三判见 §2 表）。**待改的唯一真缺口**：被新信顶替的 parked 轮**永久悬挂在 GENERATING**（探针实证 + 前端注释自认「旧轮如实半轮留在历史里」`src/elc/webui/app.js:4558-4560`）——这正是 no-reply 刀要补的显式关闭面；awaits_you 只是同一缺口的第二个入口。
3. **类型学（面③）**：叙事者词表已三分（`src/elc/world/narrator.py:180-189`），directed 实现将三词**塌缩成一种停点形**（`stop != letter_arrives` 即停，`src/elc/web.py:3304`）且停词**不落盘**（row 无 stop 字段，`src/elc/web.py:6386-6396`；payload 硬编码 `awaits_direction`，`src/elc/web.py:6551/6577`）。定谳建议：letter_arrives=RESPONSE 终停→回信（已实现）；she_thinks_of_you=NOTICE 检查点（轻继续，无候选可停——已可停、呈现未分型）；awaits_you=RESPONSE 终停**无回信**（本轮 `terminalize_turn(NO_ASSISTANT_OUTPUT)` 显式关闭 + 清 row + 世界 run 保持 AT_CHECKPOINT 由下一封信恢复）。差距清单见 §3.4。
4. **沉浸模式（面④）**：现役零停点（`src/elc/web.py:3756-3761`）。建议**收窄后置**：v1 只让 `awaits_you` 停（词义「世界在等你」与继续运转直接矛盾，是语义裂缝非节奏偏好）；`she_thinks_of_you` 不停（NOTICE 流过，保住沉浸零打断的卖点）。触发时机 = dogfood 信号或 branch-point 刀同场；注意 R6 字节兼容钉（`tests/host/test_lr4a_parked_rounds.py:500`）需随行为变更重裁。
5. **量级与刀序（面⑤）**：no-reply 刀 src 估算 **135–220 行**（web.py 70–100 + controller 40–70 + 前端 25–50）、tests 300–550，**1 刀**；branch-point 刀 src 20–50、tests 150–300，**1 刀**（依赖 no-reply 刀落盘 stop 词后才有分布读数）；沉浸 awaits_you 停为可选第 3 刀（src 15–30）。branch-point 判定设计（MH-1 必答）：**采纳「叙事者停词即停」——directed 只在 stop ∈ {she_thinks_of_you, awaits_you} 时停，stop=none 在同一请求内续转到信到或防御上限**；不新增 branch_worthy 字段（词表已是该判定）；风险与退出条件见 §5.2/§5.3。

---

## 1. 面①：转写契约现状

### 1.0 任务书指针校正

任务书面①写「docs/DATA_MODEL.md §22（Transcript Data）」——实测 `docs/DATA_MODEL.md:1209` 的 §22 是 **Delivery Data**（ServerDeliveryRecord / ClientRenderAck / ExposureEstimate）。转写契约的正典位置是 **DATA_MODEL §3（Conversation Entities + Sequence Semantics，:57-123）+ §4（TurnRecord，:147-163）+ STATE_MACHINES §10（TurnRecord State Machine，:273-303）+ DOMAIN_MODEL §3 关键律（:84）**。本面按正典位置评估；§22 对本题的相关面只有一点：投递记录以 `assistant_turn_id` 关联（`docs/DATA_MODEL.md:1213-1221`），无 assistant_turn 的轮在投递侧天然无记录，与契约自洽。

### 1.1 契约怎么约定无 assistant_turn 的轮

- 序列语义：`UserTurn 与该 turn 的 AssistantTurn? 共享 turn_id/turn_sequence`（`docs/DATA_MODEL.md:74-75`）——assistant 侧从记法上就是可选的。
- 切片形状：`CanonicalTurnSlice = UserTurn + AssistantTurn?（none/partial/full）+ TurnOutcome`（`docs/DATA_MODEL.md:114-122`）。
- 终态词：`NO_ASSISTANT_OUTPUT` 是五个轮终局之一，且「`REPLIED_FULL`、`REPLIED_PARTIAL`、`NO_ASSISTANT_OUTPUT` 都可进入 `DELIVERY_TERMINAL → POSTPROCESSING/COMPLETED`；**不要求一定存在 AssistantTurn**」（`docs/STATE_MACHINES.md:293-303`）。
- 真相律：canonical transcript 是系统确认的实际状态，「未 delivery 的 provider output 不进入 transcript」（`docs/DOMAIN_MODEL.md:84`）——没有回信 = 没有 assistant 行 = 轮仍可合法关闭。
- 落库机制：`terminalize_turn` 把 `NO_ASSISTANT_OUTPUT` 映射到 `COMPLETED`（CAS + epoch fence，`src/elc/conversation/store.py:646-705`，映射 :663-668）。
- **生产先例已存在**：守卫作废的流式投递「no assistant_turn row is written，outcome 是 CANCELLED_BY_USER 或 NO_ASSISTANT_OUTPUT」（`src/elc/runtime/controller.py:4019-4040`）；打断取消同样只终态化轮、无 assistant 行（`src/elc/runtime/controller.py:1554-1565`）。

### 1.2 lr-4a parked 轮对「无 assistant_turn 状态」的使用范围

parked 轮的 durable 形态：CP0 提交（UserTurn 行 + TurnRecord）后**条件早退**在 GENERATING——无 DecisionCycle、无 generation action、无投递（`src/elc/runtime/controller.py:1604-1643, 1780-1795`）；CP1 学习腿在停之前已结算（`src/elc/runtime/controller.py:1729-1736` 注释 + 停点在 :1780）。已在用的容忍范围：

- **读面**：用户可见窗口把该轮的 user 行带出、assistant 为 null（`src/elc/conversation/store.py:960-1013`；`src/elc/web.py:7311-7349`）——测试钉 `tests/host/test_lr4a_parked_rounds.py:413-451`（439 行 `assert turn["assistant"] is None`）。
- **跨请求/跨重启**：parking row（app_setting 键 `world_parked_turn:<conversation_id>`，`src/elc/web.py:2332-2353`）携带重入材料，continue 幂等重入原 command（`src/elc/web.py:6637-6666, 6761-6805`）——重启存活钉 `tests/host/test_lr4a_parked_rounds.py:459-492`。
- **恢复扫描**：扫描只针对旧 epoch 非终态轮（`src/elc/conversation/store.py:1142-1158`）；`_close_residual_turns` 只关「generation action 属于 CLOSED 教学时刻」的轮，无 action 的轮（parked 轮正是）**永不被误关**（`src/elc/runtime/controller.py:4755-4815`，action None → continue :4803-4804）——「零新恢复码」是 lr-4a 的设计事实（测试 459 行 docstring 明说）。
- **前端**：`assistant: null` 的渲染、搜索、history 重建全部容忍（`src/elc/webui/app.js:3811-3824, 3910-3912, 5472-5473`）；parked additive 键驱动等待态重建（`src/elc/web.py:7357-7378`；`src/elc/webui/app.js:4319-4345, 4412`）。

### 1.3 「永无回信的终态轮」vs「暂无回信的非终态轮」——两类，且必须分清

| | parked（暂无） | no-reply 终态（永无） |
|---|---|---|
| TurnRecord | GENERATING，非终态，owner epoch 现役 | COMPLETED + `NO_ASSISTANT_OUTPUT`（或 CANCELLED_BY_USER，若用户打断） |
| 恢复扫描 | 现役 epoch 不扫；旧 epoch 扫到但无 action 不关（§1.2） | 终态被扫描谓词天然排除（`store.py:1153-1154`） |
| continue 面 | row 在 → 可续 | row 清 → 409「现在没有停下来的世界」（`src/elc/web.py:6590-6599`） |
| 世界的 run | 保持 AT_CHECKPOINT，信/继续恢复（`src/elc/world/engine/orchestrate.py:341-343`——生成步从不终态化 run） | 同左：awaits_you 关轮后 run 仍锚在 checkpoint，**下一封信是唯一发条**（spec §4.1，`docs/design/2026-10-05-living-world-spec.md:63`） |
| 语义 | 「这一轮还没讲完」（重入材料在） | 「这一轮讲完了，落点是世界等你」（ transcript 事实在） |

**结论：两类。** parked 是「故意非终态 + 重入材料」，契约已由 lr-4a 用足；no-reply 是「显式终态关闭」，契约早有词、生产已有先例（§1.1）。若 awaits_you 选「悬挂」（轮永留 GENERATING）：(a) 每次重启扫描都会点名它（`controller.py:4448-4452` 的 F7 动机原话「非终态 forever…每个后续 scan 继续点名」）；(b) continue 面的 preflight 永远放行一个永远等不到 reply 的轮（`src/elc/web.py:6600-6613` 只查终态）；(c) 与 §23「非终态 = 可恢复工作」的语义冲突。**建议显式关闭。**

---

## 2. 面②：消费面容忍度清单（核心交付）

逐面三判：**已容**（引现役测试）/ **待改**（引具体行为）/ 量级（行级估算，改动面口径）。每面附「暂时无（parked）」与「永远无（终态 no-reply）」的差别影响。

| # | 面 | 判 | 依据（文件:行） | parked（暂无）vs no-reply（永无） | 量级 |
|---|---|---|---|---|---|
| 1 | 历史面（`/api/history`） | **已容** | 窗口读切片 assistant 可空（`src/elc/conversation/store.py:960-1013`）；turn 组装 `assistant: null`（`src/elc/web.py:7311-7349`）；parked additive 键只在轮活着时出现（`src/elc/web.py:7357-7378`）；钉 `tests/host/test_lr4a_parked_rounds.py:413-451` | parked：user 行 + `assistant: null` + parked 键（已钉）。no-reply：同一切片形状、**无** parked 键（row 已清）——读面 0 行改动 | 0 行（读面） |
| 2 | 交错面（wr-8 分桶） | **已容** | 分桶键 = `user_turn.created_at`（`src/elc/web.py:1200-1222`），事件按 `(previous turn, this turn]` 归桶（`src/elc/web.py:3994-4015`），只读 REVEALED（红线 `src/elc/web.py:4017-4022`）；与 assistant 无关；钉 `tests/host/test_wr8_history_world.py:216, 276, 348, 386` | 两形态无差别：世界帧按 user 行时刻交错，终态 no-reply 轮照常携带自己的世界帧 | 0 行 |
| 3 | usage 计量 | **已容** | `_usage_by_turn` 无 generation attempt → `None`「never a fabricated 0」（`src/elc/web.py:1181-1197, 7332-7334`）；累计 `_usage_totals` 按 attempt 求和（`src/elc/web.py:1160-1178`） | parked：暂 None、回信后回填；no-reply：永 None——语义正确（该轮确无生成） | 0 行 |
| 4 | 教学面（detector 输入） | **已容** | 检测输入 = `command.raw_content`（`src/elc/runtime/controller.py:1827-1837`），空文本答 None 不造假观察（`src/elc/runtime/automatic_turn.py:766-796`）；**parked 半场不跑 assemble 腿**（停点 :1780 先于 :1827），检测在重入轮跑 | parked：检测随重入发生、输入是原信文本——语义不变。no-reply：轮不重入即无检测，learning 证据已在停前由 CP1 落（`src/elc/learning/store.py:2511, 2580-2583`；CP1 时序 `controller.py:1729-1736`）——无「必须先有 assistant」假设 | 0 行 |
| 5 | 教学面（freshness/profile/recorder） | **已容** | freshness 是 target 级学习读数非轮级（`src/elc/scheduler/controller.py:164-206`）；recorder 吃 persona 可见切片、assistant 缺席时 `assistant_turn_id` 留 None（`src/elc/relationship/recorder.py:311-319`；切片读 `src/elc/relationship/projection.py:195-211`） | 两形态无差别（CP4 投影对 no-reply 轮：若跑，落一个无 assistant 证据的投影行——与 teaching 命令轮同形，已被 cs-0 形态覆盖） | 0 行 |
| 6 | episode 折叠 | **已容** | 折叠只读 `user_turn.raw_content`（`src/elc/relationship/episode.py:448-468, 471-482`） | no-reply 轮贡献自己的 user 行——「她没回的那封」进摘要，语义正确 | 0 行 |
| 7 | persona `[history]` 提示段 | **已容** | assistant 行只在有文本时渲染（`src/elc/persona/commands.py:752-773`） | 两形态无差别 | 0 行 |
| 8 | world inbox / letters_count | **已容** | `letters_count` = 用户可见窗口切片数（`src/elc/web.py:4455-4471`；居民聚合 `src/elc/web.py:4651-4656`） | no-reply 轮也计为一封寄出的信——语义正确（信确实寄了） | 0 行 |
| 9 | 重入/恢复面 | **待改（唯一真缺口）** | 新信顶替 parked 轮：CP0 无「一会话一轮非终态」守卫（`src/elc/conversation/store.py:324-364` 只查 CLOSED 与 client_message_id 幂等），新轮照铸；parking row 被新一轮覆写（`src/elc/web.py:6528-6540`），旧轮**永留 GENERATING**；前端注释自认「旧轮如实半轮留在历史里」（`src/elc/webui/app.js:4558-4560`）。**探针实证**见 §7：1 GENERATING 残留 + 1 COMPLETED | parked 顶替：旧轮悬挂（今天已发生）。no-reply（awaits_you）：同缺口第二入口——需要**显式关闭面**（coordinator 新公共面 + web 两处臂） | controller 40–70；web 30–60；详见 §5.1 |
| 10 | 前端停点呈现 | **待改（分型呈现）** | 三词塌缩为单一等待形：payload stop 硬编码 `awaits_direction`（`src/elc/web.py:6551, 6577`），chrome 单词表「让世界继续」/上限句（`src/elc/webui/app.js:3043-3055`） | 分型后 awaits_you 需要自己的形（世界在等你写信：无 continue 钮或钮改「写一封信」引导） | 前端 25–50 |
| 11 | continue/preflight 面 | **已容（关轮后自然 409）** | row 清后 continue 409「现在没有停下来的世界」（`src/elc/web.py:6590-6599`）；awaits_you 关轮后 run 仍可由信恢复（信是轻继续的超集，`src/elc/world/engine/orchestrate.py:205-208`） | 语义正好：RESPONSE 型时刻轻继续不推进世界（spec §4.6），只有信推进 | 0 行 |

**小结**：读面全家（历史/交错/usage/教学/投影/inbox）对两种「无回信」形态**零改动**——lr-4a 与 cs-0/cs-3 的先例把容忍面已经铺平；真正要写代码的只有 **§2 第 9 行的显式关闭面**（顶替臂 + awaits_you 臂共用）与**第 10 行的分型呈现**。

---

## 3. 面③：停点类型学设计定谳建议

### 3.1 现役机构盘点

- **词表已三分**：`STOP_LETTER_ARRIVES / STOP_SHE_THINKS_OF_YOU / STOP_AWAITS_YOU / STOP_NONE`（`src/elc/world/narrator.py:180-189`），`StopSignal` 数据类（:749），解析严格（只认 `{"kind": <词>}`，`src/elc/world/narrator.py:996-1015`），prompt 教学句「信到读毕标 letter_arrives」+「stop 是世界自己的判词：继续 / 信到 / 世界在等用户」（:630-638, 679-691）。
- **裁决缝已通**：`on_stop` 回调在步内只在静默臂之后触发、步本身从不据此分支（`src/elc/world/engine/orchestrate.py:310-319, 436-440`）——判词归调用方的链（`src/elc/web.py` 的 `_world_step_frame`）。
- **directed 塌缩**：`parked = directed and frames and stop != letter_arrives`（`src/elc/web.py:3304`；流式同 :3444, :3479）——三词与 none 一律停，停词本身**被丢弃**（row 无字段 :6386-6396，payload 硬编码 `awaits_direction` :6551/:6577）。
- **immersive 只认信到**：`letter_arrives` break（:3751-3755），其余词继续转（:3756-3761）。
- **turn-flow 词与叙事词两族并存**：`WORLD_STOP_AWAITS_DIRECTION`（`src/elc/web.py:2316-2322`）描述「轮在做什么」，叙事词描述「世界为何停」——两族不该混用，但叙事词今天根本没落盘。

### 3.2 三型语义定谳建议（对齐 spec §4.6）

spec §4.6 的参与要求三分（`docs/design/2026-10-05-living-world-spec.md:111-129`）与典型映射（:120-128：回信到达=RESPONSE；中途便条=NOTICE、偶尔 RESPONSE「她在等你一句话」）——叙事者词表就是这张表的运行时化身：

| 词 | 型 | directed 呈现/续转/终态建议 | immersive 建议（§4） |
|---|---|---|---|
| `letter_arrives` | RESPONSE 终停→回信 | 现役已对：链止、提交轮续跑、回信落地（`web.py:3751-3755` + 重入） | 现役已对（链止点） |
| `she_thinks_of_you` | NOTICE/DIRECTION 检查点 | **停，可轻继续，候选可空**：现役可停可续已具备（`tests/host/test_lr4a_parked_rounds.py:315` 无选择也能走；候选可空形 `web.py:6481-6497` 空列表合法）；缺的是**分型呈现**（轻一句 + 继续钮，不摆方向选择架势） | 不停（NOTICE 流过）——沉浸的呼吸感靠信到停点已足 |
| `awaits_you` | RESPONSE 终停**无回信** | **停 + 显式关闭轮**：本轮 `terminalize_turn(NO_ASSISTANT_OUTPUT)`、清 parking row、history 无 parked 键；continue 409（世界不在等导演，在等信）；世界 run 保持 AT_CHECKPOINT 由下一封信恢复（`orchestrate.py:341-343` + 信=轻继续超集 `:205-208`）；呈现「世界在等你」（写 信引导，无继续钮） | 停（唯一沉浸停点）：词义「世界在等你」与继续运转矛盾——不停即叙事违约 |
| `none` | 非停点 | **不停**（MH-1 的落点，§5.2）：同一请求内续转 | 不停（现役） |

### 3.3 parked 轮 durable 行（world_parked_turn）需扩什么

现役 row 形状（`src/elc/web.py:6386-6402`）：`{turn_id, input_id, client_message_id, raw_content, received_at, runtime_version, stops, phase, directions?}`。建议扩：

1. **`stop_kind` 字段**（叙事者原词，`"she_thinks_of_you" | "awaits_you"`；`letter_arrives` 不入 row——信到即转 reply phase，现役 `web.py:6773-6782`）。写面 `:6528-6540` +1 行，解析 `:6386-6402` +1 行（或宽容缺省 = 旧 row 视作 she_thinks_of_you，向后兼容）。
2. **`phase` 词表扩一值**：`"chain" | "reply"`（现役，`web.py:6537, 6698, 6773-6782`）→ 增 `"closed"`（或直接清 row——推荐**清 row**：关闭轮与清 row 原子，row 的存在即「轮还开着」，preflight 语义最简；`closed` 值仅在需要留「为何关」的审计时才要）。
3. **payload stop 词透传**：`_park_round`/`_parked_payload_from_row` 的 `stop` 键从硬编码 `awaits_direction` 改为「turn-flow 词 ∪ 叙事词」并陈（如 `stop: "awaits_direction"` + `stop_kind: row 词`）——前端分型呈现的数据源。
4. 量级合计：row/payload/签名 **web.py 15–30 行**；`turn()`/`turn_stream()` 捕获链尾 stop 词传参 3 处各 ~3 行（`web.py:3299-3315, 3437-3452, 3467-3494`）。

### 3.4 与 lr-4a 现役机构的差距清单

1. 停词不落盘（§3.3.1）——类型学与 branch-point 读数的前置。
2. directed 对 `none` 也停（`web.py:3304`）——每步停的 MH-1 病灶（§5.2）。
3. `awaits_you` 无 no-reply 关闭面——与顶替臂共用新 coordinator 面（§2 第 9 行）。
4. 呈现不分型（§2 第 10 行）——三词一种 chrome。
5. `she_thinks_of_you` 的「轻继续」在候选为空时今天也会摆出方向架势（candidates 空 + continue 钮同形）——分型呈现时补 NOTICE 形。
6. 沉浸模式对 `awaits_you` 继续转（`web.py:3756-3761`）——DEC-95 R4 未兑现（§4）。
7. 两族词（turn-flow `awaits_direction` vs 叙事词）关系未定谳——建议 §3.3.3 的并陈方案，不改 `WORLD_STOP_AWAITS_DIRECTION` 的契约位（测试钉 `tests/host/test_lr4a_parked_rounds.py:525-550` 断言其字面）。

---

## 4. 面④：沉浸模式停点语义（DEC-95 R4 未兑现面）

**现役**：沉浸零停点，链直通到信到（`web.py:3756-3761`；R6 钉 `tests/host/test_lr4a_parked_rounds.py:500-524`「pre-lr-4a 链 byte for byte，零停点零 parking」）。DEC-95 R4 设想：沉浸下 `she_thinks_of_you`/`awaits_you` 也停（「轻继续或写信」）。

**价值**：
- `awaits_you` 停是**语义修正**不是节奏偏好——世界亲口说「在等你」，行为却继续走，叙事违约（spec §4.6 :117 RESPONSE = 「世界保持等待，直至你的回信」）。沉浸用户收到 awaits_you 而世界不等的每一拍都在教用户「世界的话不算数」。
- `she_thinks_of_you` 停是**节奏调味**——沉浸的卖点恰是零打断（第十一击的教训反面向：directed 用户嫌「不停」，沉浸用户可能嫌「停」）。

**成本**：
- 每停点多一次请求/交互；沉浸无候选面，停 = 裸继续钮，信息密度低。
- 行为变更打红 R6 字节兼容钉族（`tests/host/test_lr4a_parked_rounds.py:500`、`tests/host/test_lr1_run_chain.py:368` 的「非信到词继续转」钉）——需要显式重裁，不是顺手改。

**推荐**：**收窄后置**——
1. v1 只兑现 `awaits_you` 沉浸停（语义修正，一次停点代价可接受：awaits_you 应是叙事者的低频词，若实测高频则该先修叙事者判词而非让用户埋单）；
2. `she_thinks_of_you` 沉浸不停，维持现役；
3. 触发时机 = branch-point 刀同场（同一词表语义统一）或 dogfood 出现「沉浸轮世界说等却不停」的用户信号；
4. 若后置，在 deferred 台账记一行（落点 = 分型刀或沉浸微刀；触发 = dogfood 信号），避免「后置 = 遗忘」。

量级：`_world_step_frame` 沉浸臂改 `awaits_you` 也 break + 停点形（沉浸停点无 directed 半场——世界停但轮已提交？**注意**：沉浸链在世界步之后才提交轮（WR-6 序），沉浸停点 = 链止 + 照常回信？不——awaits_you 是无回信停。沉浸的 awaits_you 停点需要「不回信」语义，即沉浸也走 parked/关闭路径——这比 directed 版复杂（沉浸轮今天在链后才 commit）。**建议**：沉浸 awaits_you 的第一版语义 = 链止于此 + **照常回信**（信到与否由叙事者说，awaits_you 只是把「下一封信前世界不再自转」的边界画清——即停在「不再续步」而非「不回信」），回避无回信形在沉浸的复杂度；完全对齐留 C1 后。此建议在开工裁决时需总控复裁。

---

## 5. 面⑤：量级定谳 + branch-point 必答 + no-reply 刀任务书轮廓

### 5.1 量级定谳与刀数建议

| 刀 | 范围 | src 估算 | tests 估算 | 依赖 |
|---|---|---|---|---|
| **刀 N（no-reply + 类型学最地面）** | §3.3 row 扩字段 + §2 第 9 行显式关闭面（顶替臂 + awaits_you 臂）+ §2 第 10 行分型呈现 + 契约钉 | web.py 70–100（row 15–30、关闭两臂 30–60、透传/签名 15–30）+ controller.py 40–70（新公共关闭面：lease/guard/CAS/NO_ASSISTANT_OUTPUT + CP4 裁决）+ app.js 25–50 | 300–550（新钉文件 + lr4a/wr10 既有钉随迁） | 无（可即刻开工） |
| **刀 B（branch-point）** | §5.2：directed 只在叙事者判停时停 | 20–50（三处 park 条件 + 文案 + 读数） | 150–300 | **刀 N 的 stop_kind 落盘**（否则停词分布无读数） |
| **刀 C（沉浸 awaits_you，可选）** | §4 | 15–30 | 60–120（R6 钉重裁） | 刀 B 同场或 dogfood 信号 |

**建议刀数 = 2 必做 + 1 可选**；刀 N → dogfood（收集停词分布 + 顶替/awaits_you 体验）→ 刀 B。估算口径：src-only 行级、含 docstring；与既有判例一致超带须披露。

### 5.2 branch-point 判定设计（外评 MH-1 必答面）

MH-1 原文（`AGENTS.md:73`）：「每步必停过密 → lr-4 spike 必答面加入『DIRECTION = meaningful branch point 非 every beat』（lr-4a = scaffold 不冻结）」。

**候选方案对比**：
- **方案甲（推荐）：叙事者停词即停。** directed 的 park 条件从 `stop != letter_arrives`（`web.py:3304`）收窄为 `stop ∈ {she_thinks_of_you, awaits_you}`；`stop = none`（或无信号）在同一请求内续转（复用 `_world_step_frame` 的链循环与 `MAX_CHAIN_STEPS=5` 防御上限，`web.py:2305-2314, 3635-3637`），直到信到或叙事者判停。词表零扩展、prompt 零改动——叙事者**今天就在输出这个判定**（`narrator.py:685-691`），lr-4a 只是暂时无视了它。
- **方案乙：新增 branch_worthy 字段让叙事者自判。** 否——与 stop 词完全重叠，多一份 prompt/解析面多一种谎报面，违反「词表已载判定就不造第二词表」的家族律。
- **方案丙：候选质量阈值（高价值候选才停）。** 否——「高价值」不可机器判定，启发式阈值是校准负债；候选数量与质量已由叙事者的 2–4 约束（`narrator.py:151-155`）承担。

**节奏校准（辅助）**：现有两道安全线已覆盖——单请求链上限 `MAX_CHAIN_STEPS=5`（`web.py:2314`）+ 无走向空转上限 `MAX_PARKED_STOPS=10`（`web.py:2330`，lr-3 双形豁免臂 `web.py:6700-6719`）。不建议新增数值；branch-point 后「停的频率」由叙事者判词分布决定，读数靠刀 N 的 `stop_kind` 落盘（若要分布统计，一个 app_setting 计数器 +5–10 行，随刀 B 顺手）。

**lr-4a 全停的退出条件**（scaffold 何时退场）：
1. **dogfood 疲劳信号**：用户连按「让世界继续」而不选走向（continue 次数 ≫ 走向选择次数——parking row 的 `stops` 字段已持久化，`web.py:6536`，差一个观察读出）；或用户显式反馈「停太多」。
2. **叙事者判词分布成立**：dogfood 样本中 directed 停词呈 `none` 多数 / 停词少数的分布（若叙事者几乎每步都判停，方案甲退化为每步停——那时该修的是 prompt 判词教学句，不是 park 条件）。
3. **保守默认的边界**：在 1/2 任一成立前，lr-4a 每步停**维持现役**——第十一击的判词（`AGENTS.md:93`：「每一个选择点就应当决定接下来一步的走向」）是现行为的最强背书，方案甲的落地必须以用户对「少停」的实际接受为准，不做无信号的默认翻转。

**推荐方案与风险**：采方案甲。风险两条：
- **假阴性（该停不停）**= 用户失去掌控感（MH-1 担心的反面）。缓解四层：候选仍在每一帧上（directed 帧带 directions，`web.py:3734-3742`）、自由走向通道常开（lr-3）、`awaits_you` 是叙事者可给的硬停保底、单请求链上限 5 步封顶失控窗口。假阴性的最大代价 = 一个请求内多走 1–4 步（十几秒量级），可逆、可反馈。
- **假阳性（不该停乱停）**= 退回现状，无害方向。

### 5.3 no-reply 刀（刀 N）任务书轮廓建议

- **范围**：①coordinator 新公共面（如 `close_parked_turn_without_reply(turn_id)`）：lease 持有 + guard + CAS `terminalize_turn(NO_ASSISTANT_OUTPUT)`（`store.py:646-705`）+ CP4 投影跑否的预裁（建议跑——与 `begin_turn` 完成路径对齐 `controller.py:1599-1602`，recorder/episode 已容无 assistant）；②web 顶替臂：`turn()`/`turn_stream()` 在已有 parking row 时先关旧轮再铸新轮（`web.py:3270-3315, 3380-3494` 入口处）；③web awaits_you 臂：`continue_world_stream` 判 `stop == awaits_you`（`web.py:6773-6782` 邻位）→ 关轮 + 清 row + payload 终形（无 parked 键、带 `stop_kind`）；④row/payload `stop_kind` 落盘与透传（§3.3）；⑤前端分型（awaits_you 形 / NOTICE 形 / 现役 DIRECTION 形）。冻结面零触碰；沉浸行为零改动（R6 钉不动）。
- **路径集（VAL 用）**：`src/elc/web.py`、`src/elc/runtime/controller.py`、`src/elc/webui/app.js`（+ 文案双语表）、`tests/host/`（新钉文件 + `test_lr4a_parked_rounds.py` 随迁）。
- **测试面建议**（约 10–16 例）：①awaits_you-directed 关闭全链（COMPLETED + `NO_ASSISTANT_OUTPUT` + row 清 + history 无 parked 键 + continue 409 + 新信开新轮且世界 run 恢复）；②顶替臂（新信后旧轮关闭——即 §7 探针的负形）；③she_thinks_of_you 分型（停 + 无候选可续）；④letter_arrives 回归（现役钉零降强度）；⑤重启面（关闭轮重启后不被扫描点名、row 已清不可重入）；⑥恢复扫描负钉（`_close_residual_turns` 不误关）；⑦前端刷新重建（awaits_you 形从 history 重建）；⑧沉浸零改动回归；⑨store 级状态机钉（`NO_ASSISTANT_OUTPUT → COMPLETED`）；⑩上限/豁免臂回归（`MAX_PARKED_STOPS` + lr-3 双形）。
- **验收组建议**（六至七组）：任务书符合面 / 契约钉面（§1 引文逐条）/ 行为钉面（含顶替负钉）/ 回归面（lr4a/wr10/lr3/wr8 既有钉全绿 + 逐值读数）/ 重启与恢复面 / 前端呈现面 / 变异面（关闭面拆掉→悬挂复现 RED；stop_kind 拆掉→透传断 RED）。

### 5.4 台账核对（单一台账律，四查⑤）

P14 行（`docs/design/2026-10-08-cognition-and-narrative-quality.md:145`）触发条件「**lr-4 评估同场**」被本刀命中，三项的核对结论：
1. **F-2 消费即清输入丢失窗口**（走向已存、进程死在步落地前 → 输入丢）：与刀 N 的 continue 面直接相邻（消费点 `web.py:3696-3706`）——建议**并入刀 N 的 continue 臂**一并取证（若修复，量级 +10–20 行；若维持后置，刀 N 登记一行显式改判）。
2. **wr-7 F-L1 提取器增量 flush**（流式中断丢尾块）：呈现层，与 stop 轮契约正交——维持原触发（dogfood 信号）。
3. **wr-11 INFO-1 违约挂起**：同上，维持原触发。
P16/P17 与本刀无交（P16 落点 C1；P17 落点学习桥验收刀）。其余台账行无命中。

---

## 6. 探针与证据（仓外，`D:\_lr4_spike\`）

**探针 P-1：`probe_superseded_parked.py`（2026-10-09 跑，真 web 栈 = 真 `run_web` + 真 `open_host`，DB 在 `D:\_lr4_spike\tmp\probe-superseded.db`，仓内零写入）**

场景：directed 模式，第一封信停点（parked）→ 第二封信（新 client_message_id）→ continue 到信到回信。机器读数：

```
[1] first letter final: parked=True stop=awaits_direction turn_id=turn-562b…; turn rows=[(turn-562b…, GENERATING, None)]; parked rows: 1
[2] second letter final: parked=True; turn rows=[(turn-562b…, GENERATING, None), (turn-5c5b…, GENERATING, None)]; parked rows: 1（覆写非新增）
[3] continue final: reply 落地 status=COMPLETED; turn rows=[(turn-562b…, GENERATING, None), (turn-5c5b…, COMPLETED, REPLIED_FULL)]; parked rows: 0
[4] history：无 parked 键；turn0 assistant=None（永缺）；turn1 回信在
verdict: {"orphan_confirmed": true}
```

**结论（机器实证）**：被顶替的 parked 轮永久滞留 GENERATING、无任何关闭臂触达——§2 第 9 行「待改」的判定的直接证据，刀 N 顶替臂的负形（关闭后此格必为 COMPLETED/NO_ASSISTANT_OUTPUT）可直接以本探针为 RED 基线。

**其余调查方法说明**：本评估其余结论来自仓内代码/文档/测试的静态精读（引用逐条 文件:行），未跑其他探针；测试数与门读数不在本刀范围（零代码刀不动门）。

---

## 7. 异议与登记

1. **任务书 §22 指针与正典实测不符**：任务书面①写「docs/DATA_MODEL.md §22（Transcript Data）」，实测 `docs/DATA_MODEL.md:1209` §22 = **Delivery Data**；转写契约正典在 §3/§4 + `docs/STATE_MACHINES.md` §10 + `docs/DOMAIN_MODEL.md:84`。本面按正典位置评估（题目实质不受影响），在此留痕。
2. **任务书「narrator.py:635-640 一带」的词表位置为近似**：词表常量实在 `src/elc/world/narrator.py:180-189`，prompt 教学句在 :630-638（letter_arrives 句）与 :679-691（stop 形状/说明），解析在 :996-1015——本文一律引实测行。
3. **DEC-95/DEC-128 简称的展开**：仓内引用形为 `DEC-OPI-c73dbff3…95`（lr-1 自然运转链，`narrator.py:171`）与 `DEC-OPI-c73dbff3…128`（lr-4a，`web.py:2316`）——本文按仓内展开引用。
4. **§4 沉浸 awaits_you 的「不回信」形需要总控复裁**：沉浸链在轮提交**前**跑（WR-6 序），「世界停 + 不回信」在沉浸需要把停点挪进提交序——超出本刀评估授权，本文给了第一版收窄语义（停在「不再续步」、照常回信），定谳归开工裁决。
5. **量级为静态估算**（行级、src-only 口径、含 docstring），非机器读数；落地刀超带须按判例披露。
