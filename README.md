# English Learning — Clean Rewrite (V1)

Canonical Implementation Baseline V1（2026-09-20）。规范优先级：`docs/` 六份 canonical 文档 > `behavioral_baselines/` 参考与回归资产 > 任何历史设计文档与旧实现（旧仓库 `D:\测试1` 整体作为 exploration archive 保留）。

- `docs/` — PRODUCT_CONTRACT / DOMAIN_MODEL / STATE_MACHINES / DATA_MODEL / RUNTIME_ARCHITECTURE / IMPLEMENTATION_PLAN + DECISION_REGISTER + ARCHITECTURE_BASELINE + 一致性报告（机器复核 60/60 PASS）
- `behavioral_baselines/` — BF-01～07（Estimator / Planner / Gate / Golden / Modality / Local Runtime / Security）：**实现合同，不是设计参考**；新仓库必须自动回归
- `src/` — 域模块（**Phase 0–10 已填充**：conversation / persona / learning（含 natural-chat silent evidence）/ teaching（含 Gate 的四个 profile 与 rollout 门槛检查器）/ runtime（含 recovery scan 面、delivery records、guarded stream、pre-delivery guard、exposure reconciliation）/ platform / relationship（含 Episode 投影）/ planner（kernel + 可审计 trace + 候选供给侧/scope/frontier/ledger + shadow mode 与冻结 43 例重放）/ deletion（BF-05 source-aware 删除与墓碑）/ user_config（§5.1 Goal·Policy·Focus 版本化 + §9 PlannerConstraint）/ scheduler（§5.2 ScheduleItem·ReviewEvent、spacing 纯策略 due/overdue、ScheduleView）/ curriculum（R0–R4 readiness + production TeachingTargetProvider）/ content（content.db 确定性构建与只读读面）/ world_lore；其余域按 IMPLEMENTATION_PLAN §1.5 位次待填）
- `tests/` — architecture / state-machine / determinism / property / failure-injection / golden（IMPLEMENTATION_PLAN §14）
- `migrations/` — app.db 迁移

第一条学习垂直切片现状（`DEC-OPI-5ba74efc-….65/.68`）：**Teaching-driven learning vertical slice COMPLETE**（explicit user TeachingMoment → target-specific Attempt Evidence → LearnerState，含 before≠after 可追溯与全链验收）；**natural-conversation target-specific silent Evidence 已随 Phase 5 交付、并经 P5-R 按 canonical 收窄**（自然 Persona 对话 → 确定性 target resolution：**仅 RESOURCE 目标、仅整句形式的 canonical/alternative 命中**才铸 target-specific Performance Evidence → Estimator → LearnerState；CAPABILITY 命中、仅 slot 命中、嵌入跨度/引用/转述/元语言一律**只记匹配观察、不产生证据**；无 TeachingMoment/Gate/Planner 介入，供给降级不阻聊天）。实现 PR 必须能指出自己遵循/修改哪一条 contract。

