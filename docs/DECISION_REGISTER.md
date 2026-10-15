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


### v1.3.4 — 2026-10-12 V3-4 开工裁决（L3 定谳落表 + 范围裁决 + #4 起强制；授权：总控开工四查，IP §20 刀序 V3-4 行）

**结论**：V3-4（Director + `world_chapter(_plan)`）按 IP §20 刀序开工；**零迁移**（0029 四表已备——V3-1 先例：地基在前刀、首个生产消费者本刀纯代码）；**L3（Blueprint `scenes`(JSON) ↔ `world_scene` 行对账规则）定谳并落表**（登记落点 = 本刀开工四查，v1.3.1 在册）；**#4 transition prerequisites 本刀起强制**（STATE §21/§22 合同标注「V3-4 起强制」到期）；cast input 按 V3-3R 外审 item 5 的 durable 配方装配。

1. **L3 定谳全文（落点 = `DATA_MODEL §26.2.1` 新增「V3-4 Blueprint 严格 schema 与 scenes↔world_scene 对账规则」块，同刀生效）**：`scenes[]` 元素 = Director 的场景草案（Plan 素材），规范键集 = `purpose` / `place` / `pov_actor_id` / `participants` / `planned_start_tick` / `entry_goals` / `exit_condition` / `elasticity` / `revealable` / `must_hide`（pov/participants 用 canonical identity——AI=`actor_id`、user=`player_character_id`，persona 不入口径）；对账方向单向——ADOPT 一份 Blueprint revision 时为每个元素创建一行 `world_scene`（`PLANNED`，`scene_index` = 数组序位 1..N），**行是对账锚、JSON 是内容源**；`scene_id` 派生律 = `f"{chapter_id}-s{scene_index:02d}"`；重规划 Diff 规则：新增位次→新行 PLANNED／消失位次且仍 PLANNED→`discard_scene`／已 ACTIVE·COMMITTED·CLOSED 行永不动（N-INV-003）／位次仍在但内容变→行不动／`scene_index` 不复用。
2. **范围裁决（schema-and-table-side-only）**：IP §20 V3-4 行字面 = Director + `world_chapter(_plan)`（Blueprint 严格 schema；软期望集+硬条件律；Plan≠Canon 落表）——**表侧与 schema 侧**；LLM 驱动的 Blueprint 生产面（prompt/provider/严格解析）不在其内，**登记为独立后刀（V3-8 Gold Scenario 前置依赖）**。Director 的 storyline/state 摘要读面以 `world_storyline`（0028 现役）+ `world_state_fact` CURRENT（0024 现役）为真实读面（Chapter Summaries/Reader Exposure 尚不存在，V3-7/V3-5 接入）。
3. **#4 强制形（STATE §21/§22 合同标注「V3-4 起强制」本刀生效）**：`activate_chapter` 增前置 = 该章须有 ADOPTED plan revision；**章重叠禁止从 ACTIVE-only 扩到「SETTLING 章与下一章 ACTIVE 共存亦禁」**（world 内存在 ACTIVE 或 SETTLING 章即拒开新章）；`activate_scene` 增前置 = 该场须有 ADOPTED dossier revision。
4. **cast input durable 配方（V3-3R 外审 item 5 的登记落点）**：仅从 durable instance data 装配——`world_actor.actor_id` + `character_card.name`（web `_world_actor_names` 同款 LEFT JOIN 配方）+ `world_actor_profile` + `world_player_character`；`participant_namespace` THE ONE 派生；Package 只是 seed source，绝不回读作运行时 authority；player 的 `location/state/knowledge_refs` 是 creation-time seed，不当运行态事实（V3-3R 冻结块 #3）。
5. **Director 全程不推进 `world.current_tick`**（#3 lifecycle tick authority；N-INV-007：tick 推进权只在提交事务）。
6. **窗口回归册义务落点维持**：0029 章单 ACTIVE race-free（partial UNIQUE／查进 BEGIN IMMEDIATE）仍归 V3-5/V3-6 组合翻转一次收（store docstring 已铭）；用户创建世界 world+initial Bible 真原子创建服务 = 后刀义务；narrative store docstring 同族矛盾 sealed 待下次触碰；INFO-1 CAS 守卫承重（bible.py）不动；narrator roster 迁移到 `participant_namespace` 归消费迁移刀；StoryRole 扩词时 0031+0032 CHECK 与枚举同刀随迁；`world_actor_profile` 现役定义在 0032。
7. **边界重申**：旧 V2 链零改；UI 不动；真实 automatic-teaching rollout 维持 HOLD；不开新迁移（`tests/conftest.py` 的 MIGRATION_IDS/SCHEMA_HEAD_* 不动）。

授权：总控开工四查（IP §20 刀序 V3-4 行 + v1.3.1 登记的 L3 落点到期）；DMCP 决策 `DEC-OPI-be7b094f-…7`；三件 = TASK `…11` / VAL `…13`（同铸）。

### v1.3.5 — 2026-10-12 V3-4 独立评审处置（ACCEPT-WITH-FINDINGS 无 HIGH；授权：评审结论转呈）

**结论**：V3-4 **维持推进**（不重开）；8/8 承重变异全 RED；三项 MEDIUM 与四项 LOW 全处置——**F3/F4/F5/F6/F7 修，F1/F2 追认+登记**；INFO 三件留痕。

1. **F3（MEDIUM，修）**：`revise_blueprint` 对 `SETTLING` / `CLOSED` 章拒 `VALIDATION_FAILED`（§21 「CLOSED 不可 reopen；修正走后续章」/ §24 「只重规划剩余部分」——原定「不查章状态」只覆盖「对已 COMMITTED 场无写权」，未挡住闭章内新 PLANNED 锚被激活）。守卫已落 `director.py` + 新钉 `test_revise_blueprint_refuses_a_settled_chapter` + `DATA §26.2.1` 补「重规划的章状态边界」条。
2. **F4（LOW，修）**：`STATE §21` 章重叠禁止句补**操作形**成文（与 `activate_chapter` 一致：世界内存在 ACTIVE 或 SETTLING 的其他章即拒；`PLANNED` 章不挡——多份 Blueprint 可先备好）。「前一章未 CLOSED 即拒开新章（`open_next_chapter` 守卫）」登记为 V3-5/V3-6 生命周期事项——注意其与 F1 崩溃残骸（PLANNED 无 plan 悬空章）会互相放大，届时一并裁。
3. **F5（LOW，修）**：`DATA §26.2.1` L3 块补 `chapter_id` / `plan_id` 两条派生律句（原只有 `scene_id` 一条成文，docstring/AOCI 的「三派生律 word for word」自此为真）。
4. **F6（LOW，修）**：封印切片「narrative store docstring 同族矛盾」**触发即清偿**（本刀正是 store.py 的触碰刀）：`_refusal_code` 三段归位（UNIQUE→CONFLICT／FOREIGN KEY→NOT_FOUND／其余→DEPENDENCY_UNAVAILABLE，照 `world/store.py` create_world 先例 N-W10-6）+ 模块 docstring 同刻对齐 + 新钉 `test_the_create_faces_spell_the_three_refusal_families`（锁库实证 DEPENDENCY_UNAVAILABLE，V3-2 双连接姿势）。
5. **F7（LOW，修）**：「两处 read joins／两处参数绑定 SELECT」计数错更正为**一处**（`director.py` docstring + `aoci.code.txt` WD4M 同刻）。
6. **F1（MEDIUM，追认+登记）**：Director 组合层崩溃窗口两型残骸（`open_next_chapter` 在「章已建、plan 失败」窗中断 ⇒ PLANNED 无 plan 悬空章，重放前进一章；`revise_blueprint` 在「create_plan 成功、adopt 失败」窗中断 ⇒ 悬空 PROPOSED revision，重放产出下一 revision）——**store 面幂等读法追认**（「同 payload 重放不增行」在 store 面成立且双钉在册，是可执行的最强读法；Director 层「重放」语义等价于「再规划下一章」，强行做组合层幂等需调用方钉 chapter_id，现合同无此输入）。**登记后刀义务**：「Director 组合层崩溃续跑/残骸回收语义」归 V3-5/V3-6（首次把 Director 接进管线者）或专门编排刀；RA §29 的 V3 recovery 扫描面是否补录「PLANNED 无 plan 章 / 悬空 PROPOSED revision」两类残骸届时一并裁。
7. **F2（MEDIUM，追认+成文）**：位次曾 DISCARDED 后其元素回升到该位次 ⇒ **退休锚不重铸、不复活**（`scene_index` 不复用 + §22 无 DISCARDED→PLANNED + append-only 三重约束下唯一免写史的读法）；「新增位次」= **无行的位次**。已成文入 `DATA §26.2.1` L3 块（对账方向条 + Diff ①⑤ 指针）；消费刀不得把 DISCARDED 锚当作可激活的计划场，也不得重编位次。
8. **INFO 留痕**：F8（扫描钉对拼接型 SQL 有盲区——启发式扫描共性，行为层由 store-only 写路兜底）；F9（`Director.validate_blueprint` 对不存在世界答 VALIDATION_FAILED 而非 NOT_FOUND——写面已先查世界，无实害）；F10（「persona 无 character_card 行 → LEFT JOIN NULL → 回退 actor id」未单钉——覆盖性提示）。

授权：独立评审（executor-pro 新上下文只读，2026-10-12）+ 总控处置（V3-1/V3-3 处置先例：总控亲写，注释/守卫/钉级）；处置提交随本条目同刀。

### v1.3.6 — 2026-10-12 V3-4R（外审 1 HIGH + 2 MEDIUM-HIGH；范围受限修正刀；授权：外审结论转呈）

**结论**：V3-4 主体方向正确，进入 V3-5 前做**范围受限** V3-4R——不推翻 Director、不扩 Writer/Commit、零迁移；外审五项全采，`DATA §26.2.1` L3 块同刀修订。

1. **HIGH（scene identity / replan 模型）= 呈现顺序与持久身份分离**：`scenes[]` 数组只表达呈现/计划顺序；元素可带稳定身份 `scene_ref`（指向同章既有 anchor 的 `scene_index`；严格校验：重 ref 拒/不存在拒/他章拒/同位他锚冲突拒/退休 anchor 永不指认）；不带 ref 的元素按序位指认同位置 anchor；**identity stamping**——anchor 创建时把派生 `scene_id` 烧入 plan 行 `scenes` JSON 对应元素（**受控一次性改写**：仅增 `scene_id` 一键、仅创建时一次、adopt 前完成、其余字节不动）；新增场景配 unused monotonic `scene_index`（`max(既有)+1`）；**禁止幽灵/占位 scene**；退休 anchor 永不复活永不重铸。最新 Blueprint 自然表示稀疏 durable identity（rev3 = [ref s01, ref s02, {新场→s04}]）。
2. **MH-1（World authority fail-closed）**：`world` 存在但无 `CURRENT` Bible ⇒ 禁止规划（`NOT_FOUND` 人话）；`DirectorContext` 必携带 `current_tick`（Director 产生 planned ticks 必须知道 canonical story time；初始 planning 以其为现实起点——本刀把 canonical time 摆到 Director 眼前，不改写 payload）。
3. **MH-2（POV 实权 + cast 加厚）**：`pov_eligible=False` 拒为 POV／`True` 允许／`None` = 未声明**不自动授权**（MVP 拒）；`player_character_id` 为 POV 允许；`pov_actor_id ∈ participants` 冻结为 schema invariant；cast 输入加厚——AI 成员带 `character_card` 人物六件（identity/personality/background/speech_style/values/boundaries，card 缺失=空串 honest undeclared）+ `world_actor_profile`；player 带 name/background/appearance/abilities/limits（`location/state/knowledge_refs` 继续结构级缺席）。
4. **V3-5 硬门（登记，本刀不实现）**：**Director operation crash/replay 必须在新运行链第一次真实消费 Director 前关闭**（top-level idempotent planning operation 或 resume/recovery；不得让重试自动跳到新 chapter/revision——V3-4 评审 F1 两型残骸〔PLANNED 无 plan 悬空章/悬空 PROPOSED revision〕是其具体形）。落点 = V3-5 开工四查必裁。
5. **最小语义收紧（同刀）**：`scenes` 非空（推翻 V3-4 钉「空 scenes 合法」——该钉随迁反转）；chapter `planned_start_tick <= planned_end_tick`；scene `planned_start_tick >= 0` 且 ≤ 本章 `planned_end_tick`；POV ∈ participants（同 #3）。不扩成剧情合理性检测器。

授权：外审（用户转呈，2026-10-12）；DMCP 开工裁决 `DEC-OPI-be7b094f-…21`（rev 783）。

### v1.3.7 — 2026-10-12 V3-4R 独立评审处置（ACCEPT-WITH-FINDINGS 无 HIGH；授权：评审结论转呈）

**结论**：V3-4R **维持推进**（不重开）；9/9 承重变异全 RED；MEDIUM×1 + LOW×5 全处置——**F2/F3/F4/F5/F6 修，F1 登记成文**；INFO×8 留痕（spine 钉射程注记两分／「有序」收窄为界内已成文／章面 tick 无非负检查合同未要求／仅 fresh 元素带 burned id 自洽／「31 钉」口径澄清=V3-4 全割聚合 29+2／重复节区头 V3-4 遗留／_card_faces 直读 character_card 合同指定／AGENTS 收口入册惯例）。

1. **F1（MEDIUM，登记成文）**：`scene_ref` 通道在现役同位冲突律下与数组序位行为重合——**换序与中段 PLANNED 锚退休不可表达**（评审实证四形全拒、带/不带 ref 结果全等）。裁定：**与合同逐字一致、非代码缺陷**；成文入 `DATA §26.2.1`——「`scene_ref` 是与序位一致的**对偶声明**通道，不承担重排/中段跳过；稀疏 identity 由 DISCARDED-skip + unused-monotonic 表达」+ **放宽路径登记 V3-5/V3-6**（需要换序/中段退休时显式重开，冲突律改为「该序位自有锚须被他人认领或被 discard」）。
2. **F2（LOW，修）**：AOCI `director.py[WD4M]` 的 revise_blueprint 段补「**已定章拒重规划**」（SETTLING/CLOSED 章——V3-4 处置 F3 的守卫臂，两次重写均未随迁，本次补齐）。
3. **F3（LOW，修）**：`build_director_context` 悬空 world 抛 `ValueError`（docstring 已声明的 fail-fast 前置）补钉 `test_the_context_read_fails_fast_for_a_dangling_world`（`pytest.raises(ValueError, match="world-nowhere")`）。
4. **F4（LOW，修）**：缺卡成员钉的 docstring 措辞更正——「deletion 程序清卡」与 `deletion/types.py` 的 RESTRICT/不可达登记相左；改为「防御臂；FK 下不可达；如实登记为腐坏/未来级联风险」（C1-c 先例的诚实框架）。
5. **F5（LOW，修）**：V3-4 处置 F2 的消费刀禁令句（「消费刀不得把 DISCARDED 锚当作可激活的计划场，也不得重编位次」）回迁 `DATA §26.2.1` 活合同（V3-4R 重写时丢失；与 F1 放宽路径同句落地）。
6. **F6（LOW，修）**：`open_next_chapter` 的 ref 拒案（有声明无钉）补钉 `test_open_next_chapter_refuses_a_reference_before_anything_is_written`（`scene_ref=1` 于新章 ⇒ VALIDATION_FAILED 点名 ref 与章 id，零章行）。
7. **执行者六项自报边界裁定**（评审专项裁定全采）：①revise 面 Bible fail-closed **追认**（外审 MH-1 是「禁止规划」，revise 是规划行为）；②context 悬空 world ValueError **追认+补钉**（F3）；③同位冲突律 **追认+登记**（F1）；④spine 钉强形 **追认可留+注记两分**（钉只防已知拼写，行为律由 e2e 承重——变异③实证）；⑤缺卡钉 FK-off 构造 **追认+措辞更正**（F4）；⑥「31 钉 vs 30」**口径澄清：无人记错**（V3-4 交付 29 + 处置 +2 = 全割聚合 31 = 5972−5941；本文件现役 30）。

授权：独立评审（executor-pro 新上下文只读，2026-10-12）+ 总控处置（V3-1/V3-3/V3-4 处置先例：总控亲写，注释/钉级零行为为主）；处置提交随本条目同刀。

### v1.4.0 — 2026-10-12 V3-5 开工裁决（#1/#2 硬门落法 + SEGMENT COMMIT 原子组 + Director crash/replay 关闭 + Writer 确定性基线；授权：总控开工四查，IP §20 刀序 V3-5 行）

**结论**：V3-5（Scene + Dossier + POV Writer + `narrative_passage` + SEGMENT COMMIT）按 IP §20 刀序开工；**迁移 `0033` 三表**（`narrative_passage` / `reader_exposure` / `segment_commit`——#1 lineage 显式面与 #2 解耦的物理形）；**SEGMENT COMMIT 单事务**落 NCP-3 全臂；**Director crash/replay 本刀关闭**（v1.3.6 #4 硬门到期兑现）；Writer/Planner 交付**确定性基线**（LLM 生产面登记后刀，与 V3-4 LLM Blueprint 面同族）。

1. **#1 lineage 硬门落法**：`segment_commit` 表（`commit_id` 派生 `f"sg:{scene_id}:{segment_seq:04d}"`/kind CHECK 'SEGMENT'/passage_id/actual_start/end_tick/event_id + `UNIQUE(scene_id, segment_seq)`）——V3 事件 story-time 经显式面归属（`story_time_of(event_id)` 读路）；**禁 opaque event-id 反推**；V3 cognition 不得把 legacy `occurred_at` 当世界时间。
2. **#2 exposure 解耦物理形**：`reader_exposure` 随 0033 建表但**不在 NCP-3 原子组内**；记录面 = 独立 `record_exposure`（MVP 显式调用；exposed_at 是 ISO bookkeeping 非 story time）；N-INV-005 扫描钉（曝光面 SQL 永不触 actor memory 词表）。
3. **SEGMENT COMMIT 落法（STATE §25 已收指针）**：一个短事务 = passage（id 派生 `-p{seq:04d}`，不可变）+ world_event（id 派生 `-e{seq:04d}`；participants = canonical identity；occurred_at=now 〔legacy ISO 语义，V3 不读〕）+ state 结算 + `segment_commit` 行 + `world.current_tick` 推进（actual_start=事务内读数、actual_end=+duration_ticks≥0）+ `is_last_segment` 时 scene ACTIVE→COMMITTED 同事务翻转（**SCENE COMMIT=别名**）+ 首段时章 PLANNED→ACTIVE 且 `opened_at_tick`=actual_start（**#3 tick authority 正式管线化——提交事务接管，不再调用方代书**）。幂等：同 segment_key 重放 = 全组 no-op。
4. **Director crash/replay 关闭（v1.3.6 #4 兑现）**：`open_next_chapter` 对「PLANNED 无 plan 悬空章」**复用**（不跳新章）；`revise_blueprint` 对「悬空 PROPOSED revision」**复用**（不跳下一 revision）；stamping/reconcile 幂等续跑——重试不再自动跳到新 chapter/revision。
5. **0029 章单 ACTIVE race-free 义务**：裁归本刀——`activate_chapter` 的 overlap 查+ADOPTED 查+CAS 移入同一 `BEGIN IMMEDIATE` 事务（取「查进事务」形，不另加 partial UNIQUE；store docstring 的登记句同刻清偿）。**V3-4 评审 F4「未 CLOSED 拒开新章」裁不做**（维持 v1.3.5 登记——PLANNED 章不挡是章间作者层的设计需要）。
6. **Writer/Planner 确定性基线**：`elc/world/scene.py`（ScenePlanner：open_scene——读章 ADOPTED Blueprint 的 scenes JSON 对应元素+durable cast/context → 落 dossier rev1+adopt → activate_scene；dossier `planned_start_tick` 取自 `DirectorContext.current_tick`）+ `elc/world/writer.py`（PovWriter 结构面：一场一 POV 校验、revealable/must_hide 词面不注入正文护栏、正文 body 由调用方供〔LLM 后刀〕、校验后交 SEGMENT COMMIT）。**LLM Writer/Planner 生产面（prompt/provider/严格解析/声音库与工艺注入的 prompt 材料组装）登记为独立后刀**（与 V3-4 LLM Blueprint 面同批接线，V3-8 前置）。
7. **迁移刀纪律**：0033 三表入 `GLOBAL_CONTENT_TABLES` keep 侧（15→18 员）+ `tests/deletion/test_deletion_surfaces.py` 钉随迁；conftest `MIGRATION_IDS`/`SCHEMA_HEAD_FILE`/`SCHEMA_HEAD_VERSION` 同刻（0033/33）；aoci_drift 迁移覆盖律会红 ⇒ 刀内随迁（0033 条目）。**旧链零改**；UI 不动；legacy `world_event.participants` 词表不回写（V3 事件 participants = canonical identity，区分靠 lineage 面与读路过滤）。

