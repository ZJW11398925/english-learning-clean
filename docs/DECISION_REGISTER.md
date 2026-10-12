# DECISION_REGISTER.md

> 索引文件；详细语义以六份 canonical 文档与本包 behavioral regression assets 为准。

## Frozen / Baseline

- EvidenceGroup + EvidenceClaim；Performance Type + Qualifiers；UNKNOWN first-class。
- Learner State key = Target × EvidenceModality；GoalModality 与 InteractionChannel 分离。
- Estimator Behavioral Baseline V1：deterministic/model-free、PARTIAL mixed evidence、cluster diminishing returns、transfer/support dependency derived。
- Planner Behavioral Baseline V1：canonicalize → feature completeness → hard eligibility → utility → activation → request priority → Pareto → deterministic tie-break。
- NO_TARGET first-class；Planner failure/degraded 不伪造 NO_TARGET。
- Teaching Gate 只做 execution authorization；OPEN=DecisionCycle authorization，continuation=ActiveMoment authorization。
- One Focus Target；TeachingMoment bounded；full reveal 不产生当前 Moment independent evidence。
- ServerDelivery / ClientRenderAck / ExposureEstimate 分离。
- TurnTransaction = saga + short commits；external at-least-once/uncertain，internal exactly-once canonicalization。
- Current-user Evidence before normal Planner；same-turn switch 可新 DecisionCycle。
- ConversationCoordinatorLease / TeachingLockLease 是逻辑 contracts；Local V1 分别用 keyed mutex/runtime_epoch 与 durable active lock row。
- app.db mutable state；content.db read-only；SecretStore secret values。
- Security/Privacy baseline：untrusted content proposal-only、minimal provider disclosure、provenance-aware deletion、tombstones。
- Speaking/Listening goal 可存在；无 voice/audio runtime 时不生成 direct evidence、不累计 impossible direct CoverageDebt。
- Golden Scenario Baseline V1 是实现回归门。

## Calibratable / Versioned

- Estimator numeric profile
- Planner weights/thresholds/coverage service bonus
- budget/cooldown/hard-cap counts
- freshness/review windows
- streaming/validator tuning

任何变更必须 bump profile/version 并跑 behavioral + golden regression。

## Explicitly Deferred

- full live voice/audio runtime
- multi-character Scene Runtime
- cloud multi-device sync
- multi-process/distributed coordination profile
- advanced probabilistic/IRT mastery model
- large content expansion beyond validated calibration

## Version History

### v1.0.1 — 2026-09-20 例外修订（授权：DEC-d5b616bf.3）

状态：`IMPLEMENTATION_BASELINE_V1` → `IMPLEMENTATION_BASELINE_V1_P1`（docs/manifest.json `status` 字段同步）。

内容（两处、均为白名单化而非语义变更）：

1. `behavioral_baselines/runtime/run_local_runtime_tests.py` 两行 f-string SQL
   （`SELECT COUNT(*) FROM {table}`，出现于 `cp2_rollback` 与 `cp2_success`）
   改写为按表全字面量 SQL 的 `_COUNT_SQL` 白名单字典。理由：表名不可参数绑定，
   f-string 形式违反仓库"SQL 参数绑定或全字面量"红线；四条语句的表名与
   语义完全不变。
2. `docs/manifest.json` 重钉受影响文件哈希（run_local_runtime_tests.py、
   local_runtime_test_results_v1.json、test_summary.json），并升级 status。

授权与例外性质：本次修订由外部例外决策 DEC-d5b616bf.3 显式授权，是 v1.0.1
唯一一次对 behavioral_baselines `.py` 的修改（两行）；除此以外基线
`.py` 保持字节冻结。`local_runtime_test_results_v1.json` /
`test_summary.json` 的 36/43 记录是打包作者 Windows 环境的运行读数，
仓库真相以 CI 重放读数为准（见 behavioral_baselines/runtime/REPO_RUN_NOTES.md
与 tests/behavioral/test_local_runtime_reference.py）。

### v1.2.0 — 2026-10-12 范式转折（Narrative V3；授权：用户交接 2026-10-12）

状态：工程基线（Phase 0–10 runtime 面）不重写；新增叙事域程序 **Narrative V3**，现役世界链（letter-triggered `world_run` / NOTICE·RESPONSE 停点 / reveal 推进 / 每步 direction / WorldNarrator 单体）降 **legacy 保留**（不删、测试不拆、继续全绿；退役须待新纵向切片完整后显式裁决）。

