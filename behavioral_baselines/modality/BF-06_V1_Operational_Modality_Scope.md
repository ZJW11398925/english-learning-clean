# BF-06 · V1 Operational Modality Scope

> 日期：2026-09-20  
> 状态：**MODALITY SCOPE BASELINE V1**  
> 目的：明确“学习目标是什么”“系统实际观察到什么”“界面通过什么通道交互”三者之间的边界，防止纯文本系统虚假声称已经测量 Speaking / Listening。

---

## 1. 三个不同概念必须拆开

RC2 中 `modality` 一词曾同时承担多种语义。

BF-06 正式拆成：

```text
GoalModality
EvidenceModality
InteractionChannel
```

### GoalModality

表示用户长期想提升什么：

```text
SPEAKING
LISTENING
READING
WRITING
```

它属于：

```text
LearningGoalPortfolio
```

### EvidenceModality

表示某条 Performance Evidence 实际来自什么类型的观察：

```text
V1:
  TEXT_PRODUCTION
  TEXT_COMPREHENSION

Future:
  VOICE_PRODUCTION
  AUDIO_COMPREHENSION
```

它属于：

```text
EvidenceClaim
LearnerTargetState
```

### InteractionChannel

表示输入/输出经过什么物理通道：

```text
V1:
  TEXT

Future:
  VOICE
  AUDIO
```

Channel 本身不等于能力证据。

---

## 2. V1 当前真正能测什么

### TEXT_PRODUCTION

包括：

```text
typed free conversation
typed elicited response
typed TeachingMoment attempt
explicit writing task response
```

它可以支持：

```text
target-level lexical/grammar control
typed conversational expression
accuracy
pragmatic/register control
support dependency
transfer across text contexts
```

它**不能**直接支持：

```text
speaking fluency
pronunciation
listening comprehension
voice turn-taking timing
prosody
```

### TEXT_COMPREHENSION

只有在存在 genuine comprehension opportunity 时建立，例如：

```text
explicit written passage
→ comprehension question
→ user answer
```

它可以支持 target-level：

```text
recognition/comprehension
```

但 generic chat 中“用户看到了系统文字”不自动形成 reading mastery evidence。

---

## 3. V1 暂不直接观测

由于 full voice runtime deferred：

```text
VOICE_PRODUCTION
AUDIO_COMPREHENSION
```

在 V1 core runtime 中：

```text
UNAVAILABLE
```

因此不能声称当前系统已经直接测量：

```text
SPEAKING
LISTENING
```

---

## 4. IELTS Speaking 的正确产品语义

允许：

```text
IELTS Speaking preparation
```

因为 typed conversational practice 可以训练：

```text
idea formulation
lexical choice
grammar
discourse organization
response development
register/pragmatic choices
```

但它只产生：

```text
TEXT_PRODUCTION Evidence
```

因此不允许从纯文本训练直接输出：

```text
your speaking fluency is X
your pronunciation improved
your listening is strong
your IELTS Speaking band is 7
```

除非未来有：

```text
VOICE_PRODUCTION Evidence
+
validated assessment module
```

---

## 5. Goal relevance != mastery projection

`SPEAKING` goal 可以提高某个 text-production target 的：

```text
goal_relevance
```

例如：

```text
IELTS Speaking goal
→ practice giving reasons in typed conversation
```

但：

```text
Goal relevance
```

不能改变 Evidence modality。

因此：

```text
typed response
+ SPEAKING goal
→ TEXT_PRODUCTION Evidence
not VOICE_PRODUCTION Evidence
```

---

## 6. Goal relation levels

BF-06 定义：

```text
NONE
PREPARATORY
DIRECT_TARGET_LEVEL
```

### TEXT_PRODUCTION → SPEAKING

```text
PREPARATORY
```

### TEXT_PRODUCTION → WRITING

Generic chat：

```text
PREPARATORY
```

Explicit writing task：

```text
DIRECT_TARGET_LEVEL
```

注意即使 direct target-level relevance 成立，LearnerState 仍按：

