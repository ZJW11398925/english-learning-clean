# v3-1 教学卡重做 · 前置四查报告（判分语义数据链 + 卡片信息架构）

> 日期：2026-10-02。基线：`4ea75a1`（工作树除两份既有 untracked 外干净）。
> 性质：调研报告，零仓内写盘（本文件是唯一写入）。零 dmcp 调用、零设计状态对象改动。
> 用途：v3-1 实施刀的任务书输入。所有行号以 `4ea75a1` 为准。

---

## 0. 结论摘要

**P0-1（合法句被判 FAILURE）的确切机制**——任务书初查的两条假设**都不成立**，真因在判分器的第 4 层（required_slots 覆盖）的**数据 authored 方式**上：

1. i-think 的 answer_key **不缺数据**：`content_src/entities/res-hedge-i-think.json` 的 `teaching_content` 块齐全（canonical 2 条 / alternative 2 条 / required_slots 2 组 / hint 3 级 / reveal 1 条）。事实上**全部 100 个 RESOURCE 实体都有非空 required_slots**（0 个空 key）。
2. UI **有**五态判词映射（SUCCESS/ALTERNATIVE_SUCCESS/PARTIAL/FAILURE/ABSTAIN 各有中文判词），不是「非 SUCCESS 全显没答中」——UI 如实显示了评估器给出的 FAILURE。
3. 真机制：`required_slots = [["rain"], ["think", "guess", "reckon"]]` 两组取 **AND**。体验者答句 "I think it depends on the weather." 含 "think"（第 2 组覆盖）但**不含 "rain"**（第 1 组落空）→ `all()` 失败 → 落到第 5 层 FAILURE。而 "rain" 是**示例句的内容词**，不是目标公式「I think」的组成部分——槽位把「复述示例句场景」误当成了「学会目标表达」。四个判定层全部走完后，一句完全合法的 hedge 句被判整体失败。

**canonical 判据**：`docs/STATE_MACHINES.md` §5 Resource Practice 明文「**不能把 communication success 粗暴标成整体失败**」——本例直接违反该句。

**P0-2（卡片多轮膨胀）的确切机制**——`components.js` 的回应回路全部用 `appendChild` 向同一张卡累积，且 `disarmMomentCard` 拆控件时**漏拆「先搁着」按钮**：

- 每轮 attempt 后：`readReplyAnswer` 追加 `<br>` + 「再试一回？· 状态 …」行（:422-429）+ 新结果条 `showResultStrip`（:431）；
- `disarmMomentCard`（:399-408）只删 `.replyrow` 与 `.guide`；「先搁着」按钮 class 是 `btn btn--faint`、直接挂在卡上（components.js :375-381），**不在任何 `.replyrow` 内** → 每轮重挂控件都多留一枚旧按钮（体验者数出的「3 个先搁着」）；
- 每次求助（提示/答案/讲解）`postReply` 把 `delivery_text` 追加为一条 `.noteline`（:479-482）——多轮后提示句、参考答案、讲解段全部平铺连排在卡内；
- 版式上 `#moments` 紧贴 `#messages` 之后（index.html :63-64），卡内 `.noteline` 的参考答案在视觉上直接接在信尾 "Yours, Nell" 落款后面，读起来像信件正文。

修复方向已定（§4）：判分 = **数据面主修（槽位重写按判据）+ UI 文案配合**，评估器加层为可选加固；卡片 = **当前态替换 + 历史折叠 + 参考答案独立区块 + 控件整组拆装**。

---

## 1. 查一：canonical 判分语义与 answer_key 契约

### 1.1 五态 outcome 的 canonical 语义（STATE_MACHINES.md §5，逐字）

```text
SUCCESS
PARTIAL
FAILURE
ALTERNATIVE_SUCCESS
ABSTAIN
```

- **Capability Practice**（§5 原文）：「Alternative realization 成功：`ALTERNATIVE_SUCCESS → valid capability success`」。
- **Resource Practice**（§5 原文，本刀判据句）：「用户通过其它说法完成 communication：`Capability positive` / `Resource neutral/not demonstrated`。**不能把 communication success 粗暴标成整体失败。**」
- `evaluator.py` 模块 docstring（:28-32）：五值原样返回，`ALTERNATIVE_SUCCESS` **不**在评估器内折叠成 SUCCESS——折叠是 Learning 证据转换的职责（capability positive + resource neutral），这正是 migration 0008 的 `attempt_evaluation_record.outcome` CHECK 带全部五词的原因。

### 1.2 PARTIAL 的既定语义（可再答；「mixed evidence」）