内容（四份文档同刀）：

1. 新增 `docs/design/2026-10-12-narrative-v3-paradigm-shift.md`——范式声明（新核心循环 + 旧理解七条废止/降级）+ 职责分离（World Director / Chapter Blueprint / Scene Planner·Dossier / POV Writer / User Gate / Action Resolver / Chapter Settlement）+ Plan≠Canon + story_tick 时间模型 + Passage≠Event + 记忆六分（温度降为 retrieval policy）+ durable 用户角色与 WorldActorProfile + Narrative Domain 实体清单 + 并行新链迁移原则 + 第一阶段 slicing（V3-0..V3-8；Gold Scenario 帝国历 105 年 10 月 1 日）+ 附录 A 旧→新映射审计 + 附录 B 十问自检。
2. `docs/design/2026-10-05-living-world-spec.md` 升 v3——头部范式转折节（信件降为 UI/narrative presentation element；§2/§4 等旧条款降 legacy）+ v3 变更清单；逐节处置见新篇附录 A。
3. `docs/design/2026-10-08-cognition-and-narrative-quality.md` 升 v1.3——域一重挂（Actor Memory/Belief 独立域；温度→retrieval policy；台账 P1 落点改判）；新增域五（叙事限知与 POV 纪律）与域六（叙事记忆）；域三/域四保留、注入面迁 POV Writer。
4. `docs/IMPLEMENTATION_PLAN.md` §20——Narrative V3 程序（原则六条 / 第一阶段 slicing 表 / Gold Scenario / MVP 规模纪律 / 与既有 Phase 的关系：Phase 0–10 不动，真实 rollout HOLD 不变）。

不变：教学系统、用户配置与安全边界、persona 生成基础、Local V1 运行时纪律、Golden Scenario Baseline V1（工程回归门）与全部 behavioral baselines 继续有效。`Explicitly Deferred` 的 multi-character Scene Runtime 指「完整多角色场景运行时」——Narrative V3 MVP 仍为一 AI 主角 + 一用户角色，该条维持。

### v1.2.1 — 2026-10-12 V3-0R 设计修订（外评 PASS WITH DESIGN CORRECTION）

状态：Narrative V3 设计收口稿升 **v3.1**；**V3.0 冻结待复核**（复核通过前不开 V3-1，更不写代码）。

内容（六项修订 + 三项追加，落 design 三件 + `IMPLEMENTATION_PLAN §20`）：

1. **结算两级（HIGH）**：**SEGMENT/SCENE COMMIT** 为唯一微观事实落地边界（正文段 / Action 裁定结果**即时**入正史）；**Chapter Settlement** 降为压缩与收束（摘要/线推进·收束/hooks/显著性/章关闭/下一章输入包）。修正原「Settlement 是唯一沉淀边界」表述（设计篇 §2.7/§八/十问第 2·3·5 问）。
2. **World Bible 权威独立（HIGH）**：`world_lore_fact`（0020 无 `world_id`；`scope=world` 为「所有会话共有」旧语义）**不作 per-world Bible 存储**，legacy 保留；只复用 authority/proposal 思想；方向 = World Bible → projection/adapter → legacy lore view。`world_bible_revision` 自带 `world_id`/`revision` 与 premise/genre/tone/calendar/physics/magic_rules/geography/society/politics/technology/religion/history/hard_rules/narrative_preferences。
3. **WorldActorProfile 入 V3-3**：V3-3 扩为「**World Cast & Player Identity**」（`world_actor_profile` + durable player character + participant namespace）——Director 的 cast 输入（谁是主角/可 POV/长期弧）在 V3-4 之前齐备。
4. **Reader Exposure 本体**：三种知道 = WORLD TRUTH / ACTOR KNOWLEDGE / READER EXPOSURE；`narrative passage exposure ≠ actor cognition`，绝不自动写入 Player Character Memory（实现可后置，本体先行）。
5. **时间语义**：`story_tick` = **整数世界时间单位**（数据层唯一形态；World Calendar 解释显示，不依赖地球公历；MVP 粒度 V3-1 钉死）；**planned_start/end_tick（Plan）≠ actual_start/end_tick（Canon）**。
6. **canonical 隔离**：living-world-spec §2/§4 重标题**【Legacy V2 Runtime】**、术语表拆 **V3 / Legacy V2** 两表（撤销「全稿唯一定义处」）、受影响节加【v3 处置】标注（旧文不删）。

