# AGENTS.md — english-learning-clean（Clean Rewrite · Implementation Baseline V1）

## 项目一句话

成人英语学习应用「英语客厅」的 **Clean Rewrite**：以 Implementation Baseline V1（用户主导的更高智力讨论收敛，2026-09-20 交回）为唯一规范权威，从零实现。**规范优先级：本仓 `docs/` 六 canonical 文档 > `behavioral_baselines/` 行为基线资产 > 其他一切**（旧仓 `D:\测试1` 整体为 exploration archive，其全部设计仅作历史参考）。实现栈已裁：**Python 内核 + SQLite**（app.db 可变 / content.db 只读 / SecretStore；客户端边界已裁 `DEC-…d7937fd7.12`：进程内 Python API，交互面推迟 Phase 8 末后）。

## 🔴 dmcp 段（新会话续接第一入口）

- **workspace_id**：`ws-7585bd9c-f6ec-4c73-be14-d2e635a37033`（**schema 5**；旧工作区 `ws-db58afd2-…` 已随旧仓归档，别用）
- **续接顺序**：①读本文件 → ②`design_status` 刷基 → ③`design_get` `DEC-OPI-d7937fd7-2f4e-4e4b-940e-25a8b32143f4.12`（**PHASE 1 COMPLETE** + 客户端边界裁定 + P1B 六项偏差处置）→ ④`git log --oneline` → ⑤开工前读 `docs/IMPLEMENTATION_PLAN.md` §5（Phase 2 Detail Block）与 §1.5（normative 顺序），再按派单协议铸 Phase 2 任务书（四查+VAL+TASK 同铸）
- **当前状态**（2026-09-20 第五会话末）：**Phase 2 P2A COMPLETE**（rev 36，sync 零告警）——开工决策 `DEC-…eaaa5a1d.26`（P2A/P2B 切分+前沿裁定 a–f）；P2A Learning durable core `b53a8e8`（migrations/0004 八表=六 canonical+水位/commit 两物理表、CP1 单短事务+水位单调、确定性 producer、负面证据门、coordinator CP0→analysis→CP1 接线、44 测试，`VR-…eaaa5a1d.32` PASS）；独立评审 4 findings 处置 `DEC-…eaaa5a1d.33`（**F1 MAJOR learning 腿钉死违反 RA §21 降级路径+F3 NEUTRAL 缺值→已修 `ba1794c`**（`VR-…eaaa5a1d.39` PASS+聚焦评审 0 finding）；F2 invalidate/水位→P2B 裁定；F4 opportunity_id→P3+）；**第三次 Bash 直写违规已升格政策：再犯任何执行者直接拒收返工**（DEC.33）。**下一步 = P2B**（Estimator V1+LearnerTargetState+LearningSnapshot+BF-01A 语义等价，PLAN RISK_SPIKE+VE 工作项；四查+VAL+TASK 同铸 → executor-pro）
- **P2B 任务书必带约束**（历次评审累积）：①F2：invalidate 是否推水位或 rebuild 失效判据不依赖水位（SM §18:577 active evidence 重建语义）；②pending PRODUCED artifact 归宿（消费/取代/仅审计——聚焦评审 INFO）；③claim 缺列默认值复核（spontaneity='SPONTANEOUS'/elicitation='NATURAL' 系统性偏自发，接 estimator 前显式裁定）；④钉死约定「水位=行为提交数非证据质量」（零 claim group 贡献为零）；⑤ResponseValidator≠Learning Evaluator 静态分离（VAL-…17 红线）；⑥estimator 自实现不 import 冻结资产（裁定 c），BF-01A 全场景经真实 kernel 全绿为验收门
- **对象索引**（全 id 可直接 design_get；新链 OPI 前缀 `eaaa5a1d-7ac7-4746-bcdf-c02bc9147492`）：
  - `DEC-…eaaa5a1d.33` **P2A 评审处置**（F1 MAJOR 降级路径+F3 已修/F2→P2B/F4→P3+；第三次 Bash 直写违规+拒收政策升格）
  - `VAL-…eaaa5a1d.35`/`TASK-…eaaa5a1d.37`/`VR-…eaaa5a1d.39` P2A 修复三件（PASS，聚焦评审 0 finding）
  - `DEC-…eaaa5a1d.26` **Phase 2 开工**（两刀切分+前沿裁定 a–f：decision_cycle_id 推迟 Phase 3/analysis 确定性/estimator 自实现/ExpressionNeed 非 negative/F4 挂账/user_scope_id Local V1 默认）
  - `VAL-…eaaa5a1d.28`/`TASK-…eaaa5a1d.30`/`VR-…eaaa5a1d.32` P2A 三件（PASS）
  - `PLAN-…eaaa5a1d.19` **Phase 2 PLAN**（VS→RS→VE 三工作项；VS 前半=P2A 已完，后半+RS+VE=P2B）
  - `VAL-…eaaa5a1d.17` Phase 2 验收门（BF-01A 全场景+证据先行+分离红线+范围红线）
  - `DEC-…eaaa5a1d.2` 外部评审采纳（权威漂移核实+三处修正；§16 归属对照进评审必查项）；`DEC-…eaaa5a1d.9` 边界修复评审处置
  - `VAL-…eaaa5a1d.4`/`TASK-…eaaa5a1d.6`/`VR-…eaaa5a1d.8` 边界修复三件（PASS）；`VAL-…eaaa5a1d.11`/`TASK-…eaaa5a1d.13`/`VR-…eaaa5a1d.15` 评审微修复三件（PASS）
  - `DEC-…d7937fd7.19` Phase 1 独立评审处置（6 findings；review 面构建局限留痕；RA §24.1 读法注记）；`DEC-…d7937fd7.12` **PHASE 1 COMPLETE**+客户端边界
  - `DEC-…9dc4e77f.4` **契约载体**（rev 2：契约六面+六 canonical digest+三面构建局限假设；跨会话重建先读它）
  - `DEC-…091f35c3.7` Phase 1 开工（两悬题裁定）；`DEC-…091f35c3.13` 派单阻塞处置（thoughtLevel: max）
  - `DEC-…d5b616bf.3` 基线 v1.0.1 例外修订——**例外修订范式**；`DEC-…d5b616bf.7` 外部评审采纳（五 blocker）
  - `DEC-…7bf80972.2` + `VR-…7bf80972.4` **PHASE 0 COMPLETE**

