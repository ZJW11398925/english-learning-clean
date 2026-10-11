# AGENTS.md — english-learning-clean（Clean Rewrite · Implementation Baseline V1）

## 项目一句话

成人英语学习应用「英语客厅」的 **Clean Rewrite**：以 Implementation Baseline V1（用户主导的更高智力讨论收敛，2026-09-20 交回）为唯一规范权威，从零实现。**规范优先级：本仓 `docs/` 六 canonical 文档 > `behavioral_baselines/` 行为基线资产 > 其他一切**（旧仓 `D:\测试1` 整体为 exploration archive，其全部设计仅作历史参考）。实现栈已裁：**Python 内核 + SQLite**（app.db 可变 / content.db 只读 / SecretStore；客户端边界已裁 `DEC-…d7937fd7.12`：进程内 Python API，交互面推迟 Phase 8 末后）。

## 🔴 基准纪律（用户明令，2026-10-11——任何计划从同一套设计修改完善，不是一套又一套新东西）

**任何计划必须从同一套设计/方案里修改完善，而不是另起新计划。** 发现问题的正确姿势是「在开发方案 xx 位置定义并规划了如何处理该问题——不够全面就完善该方案」，不是现场编一套新的。这是整个项目的基准，后续所有总控必须遵守。

**执行含义**：
1. **先查方案**：察觉问题后，第一件事是查总设计（living-world-spec / cognition-and-narrative-quality / IMPLEMENTATION_PLAN）有没有定义该问题的处理面——有则引用其位置并完善，没有则**补写进方案**（修改完善同一套设计），然后按补后的方案开工。
2. **禁止另起炉灶**：不得绕过总设计现场编新计划。任何刀的开工裁决必须引用总设计的具体章节作为依据；若总设计没有该面，开工裁决的第一条裁决必须是「把该面补写进总设计的 xx 章节」。
3. **总设计的修改也是交付**：补写总设计本身是刀的一部分（docs/ 改动与 src/ 改动同刀提交），不是「先写代码再补文档」。
4. **总控失职判例**：C 程序七刀（C1-a..C4）全部围绕「世界自转」深化，没有一刀问「用户在世界里的面」——正典 §3.2 写了「角色是世界内的演员」但用户从未被列为演员，总控读了两份正典全文七刀裁决都没停下来问。这是设计理解的失败：把「世界是第一公民」读成了「世界是唯一公民」。教训：**每刀开工前问「这一刀的用户面是什么」**。

## 🔴 dmcp 段（新会话续接第一入口）

- **workspace_id**：`ws-7585bd9c-f6ec-4c73-be14-d2e635a37033`（**schema 5**；旧工作区 `ws-db58afd2-…` 已随旧仓归档，别用）
- **续接顺序**：①读本文件 → ②`design_status` 刷基 → ③`design_get` 最新收口 DEC（**D-4/`DEC-OPI-a4cf2d0e-…71`** → D-2/`…69` → C4/`…27` → AOCI/`…36` → C3/`…15`；更早的 Phase 5–10 历史链全文在 `docs/sessions/session-handoffs-archive.md` 与 git 历史） → ④`git log --oneline -5` → ⑤按下一动读文档（**D 程序六刀全毕；下一动 = 用户浏览器验收 + dogfood 观察窗；真实 rollout 仍 HOLD**——SessionBudget 三分与内容补课为开闸前置）

## 🔴 第三十七会话终末换总控交接块（2026-10-11——下会话从这里接）