- **canonical 没有**给 PARTIAL 一句用户面文案；用户面判词由 FRONTEND_SPEC 8.2.10 定稿（「◐ 答了一半」，见 §3.4）。
- canonical 给了 PARTIAL 的**流程落点**：SM §1 Main flow 的 DECIDING_NEXT_ACTION 分支表里「`HINT / RETRY ───→ AWAITING_USER`」——非 SUCCESS 的评估走 retry-like continuation（`src/elc/teaching/next_action.py` :37-40、:239-249：CONTINUE/NONE 等 → `delivery_kind="RETRY"`，时刻留在 `AWAITING_USER` 可再答）。**即 PARTIAL ⇒ 可再答是 canonical 流程内建语义**。
- 证据语义：`docs/DOMAIN_MODEL.md` §6（Learning Evidence kernel 末行）：「PARTIAL 是 mixed evidence」。
- 收口面：SM §6 completion outcomes 有 `PARTIAL_PROGRESS`（软上限把续接转成收场时的落点，next_action.py :227-236）。
- ABSTAIN：`evaluator.py` :214-228——「不可判」绝不洗成 FAILURE（resolver 故障不是对学习者的负面断言）。

### 1.3 answer_key 的 canonical 数据契约：**不在 canonical 六文档内**

- `docs/DATA_MODEL.md` §17 AttemptRecord / AttemptEvaluationRecord 只定义 durable 九列（`attempt_evaluation_id / moment_id / attempt_id / evaluator_id / evaluator_version / outcome / confidence / evidence_proposal_refs / created_at`），**无 basis 列、无 answer_key 概念**。§15 TeachingMoment / §16 TeachingResponseEnvelope 同样不含 key 字段。
- §24.5 只定义 `ExampleLink` roles（`PRIMARY_TARGET / SUPPORTING / CONTRAST / ERROR_INSTANCE`）——这就是实现里 canonical_forms/alternative_realizations 的落表角色名来源，但「required_slots」五个字**在六文档中出现次数为零**（全仓 grep 证实：DATA_MODEL/DOMAIN_MODEL/RUNTIME_ARCHITECTURE 均无 `required_slots`/`canonical_forms`/`teaching_content` 字样）。
- key 的**真实契约归属**：`src/elc/teaching/evaluator.py` :99-118（`AttemptAnswerKey`：`canonical_forms` / `alternative_realizations` / `required_slots` 三元组，docstring 定义各自语义与「empty key 合法、任何具体作答 ⇒ FAILURE，最坏是 FAILURE 绝不伪造 SUCCESS」）+ 设计权威 `DEC-…2babb21e.5 Q4`（evaluator.py :3 引用）+ 判定纪律「无通用 substring 当 SUCCESS」（evaluator.py :21-26，Phase 3 任务书原文）。**v3-1 若扩展 key 契约（如 expression_markers），扩展点是 build 的 `_TEACHING_KEYS` 严格键清单 + evaluator 契约 docstring，不触 canonical 冻结面；但应在 DATA_MODEL §24 记一行契约归属（沿 C3-R1/EXT-C3-02 的「separate-document fact」措辞纪律）。**
- 行为基线（behavioral_baselines/）：estimator/gate/golden/modality/planner/runtime/security 七族，**无 attempt-evaluation 基线**——判分语义不受 BF 冻结面约束（BF-03 是 Gate 授权面）。

### 1.4 评估器判定顺序（evaluator.py :9-19 + :166-211，实现即契约）

```text
1. 归一化后无文本                          → ABSTAIN（NO_ATTEMPT）
2. 归一化后与某 canonical_form 全等         → SUCCESS（CANONICAL_FORM_EXACT, conf 1.0）
3. 与某 alternative_realization 全等        → ALTERNATIVE_SUCCESS（conf 1.0）
4. required_slots 每组至少一个 token 在场   → PARTIAL（REQUIRED_SLOT_COVERAGE, conf 0.5）
5. 否则                                     → FAILURE（NO_MATCH, conf 0.5）
```

- 全等是**整答等值**（never substring，:154-163 `_qualified`）；槽位覆盖是**整词 token** 检查（:142-151 `_tokens`，按 `\w+` 切分）。
- **basis 不落库**：`migrations/0008_attempt_records.sql` :322-340 的九列无 basis；`evaluator_id/version/outcome/confidence` 才是 durable。⇒ 评估器侧加新 basis 词**零迁移**；改判定语义只需 bump `ATTEMPT_EVALUATOR_VERSION`（注意 DATA_MODEL §25：evidence-commit key 含 evaluator version，**升版本 = 新证据身份**，旧证据不重算）。
- key 为空是合法诚实值（:110-113）——但本语料 100/100 非空（§2.3），该臂今日不承重。

