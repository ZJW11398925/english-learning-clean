# English Learning — Clean Rewrite (V1)

Canonical Implementation Baseline V1（2026-09-20）。规范优先级：`docs/` 六份 canonical 文档 > `behavioral_baselines/` 参考与回归资产 > 任何历史设计文档与旧实现（旧仓库 `D:\测试1` 整体作为 exploration archive 保留）。

- `docs/` — PRODUCT_CONTRACT / DOMAIN_MODEL / STATE_MACHINES / DATA_MODEL / RUNTIME_ARCHITECTURE / IMPLEMENTATION_PLAN + DECISION_REGISTER + ARCHITECTURE_BASELINE + 一致性报告（机器复核 60/60 PASS）
- `behavioral_baselines/` — BF-01～07（Estimator / Planner / Gate / Golden / Modality / Local Runtime / Security）：**实现合同，不是设计参考**；新仓库必须自动回归
- `src/` — 域模块骨架（Phase 0，按 IMPLEMENTATION_PLAN §2 填充：conversation / persona / relationship / learning / curriculum / scheduler / planner / teaching / runtime / content / platform）
- `tests/` — architecture / state-machine / determinism / property / failure-injection / golden（IMPLEMENTATION_PLAN §14）
- `migrations/` — app.db 迁移

第一条必须验证的学习垂直切片：**Persona Conversation → Performance Evidence → LearnerState → explicit TeachingMoment → Attempt → New Evidence**。

实现 PR 必须能指出自己遵循/修改哪一条 contract。