- **用户明令（原话）**：「本对话上下文太长，我要换一个新总控对话，请你确保可以凭DMCP等接续项目，并维持后续AOCI-CODE的合理利用。新总控务必先完全理解整个设计再布置执行任务」。
- **接续就绪三件**：①DMCP `ws-7585bd9c-…`（schema 5）**READY / SYNCED / rev 755**；②代码 tip `dd18cd9`（**已 push 远端，本地=远端 0 ahead**）；③本块即交接件。
- **本对话全貌（第三十一~三十七会话，rev 723→755）**：**C3 声音库包 v6**（六角色双语语样 + persona-voice 框块 + 认知视图；`DEC-OPI-a4cf2d0e-…6/12/15`）→ **C4 工艺护栏**（三铁律+八条负例无条件注入；金针双铸；`…18/24/27`）→ **AOCI 随迁小刀**（六条目+余项 9 面一次扫清；漂移永钉族；`…30/34/36`）→ **D 程序六刀（用户 dogfood 报告驱动）**：总设计补写 `ea2ba64`（living-world-spec §3.2 v2.2 用户角色 + cognition 域一 v1.2 用户层 + IP §19）→ **D-1 用户角色入世界**（包 v7 user_character/叙事者面/participants 扩词/认知视图第四臂；`…38/40/44/47`）→ **D-3 世界详情屏**（ensemble/storylines 两端点+五区屏；`…49/53/55`）→ **D-2 叙事密度与重量**（常量 2/3×0/3+§4.3 重量句+§4.4 后果句；金针第五铸；`…57/61/69`）→ **D-4 显示层级统一**（世界是框架/世界指示器/沓=世界里的人/世界架入坞——§7 IA 翻转完整落地；`…63/65/67/71`）。另：**AGENTS.md 瘦身**（581→196 行，历史交接块归档 `docs/sessions/`）+ **CI 触发纪律**（push 照常、push/PR 不自动跑 CI〔workflow_dispatch 手动〕、六情形硬清单、红线③「禁止把 CI 当门用」）+ **基准纪律入册**（任何计划从同一套设计修改完善，不另起炉灶——用户明令）。
- **本对话 DEC 链（新总控必读，design_get 逐读）**：上列全链 + `…71`（D-4 收口——含两臂设计裁定/三 MEDIUM 处置/N-D4-1..4 登记）。
- **下一动（已定谳）**：**用户浏览器验收 + dogfood 观察窗**——①四缺口已全毕（D-1/D-2/D-3/D-4），用户重启 web 验收（启动：`build→seed→web` 三命令加浏览，见 README；验收点=世界指示器/navdock 四项/沓世界里的人/世界面五区）；②dogfood 观察窗：**密度效力**（2/3×0/3 是否压没琐屑纹理、world_failed 频次）+ **D-4 统一体感** + **C3/C4 效力**（声音/文风）。**下一批候选**（用户裁）：**多世界 v1**（P17 学习桥硬门**先行**〔主角扩容/多世界前须跑通纵向切片〕；补 N-D4-1 多卡入口/N-D4-4 世界架多格）/ **外评第七轮**（C+D 程序整体）/ **JS 运行时测试基建**（N-D4-2，前端控制流变异边界）。
- **AOCI 接续指引（用户明令「维持合理利用」）**：①台账 `aoci.code.txt` **本对话每刀随迁已同步**（C3/C4/AOCI/D-1/D-2/D-3/D-4 的面全在——条目按「节区+文件名」定位，tag 非全局唯一〔防坑⑯〕）；②漂移永钉族在 `tests/world/test_aoci_drift.py`（六条目关键词+一致性+迁移覆盖律+八成员+无孤立 CR——**新刀触碰任一被钉面即跑**）；③**机制事实**：工作树 CRLF / blob LF（`.gitattributes eol=lf` 归一，git status 不可见）；④新刀若有新表/新迁移/新模块 ⇒ **刀内随迁**（迁移覆盖律会抓）；⑤AOCI 维护语义=改「现在时为假的断言」、历史归属句保留（prep-0 判例）。
- **防坑增量（本对话入册）**：⑪验收探测先记分支/git worktree（detached HEAD 教训）⑫通道违规记录标哈希类型 ⑬never_says 一致性含语义族 ⑭中文译写术语仓内自证词义 ⑮「byte for byte the pre-X」句族有扫全钉 ⑯台账 tag 非全局唯一 ⑰取证区分文件字节与终端渲染（GBK 控制台误读教训）⑱不 amend、改错追加 ⑲通道违规记录两更正（终态≠快照/命令形保真）⑳密集小刀期工作树并发（add 按文件）㉑前端负控钉按形态不按裸串。
- **新总控「先完全理解设计」指引（用户明令第三件——布置任何执行任务**前**必做）**：①本文件全读（特别：基准纪律区、dmcp 段、CI 触发纪律、工程事实与红线）；②`docs/design/` 两份正典全文（`2026-10-05-living-world-spec.md` v2.1/v2.2〔§3.2 用户角色款/§7 信息架构——IA 翻转/§4 运转引擎/§9 供给〕+ `2026-10-08-cognition-and-narrative-quality.md` v1.1/v1.2〔域一认知/域二剧情线/域三声音库/域四工艺〕）；③`docs/IMPLEMENTATION_PLAN.md` §19（用户角色工程含义）+ §13 附近（内容程序）；④DMCP design_get 本对话 DEC 链；⑤现役代码现场精读（web/ui 五文件+world/persona 域）。**理解标准 = 能回答**：世界怎么转（发条/run/停点）、用户在世界里是谁（§3.2 v2.2）、教学怎么藏（三根天线）、四个程序（C/D 与更早 P 系列）各自要解决什么、哪些 HOLD（rollout/SessionBudget/内容）。

