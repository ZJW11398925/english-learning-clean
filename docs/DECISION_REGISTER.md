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

