# English Learning — Clean Rewrite (V1)

Canonical Implementation Baseline V1（2026-09-20）。规范优先级：`docs/` 六份 canonical 文档 > `behavioral_baselines/` 参考与回归资产 > 任何历史设计文档与旧实现（旧仓库 `D:\测试1` 整体作为 exploration archive 保留）。

- `docs/` — PRODUCT_CONTRACT / DOMAIN_MODEL / STATE_MACHINES / DATA_MODEL / RUNTIME_ARCHITECTURE / IMPLEMENTATION_PLAN + DECISION_REGISTER + ARCHITECTURE_BASELINE + 一致性报告（机器复核 60/60 PASS）
- `behavioral_baselines/` — BF-01～07（Estimator / Planner / Gate / Golden / Modality / Local Runtime / Security）：**实现合同，不是设计参考**；新仓库必须自动回归
- `src/` — 域模块（**Phase 0–10 已填充**：conversation / persona / learning（含 natural-chat silent evidence）/ teaching（含 Gate 的四个 profile 与 rollout 门槛检查器）/ runtime（含 recovery scan 面、delivery records、guarded stream、pre-delivery guard、exposure reconciliation）/ platform / relationship（含 Episode 投影）/ planner（kernel + 可审计 trace + 候选供给侧/scope/frontier/ledger + shadow mode 与冻结 43 例重放）/ deletion（BF-05 source-aware 删除与墓碑）/ user_config（§5.1 Goal·Policy·Focus 版本化 + §9 PlannerConstraint）/ scheduler（§5.2 ScheduleItem·ReviewEvent、spacing 纯策略 due/overdue、ScheduleView）/ curriculum（R0–R4 readiness + production TeachingTargetProvider）/ content（content.db 确定性构建与只读读面）/ world_lore；其余域按 IMPLEMENTATION_PLAN §1.5 位次待填）
- `tests/` — architecture / state-machine / determinism / property / failure-injection / golden（IMPLEMENTATION_PLAN §14）
- `migrations/` — app.db 迁移

第一条学习垂直切片现状（`DEC-OPI-5ba74efc-….65/.68`）：**Teaching-driven learning vertical slice COMPLETE**（explicit user TeachingMoment → target-specific Attempt Evidence → LearnerState，含 before≠after 可追溯与全链验收）；**natural-conversation target-specific silent Evidence 已随 Phase 5 交付、并经 P5-R 按 canonical 收窄**（自然 Persona 对话 → 确定性 target resolution：**仅 RESOURCE 目标、仅整句形式的 canonical/alternative 命中**才铸 target-specific Performance Evidence → Estimator → LearnerState；CAPABILITY 命中、仅 slot 命中、嵌入跨度/引用/转述/元语言一律**只记匹配观察、不产生证据**；无 TeachingMoment/Gate/Planner 介入，供给降级不阻聊天）。实现 PR 必须能指出自己遵循/修改哪一条 contract。

**实现现状（2026-09-26）**：**Phase 0–10 全部 COMPLETE（工程）** + **prep-1 落成**（真 provider 适配 + secret 缝 + 首个 composition root + 最小 CLI）+ **prep-1R**（provider egress 加固：禁重定向 / 明文 HTTP 策略 / 响应上限）+ **C1（Phase 11 内容程序第一段）**（readiness 证据面：13 张新表（content.db 11 → 24）+ `content_src/evidence/` 严格装载 + §8.1 十九键无一缺席（18 键逐表读 + `entity_row` 由前置 `get_resource` 成功证明存在）+ 钉搬迁 ⇒ 首个 target `res-colloc-make-a-decision` 真达 **R4_DETECTION_READY**；C1 处置：`content_db_version` bump "2"、reviewed 读法 = teaching_note 行 ∧ 实体 `CANONICAL_APPROVED`、credit 批准的活风险 `R-C1-credit` 入账）+ **C2-a（Phase 11 内容程序第二段）**（其余 8 个 res 各一份 evidence 文档 ⇒ 现役真产物上 **9×R4_DETECTION_READY + 5×None**；8 条 §24.7 link 由 C2-a 编辑评审批准，**credit 面 1 → 9 条**——行为变更已单列披露，活风险 `R-C1-credit` 的 Revisit 不变）+ **C2-b（Phase 11 内容程序第三段）**（19 个新 res 实体（entity + 19 键 evidence 全链 + 19 条 link）⇒ 现役真产物上 **28×R4_DETECTION_READY + 5×None**，`resource_count`（`res-*` 实体）= **28**，即 IP §13 的 28→100 calibration 起点**第一档达成**；19 条新 link 里 6 条是 REALIZES（**credit 面 9 → 15 条**，行为变更单列披露，Revisit 不变）、13 条是 SUPPORTS（**credit-safe**：credit 读面只认 REALIZES，已批准的 SUPPORTS 行满足 §8.1 R2 的 `curriculum_link` 事实而**不铸任何学习者证据**）；**Calibration100 三门（100/30/2）仍全未过**，真实 rollout 仍 HOLD）——Phase 8 = Planner→Gate→自动教学链 + rollout 门槛检查器；Phase 9 = Delivery / Exposure Hardening（含 P9-R 三件高/中危修复后重签 PASS）；**Phase 10 = Runtime Recovery**（五刀：scan 面补齐 / 25 类失败场景套件 A+B / 两个待裁题正式裁决 / D1 fence 修复 + F4 收口 + 相位级映射表）。**测试读数以 `AGENTS.md` 台账与 CI 为准**（本文件不再复制总数 / 逐目录 / mypy 文件数，避免漂移）；这里只留不随读数变的事实：迁移 head **`0018_delivery_records`（v18）**、`dependencies = []`（标准库 + SQLite）、**语料 capable 与 rollout HOLD 分开拄**——C2-b 后 rollout 门槛检查器对现役语料的四行内容门答 **GO**（BF-02 §10 每行"至少 1 个 target"被 **28 个** R4 target 满足），但 **真实 automatic-teaching rollout 仍 HOLD**：宿主未声明 rollout stage（`stage_allows_automatic(未声明) = False`，两腿合成式拒绝），Calibration100 体量门（IP §13 的 100/30/2，现读数 `resource_count` **28/100** 未达——33 实体中 28 个 res 全 R4、5 个 cap 无 level；CORE_A **0/30**、CORE_C **0/2** 亦未达）未达，开闸由 IP §12 的门槛检查与用户裁决决定。**IP §13 的「28 → 100 resource calibration」因此走到第一档（28）**，而不是 Calibration100 的任何一门通过。具体交接与对象索引见 `AGENTS.md`。

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

### 真实端点 smoke（可复制；dogfood 步骤，不属 CI）

```bash
PYTHONPATH=src python -m elc chat --app-db ./smoke.db \
  --base-url https://<real-endpoint>/v1 --model <model> \
  --api-key-env OPENAI_API_KEY
```

**CI 不发真实请求；本仓未验证与任何具体厂商/网关的互操作性**（属 dogfood 步骤）。