## dmcp 工作流协议（v2，2026-09-20 用户纠正后立——总控必守）

每刀（task）完整链：**四查+VAL+TASK 同铸 → 派执行者 → 总控独立复核（pytest/ruff/mypy/CI 亲跑）→ validation_submit 盖章 → 独立评审（新上下文 executor-pro 只读评审，产 findings）→ 处置（修/DEFER/留痕）→ design_sync REBUILD+CHECK 收口**。缺评审即违约（本仓 2026-09-20 已犯一次，用户点名纠正）。

- **纪律 ①（⟳ 刷基）**：连续两次 dmcp 变更之间必须 design_status 纯读刷新基再填 expected——REVISION_CONFLICT 即忘了刷基（错误面会给 current id 可直接重构）
- **Phase 开工第 0 步**：`plan_build` 铸 PLAN（VERTICAL_SLICE/RISK_SPIKE/VALIDATION_EXPERIMENT/ENABLER 工作项+relations）；任务从 plan 工作项展开。**readiness 更正（2026-09-20 第四会话查实）**：design_readiness 的 gate 行来自 gate policy 而非 plan_build——默认策略是 FINDING-only 单族行集（每条 finding 一行 BLOCKING），finding 册恒空 ⇒ 恒 READINESS_BASIS_INCOMPLETE；解锁要么服务端接线 preparer 让 findings 真实入册，要么宿主侧配 `DMCP_READINESS_POLICY_FILE`（宿主操作，不代执行）。**阶段门禁当前由本仓工作流承担**（VAL+独立评审+decision），readiness 仅作解锁后的复核面
- **评审面构建局限（当前服务端，已铁证）**：REVIEW_REQUIREMENT/REVIEW_PACKET 只能由宿主侧 preparer 铸，而 dist 无任何入口接线 `createHostReviewBasisPreparer`（D:\MCP apps/mcp-server，查实 0 wiring）→ review_submit 恒 OBJECT_NOT_FOUND、finding 册因构造恒空（finding_list=0 是构建事实不是「无问题」）。**降级路径**：评审照做（独立上下文评审员），findings 全文+证据+裁定入 decision（范式见 `DEC-…d7937fd7.19`/`DEC-…eaaa5a1d.9`），服务端升级接线后补录正式 finding 并迁移裁定
- **主体/能力（当前服务端 env）**：HUMAN_USER + DESIGN_STATE_READ/MUTATE 两族——FINDING_ADJUDICATION/DISPOSITION 族未授，裁决面即使有 finding 也会被诚实拒绝；升级服务端配置属宿主侧操作，skill 不代执行
- 契约=跨会话记忆：GOAL/RUNTIME/IN_SCOPE/OUT_OF_SCOPE/TECHNICAL_CONSTRAINTS/ASSUMPTIONS 在载体 `DEC-…9dc4e77f.4`（含六 canonical 文件 digest 绑定，漂移即假设失效；AGENTS.md 活文档不绑）；契约改写是整体替换（⑲），改前先 design_get 读回