追加三项：**Blueprint 措辞律**（`desired_closing_state` → 软期望集 `closing_pressure`/`desired_development`/`soft_outcomes`/`chapter_questions_to_advance`；硬条件只允许世界规则/已发生因果/不可撤销事实）；**V3-8 结构验收 12 条**（「好玩」为唯一用户门但**不作唯一工程门**）；**刀序微调**（V3-1 Narrative foundations〔story_tick + chapter/scene 生命周期类型 + Plan/Canon 边界类型〕/ V3-5 含 SEGMENT COMMIT / V3-6 含 OUTCOME COMMIT + replan / V3-7 = Actor Memory + Chapter Settlement）。

授权：外评（用户转呈，2026-10-12）「PASS WITH DESIGN CORRECTION」；DMCP 决策 `DEC-OPI-bab4da9f-…9`。

### v1.3.0 — 2026-10-12 V3-1 实现合同（design-first；授权：V3-0R 复审通过 + 用户批准进入 V3-1）

状态：**Narrative V3 产品范式与高层架构正式冻结**；V3-1 以 design-first 开工——实现合同先写入四份 canonical 实现文档，**再**设计 migration（0029+）与 V3-1 代码（不得边写表边反推 authority）。

内容（四份文档同刀；语义冻结，具体 DDL 留待 V3-1 migration 设计）：

1. `DOMAIN_MODEL.md` §20（并 §1/§2 增行）—— Narrative（World）Domain 升为第一层；authority 明细表；**六条硬边界**（Resolver 唯一裁定权 / V3-5 最小 commit 不依赖 V3-7 表 / 两级提交语义 / 生命周期 / story_tick 粒度与写权 / 模板≠实例 Bible + Reader Exposure 只冻结本体）；不变量 N-INV-001..008。
2. `STATE_MACHINES.md` §21–§27 —— Chapter（PLANNED/ACTIVE/SETTLING/CLOSED）、Scene（PLANNED/ACTIVE/COMMITTED/CLOSED/DISCARDED；**有段落即不可取消**）、User Gate（OPEN/ANSWERED/RESOLVING/COMMITTED/CLOSED；一次 submission、无取消）、Plan Revision（PROPOSED/ADOPTED/SUPERSEDED/REJECTED；append-only 版本化）、**两级提交的原子组与崩溃重试**、story_tick 规则（MVP 1 tick = 1 分钟；actual 只在提交事务）、非法转移清单。
3. `DATA_MODEL.md` §26.2 —— V3 实体语义合同（`world_bible_revision` / `world_player_character` / `world_actor_profile` / `world_chapter(_plan)` / `world_scene(_dossier)` / `narrative_passage` / `user_gate` / `user_action` / actor memory·belief / `chapter_settlement` / `reader_exposure`）、时间字段律、**V3-5 最小读路**（`world_event`+participants+C1 认知视图）、幂等键集、可重建投影。
4. `RUNTIME_ARCHITECTURE.md` §27–§30 —— V3 管线（Director→Blueprint→Scene/Dossier→Writer→Gate→Resolver→两级 commit→Settlement）、**NCP-1..NCP-4 提交点与崩溃窗口**、V3 recovery 扫描面、不变量 N-R-INV-001..008。

V3-1 验收重点（用户明令）：同一世界 Plan/Canon 类型隔离、时间单调、状态机合法、两个 commit 原子边界成立、崩溃后不重复用户行为裁定、旧 Narrative V2 链继续全绿。

授权：用户（2026-10-12）——V3-0R 复审通过、范式冻结、批准进入 V3-1（design-first）；DMCP 决策 `DEC-OPI-bab4da9f-…11`。

### v1.3.1 — 2026-10-12 V3-1 合同 + migration 独立评审处置（PASS WITH CORRECTIONS → 放行）

**评审结论**：独立评审（新上下文只读）对四份 canonical V3 节 + migration 0029 设计 + 搬迁清单给出 **PASS WITH CORRECTIONS**，并**明确放行 migration 与 V3-1 代码实现**（修正随 V3-1 同刀落盘后生效）。INFO 核证：0029 忠实（CHECK/UNIQUE/FK 与 STATE/DATA 逐字）、最小（无提前/漏落面）、存量兼容（`current_tick` ALTER 安全）；**不迫使 V3-5..V3-7 重拆数据模型**；无静默转绿漏钉。

**内容的更正与补充**（评审 M1–M6 / L2 / L4 处置；四份文档已同步）：