**实现现状（2026-09-26）**：**Phase 0–10 全部 COMPLETE（工程）** + **prep-1 落成**（真 provider 适配 + secret 缝 + 首个 composition root + 最小 CLI）+ **prep-1R**（provider egress 加固：禁重定向 / 明文 HTTP 策略 / 响应上限）+ **C1（Phase 11 内容程序第一段）**（readiness 证据面：13 张新表（content.db 11 → 24）+ `content_src/evidence/` 严格装载 + §8.1 十九键无一缺席（18 键逐表读 + `entity_row` 由前置 `get_resource` 成功证明存在）+ 钉搬迁 ⇒ 首个 target `res-colloc-make-a-decision` 真达 **R4_DETECTION_READY**；C1 处置：`content_db_version` bump "2"、reviewed 读法 = teaching_note 行 ∧ 实体 `CANONICAL_APPROVED`、credit 批准的活风险 `R-C1-credit` 入账）+ **C2-a（Phase 11 内容程序第二段）**（其余 8 个 res 各一份 evidence 文档 ⇒ 现役真产物上 **9×R4_DETECTION_READY + 5×None**；8 条 §24.7 link 由 C2-a 编辑评审批准，**credit 面 1 → 9 条**——行为变更已单列披露，活风险 `R-C1-credit` 的 Revisit 不变）+ **C2-b（Phase 11 内容程序第三段）**（19 个新 res 实体（entity + 19 键 evidence 全链 + 19 条 link）⇒ 现役真产物上 **28×R4_DETECTION_READY + 5×None**，`resource_count`（`res-*` 实体）= **28**，即 IP §13 的 28→100 calibration 起点**第一档达成**；19 条新 link 里 6 条是 REALIZES（**credit 面 9 → 15 条**，行为变更单列披露，Revisit 不变）、13 条是 SUPPORTS（**credit-safe**：credit 读面只认 REALIZES，已批准的 SUPPORTS 行满足 §8.1 R2 的 `curriculum_link` 事实而**不铸任何学习者证据**）；C2-b 结束时 Calibration100 三门（100/30/2）全未过）+ **C3-a（Phase 11 内容程序第四段，本刀）**（CORE_A/CORE_C 读法落地——**声明读法（用户 2026-09-26 裁决）**：CORE_A = level ∈ {R3_TEACHING_READY, R4_DETECTION_READY} ∧ `content_pedagogical_profile.core_utility = HIGH` 的 res 实体数、CORE_C = 同 level ∧ {MEDIUM, LOW}；三处旧钉（c2a/c2b/p8_5）从 `curriculum_capability.family` 计数改为分档读并逐处注明「声明读法 + Revisit」，`src/elc/teaching/rollout.py` 读数句仅注释更新（剥 docstring 后 AST 同一）；18 个新 res 实体（entity + 19 键 evidence + 18 条 link，其中 3 条 REALIZES、15 条 SUPPORTS）⇒ **51 实体 / 46×R4_DETECTION_READY + 5×None / `resource_count` 46 / credit 面 15 → 18**；**三门读数分开如实**：CORE_A **32/30 达到**、CORE_C **14/2 达到**、体量门 **46/100 未过**——真实 rollout 仍 HOLD）+ **C3-b（Phase 11 内容程序第五段，本刀）**（18 个新 res 实体（entity + 19 键 evidence + 18 条 link，其中 3 条 REALIZES、15 条 SUPPORTS）⇒ **69 实体 / 64×R4_DETECTION_READY + 5×None / `resource_count` 64 / credit 面 18 → 21**；**三门读数分开如实**：CORE_A **42/30 达到**、CORE_C **22/2 达到**、体量门 **64/100 未过**——真实 rollout 仍 HOLD；src 计数句同族扫全（6 文件 14 处 hunk，全部在 docstring/注释内；剥 docstring 后 AST 同一自证）；语义诚实面：本刀 3 条 REALIZES 逐条写明「未经能力语义审计」与其限度，其余 15 条 SUPPORTS 就近选位、**不铸任何学习者证据**） + **C3-R1（Phase 11 内容程序语义检查点，本刀）**（外评 HIGH-1 的根治：5 个 capability 各补**功能定义**（`functional_definition` 五键块，build 严格读）+ 64 条 §24.7 link 逐条重审定级 `mapping_class`（**16 CURRICULUM_MAPPING + 48 COVERAGE_PLACEMENT**，m+p=64；**6 条旧 REALIZES 降级 SUPPORTS** 逐条披露）+ §8.1 R2 的 `curriculum_link` 键改读「approved ∧ `CURRICULUM_MAPPING`」（src 行为改动：`build.py` link 装载面加列 + `CONTENT_DB_VERSION` "2"→"3" + `curriculum/store.py` 读面；planner 的节点解析读 REALIZES 不同改，取证见 `curriculum/README.md`）⇒ **真值诚实回落：R4 64 → 16**（16×R4 + 48×R1_LEXICALLY_RESOLVED + 5×None；**回落是裁决目的不是事故**——readiness 阶梯重新有区分度，纯词汇资源不再凭就近 SUPPORTS 过 R2）；credit 面 21 → 15（活风险 `R-C1-credit` 随之收窄）；四行内容门仍 GO（16 个 R4 target 满足每行"至少 1 个"）；**三门读数分开如实**：CORE_A **11/30 未达（回落）**、CORE_C **5/2 达到**、体量门 **64/100 未过**） + **C3-R2（Phase 11 内容程序语义检查点第二刀，本刀）**（外评 HIGH-2 的规格层修复（正例先行，用户裁决）+ provenance 维度落地：`DETECTION_FIXTURE_KINDS` 扩第三词 **`POSITIVE_ERROR`**（学习者错误产出、声明规则应触发、expected=MATCH），kind↔expected 配对由 tests 钉升格为 **build 源契约**（`DETECTION_FIXTURE_EXPECTED_BY_KIND`，错配 ⇒ BuildError，覆盖存量 255 行）；**每实体每 error_type ≥1 条正例**（build 结构校验拒收）⇒ fixtures 255 → **379**（**124 条正例** = 60 实体×2 错误型 + 4 单错误型实体各 1；既有行零改动、新行只 append）——恒 NO_MATCH 假 detector 从此过不了全集（恒 NO_MATCH 桩失败 ≥124 / 恒 MATCH 桩失败 255，存在性逻辑钉；**仍不声称 detector 已可执行**，N21 延续）；**provenance 四级结构派生**（`PROVENANCE_LEVELS`：AUTHOR_DECLARED / EDITOR_REVIEWED / EXECUTABLY_VERIFIED / EMPIRICALLY_CALIBRATED）——audits 载体 `content_src/audits/*.json` 目录扫描严格装载（缺席/空 = 全基线；仓内本刀不写真记录，处置刀按评审抽审落地），派生 = 有 evidence ⇒ AUTHOR_DECLARED ∧ 被审计记录批准 ⇒ EDITOR_REVIEWED，后两级**今日不可达**（无 detector 执行器 N21 / 无真实运行数据，Revisit 各随其条件）；content.db 新表 `content_provenance`（**24 → 25 表**，`CONTENT_DB_VERSION` "3"→"4"）+ store 读面 `provenance_levels()` 与 `positive_errors` 计数字段——**provenance 是独立维度不进 §8.1 阶梯**：readiness 真值（16×R4+48×R1+5×None）、三门（CORE_A 11 / CORE_C 5 / resource_count 64）、四行内容门 GO 全部逐值不变，零开闸声称） + **C3-c（Phase 11 内容程序第六段，本刀）**（新模板首跑：18 个新 res 实体（entity + 19 键 evidence + 18 条 link）⇒ **87 实体 / 34×R4_DETECTION_READY + 48×R1_LEXICALLY_RESOLVED + 5×None / `resource_count` 82 / credit 面 15 → 33**（18 条新 link 全为 REALIZES ∧ CURRICULUM_MAPPING——**逐条引用对应 capability functional_definition 的 counts_as / does_not_count 具体条目判定**，选题按五份功能定义的 counts_as 定向预写；行为变更单列披露，活风险 `R-C1-credit` 登记面 15 → 33、Revisit 不变）；fixtures 379 → **487**（18 实体 × 2 错误型 = 36 条新 POSITIVE_ERROR，既有行零改动）；provenance 结构派生自动生效（18 新实体全 AUTHOR_DECLARED，`content_src/audits/` 零改动、零新记录）；**LOW-2 收口**：`res-softener-if-anything` 的 detection_rules rule 2 第三例证补先行陈述句（唯一一处既有 evidence 行改动，其既有两条正例的覆盖不变）；**三门读数分开如实**：CORE_A **24/30 未达**、CORE_C **10/2 达到**、体量门 **82/100 未过**——真实 rollout 仍 HOLD；src 计数句同族扫全（4 文件 9 处，全在 docstring/注释内，剥 docstring 后 AST 同一自证）+ tests 侧真值钉/叙述句全扫随迁；零迁移、零开闸声称） + **C3-d（Phase 11 内容程序第七段，本刀）**（新模板末次批量：18 个新 res 实体（entity + 19 键 evidence + 18 条 link）⇒ **105 实体 / 52×R4_DETECTION_READY + 48×R1_LEXICALLY_RESOLVED + 5×None / `resource_count` 100 / credit 面 33 → 51**（18 条新 link 全为 REALIZES ∧ CURRICULUM_MAPPING，同 C3-c 的逐条引用功能定义判定纪律；行为变更单列披露，活风险 `R-C1-credit` 登记面 33 → 51、Revisit 不变）；fixtures 487 → **595**（18 实体 × 2 错误型 = 36 条新 POSITIVE_ERROR，既有行零改动；语境守卫四项 BOUNDARY 例真在边界）；provenance 结构派生自动生效（18 新实体全 AUTHOR_DECLARED，`content_src/audits/` 零改动、零新记录）；**三门读数分开如实——三门全达**：CORE_A **32/30 达到**、CORE_C **20/2 达到**、体量门 **100/100 达到（IP §13「28 → 100」第一档到顶）**——**三门达 ≠ 开闸（零开闸声称）**：stage 腿未声明、SessionBudget 三分未落地，真实 rollout 仍 HOLD；src 计数句同族扫全（6 文件，全在 docstring/注释内，剥 docstring 后 AST 同一自证）+ tests 侧真值钉/叙述句全扫随迁；**N-C3C-1 三键查重刀内首跑**（新 18 实体的 canonical/alt/slot 键对全语料 100 实体零碰撞，测试钉住）+ **LOW-1 时点限定收口**（两份 capability 文件的「no resource of the current corpus is of this shape」句改时点限定，判据词零改动、判据面 digest 与父提交一致）；零迁移、零开闸声称） + **D-1（Detector Executability Program 首刀，本刀）**（POSITIVE_ERROR **真 FK**：每条正例行**必带 `source_error_type`**——值 = 该实体 `typical_errors` 声明的 `error_type` 集之一（缺失/悬空 ⇒ `BuildError` 带合法集），NEG/BOUND 行出现该键 ⇒ `BuildError`；**逐型覆盖校验取代 C3-R2 行数代理**（每声明型 ≥1 条按名匹配的正例，未覆盖 ⇒ `BuildError` 列出未覆盖型；代理删除，N-C3R2-1/EXT-C3-01 收口）；**196 行存量迁移**（POS 行按 ordinal 升序与 declared error_type 按 ordinal 升序一一对应，逐对 pattern/text 人工核验；既有行其余三键与全部 NEG/BOUND 行零改动，c3-c/c3-d 的投影 digest 钉以四键投影复原冻结常量证明）+ `content_detection_fixture` 增可空列 `source_error_type`（正例非空/其余 NULL）+ `CONTENT_DB_VERSION` "4"→"5"（表集 25 不变）；readiness 真值 52×R4+48×R1+5×None、三门 32/20/100、provenance 54×A+46×E 逐值不变；**不声称 detector 已可执行**（EV 仍 0，N21 延续），零开闸声称）——Phase 8 = Planner→Gate→自动教学链 + rollout 门槛检查器；Phase 9 = Delivery / Exposure Hardening（含 P9-R 三件高/中危修复后重签 PASS）；**Phase 10 = Runtime Recovery**（五刀：scan 面补齐 / 25 类失败场景套件 A+B / 两个待裁题正式裁决 / D1 fence 修复 + F4 收口 + 相位级映射表）。**测试读数以 `AGENTS.md` 台账与 CI 为准**（本文件不再复制总数 / 逐目录 / mypy 文件数，避免漂移）；这里只留不随读数变的事实：迁移 head **`0018_delivery_records`（v18）**、`dependencies = []`（标准库 + SQLite）、**语料 capable 与 rollout HOLD 分开拄**——C3-d 后 rollout 门槛检查器对现役语料的四行内容门仍答 **GO**（BF-02 §10 每行"至少 1 个 target"被 **52 个** R4 target 满足——C3-R1 重审后的真映射集 + C3-c/C3-d 按功能定义判定的 36 条新映射），但 **真实 automatic-teaching rollout 仍 HOLD**：宿主未声明 rollout stage（`stage_allows_automatic(未声明) = False`，两腿合成式拒绝），Calibration100 体量门（IP §13 的 100/30/2，现读数 **100/100、32/30、20/2 三门全达**——105 实体中 **52 个 res 达 R4**（C3-R1 真值回落后的真映射集 + C3-c/C3-d 按定义判定的 36 条）、48 个 res 停 R1、5 个 cap 无 level；两门按**声明读法**读，Revisit 待 canonical 定义落地）**不再是 HOLD 的原因**，HOLD 由 stage 腿与开闸独立裁决扛着，开闸由 IP §12 的门槛检查与用户裁决决定。**IP §13 的「28 → 100 resource calibration」走到 100（第一档到顶）**——这是体量门的答案，不是开闸。具体交接与对象索引见 `AGENTS.md`。

