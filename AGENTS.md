# AGENTS.md — english-learning-clean（Clean Rewrite · Implementation Baseline V1）

## 项目一句话

成人英语学习应用「英语客厅」的 **Clean Rewrite**：以 Implementation Baseline V1（用户主导的更高智力讨论收敛，2026-09-20 交回）为唯一规范权威，从零实现。**规范优先级：本仓 `docs/` 六 canonical 文档 > `behavioral_baselines/` 行为基线资产 > 其他一切**（旧仓 `D:\测试1` 整体为 exploration archive，其全部设计仅作历史参考）。实现栈已裁：**Python 内核 + SQLite**（app.db 可变 / content.db 只读 / SecretStore；客户端边界已裁 `DEC-…d7937fd7.12`：进程内 Python API，交互面推迟 Phase 8 末后）。

## 🔴 dmcp 段（新会话续接第一入口）

- **workspace_id**：`ws-7585bd9c-f6ec-4c73-be14-d2e635a37033`（**schema 5**；旧工作区 `ws-db58afd2-…` 已随旧仓归档，别用）
- **续接顺序**：①读本文件 → ②`design_status` 刷基 → ③`design_get` `DEC-OPI-d7937fd7-2f4e-4e4b-940e-25a8b32143f4.12`（**PHASE 1 COMPLETE** + 客户端边界裁定 + P1B 六项偏差处置）→ ④`git log --oneline` → ⑤开工前读 `docs/IMPLEMENTATION_PLAN.md` §5（Phase 2 Detail Block）与 §1.5（normative 顺序），再按派单协议铸 Phase 2 任务书（四查+VAL+TASK 同铸）
- **当前状态**（2026-09-20 第七会话末）：**PHASE 2 COMPLETE 不变；Phase 3 已开工，P3-0 Entry Gates COMPLETE**（rev 43，sync 零告警）——外部评审采纳 `DEC-…eaaa5a1d.51`（六门对五 DEFER 册收敛+四修正）；metadata 三件清陈 `2e5e5df`；P3-0 五门 `373f746`（`VR-…eaaa5a1d.57` PASS，**零违规**——拒收政策后首次全程清白）：快照水位一致性（stale 拒读）/LearningController 真实面/CharacterPackage 十五列 fixture 入正常链/DecisionCycle 表 0006（零写入面）/canonicalize 双道 epoch fence；聚焦评审 6 findings 处置 `DEC-…eaaa5a1d.58`（无 MAJOR，F1-F5 微修打包 P3-1 必做顺带项，F6 口径注记）。**下一步 = P3-1**（用户发起 TeachingMoment vertical slice：设计类任务书**须过 grilling 前沿**→开工决策；必带：F1-F5 微修清单+DecisionCycle lineage 语义（用户发起 vs planner 授权两源）+Opportunity 顺序硬不变量+opportunity_id 链接+0002 注释清陈+10–20 validated target fixtures；随后 P3-2 OQ-024A 状态压力→P3-3 全链验收（before≠after 可追溯 Evidence，禁 moment 直接改 mastery））
- **对象索引**（全 id 可直接 design_get；OPI 前缀 `eaaa5a1d-7ac7-4746-bcdf-c02bc9147492`）：
  - `DEC-…eaaa5a1d.58` P3-0 评审处置（6 findings；F1-F5 打包 P3-1；transition/terminalize store 级 fence 悬题 P3+）
  - `VAL-…eaaa5a1d.53`/`TASK-…eaaa5a1d.55`/`VR-…eaaa5a1d.57` P3-0 三件（PASS）
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
- **测试**：`python -m pytest`（当前 264/0/0）；静态：ruff + mypy（82 文件）；migrations 到 0006（schema_version 6）；GenerationAction 权威在 runtime（DM §16）
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