### 1.5 判分到时刻状态的接线（runtime 面，供修法定位）

- 调用点：`src/elc/runtime/controller.py` :5577-5579 `evaluate_attempt(request.envelope.attempt.text, answer_key_for(view))`；view 解析不出 → `unjudgeable_evaluation()`（ABSTAIN）。
- `answer_key_for` = `src/elc/teaching/flow.py` :279-287 → `TeachingTargetView.answer_key()`（`src/elc/teaching/targets.py` :101-109，纯投影三字段）。
- 后续：SUCCESS/ALTERNATIVE_SUCCESS 且无并列求助意图 → COMPLETING（next_action.py :179-196）；其余 outcome 走 :198-236 的续接/上限转换。
- RETRY 的交付文本 = 固定行 `RETRY_NOTE = "这句还没说对——再试一回。"`（controller.py :334、:5985-5988）；HINT/REVEAL/EXPLANATION 的交付文本 = 语料 hint rung / reveal_form / teaching_note 组装（:5990-5992、:360-375）。收场 resume 才起模型（PERSONA_RESUME，controller.py :6190+ `_resume_and_close`）。

---

## 2. 查二：answer_key 数据链全链与 i-think 实值

### 2.1 全链路（源头 → 落库 → 读取 → 判分）

```text
content_src/entities/<entity_id>.json          ← 源头（不是 evidence/ 目录）
  .teaching_content { hint_ladder[], reveal_form,
                      canonical_forms[], alternative_realizations[],
                      required_slots[[]] }
    │  build.py:1448-1465 解析（_TEACHING_KEYS 严格五键，_exact_keys 拒多键；
    │  :1461-1465 reveal_form 必须 ∈ canonical_forms，否则 BuildError）
    ▼
content.db（生成产物，VERSION 5）
  content_example(entity_id, role, ordinal, form)
      role=PRIMARY_TARGET ← canonical_forms；role=SUPPORTING ← alternative_realizations
      （build.py:2694-2705；角色词表 = DATA_MODEL §24.5 ExampleLink roles）
  content_slot(entity_id, group_ordinal, token_ordinal, token)   ← required_slots（build.py:2706-2716）
  content_hint_rung(entity_id, ordinal, rung)                    ← hint_ladder（build.py:2680-2687）
    │  store.py:415-465 get_teaching_content → ContentTeachingView
    │  _forms(entity_id, PRIMARY_TARGET/_SUPPORTING)（store.py:452-459）、_slots（store.py:467-482）
    ▼
host/content_store → TeachingTargetProvider → TeachingTargetView（targets.py:54-109）
    ▼
answer_key_for(view) → AttemptAnswerKey → evaluate_attempt（controller.py:5577）
```

注意两个容易搞错的点：① `content_src/evidence/` 目录（100 个文件）是**评估取证面**（readiness 证据），**不含 teaching_content**——key 的源头只在 `content_src/entities/`（105 个文件全部带 teaching_content 块）。② entities 的 `entity_type` 全部是 `EXPRESSION`，RESOURCE/CAPABILITY 的区分在 `target.target_type`（100 RESOURCE + 5 CAPABILITY）。

### 2.2 i-think 的 key 实值（本刀 P0-1 的直接证据）

`content_src/entities/res-hedge-i-think.json`（`entity_revision: 2`，`lifecycle_status: CANONICAL_APPROVED`）：

```json
{
  "hint_ladder": [
    "Hedge the claim so it does not sound like a fact.",
    "Use a short phrase before the statement, not after it.",
    "Start with the two words: I ___ it is going to rain."
  ],
  "reveal_form": "I think it is going to rain.",
  "canonical_forms": ["I think.", "I think it is going to rain."],
  "alternative_realizations": ["It might rain.", "I'd say it will rain."],
  "required_slots": [["rain"], ["think", "guess", "reckon"]]
}
```

**对体验者答句的逐层推演**（`"I think it depends on the weather."`）：

| 层 | 判定 | 依据 |
|---|---|---|
| 2. canonical 全等 | ✗ | `"i think it depends on the weather"` ≠ `"i think."` ≠ `"i think it is going to rain."` |
| 3. alternative 全等 | ✗ | ≠ `"it might rain"` ≠ `"i'd say it will rain"` |
| 4. slots 覆盖 | ✗ | tokens = (i, think, it, depends, on, the, weather)；组 1 `["rain"]` 无一在场 → `all()` 假 |
| 5. 兜底 | **FAILURE** | evaluator.py :207-211 |