（历史：p8-4 = COMPLETE（第十八会话）——七面全部落地；交付 `08dda87`（含处置），评审 ACCEPT-WITH-FINDINGS 无 HIGH/MEDIUM，读数 2929/0/0；详见「当前状态」p8-4 块与 ⑲）**p8-3（台账落表 + 删除面 + ReviewEvent 语义）= COMPLETE**（交付 `ff769e9`+`280adc1` + 处置 `ddbfd90`，盖 `VR-OPI-6d40862d-…15` PASS 于 `ddbfd90`；三件 = `TASK-OPI-6d40862d-…9` / `VAL-OPI-6d40862d-…11` / 处置 `DEC-OPI-6d40862d-…13`）；**p8-2 = COMPLETE**（交付 `14041d0` + 处置 `2f0b8e3`，盖 `VR-OPI-6d40862d-…7` PASS）；**p8-1 = COMPLETE**（交付 `b43d4bc` + 处置 `325e7a6`，盖 `VR-OPI-64c88704-…23` PASS）；**p8-0 = COMPLETE**（交付 `42d1b16` + 处置 `0479cbf`，盖 `VR-OPI-64c88704-…13` PASS）；**Phase 8 = 开工第 0 步已完成**（`DEC-OPI-0f76024b-…3` / `PLAN-…5` / `VAL-…7`）；四查必答面见 ⑩ 的五项 + 迁移面预写 + ⑭/⑯/⑰/⑱；**p8-4 的四查面（供参考）**：`RUNTIME_ARCHITECTURE.md` §4 步 11–20（prompt/Provider/Validator/Guard/Delivery/CP3a/terminalization/CP4）+ §6 CP3a 与 §13/§14/§15（delivery 与曝光语义）+ §22/§23（恢复与崩溃窗口的 Moment 半）+ `DATA_MODEL §22`（Delivery Data）/§15（TeachingMoment 的 lifecycle 与 delivery 转移）+ `IMPLEMENTATION_PLAN §9`（§7.2 自动路径）与 §12（rollout）+ p8-3 的 `teaching_presented` 事件面（`elc/planner/ledger_store.py` 的写面 + `planning_ledger_event` 五词）与 `ConversationPriorityView` 的生产者（RA §4 步 3））：**Phase 8** 读 `docs/IMPLEMENTATION_PLAN.md` §9（及 §12）/`docs/RUNTIME_ARCHITECTURE.md` §CP2 与 10A–10B 与崩溃窗口/`docs/DATA_MODEL.md` §14·§14.1·§15·§18/`docs/DOMAIN_MODEL.md` §13·§14/`docs/STATE_MACHINES.md` 的 Teaching 与 Gate 转移面/`behavioral_baselines/gate/*`（BF-03 v1.1 + 60 例 benchmark + 参考实现 + 决策表）。**Phase 7** 读 `docs/DOMAIN_MODEL.md` §10/§10.1/§11/§12/§13、`docs/DATA_MODEL.md` §14/§24.14、`docs/IMPLEMENTATION_PLAN.md` §8 与 `behavioral_baselines/planner/*`（BF-02 §5 的 `feature_assembly_status`/`snapshot_status`/missing_authorities 与 DEFERRED 路径）。派单协议同下：四查+VAL+TASK 同铸；**四查必答：列名/词表/判据照 canonical 原文逐字；本刀若新增迁移，stamp 钉搬迁必须预先写明**（p6-1 16 处 / p6-3 22 处的判决性实验先例；自 p6-3 起 head/stamp 值集中在 `tests/conftest.py` 常量，边际成本已降）；读数口径按 `DEC-…a68fd9eb.32`；内容补课未落地前不得假设任何 target readiness ≥ R2；禁 `_seed()`/fixture 供给；**VAL 一律带实际触及路径集**）
- **执行者遗留处理先例**（已发生三次：P3-1A/P3-2/P4-4 前均因 API 余额中断留下半成品）：开工前必查 git status——不干净时先取证（快照/sha256/差异分析），按「吸收+逐文件复核+修正+补齐+留痕」或「拒收重交」二选一，绝不静默覆盖；**P4-4 先例**：遗留半成品 3 条失败被判测试侧，评审以 as-found 原件复跑逐条复核成立
- **当前状态**（2026-10-11；rev 755；**D 程序六刀全毕（D-1/D-3/D-2/D-4）——用户四缺口交付面 + 「50→90 分」显示层级统一全落**；读数基线 **5864/0/0**，master tip `9b85102`）：
  - **Phase 9/10 = COMPLETE**；**真实 rollout 仍 HOLD**（SessionBudget 三分 + 内容补课为开闸前置）；
  - **C 程序全毕**（C1-a/b/c、C1.5、C2、C3、C4 + AOCI 随迁）；
  - **D 程序（用户 dogfood 报告驱动）**：总设计补写 `ea2ba64` + **D-1 用户角色入世界**（`5fc65ec`+`2c52002`；收口 `DEC-OPI-a4cf2d0e-…47`）+ **D-3 世界详情屏**（`56d9aaf`+`80dc7bc`；收口 `…55`）+ **D-2 叙事密度与重量**（`182accd`+`91a85df`；常量 2/3×0/3+§4.3 重量句+§4.4 后果句；收口 `…69`）+ **D-4 显示层级统一 = COMPLETE**（交付 `5d9bc2c`+处置 `9b85102`；**世界是框架/世界指示器/沓=世界里的人/世界架入坞**——§7 IA 翻转完整落地；评审 13 变异+真浏览器无 HIGH，两臂设计裁定成立，三 MEDIUM 两修一裁；收口 `DEC-OPI-a4cf2d0e-…71`；登记 N-D4-1 多卡入口归多世界刀/N-D4-2 前端 JS 控制流变异边界/N-D4-3 绑定随会话/N-D4-4 单世界架）；
  - **下一动 = 用户浏览器验收 + dogfood 观察窗**（密度效力：琐屑纹理/失败率；显示层级统一体感；D-4 后世界屏经 navdock「世界」项或主从条世界名进入）**＋ push 已随刀**（D-4 全部提交已推远端，CI 零触发）；**下一批候选**（用户裁）：多世界 v1（P17 学习桥硬门先行；补 N-D4-1 多卡入口）/ 外评第七轮 / JS 运行时测试基建（N-D4-2）；
  - **现役先读**（新会话续接）：①`design_status` 刷基 ②`design_get` 最新收口 DEC（`DEC-OPI-a4cf2d0e-…71`）③`git log --oneline -5` ④本文件基准纪律区+CI 触发纪律 ⑤按下一动读 docs/design/ + docs/IMPLEMENTATION_PLAN.md §19；
  - **台账面**：P1/P4/P7/P15/P17 未触发；P3 已销账；P6 起步腿已兑现；**用户 dogfood 报告四缺口全毕**：①用户零存在→D-1 ②密度碎→D-2 ③前端卡逻辑→D-3+D-4 ④六角色不可见→D-3；**用户评价「50 分→90 分」= D-4 的直接驱动（已落地）**；
  - **防坑区**（跨会话生效，最新在最上）：㉑**前端负控钉按形态不按裸串**（`if (name === "world")` 裸串负控会误伤回调层的合法分叉——让位律钉 `… navdock.hidden = true;` 同行形态）⑳密集小刀期工作树并发（add 按文件）⑲通道违规记录两更正 ⑯台账 tag 非全局唯一 ⑰取证区分文件字节与终端渲染 ⑱不 amend、改错追加 ⑮「byte for byte the pre-X」句族有扫全钉 ⑪验收探测先记分支/git worktree ⑫通道违规记录标哈希类型 ⑬never_says 一致性含语义族 ⑭中文译写术语仓内自证词义；
  - **历史交接块**：归档在 `docs/sessions/session-handoffs-archive.md`（第三十至三十三会话 + 更早）；

## 会话交接索引（详细块归档在 docs/sessions/session-handoffs-archive.md）

- 第三十四/三十五/三十六会话（2026-10-11）：**总设计补写 + D-1 用户角色 + D-3 世界详情 + D-2 密度重量 + D-4 显示层级统一**——详见「当前状态」块；DEC 链：`…40/44/47`（D-1）、`…49/53/55`（D-3）、`…57/61/69`（D-2）、`…63/65/67`（D-4）
- 第三十三会话交接块
- 第三十二会话交接块
- 第三十一会话交接块
- 第三十会话终末交接块
- 第二十九会话交接块
- 第二十八会话终末交接块
- 第二十七会话·总账
- 第二十七会话·wr-7 主链留档
- 第二十七会话·wr-7 主链留档
- 第二十七会话·wr-7 主链留档
- 第二十七会话·wr-7 主链留档
- 第二十七会话·wr-7 主链留档
- 第二十七会话·wr-7 主链留档
- 第二十七会话·wr-7 主链留档
- 第二十六会话终末交接块
- 第二十六会话终末交接块
- 第二十五会话终末
- 第二十五会话

## dmcp 工作流协议（v2，2026-09-20 用户纠正后立——总控必守）