```text
TEXT_PRODUCTION
```

保存，不建立一个模糊的全局“WRITING mastered”数字。

### TEXT_COMPREHENSION → READING

显式 comprehension task：

```text
DIRECT_TARGET_LEVEL
```

### TEXT_COMPREHENSION → LISTENING

```text
NONE
```

---

## 7. State scope 修订

RC2 的：

```text
Target × SkillModality
```

在 V1 implementation 中应规范为：

```text
Target × EvidenceModality
```

即：

```text
RESOURCE × expr.X × TEXT_PRODUCTION
CAPABILITY × cap.Y × TEXT_PRODUCTION
RESOURCE × expr.Z × TEXT_COMPREHENSION
```

未来再加入：

```text
VOICE_PRODUCTION
AUDIO_COMPREHENSION
```

这比直接使用 `SPEAKING / WRITING / LISTENING / READING` 作为 Evidence key 更精确。

---

## 8. EvidenceClaim 字段修订

建议 canonical 字段从：

```text
skill_modality
```

改为：

```text
evidence_modality
```

Goal 相关性另存于 Planner/Goal View，不写回 Evidence。

`modality_novelty` 也应改为：

```text
evidence_modality_novelty
```

---

## 9. `fluency` 字段的 V1 边界

RC2 `EvidenceClaim` 中存在：

```text
fluency?
```

BF-06 冻结：

```text
TEXT_PRODUCTION
TEXT_COMPREHENSION
→ fluency must not mean speaking fluency
```

V1 core 建议：

```text
fluency = null
```

文本响应时间、打字速度、停顿时间可以记录为 interaction telemetry，但不能投影到：

```text
SPEAKING_FLUENCY
```

未来 `VOICE_PRODUCTION` 上线后，应显式使用：

```text
speaking_fluency
pronunciation
```

而不是继续复用含义模糊的 `fluency`。

---

## 10. ASR 不改变 Evidence 来源

未来用户真实说话：

```text
voice audio
→ ASR transcript
```

即使 evaluator 最终读取文本 transcript：

```text
EvidenceModality = VOICE_PRODUCTION
```

因为证据来源是：

```text
user voice production
```

不是 transcript 的表示格式。

因此必须区分：

```text
source modality
representation format
```

---

## 11. Listening attribution contamination

未来听力任务只有在：

```text
audio actually delivered
+
genuine comprehension opportunity
+
answer given before transcript exposure
```

时，才允许：

```text
AUDIO_COMPREHENSION Evidence
```

如果用户在回答前看到了完整 transcript：

```text
audio-specific attribution contaminated
```

不能把正确答案写成 listening comprehension mastery。

---

## 12. Reading attribution

系统普通文字消息：

```text
用户看到了
```

不等于：

```text
TEXT_COMPREHENSION success
```

必须存在：

```text
Opportunity
+
response/attempt
+
target-specific evaluation
```

才能产生 comprehension Evidence。

---

## 13. Writing attribution

Generic typed chat：

```text
TEXT_PRODUCTION
```

可为 Writing goal 提供 preparatory value，但不能自动声称：

```text
structured writing ability mastered
```

只有明确 writing-task context：

```text
genre
prompt
writing objective
evaluation basis
```

才允许 `WRITING` goal relation 达到：

```text
DIRECT_TARGET_LEVEL
```

但 Evidence state 仍保持 `TEXT_PRODUCTION` + context/genre provenance。

---

## 14. Unsupported goal 不制造不可能偿还的 CoverageDebt

如果 V1 当前：

```text
voice_input = unavailable
listening evaluator = unavailable
```

那么：

```text
SPEAKING direct-modality obligation
LISTENING direct-modality obligation
```

必须标：

```text
UNAVAILABLE_IN_CURRENT_RUNTIME
```

并且：

```text
do not accrue direct CoverageDebt
```

否则系统会永久认为：

```text
“用户口语一直没覆盖”
```

然后不断尝试插入一个自己根本无法直接验证的任务。

允许：

```text
preparatory text training
```

继续获得 Goal relevance。

