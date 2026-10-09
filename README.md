# English Learning — Clean Rewrite (V1)

Canonical Implementation Baseline V1（2026-09-20）。规范优先级：`docs/` 六份 canonical 文档 > `behavioral_baselines/` 参考与回归资产 > 任何历史设计文档与旧实现（旧仓库 `D:\测试1` 整体作为 exploration archive 保留）。

- `docs/` — PRODUCT_CONTRACT / DOMAIN_MODEL / STATE_MACHINES / DATA_MODEL / RUNTIME_ARCHITECTURE / IMPLEMENTATION_PLAN + DECISION_REGISTER + ARCHITECTURE_BASELINE + 一致性报告（机器复核 60/60 PASS）
- `behavioral_baselines/` — BF-01～07（Estimator / Planner / Gate / Golden / Modality / Local Runtime / Security）：**实现合同，不是设计参考**；新仓库必须自动回归
- `src/` — 域模块（**Phase 0–10 已填充**：conversation / persona / learning（含 natural-chat silent evidence）/ teaching（含 Gate 的四个 profile 与 rollout 门槛检查器）/ runtime（含 recovery scan 面、delivery records、guarded stream、pre-delivery guard、exposure reconciliation）/ platform / relationship（含 Episode 投影）/ planner（kernel + 可审计 trace + 候选供给侧/scope/frontier/ledger + shadow mode 与冻结 43 例重放）/ deletion（BF-05 source-aware 删除与墓碑）/ user_config（§5.1 Goal·Policy·Focus 版本化 + §9 PlannerConstraint）/ scheduler（§5.2 ScheduleItem·ReviewEvent、spacing 纯策略 due/overdue、ScheduleView）/ curriculum（R0–R4 readiness + production TeachingTargetProvider）/ content（content.db 确定性构建与只读读面）/ world_lore（世界静态知识）/ detection（registry/runner/pilot——EXECUTABLY_VERIFIED 检测的执行层）/ world（活世界运行时：package/store/narrator/engine 生成式叙事）/ host.py（composition root）/ cli.py（chat/gate/seed/observations/web 五子命令）/ web.py + webui/（本地 dogfood 单页）/ lexicon（离线小词典——词卡第二档））
- `tests/` — architecture / state-machine / determinism / property / failure-injection / golden（IMPLEMENTATION_PLAN §14）
- `migrations/` — app.db 迁移

第一条学习垂直切片现状（`DEC-OPI-5ba74efc-….65/.68`）：**Teaching-driven learning vertical slice COMPLETE**（explicit user TeachingMoment → target-specific Attempt Evidence → LearnerState，含 before≠after 可追溯与全链验收）；**natural-conversation target-specific silent Evidence 已随 Phase 5 交付、并经 P5-R 按 canonical 收窄**（自然 Persona 对话 → 确定性 target resolution：**仅 RESOURCE 目标、仅整句形式的 canonical/alternative 命中**才铸 target-specific Performance Evidence → Estimator → LearnerState；CAPABILITY 命中、仅 slot 命中、嵌入跨度/引用/转述/元语言一律**只记匹配观察、不产生证据**；无 TeachingMoment/Gate/Planner 介入，供给降级不阻聊天）。实现 PR 必须能指出自己遵循/修改哪一条 contract。

