# 活世界 M0.1 · 工程对齐与建设方案（架构勘误版）

> 依据：`living-world-spec.md` **v2.1**（外审终裁 PASS）+ **M0 架构勘误（外审 NEEDS ONE ARCHITECTURE CORRECTION，2026-10-05，四项全验证成立）**。
> 性质：M0 交付物——spec 到工程的映射、架构决策、刀序与依赖。**每把刀开工时仍走完整开工三件（DEC/VAL/TASK）**，本文是母蓝图。
> 工程现状基线：master 本地全量 5158/0/0（**CI 红灯见 §6**）；迁移 head 0020/v20；mypy **174**（M0 原文 173 系账面错误）。

---

## 1. 现状对齐表（spec 机制 × 现役系统 × 动作）

| spec 机制 | 现役锚点 | 动作 |
|---|---|---|
| 世界（第一公民/存档单位） | 无 | **新建**：`world` 表（迁移 0021）+ `elc/world/` 域 |
| 事件树/编年史 | 无 | **新建**：`world_event` 表（事件史唯一载体——记忆与状态两个投影的源头） |
| 记忆温度三层 | episode（角色侧折叠记忆） | **升级+新建**：episode 保留为角色记忆底料；世界侧新建温度投影（world_event 上的温度/唤起计数 + 压缩摘要列） |
| 世界状态投影 | **world_lore_fact（ACTIVE/superseded）** | **复用扩格**：scope 语义已含 world/character；冷层事实沉降即写入此表，supersede 链直接用——主线-3 的域就是世界状态投影的家 |
| 运转引擎（七步/checkpoint/揭示） | planner（确定性编排先例）、runtime coordinator | **新建**：`elc/world/engine/`（确定性编排 + checkpoint 状态机 + 揭示队列） |
| 特殊时刻协议 | 无 | 新建（engine 内的时刻类型学 + NOTICE/RESPONSE/DIRECTION 状态机） |
| 通信编排（谁何时写信） | 无（被动回复制） | **新建**：编排调度面（确定性规则：近况×剧情×间隔） |
| 回信生成 | PersonaRuntime/PromptCompiler（现役） | **复用**：世界上下文装配进 compiler（新增 [world] 节，UNTRUSTED carrier 同 [lore]） |
| 纠错天线 | detection 链（EV 36） | **复用**（现役不动） |
| 意图天线（中文→值不值得教） | 无 | **新建**：判定器（模型调用面，新 provider 判定端点或复用 call 的结构化输出） |
| 索取天线（教我） | teach_me/词卡 | **升级**：点选对象扩展（句/事件卡），进教学流程 |
| 教学贴合候选 | 无 | **新建**（候选生成受供给域约束） |
| affordance 声明 | 无 | **新建**：世界包的组成节 + 93 R4 按域聚类的映射素材 |
| 世界包 | 角色包（official.py）、lore content | **升格新建**：`worlds/` 内容格式（设定+阵容+事件池+剧情线+贴合映射+供给声明） |
| 多世界/世界架/出入场 | mc-0 多角色（现役） | **升级**：world 为容器、角色入世界阵容；出入场叙事化事件 |
| 可见性梯度/走向 UI/时刻呈现 | webui | **新建**（M3 起；与在飞前端包的关系见 §4） |
| 揭示/积攒等待 | 无 | 新建（揭示队列表 + 进入应用时的呈现触发） |

## 2. 架构决策（M0 裁决，四条）

**AD-1 conversation 兼容路线（保守叠加）**：现役「每角色一线 conversation」管线**不动**；世界层叠加其上——`world` 表持有阵容与事件树，信件仍走现役 conversation 管线；「世界收件箱」= 世界维度的**聚合读面**（新读端点），不改写面。理由：5158 例的现役管线是资产；世界重构通信 schema 的收益不抵风险。

**AD-2 编排确定性、生成模型化**：七步编排中「事件判定/通信编排/时刻判定」是**确定性代码**（规则+权重+池+种子随机）；模型只做**文本生成**（事件叙述/回信内容/摘要压缩），全部经现役 provider 面与 fail-即-值纪律。与仓内 planner（确定性）/persona（模型）分层精神一致。

**AD-3R（M0.1 撤销原 AD-3）静态 lore ≠ 世界状态，分表**：外审核验成立——`world_lore_fact.status` 是 **P-INV-013 审批生命周期**（ACTIVE=canonical 可见 / PENDING=未信提案），**无 SUPERSEDED**；且表**无 world_id**（`scope='world'` 的语义是「common to every conversation」——多世界并存时 Manchester 的对话能读到 Berrymoor 的事实，串世界）。故：
- `world_lore_fact` 保持其本职：**静态 canonical lore**（「这个世界**是**什么」——Berrymoor 是港口小镇），世界包携带、按世界实例隔离的问题由 W-1-0 的绑定解决（lore 随世界包走）；
- **新建 `world_state_fact`**（世界状态投影的家）：`world_id / source_event_id / canonical_key / statement / status(CURRENT→SUPERSEDED)`——「这个世界**现在怎样**」（Alder & Son 的屋顶目前损坏）。事件→状态沉降在 W-1-1 落最小面（见刀序修正）。