---

## 15. Planner semantics

Planner Candidate 应区分：

```text
goal_relation:
  NONE
  PREPARATORY
  DIRECT_TARGET_LEVEL
```

`PREPARATORY` 可以增加：

```text
goal_relevance
```

但不能伪装成：

```text
direct modality coverage repayment
```

---

## 16. Scheduler semantics

Scheduler 只能基于实际 Evidence modality 创建对应 review obligation。

例如：

```text
TEXT_PRODUCTION Evidence
→ text-production retrieval review
```

不能因为用户 goal 是 Speaking，就创建：

```text
SPEAKING pronunciation review due
```

---

## 17. Product claims

V1 可以说：

```text
帮助你练习如何用英语组织和表达真实想法
帮助你准备 IELTS Speaking 中的词汇、语法、结构与回答内容
根据你的文字表达表现调整后续练习
在明确阅读任务中跟踪目标级文本理解表现
```

V1 不应说：

```text
我们已经测量你的真实口语流利度
我们已经测量你的发音
我们已经测量你的听力理解
你的 IELTS Speaking 是 X 分
你的 typed chat mastery 就等于 Speaking mastery
```

---

## 18. UI / Reporting

状态页面必须优先显示：

```text
Typed conversational production
Text comprehension
```

而不是在没有 voice Evidence 时显示：

```text
Speaking: 78%
Listening: 65%
```

如果用户设置 Speaking goal，可显示：

```text
Speaking goal
Direct voice evidence: not yet available in this runtime
Text-based speaking preparation: active
```

这是诚实的 Goal progress，而不是虚构 modality mastery。

---

## 19. V1 Evidence Modality baseline

```text
Operational:
  TEXT_PRODUCTION
  TEXT_COMPREHENSION

Reserved for future runtime:
  VOICE_PRODUCTION
  AUDIO_COMPREHENSION
```

---

## 20. Normative invariants

```text
MOD-INV-001
GoalModality != EvidenceModality != InteractionChannel.

MOD-INV-002
Goal weighting cannot rewrite Evidence modality.

MOD-INV-003
Typed chat cannot produce VOICE_PRODUCTION Evidence.

MOD-INV-004
Typed text cannot directly support pronunciation or speaking-fluency state.

MOD-INV-005
Text comprehension cannot directly support listening-comprehension state.

MOD-INV-006
SelfReport/exposure alone creates no modality performance evidence.

MOD-INV-007
Explicit comprehension Opportunity is required for TEXT_COMPREHENSION.

MOD-INV-008
Generic typed chat is not automatically structured-writing mastery.

MOD-INV-009
Explicit writing task can have DIRECT_TARGET_LEVEL writing relevance while Evidence remains TEXT_PRODUCTION.

MOD-INV-010
ASR transcript representation does not convert voice-source evidence into text-source evidence.

MOD-INV-011
Transcript exposure before listening response invalidates independent audio attribution.

MOD-INV-012
Unsupported direct modalities do not accrue impossible CoverageDebt.

MOD-INV-013
Speaking-preparation relevance does not equal Speaking measurement.

MOD-INV-014
No IELTS Speaking band prediction without a separately validated assessment module and voice evidence.
```

---

## 21. Benchmark

BF-06 reference benchmark：

```text
40 / 40 PASS
```

Metamorphic properties：

```text
12 / 12 PASS
```

Total：

```text
52 / 52 PASS
```

覆盖：

```text
typed conversation
explicit writing task
text comprehension
voice unavailable
audio unavailable
future voice/audio mapping
goal relevance
pronunciation/fluency prohibition
listening prohibition
IELTS claim boundary
CoverageDebt pause
ASR source semantics
transcript contamination
state-key semantics
```

---

## 22. Current status

BF-06 正式标记：

```text
MODALITY SCOPE BASELINE V1
```

这关闭了外部评审指出的：

> V1 明明没有完整 voice runtime，却在 schema/产品语义上可能暗示已测量 Speaking/Listening。

下一步：

```text
BF-07 — Local Runtime Profile
```