体验者被接受的唯一句 `"I think it is going to rain."` = canonical_forms[1] 逐字。体验报告与机械推演完全吻合。

**同族数据张力（顺带取证）**：i-think 自己的 `detection_rules[2]`（ACCEPTED_REALIZATIONS）声明「It is going to rain, I think.」是 accepted realization，但它**不在** `alternative_realizations` 白名单里——按现 key 只能落 PARTIAL（rain ✓ think ✓），声明面与判分面不一致，槽位重写时应一并裁。

### 2.3 全量统计（105 实体亲扫，机器读数）

- 105 实体 = 100 RESOURCE + 5 CAPABILITY；**100/100 RESOURCE 都有非空 required_slots**（0 空 key）——「key 缺数据」假设不成立。
- **88/100 RESOURCE 只有 1 条 canonical_form**（即 reveal_form 本身）；4 个 RESOURCE 的 alternative_realizations 为空；「≥2 canonical 且 ≥2 alternative 且 ≥1 slots」的只有 i-think 一个。
- i-think 已是**最丰富**的 key 之一——它仍然把合法 hedge 句判 FAILURE。**问题不是数据缺失，是槽位 authored 判据**。

### 2.4 五个对比样本（key 丰富度抽样，亲读源文件）

| target | canonical | alternatives | required_slots | 备注 |
|---|---|---|---|---|
| res-hedge-i-guess | 2（含裸形 "I guess."） | 1 | `[["guess"]]` | 单组＝公式词，**判据正确**的形态 |
| res-colloc-heavy-rain | 1 | 1 | `[["rain"], ["heavy"]]` | 两组都是目标自身词，判据正确 |
| res-discourse-to-be-honest | 1 | 1 | `[["honest"], ["design"]]` | "design" 是示例句内容词——i-think 同病 |
| res-discourse-anyway | 2（含裸形 "Anyway."） | 1 | `[["anyway"]]` | 公式词单组，正确 |
| res-phrasal-figure-out | 1 | 1 | `[["figure"], ["answer"]]` | "answer" 是示例句内容词——同病 |

**规律**：collocation/idiom 类把目标自身词做槽位（对）；formula/discourse 类把**示例句的话题词**（rain/design/answer）混进槽位（错）——示例句内容词是「练什么场景」，不是「学会什么表达」。

### 2.5 测试侧镜像（修数必随迁）

`tests/phase3/target_fixtures.py` :55-64 与 content_src 逐字镜像：

```python
"res-hedge-i-think": {
    ...
    "required_slots": (("rain",), ("think", "guess", "reckon")),
```

（同族：heavy-rain `[["rain"], ["heavy"]]` 等 14 fixture 全镜像。）**改 content_src 槽位 ⇒ target_fixtures.py 真值随迁 + `test_teaching_evaluator_v0.py` :144 `test_every_validated_fixture_has_a_usable_answer_key` 复核**（沿 c2-a「真值全扫」先例）。

---

## 3. 查三：UI 链与膨胀机制

### 3.1 渲染链（端点 → 组装 → 回合累积）

```text
POST /api/turn（web.py:3574）
  └─ 响应带 teaching_moments[]（_moments_of_turn web.py:2150-2176：
     focus_target_id / lifecycle_state / kind / title / status_cn / kind_cn）
  └─ app.js:2497-2498 showMoments(moments)
GET /api/teaching/current（web.py:3425 → _current_teaching_ro web.py:1961-2038，W-4 脱队列 ro 面）
  └─ 另带 last_attempt_feedback（_last_attempt_feedback_of web.py:1937-1958，
     读 attempt_evaluation_record 最新行 → _readable_outcome）
  └─ app.js:2569-2570 / 2419 showMoments([moment])（刷新恢复 / 轮询）
POST /api/teaching_reply（web.py:3575 → BaseHandler.teaching_reply web.py:2189-2305）
  └─ 响应 { accepted, moment_state, feedback, delivery_text?, error }
  └─ components.js postReply(:459-490) → readReplyAnswer(:417-457)
```

卡片 DOM 的唯一组装点是 `components.js` 的 `showMoments`（:283-338，每次整组重渲 `momentsBox.textContent=""`）；**回合内的累积发生在 postReply/readReplyAnswer 对同一 card 节点的 appendChild**。

### 3.2 P0-2 膨胀的确切机制（四个累积源 + 一个漏拆，全部带行号实锤）

