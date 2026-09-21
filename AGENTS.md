# AGENTS.md — english-learning-clean（Clean Rewrite · Implementation Baseline V1）

## 项目一句话

成人英语学习应用「英语客厅」的 **Clean Rewrite**：以 Implementation Baseline V1（用户主导的更高智力讨论收敛，2026-09-20 交回）为唯一规范权威，从零实现。**规范优先级：本仓 `docs/` 六 canonical 文档 > `behavioral_baselines/` 行为基线资产 > 其他一切**（旧仓 `D:\测试1` 整体为 exploration archive，其全部设计仅作历史参考）。实现栈已裁：**Python 内核 + SQLite**（app.db 可变 / content.db 只读 / SecretStore；客户端边界已裁 `DEC-…d7937fd7.12`：进程内 Python API，交互面推迟 Phase 8 末后）。

## 🔴 dmcp 段（新会话续接第一入口）

- **workspace_id**：`ws-7585bd9c-f6ec-4c73-be14-d2e635a37033`（**schema 5**；旧工作区 `ws-db58afd2-…` 已随旧仓归档，别用）
- **续接顺序**：①读本文件 → ②`design_status` 刷基 → ③`design_get` `DEC-OPI-2babb21e-bc72-47a2-9382-e773c92211d2.5`（**P3-1 开工基线**：grilling 两轮 20 问全量裁定，两项核心裁定=USER_INITIATED Gate specialization/Legacy DecisionCycle backfill）→ ④`git log --oneline` → ⑤开工前读 `docs/IMPLEMENTATION_PLAN.md` §9（Teaching Detail Block）与 §1.5（normative 顺序），再按派单协议铸任务书（四查+VAL+TASK 同铸；P3-1B 任务书必带 DEC-…2babb21e.34 的 F5+F9/F8/F10 清单）
- **当前状态**（2026-09-21 第八会话末）：**Phase 3 进行中，P3-1A COMPLETE**（rev 51，sync REBUILD+CHECK 零告警）——grilling 两轮（20 问）收敛 → 开工决策 `DEC-…2babb21e.5`（OPI `2babb21e-bc72-47a2-9382-e773c92211d2`）→ 母计划 `PLAN-…2babb21e.15`（p3-1a→p3-1b→p3-2→p3-3）→ P3-1A 交付 `148f96f`（`VR-…2babb21e.25` PASS）：0007 三表+legacy cycle backfill+全 action lineage 收紧（NOT NULL+FK）/Runtime DecisionCycleStore（authority 归 Runtime）/Gate v1.1 USER_INITIATED profile（BF-03 冻结 17 词逐词同+差分矩阵以冻结参考为 oracle）/CP2 五事实原子/request_teaching canonical command turn/六顺带（DEC-…58 全清）/14 validated target fixtures。独立评审 10 findings 处置 `DEC-…2babb21e.34`（F1 MAJOR 同 target 重复请求静默回放已修+F2/F3/F4 已修+F6 留痕式钉；**P3-1B 必带**：F5+F9 教学恢复面（DEGRADED 崩溃续接+recovery 词典咬合）、F8 completion/abort 词表 CHECK、F10 导出面；F7 字面量白名单 join 口径裁定合规）。违规执法一次：执行者 Bash heredoc 落盘一处 → 按 `DEC-…eaaa5a1d.33` 升格政策拒收 → Read→Write 重落 sha256 零差返工。**下一步 = P3-1B**（envelope 五步/Attempt+Evaluation+evaluator v0 五值含 ALTERNATIVE_SUCCESS/LOR+Evidence 编排链（opportunity_id 恒链+Learning 验 LOR 语义）/presentation ladder/hint/retry/reveal/skip/reject/topic shift/switch target（同 turn cycle+1）/limits v0（2/3/3/5+hard cap 收尾豁免）/TEACHING_TERMINAL+lock 释放同事务/PERSONA_RESUME（只传 ResumeDirective）→CLOSED/0008 attempt 两表/教学 turn 终态化与恢复面；验收=VAL-…2babb21e.9 十组）→ P3-2（OQ-024A 16+ 状态压力，本体定位=开工四查必答，VAL-….11）→ P3-3（全链验收 before≠after 可追溯，VAL-….13）
- **对象索引**（全 id 可直接 design_get；新增 OPI 前缀 `2babb21e-bc72-47a2-9382-e773c92211d2`，Phase 3 系列全在此；旧系列 OPI 前缀 `eaaa5a1d-7ac7-4746-bcdf-c02bc9147492`）：
  - `DEC-…2babb21e.5` **P3-1 开工基线**（grilling 20 问全量；两核心裁定+CP2 五事实+两时点+request_teaching+evaluator 五值+limits+provider port——P3-1B 任务书的第一设计权威）
  - `DEC-…2babb21e.34` P3-1A 评审处置（10 findings；F5+F9/F8/F10 打包 P3-1B 必带；F7 口径；违规执法留痕）
  - `VAL-…2babb21e.7/.9/.11/.13` P3-1A/P3-1B/P3-2/P3-3 四验收；`PLAN-…2babb21e.15` Phase 3 母计划；`TASK-…2babb21e.17` P3-1A 任务书；`VR-…2babb21e.25` P3-1A 盖章（PASS）
  - `DEC-…eaaa5a1d.58` P3-0 评审处置（六顺带已随 P3-1A 全清；transition/terminalize store 级 fence 悬题 P3+ 复审）
  - `DEC-…eaaa5a1d.51` **外部评审采纳**（Phase 3 GO+六门+P3-0/1/2/3 分解+四修正+metadata 授权）
  - `DEC-…eaaa5a1d.48` **PHASE 2 COMPLETE**；`VR-…eaaa5a1d.46/.47` P2B+相位门；`VAL/TASK/VR-…eaaa5a1d.42/.44/.46` P2B 三件
  - `DEC-…eaaa5a1d.33` P2A 评审处置（拒收政策升格）；`DEC-…eaaa5a1d.26` Phase 2 开工（裁定 a–f）
  - P2A 三件 `.28/.30/.32`、修复三件 `.35/.37/.39`、边界修复 `.4/.6/.8`、微修复 `.11/.13/.15`
  - `PLAN-…eaaa5a1d.19` Phase 2 PLAN（执行完毕）；`VAL-…eaaa5a1d.17` 相位门（PASS）
  - `DEC-…eaaa5a1d.2` 外部评审采纳（权威漂移）；`DEC-…d7937fd7.19`/`DEC-…d7937fd7.12` Phase 1 评审/COMPLETE
  - `DEC-…9dc4e77f.4` **契约载体**（跨会话重建先读它）；`DEC-…091f35c3.7/.13`；`DEC-…d5b616bf.3/.7`；`DEC-…7bf80972.2` PHASE 0

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
- **测试**：`python -m pytest`（当前 395/0/0）；静态：ruff + mypy（88 文件）；migrations 到 0007（schema_version 7）；GenerationAction 权威在 runtime（DM §16）；DecisionCycle 权威在 Runtime（`DEC-…2babb21e.5`：DecisionCycleStore port，physical adapter 共址 platform/db）
- **Mimosa 安全钩子**：Bash 直写源码/配置被拦——**.py/.sql/.yml/.toml 一律 Write/Edit 工具落盘**（P1B 执行者曾一次 Bash 直写 .py 未被钩子拦但违反明令，已在 `DEC-…d7937fd7.12` 训诫留痕——总控与执行者均不得再犯）；SQL 一律参数绑定或全字面量（标识符用白名单全字面量），禁任何拼接
- **基线冻结**：`behavioral_baselines/` 的 .py 一字节不改（例外须按 `DEC-…d5b616bf.3` 范式：显式决策+最小改动+manifest 重钉）；六 canonical 文档只许 `DECISION_REGISTER.md` 的版本条目
- **不做**（纪律）：未到位次的域逻辑/域表提前实现（位次见基线 §1.5：Phase 3=用户发起 TeachingMoment 已解锁（P3-1A 开链完成，P3-1B 面=envelope/attempt/evaluation/evaluator/0008/[teaching] prompt 节/PersonaResume 仍禁至 P3-1B 开工），其余域仍禁）；Redis/Kafka/分布式锁/TTL/heartbeat（Local V1 §24.1 永禁）；自动教学/Planner SELECT（Phase 8 才开）；`decision_cycle_id` 收紧已随 0007 兑现（`DEC-…091f35c3.7` 裁定 b 闭环）
- docs/run_post_bf_regression.py 的 ROOT 自相矛盾是原件冻结缺陷，永久不可修——repo-native 七套件是长期替代；勿再尝试修它
- Windows：core.autocrlf 与 blob 有字节差，哈希校验须 CRLF 归一；建议后续加 .gitattributes（勿扰动冻结文件行尾）

## 常用命令

```bash
python -m pytest          # 全量（含架构门与七套件行为基线）
ruff check . && mypy src  # 静态门
git push                  # CI 自动跑四门
```