## 派单协议（用户明令，2026-09-20）

- **执行者 = `executor-flash`（一般任务）/ `executor-pro`（难题）**——用户安装在 `~/.zcode/agents/`（model 钉 GLM-5.3-Flash / GLM-5.3，**须带 `thoughtLevel: max` 键**——2026-09-20 补，缺则新 harness 拒启，见 `DEC-…091f35c3.13`）。**禁止用内置 `general-purpose` 做执行任务**。
- 总控不亲自执行（写代码/测试/探针/部署一律派执行者，先 `task_build` 铸任务书）；设计类任务书先过 grilling 前沿；**任务书四查 + VAL 与任务书同铸**（前沿/实现设计条目/计划时效/预算算术；交付后补盖 VAL 视同无效验收）。红线全文 0–31 见旧仓 `D:\测试1\AGENTS.md`（红线 28/29/30/31 尤其要读）。

## 工程事实与红线（本仓特有）

- **远程**：github.com/ZJW11398925/english-learning-clean（public）；**CI 四门**：ruff → mypy → compileall → pytest（push+PR，Ubuntu，0 skipped 为准）
- **测试**：`python -m pytest`（当前 180/0/0）；静态：ruff + mypy（81 文件）；migrations 到 0004（schema_version 4）；GenerationAction 权威在 runtime（DM §16）
- **Mimosa 安全钩子**：Bash 直写源码/配置被拦——**.py/.sql/.yml/.toml 一律 Write/Edit 工具落盘**（P1B 执行者曾一次 Bash 直写 .py 未被钩子拦但违反明令，已在 `DEC-…d7937fd7.12` 训诫留痕——总控与执行者均不得再犯）；SQL 一律参数绑定或全字面量（标识符用白名单全字面量），禁任何拼接
- **基线冻结**：`behavioral_baselines/` 的 .py 一字节不改（例外须按 `DEC-…d5b616bf.3` 范式：显式决策+最小改动+manifest 重钉）；六 canonical 文档只许 `DECISION_REGISTER.md` 的版本条目
- **不做**（纪律）：未到位次的域逻辑/域表提前实现（位次见基线 §1.5：Phase 2=Learning Evidence Kernel 已解锁，其余域仍禁）；Redis/Kafka/分布式锁/TTL/heartbeat（Local V1 §24.1 永禁）；自动教学（Phase 8 才开）；`decision_cycle_id` 等 Phase 2 收紧钩子见 `DEC-…091f35c3.7` 裁定 b
- docs/run_post_bf_regression.py 的 ROOT 自相矛盾是原件冻结缺陷，永久不可修——repo-native 七套件是长期替代；勿再尝试修它
- Windows：core.autocrlf 与 blob 有字节差，哈希校验须 CRLF 归一；建议后续加 .gitattributes（勿扰动冻结文件行尾）

## 常用命令

```bash
python -m pytest          # 全量（含架构门与七套件行为基线）
ruff check . && mypy src  # 静态门
git push                  # CI 自动跑四门
```