| # | 机制 | 位置 | 每轮效果 |
|---|---|---|---|
| 1 | **「先搁着」按钮漏拆** | `addReplyControls` :375-381 把 skip `<button class="btn btn--faint">先搁着</button>` **直接挂在卡上**；`disarmMomentCard` :399-408 只删 `.replyrow` 和 `.guide` —— skip 两头都不沾 | 每轮作答/求助后重挂控件时，旧按钮留下 → N 轮 N 枚（体验者数到 3） |
| 2 | 结果条累积 | `readReplyAnswer` :430-432 每次评估有反馈就 `showResultStrip`（:241-249 `card.appendChild(strip)`，从不移除旧条） | 每轮 attempt 多一条 ✗/◐/✓ 条 |
| 3 | 「再试一回？· 状态 …」行累积 | `readReplyAnswer` :422-429 appendChild(`<br>`) + appendChild(`<b>`) | 每轮多一行 |
| 4 | 交付文本平铺累积 | `postReply` :475-482 `data.delivery_text` 每次求助追加一条 `.noteline`（textContent 平铺、无格式） | 提示句/参考答案/讲解段全部连排堆叠（「格式压成连排」的来源） |
| 5 | 状态行/类型行/卡头不累积 | `showMoments` 整组重渲时重建 | 仅回合内膨胀，回合边界（下一轮 /api/turn）自愈 |

（对照：`addReplyControls` 的 guide 行与两个 `.replyrow`——作答行 + 求助三钮行——每轮被 `disarmMomentCard` 正确拆掉；**唯独 skip 按钮游离在拆装契约之外**。）

### 3.3 「参考答案接在 Yours, Nell 后面」的版式根源

`index.html` :63-64：

```html
<div id="messages" aria-live="polite"></div>
<div id="moments"></div>
```

`#moments` 紧贴信流之下；看答案（REVEAL）的 `delivery_text` 以裸 `.noteline`（弱化小字行，components.css :190-192）落在卡内，与信纸同底色纸面视觉连续——参考答案句 `I think it is going to rain.` 在屏上紧跟信尾 "Yours, Nell"，无任何「这是参考答案」的视觉标记。spec 8.2.10 对 REVEAL 的卡内呈现**没有任何定形**（只定了 confirm 文案），这是 v3-1 要补的空档。

### 3.4 判词文案映射（三处，均为现役真值）

- **web.py :416-424 `_OUTCOME_CN`**（runtime 原话的中文读法）：`SUCCESS:回答正确 / ALTERNATIVE_SUCCESS:回答正确（另一种合格表达）/ PARTIAL:部分正确 / FAILURE:未命中目标表达 / ABSTAIN:本次作答无法评判`；`:519-525 _readable_outcome` 拼成 `FAILURE（未命中目标表达）` 形。
- **components.js :223-229 `OUTCOME_VERDICT_CN`**（中文判词打头，FRONTEND_SPEC 8.2.10 定稿）：`✓ 答得漂亮 / ✓ 答得漂亮（另一种说法也算）/ ◐ 答了一半 / ✗ 没答中 / 这次没法判`；条上全文 = `判词 · FAILURE（未命中目标表达）`（:247）。
- 措辞张力（登记级）：8.3 术语表总则「状态/枚举只出中文」，但结果条现役把英文工程词 `FAILURE（…）` 原样带出（web.py `_readable_outcome` 的形状）——沿「纸边小字（人话主句 + 括号工程词）」的 spec 470 条款可辩，v3-1 若动判词区可一并裁。

---

## 4. 查四：修法方案（施工级）

> 推荐组合：**A1（数据面，主修）+ A3（UI 文案配合）+ B（卡片 IA）**；A2（评估器加层）列为可选加固，默认不做。理由：A1 已能让 i-think 及全部 formula 类 target 的合法句落到 PARTIAL（可再答、不再是整体失败），且零 canonical 冲突、零迁移、零证据身份变更；A2 动判定语义，牵动 evaluator version / 证据身份 / phase3 十例钉，收益边际。

### 4.1 刀 A：判分语义修复

#### A1（主修）数据面：required_slots 重写按判据「槽位 = 目标自身的词汇材料」