## 最小 CLI（prep-1）：一个真进程里聊一句

`prep-1` 落成首个 composition root（`elc.host`：迁移 → 开本进程 `runtime_epoch` → 建真 store → `PersonaRuntime`（注入 provider）→ `ConversationCoordinator`，lease 已 adopt 该 epoch），CLI 在其上做最简 REPL。**只走进程内 Python API：不起 HTTP 服务、不监听端口**（客户端边界仍按 `DEC-…d7937fd7.12` 推迟）。

```bash
# BYOK（PRODUCT_CONTRACT §11）：OpenAI-compatible baseURL + key + model；key 本地保存
export OPENAI_API_KEY=sk-...     # 或 --secrets-file <仓外 JSON {"api-key": "sk-..."}>
PYTHONPATH=src python -m elc chat \
  --app-db ./app.db --base-url https://api.example.com/v1 --model gpt-4o-mini \
  --api-key-env OPENAI_API_KEY --conversation demo
```

- 启动即跑**一次** startup recovery（RA §22 / §24.1）：扫描并**报告**旧 epoch 残留；普通 turn 的判终/闭合面需 teaching·learning 端口，本装配未装（登记 N2）——**不声称 recovery 会收口教学残件**。随后每读一行 = 一条 `CommitUserTurn` → `coordinator.begin_turn`；`:quit` 或 EOF 退出并关连接。
- 密钥在 **send-time resolve**（RA §24.3）：只进 `Authorization` 头——不进 **PromptCompiler / durable GenerationAction / 普通日志 / portable export**（canonical 四词逐字）；`--api-key-env` 与 `--secrets-file` 互斥，密钥永不作为参数出现。provider 若在 **2xx** 回复里回显密钥，该回复按 `key-echo` **值**拒收（既不进 transcript 也不落 app.db；钉在 `tests/host/test_key_leak.py`）。
- provider egress 姿态（prep-1R）：**3xx 一律拒**（301/302/303/307/308 都不跟随 `Location`，值为 `http-302` 这类 `http-<status>`）且 `Authorization` 走 unredirected 头；**非 loopback 的明文 `http://` 默认拒**（值 `cleartext-http`；`localhost` / `127.0.0.0/8` / `::1` 免开关，其余须显式 `--allow-insecure-http`）；**单次响应上限 4 MiB**，超限为 `response-too-large`（不落任何字节）。
- 操作者卫生（不要求改代码）：`--secrets-file` 指向的仓外 JSON 由操作者自行设权限（本仓只读它，不检查 group/world 可读）；**错路径 / 错 `--secret-ref` 与「未设密钥」在 CLI 上是同一个 `missing-secret` 事实**（该缝所有失败都答 `None`）。
- 参数缺失 / 互斥 ⇒ 人话错误 + 退出码 **2**；app.db 打不开 ⇒ 退出码 **1**。**真实 automatic-teaching rollout 仍 HOLD**（开闸由 IP §12 的门槛检查与用户裁决决定，本 CLI 不改变它）。