**实现现状（2026-10-09）**：**Phase 0–10 全部 COMPLETE（工程）**（Phase 8 = Planner→Gate→自动教学链 + rollout 门槛检查器；Phase 9 = Delivery/Exposure Hardening（P9-R 三件修复后 FINAL SECURITY/SEMANTIC ACCEPTANCE 重签 PASS）；Phase 10 = Runtime Recovery 五刀：scan 面补齐 / 25 类失败场景套件 / 两个待裁题正式裁决 / D1 fence 修复 + 相位级映射表）+ **prep-1**（真 provider 适配 + secret 缝 + 首个 composition root + 最小 CLI）+ **prep-1R**（provider egress 加固：3xx 一律拒 / 明文非本机 HTTP 策略 / 响应上限 4 MiB）+ **Phase 11 内容程序**（**C1** readiness 证据面（content.db 11 → 24 表 + `content_src/evidence/` 严格装载 + §8.1 十九键全真读）→ **C2-a/C2-b**（28 个 res 实体，`resource_count` 28 = IP §13「28 → 100」第一档起点）→ **C3-a/b**（CORE_A/CORE_C 分档声明读法落地——用户裁决：CORE_A = R3+ ∧ core_utility=HIGH、CORE_C = R3+ ∧ {MEDIUM,LOW}，Revisit 待 canonical 定义）→ **C3-R1**（5 份 capability 功能定义 + 64 条 link 逐条 mapping_class 重审定级：16 CURRICULUM_MAPPING + 48 COVERAGE_PLACEMENT——R4 真值诚实回落、readiness 阶梯重新有区分度）→ **C3-R2**（POSITIVE_ERROR 正例全量 + provenance 四级结构派生 + audits 严格装载）→ **c3-c/c3-d**（**Calibration100 三门全达：CORE_A 32/30、CORE_C 20/2、resource_count 100/100——IP §13 第一档到顶；三门达 ≠ 开闸**）→ **队列②**（3 个词法 capability 节点 + 48 个 R1 逐实体筛选判定：41 前进 R4 / 7 留 R1 ⇒ 现役真值 **108 实体 / 93×R4 + 7×R1 + 8×None**）→ **队列③**（30 个核心表达各补 4 个真实语境分化变体句 + `/api/word` usage_variants 读面）→ **队列④**（官方角色扩充））+ **Detector Executability Program（D-1..D-6）**（D-1 POSITIVE_ERROR 真 FK + 逐型覆盖取代行数代理 → D-2 检测骨架（registry/runner/build 内嵌 EV 派生）→ D-3 试点 matcher 真跑三词 fixtures（**EXECUTABLY_VERIFIED 0→12**，后扩容至 36）→ D-4 硬门接线（automatic CURRENT_USER_ERROR 需 **R4 ∧ EXECUTABLY_VERIFIED** 第五腿）→ D-5 完整 production composition root + D-5R pre-dogfood 安全收口（预算 fail-closed + 逐 target EV 资格 + verification profile）→ D-6-a online CURRENT_USER_ERROR 生产者 → **D-6-b 用户真实 dogfood 进行中**）+ **W 系列 dogfood 面**（W-1 本地 web 面 → seed 冷启动铺路 → W-1R/W-2/W-3/W-4/W-6 教学闭环（触发→作答→判分→结课/再答→跳过→冷却→再触发全部可用）→ veto-R（mode 页面可改）→ 主线-1 设置真面 / 主线-2 调度历史纵深 → provider 面与多模型配置档 → 启动系统刀（端点/模型/密钥页面可设、保存热生效）→ F/r1/rd/mc/v2/ux 前端工艺、多角色与全屏重铸系列）+ **活世界程序（wr-0..wr-12 + lr-1..lr-4a，见下段）** + **外评第六轮（2026-10-09）采纳：产品方向 PASS 9.0、单世界主线可 dogfood、综合 8.1**。**测试读数以 `AGENTS.md` 台账与 CI 为准**（本文件不再复制总数 / 逐目录 / mypy 文件数，避免漂移）；这里只留不随读数变的事实：app.db 迁移 head **`0027_chronicle_attribution`（v27）**、`CONTENT_DB_VERSION = "6"`、`dependencies = []`（标准库 + SQLite）、**语料 capable 与 rollout HOLD 分开拄**——rollout 门槛检查器对现役语料的四行内容门仍答 **GO**（BF-02 §10 每行「至少 1 个 target」被 **93 个** R4 target 满足），但**真实 automatic-teaching rollout 仍 HOLD**：宿主未声明 rollout stage（`stage_allows_automatic(未声明) = False`，两腿合成式拒绝）+ SessionBudget 三分未落地 + 开闸由 IP §12 的门槛检查与用户独立裁决决定——**Calibration100 体量门（现读数 100/100、60/30、33/2 三门全达；两门按声明读法读，Revisit 待 canonical 定义落地）不再是 HOLD 的原因**。具体交接与对象索引见 `AGENTS.md`。