**AD-5（M0.1 新增）身份绑定三表**：`world`（世界实例）/ `world_actor`（world_id + persona_id——「这个世界里的她」：角色模板身份 ≠ 世界内实例，模板分叉出的两个 Berrymoor 各有一个 Nell 实例）/ `world_conversation`（world_id + world_actor_id + conversation_id——现役 conversation 管线的纯外缝绑定，AD-1 保守叠加的具体形状）。W-1-0 一次钉死三表，否则 W-1-3 收件箱与 W-3-1 多世界必然回头改主键。

**AD-6（M0.1 新增）World Run 必须 durable**：checkpoint 跨重启恢复是架构原则非实现细节——`world_run`（run_id / world_id / trigger_turn_id / seed / status / checkpoint_kind / cursor / state_version），与现役 TurnRecord/epoch/state_version 纪律同构；用户点「继续」不得重新掷骰。W-1-2 落表。

**AD-4 域划分**：`elc/world/`（世界聚合：world/event/storyline/store）+ `elc/world/engine/`（运转编排/时刻状态机/揭示队列/通信编排）+ `elc/world/affordance.py`（供给域）+ `worlds/`（内容包，与 content_src 平级）；意图天线落 `elc/teaching/`（教学域内新面）；记忆温度投影落 world 域（world_event 上的投影函数，非独立存储域）。

## 3. 刀序（M1–M4 工程化，17 刀——M0 原文「14」系账面错误，M0.1 对账）

> 依赖：→ 线性依赖；‖ 可并行。每刀验收形态同现役纪律（VAL/TASK/独立评审/处置/章）。

**M1 最小活世界——「她活起来了」**
- **W-1-0 世界域骨架**：迁移 0021（**world + world_actor + world_conversation 三表一次钉死**，AD-5）+ `elc/world/` 域 + host 装配 + census 行 + conftest 随迁族。〔工程面刀，量级：mc-0 同型〕
- **W-1-1 事件树与最小状态投影**：world_event 表（append-only）+ 编年史读面 + **world_state_fact 最小投影（M0.1 前移自 W-4-1）**——预制事件显式携带 state effects（storm → roof=DAMAGED），不待智能派生；CURRENT→SUPERSEDED 基本链。→ W-1-0
- **W-1-2 运转引擎 v1**：七步编排骨架（确定性；RESPONSE terminal + NOTICE checkpoint 双出口；事件从预制池条件选择；种子随机可重放）+ 时刻状态机。→ W-1-1
- **W-1-3 揭示与节奏**：揭示队列 + 通信编排 v1（间隔规则）+ 世界收件箱聚合读面（AD-1）。→ W-1-2
- **W-1-4 世界包 v1（Berrymoor）**：`worlds/` 格式 + Berrymoor 包（设定/阵容 Nell/首批事件池/供给声明）+ host seed 幂等。→ W-1-0 ‖ W-1-2

**M2 剧情与教学咬合——「学习藏进了世界」**
- **W-2-1 剧情线**：storyline 结构 + 开启/推进/收束 + 记忆挂架。→ W-1-2
- **W-2-2 走向与双模式**：DIRECTION checkpoint + 候选四源生成（随机/贴合/剧情线/自由输入）+ 导演/沉浸模式设置。→ W-1-2
- **W-2-3 记忆与预算**：温度投影（分层/压缩/遗忘）+ 三指针唤起 + token 分层装配 + [world] prompt 节。→ W-1-1
- **W-2-4 教学天线 v1**：意图判定器 + 教我扩展 + 贴合候选（供给约束）+ 三层并存。→ W-2-2 ‖ detection 现役
- **W-2-5 潜入层与延迟教学**：标记渲染 + 高潮降权 + 事后跟进。→ W-2-4

**M3 多世界与编排——「你是造物者」**
- **W-3-1 多世界**：world 多实例 + 世界架读面 + 跨世界揭示积攒。→ W-1-3
- **W-3-2 世界创建三档**：直用/模板分叉/自建（塑造式 affordance：期望域→设计辅助→派生验证）。→ W-3-1
- **W-3-3 出入场叙事化**：阵容管理 + 入/退场事件生成 + 世界原生绑定强化。→ W-1-4
- **W-3-4 联动与互联**：联动事件 + 关系预设/演化 + 传闻视角 + 传话玩法。→ W-2-1