授权：总控开工四查（IP §20 刀序 V3-5 行 + v1.3.2 #1/#2 硬门 + v1.3.6 #4 硬门到期）；DMCP 决策 `DEC-OPI-be7b094f-…32`（rev 787）。

### v1.4.1 — 2026-10-12 V3-5 独立评审处置（ACCEPT-WITH-FINDINGS 无 HIGH；授权：评审结论转呈）

**结论**：V3-5 **维持推进**（不重开）；三项硬门（#1 lineage/#2 exposure/v1.3.6 #4 两型残骸面）与 DDL 逐字、旧链零改、迁移搬迁全部兑现；原子性经仓外深处注入实证全组回滚（变异 A）；9/12 变异承重 RED。MEDIUM×2 + LOW×4 全处置——**F1/F2/F3/F5/F6 修，F4 成文**；INFO×3 留痕。

1. **F1（MEDIUM，修）**：open 面三个中间崩溃窗口仍铸新章（crash 于 create_plan 后/ adopt 后零锚 / adopt 后部分锚 ⇒ 重试铸 ch02，v1.3.6 #4 主句的残留窗口）。修正：`_residue_chapter` 判定扩到**三型**（无 plan revision / 顶版 PROPOSED / 顶版 ADOPTED 且锚未全落——`len(latest.scenes) > len(anchors)` 检测）；`open_next_chapter` 的复用分支按残骸形态续跑（无 revision 铸 r1；PROPOSED 走 `_continue_proposed_residue`〔形状同→adopt 续跑；异→reject 后铸下一 revision〕；ADOPTED 锚未全落→零新 revision、`_reconcile_scenes` 幂等续补锚）；`_adopt_residue_and_reconcile` 抽取为 revise 与 open 两面的共享臂（一真源）。两新钉（PROPOSED 残骸复用不铸新章 / ADOPTED 部分锚续补——三型全覆盖）。
2. **F2（MEDIUM，修）**：`test_the_group_transaction_has_one_begin_and_one_commit` 的 body 半空转（DML 过滤版扫描器看不见 `"COMMIT"` 常量——两段事务变异零报警，整套 37 钉全绿）。修正：新增 `_all_constants`（无过滤常量族）；body 半直断 `BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK` 常量集合为空；public 半用 count 断言（各恰一枚）。
3. **F3（LOW，修）**：同族空转第二处（arm 钉）——同 `_all_constants` 修正（两个 `_flip_*_tx` 臂禁事务控制常量）。
4. **F4（LOW，成文）**：`record_exposure` 存在性读取在 `BEGIN IMMEDIATE` 之外——docstring 增成文句（Local V1 单连接窗口不可达；并发首写竞争面为 UNIQUE 的 CONFLICT，绝无静默第二行；race-free 形态登记为该面自身的后续义务，与 bible.py INFO-1 同族口径）。
5. **F5（LOW，修）**：`say_33` 数字戳记名（v3_2/v3_3 两处）归一到戳记无关耐久形 `say_the_chain_head`（防坑㉕先例）。
6. **F6（LOW，修）**：AOCI `0030_world_bible.sql[WB2T]` 条目残留现在时为假的前瞻句——「0029 store 具名的章『at most one ACTIVE』义务仍归 V3-5/V3-6，未被本刀清偿」改为「已由 V3-5 清偿（TASK-OPI-be7b094f…34）」。
7. **INFO 留痕**：F7（exposure 扫描钉覆盖面=DML-shaped 常量——假 SQL 红/裸字符串不红，与钉名宣称面一致、风险低）；F8（`_replay_outcome` 把内部一致性〔passage.created_at_tick == commit.actual_end_tick〕混入与载荷的形状比较——极端腐坏面报 CONFLICT，如实登记）；F9（RA §29 V3 恢复扫描面〔world_scene ACTIVE 续跑等〕不在本刀合同面，V3-6+ 承接）。
8. **「6026 算术链差 1」查明**：净增 38 = 新文件 37 钉 + `test_aoci_drift.py` 净增 1 钉（`test_v3_5_entries_carry_the_segment_commit_faces`）；执行者自报「37 钉八组」仅指新文件口径，无人记错。
9. **通道纪律（总控自报，如实留痕）**：本刀处置期间总控本人一次 Bash heredoc Python 写仓内 `.py`（say_33→say_the_chain_head 改名，两文件各一行）——违反落盘通道纪律①；**第一次＝训诫留痕**（改动纯改名、零行为副作用、主动自报、随即验证 diff 精确 1+/1−）。

授权：独立评审（executor-pro 新上下文只读，2026-10-12）+ 总控处置（V3-1/V3-3/V3-4/V3-4R 处置先例：总控亲写）；处置提交随本条目同刀。

### v1.4.2 — 2026-10-12 V3-5R 开工裁决（外审 2 HIGH + 1 MEDIUM-HIGH + 时间语义修正 + provider Writer 硬门登记；范围受限；授权：外审结论转呈）

**结论**：V3-5 主体（NCP-3 / lineage 写侧 / reader exposure 解耦 / Director crash-replay）通过；**暂不进入 V3-6**，先做**范围受限 V3-5R**——不扩大到 User Gate / Action Resolver。已铸 V3-6 三件（`DEC-OPI-dc1bafdf-…5` / `TASK-…7` / `VAL-…9`）**暂缓执行**（重放行时迁移号顺延修订）。

1. **HIGH-1（cognition read gate）**：建立 Narrative V3 专用最小 cognition read face（`src/elc/world/cognition.py`）——V3 event 判定走**显式 lineage**（`segment_commit.event_id` JOIN）；排序用 `segment_commit.actual_start_tick / actual_end_tick`；公共/亲历直接以 canonical `actor_id / player_character_id` 过滤（**不得** persona id 或 Package user-character mapping）；legacy C1（`host.py` 世界端口）**不改写**、保持 legacy 读面。`ScenePlanner` 把当前 POV 的该读面作为 dossier/context 输入（`SceneContext` + `SceneOpening.context`）。V3-7 Actor Memory 上线后该面降为兼容/fallback。
2. **HIGH-2（scene actual span）**：NCP-3 成为 `world_scene.actual_start_tick / actual_end_tick` 的**唯一写者**——首段同事务写 start、每段同事务推进 end、最后一段同时 `ACTIVE → COMMITTED`（**一个 UPDATE 一次版本推进**，不得另起第三事务）；replay 不重改。
3. **MEDIUM-HIGH（顺序与 terminality 幂等）**：fresh segment 严格 `max(committed_seq)+1`（第一段必须 1；拒绝 0 / 负数 / 跳号 / 倒序——replay arm 仍先行）；**terminality 持久化**：`migration 0034_segment_terminality.sql`——`ALTER TABLE segment_commit ADD COLUMN is_last_segment INTEGER NOT NULL DEFAULT 0 CHECK (is_last_segment IN (0,1))` + 精确回填（`COMMITTED/CLOSED` 场的最大 seq 行 = 1；推演式「等价记录」被否：`commit_scene` 显式面可造出无对应 terminality 的 COMMITTED 场，推演会误报 CONFLICT）；replay 形状比对含该列（同 key 不同 `is_last_segment` ⇒ 明确 `CONFLICT`）。
4. **时间语义修正**：dossier `planned_start_tick = max(current_tick, blueprint_scene.planned_start_tick)`——现实拖延时 current 获胜、未来计划保留；actual 仍只由 commit 推进。
5. **provider Writer 硬门登记**：现役 literal `must_hide` substring guard **不是** POV knowledge firewall（语义改写可绕过）；真实 LLM Writer 上线前必须采用 **POV-safe context compilation**（Writer 默认拿不到不可知秘密），lexical guard 仅作第二道 deterministic guard——登记入 `writer.py` docstring + 本条目 + 窗口回归册。
6. **迁移刀纪律**：搬迁面预写名单（conftest 三常量 0034/34 / 负索引 shift 族 / SCHEMA_HEAD 字面族 / aoci drift 0034 条目 + cognition.py 条目 + 三模块更新）；`GLOBAL_CONTENT_TABLES` **不变**（无新表，18 员）；`behavioral_baselines/` 与 0001–0033 迁移文件零改动；旧链零改；UI 不动。
7. **合同增量（总控亲写、随刀提交）**：`DATA §26.2.1` 增补（segment_commit `is_last_segment` 列 + 回填律）+ `§26.2.3` 重写（V3-5R 最小读路：V3 cognition read face + C1 legacy 兼容）；`STATE §25`（NCP-3 增补：span 臂 / 顺序律 / 终态列）+ `§26`（scene actual span 唯一写者）；`RA §28` NCP-3 落法句。

授权：外审（用户转呈，2026-10-12）；DMCP 开工裁决 `DEC-OPI-dc1bafdf-…11`（rev 794）。

### v1.4.3 — 2026-10-12 V3-5R 独立评审处置（ACCEPT-WITH-FINDINGS 无 HIGH/MEDIUM；授权：评审结论转呈）

**结论**：V3-5R **维持推进**（不重开）；五项外审基准逐项在码在册（读面三律 / span 唯一写者 / 顺序律与 terminality 持久化 / max 时间律 / Writer 硬门登记）；14 项承重变异 12 红；禁改面全空；四门绿（评审副本全量 6061/0/0，仓内零写入）。LOW×3 + INFO×5 全处置——**F1/F2/F3/F4/F5/F7 修，F6/F8 留痕**。

1. **F1（LOW，修）**：replay 的 `scene_committed` 由「读时推导」（scene.status ∧ max seq）改为**持久标志本身**（`stored_is_last`——翻转与插入同事务的 durable 见证；经 `commit_scene` 显式面造的「无终态段 COMMITTED 场」不再误报 True）；`_replay_outcome` 的 `segment_seq` 死参随删；新钉 `test_the_replay_answers_scene_committed_from_the_stored_flag`（旧推导下必红）。
2. **F2（LOW，修）**：排序键列补行为钉 `test_the_cognition_read_orders_by_the_lineage_ticks_not_the_ids`——两场乱序提交（s02 先、s01 后）使 tick 序与 id 字典序相反；`ORDER BY e.event_id` 变异自此必红（评审盲区关闭）。未采用「源文本钉」路径。
3. **F3（LOW，修）**：`writer.py` 所称「窗口回归册」句于本刀收口入册时补进 `AGENTS.md` 窗口册（LLM Writer 行增 POV-safe context compilation 硬门）。
4. **F4（INFO，修）**：腐坏 `participants` 列的 `ValueError` 臂补钉 `test_the_cognition_read_refuses_a_corrupted_participants_column`。
5. **F5（INFO，修）**：末段提交后的 `scene.state_version` 补行为断言（「一 UPDATE 一次版本推进」的第二个见证）。
6. **F7（INFO，修）**：时间律（`max(current_tick, element)`）补入 `DATA §26.2.1` V3-5R 块（原只在 DEC / code / 测试）。
7. **F6（INFO，留痕）**：cognition 的 no-Package 钉为 import-路径级（散文含否定式 persona/Package 词）——判定路径零命中已证；不动。
8. **F8（INFO，留痕）**：交付提交信息「SCHEMA_HEAD 字面族 15 文件」与其自列 17 名 / 实测 22+1 有名数出入——纯文字精度；搬迁面实测完整（无残钉）。不 amend，随本条目留痕。
9. **评审外同族观察（总控，留痕）**：`chapter_activated` 的重放答仍为读时推导（`chapter.opened_at_tick == actual_start`）——零时长段（`duration_ticks=0`）可造同 tick 误报（F1 同类；持久见证需另一列 ⇒ 归后续刀显式重开）。V3-5 既有行为，本刀不扩。

授权：独立评审（executor-pro 新上下文只读 + 仓外副本 `D:\v35r_review\copy` 变异，2026-10-12）+ 总控处置（V3-1/V3-3/V3-4/V3-4R/V3-5 处置先例：总控亲写）；处置提交随本条目同刀。

### v1.5.0 — 2026-10-12 V3-6 重放行 + 开工裁决修订（迁移号顺延 0035 + 吸收 V3-5R 面；授权：外审放行条件达成〔V3-5R 收口 `DEC-OPI-dc1bafdf-…19`〕）

**结论**：V3-6 按 `DEC-OPI-dc1bafdf-…5`（十一项）重放行——**迁移号 0034→0035 顺延**（`0034_segment_terminality.sql` 已占用），任务书吸收 V3-5R 面。

1. **迁移 0035_user_gate_action.sql**：`user_gate` + `user_action` 两表逐字（含终态完整性复合 CHECK、`UNIQUE(gate_id, submission_id)`、五词/三词 status）；`segment_commit` **重建**——`kind` CHECK 扩 `('SEGMENT','ACTION_OUTCOME')`、新增 `action_id` FK、`segment_seq`/`passage_id` 改 NULLable、两条 kind 一致性 CHECK（ACTION_OUTCOME 行 `is_last_segment`=0——门面不翻场）、**`is_last_segment`（0034）与 `UNIQUE(scene_id, segment_seq)` 原样保留**、显式列名 INSERT…SELECT；建表序 gate→action→重建；双 stamp '35'。
2. **action.py**（NCP-1/NCP-2 单事务全臂 + 门面组 + Adjudication 形状 + recovery_scan）与**互锁两臂**（`settlement.commit_segment`）与 **`ScenePlanner.replan_scene`** 与 **replan 三值**（CHAPTER=现役 `revise_blueprint`；F1 放宽路径不重开）——按 `…5` 逐字。
3. **V3-5R 面联动**：`v3_cognition_view` 自 V3-6 起可见 ACTION_OUTCOME 事件（lineage JOIN kind 无关）；`SceneContext`/`max` 时间律沿用；`_replay_outcome` 与 `stored_is_last` 语义不扰。
4. **两表入 `GLOBAL_CONTENT_TABLES`**（18→20 尾插；deletion 钉族与 aoci「十八员」→「二十员」随迁）。
5. **开工四查新裁**：`chapter_activated` 同族观察（读时推导类）在 NCP-2 章臂同形——**默认维持现形**（消费刀知悉；持久见证归后续刀显式重开）。
6. **搬迁面预写**：conftest 0035/35；负索引 shift（[-7]→[-8]）；SCHEMA_HEAD 字面族再挪（0034 头已随 V3-5R 搬迁）；aoci 0035 条目 + action.py 条目 + 三模块更新；散文扫尾（0034 为历史层句保留）。

授权：外审放行（用户转呈：完成 V3-5R 后再重放行 V3-6）；DMCP 重放行裁决 `DEC-OPI-dc1bafdf-…21`（rev 798）；三件 = TASK `…23`（rev 799）/ VAL `…25`（rev 800）；原始开工裁决 `…5` 内容维持（两处修订见上）。

### v1.5.1 — 2026-10-12 V3-6 独立评审处置（ACCEPT-WITH-FINDINGS 无 HIGH/MEDIUM；授权：评审结论转呈）

**结论**：V3-6 **维持推进**（不重开）；`…5` 十一项 + `…21` 两处修订逐项在码在册；17 项承重变异 14 红；迁移 0035 专项探针（重建保留 `is_last_segment` 逐值全等、六类违例全拒）；禁改面全空；副本全量 6099/0/0。LOW×2 + INFO×2 全处置——**F1/F2/F3 修，F4 留痕**。

1. **F1（LOW，修）**：NCP-1 无行为注入钉且扫描钉为字面量族（`conn.commit()` 方法调用形可静默拆事务——变异 1b 全绿）。修正：①扫描钉补 AST 断言（action.py 全树无 `commit`/`rollback` 属性调用——事务控制只许 `execute("…")` 字面形）；②新钉 `test_ncp1_rolls_the_whole_group_back_on_a_deep_failure`（mid-group 注入 `_action_row` 抛 `OperationalError` ⇒ gate 仍 `OPEN`、零 action 行、重试落成——与 NCP-2 注入钉同形）。
2. **F2（LOW，修）**：`replan_scope` 落库值无钉（变异 14 写死 NONE 全绿；仅 `ActionOutcome` 入参面被钉）。修正：新钉 `test_the_ruling_scope_is_persisted_and_its_replay_is_a_no_op`（CHAPTER 裁决 → `action_of` 读回 `ReplanScope.CHAPTER`；同形重放 `ActionOutcome` 全等 + 零第二 event/零 tick 再推进）。
3. **F3（INFO，修）**：options 上限（4）无钉（变异 17 全绿）。修正：`test_ncp1_judges_the_option_and_the_scenes_status` 补 5 选项拒案。
4. **F4（INFO，留痕）**：`_replay_action` 腐坏残骸 `assert` 姿态（与 V3-5 `_replay_outcome` 同族；单事务下不可达）——消费刀知悉。
5. **执行者自报偏差裁定（六项全采）**：`commit_action` 增 `world_store`/`narrative_store` 参（与 `commit_segment` 同姿态，namespace/章节臂所需）／`player_character_id_of` 公开（一真源+钉）／`_element_fields` 拆 `_checked_fields`（一躯两址，双坐标消息均有钉）／`chapter_activated` 读时推导维持现形（v1.5.0 第 5 条登记）／腐坏 `assert` 姿态／intermediate 6094/1（p9_1 第二元组漏迁、最终态已含双元组）。
6. **观察入册（后刀散文扫尾候选）**：`time.py`/`narrative/store.py`/`narrative/types.py` 的「V3-1 ships no commit transaction / the later cuts'」类现在时句自 V3-5 起不精确（切面作用域可读为历史归属句）；`deletion/types.py` 模块 docstring 的「ALL_USER_DATA keeps」与 `RETAINED_TABLES` 五员不符（非本刀引入）——归后刀散文扫尾。

