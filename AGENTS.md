# AGENTS.md — english-learning-clean（Clean Rewrite · Implementation Baseline V1）

## 项目一句话

成人英语学习应用「英语客厅」的 **Clean Rewrite**：以 Implementation Baseline V1（用户主导的更高智力讨论收敛，2026-09-20 交回）为唯一规范权威，从零实现。**规范优先级：本仓 `docs/` 六 canonical 文档 > `behavioral_baselines/` 行为基线资产 > 其他一切**（旧仓 `D:\测试1` 整体为 exploration archive，其全部设计仅作历史参考）。实现栈已裁：**Python 内核 + SQLite**（app.db 可变 / content.db 只读 / SecretStore；客户端边界已裁 `DEC-…d7937fd7.12`：进程内 Python API，交互面推迟 Phase 8 末后）。

## 🔴 dmcp 段（新会话续接第一入口）

- **workspace_id**：`ws-7585bd9c-f6ec-4c73-be14-d2e635a37033`（**schema 5**；旧工作区 `ws-db58afd2-…` 已随旧仓归档，别用）
- **续接顺序**：①读本文件 → ②`design_status` 刷基 → ③`design_get` 三件：`DEC-OPI-4d516e4f-9575-4cbf-8d08-6bf19a95bd25.22`（**P4-3 处置+revisit**：P4-4 必带六项）＋`DEC-…5ba74efc.68`（**Phase 4 总设计权威**：P4-G1 门定义+五刀切法+P4-0 两 carryover+projection 语义要求——P4-4 仍要它）＋`PLAN-…5ba74efc.82`（Phase 4 母计划）→ ④`git log --oneline` → ⑤开工前读 `docs/IMPLEMENTATION_PLAN.md` §4（Phase 4 Detail Block）与 §1.5，再按派单协议铸下一刀任务书（四查+VAL+TASK 同铸；**四查必答：列名/词表照 canonical 原文；P4-4 任务书必带 DEC-…22 revisit 六项（stress+端到端验覆盖 P4-2 投影线与 P4-3 三面 / VAL 同题取代关系按同一口径 / 下次 submit 补 evidence_basis 族字段 / INFO-2 prompt 转义归 Phase 9 / INFO-4 Episode status 随会话关闭面 / controller.py ~3637 行 mojibake 单独小刀）+落盘通道自查清单+Bash 使用清单；**VAL 一律带实际触及路径集**）
- **执行者遗留处理先例**（发生过两次：P3-1A/P3-2 前均因 API 余额中断留下半成品）：开工前必查 git status——不干净时先取证（快照/差异分析），按「吸收+逐文件复核+修正+补齐+留痕」或「拒收重交」二选一，绝不静默覆盖
- **当前状态**（2026-09-21 第十会话末）：**Phase 4 进行中，P4-0+P4-1+P4-2+P4-3 COMPLETE**（rev 74；sync 见收口记录）——P4-0 `d8866b8`（`VR-…5ba74efc.91`）+P4-1 `2acaaca`（`VR-…5ba74efc.109`）+P4-2 `ffcafcf`（`VR-…4d516e4f.12`，处置 `DEC-…4d516e4f.13`）+P4-3 `6ef5ca1`（`VR-OPI-4d516e4f-…21` PASS，处置 `DEC-OPI-4d516e4f-…22`）。P4-3 三面全落：**Episode 投影**（`relationship/episode.py` §5.3 十列逐字+幂等/版本感知重建（版本 digest 无时钟）+`episode_store.py`；EPISODE 入 CP4＝第二投影类型，`ensure_projection_jobs` 多类型返回/`ensure_missing_jobs` per-(type,turn)/构造期执行器完备性 fail-fast/F-5 discard）+**DisclosedUserProfile**（`user_config/types` 按 §5.1 列集逐字改写 + `disclosure.py` 纯判定（高敏仅 persona-specific ∧ RICH，默认规则永不授权高敏）+`store.py` + 控制器毕业含显式同意门）+**PromptCompiler 消费**（节序 persona→profile→contract→history→relationship→episode→teaching→channel；三节版本键；byte-determinism；跨 persona 零泄漏双向）+`runtime/persona_views.py` 装配（可选端口，Err/异常→None 不阻 turn；HEAD 快照对跑证明缺省时 prompt 字节零变化）+migration 0010（episode/user_profile/disclosure_policy，v10）。评审链：独立评审 A–H 八面全 PASS+15 组自建探针（**639 条既有断言以 HEAD 快照双侧对跑证零放松**）；findings 1 MINOR+2 LOW+5 INFO 处置（LOW-1 user_id 护栏/LOW-2 构造期 fail-fast/INFO-1 常量互指+相等钉；INFO-2/INFO-4 DEFER）；通道违规两起自报（第六次 Bash heredoc→整文件 Write 重写返工；`ruff --fix` 一次→**Edit 往返字节零差复写**，总控裁定接受并锁定形式）+升级（回执强制 **Bash 使用清单**/同一刀二次违规即拒收/大文件禁单次全量 Write 复写）。测试读数 **734/0/0**、mypy 108 文件、migrations 0010/v10。**下一步 = P4-4**（stress+端到端验收，VAL-…5ba74efc.80；**铸书必带 DEC-…22 revisit 六项+两份清单**）→ Phase 4 收口
- **对象索引**（全 id 可直接 design_get；OPI 前缀：Phase 3 早期 `2babb21e-bc72-47a2-9382-e773c92211d2`、P3-1B 起及 Phase 4 全在 `5ba74efc-9f26-483b-a7de-c833834275a4`；旧系列 `eaaa5a1d-7ac7-4746-bcdf-c02bc9147492`）：
  - `DEC-…4d516e4f.22` **P4-3 处置+revisit**（P4-4 必带六项：stress+E2E 覆盖 P4-2/P4-3 面 / VAL 取代关系口径 / evidence_basis 族字段 / INFO-2 prompt 转义归 Phase 9 / INFO-4 Episode status / mojibake 小刀）——P4-4 续接先读
  - `DEC-…4d516e4f.13` P4-2 处置+revisit（其四项已由 P4-3 全兑现：EPISODE 扩集重审/F-5 discard/F1 规模面留痕/evidence_basis 字段待下次）
  - `DEC-…5ba74efc.115` P4-1 处置+待裁裁定（其 P4-2 必带三项已由 P4-2 全兑现）；`DEC-…5ba74efc.96` P4-0 处置；`DEC-…5ba74efc.68` **外部评审采纳（Phase 3 复核+P4-0 授权）**
  - `PLAN-…5ba74efc.82` Phase 4 母计划（p4-0..p4-4）；`VAL-…5ba74efc.70/.72/.74/.76/.80` 五验收（**VAL-…74/VAL-…76 路径集过窄未被单独提交**，其同题组分别并入 `VAL-OPI-4d516e4f.…7`/`VAL-OPI-4d516e4f.…17` 盖章——取代关系见 `DEC-…4d516e4f.13`/`DEC-…4d516e4f.22`）
  - `TASK-…5ba74efc.84/.100`+`VR-…5ba74efc.91/.109` P4-0/P4-1 两对（PASS）；`TASK-…4d516e4f.9`+`VR-…4d516e4f.12`+`VAL-…4d516e4f.7` P4-2 三件（PASS）；`TASK-…4d516e4f.19`+`VR-…4d516e4f.21`+`VAL-…4d516e4f.17` P4-3 三件（PASS）
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
- **测试**：`python -m pytest`（当前 734/0/0）；静态：ruff + mypy（108 文件）；migrations 到 0010（schema_version 10）；GenerationAction 权威在 runtime（DM §16）；DecisionCycle 权威在 Runtime（`DEC-…2babb21e.5`）；TeachingMoment/Attempt 全链已实装（P3-1/2/3）；Relationship durable core 已实装（P4-1）；CP4 projection runtime 已实装（P4-2：`elc.runtime.projections`（SQL-free，执行器协议方法名 `project()`）+`elc.platform.db.projection_store`）；**Episode 投影 + DisclosedUserProfile + PromptCompiler 三新节已实装（P4-3：`relationship/episode{,_store}.py`、`user_config/{disclosure,store}.py`（§5.1 列集逐字）、`persona` 节序 persona→profile→contract→history→relationship→episode→teaching→channel、`runtime/persona_views.py` 装配）**
- **规范优先级执行**（P4-0 教训留痕）：canonical 与既有实现漂移时**实现服从 canonical**（列名/词表逐字照原文；无决策裁定不得以「Phase 0 拼写」为由倒置）；本仓已有两例（0007 列集、P4-0 relationship 列名/枚举）——任务书四查加「列名/词表照 canonical 原文」必答项
- **门是意图不是障碍**（P4-2 教训留痕）：实现**不得为过架构门而变形**——P4-2 首轮执行者把 `ProjectionExecutor.execute` 以「取方法值再调用」（`run = executor.execute; run(view)`）绕开 Gate 2 的 `.execute(` 调用形态扫描，总控判返工改**正向命名** `project()`（Gate 2 把 `.execute()/.commit()/.rollback()` 词表留给 runtime 不得触碰的 DB 机件；改名后结构性护栏不变、独立 AST 扫描 0 违规）。同轮总控把执行者自报的边界「RUNNING 残骸本刀不回收」升格为本刀内做（RA §22 明文把 pending projections 列入恢复扫描）——**边界自报是诚实的，但「RA 明文要求」级缺口不因自报而免做**
- **VAL 路径集纪律**（P4-2 教训留痕）：验收的 `applicability_contract.paths` 必须覆盖实际触及路径——VAL-…74 漏 `src/elc/platform/db`（Gate 2 规定 runtime 无 SQL，Runtime 拥有的投影适配器只能落此）与 `src/elc/teaching`（对账需 refs 扫描面），P4-2 铸同题扩集 `VAL-OPI-4d516e4f.…7` 盖章并在 `DEC-…4d516e4f.13` 显式留痕取代关系（**不双重声明同一观察**）；P4-3 同例（VAL-…76 漏 runtime/migrations → `VAL-…4d516e4f.17`）
- **落盘通道三段纪律**（P4-3 教训留痕，第六次违规后升级）：①一切 `.py/.sql/.yml/.toml` **一律 Write/Edit 工具落盘**（Bash heredoc/`sed -i`/重定向/`ruff --fix` 等一律违规——`--fix` 属同族写操作）；②回执必附**「Bash 使用清单」**（逐条命令意图，非只读用途标红；同一刀内第二次违规=整刀拒收重交）；③**字节零差复写一律用 Edit 往返 + 四重验证**（H1==H2、`--no-filters` raw 相等、字节数/行数相等、分块 sha256 全等），**禁止**对超大文件（本仓 `runtime/controller.py` 195KB）做单次全量 Write 复写——该文件含历史 mojibake 字节（~3637 行），Read 显示与真实字节不一致，人工转录必带显示伪影
- **冷启动 import 闭环**（P4-3 教训留痕）：`elc.runtime.__init__` 聚合导出 + 域模块互相引用可造出「域模块 → runtime 包 → 新模块 → 域模块」的闭环，测试套件因导入顺序侥幸不报而 `import elc.conversation` 冷启动失败；解法＝本地窄 Protocol + `TYPE_CHECKING` 注解导入 + **subprocess 冷启动钉**（逐包 import）——凡新增跨包引用面必带冷启动钉
- **Mimosa 安全钩子**：Bash 直写源码/配置被拦——**.py/.sql/.yml/.toml 一律 Write/Edit 工具落盘**（P1B 执行者曾一次 Bash 直写 .py 未被钩子拦但违反明令，已在 `DEC-…d7937fd7.12` 训诫留痕——总控与执行者均不得再犯）；SQL 一律参数绑定或全字面量（标识符用白名单全字面量），禁任何拼接
- **基线冻结**：`behavioral_baselines/` 的 .py 一字节不改（例外须按 `DEC-…d5b616bf.3` 范式：显式决策+最小改动+manifest 重钉）；六 canonical 文档只许 `DECISION_REGISTER.md` 的版本条目
- **不做**（纪律）：未到位次的域逻辑/域表提前实现（位次见基线 §1.5：Phase 4=Relationship+Episode projection 进行中（P4-0 契约/P4-1 Relationship/P4-2 CP4 投影运行时/P4-3 Episode+披露+prompt 消费均已落地；**剩 P4-4 stress+端到端验收**）；natural-conversation silent Evidence 留 Phase 5；其余域仍禁）；Redis/Kafka/分布式锁/TTL/heartbeat（Local V1 §24.1 永禁）；自动教学/Planner SELECT（Phase 8 才开）；`decision_cycle_id` 收紧已随 0007 兑现（`DEC-…091f35c3.7` 裁定 b 闭环）
- docs/run_post_bf_regression.py 的 ROOT 自相矛盾是原件冻结缺陷，永久不可修——repo-native 七套件是长期替代；勿再尝试修它
- Windows：core.autocrlf 与 blob 有字节差，哈希校验须 CRLF 归一；建议后续加 .gitattributes（勿扰动冻结文件行尾）

## 常用命令

```bash
python -m pytest          # 全量（含架构门与七套件行为基线）
ruff check . && mypy src  # 静态门
git push                  # CI 自动跑四门
```