每刀（task）完整链：**四查+VAL+TASK 同铸 → 派执行者 → 总控独立复核（pytest/ruff/mypy/CI 亲跑）→ 独立评审（新上下文 executor-pro 只读评审，产 findings）→ 处置（修/DEFER/留痕）→ validation_submit 盖章（在最终验证过的提交上）→ design_sync REBUILD+CHECK 收口**。缺评审即违约（本仓 2026-09-20 已犯一次，用户点名纠正）。**顺序修正（2026-09-22 p6-2/p6-3 实测）**：原书写「复核 → 盖章 → 评审 → 处置」在实践中不可执行——VR 必须盖在**最终验证过的提交**上，而「处置」按定义会再改一次代码（p6-1/p6-2/p6-3 的 VR 实际都盖在处置修后的提交上）⇒ 自本行起以「处置 → 盖章」为书序（盖章仍是验收要件，只是位次挪到最终态）；因此「盖章后不得再改该切片代码」成为新硬约束。**迁移刀的成本（p6-1/p6-3 实测）**：新增一个迁移会使**所有** head/stamp/applied 钉变假（0012 断 16 个测试、0013 断 22 个），任务书必须**逐条预写**搬迁名单；自 p6-3 起这些值集中在 `tests/conftest.py` 的 `MIGRATION_IDS`/`SCHEMA_HEAD_FILE`/`SCHEMA_HEAD_VERSION`（改一处 + 该刀自己的迁移测试），并有一条自证钉校验常量 == 真实仓库。

- **纪律 ①（⟳ 刷基）**：连续两次 dmcp 变更之间必须 design_status 纯读刷新基再填 expected——REVISION_CONFLICT 即忘了刷基（错误面会给 current id 可直接重构）
- **Phase 开工第 0 步**：`plan_build` 铸 PLAN（VERTICAL_SLICE/RISK_SPIKE/VALIDATION_EXPERIMENT/ENABLER 工作项+relations）；任务从 plan 工作项展开。**readiness 更正（2026-09-20 第四会话查实）**：design_readiness 的 gate 行来自 gate policy 而非 plan_build——默认策略是 FINDING-only 单族行集（每条 finding 一行 BLOCKING），finding 册恒空 ⇒ 恒 READINESS_BASIS_INCOMPLETE；解锁要么服务端接线 preparer 让 findings 真实入册，要么宿主侧配 `DMCP_READINESS_POLICY_FILE`（宿主操作，不代执行）。**阶段门禁当前由本仓工作流承担**（VAL+独立评审+decision），readiness 仅作解锁后的复核面
- **评审面构建局限（当前服务端，已铁证）**：REVIEW_REQUIREMENT/REVIEW_PACKET 只能由宿主侧 preparer 铸，而 dist 无任何入口接线 `createHostReviewBasisPreparer`（D:\MCP apps/mcp-server，查实 0 wiring）→ review_submit 恒 OBJECT_NOT_FOUND、finding 册因构造恒空（finding_list=0 是构建事实不是「无问题」）。**降级路径**：评审照做（独立上下文评审员），findings 全文+证据+裁定入 decision（范式见 `DEC-…d7937fd7.19`/`DEC-…eaaa5a1d.9`），服务端升级接线后补录正式 finding 并迁移裁定
- **主体/能力（当前服务端 env）**：HUMAN_USER + DESIGN_STATE_READ/MUTATE 两族——FINDING_ADJUDICATION/DISPOSITION 族未授，裁决面即使有 finding 也会被诚实拒绝；升级服务端配置属宿主侧操作，skill 不代执行
- 契约=跨会话记忆：GOAL/RUNTIME/IN_SCOPE/OUT_OF_SCOPE/TECHNICAL_CONSTRAINTS/ASSUMPTIONS 在载体 `DEC-…9dc4e77f.4`（含六 canonical 文件 digest 绑定，漂移即假设失效；AGENTS.md 活文档不绑）；契约改写是整体替换（⑲），改前先 design_get 读回

## 派单协议（用户明令，2026-09-20）

- **执行者 = `executor-flash`（一般任务）/ `executor-pro`（难题）**——用户安装在 `~/.zcode/agents/`（model 钉 GLM-5.3-Flash / GLM-5.3，**须带 `thoughtLevel: max` 键**——2026-09-20 补，缺则新 harness 拒启，见 `DEC-…091f35c3.13`）。**禁止用内置 `general-purpose` 做执行任务**。
- 总控不亲自执行（写代码/测试/探针/部署一律派执行者，先 `task_build` 铸任务书）；设计类任务书先过 grilling 前沿；**任务书四查 + VAL 与任务书同铸**（前沿/实现设计条目/计划时效/预算算术；交付后补盖 VAL 视同无效验收）。红线全文 0–31 见旧仓 `D:\测试1\AGENTS.md`（红线 28/29/30/31 尤其要读）。

## 工程事实与红线（本仓特有）

- **前端治理（`DEC-OPI-631452f9-bd11-4b69-8fb6-df16f825fca6.37`，F-G1 起）**：前端改动必须经组件库（`src/elc/webui/`）与 `docs/FRONTEND_SPEC.md`；库中已有组件禁止重复实现（评审 finding + 拒收事由）；新组件须同刀登记 spec（组件契约条目 + 任务书四查写明）；**库随产品增长**（用户裁决 2026-09-28：活注册表——先查库、已有复用、无则新建并同刀登记 spec 表 + COMPONENTS 元组）。
- **远程**：github.com/ZJW11398925/english-learning-clean（public）；**CI 四门**：ruff → mypy → compileall → pytest（Ubuntu，0 skipped 为准）。**CI 触发纪律（用户明令 2026-10-11：「不要老是触发 CI，损耗太多 action 额度；**不是不 push，而是 push 跳过 CI**」）**：①**push 照常做**——代码同步/备份是硬要求，远端必须跟手（按交付节点批量推即可，不逐刀推）；②**push 与 PR 都不自动跑 CI**——`ci.yml` 已改为 `workflow_dispatch` 手动触发；本仓全流程本地验证（总控亲跑全量+四门）为硬门，CI 是按需手动的备用复核面；③**禁止再把 CI 当门用**——验收/交接一律引用本地亲跑读数。
  **「必须跑 CI」硬清单（手动触发，仅此六情形）**：
  1. **CI 配置自身变更后**（改 `ci.yml`/安装步骤/依赖）——验证配置有效（本次已跑：run 38127998426）；
  2. **相位收口 / 程序收官 / 外评轮启动前 / 换总控交接前**——远端绿标作交接面（每相位一次量级）；
  3. **跨平台风险刀**——改动涉及行尾（CRLF/LF）、文件系统行为、路径大小写、编码的刀完成后（本地 Windows 过了≠Linux 过）；
  4. **依赖面变化**——`pyproject.toml`/安装流程/导入拓扑（跨包引用、冷启动面）变更后；
  5. **长期累积兜底**——距上次绿标 ≥ 一个相位时，在下个节点补跑一次；
  6. **用户明示要求**时。
  **不必跑**（默认不跑）：单刀日常交付（本地硬门已覆盖）、纯 docs/台账/内容数据提交。**跑法**：`gh workflow run ci.yml`；结果回执入当刀/当会话台账（run id + 结论）。**红则当刀处理**（不阻塞已收口刀的本地验收，但修复优先）。
