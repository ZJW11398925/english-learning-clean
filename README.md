# English Learning — Clean Rewrite (V1)

Canonical Implementation Baseline V1（2026-09-20）。规范优先级：`docs/` 六份 canonical 文档 > `behavioral_baselines/` 参考与回归资产 > 任何历史设计文档与旧实现（旧仓库 `D:\测试1` 整体作为 exploration archive 保留）。

- `docs/` — PRODUCT_CONTRACT / DOMAIN_MODEL / STATE_MACHINES / DATA_MODEL / RUNTIME_ARCHITECTURE / IMPLEMENTATION_PLAN + DECISION_REGISTER + ARCHITECTURE_BASELINE + 一致性报告（机器复核 60/60 PASS）
- `behavioral_baselines/` — BF-01～07（Estimator / Planner / Gate / Golden / Modality / Local Runtime / Security）：**实现合同，不是设计参考**；新仓库必须自动回归
- `src/` — 域模块（**Phase 0–10 已填充**：conversation / persona / learning（含 natural-chat silent evidence）/ teaching（含 Gate 的四个 profile 与 rollout 门槛检查器）/ runtime（含 recovery scan 面、delivery records、guarded stream、pre-delivery guard、exposure reconciliation）/ platform / relationship（含 Episode 投影）/ planner（kernel + 可审计 trace + 候选供给侧/scope/frontier/ledger + shadow mode 与冻结 43 例重放）/ deletion（BF-05 source-aware 删除与墓碑）/ user_config（§5.1 Goal·Policy·Focus 版本化 + §9 PlannerConstraint）/ scheduler（§5.2 ScheduleItem·ReviewEvent、spacing 纯策略 due/overdue、ScheduleView）/ curriculum（R0–R4 readiness + production TeachingTargetProvider）/ content（content.db 确定性构建与只读读面）/ world_lore；其余域按 IMPLEMENTATION_PLAN §1.5 位次待填）
- `tests/` — architecture / state-machine / determinism / property / failure-injection / golden（IMPLEMENTATION_PLAN §14）
- `migrations/` — app.db 迁移

第一条学习垂直切片现状（`DEC-OPI-5ba74efc-….65/.68`）：**Teaching-driven learning vertical slice COMPLETE**（explicit user TeachingMoment → target-specific Attempt Evidence → LearnerState，含 before≠after 可追溯与全链验收）；**natural-conversation target-specific silent Evidence 已随 Phase 5 交付、并经 P5-R 按 canonical 收窄**（自然 Persona 对话 → 确定性 target resolution：**仅 RESOURCE 目标、仅整句形式的 canonical/alternative 命中**才铸 target-specific Performance Evidence → Estimator → LearnerState；CAPABILITY 命中、仅 slot 命中、嵌入跨度/引用/转述/元语言一律**只记匹配观察、不产生证据**；无 TeachingMoment/Gate/Planner 介入，供给降级不阻聊天）。实现 PR 必须能指出自己遵循/修改哪一条 contract。

**实现现状（2026-09-25）**：**Phase 0–10 全部 COMPLETE（工程）**——Phase 8 = Planner→Gate→自动教学链 + rollout 门槛检查器（判 `HOLD`）；Phase 9 = Delivery / Exposure Hardening（含 P9-R 三件高/中危修复后重签 PASS）；**Phase 10 = Runtime Recovery**（五刀：scan 面补齐 / 25 类失败场景套件 A+B / 两个待裁题正式裁决 / D1 fence 修复 + F4 收口 + 相位级映射表）。读数：**3608 passed / 0 failed / 0 skipped**（phase3 280 / phase6 666 / phase7 420 / phase8 667 / phase9 511 / phase10 65 / deletion 120）、ruff clean、mypy **154 文件 0 error**、compileall 0；迁移 head **`0018_delivery_records`（v18）**。**真实 automatic-teaching rollout 仍 HOLD**（开闸前置 = SessionBudget 三分 + 内容补课，与 Phase 9/10 无关）；具体交接与对象索引见 `AGENTS.md`。