1. **M1 计数更正**：DOMAIN §20.3「六条」→「**七条**硬边界」（编号实为 1–7；§20.3-6 模板条引用不变）。
2. **M2 验收改标（更正 v1.3.0 的 V3-1 验收行）**：V3-1 本刀验收 = 同一世界 Plan/Canon 类型隔离 + tick 单调 + 状态机合法 + 旧 V2 链全绿 + 两 commit 的**类型与幂等键基础**就位；「两个 commit 原子边界成立 / 崩溃后不重复用户行为裁定」= **V3-5 / V3-6 兑现门**（V3-1 无 passage/gate/action 表，物理上不可测）。
3. **M3 补句**：`user_action` 增 `actual_tick`（ACTION 族 Canon 时间锚）；DATA §26.2.2 增「V3 事件叙事时间 = 其提交事务的 actual tick，经派生键连回（SEGMENT→`narrative_passage.created_at_tick` / ACTION→`user_action.actual_tick`）；不为 `world_event` 增 ISO/tick 列」。
4. **M4 补句**：**SCENE COMMIT = 场的最后一段 SEGMENT COMMIT 的别名**（`ACTIVE→COMMITTED` 与提交同事务），非第三种事务（STATE §22/§25）。
5. **M5 补句**：RA §28 NCP-1 原子组 = {`user_gate` OPEN→ANSWERED；`user_action` 建 ANSWERED 行（intent_text / submission_id）} **同一短事务**；DATA §26.2.4 增 action 族 event/outcome id 由 `action_commit_key` 派生。
6. **M6 搬迁清单更正**（归任务书）：补 `tests/world/test_c2_storylines.py:172/174/175/181`、`tests/world/test_w13_reveal_and_inbox.py:171/174/176/180`、`tests/host/test_c1a_chronicle_attribution.py:194–197`（stamps 两处）；全量面以 `grep -rn '"0028\|== "28"\|== 28\b' tests/` 为准（**51 处字面钉**）。**L5 裁**：四张新表随刀入 **`GLOBAL_CONTENT_TABLES`**（world 系 keep 集惯例，`src/elc/deletion/types.py:334-340` 同区），`tests/deletion/test_deletion_surfaces.py` 的表元组钉随迁。
7. **L2 措辞**：DATA §26.2.2 前缀律改实质表述（Plan 面带 `planned_` 前缀；Canon 面一律 tick 语义、禁 ISO；字段名可含 `opened_at_tick`/`created_at_tick` 等）。
8. **L4 钉**：`reader_exposure` 建表刀位 = **V3-5** 与 `narrative_passage` 同刀（与 NCP-3 原子组一致）。

**登记（后刀落点）**：**L1**（0029 DDL 定稿三处：`CHECK (state_version > 0)`、文件尾双 stamp INSERT〔schema_version/runtime_schema_version → '29'〕、PLAN 行补 `updated_at` + `state_version`）归 V3-1 任务书定稿；**L3**（Blueprint `scenes`(JSON) ↔ `world_scene` 行对账规则）落点 = **V3-4 开工四查**。

授权：独立评审（executor-pro 新上下文只读，2026-10-12）+ 用户口径「合同合理即放行迁移与代码」；DMCP 处置决策 `DEC-OPI-bab4da9f-…16`（注：本条目初稿预填 `…15`，服务器实际分配 `…16`——如实更正）。**V3-1 状态：允许开工；三件已铸（TASK `…18` / VAL `…20`），executor-pro 已派单。**

### v1.3.2 — 2026-10-12 V3-1 外审（ACCEPT WITH FINDINGS）+ 五项跨刀义务处置

**结论**：V3-1 **维持 COMPLETE**（不重开）；无 HIGH；批准进入 V3-2。五项跨刀义务（外审新增）全部收讫入册——#2/#5 即修文档；#1/#3/#4 写入合同并标注执行刀位：

