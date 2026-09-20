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