- **测试**：`python -m pytest`（当前 **2787/0/0**，0 skipped；**非 phase6/7 不含 deletion = 1581**；`tests/phase8` = **422**；`tests/phase3` = **280**；`tests/phase7` = **420**；`tests/deletion` = **120**；phase6 = 666；**collect 须写 `-o addopts=""` 才会打印总数**）；静态：ruff + mypy（**144** 文件 0 error）；migrations 到 **0016**（schema_version **16**；0011 = p6-0 三表、0012 = p6-1 的 `schedule_item`/`review_event`、0013 = p6-3 的 `planner_constraint`、0014 = 门二的 `deletion_tombstone`、0015 = p8-0 的 §14 四表 `planner_evaluation`/`planner_decision`/`planner_execution_status`/`runtime_decision_outcome`、**0016 = p8-3 的台账三表 `planning_ledger`/`coverage_obligation`/`planning_ledger_event`**；p8-1/p8-2 零迁移；**p6-2 零迁移**；head/stamp 值集中在 `tests/conftest.py` 的 `MIGRATION_IDS`/`SCHEMA_HEAD_FILE`/`SCHEMA_HEAD_VERSION`；新增迁移会使同族钉变假，搬迁面须**预先写明**——门二实测 **27 处**（25 实改 + 2 核过））；GenerationAction 权威在 runtime（DM §16）；DecisionCycle 权威在 Runtime（`DEC-…2babb21e.5`）；TeachingMoment/Attempt 全链已实装（P3-1/2/3）；**Phase 4 全毕（P4-0..P4-4）**：Relationship durable core（P4-1）+CP4 projection runtime（P4-2，`elc.runtime.projections` SQL-free + `elc.platform.db.projection_store`）+Episode 投影与 DisclosedUserProfile 与 PromptCompiler 八节（P4-3）+E2E/压力验收（P4-4：`tests/phase4/test_p4_4_{full_chain,stress}.py`；F-1 缺陷修复=分类器读失败不再被洗成空成功）；**Phase 5 COMPLETE（P5-0/P5-1/p5-2 + P5-R 语义重签已毕）**：`content_src/`+`curriculum/` 资产（14 validated target，P3 fixture 原件零改动）+ `elc/content`（确定性构建 content.db 2c617a95…bde96 / 只读读面写全拒）+ `elc/curriculum`（readiness R0–R4 + production `ContentBackedTeachingTargetProvider`）+ `elc/learning`（抽取式 target resolution + silent evidence 链，无 TeachingMoment/Gate/Planner）；`tests/phase5/` 327 新用例，全零 `_seed()` 真链路；**Phase 6 COMPLETE（四刀全毕 + 相位收口已毕，收口 `DEC-OPI-b99560d4-…10`；盖 `VR-OPI-b99560d4-…8` PASS 于 `97b0dc7`）**：`elc/user_config`（§5.1 Goal/Policy/Focus + 版本/append-first 纪律 + keying convention；§9 `PlannerConstraint` + 两 StrEnum + 5 面）与 `elc/scheduler`（§5.2 `ScheduleItem`/`ReviewEvent` 逐字 + `SqliteSchedulerStore` 当前投影/append-first/CONFLICT/epoch fence + `spacing.py` 纯策略 due 四步派生 + `recompute_schedule_item`/`get_schedule_view(as_of)`/`is_review_due` 三法 + 内容寻址 version）+ registry 换代；**门二 COMPLETE（BF-05 source-aware 删除与墓碑，独立一刀）**：`src/elc/deletion/`（七文件：scope 词表 / 删除计划 / store / controller / commands / queries / `__init__`）+ `migrations/0014_deletion_tombstone.sql`（v14）+ `tests/deletion/` **120 例** + **27 处既有迁移钉搬迁**；独立评审 ACCEPT-WITH-FINDINGS 无 HIGH、处置修 `4ce43ed`、盖 **`VR-OPI-b99560d4-…28` PASS**、sync SYNCED 117；**PHASE 7 COMPLETE（Planner shadow mode + Planner Behavioral Baseline V1）：四切片 p7-0..p7-4 全毕 + 相位验收 `VR-OPI-44647873-…38` PASS 于 `5395694` + 收口 `DEC-OPI-44647873-…39`；下一动 = Phase 8 开工第 0 步**：p7-1 kernel+trace（`f79a36d`+处置 `d876ed5`）+ p7-2 候选供给侧（`4c6afb7`+`40ffa5c`+处置 `53b330e`）+ p7-3 frontier+ledger+coverage（`821b247`+处置 `51a9868`+收口 `b7b29f3`）+ **p7-4 shadow mode + 冻结 43 例重放（`f66cc2d`+处置 `5e33d0d`；`src/elc/planner/{shadow,stress_suite}.py`；43/43 且与冻结参考实现逐例一致；**零迁移**）**
- **规范优先级执行**（P4-0 教训留痕）：canonical 与既有实现漂移时**实现服从 canonical**（列名/词表逐字照原文；无决策裁定不得以「Phase 0 拼写」为由倒置）；本仓已有两例（0007 列集、P4-0 relationship 列名/枚举）——任务书四查加「列名/词表照 canonical 原文」必答项
- **门是意图不是障碍**（P4-2 教训留痕）：实现**不得为过架构门而变形**——P4-2 首轮执行者把 `ProjectionExecutor.execute` 以「取方法值再调用」（`run = executor.execute; run(view)`）绕开 Gate 2 的 `.execute(` 调用形态扫描，总控判返工改**正向命名** `project()`（Gate 2 把 `.execute()/.commit()/.rollback()` 词表留给 runtime 不得触碰的 DB 机件；改名后结构性护栏不变、独立 AST 扫描 0 违规）。同轮总控把执行者自报的边界「RUNNING 残骸本刀不回收」升格为本刀内做（RA §22 明文把 pending projections 列入恢复扫描）——**边界自报是诚实的，但「RA 明文要求」级缺口不因自报而免做**
- **VAL 路径集纪律**（P4-2 教训留痕）：验收的 `applicability_contract.paths` 必须覆盖实际触及路径——VAL-…74 漏 `src/elc/platform/db`（Gate 2 规定 runtime 无 SQL，Runtime 拥有的投影适配器只能落此）与 `src/elc/teaching`（对账需 refs 扫描面），P4-2 铸同题扩集 `VAL-OPI-4d516e4f.…7` 盖章并在 `DEC-…4d516e4f.13` 显式留痕取代关系（**不双重声明同一观察**）；P4-3 同例（VAL-…76 漏 runtime/migrations → `VAL-…4d516e4f.17`）
- **落盘通道三段纪律**（P4-3 教训留痕，第六次违规后升级；**p6-2 追加第四段**）：①一切 `.py/.sql/.yml/.toml` **一律 Write/Edit 工具落盘**（Bash heredoc/`sed -i`/重定向/`ruff --fix` 等一律违规——`--fix` 属同族写操作）；②回执必附**「Bash 使用清单」**（逐条命令意图，非只读用途标红；同一刀内第二次违规=整刀拒收重交）；③**字节零差复写一律用 Edit 往返 + 四重验证**（H1==H2、`--no-filters` raw 相等、字节数/行数相等、分块 sha256 全等），**禁止**对超大文件（本仓 `runtime/controller.py` 195KB）做单次全量 Write 复写——该文件含历史 mojibake 字节（~3637 行），Read 显示与真实字节不一致，人工转录必带显示伪影；④**仓内零写入（含临时/诊断文件）**——「同一条命令内创建并随后删除」**不构成豁免**（红线约束的是钩子与审计面而非持久性，见 `DEC-…5a0be06d.…9`）；需要诊断脚本一律落仓外临时目录。**p8-1 追加第五段（口径收紧）**：**变异/诊断脚本（含 `.py`）一律 Write/Edit 工具落盘——仓外副本也一样**（处置刀曾以 `printf >> <仓外副本>.py` 追加变异，虽仓内零痕仍计一次违规）；Bash 只许只读命令、`git add/commit` 与不在禁列的构建命令（`pytest`/`ruff check`（无 `--fix`）/`mypy`/`compileall`）；**同一刀第 1 次＝训诫留痕、第二次＝整刀拒收重交**（p8-1 切片两刀各 1 次、均训诫留痕；本切片内第三次违规一律整刀拒收）
- **冷启动 import 闭环**（P4-3 教训留痕）：`elc.runtime.__init__` 聚合导出 + 域模块互相引用可造出「域模块 → runtime 包 → 新模块 → 域模块」的闭环，测试套件因导入顺序侥幸不报而 `import elc.conversation` 冷启动失败；解法＝本地窄 Protocol + `TYPE_CHECKING` 注解导入 + **subprocess 冷启动钉**（逐包 import）——凡新增跨包引用面必带冷启动钉
- **Mimosa 安全钩子**：Bash 直写源码/配置被拦——**.py/.sql/.yml/.toml 一律 Write/Edit 工具落盘**（P1B 执行者曾一次 Bash 直写 .py 未被钩子拦但违反明令，已在 `DEC-…d7937fd7.12` 训诫留痕——总控与执行者均不得再犯）；SQL 一律参数绑定或全字面量（标识符用白名单全字面量），禁任何拼接
- **基线冻结**：`behavioral_baselines/` 的 .py 一字节不改（例外须按 `DEC-…d5b616bf.3` 范式：显式决策+最小改动+manifest 重钉）；六 canonical 文档只许 `DECISION_REGISTER.md` 的版本条目
- **不做**（纪律）：未到位次的域逻辑/域表提前实现（位次见基线 §1.5：**Phase 5 工程 + 语义均已 COMPLETE（P5-R 已毕并重签）**；当前位次 = **Phase 8（Teaching Gate + 自动教学面）**——**p8-0/p8-1/p8-2/p8-3 均已 COMPLETE、p8-4（同 turn 集成 + exposure 生产者 + 崩溃窗口 Moment 半）可以开**；**真实 automatic-teaching rollout 本体仍 HOLD**（语料 14/14 `readiness=None` ⇒ R2/R3/R4 可用目标 0；BF-02 §10 逐字门槛——**不是 Planner 的问题**））；Redis/Kafka/分布式锁/TTL/heartbeat（Local V1 §24.1 永禁）；自动教学/Planner SELECT（Phase 8 才开）；`decision_cycle_id` 收紧已随 0007 兑现（`DEC-…091f35c3.7` 裁定 b 闭环）
- docs/run_post_bf_regression.py 的 ROOT 自相矛盾是原件冻结缺陷，永久不可修——repo-native 七套件是长期替代；勿再尝试修它
- Windows：core.autocrlf 与 blob 有字节差，哈希校验须 CRLF 归一；建议后续加 .gitattributes（勿扰动冻结文件行尾）