- **改哪个文件**：`content_src/entities/*.json`（本轮至少 `res-hedge-i-think.json`；建议同刀全量审计 100 个 RESOURCE，凡槽位含**示例句话题词**的按判据重写）→ 重建 content.db（生成产物，CLI build 即可）。
- **i-think 具体改法**：`required_slots: [["rain"], ["think","guess","reckon"]]` → `[["think","guess","reckon"]]`（删示例句话题词组，保留公式词组）。改后推演：`"I think it depends on the weather."` → 组 1 think ✓ → **PARTIAL**（可再答/可先搁着）；`"I like rain."` → FAILURE（无 hedge，正确拒）；`"It might rain."` → ALTERNATIVE_SUCCESS（白名单，不变）。
- **顺带裁 i-think 的声明面张力**（§2.4）：`"It is going to rain, I think."`（detection_rules[2] 声明的 accepted realization）建议补进 `alternative_realizations`，让声明与判分一致；若不补，登记 Revisit。
- **必随迁**（沿 c2-a/c3-d「真值全扫 + 判据面 digest 钉随迁」先例）：
  - `tests/phase3/target_fixtures.py`（14 fixture 的 required_slots 镜像，至少 i-think 行 :64）；
  - `tests/phase3/test_teaching_evaluator_v0.py`（:88 十例钉 + :144 全 fixture 可用性钉复核）；
  - 真值随迁全扫（phase5 真值钉族 + `N-C3D-3` 判据面 digest 钉若涉 content_src）；
  - content.db 双构建字节一致 + `PYTHONHASHSEED` 跨进程（机制事实 m6：确定性靠排序键）。
- **canonical 依据**：STATE_MACHINES §5 Resource Practice「不能把 communication success 粗暴标成整体失败」；PARTIAL ⇒ AWAITING_USER 可再答（SM §1 + next_action.py 现役实现不动）。
- **风险**：① 假阳面变宽——`"I think so."`、`"I don't think so."` 也会落 PARTIAL（公式确实在场，判「答了一半」可辩；但 `"I don't think so"` 语义反向，建议写进 evidence 的 BOUNDARY 或登记）；② 88 个单 canonical target 的槽位重写会改变其 PARTIAL 面宽度，**建议本刀只重写「槽位含示例句话题词」的 target 并逐条列出**，不做一刀切的全量改槽；③ content_src 是 C 系列多刀冻结面——需总控在任务书显式授权（C1 先例：冻结面触碰走授权）。

#### A2（可选加固，默认不做）评估器面：声明式 expression-marker 层

- **若做**：`AttemptAnswerKey` 增字段 `expression_markers: tuple[str, ...]`（声明式，非推导）；判定序插在第 3 层后：marker 序列以**整词序列**在场（非 substring）→ PARTIAL（新 basis `EXPRESSION_MARKER_PRESENT`，conf 0.5）。
- **改哪个文件**：`src/elc/teaching/evaluator.py`（key 字段 + 判定层 + `EVALUATION_BASES`/`_CONFIDENCE_BY_BASIS`）、`src/elc/content/build.py`（`_TEACHING_KEYS` 增键 + `_slot_groups` 同级的严格装载）、`src/elc/content/store.py` + `content/types.py`（view 投影）、`src/elc/teaching/targets.py`（view 字段）、content_src 各 entity 补声明。
- **canonical 允许吗**：允许。SM §5 的 PARTIAL 层语义可承载「目标表达在场但整句未达标」；evaluator.py :21-26 的禁令是「**无通用 substring 当 SUCCESS**」——marker 层产出的是 PARTIAL 且是**逐 target 声明的事实**（「declared, reviewable fact about the target」正是原文对第 4 层的要求，marker 层满足同一纪律）。**不做无声明的通用兜底**（「句含目标表达即 PARTIAL」若无逐 target 声明载体，就是被禁的通用 substring 规则的 PARTIAL 版——契约上站不住）。
- **成本/风险**：durable 零迁移（basis 不落库、五词 CHECK 不动）；但 `ATTEMPT_EVALUATOR_VERSION` 应 bump `v0→v1`（DATA_MODEL §25：**升版本 = 新证据身份**，旧 EVALUATION 证据不重算——这是语义行为变更，必须单列披露）；phase3 评估器十例钉 + 「no substring SUCCESS」钉逐条复核；5 端到端面（evidence 转换读 outcome）复跑。

#### A3 UI 面：PARTIAL/FAILURE 判词的人话呈现

- **PARTIAL 加方向指引**（现役只有「◐ 答了一半 · PARTIAL（部分正确）」，无下一步指引）：结果条下补一行卡内指引导向，推荐文案「目标表达用上了——把整句说完，或点「提示」再看一眼。」（绑「提示」按钮的既有词族，不引入新控件）。**改哪个文件**：`src/elc/webui/components.js`（`readReplyAnswer` 的 PARTIAL 臂或 `showResultStrip` 增 part 臂的伴随行）+ **spec 回填** FRONTEND_SPEC 8.2.10 文案定稿段（判词区文案是 spec 钉面，改词必须同刀回填，v2-2 先例）。
- **SUCCESS/ALTERNATIVE_SUCCESS 判据呈现**：现役「✓ 答得漂亮」已够；可选在成功收场后于卡内参考答案区块标「参考说法」（B 刀的区块，见下），让「答对」与「参考」对照可读。
- **FAILURE 措辞**：维持「✗ 没答中」判词，runtime 原话括号保留（spec 470 纸边小字条款）；不建议本刀动。
- **风险**：spec 冻结字面（8.2.10 文案定稿段）必须同刀回填，否则下刀普查打假句；中文字面包络（铁律系）由总控评审。

