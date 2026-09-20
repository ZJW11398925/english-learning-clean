# PRODUCT_CONTRACT.md

> 状态：CANONICAL IMPLEMENTATION BASELINE V1  
> 产品：英语客厅 / 对话客厅  
> 目标：定义 V1 Clean Rewrite 必须兑现的产品行为，不描述具体技术实现。

---

## 1. Product Thesis

产品让成年人以自然对话为中心学习英语。用户可以与自定义 AI 角色建立持续关系，同时系统在不破坏对话的前提下识别真实表达需求、组织系统学习、安排复习与迁移，并帮助用户把“自己真正想表达的意思”转化成更自然、准确、灵活的英语。

核心不是把聊天包装成练习题，而是：

> **以用户真实想表达的意思为教学入口，以课程系统保证长期覆盖，以行为证据决定学习状态。**

---

## 2. Product Principles

### 2.1 角色拥有关系，系统拥有教学

- Character / Relationship 决定角色是谁、与用户是什么关系、如何说话。
- Learning / Curriculum / Teaching 决定学什么、会什么、何时教学、怎样教学。
- 角色可以执行教学表达，但不能拥有学习真值。
- 教学状态不能自动进入 Relationship Memory。
- Persona subjective impression 不能自动变成 Teaching Fact。

### 2.2 不缩减用户原意

系统的最终 target 是：

```text
用户真正想表达的完整意思
```

支架可以暂时简化，但不能通过“把用户原意砍短”伪造成功。

### 2.3 自然对话与系统课程并存

产品同时支持：

```text
娱乐/关系优先
平衡
学习优先
```

不同模式共享同一 Learning truth，只改变教学策略与介入频率。

### 2.4 不把每轮对话都变成课堂

`NO_TARGET` 是合法且常见结果。尤其 Lounge 模式下，大量 turn 只进行自然对话完全正确。

### 2.5 学习状态来自证据

以下不等于“会了”：

```text
系统讲过
用户看过答案
用户点“知道了”
用户复述刚显示的完整答案
用户说“我会”
某个词属于考试词表
本轮没出现错误
```

### 2.6 UNKNOWN 不是差

系统不知道 ≠ 用户不会。未知能力优先通过自然观察或低成本 probe 减少不确定性。

---

## 3. User-facing Learning Modes

### Lounge / Entertainment-first

目标：

```text
conversation continuity > teaching frequency
```

特征：

- 自动打断少。
- 优先 Reactive / Opportunistic。
- Proactive curriculum 低频。
- 高 interruption cost。
- 更偏自然 elicitation / silent observation。
- 允许高比例 `NO_TARGET`。

### Balanced

目标：

```text
conversation + systematic progress
```

特征：

- 当前表达需求与 review/curriculum 同时参与 Planner。
- 适度 proactive。
- 保留明显课程进度感，但不菜单化。

### Study-first

目标：

```text
explicit practice density > free-flow continuity
```

特征：

- 更积极 probe/review/curriculum progression。
- 更高 practice density。
- 更低 activation threshold。
- 仍然使用同一 Evidence / Learning / TeachingMoment truth。

---

## 4. Goal Model

`TeachingPolicyProfile` 回答：

```text
HOW
```

`LearningGoalPortfolio` 回答：

```text
WHAT
```

两者正交。

### 4.1 Context / Domain Goals

```text
DAILY_CONVERSATION
SOCIAL_RELATIONSHIP
ACADEMIC
WORKPLACE
TRAVEL
DEBATE
PUBLIC_SPEAKING
TECHNICAL
FICTION_ROLEPLAY
```

### 4.2 Genre / Discourse Goals

```text
CASUAL_CHAT
NARRATIVE
ARGUMENTATION
EXPOSITION
DESCRIPTION
PERSUASION
DAILY_WRITING
ACADEMIC_WRITING
CREATIVE_WRITING
LITERARY_READING
POETRY_READING
POETRY_WRITING
```

### 4.3 Goal Modality Weights

`GoalModality` 表示用户长期希望提升的技能目标：

```text
SPEAKING
LISTENING
READING
WRITING
```

它属于 `LearningGoalPortfolio`，不能直接改写 Performance Evidence 的来源。

V1 operational `EvidenceModality`：

```text
TEXT_PRODUCTION
TEXT_COMPREHENSION
```

Future：

```text
VOICE_PRODUCTION
AUDIO_COMPREHENSION
```

界面/设备通道单独称 `InteractionChannel`（V1=`TEXT`；未来可有 `VOICE/AUDIO`）。

因此：

```text
IELTS Speaking preparation != Speaking measurement
typed chat != VOICE_PRODUCTION Evidence
```

纯文本 V1 可以训练口语考试所需的表达组织、词汇、语法、论证与语用选择，但不得据此声称已经测量 pronunciation、speaking fluency、listening comprehension 或直接给出 IELTS Speaking band。

### 4.4 Expressive Depth

```text
FOUNDATIONAL
FUNCTIONAL
NATURAL
NUANCED
ADVANCED
```

这是内部偏好层，不替代 CEFR。

### 4.5 External Assessment Goals

可包含：

