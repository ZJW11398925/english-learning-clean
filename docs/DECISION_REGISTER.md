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