## 常用命令

```bash
python -m pytest          # 全量（含架构门与七套件行为基线）
ruff check . && mypy src  # 静态门
git push                  # CI 自动跑四门
```

<!-- aoci:begin -->
## AOCI 仓库认知

AOCI 为本仓库维护一个稳定、可版本化、可增量更新的仓库级认知层，供模型跨任务复用对系统的理解。

`aoci.txt` 是面向模型的结构化认知索引。它以每个受管理文件、数据库表或其他受管理对象一条独立 Entry 的方式，用符号标签与 F/R/A/S 语义表达对象的核心职责、重要关系、对外契约，以及理解或修改系统时必须知道的非显然约束和设计决策。

Header、目录段和全部 Entry 共同组成完整仓库索引，可以覆盖前端、后端、配置、数据库结构及其他受管理内容。受管理内容发生变化时，通常只需维护受影响的认知条目，不需要重新生成整个索引。

AOCI 提供系统架构、对象职责、重要关系、对外契约和关键约束的高密度视图。

### 工作原理

AOCI 采用“模型生成、模型读取”的认知闭环。

Header、Entry 和 Curation 语义的创作只按当前机器签发的 Plan 与实时 Guide 执行；由 Host 模型基于当前绑定证据独立完成。

Entry 的语义必须来自模型对真实证据的理解。不得仅依据路径、文件名、扩展名、AST、符号列表、依赖扫描、正则、固定模板或规则引擎推导、预填、拼接或改写索引语义。