```text
CET4
CET6
IELTS
TOEFL
```

并保存 target score/date/skill priorities。

考试包只映射和重加权共享 Curriculum Graph，不创建独立重复课程树。

### 4.6 Register / Style

```text
CASUAL
NEUTRAL
POLITE
FORMAL
ACADEMIC
PERSUASIVE
LITERARY
PLAYFUL
```

---

## 4.7 Goal / Policy / Profile Authority

以下长期用户配置由 `User Configuration/Profile` bounded context 持有：

```text
UserProfile
DisclosurePolicy
LearningGoalPortfolio
TeachingPolicyProfile
SessionFocus
```

它们可以影响 Planner / Persona Runtime 的 view，但不能直接改写 Learning Evidence 或 Learner State。

`World/Lore` 的 canonical truth 由 Persona/World authority 管理；不同 Persona 的 Relationship Memory 仍保持隔离。

---

## 5. Teaching Experience Contract

### 5.1 Automatic teaching requires authorization

自动 TeachingMoment 只有在：

```text
Planner SELECT
+
Teaching Gate ALLOW
```

后创建。

User-initiated teaching 也进入统一 authorization/trace path，但使用 user-requested/manual policy context，不与自动教学共享相同 interruption threshold。

### 5.2 User intent has scope authority

用户明确说：

```text
“这句怎么说？”
“练一下这个”
```

当前 targeted request 约束候选范围；无关的 overdue review / coverage debt 不得抢占。

### 5.3 Just Chat is binding

用户进入：

```text
JUST_CHAT
```

自动教学候选 hard excluded，直到用户显式重新发起学习。

### 5.4 One Focus Target

一个 TeachingMoment：

```text
1 FocusTarget
0–2 SupportingTargets
```

不在一次纠错中继续连环开新点。

### 5.5 Hint ladder

系统可使用：

```text
SEMANTIC_HINT
STRUCTURAL_HINT
PARTIAL_FORM
FULL_REVEAL
```

但具体策略按 mode/profile 配置。

### 5.6 Full reveal changes evidence meaning

当 `ExposureEstimate` 被归因为 FULL exposure 后，本 TeachingMoment 后续复述不再算 independent production；若 exposure 不确定，按 conservative upper-bound support 归因。

### 5.7 Skip / reject / topic shift

这些结束或中止 TeachingMoment，但不自动产生负向 mastery evidence。

### 5.8 Teaching completion ≠ mastery

完成一次教学 episode 不代表掌握。

### 5.9 TeachingPointResolved ≠ SentenceFullyNatural

解决一个焦点问题，不能宣称整句完全地道。

---

## 6. Expression-driven + Curriculum-driven

### Track A — Expression-driven

来源：

```text
CURRENT_USER_ERROR
EXPRESSION_NEED
NATURAL_USE_EXPANSION
PRAGMATIC_REGISTER_OPPORTUNITY
MANUAL_USER_REQUEST
CURRENT_CONTEXT_TRANSFER_OPPORTUNITY
```

负责：

> 此刻什么与用户真实表达最相关。

### Track B — Curriculum-driven

来源：

```text
CONFIRMED_GAP
SCHEDULED_REVIEW
UNKNOWN_PROBE
TRANSFER_EXPANSION
SUPPORT_WITHDRAWAL
CORE_COVERAGE
GOAL_SPECIFIC_TARGET
COVERAGE_DEBT
```

负责：

> 长期什么不能一直没学。

两条 lane 进入同一 Planner，不做成两个系统。

---

## 7. Curriculum Contract

Curriculum Graph 回答：

```text
长期要发展什么能力
```

Canonical node ontology：

```text
CommunicativeCapability
LanguageFunction
GrammarConstruction
LexicalResource
DiscourseAndInteractionStrategy
PragmaticAndRegisterResource
PhonologyAndListeningResource
```

Topic 只是 context/scenario metadata，不作为主课程脊柱。

Curriculum node ≠ Lesson ≠ TeachingMoment。

---

## 8. Content Contract

Content Library 回答：

```text
具体用什么资源教
```

层级：

```text
Source Facts
Normalized Language Knowledge
Pedagogical Annotation
```

LLM 可以生成候选、例句、映射、错误候选，但不能静默 canonicalize。

`content.db` 是 build artifact；作者源在 version-controlled `content_src/*`。

自动 error-triggered teaching 默认要求 R4；如未来引入等价 detector certification，必须有独立的结构化认证契约，不能以模型自报 confidence 代替。R3 可正常 teach/review/transfer。

---

## 8.1 Content Readiness（Normative）

V1 使用五级 readiness：

```text
R0 INDEXED
  source / assessment membership / canonical form 可定位；
  仅用于搜索、覆盖统计和来源追踪。

R1 LEXICALLY_RESOLVED
  POS / sense / basic definition / forms 已可追溯。

R2 PLANNER_READY
  已具备 CurriculumLink、PedagogicalProfile、
  goal/pack overlay、register/usage-modality/context 等 Planner 所需信息。

R3 TEACHING_READY
  已具备 reviewed explanation/note、可用 example policy、
  必要 contrast/usage，以及需要时的 TypicalError。

R4 DETECTION_READY
  在 R3 基础上具备 detection policy / recognition rules /
  negative fixtures / false-positive boundaries，
  可支持高置信 automatic error-triggered teaching。
```