授权：独立评审（executor-pro 新上下文只读 + 仓外副本 `D:\v36_review\`，2026-10-12）+ 总控处置（历刀先例：总控亲写）；处置提交随本条目同刀。

### v1.5.2 — 2026-10-13 V3-6R 开工裁决（外审 2 HIGH + 1 MEDIUM-HIGH + RESOLVING 收紧；范围受限；授权：外审结论转呈）

**结论**：V3-6 主体（Gate/NCP-1/NCP-2/Intent≠Fact/Action lineage）通过；**暂不进入 V3-7**，先做**范围受限 V3-6R**——不扩 Actor Memory/Chapter Settlement。

1. **HIGH-1 durable replan obligation**：新表 `action_replan`（**migration 0036**）——`replan_request_id` 派生 `f"rp:{gate_id}:{submission_id}"` / `user_action_id` UNIQUE FK / `scope` SCENE|CHAPTER / `status` PENDING|APPLIED / `target_ref`（eager claim；APPLIED ⇒ NOT NULL 复合 CHECK）/ 双 stamp / state_version；入 `GLOBAL_CONTENT_TABLES`（20→21）。**NCP-2 第⑧臂**：scope≠NONE ⇒ 同事务建 PENDING（NONE 零行）。**消费协议 claim → work → complete**：`replan_scene(replan_request_id, …)` / `apply_action_replan(replan_request_id, …)`——APPLIED 零写返回 target_ref；PENDING 先写 target_ref 再执行；崩溃重试收敛同一 revision、零第二次计划变更；`revise_blueprint` 语义不动。`recovery_scan` **第五族**：PENDING obligations。
2. **HIGH-2 `outcome_ref` 链**：`PovWriter.write_segment(..., outcome_ref)` → NCP-3 校验（指向真实 COMMITTED action；gate 属本场）→ passage 落 `outcome_ref` → **同事务**关其 gate；**强制律**：场有 COMMITTED 未 CLOSED gate ⇒ fresh 段必须携带该 ref；replay 形状含 `outcome_ref`。链：`intent → adjudication → committed action → outcome_ref → passage`。
3. **一场一未 CLOSED 门**：`open_gate` 拒绝场景存在任何非 CLOSED gate（COMMITTED 未续写亦拦）。
4. **MEDIUM-HIGH span 覆盖 ACTION_OUTCOME**：臂语义化 `advance_scene_actual_span_tx(..., close_scene)`——NCP-2（close_scene=False）/ NCP-3（close_scene=is_last_segment）共同臂；V3-6「ACTION 不写场 span」钉反转（不翻场保留）。
5. **RESOLVING 收紧**：`commit_action` 仅接受 RESOLVING（ANSWERED 直达拒、点名 `begin_resolving`）；单一主路径无旁路；测试随迁。
6. **Resolver 生产面硬门维持**（非本刀 blocker；V3-8 Gold Scenario 前必须建成——intent+Bible+state+capability/environment → Adjudication）。
7. **迁移刀纪律**：0036 头（conftest 0036/36、负索引 shift、SCHEMA_HEAD 字面族、GLOBAL_CONTENT_TABLES 20→21 + aoci 廿一员钉、0036 条目）；禁改面；四门亲跑。

授权：外审（用户转呈，2026-10-13）；DMCP 开工裁决 `DEC-OPI-dc1bafdf-…31`（rev 802）。

### v1.5.3 — 2026-10-13 V3-6R 独立评审处置（ACCEPT-WITH-FINDINGS 无 HIGH/MEDIUM；授权：评审结论转呈）

**结论**：V3-6R **维持推进**（不重开）；四面逐项在码在册；**15/15 承重变异全红、无盲区**；禁改面全空；吸收完整性确认；副本定向 1068 钉全绿 + collect 6127 对齐。INFO×4 全登记（无代码改动）。

1. **执行者中断与吸收（如实留痕，V3-5 遗留先例同族）**：执行者先遭 API 余额中断（首次派单即拒），重试后在 600s 静默中断（长命令）——遗留**未提交半成品**（43 文件，含四面代码与 25+26 新钉；中间快照 +2106/−542）。总控取证（新钉族 25/25 绿、ruff/mypy(198)/compileall 全绿、禁改面 diff 空、无 TODO 残标、`replan_scene`/`apply_action_replan`/claim·complete/第五族逐面在码）→ 裁 **「吸收+复核」** → 代提交 **`ebc1020`**（43 文件 +3808/−542；提交信息已载明中断与吸收裁定）。
2. **F1（INFO，登记）**：提交信息「树 43 文件+2106/−542」的 +2106 为吸收取证时点的中间快照；终态 `git show --numstat` 为 **+3808/−542**。纯口径，不改提交（不 amend 纪律）。
3. **F2（INFO，登记）**：SCENE/CHAPTER 消费的崩溃收敛——「claim 后、work 前」窗口重算与已存 claim 同值（由 claim 的同值幂等兜底）；绕过语义由 before-complete / resumes-created-proposed 两钉捕获。收敛语义完整，登记「同值重算依赖幂等第二道」。
4. **F3（INFO，登记）**：`_replay_action` 与 `apply_action_replan` 的 `assert` 姿态在 `-O` 下剔除（后者有下游 `get_plan(None)` → ValueError 腐坏防御）——store 家族同姿态，非缺陷。
5. **F4（INFO，维护须知）**：`test_the_new_faces_are_one_transaction_and_the_close_targeted` 的全树 AST 断言将拦 action.py 未来**任何** `.commit(`/`.rollback(` 属性调用（含合法用途）——刻意纪律钉（p8-3 F2 先例同形态），消费刀须知。
6. **口径澄清（评审）**：新钉计数 = 25（新文件）+ 净 26（6127−6101）其中旧 V3-6 文件 36→36 持平、drift 净 +1；outcome_ref 校验实为六类检查（非五类）。

授权：独立评审（executor-pro 新上下文只读 + 仓外副本 `D:\v36r_review\`，2026-10-13）+ 总控处置（历刀先例：总控亲写）；处置提交随本条目同刀。

### v1.6.0 — 2026-10-13 V3-7 开工裁决（Actor Memory/Belief + Chapter Settlement + chapter summary + Narrative Memory；授权：IP §20 刀序 + 外审放行〔V3-6R 收口 rev 805「下一动 = V3-7」〕）

**结论**：V3-6R 已 COMPLETE（rev 805，6127/0/0，迁移 0036/36）——按 IP §20 刀序开工 **V3-7**，把四 canonical 已冻结的「（V3-7 起）actor memory/belief 增量」臂与 NCP-4 面落成物理形（确定性基线，schema-and-table-side-only）。

1. **开工依据（四查①）**：合同面已冻结——`DATA §26.2.1`「actor_memory / belief」块（五词 kind）与「chapter_settlement」块；`STATE §25` 两原子组的「（V3-7 起）actor memory / belief 增量」臂；`RA §27-28` NCP-4 + `§29` 恢复；`DOMAIN §20.2` authority 表 + N-INV-004；`§26.2.3`「V3-7 物化后 commit 增臂、dossier 改读、读面降兼容」。**不另起炉灶**——合同增量（DATA §26.2.1「V3-7 落表形」块 + STATE §25 臂落实 + RA §28/§29 落法）与代码同刀提交（基准纪律③）。
2. **迁移 0037 两表**：`actor_memory`（`memory_id` 派生 `f"mem:{event_id}:{participant_id}:{kind}"` / `participant_id` = canonical identity / `kind` 五词 CHECK 全可达 / `content` / `source_event_id` FK / `learned_at_tick` / `salience` NULL / append-only）+ `chapter_settlement`（`chapter_id` 一章一版 PK / summary / storyline_updates / hooks / resolved_lines / salience_notes / created_at_revision；**N-INV-004 存储面**——不写 event/state/tick）。schema_version 36→37。
3. **两提交事务记忆臂**：`commit_segment`（NCP-3）与 `commit_action`（NCP-2）同事务为事件 `participants` 落 `EXPERIENCED`（自动臂）；调用方供 HEARD/BELIEVED/INFERRED/MISTAKEN（显式增量面）；**replay 形状含之**（重放不二次落记忆——fresh 路径，replay 先行）。
4. **NCP-4 编排面**：`settle_chapter` 编排——一个短事务：章须 SETTLING ⇒ 落一章一版 settlement + 同事务 SETTLING→CLOSED（复用现役 `close_chapter` 臂，`closed_at_tick`=事务内读，tick 不推进）；**重跑 = no-op**（一章一版 PK），形状异 CONFLICT；storyline 结构性推进归后刀登记。
5. **下一章只读摘要面**：`chapter_settlement` 读面 + `DirectorContext.chapter_summaries` 增臂（`build_director_context` 装配已 CLOSED 章 settlement，chapter_index 升序）。
6. **dossier 改读 actor memory**：新 `v3_memory_view`（`elc/world/memory.py`——viewer 的 canonical identity 读面，kind 分层 + learned_at_tick 排序）+ `SceneContext` 增 `memory` 字段；`v3_cognition_view` **行为不变、钉不破**（降兼容/fallback——35 钉族须全绿）。
7. **RA §29 第六族**：`world_chapter SETTLING` 恢复族（NCP-4 中崩溃 ⇒ 重跑 Settlement 落同一版；扫描行不变、语义升族）。
8. **范围收紧与登记**：确定性基线（EXPERIENCED 自动臂 + 调用方供值面 + 保守拼接摘要）；LLM 显著性评估/摘要生成/传闻失真归 provider 生产面后刀（与 Writer/Planner/Resolver 同批，V3-8 前置族）；**P1 传闻失真未触发**（触发条件〔dogfood「知道得太准」信号或多世界开工〕未命中——本刀是 P1 落点归属刀但不兑现、维持后置、留痕）；`salience` 只存储透传（retrieval policy 后刀）。**搬迁面预写（四查④）**：conftest 0037/37；GLOBAL_CONTENT_TABLES 21→23 员 + deletion/types.py 注释与钉随迁；aoci.code.txt 0037 条目 + 受影响模块条目（覆盖律会红）；负索引钉族 grep（`MIGRATION_IDS[-N]`/`applied[-N]`）；散文扫尾（0036 头注释改历史层；本刀触 deletion/types.py ⇒ 顺笔核其 docstring 与 RETAINED_TABLES 不符句——V3-6 处置 F4 候选）。**窗口回归册核对**：LLM 生产面/replan 自动路由/reader 渲染 ack/record_exposure race-free/chapter_activated 读时推导——均维持登记不动。**禁改面**：behavioral_baselines 一字节不动；sealed 0029–0036 不改；reader_exposure 写面不动；legacy V2 链不动。**门**：pytest（自 6127 起）/ruff/mypy（198 起）/compileall 亲跑全绿。

授权：IP §20 刀序 + 外审放行；DMCP 开工裁决 `DEC-OPI-d274a7fb-bf78-4149-b38d-1e59b44b697c.6`（rev 806）；三件 = TASK `…8`（rev 807）/ VAL `…10`（rev 808）。

### v1.6.1 — 2026-10-13 V3-7 独立评审处置（ACCEPT-WITH-FINDINGS 无 HIGH/MEDIUM-HIGH/MEDIUM；授权：评审结论转呈）

**结论**：V3-7 **维持推进**（不重开）；八面逐项在码在册；**26 承重变异在其「有害方向」全红**（tick 推进/写事件/双落/跳参与者/接受 EXPERIENCED/序翻转/守卫对/认知行为均被抓）；禁改面全空；吸收完整性确认（产物完整自洽、无半落地痕迹）；副本全量 6154/0/0 + 静态三门绿。LOW×3 + INFO×4 全处置——**F1/F2/F3 修（总控亲写），F4/F5/F6/F7 留痕登记**。

1. **执行者中断与吸收（如实留痕，防坑㊲ 第二型，V3-5/V3-6R 先例同族）**：执行者派单后 600s 静默中断（长命令），遗留**未提交半成品**（40 文件：37 改 + 3 新〔0037/memory.py/test_v3_7〕，六面代码与 26 新钉俱在）。总控取证（新钉 26/26 绿、全量 6154/0/0、ruff/mypy(199)/compileall 全绿、禁改面空、无残标、六面逐面在码）→ 裁**「吸收+复核」**→ 代提交 **`c263192`**（40 文件 +3613/−429；提交信息载明中断与吸收裁定）。
2. **F1（LOW，修）**：`v3_memory_view` 的 kind 分层判别盲区（删整段 CASE 全族绿——夹具 kind 层与 tick 序同向不可判别）——补一条 `learned_at_tick=2` 的 `INFERRED` 行（先于 EXPERIENCED 行），使分层与 tick 序互斥：删 CASE 则该行排最前必红。（不用第二条 HEARD：同 `(event, participant, kind)` 撞派生 id CONFLICT；INFERRED 判别力相同。）
3. **F2（LOW，修一半+登记一半）**：两处「升序」子句单行夹具不可判别——①`chapter_settlements_of` 的 `chapter_index ASC`：**修**（新钉 `test_chapter_settlements_of_orders_two_chapters_by_index`——settle ch01 后开 ch02、commit、双 face settle，断言两章 ch01→ch02 序）；②recovery 第六族 `settling_chapters` 的 `world_id, chapter_index ASC`：**登记**（同世界物理上不可达两 SETTLING 章——章重叠禁止；判别需两世界夹具，成本/收益不合，归后刀按需）。
4. **F3（LOW，修）**：`memory_id` 派生拼写无字面钉（两侧同走 `memory_id_for` 的断言不可判别）——新钉 `test_memory_id_for_spells_the_contract_literal`（字面断言 `mem:<event>:<participant>:<KIND>`，照 V3-5 `sg:` 先例）。
5. **F4（INFO，登记）**：腐坏 kind 词的 `ValueError` 姿态全仓无钉（正常写入不可达、CHECK 兜底；探针 P4b 经 `PRAGMA ignore_check_constraints` 正面验证两读面一致）——未钉防御臂，登记。
6. **F5（INFO，登记）**：`settle_chapter` 的「重跑=no-op」是同形条件——结算后活跃剧情线快照漂移则重跑 CONFLICT（探针 P2）；与合同「形状异 CONFLICT」逐字一致，且交付恢复窗口（第六族只扫 SETTLING）不可达该路径；消费刀编排者知悉。
7. **F6（INFO，登记）**：`record_belief` 不校验源事件的 V3 lineage（legacy 事件为源可写入，探针 P3）——合同拒案清单未要求 lineage；若后刀收紧需显式加面。
8. **F7（INFO，变异台账留痕）**：两处等效变异（M03 仅删外层 SETTLING 守卫——第二守卫+事务回滚行为全同；M20 删 CLOSED 过滤——公开面下结算行只与 CLOSED 共存）——防御纵深，成对变异（M03b）已红。

授权：独立评审（executor-pro 新上下文只读 + 仓外副本 `D:\v37_review\` / `D:\v37_mut\`，2026-10-13）+ 总控处置（历刀先例：总控亲写）；处置提交随本条目同刀。

### v1.7.0 — 2026-10-13 V3-8a 开工裁决（原子创建服务 + V3 管线编排器 + provider 协议面；授权：V3-7 收口 `DEC-OPI-d274a7fb-…14` rev 809「下一动 = V3-8」+ 窗口回归册前置族登记）

**结论**：V3-7 已 COMPLETE（rev 809，6156/0/0，迁移 0037/37）。**V3-8（Gold Scenario 端到端 + 结构验收 12 条 + 用户「好玩」亲验）有前置缺口**：原子创建服务（world+初始 Bible，窗口回归册登记的「后刀」）未建；V3 管线编排器（把 Director→ScenePlanner→Writer→commit→settle→Director 串成可驱动循环）未建——现役面全是库面（host.py 无 V3 装配，测试直接驱动）；provider 协议面（Writer/Planner/Resolver 生产面）未接线。故先拆前置刀 **V3-8a**（全确定性、零迁移、无真实 LLM 调用），V3-8 本体留给「用可驱动管线跑通 Gold Scenario + 12 条 + 阅读面」。

1. **开工依据（四查①）**：范式篇 §10.2 验收链（编排器的设计依据）+ §9.1「persona 生成基础（provider/validator/streaming）直接复用」+ 窗口回归册登记（原子创建服务后刀 / LLM Writer/Planner 生产面 V3-8 前置 / LLM·规则 Resolver 生产面 V3-8 前置族）。**不另起炉灶**——合同增量（RA §27 编排面+provider 协议面+原子创建服务端、DOMAIN §20.2 authority 表三行）与代码同刀提交。
2. **范围裁（四查②，三项，全确定性基线）**：(a) **原子创建服务** `create_world_with_bible`（world 行 + 首版 `world_bible_revision` CURRENT + durable player character 种子 + AI cast 种子——**一个短事务全或无**，幂等键 world_id，重放同形 no-op/异形 CONFLICT；清偿「真原子创建服务」后刀义务）；(b) **provider 协议面** `elc/world/providers.py`（Writer→正文 / Planner→dossier 内容 / Resolver→`Adjudication` 三 Protocol + **一个可控 deterministic fake 实现**——端到端可重复、可测、CI 可跑；真实 LLM 接线复用 persona provider/validator/streaming 基础，是「好玩」亲验前的显式一步，**不在本刀**；Resolver 唯一裁定权不松；**POV-safe context compilation 硬门**在 fake 面上以显式上下文装配立形——provider 只收该 POV 可见面）；(c) **V3 管线编排器** `elc/world/pipeline.py`（确定性编排循环：按 RA §27 图调用既有库面——open_next_chapter/open_scene/write_segment/open_gate/submit_gate/begin_resolving/commit_action/replan_scene/apply_action_replan/settle_chapter；**自身零写权、不新开事务**——一切写入由被编排库面在自家短事务落，N-R-INV-004 不变；**崩溃续跑**从 `recovery_scan` 六族读数续跑——清偿「replan 消费的自动路由归管线刀」登记）。
3. **零迁移（四查④）**：本刀不新增表——provider 协议/编排器/原子创建服务全是代码面（V3-1 先例：地基在前刀、首个生产消费者纯代码）。搬迁面 = 仅 aoci.code.txt 新模块条目 + 散文扫尾（若有）；无 conftest/GLOBAL_CONTENT_TABLES 变动。
4. **计划时效（四查③）**：V3-7 收口 DEC…14「下一动 = V3-8」+ 窗口回归册前置族——现行有效；范式篇 §10.2/§10.3 未推翻。
5. **范围收紧与登记**：**真实 LLM 调用不在本刀**（fake provider 接线）；**最小阅读面 / 用户「好玩」亲验不在本刀**（归 V3-8 本体）；**多世界 UI / 多主角**不动（MVP 规模纪律）；**legacy V2 链**不动；**P1 传闻失真**维持后置（触发未到）。**窗口回归册核对**：reader 渲染 ack 面、record_exposure race-free 形态、chapter_activated 读时推导、散文扫尾候选（time.py 现在时句等）——本刀触 pipeline/providers 新模块即登记，其余维持。
6. **禁改面**：behavioral_baselines 一字节不动；sealed 0029–0037 不改；v3_cognition_view / v3_memory_view 行为不破（钉族全绿）；reader_exposure 写面不动；host.py legacy C1 不动。
7. **门**：pytest（自 6156 起）/ruff/mypy（199 起）/compileall 亲跑全绿；新钉族 tests/world/test_v3_8a_*.py。

授权：V3-7 收口「下一动 = V3-8」+ 窗口回归册前置族；DMCP 开工裁决 `DEC-OPI-06b954e0-5f60-4252-b1de-177cfbee396f.2`（rev 810）；范围裁决 = 先拆前置刀（自治——用户未答范围问询，按推荐路径与全程「确定性基线先行」先例）。

### v1.7.1 — 2026-10-13 V3-8a 独立评审处置（ACCEPT-WITH-FINDINGS 无 HIGH/MEDIUM；授权：评审结论转呈）

**结论**：V3-8a **维持推进**（不重开）；三面逐项在码在册；**点名变异组全红**（原子性/重放/异形/事务纪律/tick 纪律/POV-safe/义务路由/异 submission_id/`_tx` 行为保持——后者经机械证据〔五对 INSERT 表达式逐字节全同〕额外证实）；禁改面全空；吸收完整性确认；副本全量 6181/0/0 + 静态三门（mypy 202）绿。F1/F2 LOW 修（总控亲写），F3/F4 INFO 留痕登记。

1. **执行者中断与吸收（如实留痕，防坑㊲ 第二型，本程序第三次）**：执行者派单后 600s 静默中断（长命令），遗留**未提交半成品**（8 文件：4 新〔bootstrap/pipeline/providers/test_v3_8a〕+ 4 改〔aoci/bible/cast/store 新增 `_tx` 臂〕）。总控取证（新钉 25/25 绿、全量 6181/0/0、ruff/mypy(202)/compileall 全绿、零迁移、禁改面空、无残标、三面逐面在码）→ 裁**「吸收+复核」**→ 代提交 **`04c5d8f`**（8 文件 +4180/−82；提交信息载明中断与吸收裁定）。
2. **F1（LOW，修）**：管线纪律钉 AST 缺口——`test_the_pipeline_holds_no_transaction_and_spells_no_sql` 的属性扫描只拦 `execute`，`commit`/`rollback`/`with conn:` 形态存活（变异 M4b/M4c 绿）。修：属性集扩为 `{"execute","executemany","executescript","commit","rollback"}`（Gate-2 词表；同仓三先例钉〔test_v3_6/test_v3_6r/test_v3_7〕同款的补齐）。**现码零此类调用，钉是纪律加固**。
3. **F2（LOW，修）**：POV 硬门的「最后一跳地址」未校验——`pov_context_of` 只校 `context.pov_actor_id == dossier.pov_actor_id`，未校两内层读面（cognition/memory）的 `viewer_id` 同址；仓外误构造（pov 匹配但内层读面异址）会静默编译。修：门内补两条校验（cognition.viewer_id 与 memory.viewer_id 均须 == pov_actor_id，违则 ValueError）+ 新钉 `test_the_pov_context_refuses_a_mis_addressed_inner_view`（两种异址各拒）。
4. **F3（INFO，登记）**：resume 不重建站立 `outcome_ref`——NCP-2 后/续段前崩溃窗口，resume 只报告 ACTIVE 场景（不路由）；调用方只驱新段则吃 writer 强制律拒绝（fail-closed，安全）。设计用法 = 重放同一 beats；**V3-8 Gold Scenario 驱动接线时在 resume/驱动器调用约定里显式成文**（消费刀须知）。
5. **F4（INFO，登记）**：bootstrap 两边缘语义留档（与家族姿态一致，非本刀缺陷）——①重放读在 `BEGIN IMMEDIATE` 前（TOCTOU；并发同形创建以 UNIQUE→CONFLICT 收场而非 no-op，fail-closed 零部分写，单连接 MVP 不可达，多连接部署刀需知）；②组内非 `sqlite3.Error` 异常与失败的 COMMIT 不映射为 Result（异常外逸、连接暂留——与 store 家族既有姿态一致）。另：「重放写第二 bible 行」在存储层被 `UNIQUE(world_id, revision)` + CURRENT 部分唯一索引挡住（与 M2 world 行变体双保险）。
6. **遗留（评审明示）**：真实 LLM 接线/最小阅读面/用户「好玩」亲验按合同归 V3-8 本体，本刀未越位；`action_duration_ticks` 单实例校准语义文档化在案，V3-8 换真实 resolver 时须保持崩溃重试同值。

授权：独立评审（executor-pro 新上下文只读 + 仓外副本 `D:\v38a_review\` / `D:\v38a_mut\`，2026-10-13）+ 总控处置（历刀先例：总控亲写）；处置提交随本条目同刀。

### v1.7.2 — 2026-10-13 V3-8b 开工裁决（外审〔基于 HEAD 10b4489〕范围受限修正刀：3 HIGH + 1 HARD GATE + 1 MEDIUM-HIGH；授权：外审结论转呈）

**结论**：V3-7/V3-8a 主体方向正确，但**进 V3-8 本体（Gold Scenario/真实 provider 接线）前须先修五面**——不开始 UI、不开始旧链退役（外审明令）。合同增量（STATE §21 SETTLING 前置律 + §25 NCP-4 修订 + DOMAIN §20.2 authority 表改写 + DATA §26.2.1 V3-7 块 hooks 修订 + RA §27 V3-8b 修订段）与代码同刀提交。

1. **HIGH-1 关闭「章 CLOSED / 场 ACTIVE」非法状态**：SETTLING 前置律闸门落 `SqliteNarrativeStore.settle_chapter`（ACTIVE→SETTLING 翻转面）——进 SETTLING 前同事务校验四者：无 `ACTIVE` 场、无 `OPEN`/`ANSWERED`/`RESOLVING`/`COMMITTED`-未-`CLOSED` gate、无 `PENDING` `action_replan` 义务（任一存在 ⇒ `VALIDATION_FAILED` 且零状态改变）；剩余 `PLANNED` 场由调用方先显式 `DISCARDED`（不得要求所有计划场都必须发生，但不得存在仍运行中的故事）。**反转 V3-7 的 `_settling_chapter` 夹具语义**（曾允许 ACTIVE 场下结算）——V3-7 钉族随迁。行为钉：ACTIVE 场存在时拒且零状态改变；未决 gate/PENDING replan 同理。
2. **HIGH-2 ResolverProvider 权威输入**：`AdjudicationContext` 升格为 world-authoritative **`ResolverContext`**——CURRENT World Bible/hard rules + relevant `world_state_fact` + player profile（abilities/limits）+ 当前 location/physical state + inventory/resource state + scene/environment canonical facts + relevant counterpart state + 用户提交（intent/option）+ 当前 POV 面。**玩家的 knowledge/memory 用于判断「用户角色知道什么」，不是 Resolver 自身的知识上限**；Resolver 知道真实世界规则与物理事实，但仍不替用户发明 intent（N-INV-002 不松）。`User Intent → ResolverProvider(world authority + player state + knowledge) → Adjudication → NCP-2` 不变。
3. **HIGH-3 CHAPTER replan 回归 World Director**：provider 分工重冻结——`PlannerProvider` 只管 **SCENE** 级（dossier 内容/SCENE replan，POV cognition/memory + 当前场景状态为主要输入）；**新 `DirectorProvider`** 管**初次 Chapter Blueprint + CHAPTER replan**，输入基于 `DirectorContext` 全知面（Bible/current facts/full cast/active storylines/chapter settlements/current_tick）+ 触发本 replan 的 action/reason。`Director.apply_action_replan` 继续负责 validation/persistence，Blueprint **生产权**不由 POV-limited PlannerProvider 代替。
4. **HARD GATE（结构验收第 12 条前置）committed action 的 continuation obligation**：recovery 识别 `gate=COMMITTED 未 CLOSED 且无 continuation passage` 窗口，恢复 `scene_id`/`gate_id`/committed `user_action_id`（outcome_ref）/`next_segment_seq`；Pipeline 从 durable state 续生成第一条 continuation passage（强制 `outcome_ref`、同事务 CLOSED gate）——**不要求调用方依赖进程内记忆重供旧 GateBeat**。取消/降级外部 `first_segment_seq` 状态，Pipeline 从 `segment_commit` durable rows 推导下一 `segment_seq`。`recovery_scan` 增**第七族**（`COMMITTED` 未 `CLOSED` gate 且其场无 outcome_ref 指向它的 passage）；`resume` 路由该族。
5. **MEDIUM-HIGH 禁止 Blueprint 直接升级为 Narrative Memory hook**：`chapter_settlement.hooks` 不复制 `chapter_questions_to_advance`（Plan 内容不因结算自动升级为 Narrative Memory——防 Plan→Memory 软铁路回流）；确定性基线无可靠 hook extraction ⇒ **`hooks = ""`（空串诚实）**；`created_at_revision` 保留为 plan provenance（只溯源不搬运内容）；真 hook extraction（已发生伏笔/已暴露问题/已建立未决悬念——Canon/Reader-visible 面）归后刀。
6. **范围收紧与纪律**：**零迁移**（不改表——全是代码面与读面）；搬迁面 = aoci.code.txt 受影响模块条目 + 散文扫尾；**不开始 UI、不退役旧链**（外审明令）；真实 LLM 接线/最小阅读面/好玩亲验仍归 V3-8 本体（本刀修完后才进）。**禁改面**：behavioral_baselines/sealed 0029–0037/v3_cognition_view/v3_memory_view 行为/reader_exposure 写面/legacy V2 链/host.py legacy C1 不动。**门**：pytest（自 6182 起）/ruff/mypy（202 起）/compileall 全绿；新钉族 tests/world/test_v3_8b_*.py + 受影响既有钉族随迁。

授权：外审（用户转呈，基于 HEAD 10b4489，2026-10-13）；DMCP 开工裁决 `DEC-OPI-06b954e0-…15`（rev 814）。**其后**：五面修完才进 V3-8 本体（真实 provider wiring → 固定 Gold Scenario → 结构验收 12 条 → 最小阅读面 → 用户亲验「好玩」）；结构 12 条与「好玩」双门通过前不切主 UI、不退役 Legacy V2。

### v1.7.3 — 2026-10-13 V3-8b 独立评审处置（ACCEPT-WITH-FINDINGS 无 HIGH/MEDIUM 阻断；F1 MEDIUM-HIGH 升格本刀修；授权：评审结论转呈）

**结论**：V3-8b **维持推进**（不重开）；五面逐项在码在册；**点名变异组全红**（SETTLING 三查/拒绝零状态改变/ResolverContext 各臂/resolver 不造 intent/CHAPTER replan 归 DirectorProvider/第七族/outcome_ref 强制/next_segment_seq 推导/hooks=\"\"）；V3-7/V3-8a 迁移钉族未弱化；F3（continuation obligation）清偿属实；吸收完整性确认；副本全量 6205/0/0 + 静态三门绿。F1（MEDIUM-HIGH，HIGH-1 同族旁门）**升格本刀修**；F2/F3/F4 INFO 留痕登记。

1. **执行者中断与吸收（如实留痕，防坑㊲ 第二型，本程序第四例）**：执行者 600s 静默中断遗留半成品（10 文件），总控取证（新钉 22/22+受影响三族 73/73 绿、全量 6205/0/0、静态三门绿、零迁移、禁改面空、无残标、五面逐面在码）→ 裁「吸收+复核」→ 代提交 **`73f6fd7`**（10 文件 +2560/−291）。
2. **F1（MEDIUM-HIGH，升格本刀修——P4-2「RA 明文要求级缺口不因自报免做」先例 + HIGH-1 同族）**：SETTLING 前置律钉在翻转面，但「章 CLOSED/场 ACTIVE」仍可经「结算后激活剩余 PLANNED 场」两步合成——`activate_scene`/`open_scene` 无章状态守卫。修：`SqliteNarrativeStore.activate_scene` 增章状态守卫（场所属章为 `SETTLING`/`CLOSED` ⇒ `VALIDATION_FAILED` 零状态改变，场仍 PLANNED）——「settling/closed chapter opens no new scene」；新钉 `test_a_settled_chapter_opens_no_new_scene`（SETTLING 与 CLOSED 两态各拒）。**现码已零此旁门**（评审实测两门均闭：翻转面 HIGH-1 闸 + 本守卫）。
3. **F2（INFO，登记）**：「next_segment_seq 从 segment_commit durable rows 推导」无源表级钉——源表换成 `narrative_passage` 全绿（观测等价：两表每段同事务成对落行、ACTION_OUTCOME 行 seq 为 NULL）。非行为覆盖洞，登记为源文措辞未钉（如需字面钉归后刀）。
4. **F3（INFO，维护须知）**：`test_the_settling_precondition_rides_the_flip_transaction` 只查事务常量与 SQL 字面，`if False and …` 型禁用可绕过——行为钉（M1–M4 全红）承担实质捕获，现役组合无洞。
5. **F4（INFO，措辞歧义交 V3-8 接线前裁）**：DOMAIN §20.2「**玩家**的 knowledge/memory 用于判断『用户角色知道什么』」与交付的知识臂实为**场景 POV** 的 cognition/memory 之间的措辞歧义——RA §27 枚举面写「+ 当前 POV 面」故交付不违约；当场景 POV≠玩家角色时该臂并非「用户知道什么」。确定性基线下惰性，**真实 resolver 接线前合同澄清（POV 面即知识臂）或增读 player-view——归 V3-8 本体开工四查**。

授权：独立评审（executor-pro 新上下文只读 + 仓外副本 `D:\v38b_review\` / `D:\v38b_mut\`，2026-10-13）+ 总控处置（历刀先例：总控亲写）；处置提交随本条目同刀。

### v1.7.4 — 2026-10-13 V3-8c 开工裁决（真实 LLM 接线 + F4 裁定落地；授权：V3-8b 收口 `DEC-OPI-06b954e0-…24`「下一动 = V3-8 本体」+ 用户凭证明示）

**结论**：V3-8 本体拆三刀开工——**V3-8c（本刀：真实 LLM 接线 + F4）** → V3-8d（Gold Scenario + 结构验收 12 条）→ V3-8e（最小阅读面 + render ack）。本刀把 `elc/world/providers.py` 冻结的四个 Protocol 落成真实 LLM 实现（缝 + prompt 装配 + 严格解析 + 失败语义），并把 V3-8b 登记的开工四查必裁项 **F4**（DOMAIN §20.2「玩家」与交付知识臂〔场景 POV〕的措辞歧义）裁定落地：**增读 player-view 并保留 POV 面**。合同增量（DOMAIN §20.2 行精确化 + RA §27 F4 补注）与代码同刀提交。

1. **新模块 `elc/world/llm_providers.py`（缝 + 四实现）**：窄缝 `TextCompletion.complete(prompt) -> CompletionOutcome`（`text`/`error` 值语义、冻结；streaming 面 `complete_streaming` 登记为扩展点，本刀不实现——阅读面 UX 需要时由后刀显式重开）；四类**结构性**满足 providers.py 四 Protocol（无继承）——`LlmWriterProvider.write_segment(PovContext)->str` / `LlmPlannerProvider.plan_scene·replan_element(ScenePlanContext)->Mapping` / `LlmDirectorProvider.draft_blueprint·replan_blueprint(DirectorPlanContext)->Mapping` / `LlmResolverProvider.adjudicate(ResolverContext)->Adjudication`（输出形逐字照 `elc/world/action.py`）。**绝不通 import `elc.persona`**（`elc.world` 保持无编译期跨包引用边——P4-3 冷启动纪律；persona 的 BYOK egress——`OpenAICompatibleProvider` + `SecretSource`——由装配面〔V3-8e 阅读面〕适配进缝；本刀零真实网络调用、零凭证读取）。
2. **提示词装配（本刀核心价值）**：全部为纯函数（context → prompt str）——**Writer**：系统指令（one main POV、限知——只写 POV 可知可见者、不替用户角色做有意义的意志决定/发言〔N-INV-002〕、不写未来与未成立之事、只呈现已成立结果、英文正文）+ 场计划面（`place`/`entry_goals`/`exit_condition`/`revealable`/`must_hide` 逐条硬禁令）+ 该 POV 自己的 cognition/memory + `segment_seq`/`current_tick`/participants（**POV-safe 硬门=装配只读 PovContext 携带面**——无他者私有读可载入）；**Planner**：element 九键（`pov_actor_id`/`participants`/`planned_start_tick`/`place`/`entry_goals`/`exit_condition`/`elasticity`/`revealable`/`must_hide`，照 `pipeline._element_mapping_of`）；**Director**：章九字段 + scenes 元素十键含 `purpose`（照 `_blueprint_mapping_of`/`BLUEPRINT_SCENE_KEYS`）、**软期望措辞律入 prompt**（closing_pressure 等只表达「朝哪里压」，不是 postcondition——软期望永不作为硬条件）、replan 臂携 `chapter_id`/`replan_request_id`/触发裁定全文/当前 Blueprint；**Resolver**：world-authority 全臂（Bible/hard rules、current facts、player abilities/limits、place/participants、counterparts）+ **F4 玩家知识臂** + POV 叙述面 + submission（intent/selected_option/options）；intent 非 fact、不替用户发明 intent、按世界规则/物理/参与者能力裁定。
3. **严格解析**：剥首尾空白与单层 markdown 围栏（`json` 标注或裸围栏；确定性最小清洗，规则成文）后必须为 JSON **对象**；各键存在且类型正确（`participants` 字符串数组、`state_effects` 照 `StateEffect` 形、`replan_scope` 三词之一）；缺失/类型错 ⇒ 拒；**多余键忽略**（宽容）。
4. **失败语义**：V3 Protocol 面（已盖章冻结）无 Result 通道 ⇒ 真实实现的运行时失败经异常外逸——`LlmProviderError`（模块自含；`reason` 短 body-free 码：`transport-error`/`no-output`/`bad-payload`/`missing-field:<name>`/`bad-shape`；**绝不回带 prompt/机密**——调用方〔驱动/阅读面〕负责转 Err/HTTP）。与 fake 的 `ValueError`（程序错误姿态）同为「拒」，姿态分族：本类是运行时错误姿态（模块 docstring 成文）。
5. **纪律（AST 钉承重）**：模块不持 `sqlite3.Connection`、零 SQL、零事务（无 `execute`/`commit`/`rollback` 属性调用、无 `BEGIN` 字面）、不持时钟（无 `datetime.now`/`time.time`）；一切调用在事务外（不触 DB——结构性保证）；值语义/冻结记录；`__all__` 明确导出；新模块不广出（不进 `world/__init__`）。
6. **F4 裁定落地（增读 player-view 并保留 POV 面）**：`ResolverContext` 增 `player_cognition`/`player_memory` 两字段（**保留**现有 `pov_actor_id`/`cognition`/`memory` 不动——RA §27「＋ 当前 POV 面」继续为真）——语义：**世界声明了玩家角色时**=玩家角色自身的读面（`viewer_id == player_character_id`），即「用户角色知道什么」的权威判据；**无玩家** ⇒ 两字段 `None`（与 `player_character` 同条件律）。`pipeline._resolver_context_of`：player 存在时增两读 `v3_cognition_view`/`v3_memory_view(viewer=player_character_id)`（错误面照既有风格 `Err` 外逸）。合同措辞精确化：DOMAIN §20.2「Resolver 裁定的权威输入」行 + RA §27 V3-8b 段补注（一句，V3-8c F4）——POV 面为叙述面、不作「用户知道什么」判据。**钉随迁**：8a/8b 两族凡构造/断言 `ResolverContext` 处补 player 臂断言（player 声明时 `player_cognition.viewer_id == player_character_id` 且 `player_memory.viewer_id` 同址；无玩家世界两字段 `None`——落 8c 族）；field-set 冻结钉纳入两新字段；**不弱化既有断言**。
7. **范围与登记**：**零迁移**（不新增表）；真实网络调用/凭证读取**不在本刀**（缝上适配归 V3-8e）；**最小阅读面/结构验收 12 条/用户「好玩」亲验归 V3-8d/e**；多世界 UI / 多主角不动（MVP 规模纪律）。**禁改面**：`behavioral_baselines/**` 一字节不动；sealed `0029–0037` 不改；`v3_cognition_view`/`v3_memory_view` 行为不破（各钉族全绿）；`reader_exposure` 写面语义不动；legacy V2 链与现役 UI（`src/elc/web.py` 既有路由、`src/elc/webui/**`）不动；`src/elc/persona/**` 既有面不改（本刀根本不 import 它）；`host.py` legacy C1 不动；零新依赖（stdlib only；`pyproject.toml` 不动）。**门**：pytest（自 6206 起）/ruff/mypy（202→203 files）/compileall 亲跑全绿；新钉族 `tests/world/test_v3_8c_*.py` + 受影响 8a/8b 两族随迁。**双门纪律不变**：结构验收 12 条全绿 + 用户亲验「好玩」两者同时通过前，不切主 UI、不退役 Legacy V2（外审明令）。

授权：V3-8b 收口 `DEC-OPI-06b954e0-…24`（rev 817）「下一动 = V3-8 本体」+ 用户明示（本机已配 OpenAI 兼容凭证、直接接线；「好玩」亲验以真实 LLM 跑 Gold Scenario 收官）；DMCP 开工裁决 `DEC-OPI-cddb517c-dafb-4a64-a99e-0a691394156e.5`（rev 818）；三件 = TASK `…7`（rev 819）/ VAL `…9`（rev 820）。

### v1.7.5 — 2026-10-13 V3-8c 独立评审处置（ACCEPT-WITH-FINDINGS 无 HIGH/MEDIUM 阻断；F1/F2/F3 升格本刀修；授权：评审结论转呈）

**结论**：V3-8c **维持推进**（不重开）；真实 LLM 接线的四实现 / POV-safe 装配 / 严格解析 / 失败姿态与 F4 四处逐项在码在册；**点名变异全红**（执行者 M1–M4 评审抽验一致 + 评审自加 V1–V6 相邻面变异全按预期红且零溢出）；POV-safe 硬门（prompt 级端到端）与解析拒绝族经独立 AST/探针复核；禁改面零触碰；零迁移；副本四族 88/0 + collect 6226 + 静态三门绿。F1/F2/F3（LOW/INFO）**升格本刀修**（总控亲写，提交 `b63fcbb`）；F4 口径确认（不改码）；F5 INFO 登记。

1. **F1（LOW，修——防坑㉘ 散文扫尾补全）**：`writer.py`「provider Writer 硬门」段的「this docstring is its in-repo record **until that cut lands**」随 V3-8c 落地已成假句 ⇒ 改为「POV-safe compilation **landed in V3-8c**」（compiled by `pov_context_of`〔V3-8a〕+ rendered by `llm_providers`〔V3-8c〕；「好玩」仍待装配面接线与 Gold Scenario 双门）；`pipeline.py` 三处同族陈旧句（`SegmentBeat`「the LLM planner's seat in a later wiring」／`Pipeline` 类 docstring「the LLM resolver judging its own duration is the later wiring」／`_drive_continuation`「the planner's seat in the LLM wiring」）统一为「LLM faces landed in V3-8c；该席位分配是 later, explicit cut」口径。**`settlement.py:1206`「registered later cuts」复核判仍真**（LLM summary 未落）——不改，入窗口回归册后刀扫尾。
2. **F2（LOW，修）**：`llm_providers.py` 删两个死常量 `_BLUEPRINT_SCENE_TEXT_KEYS`／`_BLUEPRINT_TEXT_KEYS`（评审 AST 扫描 `loads=[]` 实证零引用；删除零行为改动；`_parse_blueprint` 手工逐键展开不变）。
3. **F3（INFO，修）**：`_clean` docstring 补「闭合围栏可缺省」档（实现本已容忍 open-only 围栏，宽容方向安全——文档与实现对齐）。
4. **F4（LOW，口径确认，不改码）**：DMCP 开工裁决 `DEC-OPI-cddb517c-…5`／TASK `…7` 原文的「失败值语义／不 raise」指**缝**（`TextCompletion`）与解析的判定形态；`ResolverContext` 等冻结 Protocol 面无 Result 通道 ⇒ 四实现类的**运行时失败以 `LlmProviderError` 异常外逸承载**（与 fake 的 `ValueError` 程序错误姿态分族；模块 docstring 成文；REGISTER v1.7.4 第 4 点已登记）。收口 DEC 同载——**口径确认留痕，不 amend 纪律⑱**。
5. **F5（INFO，登记）**：`llm_providers.py` AST 纪律钉（零 SQL/事务/时钟）为 attr 词表扫——P4-2 先例（取方法值绕过）可绕，**维护须知 = 结构性论据优先**（构造面不收 conn／运行时 import 面仅两值形状／`import elc.world` 不加载该模块——评审三证在案）；入窗口回归册。
6. **遗留登记**：persona BYOK egress → `TextCompletion` 适配器归 **V3-8e**（本刀零网络/零凭证）；缝的 streaming 扩展点（`complete_streaming`）后刀按需显式重开；解析宽容度边界（多行围栏内嵌文本/前置说明文本拒；多余键忽略并丢弃）成文并钉。
7. **处置后四门完整重跑（防坑㉞）**：pytest 6226/0/0（分段合计核验）、ruff clean、mypy 203 files clean、compileall clean、drift 19/19。

授权：独立评审（executor-pro 新上下文只读 + 仓外副本 `D:\v38c_review\`／`D:\v38c_mut_r\`，2026-10-13）+ 总控处置（历刀先例：总控亲写）；处置提交 `b63fcbb`，本条目为处置留痕。

### v1.7.6 — 2026-10-13 V3-8d 开工裁决（Gold Scenario 端到端 + 结构验收 12 条；授权：V3-8c 收口 `DEC-OPI-cddb517c-…17`「下一动 = V3-8d」）

**结论**：把设计篇 §10.2 的固定 Gold Scenario 落为**可执行 fixture**（新模块 `elc/world/gold.py`），并把 12 条结构验收逐条立钉（新钉族 `tests/world/test_v3_8_gold_gates.py`）——**全部经真实接线**（`elc/world/llm_providers.py` 四实现）＋脚本化 completion 驱动，**离线、0 skipped、CI 可跑**。零迁移、零新依赖；禁改面见下。其后 V3-8e（最小阅读面）＋用户亲验「好玩」＝双门（**双门通过前不切主 UI、不退役 Legacy V2**——外审明令不变）。

1. **固定要素（范式篇 §10.2，逐字保留）**：帝国历 105 年 10 月 1 日；主角莉亚（AI，`PROTAGONIST`、`pov_eligible`）；用户角色＝远房表弟（`cousin`）；父亲凌晨赴帝都（tick 300＝05:00）；母亲上午从乡下带用户回来（tick 480＝08:00）；玩家与莉亚第一次见面；**至少一次自由 User Gate**；ActionResolver 裁定；按用户选择继续；第一章结束；Settlement；生成第二章 Blueprint。**日历**：`BibleContent.calendar` 声明 1 tick＝1 分钟、tick 0＝105-10-01 00:00；`hard_rules` 至少一条真约束（「帝都来的信最快次日才到…」）；Bible 十四字段齐。
2. **新模块 `gold.py`＝库面固定夹具**（骨架固定、prose/蓝图措辞随 provider；供本刀钉族＋V3-8e 阅读面复用）：`seed_gold_world`（persona 卡前导＋`create_world_with_bible` 原子创建；同形重放零写）/ `gold_beats_by_scene`（**≥3 场**：s01 初见〔Lia POV；段 1–2 → **恰一门** GateBeat〔2–4 自然选项＋`submission_id`＋`intent_text` 自由输入、`selected_option=None`，意图令原计划失效〕→ 后随段携 `outcome_ref`〕、s02、s03〔读得到 s02 已 commit 之事〕）/ 三场由第一章 Blueprint 计划并逐一 `run_scene` 驱动；固定 payload：CH1 Blueprint（九章字段＋scenes 非空，元素十键含 `purpose`；**初始蓝图含 ≥2 后续场**，使 CHAPTER replan 有「剩余部分」可失效）、CHAPTER replan 后新 Blueprint（不再指认被失效旧场／按裁定方向发展）、第二章 Blueprint（引用第一章真发生之事）、`Adjudication`（**`replan_scope=CHAPTER`**＋至少一条真实 `state_effect`〔⑪ 断言进 current facts〕＋participants 含玩家与莉亚＋consequences 指明原计划不成立）；**must_hide**＝scene 1 dossier 携真秘密双片段（「the sealed letter from the capital」/「the Imperial post's red seal」），剧本至少一处触其边缘不泄露；**脚本化 completion**＝`TextCompletion` 缝实现，**按 prompt 内容键定答复**（writer=(place, segment_seq)、resolver=intent_text、director replan=replan_request_id、director 初次=标记序首中〔CH1 定居摘要标记→第二章；None 兜底→第一章〕、planner=scene_id），**未编剧一律 `GoldScriptError` 响亮拒、绝不静默胡答**，全 prompt 按臂记录（「provider 能看见什么」的可证形）；一切 payload 逐字过 `director.py`/`scene.py` 的 `_checked_fields`/`validate_blueprint` 校验面。
3. **12 条结构验收（逐条一个钉，`test_gate01_…`…`test_gate12_…`，经真实接线、离线 0 skipped）**：① Director 产出完整 Blueprint（落库九字段与脚本一致、scenes 非空、记录面含 Bible/cast/current_tick）；② Writer 正确保持莉亚 POV（POV 视野面 viewer==lia、prompt 不含他者私有记忆——组件对照）；③ 秘密没有提前泄漏（≥2 断言：prompt 逐条禁令／泄漏样张被 `PovWriter` 拒 `VALIDATION_FAILED` 点名片段／落地 passages 全文不含片段）；④ User Gate 只在真实意志点触发（整链恰一门、选项 2–4、开门时点＝脚本意志点、自由输入提交路径可用）；⑤ 用户自由输入被 Resolver 裁定（意图自 durable `user_action` 行进；裁定落 canon 八列；**intent 文本不入 world_event**）；⑥ 一个用户选择真正让原计划失效（`replan_scope=CHAPTER` → 义务出生＋APPLIED；`apply_action_replan` 落 **plan revision 2**；旧计划剩余场按 §24 不再被采纳）；⑦ replan 后没有强行绕回旧计划（后续 prompt 内容＝replan 后内容；DISCARDED 场永不复活/激活/指认）；⑧ Scene 3 能读取 Scene 2 已 commit 的事实（`SceneContext` cognition/memory＋`v3_memory_view`/`v3_cognition_view` viewer=lia；writer prompt 含该事实文本）；⑨ 第一章实际结果与 Blueprint 可以明显不同（actual_end 超出初始 planned_end／roster 差异）且系统诚实记录（无对账强迫、无改写已 commit 面）；⑩ Settlement 生成摘要（lineage 行；tick 不推进；N-INV-004 存储面）；⑪ Chapter 2 使用真实 Chapter 1 结果（DirectorPlanContext 含 ch1 settlement summary **且**含裁定 state_effect 进入的 current fact；ch2 Blueprint 落库）；⑫ 重启后能从最新 narrative state 恢复（**文件库**；门 COMMITTED 未 CLOSED 的 V3-8b 第七族窗口——关连接重开新连接 → `Pipeline.resume` → `continuations_driven=[gate]`；续段带 `outcome_ref`、同 commit 门 CLOSED；**无二次裁定**；随后可继续驱动剩余场）。
4. **诚实边界（本刀成文）**：脚本化 completion 下驱动的 12 条＝**结构验收**（provider 为真实四实现、无网络调用、无模型判语）；**用户「好玩」亲验归 V3-8e**（真实 LLM 装配面）；双门（12 条全绿＋亲验「好玩」）同时通过前不切主 UI、不退役 Legacy V2；真实 rollout 仍 HOLD（SessionBudget 三分＋内容补课为开闸前置）。
5. **范围与纪律**：**零迁移**（不新增表）；零新依赖（stdlib only；`pyproject.toml` 不动）；**c revisit（`DEC-OPI-cddb517c-…17` 的 revisit 条件）**：场景驱动若暴露 `llm_providers` 的 prompt/解析真需求 ⇒ 本刀内修（改动面限 `llm_providers.py`/`gold.py`，**不得改 `providers.py` 协议语义**）；无需求则报告明写并列出核过面。**禁改面**：`behavioral_baselines/**` 一字节不改；`migrations/0029–0037` sealed 不改；`v3_cognition_view`/`v3_memory_view` 行为不破；`reader_exposure` 写面语义不动；legacy V2 链与现役 UI（`web.py` 既有路由、`webui/**`）不动；`src/elc/persona/**` 不改；`host.py` legacy C1 不动；**`providers.py` 协议面语义不改**。**门**：pytest（自 6226 起）/ruff/mypy（203→204 files）/compileall 亲跑全绿；新钉族 `tests/world/test_v3_8_gold_gates.py` + drift 钉（`tests/world/test_aoci_drift.py`）全绿；台账随迁（`aoci.code.txt` 新 `gold.py[GD8T]` 条目）。

授权：V3-8c 收口 `DEC-OPI-cddb517c-…17`（rev 821「下一动 = V3-8d」）；DMCP 开工裁决 `DEC-OPI-cddb517c-dafb-4a64-a99e-0a691394156e.19`（rev 822）；三件 = TASK `…21`（rev 823）/ VAL `…23`（rev 824，路径集=所触面）。

### v1.7.7 — 2026-10-13 V3-8d 独立评审处置（ACCEPT-WITH-FINDINGS 无 HIGH/MEDIUM 阻断；F1/F2 升格本刀修；授权：评审结论转呈）

**结论**：V3-8d **维持推进**（不重开）；固定要素 **11/11 保真**（§10.2/PLAN §20 逐条核，无违背；命名级细节诚实分级）；**12 条结构门全为行为钉**（真驱动链 + durable 面；无 `if False` 型可绕过钉）；**c revisit 证实成立**（`git diff c4756ba..HEAD -- src/elc/world/llm_providers.py` 空；四臂覆盖经记录 prompt 逐字核过、planner 臂不在本链有结构证据 + gate07 钉）；禁改面零触碰；零迁移。**点名变异全红**（执行者 M1–M6 评审抽验一致〔M1/M3 等价重建，M2/M4/M5/M6 日志签名核对〕+ 评审自加 6 组相邻面变异：A ⑩⑪／B 全链 12 红／C ⑥⑦⑨／**D 幸存→分工结论**〔viewer 过滤由 V3-7 隔离钉承重，Gold 族不重复〕／E 全链／F ⑫）。四族亲跑 105/0 + collect 6243 + 静态三门绿；总控亲跑全量 6243/0/0。F1/F2（LOW）**升格本刀修**（总控亲写，提交 `cccae95`）；F3/F4/F5（INFO）登记。

1. **F1（LOW，修）**：`gold.py` `GOLD_PROSE` 注释的「post-gate continuation takes the (gate, 2) entry」失实——**两窗都取 `(gate, 3)`**：全驱＝段 1–2＋门后段 3；崩溃续窗 ordinal＝`max(segment_seq)+1`＝3（ACTION_OUTCOME 行 seq 为 NULL）。评审探针实证（`p0003 seq=3`）＋MUT-F 拒绝消息互证。改为两窗同键的键定律措辞（V3-8e 复用照读）。
2. **F2（LOW，修）**：`gold.py` `MOTHER_PRIVATE` 注释「rides the Director's and the Resolver's prompts」中 Resolver 半句失实——本夹具 Resolver counterparts＝裁定场 participants−玩家＝仅 Lia，Mother 非任何场景参与者 ⇒ Resolver prompt 不载之（评审探针：`arm=resolver MOTHER_PRIVATE_in=[]`）；Director 载（3 prompt 全命）/Writer 不载（0 命中）为真。②钉的组件对照只主张 Director 面（与实测一致，无测试受骗）。
3. **F3（INFO，登记）**：viewer 过滤面在 Gold 族不可观测（变异 D 幸存）——分工：V3-7 隔离钉承重（同变异下该族红）；无需动作（未来若愿 Gold 族自守可加一条参与者私有记忆行）。
4. **F4（INFO，登记）**：④无负控面（「无 GateBeat 则零门」型未断言；库面 `open_gate` 自拒 <2 选项为次级见证）——后刀可选加，不阻断。
5. **F5（INFO，登记）**：执行者变异 M1–M6 的操作脚本未随日志留档、时间戳早于最终提交（补钉不在其路径上、最终树已全绿）——**后续刀纪律提示：变异操作随日志留档**。
6. **遗留观察（非缺陷）**：`GoldScriptError` 经缝以异常外逸（无 Result 通道的既定姿态）——V3-8e 在装配层承接该姿态（转 Err/HTTP）；脚本 completion 的匹配依赖（place 唯一 / intent 唯一 / director 首中标记）在 gold 场景内成立，扩场景需扩键。
7. **处置后四门完整重跑（防坑㉞）**：pytest 6243/0/0（702+1017+2653+1871 分段合计）、ruff clean、mypy 204 files clean、compileall clean、drift 19/19。

授权：独立评审（executor-pro 新上下文只读 + 仓外副本 `D:\v38d_review\`／`D:\v38d_mut2\`，2026-10-13）+ 总控处置（历刀先例：总控亲写）；处置提交 `cccae95`，本条目为处置留痕。

### v1.7.8 — 2026-10-13 V3-8e 开工裁决（最小阅读面 + render ack + 真实 egress 适配；授权：V3-8d 收口 `DEC-OPI-cddb517c-…29`「下一动 = V3-8e」）

**结论**：把 V3-8c 登记给装配面的 egress 适配与 V3-8d 留给「好玩」亲验的**最小阅读面**落成可运行面——`src/elc/narrative_web.py`（装配层新模块：真实 egress 适配器 + 阅读面服务面 + 回放 provider）+ `web.py` 只增路由分支与静态条目 + `webui/` 三个新文件（reader.html/css/js，独立于主 UI）。**零迁移、零新依赖（stdlib only）**；**主 UI 一个字节不改**（外审明令双门通过前不切主 UI、不退役 Legacy V2；用户明令现役 UI 不许删）。其后门 = 结构 12 条全绿（已由 V3-8d 达成）+ 用户亲验「好玩」（本刀运行面就绪后由用户以真实凭证跑）。

1. **2a 真实 egress 适配（V3-8c 登记本刀义务）**：`PersonaEgressCompletion` 把 persona 的 `OpenAICompatibleProvider`（含 `SecretSource` 解析）适配进 `TextCompletion` 缝——`ProviderOutput.text`→`CompletionOutcome(text=…)`、`error`→短码值（**失败值语义、不 raise**；短码即 persona 适配器自己的 body-free 词表）；**坐标复用现役装配**（`host.coordinator.persona_provider` **每调用读活件**——settings 的 base_url/model/secret_ref、页面 key 优先源与热换全走同一配置源，**零新凭证通道、零新配置面**）；未配置坐标/非 OpenAI 形 provider/读不到坐标 ⇒ 诚实人话（指向设置面），不静默造假；prompt 与密钥绝不回带（key-echo 由 persona 适配器上游拦）。位置在**装配层**（elc 根）——`elc.world` 不新增任何 persona 边（P4-3 纪律）；测试全程离线（注入 transport + 测试用 SecretSource，零 socket 零真凭据）。
2. **2b 阅读面（web.py 只增不改）**：路由族 `GET /v3`（reader.html）、`GET /api/v3/state`、`POST /api/v3/start|continue|submit|settle|next_chapter|ack`。语义：`start` 幂等（无 gold 世界则 `seed_gold_world`、无第一章计划则 `Pipeline.plan_chapter`；重放零写）；`state` 纯读、全自 durable 行推导（世界存在/章状态序/当前场状态 POV/本章 passages〔id/seq/body/language〕/未 CLOSED gate〔选项/状态〕/settlement/当前 adopted 计划摘要 + next 与 controls 派生面）；`continue` 一次一段（位置自 `segment_commit`/`world_scene`/`user_gate` 推导、不持进程内位置；真实 LLM 下一次写作 10–60s，页面以轮询 state + spinner 呈现进度，**不实现 streaming**）；`submit` 携 `GateBeat` 一次驱动 open→NCP-1→裁定→NCP-2→replan 自动路由→续段携 outcome_ref→门 CLOSED（库里已有提交 ⇒ 空请求体从 durable 提交续跑）；`settle`=本章计划场走完（roster 空）后 `Pipeline.settle`；`next_chapter`=`Pipeline.plan_chapter`（真实 DirectorProvider，前置=本章 CLOSED）；`ack`=已渲染 passage_id 列表 → `record_exposure`（reader_id=local-user，与对话/提交解耦、幂等；N-INV-005：零 actor_memory/belief）。**驱动政策（成文于模块 docstring 与钉族）**：作者锚场用 `gold_beats_by_scene` 作者脚本（段长/终场/门选项作者定、提交携用户自由输入），重规划新建场走最小默认（每次 1 tick 一段；「结束本场」= `is_last_segment=True`）；前缀自 durable 行重建整段重演（V3-8b 脚本律）+ **回放 provider（DurableReplayWriter/Resolver）让已 commit 面零重写、门裁定不二次判断**——每次 continue 恰一次真实写作；durable 面永远优先于脚本（replan 使场不再存在/状态不符 ⇒ state 诚实呈现、不再驱动）。**序列化纪律**：一切写路由走工作队列（一线程律）；`state` 轮询**脱队**（自开 mode=ro 短连接，`/api/teaching/current` 同姿态——驱动占队列时轮询不被 60s 超时打死、绝不 500）；长 LLM 调用全在事务外（结构性：providers 不触 DB）。**web.py 既有路由/分支一字不改**（只增：三条静态白名单条目、`_WebFace.narrative` 懒建属性、GET 两条分支、POST 六条分支）；新页面为新文件（不设主屏入口、URL 直达；组件零新增——复用 #1/#2/#3/#4 的 `.say`/#9/#12）。
3. **2c 新钉族**：`tests/host/test_v3_8e_reader.py`（离线 0 skipped）——适配器钉（text/error 值映射、timeout/http-500/not-configured/no-egress、prompt 与 key 不回带）；路由钉（start 幂等零写、continue×n 段落地与门开、submit 自由输入→裁定→续段 outcome_ref→门 CLOSED→CHAPTER replan 落 revision 2、settle→CLOSED+settlement、next_chapter 新计划、ack 曝光行落地且**不写 actor_memory/belief**）；durable 位置律（重开栈续跑同形 + 崩溃窗从 durable 提交续跑、**resolver 零二次调用、writer 零重新生成**）；轮询脱队（驱动阻塞时 state 秒答）；诚实面（未配置/非 OpenAI/host 无腿/语法 400）；页面钉（/v3 与两资产按白名单服务、零外链、主壳零引用）。主 UI 零改动 = git diff 面（评审核）+ 壳内 `/v3`/reader 零字面运行时钉。
4. **2d 台账**：`docs/FRONTEND_SPEC.md`（⑦ 架构说明增三新文件 + 8.1.3 导航模型增「试读面无坞内入口」+ 新 8.2.13 试读面节）；`aoci.code.txt`（新 `narrative_web.py[NW8E]` 条目 + `web.py[EC8L]` 增 V3-8e 路由族段 + `gold.py[GD8T]` 增 lore_refs 形记录）；drift 钉全绿。
5. **随刀真需求修（登记）**：`gold.py` persona 卡前导的 `lore_refs` 由空串改为 canonical 空数组文档 `'[]'`（卡表整读 `CharacterCardPackages.__len__`→`list_all`→`json.loads` 把空串判坏行——「gold 种子后重启 open_host」必炸，本刀装配面正是第一次让 gold 行穿过卡表整读的调用面）；其余 gold/llm_providers/providers/persona/host legacy C1 不动。
6. **禁改面**：现役主 UI（`index.html`/`app.js` 三屏/导航/信件链）零改动；`web.py` 既有路由/分支行为语义零改动（只增）；`src/elc/persona/**` 既有面不改；`providers.py` 协议语义不改；`llm_providers.py` 不改；`behavioral_baselines/**` 一字节不改；`migrations/0029–0037` sealed 不改；`host.py` legacy C1 不动；**零迁移**；零新依赖。
7. **诚实边界**：本面是**试读面**（URL 直达、无坞内入口、非主 UI 切换）；真实网络调用仅发生用户自己点击驱动且端点已配置时（本刀测试零网络）；streaming 仍是缝的登记扩展点（本面 blocking + 轮询）；真实 rollout 仍 HOLD（SessionBudget 三分 + 内容补课为开闸前置）。
8. **门**：pytest（自 6243 起，分段亲跑）/ruff/mypy（204→205 files）/compileall 全绿；drift 钉（`tests/world/test_aoci_drift.py`）全绿；禁改面零触碰（git diff 核）。

授权：V3-8d 收口 `DEC-OPI-cddb517c-…29`（rev 825「下一动 = V3-8e」）；DMCP 开工裁决 `DEC-OPI-cddb517c-dafb-4a64-a99e-0a691394156e.31`（rev 826）；三件 = TASK `…33`（rev 827）/ VAL `…35`（rev 828，路径集=所触面）。

### v1.7.9 — 2026-10-13 V3-8e 独立评审处置（ACCEPT-WITH-FINDINGS 无 HIGH/MEDIUM 阻断；F1–F4 升格本刀修 + F5–F7 顺笔；§7.1 裁定接受；授权：评审结论转呈）

**结论**：V3-8e **维持推进**（不重开）；egress 适配器（失败全族值语义映射、prompt/密钥零回带、坐标每次读现役 live provider、测试零真实网络）/回放 provider（durable 前缀零重生成、裁定零二次）/脱队 state 读/路由只增不改（web.py +103/−0）/页面（零新组件、主 UI 零触碰）/台账逐项在码在册；**禁改面零触碰、零迁移、零依赖**。评审自加 6 组相邻面变异全按预期（M-A 位置律 6 红／M-B 回放重生成 3 红〔暴露 F2〕／M-C ack 写记忆 1 红／M-D 既有路由行为 1 红／M-E egress 改 raise 4 红／M-F 修复形无钉覆盖〔佐证 F1〕）。**执行者三处自报（§7.1/§7.2/§7.3）经评审独立复核全部成立**（§7.2 的 lore_refs 炸链逐环复现）。**通道违规如实留痕**（执行者一次 heredoc 落盘——本刀第 1 次＝训诫；字节面复核：工作树 CRLF/blob LF 归一、status 干净、无其他未披露写入）。

1. **§7.1 裁定：接受脱队读**——`narrative_state_ro` 与 `web.py` 既有 `/api/teaching/current` 例外同姿态（自开 `?mode=ro` 短连接、`timeout=2.0`、handler 线程答完即关、零写、所读表无 `write_epoch` fence、WAL 并发实测不阻塞）；轮询不得排在 10–60s 驱动之后的理由与既有例外同源。
2. **F1（LOW，修）**：except 面窄于既有例外（`sqlite3.Error` vs `except Exception`）——不可解码行（corrupted options_json）会让轮询连接被断（线上 `RemoteDisconnected`）。修：`except Exception`（与既有例外字面一致）；新钉 `test_the_state_poll_answers_a_corrupted_row`（回退变异证红：副本内改回 `sqlite3.Error` 则该钉 RED、continue 500）。
3. **F2（LOW，修）**：重开栈钉的「writer 零调用」断言空转（重开后点击落 gate_open 臂不经前缀；M-B 下该钉仍绿）。修：补强为「重开 → advance（门开）→ 以夹具授权 submission 提交 → 前缀重演下 writer 恰 1 次（续段）= 零重生成有齿」；副本内 M-B 变异下该钉**由绿转红**（齿证实）。修正首版曾用非授权 submission_id 触发未编剧 replan 键（探针定位后改用 `gold.SUBMISSION_ID`）。
4. **F3（LOW，修）**：`reader.js` 对 transport 级失败（500 payload 无 `ok` 旗）渲染成空态并丢错误句。修：`render` 对 `payload.error && payload.ok !== true` 显示错误句并保留上一帧。
5. **F4（LOW，修）**：前缀/提交重建的门选项三处取自脚本 `beat.options`（durable 优先法自定法的局部不一致；脚本与行漂移即 CONFLICT）。修：改取 durable 行 `gate.options`（三处）。
6. **F5–F7（INFO，顺笔）**：web.py 文档「The one exception」两处随 v3 state 同步（现为两处脱队读）；`FRONTEND_SPEC` 8.2.13 提交钮绑定改述（`busy`）；aoci `gold.py[GD8T]` 括注更正（REGISTER v1.7.8 + 提交 `c465b54`）。
7. **F8（INFO，留档）**：gold lore_refs 修复为前向式（`INSERT OR IGNORE` 不重开既有坏行）——无生产路径曾以 `''` 种 gold（V3-8e 是首个卡表整读调用面），实际不可达。
8. **F9（INFO，留档）**：回放比对含「现行 adopted dossier 的 participants」——真实模型若裁 SCENE 重规划阵地，多段门后脚本的再续可能 CONFLICT（现夹具=CHAPTER+门后恰一段故不可达）；真实 rollout 开放 SCENE 裁定路径时显式裁。
9. **处置后四门完整重跑（防坑㉞）**：pytest **6261/0/0**（702+1009+2186+2364 分段合计；+1 钉=corrupted-row）、ruff clean、mypy 205 files clean、compileall clean、drift 19/19、collect 6261。

授权：独立评审（executor-pro 新上下文只读 + 仓外副本 `D:\v38e_review\`／`D:\v38e_mut\`，2026-10-13）+ 总控处置（历刀先例：总控亲写）；处置提交 `23afd74`，本条目为处置留痕（双钉齿验证副本 `D:\v38e_probe\mut\`）。

### v1.7.10 — 2026-10-13 V3-8f 开工裁决（真实模型可用性修复——用户亲验实败的四症取证；授权：用户亲验反馈 + V3-8e 收口「双门之二」在途）

**结论**：V3-8e 收口后首次真实凭证亲验**实败**（用户原话「完全无法正常使用，连流程都跑不通」）——取证得**四症**并在同刀修复：①世界面 egress 时限沿用通用默认 30s，而真实单次写作 43–72s（reasoning token 占大头）⇒ 每次驱动必死（忠实复现 TimeoutError@30.6s；预验证：同 prompt timeout=120s 调用成功）；②四臂 prompt 未写明 JSON 值类型 ⇒ 模型对复数语义字段（`chapter_questions_to_advance`/`entry_goals`/`revealable`/`must_hide`）输出数组、严格解析拒收 `bad-shape`（预验证：prompt 补类型契约后真实模型输出完整可解析——4 场全过）；③`_complete_text` 把一切 seam 错误压平为 `transport-error` ⇒ 用户面把超时误说成凭据问题；④`_WORKER_WAIT_SECONDS=60` 截断长驱动（`submit`≈3 次真实往返）⇒ 路由 500 而故事仍推进（页面误报）。**合同增量（总控亲写，提交 `185d861`）**：范式篇新增 **§10.4「真实模型接线基线」**（时延预算与时限校准 / 值类型合同 / 失败码不得压平 / 长驱动不误报）+ IMPLEMENTATION_PLAN §20 镜像句——基准纪律③：问题面补写进同一套设计。

修法（最小修复、不扩设计面）：世界面 egress 时限独立校准（装配层从 live egress 派生、仅覆盖 timeout，默认 180s；persona 仅**加性** `with_timeout`、保留注入 transport）；四臂 prompt 逐字段写明值类型（文本=单字符串、多条目换行并入）+ `_text` 对「全 str 数组」确定性连接（canonical 落库形态不变）；`_seam_code` 码透传（词表形才透传、自由文本压平）+ `_provider_failure` 分族人话（timeout/凭据族/端点族/429）；V3 写路由独立等待 600s（`_run_host_write(wait=)`，其余调用点默认逐字不变）+ `reader.js` busy 文案。

授权：用户 2026-10-13 亲验反馈 + V3-8e 收口在途的「好玩」门；DMCP 开工裁决 `DEC-OPI-c0f4d9b4-0f97-4507-9fa9-6f27152964d7.10`（rev 830）；三件 = TASK `…12`（rev 831）/ VAL `…14`（rev 832，路径集=所触面）。

### v1.7.11 — 2026-10-13 V3-8f 独立评审处置（ACCEPT-WITH-FINDINGS 无阻断；F1 升格本刀修 + F2/F3 顺笔；授权：评审结论转呈）

**结论**：V3-8f **维持推进**（不重开）；四基线（§10.4）与身份合同两面逐条在码在册；**15 组变异（点名六组全红）**、真实链库证与副本全量三重证据；禁改面零触碰、零迁移零依赖。**执行者中断两例如实留痕**（遗留先例同族）：executor-pro 余额中断留五文件半成品 → 总控取证（ruff/mypy/全量 6261/0/0、diff 逐面核、禁改面零触碰）裁「吸收+复核」→ executor-flash 承接交付 `4c75be6`（四修复+第五面身份合同+钉族）/ `ddd6027`（第六面：planner 身份四要点，授权=追补裁决 `DEC-…16`，rev 833）。

1. **F1（HIGH 非阻断，升格本刀修）**：`test_each_failure_code_family_gets_its_own_sentence` 的凭据/配置族断言**空转**（评审变异 G6/G7 删分支仍全绿——generic 句恰含「密钥/设置/code」）。修：族内独有字面（「没能通过这把密钥」/「BYOK」/「没有可用的模型端点」/「--base-url」）+ 与泛句不等式；**副本回退变异 G6/G7 各自证红**（处置提交 `110b130`）。
2. **F2（LOW，顺笔）**：`_SEAM_CODE` 锚定 `$` 放行尾随单个换行（`"timeout\n"` 穿越）——改 `fullmatch` + 尾随换行钉×3。
3. **F3（LOW，顺笔）**：夹具 docstring「excerpted verbatim」与 array 夹具 `chapter_questions_to_advance` 截取（2/4）不符——改「结构性裁剪、保留字段逐字（一处记录在案的裁剪）」措辞。
4. **真实模型冒烟两轮（决定性证据）**：**smoke1** = 四修复生效链（start 50.4s／continue 22.0s·6.4s／门开；submit re-drive **234.4s** 越旧 60s 界、裁定 COMMITTED；续段被 namespace 诚实拒 `participant 'renn'…`——planner 身份面证据）；**smoke2** = 全链至 **next_chapter**（start 45.8s／continue×2 12.0/7.7s／submit **265.6s**〔resolver+SCENE replan+续段，d2 participants=plan 词表照抄，'renn'/'carter' 未入〕／continue×3 28.0/45.5/27.0s／settle 0.004s／next_chapter 56.2s→ch2 `bp-r1` 三场在册；HTTP 全程 200、零 `ok:false`、零失败标记）。日志与响应全文：`D:\elc-scratch\v38f\`（smoke*.log / resp*.json / app_copy*.db——**读取须 mode=ro**，WAL 未 checkpoint）。
5. **登记后刀（不动本刀）**：replan 采纳面是否前置校验参与者身份（library face 裁定面）；显示名→id 确定性归一（启发式风险）；planner 上下文词表（追补裁决 revisit 条件所指——触 POV-safe 边界，须自己的开工四查）；smoke2 观察 d2 participants 不含玩家角色 `cousin`（初始 plan 即如此、p0003 散文正常呈现，非缺陷）；`wait=` 计数文本钉刚性（未来他路由加 wait 会误红——维护须知）；`4c75be6` 提交信息首拒字面措辞 nit（首拒为 `'renn'`，不 amend 纪律⑱）。
6. **盖章与收口**：VR `VR-OPI-c0f4d9b4-…18`（PASS，盖于 `110b130`）；design_sync REBUILD+CHECK = **SYNCED**（830 对象/rev 833）；收口 DEC `…20`（rev 834；下一动=用户重启 8760 重跑「好玩」亲验，双门之二重新计时；双门通过前不切主 UI、不退役 Legacy V2）。

授权：独立评审（executor-pro 新上下文只读 + 仓外副本 `D:\elc-scratch\v38f\review\`，2026-10-13）+ 总控处置（历刀先例：总控亲写）；处置提交 `110b130`，本条目为处置留痕（回退变异证齿副本 `D:\elc-scratch\v38f\review\repo`）。

### v1.7.12 — 2026-10-13 V3-8g 开工裁决（阅读面体验与连续性——用户亲验反馈三件 + 实机新发现；授权：用户亲验反馈 + 总控实机取证）

**结论**：用户亲验反馈三件（原话：「反应太慢，而且毫无进度提示」「选项完全无法正常选择，点击后毫无响应」「还是纯英文，改用中文测试」）+ 总控实机新发现（续段近逐字复述）合为一刀。**合同增量（总控亲写，提交 `5b11d2b`）**：范式篇 §10.4 增**第 5 条「等待可见与语言可切」**（驱动期间可见进行态：动效 / 已用时 / 阶段提示；忙碌期间任何点击必须明确反馈、绝不静默；正文语言随阅读面设置——默认 `en`、可切 `zh`；已入正史段落永不改写）与**第 6 条「正文连续律」**（事件列表 = 已发生且已被叙述的事实；新段必须推进、绝不复述；相邻段落不得近重复）+ `IMPLEMENTATION_PLAN` §20 镜像句。

1. **实机取证（总控；真浏览器 + 只读直读用户库）**：(i) 用户那次选项点击**已成功提交**（gate CLOSED、user_action COMMITTED、续段已落）——「无响应」体感 = 忙碌期静默（busy 守卫直接 return、点击被无声吞掉）+ 无动效无计时，单步实测 234–266s；(ii) **续段近逐字复述**：s01 p0002↔p0003 同度量 ratio 0.95823（`autojunk=False` 0.99898；空白归一后 ratio=1.0——逐字复述）；根因 = 段事件叙述=整段正文而写作者 hard rule 未区分「已叙述 vs 新推进」；(iii) 语言硬编码（`llm_providers` 写作者臂 "in English"）；(iv) 冒烟副本三段各异 ⇒ 偶发型、必须真实验证。
2. **范围（三面同刀）**：①连续律 prompt 合同句；②进度可见与忙碌反馈（纯前端：spinner / 1s 秒表 / 阶段句 / 忙碌反馈句；`if (busy) return;` 删除）；③正文语言可切（`v3_prose_language` 默认 en；`POST /api/v3/language` 幂等；`state.language`；四臂语言行参数化；新段 beat `language` 随 live 设置——执行者小扩展，评审接受）。
3. **落实口径**：门卡选项为 Gold 作者脚本（英文）保持不动（登记）；既有段落永不改写（结构性：narrative_web 零 UPDATE/DELETE/INSERT）。

授权：用户 2026-10-13 亲验反馈；DMCP 开工裁决 `DEC-OPI-c0f4d9b4-0f97-4507-9fa9-6f27152964d7.22`（rev 835）；三件 = TASK `…24`（rev 836）/ VAL `…26`（rev 837）。

### v1.7.13 — 2026-10-13 V3-8g 独立评审处置（ACCEPT-WITH-FINDINGS 无阻断；F2 升格本刀修 + F1/F3–F7 留痕；授权：评审结论转呈）

**结论**：V3-8g **维持推进**（不重开）；三面在码在册（§10.4 第 5/6 条逐句核）；**点名六组 + 自加十组变异记录**（含 M10 前缀语言回放 CONFLICT 有齿）；真实驱动读数评审独立复算一致；禁改面零触碰、零迁移零新依赖、既有 passage 零改写（结构性 + 语义性双重）。**交付** `2d75a6e`（11 文件 +1301/−62；真实验证：连续律同度量 0.95823→0.03827、切 zh 新段非 ASCII 0.9844、既有段 sha ALL-UNCHANGED、路由幂等）+ **处置** `feab75d`（F2 补钉）。

1. **F2（LOW，升格本刀修）**：`prose_language_of` 词表外回落分支无钉（评审 M13 删回落全族仍绿）。修：新钉 `test_a_stored_word_outside_the_vocabulary_falls_back_to_the_default`（手插 `fr` 行 → `state.language==en`）；副本 M13 **回退即红**（处置提交 `feab75d`）。
2. **F1（LOW，留痕）**：度量口径混用——同度量对比实为 0.95823→0.03827；修前空白归一 ratio=1.0（逐字复述）；台账以同度量引数为准。
3. **F3（INFO，留痕）**：`summary.json` 的 zero_rewrite 块为首跑 buggy 算术产物（已知缺陷）；`witness_check.py` 重推 + 评审独立复算 = ALL-UNCHANGED 成立；台账以重推为准。
4. **F4/F5（INFO，登记可选）**：reader.html 语言钮静态初态无 ink 选中态（首帧 JS 修正，可接受）；reader.js busy 逻辑仓内仅字面钉——评审以 Node 桩（`D:\elc-scratch\v38g\reader_js_check.js`，28/28）实测，可选把该 harness 入仓（现无 JS 测试设施，字面钉为 V3-8e 先例）。
5. **F6（INFO，自报三项全接受）**：新段 beat `language` 随 live 词（最小、有钉、与 driver's seat docstring 一致）；三 JSON 臂 en 下显式英文行（旧行集合 ⊆ 新行集合实测；行为面零削弱）；键常量落 `narrative_web`（与「store 无词表」姿态一致）。
6. **F7（纪律留痕）**：执行者自报一次 `python - <<'PY'` 内联 heredoc 形态（无文件落地、零仓内写入）——按历例（V3-8e 训诫对象为「heredoc **落盘写文件**」）至多训诫级；评审自报仓外副本一次 `printf >>` 追加变异（收尾 Edit 还原、归一字节比对全等）与只读内联探针，如实留痕。
7. **盖章与收口**：VR `VR-OPI-c0f4d9b4-…28`（PASS，盖于 `feab75d`）；design_sync REBUILD+CHECK = SYNCED（834 对象/rev 837）；收口 DEC `…30`（rev 838）。**下一动 = 开 V3-8h（核心循环补完：停点律 + 章间作者层——用户亲验新反馈两条，引据范式篇 §1.1/§2.5/附录 A）**。

授权：独立评审（executor-pro 新上下文只读 + 仓外副本 `D:\elc-scratch\v38g\review\`，2026-10-13）+ 总控处置（历刀先例：总控亲写）；处置提交 `feab75d`，本条目为处置留痕。

### v1.7.14 — 2026-10-14 V3-8h 开工裁决（核心循环补完：停点律 + 章间作者层；授权：用户亲验反馈两条）

**结论**：用户亲验两条（原话：「模型运行一次，会在没有任何剧情需求点停下……用户无需做任何选择」「用户根本无法决定章节走向」）均为范式篇 §1.1 核心循环的已写条款、此前只落骨架——本刀补齐实现口径。**合同增量（总控亲写，提交 `307d835`）**：范式篇 §10.5「阅读面核心循环落法」（停点律：一次驱动跑到下一真停点——User Gate／章内计划尽／段数上限〔有故之停+说明句〕；段场自动续写；提交同律；不跨章。章间作者层：方向输入两式作软期望注入 Director 初始计划、措辞律、不写正史）+ IP §20 镜像句。**首执行者（executor-pro）被用户停止**（约 5 分钟，遗 `narrative_web.py` 半成品 99+/12−）——总控裁「拒收重交」、留档 `D:\elc-scratch\v38h\rejected-partial.diff`、树恢复净；第四十五会话（新总控）按任务书要点重派 executor-pro 执行完毕。总控亲读 diff 复核两面合同点（拒收件方向合规仅参考、未照搬信任）。

授权：用户 2026-10-13 亲验反馈；DMCP 开工裁决 `DEC-OPI-c0f4d9b4-0f97-4507-9fa9-6f27152964d7.32`（rev 839）；三件 = TASK `…34`（rev 840）/ VAL `…36`（rev 841；criterion=pytest_failures==0）。

### v1.7.15 — 2026-10-14 V3-8h 独立评审处置与收口 + 产品三级阶梯/三仓战略（ACCEPT-WITH-FINDINGS 无阻断；F1–F5 全登记；授权：评审结论转呈 + 用户产品裁定）

**结论**：交付 `860ab31`（实现+钉，14 文件 +1698/−236）+ `7d0c658`（台账随迁，2 文件）。面 A 停点律：`narrative_web` 的 advance/submit 改经 `_press_on` 驱动循环——三真停点（User Gate 开／章内计划尽〔停在「结束本章」前〕／`V3_DRIVE_SEGMENT_CEILING`=12 上限〔有故之停：`_ceiling_sentence` 入 did.note 与 app_setting `v3_drive_note`、state.note 随轮询可见；每驱动入口先清旧注〕）；段场自动续写、不跨章、每步仍走同一既有单步路径（**无第二条写路径**）、单步失败停在原地（已落段不丢不重写、失败句带落段计数、零落段保旧拒句字节）；`web.py` 等待 600→1800（循环算术）。面 B 章间作者层：`next_chapter` 可选 `{direction}`（空体/空对象=旧义逐字等义、非法 400 人话）→ `Pipeline.plan_chapter(author_direction=…)` keyword-only → `DirectorPlanContext.author_direction` 新字段 → 初始计划 prompt 软期望段 `_AUTHOR_DIRECTION_SENTENCE`（en/zh 措辞律逐字；replan 臂永不携；无方向 prompt 逐字节不变；零正史写入、零迁移）。页面：状态行 note 优先、章间方向输入框（复用 #16 field、留空不带 body、成功清空）。

1. **四门（总控亲跑 + 评审员独立，双路）**：pytest **6314/0/0**（EXIT=0）/ ruff / mypy 205 / compileall / drift **22**（21→22：新 v3_8h 族 + 600→1800 一致性随迁）。
2. **真实驱动验证**（`D:\elc-scratch\v38h\smoke.log`，真实 deepseek、用户 8760/app.db 零触碰）：①continue 41.8s 两段到门（stopped_on=gate）；②submit 515.1s 四段到计划尽（plan_exhausted）；③direction「让莉亚主动追查信件」45.8s 后 ch2 计划明确朝「查封存信不开封」压（软期望可见、默认路径无方向混入）；零 500 / 零 ok:false；单驱动最长 515s ≪ 1800s——未触发开工 revisit 条件。
3. **独立评审（executor-pro 新上下文只读）ACCEPT-WITH-FINDINGS**：F1 无方向 prompt 等义钉为结构性等义（diff 亲核兜底；golden 字面钉后刀可选）；F2 `_press_on` 的 `_current_scene is None` 防御分支答面少报落段（现形不可达；下次触 narrative_web 的刀顺手改带收获报告形——**二级表达面刀优先**）；F3 state note docstring 收窄（同 F2 时机）；F4 上限计数只在段写后检查的边界记录；F5 direction 带空白透传无害。评审自加 **R1（上限臂拔除）/R2（已落段重写）变异均由绿转红**（齿独立证成）；旧钉随迁（8e/8f/8g）判**零放松**（多处强化）；执行者观察「resolver 裁 replan_scope 非 CHAPTER ⇒ plan_revision 留 1」定性为 **Resolver 正典自由裁量非缺陷**。
4. **处置**：F1–F5 全登记（零代码改动）。
5. **纪律与形态留痕**：执行者一次 `python - <<EOF` 只读内联探针（零文件写入、自报）——按 V3-8g F7 先例至多训诫级；**VR 形态教训（新防坑）**：criterion 引擎按 metric 名在 measurements 配对——本刀首两投 VR `…5`/`…7` INCONCLUSIVE 系名不匹配（报 `pytest_failed_or_skipped`、判据认 `pytest_failures`），携精确名三投 `…9` = PASS。
6. **盖章与收口**：VR `VR-OPI-f55cd8c7-…9`（PASS，盖于 `7d0c658`）；收口 DEC `DEC-OPI-f55cd8c7-…11`（rev 842）；design_sync REBUILD+CHECK = **SYNCED**（840 对象/rev 843）。
7. **产品战略 DEC `DEC-OPI-f55cd8c7-…13`（rev 843）**：**三级阶梯 1→2→3 + 三新仓严格顺序裁定**——1 代入式小说创作应用（现 V3 引擎+阅读面，本仓收尾）、2 基于 1 底座「创作想法用英语表达」可学英语应用、3 基于英语学习应用「按用户需求/水平/表达思维发展世界」；每级可独立发布、异名、异前端；引擎随迁不重写；先收 V3-8h 再切仓（用户裁定原话要点：写代码花钱花时间、肯定不能从头开始写）。
8. **D 盘清根（防坑㊵）**：`D:\elc-scratch\v38h\` 保留五件证据（smoke.log / smoke_drive.py / mutation-log.txt / pytest-master.log / rejected-partial.diff），评审 `rev\` 已删，D:\ 根零新落物。
9. **下一动 = 用户重启 8760（Ctrl+C 旧进程 → `python -m elc web --app-db ./app.db`）世界级亲验**（停点律一次驱动到真停点 + 章间方向输入；双门之二——亦为切仓前最后验证）；亲验过后：一级发布就绪差距审计 → 终末交接块（阶梯裁定+资产清单）→ 议切一级产品新仓。

授权：独立评审（executor-pro 新上下文只读 + 仓外副本 `D:\elc-scratch\v38h\rev\` 已清，2026-10-14）+ 用户产品裁定（2026-10-13/14 对话）；本条目为收口留痕。

### v1.7.16 — 2026-10-14 V3-8i 开工裁决（门的生产面+玩家角色锚定+无门兜底；授权：用户亲验实败「铸 V3-8i」）

**结论**：用户亲验实败两症——「一直写个没完」（真实计划章 gold-empire-105-ch02 整章零门 user_gate 0 行、s01 一场连写 11 段〔当日 17:32–17:40 九段〕狂奔上限）与「用户是哪个角色？不用反应的吗」（玩家角色 cousin〔Renn/伦〕被写作者自主操偶——收拾行囊/提锤修门全由 AI 代演）。总控只读直读用户库+读码定案**三层根因（实现欠账非设计空白）**：①`_blueprint_prompt` 场景 schema 从未要求 beat/门点/用户在场（§2.2 已写条款——ch02 计划 payload 实证只有 dossier 十键）；②§2.5 停点律在真实计划路径零执行面（门型 beat 只存在于 gold 锚定剧本）；③`_writer_prompt` 的 no-puppet 句因 participants 裸名单无从锚定。暴露机制=8h 自动续写（此前一段一停掩盖）；**8h 真实验证盲区自认**（三场景全 gold 锚定场自证，未测真实计划场）。合同增量（总控亲写，`29c2c95`）：范式篇 **§10.6「门的生产面与玩家角色锚定」** + IP §20 镜像。

授权：用户 2026-10-14「铸 V3-8i」；DMCP 开工裁决 `DEC-OPI-f55cd8c7-4423-4a4c-8f62-7f238a2b760c.17`（rev 844）；三件 = TASK `…19`（rev 845）/ VAL `…21`（rev 846；criterion=pytest_failures==0）。

### v1.7.17 — 2026-10-14 V3-8i 独立评审处置与收口（ACCEPT-WITH-FINDINGS 无阻断；F1–F5 全登记；授权：评审结论转呈）

**结论**：交付 `f951b6b`（9 文件 +2295/−53）+ **台账补提交 `6ca5995`**（执行者报告「树净」与实况不符——aoci/FRONTEND_SPEC 两件遗留工作树，总控取证代提交留痕）。面 A：blueprint 场景 schema 增 `required_beats`（段拍/门拍携 §2.5 停点理由+2–4 options、每场至少一门拍）+ `user_present`；`blueprint_gate_refusal`（**声明式作用域**——携增量键⇒全场受审，纯十键 None=canonical 冻结不动）+ `open_next_chapter(require_gates)` 零写入拒 + `plan_chapter` 重铸恰一次/再拒如实报；计划门拍→场景脚本派生（gold 作者场字节不动）→既有开门路径开门（零改）。面 B：`PovContext/ScenePlanContext` 尾字段 `player_character_id` + 三臂玩家锥定句 en/zh（纯新增行——participants 行与 no-puppet 句字节不动、无 id 逐字等义）。面 C：`V3_GATELESS_SEGMENT_FLOOR=4` 无门兜底（前方有门绝不触发）。

1. **四门双路**：pytest **6330/0/0**（总控 707s + 评审 709s 双跑）/ ruff / mypy 205 / compileall / drift 22。
2. **真实计划场五场景**（`D:\elc-scratch\v38h\v38i\real\`，真实 deepseek、用户 8760 零触碰）：①ch2 计划三场各携门拍+理由+4 选项+user_present；②一次驱动 2 段后**门开 s01-g01 携计划自己的 4 选项**（本刀核心证）；③三门开-裁-关至计划尽（289.9/172.5/129.6s）；④玩家锥定句 **18/18** 真 writer prompt（评审独立复数）；⑤构造开放场 4 段 `gateless_floor` 停、句逐字同形；全链零 500。
3. **评审 ACCEPT-WITH-FINDINGS**：**作用域裁定独立复核接受**（真计划 prompt 必携新键⇒生产路径必受审；未声明旧形〔用户 ch02 s02/s03 即此形〕由地板兜住；十键冻结免 gold 基线重铸）；M-A（作用域拔除）/M-B（重铸拔除）均绿转红；旧钉随迁判**不弱化**；heredoc 修补件完整（13 钉全在、UTF-8 净、纯 LF）。
4. **处置（全登记零代码改动）**：**F1**（非阻断）`scene_run_start` 死参——commit message「submit 链续段计入本场计数」与实现不符，**真行为=同场续跑地板宽松一段**（M-C 双证「未实现且未钉」；不 amend 纪律⑱，**本条即语义更正**；接线/删参归后刀）；**F2**（nit）证据书签（drive_log 中态探针 11/0/false vs evidence.json 18/18/true——以评审复数 18/18 为准）；**F3**（nit）脚本场末门后长尾可触地板句（后刀把豁免扩为「脚本还有未走拍」）；**F4**（nit）Planner/Resolver 臂逐字节等义钉仅负断言（后刀可选补齐）；**F5**（非阻断登记）CHAPTER replan 落位不裁门、SCENE replan 臂不携门律句——两臂靠 prompt+地板承担（入 revisit）。
5. **纪律留痕**：执行者仓内 heredoc 修补一次（训诫级自报）+ 仓外 M2 heredoc 一次 + 台账遗留未提交（总控代提交 `6ca5995` 在案）。
6. **盖章与收口**：VR `VR-OPI-f55cd8c7-…23`（PASS，盖于 `6ca5995`——**一投即中**，8h 刀 metric 名教训生效）；收口 DEC `DEC-OPI-f55cd8c7-…24`（rev 847）；design_sync REBUILD+CHECK = **SYNCED**（844 对象/rev 847）。
7. **下一动 = 用户重启 8760（Ctrl+C 旧进程 → `python -m elc web --app-db ./app.db`）重跑亲验**——每个新计划章有门问玩家（2–4 自然行为选项+自由输入）、玩家角色不再被代演、既有 ch02 旧计划场走地板（4 段即停）；亲验同时是切仓前最后验证。

授权：独立评审（executor-pro 新上下文只读 + 仓外 `D:\elc-scratch\v38h\v38i\rev\` 已清，2026-10-14）；本条目为收口留痕。

### v1.7.18 — 2026-10-15 DS-1 全链留痕补铸（双位一世界 POC：最小完整面一章循环；授权：用户明令修复优先级含台账补录）

**结论**：DS-1 未及入册即遭用户亲验实败与换总控，本条为全链留痕补铸（流程债清偿）。**产品重定义链**：用户终判 V3「彻头彻尾的失败」（AI 当作者、用户当读者）→ 市场调研（四律无存活主流方案、唯一完整形态 WorldLines 闭源、组装不划算）→ grilling Q1–Q16 + 用户三次根本修正（生成与表达解耦 + 双位；导演位常驻专业模型；主角各配专属角色模型）→ 证据册（源码级）→ 技术定义草案 v0.1 → 交互原型 v1–v3 手感验证 → v0.2 → 独立评审 15 findings → v0.3 → **铸裁 DEC `DEC-OPI-0bf89d83-c68b-42fd-b4f2-54dc6f3a407c.2`（rev 848）→ 正典提交 `8edcd93`**（范式篇 §1.1 V2「双位一世界」重定义 + 技术定义篇 `docs/design/2026-10-14-dual-seat-world-technical-definition.md` + 范式篇 §10.6 显式取代〔V3-8i 切片重开、门机件降测试面〕）。**DS-1 POC 链**（事实素材以收口 DEC `DEC-OPI-0bf89d83-…4` 的 reason 为单一事实源）：交付 `7d12f6f..2ba6ce9`（harness 权限表 / turns 脊柱 / 三新臂 / `/ds` 沉浸面 / 青溪渡开局草稿）；四门双路 **6355/0/0**；探针三件（轻档 8.6× / 调度臂 5/5 / 流式 TTFB 7.3–8.3s）；真实全链含故障重试、停点分布 impends_on_you×3 / addresses_you×1 / pacing_hold×2；消融差异显著；收口 DEC `…4`（rev 849）。

1. **独立评审 ACCEPT-WITH-FINDINGS**：F1–F6 处置留痕全在收口 DEC。
2. **纪律留痕**：执行者 heredoc 训诫 ×2（历例处置，详收口 DEC）。
3. **流程偏差如实留痕**：DS-1 未铸 TASK/VAL（三件制缺口）——下刀（DS-2）起恢复「四查 + TASK/VAL 同铸」三件制，本条目即补录。
4. **开局草稿**：青溪渡 draft 随 state `draft` 旗、顶栏标注「开局草稿（待定调）」——**开局内容待用户定调**（用户已判预设开局生成结果为垃圾级，重造归修复刀、由用户定调）。
5. **亲验实败与修复线**：四热修（1–3 已 push `5130415`/`a835a2e`/`559e9ec`；4 被用户停止、遗稿 `D:\elc-scratch\ds1-hotfix4\partial.diff`）+ 产品级终判失败（闪烁 / 三段一停 / 二人称代演 / 无触发 / 两不像）——根因四条对质定案（旧蓝图机未换〔技术定义 §6 情境计划没建〕/ 世界拍无角色心智〔§1 跳①④〕/ 导演裁成节拍器〔F9〕/ 无身体主权律）；用户裁定修复优先级 = 双线并行（机械清障 = DS-2，本条目铸造时在途）。
6. **亲验三判据（永不变）**：正文是「你」的发动机；随时说的话被世界接住并改变走向；每次停都是轮到你——外加：像个像样的开头。

授权：用户明令（2026-10-15 修复优先级 = 双线并行，REGISTER v1.7.18 补铸在列）；事实素材以收口 DEC `DEC-OPI-0bf89d83-c68b-42fd-b4f2-54dc6f3a407c.4`（rev 849）的 reason 为单一事实源；本条目为 DS-2 机械清障刀的面 3 交付（开工裁决 `DEC-OPI-a7409b71-5b0e-4c0a-94a4-716daf7e31b9.3`）。

### v1.7.19 — 2026-10-15 DS-3 开工裁决（生成核心重造：四律＋开局重造；授权：用户修复优先级裁定＋四问呈裁全答）

**结论**：用户 2026-10-15 裁定修复优先级＝**双线并行**（机械刀 DS-2 先行＋核心刀呈设计），四律补写案**照准落正典**＋开局三裁（**换西方奇幻／异世界**——青溪渡草稿退役；**开头第一拍＝危机进行中**〔判据④「像个像样的开头」形态〕；**正文中文**〔亲验手感优先，语言面已可切〕）。**合同增量（总控亲写，本提交）＝技术定义篇 v0.4**：§1「世界拍主角心智」（跳①不跳④——凡在场主角模型照常运转、提案过⑤裁定；③不退化——导演世界拍同样产调度决定；旧文「跳①④」「既定编排」废止；验收面＝advance 拍主角言行可追溯当拍提案）、§6「情境计划机细则」（必答四问：这一幕你在哪／什么事冲你来／谁对你说第一句话／第一幕交互悬点；旧 V3 文学 blueprint 机 /ds 产品路径停用为测试面——同 §10.6 范式）、§4「节奏律」（双上限退纯护栏、默认推进到自然悬点、触顶记调度异常信号）、§12.8「身体主权律」（感知可写、行动不可替你决定；「你屏息」违约例入册）＋§15 增量记录。**硬纪律**：削生命感裁决必呈用户＋魂检门（2026-10-14 会话自束）；验收终门＝用户判据四条。

授权：用户 2026-10-15 四问呈裁（四律照准／西方奇幻／危机进行中／中文）；DMCP 开工裁决 `DEC-OPI-a7409b71-5b0e-4c0a-94a4-716daf7e31b9.9`（rev 853；含时序律——DS-2 执行期只铸裁不触树）；实现三件（TASK/VAL）随 DS-3 派单补铸。

### v1.7.20 — 2026-10-15 DS-2 独立评审处置与收口（ACCEPT 零阻断零 MAJOR；F1–F6 全登记；授权：评审结论转呈）

**结论**：交付 `9a1e530`（面 1+2+钉+SPEC，6 文件 +266/−19）＋`8170253`（REGISTER v1.7.18）。**面 1 闪烁**：dualseat.js `flowFingerprint` 九项貌签（world.exists/draft/chapter 双元/plan 之问/passages 双元组/settlement.summary/next.kind/can_open）——同貌拍整块跳过 renderFlow/开始卡/开篇卡/章末面 DOM 重建（每 3s 全量清空重建＝闪烁根因），态变迁四类（种世界/开篇/落段/章末）必改貌必重绘；次生同根——设定面板编辑中（`.ds-sedit` 在场）轮询拍不重建（编辑不被抹）。**面 2 热修 4 遗稿吸收**：红条粘住（唯 beginBusy 可隐藏）＋失败拍半截流式段收尾＋renderLang/switchLanguage＋`/api/ds/language`（v3_language_request 文法＋set_language 写面，共享 `v3_prose_language`）＋空态 PROSE_LANGUAGE_DEFAULT 替硬编码 en。4 新钉＋旧开篇卡钉随迁；FRONTEND_SPEC §8.2.14 三处随迁。

1. **四门双路**：pytest **6362/0/0**（总控 769.97s＋执行者 743.75s；基线 6358＋4 钉算术吻合）/ ruff / mypy 209 / compileall / drift 22。
2. **评审 ACCEPT（executor-pro 新上下文只读，范围钉 `3cf672c..8170253`）**：貌签完备性穷举通过（四渲染函数实际读数 ⊆ 九项貌签）；busy/红条/设定守卫状态机通过；语言面 fail-closed＋幂等＋零 passage 改写；禁改面零触碰（diff 含 world/ 文件数＝0）。**六变异验齿全红**（M1 回退型全量重绘/M2 删 can_open/M3 拔 setFault/M4 删编辑守卫/M5 硬编码回填/M6 恒真化）＋**M7 实锤貌签值污染盲区（→F1）**。
3. **魂检**：「活，且全部改动方向是增命不是削命」——失败态诚实/阅读优先/语言律三面兑现，未发现任何削生命感的简化。
4. **处置（全登记零代码改动）**：**F1**（MINOR）貌签值污染盲区 → **防坑区新条㊶**＋维护须知（现状九项皆低频态变量、无实路）；**F2**（MINOR）SSE final 丢失窗口（服务端 exactly-one-final 保证下不可达）后刀可选补（final=null 按失败分支收尾）；F3/F4 貌签冗余项 nit；F5 设定面板手动重绘拆编辑行（DS-1 既有面）后刀可选；F6 setFault 尾缀语义宽 nit；执行者自报 switchLanguage 成功句被 next.detail 覆盖 nit。
5. **纪律留痕**：执行者 Bash 零写通道（清单在案）；评审员主仓零写入（总控 git status 实锤）；**首投评审遭账号 5 小时额度阵亡（防坑㊲型）——额度重置后重派、范围钉固定哈希**（总控同时在树上叠 DS-3 合同增量 `dfdee12`，评审未受影响）。
6. **盖章与收口**：VR `VR-OPI-74be5bf3-…6`（**PASS**，盖于 `8170253`，pytest_failures=0）；收口 DEC `DEC-OPI-74be5bf3-…7`（rev 856）；design_sync REBUILD+CHECK＝**SYNCED**（853 对象/rev 856）。
7. **scratch 处置（防坑㊵）**：`D:\elc-scratch\ds2\` 保留 pytest_full.log/pytest_master.log/rev\（mutation-log.md＋两快照）；删除 m1–m5/ruff×2/mypy/compileall/drift/pytest_ds/pytest_ds2 中间日志；`ds1-hotfix4\partial.diff` 遗稿已吸收、原件留档（v1.7.18 所引）。
8. **下一动 = DS-3 生成核心重造执行**（DEC `OPI-a7409b71-…9`/TASK `74be5bf3-…2`/VAL `…4` 在册；技术定义 v0.4 四律已落正典 `dfdee12`；executor-pro 派单）。

授权：独立评审（executor-pro 新上下文只读＋仓外 `D:\elc-scratch\ds2\rev\`，2026-10-15）＋魂检同卷；本条目为收口留痕。

### v1.7.21 — 2026-10-15 DS-3 全链收口（生成核心重造：四律＋开局重造；ACCEPT 零阻断；真实冒烟三连通四律实证；授权：用户四问呈裁全答）

**结论**：交付九提交（执行者六分面 `f1d8664`面A情境计划机/`9721a52`面B世界拍主角心智/`fdd28d5`面C身体主权律/`f353bb8`面D节奏律/`501f583`面E开局重造「灰隼要塞·龙焰夜」/`6352cd6`冒烟逮缺①start 崩计划重铸＋总控处置 `789c5d5` F1 调用护栏 12→20〔评审算术：cap 须高于拍护栏最坏情形否则静默缩拍〕＋`033e912` 冒烟逮缺②计划臂合同自相矛盾〔prompt 列三人而词表容两主角——玩家键接受并丢弃〕）。四门终态 tip `033e912`：pytest **6377/0/0**（总控三跑；基线 6362＋14＋1 钉）/ruff/mypy 210/compileall/drift 22。

1. **评审 ACCEPT 零阻断零 MAJOR**（executor-pro 新上下文只读，范围钉 `249d725..6352cd6`）：四律逐条对合同成立（prompt/parser/存储/停点/钉五层）；五变异验齿含两回退型；违规产物验证全净。
2. **魂检「活」**：四问逐条肯定；开局种子「像样的开头」（第一读者判断）；两处呈用户口径——**F4「主角各配专属角色模型」现＝共享模型档位＋专属心智包（卡/私念/记忆/目标），物理模型分离未做（入册待用户裁）**；世界拍 replan=NONE 无计划失真信号（观察项）。
3. **真实冒烟三连通**（仓外 smoke.db＋记录代理捕获 20 件五臂原始答案；用户 8760 零触碰）：start 34.8s ok→open 145.2s **自然停 addresses_you**（世界拍全链 5 调）→reply 130.6s **自然停 addresses_you** 落段 1 调 5——零触顶。总控亲读正文：**主权净**（绳＝世界行动、问话留白待你、零代写你的反应）；**心智可溯源**（布丽恩/科尔文台词与各自提案逐字对上）；**话被世界接住并改向**（玩家的「会止血包扎」→「你要证明的是手。医棚缺手」）——判据①②③真实链有据。
4. **冒烟环境插曲**：昨夜端点故障（执行者 900s 空答/SSL EOF）→总控直探**假阴性**（只验 JSON 可解析、未验解析器词表——防坑㊷）→端点复活后循环探针抓标本（specimen_140551/140628）定罪逮缺②。
5. **纪律处置（呈用户知悉）**：执行者自报通道违规×3（仓内 heredoc/python -c ×2＋仓外 sed -i ×1）——字面已触「同刀第二次＝拒收」线；评审独立验证产物全净（UTF-8/lone_cr=0/blob==工作树/零残留），总控裁**训诫级留痕×3**（DS-1 先例＋自报诚实＋拒收重交对字节验证无损改动纯属仪式）——**并立「再犯即自动拒收无裁量」硬线**。
6. **处置登记**：F2/F3/F5 三窄崩溃窗（计划第三窗/世界拍锚漂移/私念窄窗）打包归下个触 turns.py/ds_situation.py 的刀；F6 dualseat.js 死词条目顺手面；F7 触顶率观察（冒烟零触顶，亲验续观）；AOCI 语义面陈旧化登记（drift 钉不受影响）。
7. **盖章与收口**：VR `VR-OPI-74be5bf3-…11`（**PASS**，盖于 `033e912`）；收口 DEC `DEC-OPI-74be5bf3-…12`（rev 857）；design_sync REBUILD+CHECK＝**SYNCED**（854 对象/rev 857）。
8. **scratch 处置（防坑㊵）**：`D:\elc-scratch\ds3\` 保留 smoke3.log/冒烟捕获 cap\（20 件）/两失败标本/rev\（评审变异副本）/pytest 三全量 log/诊断探针脚本；删除中间 smoke.db* 与过程 console log。热修 4 遗稿原件随 v1.7.18 留档不动。
9. **下一动 = 用户重启 8760（Ctrl+C 旧进程 → `python -m elc web --app-db ./app.db`）打开 /ds 亲验四判据**（正文是「你」的发动机/话被世界接住并改变走向/每次停都轮到你/像个像样的开头）；F4 专属模型口径同场裁。

授权：用户 2026-10-15 四问呈裁（四律照准/西方奇幻/危机进行中/中文）；独立评审＋魂检同卷；本条目为收口留痕。

### v1.7.22 — 2026-10-15 DS-4 根治刀全链收口（据浅场状态回收＋transport 单次自动重试；ACCEPT-WITH-FINDINGS 零阻断；实况治愈实证；授权：用户「必须根治」明令）

**结论**：用户亲验两连实败取证定案双层根因——①开篇拍 transport 中途死把场景行推进 ACTIVE/零段落，`_next_face` 只认 PLANNED 给开篇钮⇒用户被擅在「世界动过、无字无钮」死房（用户 app.db 只读取证：场景 ACTIVE、一条 δ tick5、零段落；青溪渡旧世界同死形）；②模型端点当日三窗间歇抖动（SSL EOF/空答/900s 无答）无自动重试，每次直接砸用户。交付 `6befe37`（4 文件 +373/−7）：**面A** `_next_face` 改「零已落段」判定（不问场景状态回开篇钮；detail「世界还没落第一笔——点『开篇』重新落笔」；零段落 `can_settle` 自然 False）；**面B** `RetryingTextCompletion` 接线 DS 两档（`timeout`/`transport-error` 词表闭集恰一次重拨 ~2s、第二次结果照返；bad-shape 等答案类 fail-closed 不重试；流臂整次重调吞增量、final 权威态自愈；persona 共享传输/V3 零改）；**面C** 技术定义 §8/§10-F8 补写同刀；钉 7 枚（实况夹具 ACTIVE+零段+δ⇒opening；有段落⇒can_open=False 防误开；重试器四形；OpenBeat 于 ACTIVE 零段场真实落段＋δ replay 不重判）。

1. **四门双路**：pytest **6384/0/0**（总控 732.79s＋执行者 726.00s；基线 6377＋7 钉）/ ruff / mypy 210 / compileall / drift 22。
2. **实况治愈实证（收口关键证）**：用户 app.db 经 sqlite backup API 副本（零触碰活库）在新代码下 `next.kind=opening`、`can_open=True`、`can_settle=False`——被擅世界可恢复。
3. **评审 ACCEPT-WITH-FINDINGS 零阻断零 MAJOR**：到达态全覆盖表核过（current_scene 只返 ACTIVE/PLANNED）；重试器流式面三大疑点（裸抛穿透/半截重复/marker 泄漏）实读排除；四变异独立复演全红（拔面A/清词表/拒 ACTIVE 场/无条件 can_open）。
4. **魂检**：「修复的不是按钮的显示条件，是用户在世界里的可恢复位。重试诚实——没有一处把失败洗成静默的成功。」
5. **处置登记**：F1（MINOR）引擎层零段 settle 门仅面控位（UI 不可达，直呼 API 可产 CLOSED+零段永久态）→与 DS-3 F2/F3/F5 窄窗打包归下个触 turns.py 的刀；F2/F3 NIT（detail 语义偏差/inner:Any）；F4 观察（5xx/429 不在重试词表——与 §8 合同严格一致，放宽须同步合同＋钉）；F5 观察（预算注释半句差）；流臂重拨期间无「重拨中」信号（final 自愈兜底，可选增强）。
6. **纪律**：执行者零通道违规（DS-3 训诫后首次全净）；评审自报仓外探针 heredoc ×1（训诫留痕）。
7. **盖章与收口**：VR `VR-OPI-6cb9104c-…8`（**PASS**，盖于 `6befe37`）；收口 DEC `DEC-OPI-6cb9104c-…9`（rev 861）；design_sync REBUILD+CHECK＝**SYNCED**（858 对象/rev 861）。
8. **scratch 处置（防坑㊵）**：`D:\elc-scratch\ds4\` 保留 pytest_master.log/heal_probe.py/rev\full_suite.txt；**删除 heal_copy.db**（用户库副本——证据已入 VR/REGISTER，不留用户数据副本）＋中间日志。
9. **下一动 = 用户重启 8760（Ctrl+C → `python -m elc web --app-db ./app.db`）→开篇钮回归→点开篇从世界真实位置（布丽恩问话悬着/玩家手艺已递）继续落笔→亲验四判据**；F4 专属模型口径同场可裁。

授权：用户 2026-10-15「必须根治」明令＋两连实败取证；独立评审＋魂检同卷；本条目为收口留痕。

### v1.7.23 — 2026-10-15 用户亲验终审：呈现/体验层不满意（六簇批评全量入册；设计义务随一级新仓；授权：用户原话「我不满意」＋「起码是要知道的」）

**结论**：DS-4 修复后用户重启亲验（开篇钮回归、世界可恢复——机械面验证通过），随后对**呈现/体验层**作终审不满意。六簇批评（原话要点，DEC `OPI-f45d1976-…2` 全量在册）：**A 行文生硬**（「你看得明白在写什么吗？怎么设计的」）；**B 无引向用户输入的手段**（正文不把话筒递给用户）；**C 停点不可解**（看不懂为什么停在这、知道该写也不知怎么写）；**D 无推荐选项**（本应有可选接话选项）；**E 文字到达体验全败**（「突然之间全部显示，完全不是流式；文字输出的方式非常重要，必须精巧设计，仅流式都不够」——总控注：叙述臂技术上是 SSE 流式但排五臂末尾，体感＝空白百余秒后文字爆出；SSE 分帧是否真到达浏览器待探针）；**F 思考过程不可见＋UI/UX「糟糕透顶，比原来信件UI差十倍不止，毫无前瞻性/功能设计/设计性」**。**总控结构性自认**：引擎已捕获呈现层所需的一切（停因判定依据〔§4 已记日志〕、接话选项〔调度 options 字段已解析〕、角色私念〔已锚记忆行〕、提案保真〔可溯源〕）——**UI 从未显示其中任何一项，是调试台不是产品**。四判据终审：引擎层有据（DS-3 实证）但判据③体验层失败、判据④受行文拖累——**产品不通过**。

1. **归位（用户明裁）**：「不一定非要现在做，等到了新仓做也未尝不可，但你起码是要知道的」——设计义务随一级新仓（三仓战略 DEC `OPI-f55cd8c7…13`，异名异前端），本 DEC 为新仓呈现层**设计输入与验收基准**，revisit 钉在新仓开仓条件上。
2. **设计方向候选（总控提出，待新仓深化＋原型手感验证，非承诺）**：①落笔即体验——句级到达/阅读节奏自适应/段间呼吸，等待四臂期间以角色心声细语行填充（私念已入库）；②话头合同——停拍正文末句以悬置形递话筒＋2–3 枚可编辑接话签（options 已有）＋自由输入永在；③停点可解释——停因依据轻注呈现；④行文风律——约束堆叠移入结构层、文风律入叙述合同。
3. **本仓不动刀**（用户裁度）；SSE 分帧到达验证与「本仓先修某项」留待用户另裁。

授权：用户 2026-10-15 原话反馈（「我不满意」）；本条目为用户判词留痕，无代码交付。

### v1.7.24 — 2026-10-15 F4 裁决：主角专属模型＝物理分离＋用户可配（每主角模型＋行文模型自选；授权：用户原话）

**结论**：用户原话裁决（DEC `OPI-f45d1976-…5`）：「主角各配专属角色模型可以做，而且用户应当可自己设置决定每个主角使用什么模型，行文使用什么模型」——**per-role 用户可配模型面**：①角色→模型映射（双主角各自专属模型实例）；②行文（叙述臂）独立可选；③**用户设定面自选**（新仓呈现层）；④调度/计划/裁定臂维持现 main/light 档位（未裁扩大，留扩展）；⑤首版建议同 provider 异模型名（provider-per-role 列扩展档）；⑥**归位**：引擎接线（per-role provider 构造＋配置存储）＋设定面为一完整特性，随新仓开仓动工——本仓冻结现状保「引擎随迁不重写」干净；⑦验证注：独立性消融须两组对照（同模型心智包 on/off＝心智贡献；不同模型＝模型贡献）；⑧成本注：per-role 改变成本结构，设定面示每角色当前模型。

授权：用户 2026-10-15 原话；本条目为产品裁决留痕，无代码交付。