**世界运行时（活世界程序，wr-0..wr-12 + lr-1..lr-4a）**：用户寄一封信 → 世界先于回信连转若干叙事步（**生成式叙事器**——严格 JSON 契约的世界自主运转；**双层律**：信只属笔友层，信文永不进世界 prompt，世界只知道「有封信在路上、走了几天」）→ directed 模式每一步是选择点（**停点轮**：世界停下来，导演从候选走向里挑一个、或自己写一句，世界按走向再走一步；immersive 模式世界自主连转）→ 信在世界时间里自然抵达（叙事者自己的 `letter_arrives` 停词），**角色此时才回信**，且回信知道世界刚发生什么（近期编年史入 persona prompt——wr-12）→ 刷新后信、世界事件、回信按实况正序恢复（wr-8/wr-8R 交错读面 + 读面永不翻揭示面的红线）。世界有自己的虚拟历（派生故事日、零时钟读面）、居民（cast⨝角色卡）与揭示纪律（PENDING 便条只有收件箱这一处呈现触发；「看一眼」不等于「拆信」）。外评第六轮（2026-10-09）的定性：**产品真跑起来，但最深世界语义未完成**——HIGH-1（生成事件系统性无状态效果）路由给 C1 world event semantics 收口、HIGH-2（信打动角色但角色不因信产生世界行动）路由给 C1.5 中介因果协议，均未动工。

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
- `--content-db` 缺省指仓内构建产物 `build/content.db`（`PYTHONPATH=src python -m elc.content.build` 生成——该口径带 D-3 名单的 36 实体 EV 集；库 API `build_content_db` 缺省零 EV，两种构建的门读数不同是**产物事实**）。

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
- `--content-db` 给 chat 装配**全链 tier**（自动教学腿 + 真检测器）；`--rollout-stage` 声明 §12 四词之一（非法词人话退出 2）。**可选**（veto-R 起）：不传时读 app.db 里持久的教学模式（设置页「教学模式」写入的档，migration 0022 的 `app_setting` 表）；两边都没有 = fail-closed，零自动教学。启动命令显式给档时，本进程以启动命令为准（页面仍可热改，重启后回到显式档）。
- `observations` 是纯 SQL 读面：§12 六指标声明 + app.db 真实计数（gate_decision 按 decision×reason_codes，含 `TARGET_NOT_EXECUTABLY_VERIFIED` 漂移信号计数）+ D-3 matcher 已知假阳面清单——只打印，不写任何表。

### 本地 Web 面（W-1，用户已明示同意）：浏览器里的 Study-first dogfood

```bash
# 最小启动（启动系统刀：端点/模型/密钥都在设置页「模型与端点」里设，
# 保存即热生效、重启后仍以页面值为准）：
PYTHONPATH=src python -m elc web --app-db ./app.db \
  --content-db ./build/content.db --port 8760
# 浏览器打开 http://127.0.0.1:8760 → 抽屉 · 设置 → 模型与端点

# 也可以照旧在启动命令里给全套（chat 仍要求全套；web 全可选）：
PYTHONPATH=src python -m elc web --app-db ./app.db \
  --base-url https://api.example.com/v1 --model gpt-4o-mini \
  --api-key-env OPENAI_API_KEY \
  --content-db ./build/content.db --rollout-stage Study-first \
  --port 8760
```

- **web 的启动参数只剩 `--app-db` 必填**：端点、模型、API 密钥都是页面可设面（保存即热换——下一封信就走新设置；密钥只存本机 app.db，任何读数不回显，只报「已保存/未保存」）；裸启动时发信答诚实的 `not-configured` 值，直到页面把三件填齐。**多模型配置档**：设置页可把端点+模型+密钥存成多个具名配置档，点一下随时切换（下一封信即生效）。**教学档位同理**：`--rollout-stage` 可选，设置页「教学模式」可热切换（带 `--content-db` 即可，无需重启）。
- 参数 = chat 全套 + `--port`（缺省 8760）；**只绑 127.0.0.1、无鉴权**——单用户单机 dogfood 面，不是服务，别暴露到本机之外。
- 页面：对话区（逐轮走 `/api/turn_stream` SSE 流——世界先讲（叙述增量上页、整帧定版）、回信增量随后、恰一 `final`；只有流**未开始**的失败（请求没发出去、信未上链）才回退旧 POST `/api/turn` 重寄；对端非 SSE 或流中途断开都**不重发**——拉历史按库里事实对齐，同一封信永不寄两遍）+ 停点态（directed 模式世界走一步就停：走向候选点选/自由输入一句/「让世界继续」按钮，信到才回信）+ 世界故事块随信呈现（日期行+叙述段，历史恢复时按实况正序织回）+ 本轮教学时刻卡（按 turn 血缘查，非「最新行」；等待回应的时刻带**「回应」输入框**（POST `/api/teaching_reply` `{"control":"attempt","text":"…"}`，经 coordinator 既有回应入口进 §4 评估链判分，答对结课释锁、答错再给一次；`hint`/`reveal`/`explanation` 三帮助词同入口）与**「先搁着」按钮**（`{"control":"skip"}` 同入口释放时刻锁））+ 观察读数按钮（与 `observations` 命令同一读数核心，数字同源）+ 打开页面即拉最近 50 轮恢复对话。
- turn 级失败是**运行事实**（HTTP 200 + failure 字段）；只有坏请求体才是 400。

### 真实端点 smoke（可复制；dogfood 步骤，不属 CI）

```bash
PYTHONPATH=src python -m elc chat --app-db ./smoke.db \
  --base-url https://<real-endpoint>/v1 --model <model> \
  --api-key-env OPENAI_API_KEY
```

**CI 不发真实请求；本仓未验证与任何具体厂商/网关的互操作性**（属 dogfood 步骤）。