默认：

```text
R0/R1 → 不进入自动 Teaching Frontier
R2    → Planner / probe 可用，默认不自动教学
R3    → teach / review / transfer 可用
R4    → automatic error-triggered teaching 可用
```

V1 不把“模型自称高置信”自动视为 R4 等价认证。

---

## 9. Memory Product Contract

### User Profile

全局事实/偏好/设置，受 disclosure policy 控制。

### Learning Memory

系统拥有，跨角色聚合学习证据与状态。

### Character Card / CharacterPackage

角色 identity/personality/background/speech style/values/boundaries/scenario/lore。

### Relationship Memory

Persona × User 私有关系记忆。

### Episode Memory

当前会话/故事/近期事件/未决上下文。

### World/Lore

场景、NPC、地点、规则。

### Retrieval Index

可重建，不是 source of truth。

---

## 10. Persona Privacy Contract

允许：

```text
Learning evidence 跨 Persona 聚合
```

禁止：

```text
Relationship Memory 跨 Persona 泄漏
```

Planner 可以知道：

```text
某 target 有跨 Persona transfer evidence
```

不能因此看到另一个 Persona 的私有关系内容。

---

## 11. BYOK / Local-first

V1 继续支持：

```text
OpenAI-compatible baseURL + key + model
```

Key 本地保存。

浏览器端任意 baseURL 可能受 CORS/preflight/origin 限制；协议兼容不等于 browser-compatible。

Local-first 不承诺自动跨设备连续性。V1 更适合：

```text
versioned export / backup / import
```

未来再扩展同步。

---


## 11.1 Security / Privacy / Deletion Product Contract

V1 将用户文本、学习状态、关系记忆与密钥视为不同的数据等级。

```text
API key / token
→ SecretStore only
→ not promptable
→ not loggable
→ not included in portable export
```

Provider 只获得完成当前 action 所需的最小 disclosure view；Persona reply 不自动获得 raw Learning Evidence，Learning evaluator 不自动获得 Relationship Memory。

用户自由文本、Persona card、Lore、provider output 与 retrieved memory 均属于 **untrusted content**，不能通过提示词获得 Domain write authority。模型只能提出 proposal，canonical write 必须经过相应 Domain validator。

高敏感信息可以存在于用户主动发送的 transcript，但默认不得自动晋升为长期 UserProfile/RelationshipMemory；持久保存需要显式用户许可，模型不得推断高敏感属性后长期保存。

删除是 provenance-aware operation，而不是 UI hide：删除 canonical user source 后，solely-derived Relationship/Episode/Learning/Index/Embedding 等数据必须删除或重建；pending action/job 必须取消；删除 tombstone 不保存被删 plaintext，并防止旧备份静默复活。

对已经发送给第三方 Provider 的数据，产品只能承诺本地删除与停止未来披露；若 Provider 无删除 API/无法定位远端数据，不得声称“已从第三方永久删除”。

## 12. Product Non-goals for V1

V1 不要求：

```text
完整多角色 Scene Runtime
真正云端多设备实时同步
复杂 Bayesian/IRT learner model
全量 5418 词 Teaching-ready
每轮自动纠错
在无 VOICE_PRODUCTION Evidence 时判断口语流利度/发音/听力
用一个总分代表“英语水平”
```

---

## 13. Product Success Metrics

禁止单独优化：

```text
teaching selection rate
```

建议至少观察：

```text
user-request fulfillment
unwanted interruption rate
skip/reject after auto teaching
conversation continuation
NO_TARGET appropriateness
overexposure rate
coverage starvation
review completion
transfer evidence gain
uncertainty reduction
supported → independent progression
```

Lounge 模式高 `NO_TARGET` 比例可能是健康表现。

---

## 14. Product-level Invariants

```text
P-INV-001  用户明确请求优先于无关 curriculum debt。
P-INV-002  JUST_CHAT 不被 coverage debt 突破。
P-INV-003  UNKNOWN 不按 WEAK 处理。
P-INV-004  一次 TeachingMoment 只有一个 FocusTarget。
P-INV-005  Skip/Reject 不等于能力失败。
P-INV-006  完整答案曝光后，本 Moment 不生成 independent evidence。
P-INV-007  角色关系与系统学习真值分离。
P-INV-008  自动教学可以被 NO_TARGET / Gate DENY 阻止。
P-INV-009  自然对话本身是正常产品状态。
P-INV-010  产品不得用“已掌握/整句地道”等强结论超越 Evidence。
P-INV-011  GoalModality 不得改写 EvidenceModality。
P-INV-012  纯文本 V1 不得声称直接测量 Speaking/Listening。
P-INV-013  用户自由文本/Persona/Lore/模型输出不得获得 canonical memory write authority。
P-INV-014  Secret 不得进入 prompt、普通日志或 portable export。
P-INV-015  删除 canonical user source 必须级联删除/重建 solely-derived private state。
```
