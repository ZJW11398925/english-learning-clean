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