1. **V3-5 硬门 #1：Narrative Event story-time attribution**——`world_event.occurred_at` / `chronicle_of()` 属 **Legacy V2 ISO 语义**，而 V3 唯一时间权威是 `story_tick`；V3-5 接通 Segment Commit / C1 cognition 前必须建立**显式 V3 event lineage + story-time read path**（提交记录表面），**禁止以 opaque event-id 命名规则反推**，V3 cognition 不得把 legacy `occurred_at` 当世界时间。**已入合同**：`DATA_MODEL §26.2.2`（lineage 要求 + legacy 禁入语）+ `§26.2.4`（id 派生只服务幂等重放的收窄）。
2. **V3-5 硬门 #2：Reader Exposure 与 Canon Commit 解耦**——passage commit ≠ 用户已看见；删除「NCP-3 同事务即代表呈现」语义；exposure 需独立 delivered/rendered 记录或保守 estimate（RA §14 certainty 家族）；**DB commit 不是 reader knowledge**。**已入合同**：`STATE_MACHINES §25`（移出 SEGMENT COMMIT 原子组 + 解耦注）+ `RUNTIME_ARCHITECTURE §28` NCP-3 + `DATA_MODEL §26.2.1`（reader_exposure 建表刀位句改）。
3. **V3-4/V3-5 前置修正 #3：lifecycle time authority**——`opened_at_tick` / `closed_at_tick` 不得由任意调用方伪造；正式管线必须取自 `world.current_tick` 并在转移事务内验证（V3-1 staging 的调用方代书为过渡态）。**已入合同**：`STATE_MACHINES §21`。
4. **V3-4 前裁决 #4：transition prerequisites（MVP 按外审建议全采）**——①章 `ACTIVE` 须有 `ADOPTED` Blueprint；②场 `ACTIVE` 须有 `ADOPTED` Dossier；③**章重叠禁止**（`SETTLING` 与下一章 `ACTIVE` 共存亦禁）。**已入合同**：`STATE_MACHINES §21/§22`（标注 V3-4 起强制；**V3-1 store 为 staging，不重开**）。
5. **文档歧义修正 #5**：「行为事实与正文同批提交」语义删除——用户行为经 **ACTION OUTCOME COMMIT** 先成为 canon 事实；POV Writer **随后引用该 committed outcome** 生成 prose，再由 **SEGMENT COMMIT** 落正文及其新产生的非用户事实；**两者不是同一事务**。**已入合同**：`STATE_MACHINES §25` 共同纪律 + `RUNTIME_ARCHITECTURE §27` 边界。

**V3-2 口径重申**：Template/Package 只负责创建时 seed；World Instance 的 `world_bible_revision` 是唯一世界设定权威；模板升级不得静默改写既有世界（N-INV-006）。

授权：外审（用户转呈，2026-10-12）；DMCP 决策 `DEC-OPI-bab4da9f-…27`。

### v1.3.3 — 2026-10-12 V3-3R identity correction（外审；授权：外审结论转呈）

**结论**：V3-3 **维持 COMPLETE**（不重开）；五项 identity/authority 收口落定——items 1/2/3 落 `DATA_MODEL §26.2.1`（identity 冻结 + seed 语义）；item 4 落 migration `0032`（composite FK storage invariant）；item 5 落 `elc/world/cast.py` 装配配方（Director cast input 仅从 durable instance data 构建）。

1. **Narrative V3 canonical participant identity 冻结**——AI-controlled durable character → `world_actor.actor_id`；user-controlled character → `world_player_character.player_character_id`。**persona_id 是 CharacterCard/template identity，不作为 V3 canonical world participant identity**（V3 链不做 actor↔persona 转换）。已入合同：`DATA_MODEL §26.2.1`。
2. **package-only residents 暂不具 durable V3 participant identity**——仍为 prose/scene 素材；未来需长期被事件引用、拥有 memory 或升级 POV 时，另定显式 durable identity 方案（不在本轮扩表）。
3. **seed 语义冻结**——`world_player_character` 的 `location/state/knowledge_refs` 仅表示 **creation-time seed**；当前 location/state → `world_state_fact`；当前 knowledge/belief → **V3-7 actor memory/belief**；V3-4 Director 不得把 seed 字段当运行态当前事实。
4. **actor-profile 归属 storage invariant**——`world_actor_profile` 经 migration `0032` 重建为 composite FK `(actor_id, world_id) → world_actor(actor_id, world_id)`（0023 已有该 UNIQUE）；store precheck 保留为人话层。
5. **V3-4 Cast Input 约束**——必须可仅从 durable instance data 构建（`world_actor` + `character_card.name` + `world_actor_profile` + `world_player_character`）；Package 是 seed source，不重新成为用户自建世界的运行时 authority。

**Legacy 不回写**：`world_event.participants`（Legacy V2：cast persona ids ∪ user id）语义不动、零回填——V3-5 的 lineage/cognition read path 负责区分。

**边界重申**：不扩 StoryRole 词表、不建居民系统、不多玩家角色、不动 UI。