### 语料 rollout 门（D-5）：`gate` 子命令

```bash
PYTHONPATH=src python -m elc gate --content-db ./build/content.db
```

- 只读 content.db（不需要 app.db / 密钥 / 网络）：打印四行门报告（每行的 usable 目标数与 verdict，`automatic CURRENT_USER_ERROR` 行含 provenance 腿的 blocked 计数）+ targets 行 + verdict；退出码 **GO=0 / HOLD=1**，可脚本化判读。
- 门报告是**内容腿的答案，不是开闸**：GO 也不开任何东西——HOLD/GO 之外的 rollout 归因（stage 腿未声明、SessionBudget 三分、独立开闸裁决）打印在报告之后。
- `--content-db` 缺省指仓内构建产物 `build/content.db`（`PYTHONPATH=src python -m elc.content.build` 生成——该口径带 D-3 的 12 实体 EV 集；库 API `build_content_db` 缺省零 EV，两种构建的门读数不同是**产物事实**）。

### 全链 chat 与 dogfood 观察（D-6-a，用户已明示同意 D-6）

```bash
PYTHONPATH=src python -m elc seed --app-db ./app.db --content-db ./build/content.db
PYTHONPATH=src python -m elc chat --app-db ./app.db \
  --base-url https://api.example.com/v1 --model gpt-4o-mini \
  --api-key-env OPENAI_API_KEY \
  --content-db ./build/content.db --rollout-stage Study-first
PYTHONPATH=src python -m elc observations --app-db ./app.db
```