### 4.2 刀 B：卡片信息架构重做（P0-2）

**推荐形态：当前态替换 + 历史折叠（混合）**——纯「替换」会丢多轮提示的语境，纯「全历史」就是现状。四条施工面：

#### B1 回合态槽位化：状态行/结果条/回试行从 append 改 replace

- `readReplyAnswer` 的「再试一回？· 状态 …」（:422-429）与结果条（:430-432）改为**写固定槽**：卡上至多一个 `.note-state`（回试行）+ 一个 `.resultstrip`（新条来时先移除旧条再挂新条；或直接复用同一节点改 textContent/className——推荐后者，零节点抖动）。
- 改哪个文件：`src/elc/webui/components.js`（`showResultStrip` :241-249 改「查旧条→更新或新建」；`readReplyAnswer` :417-457 改槽写入）；`components.css` `.resultstrip` 结构注释同步（:371-375 的结构注释写明「卡内至多一条」）。
- **不丢的东西**：W-6 判词词族、W-3 刷新恢复（`last_attempt_feedback` 只有一「最新」值，槽位化后语义天然一致——现状 append 多条反而是与 durable 单值不一致的假象）。

#### B2 skip 按钮整组拆装（P0-2 的确定性 bug）

- 「先搁着」按钮并入求助行所在的 controls 包装（或自成一个 `.skiprow` 参与拆装），`disarmMomentCard` 一并拆除。**保证不变量：卡内「先搁着」至多一枚**。
- 改哪个文件：`components.js` `addReplyControls` :372-381 + `disarmMomentCard` :399-408。

#### B3 参考答案独立区块：永不与信混排

- REVEAL 的 `delivery_text` 从裸 `.noteline` 改为专用区块：`<div class="note-answer">参考答案 · I think it is going to rain.</div>`——带「参考答案」标签行 + 左缘界尺或垫纸层次与信尾视觉断开（遵守 note-paper 禁止变体：不搞四侧描边框/弹层/大阴影；建议 `--pencil` 墨色 + 标签 mono 微标签，沿用 `.kv`/meta 字体配方）。
- 数据缝：web.py `teaching_reply` 的响应（:2294-2302）**加一个附加字段 `delivery_kind`**（`result.value.delivery_kind` 现成有值：HINT/REVEAL/EXPLANATION/RETRY，additive、不破既有键）——页面凭它分派区块；RETRY 的固定行维持 `.noteline`。**改哪个文件**：`src/elc/web.py`（teaching_reply 响应 +1 字段，docstring 契约段同步）、`components.js`（postReply 分派 + 渲染）、`components.css`（`.note-answer` 新件，入 8.2.10 与组件注册表）。
- spec 回填：FRONTEND_SPEC 8.2.10 增「参考答案区块」定形段（含「看答案后仍可回应」的既有 confirm 语义衔接）。

#### B4 交付历史折叠：多轮提示/讲解只保留最新显式，旧的进折叠

- 卡内交付区结构：最新一条显式；此前的 HINT/EXPLANATION 收进 `<details class="note-history"><summary>已看过的提示（n）</summary>…</details>`（REVEAL 始终走 B3 区块，不进折叠——参考答案在场就该显眼）。折叠是纯前端态，零新端点。
- 改哪个文件：`components.js`（postReply 交付分派处维护一个小队列）；`components.css`（details/summary 配方）。
- **回信去重的口径**：回合内卡内交付「只保留最新 + 折叠历史」；信流里的系统回执行（「回应已寄出。」「已看答案」等 `addLine("system", …)`）**保持现状**——信流是流式历史，不是卡内状态，不折叠。

### 4.3 卡片目标 DOM 结构草图（刀 B 落地后）