**M4 记忆深化与打磨——「世界有了自己的生命」**
- **W-4-1 状态投影深化**（M0.1 收窄：最小面已前移 W-1-1）：自动事件→事实派生（非显式 effects）+ 复杂 supersede 推导 + 与 lore 共存的完整语义。→ W-2-3
- **W-4-2 标定面**：密度/时刻配比/预算的 calibratable 参数 + 用户实测工具（观察仪表扩展）。→ W-1-2
- **W-4-3 可见性与叙事外衣**：四档梯度渲染 + 画龙点睛阶段的外衣形态。→ W-1-3

## 4. 与在飞线的整合

- **前端包（frontend-revamp，用户执行者在飞）**：五问题+动画**不含**活世界 UI——无文件冲突；活世界 UI 面（世界架/走向/时刻呈现）在 W-1-3 起进入 webui，**建议活世界刀的 webui 触碰等前端包合并后再开**（W-1-0…W-2-2 的 src/面可先行）。
- **主线-4 rollout 链**：独立件不受本方案阻塞；活世界教学天线中纠错/意图/索取均**不依赖** rollout 开闸；开闸后的自动教学与贴合候选的正交性在 W-2-4 裁决时定。先后或并行由用户定向。
- **Backlog G 组**：并入本刀序（A3=W-1-3 揭示与节奏的实现面）。

## 5. 风险与开放工程题

- **量级诚实**：17 刀 ≈ 一整个 Phase 的量级（对照 Phase 8 五刀/Phase 11 十余刀）；建议按 M 台阶分相位入册母计划。
- **模型调用面扩展**：意图判定器与摘要压缩是新增模型用途——出网纪律（单出网点）与 fail-即-值沿用；判定端点的成本与延迟需在 W-2-4 评估。
- **确定性纪律延续**：编排可重放（种子随机）、内容包构建确定性、跨进程字节钉——全刀沿用现役四查/VAL/验收链纪律。
- **开放题**（各刀裁决时定）：事件池的持久化与热更、世界包版本化、揭示队列与多端打开的幂等、供给域聚类首轮映射的落点（content 侧 or worlds 侧）。

---

## 6. CI digest 对账（M0.1 新增，外审核验成立）

**事实（总控亲验）**：CI 连续红灯（`gh run list` 三连 failure）；失败测试 `test_the_default_build_stays_zero_ev_and_byte_identical_with_the_parent`——provenance 断言（100 实体/EV 0/EDITOR 46/AUTHOR 54）**全过**，唯 sha256 不等（CI `3da60bc…` vs 钉 `90932ab…`）；本地同提交全量两跑 5158/0/0。工作树与 git blob 双纯 LF（CRLF 排除）；CI 与本地同为 Python 3.13。

**根因（高置信）**：**sqlite3 库版本差异**——本地 sqlite 3.45.3（Windows），CI 为 Ubuntu 系统库（不同 minor）。SQLite 文件**字节不跨库版本稳定**（页内结构/空闲页细节随库版本变），同源同序插入产出不同字节。内容逻辑逐项相同（provenance 全绿即证）。

**M0 原判错误自认**：M0 将 CI 预警记为「本地不复现、疑外审环境差异」——**错误**：本地当然不复现（同库版本），红灯在跨环境才显。且队列③处置刀起 CI 即红而总控只跑本地未查 CI——**验收纪律漏洞**：处置刀后应核 CI。现已补纪律：**凡重导 digest 钉的刀，收口必须核 CI 绿**。

**修复方向（对账刀，W-1-0 前置，待铸）**：字节钉改为**语义 digest**——确定性行序导出 + 规范序列化的内容哈希（与库版本无关，跨环境稳定）；保留内容漂移检测力（任何内容变动仍红）。附 CI 诊断输出（python/sqlite 版本打 into 日志）。

## 7. mypy 基线对账

M0 原文 173 系账面错误：本地与 CI 均 **174**（主线-3 合并后即 174，总控台账未随迁）。

## 8. M0.1 变更总目

| # | 项 | 性质 |
|---|---|---|
| 1 | AD-3R：lore ≠ state 分表（world_state_fact 新建；world_lore 保持静态本职） | 撤销原裁决（外审验证成立） |
| 2 | AD-5：world / world_actor / world_conversation 三表身份绑定（模板≠实例） | 新增 |
| 3 | AD-6：World Run durable（跨重启恢复/seed/游标/state_version） | 新增架构原则 |
| 4 | 刀序：最小状态投影前移 W-1-1；W-4-1 收窄为深化；17 刀对账 | 修正 |
| 5 | CI digest 根因（sqlite 库版本）+ 语义 digest 修复方向 + 验收纪律补（重导钉必核 CI） | 基线修正 + 纪律 |
| 6 | mypy 174 对账 | 账面修正 |