- **dogfood 前对全新 app.db 跑一次 `seed`**：它经 host 自己的 controller 写入缺省教学策略（`pv-seed-v1`，BALANCED）+ 单一 SPEAKING 目标（`goal-seed-v1`）+ 每个可执行验证（EV）目标一行 §5.2 schedule 行——没有这三件，planner 生成零候选，自动教学永不触发。
- `seed` 幂等：所有写入都是 upsert（schedule 行按 target×modality 键重放），重跑安全；它不发任何网络请求（不需要 provider/model/key），也不声明 rollout stage——只铺配置，不开闸。
- `--content-db` 给 chat 装配**全链 tier**（自动教学腿 + 真检测器）；`--rollout-stage` 声明 §12 四词之一（缺省不声明 = fail-closed，零自动教学；非法词人话退出 2）。
- `observations` 是纯 SQL 读面：§12 六指标声明 + app.db 真实计数（gate_decision 按 decision×reason_codes，含 `TARGET_NOT_EXECUTABLY_VERIFIED` 漂移信号计数）+ D-3 matcher 已知假阳面清单——只打印，不写任何表。

### 本地 Web 面（W-1，用户已明示同意）：浏览器里的 Study-first dogfood

```bash
PYTHONPATH=src python -m elc web --app-db ./app.db \
  --base-url https://api.example.com/v1 --model gpt-4o-mini \
  --api-key-env OPENAI_API_KEY \
  --content-db ./build/content.db --rollout-stage Study-first \
  --port 8760
# 浏览器打开 http://127.0.0.1:8760
```