```html
<div class="note-paper [circled|settled|skipped] [note-paper--enter]">
  <div class="note-head">[inkicon note] <b>批注：{spoken 名} — {功能句}</b></div>
  <div class="noteline">{status_cn}</div>                 <!-- 服务端原词 -->
  [<div class="noteline">{kind_cn}</div>]                  <!-- 中文映射，未知省略 -->
  [<div class="resultstrip ok|part|miss">{判词} · {runtime 原话}</div>]  <!-- 至多一条，replace -->
  [<div class="note-state">{再试一回？ · 状态 等你回应}</div>]           <!-- 至多一条，replace -->
  <div class="note-delivery">
    [<details class="note-history"><summary>已看过的提示（n）</summary>…</details>]
    [<div class="noteline">{最新 HINT/EXPLANATION/RETRY 交付}</div>]
  </div>
  [<div class="note-answer"><b>参考答案</b> · {reveal_form}</div>]        <!-- REVEAL 专用，独立区块 -->
  [<div class="replyrow guide">回应写在这张批注上（不是下面的信纸）。</div>] <!-- 回应开着才在 -->
  [<div class="replyrow"><input.replytext><button 寄出回应></div>]
  [<div class="replyrow"><button 提示><button 答案><button 讲解></div>]
  [<div class="skiprow"><button 先搁着</div>]              <!-- 参与拆装，至多一枚 -->
  [<div class="busystrip">{批改中……}</div>]
  [<span class="card-stamp stamp-press">（成功族盖戳）</span>]
</div>
```

### 4.4 验收建议（真实场景，执行者可直接照做）

1. **P0-1 主场景**：pilot 构建库 + seed + `python -m elc web`，对 i-think 卡答 `I think it depends on the weather.` → 结果条 `◐ 答了一半`，卡仍可再答/先搁着；再答 `I think it is going to rain.` → `✓ 答得漂亮` + 盖戳收场。负例：`I like rain.` → `✗ 没答中`。
2. **P0-2 主场景**：同一张卡连续走「答错 → 取提示 → 看答案 → 答对」四步 → 卡内任意时刻**至多一枚**「先搁着」、**至多一条**结果条/回试行；提示历史在折叠里；参考答案带「参考答案」标签独立成块；刷新后卡片重建不复活已拆控件（W-3 恢复钉复跑）。
3. **回归**：全量 pytest（真值随迁后逐目录读数对齐）；`test_teaching_evaluator_v0.py` 十例、`test_teaching_reply_turn.py`、W-6/W-3/W-2 前端钉、双构建字节一致。

---

## 5. 异议区（对任务书初查的两处纠偏，附实测证据）

1. **「该 target 的 key 缺 required_slots 数据（语料面缺口）」——不成立**。i-think 的 key 三元组齐全且是全语料最丰富的之一（§2.2）；100/100 RESOURCE 全部有非空 required_slots（§2.3）。真因是槽位 authored 判据把示例句话题词（rain）当必答材料（§2.4 规律 + §2.2 逐层推演）。修法 accordingly：主修数据判据，不是补数据存在性。
2. **「UI 把非 SUCCESS 全显『没答中』」——不成立**。UI 有完整五态映射（web.py `_OUTCOME_CN` + components.js `OUTCOME_VERDICT_CN`，§3.4），体验者看到的正是 FAILURE 的忠实渲染。UI 侧的真实缺陷是 P0-2 的 append 累积与 skip 漏拆（§3.2）。

另登记一处**任务书外的顺带发现**：i-think 的 `detection_rules[2]` 声明 `"It is going to rain, I think."` 为 accepted realization，但它不在 `alternative_realizations` 白名单——同一语料内声明面与判分面自相矛盾（§2.4），A1 一并裁。

## 6. 遗留与风险

- **canonical 契约归属**：answer_key/teaching_content 五键在 canonical 六文档零记载（§1.3）——A2 若扩键，建议 DATA_MODEL §24 补一行归属注记（separate-document fact 措辞纪律）；纯 A1 不需要。
- **content_src 是多刀冻结面**：A1 的槽位重写与（可选的）alternative 补录都动它，需总控显式授权并带真值全扫义务（§4.1 A1 必随迁清单）。
- **假阳边界**：i-think 槽位改为单组后，`"I don't think so."` 类反向句也会 PARTIAL——建议该句入 evidence BOUNDARY 或登记 Revisit，不阻塞本刀。
- **A2 的证据身份语义**：若做，ATTEMPT_EVALUATOR_VERSION v0→v1 = 新证据身份（DATA_MODEL §25），必须行为变更单列披露；本报告默认不做。
- **spec 回填义务**：A3/B3 动 FRONTEND_SPEC 8.2.10 定稿字面（判词伴随行、参考答案区块），必须同刀回填，否则下一轮普查按假句打（v2-s 先例）。
- **P0-2 的回合边界自愈**：`showMoments` 整组重渲会清掉回合内累积——膨胀只在单张卡的活跃回合内可见；这解释了为何「3 封」而非「N 封」，修复后该形态不复存在。
- 未查面：`request_teaching`（USER_INITIATED 开卡面）与本刀无涉，未展开；`teaching/rollout.py` 观察面不涉判分，未展开。