对 Fresh Bootstrap，只按当前机器签发的 Plan 和实时 Guide 执行。当它们要求创作时，Host 模型创作 Root、Meta、Tag 和 F/R/A/S，提供 authoring-run 声明，并把它绑定到 Plan、Evidence 与完整 Candidate。不得要求 AOCI 填写 `origin=host_model`、制造 Receipt 或把程序生成的 Framework 当作语义。本文件不自行重建 Onboarding 流程。内部批次不是用户决策；只有遇到既有批准边界或真实的安全、漂移、CAS、Recovery 条件才停止。

### 最小使用入口

- `aoci_rules`：取得当前AOCI版本的会话运行合同。
- `aoci_overview`：建立或恢复本仓库的完整认知。
- `aoci_maintain`：受管理对象达到最终稳定状态后检查认知是否需要维护。
- `aoci_update_entry`：提交与当前证据和源码摘要绑定的完整语义更新批次。
- `aoci_report`：仅当当前布局和工具状态支持时，在证据不足、无法可靠生成语义时登记待办，不猜写。

其他MCP工具、CLI命令、参数和专项流程，以当前工具说明、Guide和 `--help` 返回内容为准，不在本文件中重复完整手册。

本区块只规定仓库接入、认知使用和收尾原则。`aoci_rules` 承载当前会话合同，Guide实时输出承载当前Plan的执行顺序与停点，工具Schema、Spec和Validator承载机器结构与判据；Prompt、Description、README和静态文档不能覆盖这些机器事实。

### 建立、生成和恢复认知

1. 每个新的 Agent Run 开始时，应先判断：

   - 本仓库是否已经存在可用的完整AOCI索引；
   - 当前上下文中是否已有与本仓库根、当前索引版本和当前AOCI服务相匹配，并且模型仍可可靠使用的完整仓库认知。

2. 仓库已经存在可用的完整索引，但当前Run没有可靠完整认知时，先调用 `aoci_rules`，再调用 `aoci_overview`。

   完整认知仍可靠时直接复用。局部不确定本身不要求机械重读系统全貌。

   本Run从已知Host上下文压缩恢复时（包括宿主注入的压缩摘要），必须把此前模型认知视为不可靠。压缩handoff不得保留或摘要正式Whole-Index，也不得保留或摘要任何Overview Header、Entry、Chunk、Challenge或Attestation正文；只能保留安全续接所需的receipt身份、未完成write或Recovery状态，以及立即重载指令。复制进handoff的Whole-Index语义或receipt不能证明恢复后模型的当前认知可靠。若当前上下文已无法可靠保留运行合同，先调用 `aoci_rules`。继续业务任务前，使用 `refresh_reasons=["context_compaction"]` 和新的 `refresh_event_id` 调用普通完整Whole-Index `aoci_overview`（不设置 `check_only` 或设为false）；不得使用 `check_only` 或认知probe。原样跟随每个 `next_cursor` 直到 `completed=true`，确认交付，并且只基于新交付正文提交一次Attestation。完成这次新的完整传输后，即使Attestation为partial或fail也消费该generation，并按既有合同继续source-bound任务，不再自动调用第二次Overview。

   AOCI可以针对 `context_compaction`、项目 `cognition_refresh_threshold` 下的机器 `semantic_threshold` 或主要 `phase_transition` 提供checkpoint与认知状态事实。只需要这些紧凑事实时使用 `check_only=true`；这些事实只向Agent提供建议，不替模型决定是否需要系统全貌。

   Agent显式调用普通 `aoci_overview`（未设置 `check_only` 或为false）时，只要能形成一致的CognitionSet，AOCI必须完整交付请求scope。不得因为已有receipt、阈值未达到或没有待处理刷新原因而抑制正文。正式认知Dirty或Stale时仍交付正文，但必须标记不可靠。存在未决恢复或无法形成一致snapshot时失败关闭，不返回混合正文。

   普通Overview返回 `continuation_required=true` 时，必须原样提交 `next_cursor` 并自动继续到 `completed=true`。不得询问用户、开始业务任务或给出阶段性系统结论。Host截断、缺块、重复、乱序、cursor失败、Index变化或`chunk_tokens`变化时停止本次认知链。Attestation完成前不得用Memory、源码、Spec、`aoci.txt`、历史会话、scope、search或Entry读取修补或补充Whole-Index认知。Challenge ordinal是正式Entry序列中的1-based位置；Header内容、注释、空行、Section/Overview/Chunk Marker、Receipt与Metadata均不计数，Chunk Receipt ordinal使用同一序列。Attestation必须原样回绑本次Challenge发布的当前`index_sha256`、`entry_sequence_sha256`与`entry_count`；旧Index、旧Entry序列、旧数量或旧Attestation均无效。完整链结束后只正式提交一次既有模型认知Attestation；同一响应只允许一次不改变语义答案的JSON Schema或字段格式修正。对象、Tag或F不匹配即失败且认知吸收不确定，不得语义重试或旁路补答。首次认知失败时还不得执行Root/Meta、Migration、全局布局或其他未重新绑定的系统级决策。上下文压缩刷新若传输完整、认知身份不变、治理对齐且没有Recovery或第三方冲突，即使Attestation为partial或fail也消耗该refresh generation，并继续原任务，不再自动重读Overview。`system_mastery_percent`只自评系统框架——架构、职责、强关系、稳定外部契约以及高熵安全和维护约束——不表示完整实现或运行实况知识；机器索引覆盖率必须分开。默认只向用户输出由本次真实覆盖率、Challenge、块数、Token和掌握度生成的规定成功或失败一句话。Host截断时提示用户把 `overview_delivery.chunk_tokens` 设置为更小的合法值后重新开始，不得自动修改。

   加法认知等级必须与严格证明字段分开解释。`delivery_verified`表示已加载Index且Host交付已确认，但完整认知验证仍未完成；应表达为“已加载且交付已验证”，不得描述为“没有认知”或“没有理解系统”。`cognition_verified`要求Attestation通过（Challenge至少80%的ordinal完全正确且对象身份至多失手一处），`cognition_governed`还要求治理对齐。通用完整读取失败句只用于真实交付故障。

   当Overview响应包含可选`cognition-state/v2`投影时，必须分别解释各维度。其Level止于`model_cognition_usable`；`strict_attestation_verified`、`governance_aligned`与`current_system_cognition_reliable`都是独立状态，绝不参与该Level。ordinal、对象身份、Tag或核心F不匹配可以导致严格Attestation失败，而模型认知仍然可用；不得仅凭这种不匹配就宣称模型没有理解系统。只有`current_system_cognition_reliable=true`允许无保留地声称当前完整系统认知可靠。投影缺失时继续使用上述Legacy解释。

   普通的只读审计、分析、检查、不修改代码或不提交、不push，不自动等于严格零写入，也不改变上述认知有效性判断。Codex Memory和历史Skill只能辅助恢复经验、用户偏好与调查方向，不能替代与当前仓库根、索引摘要、AOCI服务身份和认知范围匹配的当前认知收据；项目AGENTS和当前AOCI身份在AOCI状态上优先于历史Memory。

   只有用户明确禁止Ledger、元数据、`.aoci`运行资产及任何文件写入时，才按严格零写入处理。若必要的认知建立与该边界冲突，必须报告冲突并请求用户裁决或建议使用隔离副本，不得静默以Memory替代当前仓库认知。