- 参数 = chat 全套 + `--port`（缺省 8760）；**只绑 127.0.0.1、无鉴权**——单用户单机 dogfood 面，不是服务，别暴露到本机之外。
- 页面：对话区（逐轮 POST `/api/turn`）+ 本轮教学时刻卡（按 turn 血缘查，非「最新行」；等待回应的时刻带**「回应」输入框**（POST `/api/teaching_reply` `{"control":"attempt","text":"…"}`，经 coordinator 既有回应入口进 §4 评估链判分，答对结课释锁、答错再给一次）与**「先搁着」按钮**（`{"control":"skip"}` 同入口释放时刻锁））+ 观察读数按钮（与 `observations` 命令同一读数核心，数字同源）+ 打开页面即拉最近 50 轮恢复对话。
- turn 级失败是**运行事实**（HTTP 200 + failure 字段）；只有坏请求体才是 400。

### 真实端点 smoke（可复制；dogfood 步骤，不属 CI）

```bash
PYTHONPATH=src python -m elc chat --app-db ./smoke.db \
  --base-url https://<real-endpoint>/v1 --model <model> \
  --api-key-env OPENAI_API_KEY
```

**CI 不发真实请求；本仓未验证与任何具体厂商/网关的互操作性**（属 dogfood 步骤）。
