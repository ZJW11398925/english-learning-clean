# AGENTS.md — english-learning-clean（Clean Rewrite · Implementation Baseline V1）

## 项目一句话

成人英语学习应用「英语客厅」的 **Clean Rewrite**：以 Implementation Baseline V1（用户主导的更高智力讨论收敛，2026-09-20 交回）为唯一规范权威，从零实现。**规范优先级：本仓 `docs/` 六 canonical 文档 > `behavioral_baselines/` 行为基线资产 > 其他一切**（旧仓 `D:\测试1` 整体为 exploration archive，其全部设计仅作历史参考）。实现栈已裁：**Python 内核 + SQLite**（app.db 可变 / content.db 只读 / SecretStore；客户端边界已裁 `DEC-…d7937fd7.12`：进程内 Python API，交互面推迟 Phase 8 末后）。

## 🔴 dmcp 段（新会话续接第一入口）

- **workspace_id**：`ws-7585bd9c-f6ec-4c73-be14-d2e635a37033`（**schema 5**；旧工作区 `ws-db58afd2-…` 已随旧仓归档，别用）
- **续接顺序**：①读本文件 → ②`design_status` 刷基 → ③`design_get` 三件：`DEC-OPI-4d516e4f-9575-4cbf-8d08-6bf19a95bd25.32`（**外部评审采纳（Phase 4 复核 + Phase 5 GO）：表述收窄 + 三重生产硬门 + Phase 5 指引「禁用 _seed()」**——Phase 5 开工前必读）＋`DEC-…4d516e4f.29`（**P4-4 处置 + PHASE 4 COMPLETE 收口**：五刀链+五验收+遗留清单七项）＋`DEC-…5ba74efc.68`（**Phase 4 总设计权威**，其表述收窄句 Phase 5 仍要并已由 DEC-…32 扩写）→ ④`git log --oneline` → ⑤开工前读 `docs/IMPLEMENTATION_PLAN.md` §1.5 与 **§6（Phase 5 Detail Block）**（另需 §16 DoD #25 删除项与 §14 测试策略），再按派单协议铸下一刀任务书（四查+VAL+TASK 同铸；**四查必答：列名/词表照 canonical 原文；Phase 5 首刀必带「禁用 _seed()」验收条 + 先接真链路（content.db 只读 reader→curriculum identity→R0–R4 readiness→production TeachingTargetProvider→natural-chat resolver）后扩内容 + 外评工具链读数（28/47-of-89/14/13-13）四查验真 + 三重生产硬门触发条件进 PLAN + DEC-…29 遗留取舍 + 两份清单；**VAL 一律带实际触及路径集**）
- **执行者遗留处理先例**（已发生三次：P3-1A/P3-2/P4-4 前均因 API 余额中断留下半成品）：开工前必查 git status——不干净时先取证（快照/sha256/差异分析），按「吸收+逐文件复核+修正+补齐+留痕」或「拒收重交」二选一，绝不静默覆盖；**P4-4 先例**：遗留半成品 3 条失败被判测试侧，评审以 as-found 原件复跑逐条复核成立
- **当前状态**（2026-09-21 第十会话末）：**PHASE 4 COMPLETE**（rev 76；sync 见收口记录）——五刀链 P4-0 `d8866b8`（`VR-…5ba74efc.91`）+P4-1 `2acaaca`（`VR-…109`）+P4-2 `ffcafcf`（`VR-…4d516e4f.12`）+P4-3 `6ef5ca1`（`VR-…21`）+P4-4 本刀（`VR-…4d516e4f.28` PASS，处置与收口 `DEC-OPI-4d516e4f-…29`）；五验收全 PASS（VAL-…70/72/80 直盖；VAL-…74/76 路径集过窄 → 同题扩集 VAL-…4d516e4f.7/.17 代盖并留痕取代）。**Phase 4 交付面**：Relationship durable core（Recorder P4-G1 门/validate 八规则/dedupe/append-first supersede/sensitive gate 四判定序/Persona×User 全隔离）+ **CP4 projection runtime**（确定性 pj- id/幂等 enqueue/五态 CAS/slice+based 双重重校验无盲重放/启动三连 reopen→ensure→drain/F-5 claim 护栏/构造期执行器完备性 fail-fast）+ **两投影类型**（RELATIONSHIP + EPISODE；episode §5.3 十列逐字、幂等版本感知重建）+ **DisclosedUserProfile**（§5.1 列集逐字+显式同意门+高敏仅 persona-specific ∧ RICH）+ **PromptCompiler 八节**（persona→profile→contract→history→relationship→episode→teaching→channel；byte-determinism；跨 persona 零泄漏双向）+ 启动恢复五步 + 全链三模式隔离。**P4-4 收官刀亮点**：压力套件抓到并修复真实缺陷 F-1（分类器读失败原被洗成「空成功」COMMITTED、烧掉确定 id 致该轮投影永久丢失 → 检出该 refusal 即 FAILED_RETRYABLE 可重试；评审两次独立反证）；E2E 四组（含 guard 释放/不重发 assistant 直证/durable 行逐字对账/两次重建编译逐字节相等）。读数 **761/0/0**、mypy 108、migrations 0010/v10、冻结面零改动。**遗留清单七项入册 `DEC-…29`**（Phase 5 接续用）。**外部评审（Phase 4 复核 + Phase 5 GO）已采纳入册 `DEC-…32`**：表述收窄=**Relationship/Episode infrastructure COMPLETE；automatic natural-language relationship extraction NOT production-wired**；三重生产硬门（均不阻塞 Phase 5、均不得因「PHASE 4 COMPLETE」被遗忘）：**门一** model proposal 的语义支撑与权威分离（受信 sensitivity authority + 真实 consent 记录 + 抽取式 evidence span/独立语义校验——现 gate 判定序已墙断「模型推断高敏」，但两字段仍是候选层声明）；**门二** BF-05 source-aware deletion + tombstone（**IP §16 DoD #25，V1 内必须排位次**；现状：src 零 delete/tombstone 实现）；**门三** untrusted durable memory → prompt 安全 framing（JSON framing/长度前缀/显式不可信分隔符 + section-spoofing 测试；触发条件=**真实 external provider 或 production candidate provider 任一启用前**，已由此句取代 DEC-…29 遗留③的「Phase 9」表述）；另 CP4 claim→domain write 的 base CAS 加固随下次触碰 CP4 带入。**下一步 = Phase 5（Curriculum + Content runtime integration）**：**开工第 0 步已完成**——母计划 `PLAN-OPI-4d516e4f-…36`（p5-0 基底 / p5-1 readiness+production provider / p5-2 natural-chat 闭环，MUST_PRECEDE 链）+ 相位验收 `VAL-OPI-4d516e4f-…34` 已铸。**P5-0 已 COMPLETE**（`TASK-…4d516e4f.38`，切片验收 `VAL-…4d516e4f.40` 盖 `VR-…4d516e4f.42` PASS，处置 `DEC-OPI-4d516e4f-…43`）：`content_src/`（14 实体迁移自 target_fixtures.py，原件与 P3 消费者零改动）+`curriculum/`（5 capability / 9 CurriculumLink）+`content/{build,store}.py`（确定性构建：四路 sha256 同值；只读连接写全拒；unknown ID 全 NOT_FOUND；§24.1 七列逐列）+`tests/phase5/` **138 用例**。评审 **A–H 全 PASS + 两轮处置**：F-1 写通道单一化并**发现机制事实**——Write/Edit 按目标文件既有行尾复写，改行尾须「无信号 Write 两步法」（**修正了此前锁定的「Edit 往返」表述**）；F-2 校验面四缺口补齐（format/format_version/实体 language 交叉校验）；F-3 §11 词表 canonical 抽取钉；F-5 措辞收窄；F-4/F-6 留痕（F-6 归 p5-1）；第 7 次 Bash 直写按先例处置。读数 **899/0/0**、mypy 110、零 migration、冻结面零改动。**p5-1 已 COMPLETE**（`TASK-…4d516e4f.46`，切片验收 `VAL-…4d516e4f.48` 盖 `VR-…4d516e4f.50` PASS，处置 `DEC-OPI-4d516e4f-…51`）：`curriculum/readiness.py`（§8.1/§24.10 五级判定，三键集；R4 要求可测 detection；**语料 14 target 全为 R1、无虚报 R4**）+`curriculum/provider.py`（production `ContentBackedTeachingTargetProvider` 接 content.db 只读面，语义照 P3 port）+`curriculum/store.py`（薄读适配+12 方法签名统一 = DEC-…43 F-6 收口）+origin/candidate exclusion（§24.11 判据）；**新 E2E 全走真供给链，零 `_seed()` 零 fixture**。读数 **982/0/0**、mypy 113。**两处留痕必读**：①**R1 读法是实现侧解释而非 canonical 裁决——严格读法（POS/sense/basic definition/forms 逐字）下本语料 14 个应是 R0**（前提「全实体皆 EXPRESSION」已由 pin 钉住）；②**全语料止步 R1 ⇒ 按 §8.1 默认表无一 target 满足 Planner 默认门槛**（内容侧补课：PedagogicalProfile/ResourceLabel/PackOverlay/explanation/example policy/contrast/TypicalError/detection fixtures）。**p5-2 已交付待收口**（`TASK-…4d516e4f.55`，切片验收 `VAL-…4d516e4f.57` 盖 `VR-…4d516e4f.59` PASS；**工作树未提交，11 文件**）：`learning/target_resolution.py`（确定性抽取式 resolver：canonical forms 精确→alternative realizations→required slots，固定优先序+仲裁+kind 守卫；未命中 NO_TARGET 零副作用）+`silent_claim.py`（静默观测 claim 契约）+`silent_evidence.py`（content.db 供给端口，坏/缺→降级不阻聊）+`analysis/store/controller` 接线（**静默证据经既有 learning 链落 claim，全程无 TeachingMoment**）；`tests/phase5/test_p5_2_*` 98 条。**前置裁决已落地**：§8.1 默认门槛只约束 Planner 自动教学面、不约束证据形成面（全链零 readiness import 且教学面零动作）。读数 **1080/0/0**、mypy 116。**待办**：独立评审（进行中）→ 处置 DEC → commit + docs 交接 → **Phase 5 收口**（相位验收 `VAL-…34` 六组总体裁证 + 内容侧补课清单 + R1 读法口径 + metadata 三件 + 交接）
- **对象索引**（全 id 可直接 design_get；OPI 前缀：Phase 3 早期 `2babb21e-bc72-47a2-9382-e773c92211d2`、P3-1B 起及 Phase 4 全在 `5ba74efc-9f26-483b-a7de-c833834275a4`；旧系列 `eaaa5a1d-7ac7-4746-bcdf-c02bc9147492`）：
  - `DEC-…4d516e4f.29` **P4-4 处置 + PHASE 4 COMPLETE 收口**（五刀链+五验收+**遗留清单七项**：derive_reply 启发式/prompt 转义归 Phase 9/Episode status/双证口径/history 期望/零候选边界/服务端 warning）——Phase 5 续接先读
  - `DEC-…4d516e4f.22` P4-3 处置（其六项已由 P4-4 全兑现或转留痕）；`DEC-…4d516e4f.13` P4-2 处置；`DEC-…5ba74efc.115` P4-1 处置；`DEC-…5ba74efc.96` P4-0 处置；`DEC-…5ba74efc.68` **外部评审采纳（Phase 3 复核+P4-0 授权）**
  - `PLAN-…5ba74efc.82` Phase 4 母计划（p4-0..p4-4，**全毕**）；`VAL-…5ba74efc.70/.72/.80` 直盖 PASS；`VAL-…74/76` 路径集过窄 → 同题扩集 `VAL-…4d516e4f.7/.17` 代盖（取代关系见 `DEC-…4d516e4f.13/.22`）
  - P4 五对交付：`TASK-…5ba74efc.84/.100`+`VR-…91/.109`（P4-0/P4-1）；`TASK-…4d516e4f.9`+`VR-…12`（P4-2）；`TASK-…4d516e4f.19`+`VR-…21`（P4-3）；`TASK-…4d516e4f.26`+`VR-…28`（P4-4）
  - `DEC-…5ba74efc.65` **PHASE 3 COMPLETE 收口**（五刀链+遗留清单七项）
  - `DEC-…2babb21e.5` P3-1 开工基线；`DEC-…5ba74efc.43/.20`+`DEC-…2babb21e.34` P3-2/P3-1B/P3-1A 评审处置
  - `TASK-…5ba74efc.2/.24/.47`+`VR-…5ba74efc.13/.38/.57` P3-1B/P3-2/P3-3 任务书+盖章（PASS）
  - `VAL-…2babb21e.7/.9/.11/.13` P3 四验收（全 PASS）；`PLAN-…2babb21e.15` Phase 3 母计划；`TASK-…2babb21e.17`+`VR-…2babb21e.25` P3-1A 两件
  - `DEC-…eaaa5a1d.58` P3-0 评审处置；`DEC-…eaaa5a1d.51` 外部评审采纳（Phase 3 GO）；`DEC-…eaaa5a1d.48` PHASE 2 COMPLETE；`DEC-…eaaa5a1d.33` 拒收政策升格；`DEC-…eaaa5a1d.26` Phase 2 开工
  - `PLAN-…eaaa5a1d.19` Phase 2 PLAN；`VAL-…eaaa5a1d.17` 相位门；P2A/P2B 各系列 id 见旧交接（`git log` 可溯）
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
- **测试**：`python -m pytest`（当前 761/0/0）；静态：ruff + mypy（108 文件）；migrations 到 0010（schema_version 10）；GenerationAction 权威在 runtime（DM §16）；DecisionCycle 权威在 Runtime（`DEC-…2babb21e.5`）；TeachingMoment/Attempt 全链已实装（P3-1/2/3）；**Phase 4 全毕（P4-0..P4-4）**：Relationship durable core（P4-1）+CP4 projection runtime（P4-2，`elc.runtime.projections` SQL-free + `elc.platform.db.projection_store`）+Episode 投影与 DisclosedUserProfile 与 PromptCompiler 八节（P4-3）+E2E/压力验收（P4-4：`tests/phase4/test_p4_4_{full_chain,stress}.py`；F-1 缺陷修复=分类器读失败不再被洗成空成功）
- **规范优先级执行**（P4-0 教训留痕）：canonical 与既有实现漂移时**实现服从 canonical**（列名/词表逐字照原文；无决策裁定不得以「Phase 0 拼写」为由倒置）；本仓已有两例（0007 列集、P4-0 relationship 列名/枚举）——任务书四查加「列名/词表照 canonical 原文」必答项
- **门是意图不是障碍**（P4-2 教训留痕）：实现**不得为过架构门而变形**——P4-2 首轮执行者把 `ProjectionExecutor.execute` 以「取方法值再调用」（`run = executor.execute; run(view)`）绕开 Gate 2 的 `.execute(` 调用形态扫描，总控判返工改**正向命名** `project()`（Gate 2 把 `.execute()/.commit()/.rollback()` 词表留给 runtime 不得触碰的 DB 机件；改名后结构性护栏不变、独立 AST 扫描 0 违规）。同轮总控把执行者自报的边界「RUNNING 残骸本刀不回收」升格为本刀内做（RA §22 明文把 pending projections 列入恢复扫描）——**边界自报是诚实的，但「RA 明文要求」级缺口不因自报而免做**
- **VAL 路径集纪律**（P4-2 教训留痕）：验收的 `applicability_contract.paths` 必须覆盖实际触及路径——VAL-…74 漏 `src/elc/platform/db`（Gate 2 规定 runtime 无 SQL，Runtime 拥有的投影适配器只能落此）与 `src/elc/teaching`（对账需 refs 扫描面），P4-2 铸同题扩集 `VAL-OPI-4d516e4f.…7` 盖章并在 `DEC-…4d516e4f.13` 显式留痕取代关系（**不双重声明同一观察**）；P4-3 同例（VAL-…76 漏 runtime/migrations → `VAL-…4d516e4f.17`）
- **落盘通道三段纪律**（P4-3 教训留痕，第六次违规后升级）：①一切 `.py/.sql/.yml/.toml` **一律 Write/Edit 工具落盘**（Bash heredoc/`sed -i`/重定向/`ruff --fix` 等一律违规——`--fix` 属同族写操作）；②回执必附**「Bash 使用清单」**（逐条命令意图，非只读用途标红；同一刀内第二次违规=整刀拒收重交）；③**字节零差复写一律用 Edit 往返 + 四重验证**（H1==H2、`--no-filters` raw 相等、字节数/行数相等、分块 sha256 全等），**禁止**对超大文件（本仓 `runtime/controller.py` 195KB）做单次全量 Write 复写——该文件含历史 mojibake 字节（~3637 行），Read 显示与真实字节不一致，人工转录必带显示伪影
- **冷启动 import 闭环**（P4-3 教训留痕）：`elc.runtime.__init__` 聚合导出 + 域模块互相引用可造出「域模块 → runtime 包 → 新模块 → 域模块」的闭环，测试套件因导入顺序侥幸不报而 `import elc.conversation` 冷启动失败；解法＝本地窄 Protocol + `TYPE_CHECKING` 注解导入 + **subprocess 冷启动钉**（逐包 import）——凡新增跨包引用面必带冷启动钉
- **Mimosa 安全钩子**：Bash 直写源码/配置被拦——**.py/.sql/.yml/.toml 一律 Write/Edit 工具落盘**（P1B 执行者曾一次 Bash 直写 .py 未被钩子拦但违反明令，已在 `DEC-…d7937fd7.12` 训诫留痕——总控与执行者均不得再犯）；SQL 一律参数绑定或全字面量（标识符用白名单全字面量），禁任何拼接
- **基线冻结**：`behavioral_baselines/` 的 .py 一字节不改（例外须按 `DEC-…d5b616bf.3` 范式：显式决策+最小改动+manifest 重钉）；六 canonical 文档只许 `DECISION_REGISTER.md` 的版本条目
- **不做**（纪律）：未到位次的域逻辑/域表提前实现（位次见基线 §1.5：**Phase 4 全毕**；当前位次=**Phase 5（Curriculum + Content runtime integration）**，natural-conversation target-specific silent Evidence 是它的核心目标；其余域（Scheduler/Planner/Teaching 自动面）仍禁）；Redis/Kafka/分布式锁/TTL/heartbeat（Local V1 §24.1 永禁）；自动教学/Planner SELECT（Phase 8 才开）；`decision_cycle_id` 收紧已随 0007 兑现（`DEC-…091f35c3.7` 裁定 b 闭环）
- docs/run_post_bf_regression.py 的 ROOT 自相矛盾是原件冻结缺陷，永久不可修——repo-native 七套件是长期替代；勿再尝试修它
- Windows：core.autocrlf 与 blob 有字节差，哈希校验须 CRLF 归一；建议后续加 .gitattributes（勿扰动冻结文件行尾）

## 常用命令

```bash
python -m pytest          # 全量（含架构门与七套件行为基线）
ruff check . && mypy src  # 静态门
git push                  # CI 自动跑四门
```