3. 仓库没有可用的完整索引，或当前只有最小骨架、Header不完整、Entries未完成、必要Curation尚未裁决时，如果需要建立正式完整AOCI索引，先取得 `aoci_rules`，然后进入当前AOCI Guide。由Guide依据仓库真实状态决定下一阶段并完成必要安全步骤。

   `aoci_maintain` 不替代索引建立流程。

   不在本文件中自行重建或硬编码完整索引生成状态机。

4. 在长程任务中，模型负责保留当前认知收据并正确使用刷新门禁：

   - Host报告上下文压缩或模型已知系统全貌丢失时，执行上述强制 `context_compaction` 重载规则；AOCI不能自行推断Host事件；
   - 进入真正的主要阶段时声明 `phase_transition`，不得把函数、测试运行或小步骤当作阶段；
   - 在有用的稳定检查点通过 `check_only=true` 取得机器语义计数；
   - 除已知压缩的强制重载外，由Agent判断当前任务是否需要再次显式获取指定scope或完整Overview；
   - 在维护和对齐完成前，保留AOCI报告的Dirty或Stale可靠性状态。

### 任务收尾与认知维护

5. 纯只读问答、分析、版本核验，或没有产生受AOCI管理对象变化的任务，不需要调用维护工具。当前AOCI版本是任意`aoci_overview` check_only或`aoci_maintain`响应里的`cognition_receipt.mcp_service_version`；二进制路径是项目`.mcp.json`里的`command`，CLI不必在PATH上。

6. 发生受AOCI管理对象变化时，待其达到本次任务的最终稳定状态后，只调用一次 `aoci_maintain`。不要在每次中间修改后逐文件维护。

7. 若维护结果返回真实语义候选，Host 模型必须基于每个候选绑定的对象和必要证据，独立创作完整标签与F/R/A/S更新。通过 `aoci_update_entry` 一次提交当前机器签发批次的完整候选集合，同时原样保留每项 `source_sha256`、`candidate_id` 与对应domain批次身份。`max_entries`只限制单次请求和原子事务，不限制logical plan、Whole-Index或Managed Scope。`remaining`非零时，在当前批次成功Apply后重新调用Maintain并从新preimage继续；绝不能为满足transport上限缩减Index覆盖或自行截取返回批次。

   没有足够证据且当前布局支持 `aoci_report` 时，使用它而不猜测、套用模板或为消除待办而生成缺乏证据的认知。

8. 必须遵守工具返回的结构化状态和安全边界：

   - `repair_required`：只修复明确命中的候选，再重新提交当前机器签发的完整批次；
   - `stopped`：结束当前写入尝试并检查 `failed_step`、错误、正式写入证据与Recovery。auto模式下，已证明零写入则记录closure并重新Plan；完整Intent和可证明postimage则Resume；策略要求Rollback且preimage可证明则精确恢复后重新Plan。只有证据不足、第三方正式字节冲突、需要审批或外部动作，或命中其他真实安全边界时，才停止整个用户任务；
   - 冲突、审批、人工裁决、权限和安全信号不得忽略；
   - 已经对齐后不得重复维护或重复写入；`refresh_ready_for_overview` 是checkpoint事实，由Agent决定是否为下一阶段请求普通完整Overview。

   维护完成后如果又修改了任何受管理对象，之前的维护结果失效，应在新的最终稳定状态重新完成收尾。

9. 用户只限制业务文件范围，但没有明确禁止仓库托管资产时，AOCI托管资产可以在收尾阶段为保持认知一致而更新，并应在审计和提交中与业务文件区分。

   用户明确禁止修改 `aoci.txt`、`.aoci`、元数据或任何额外文件时，以用户限制为准，不得写入，并如实报告剩余不一致。

### 专项流程

初始化、完整索引生成、Header生成、Entries生成、数据库结构索引、Curation、人工评审和故障恢复，只按当前AOCI Guide或工具在对应阶段返回的指令、命令和安全停点执行。

不预加载、不猜测，也不自行重建这些专项流程。平台调用方式、请求格式、批次上限、审批规则、索引格式细节和恢复步骤由对应Guide、工具说明、模型Prompt和CLI帮助按需提供。
<!-- aoci:end -->
