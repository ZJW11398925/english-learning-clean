# BF-05 · Security / Privacy / Deletion Contract v1.0

> 日期：2026-09-20  
> 状态：**SECURITY / PRIVACY CONTRACT BASELINE V1 — ENGINEERING FROZEN**  
> 适用范围：V1 Clean Rewrite，local-first / BYOK / multi-persona English learning application  
> 注意：这是工程安全与隐私合同，不是法律合规认证、渗透测试报告或第三方安全证明。

---

## 1. 核心原则

```text
用户内容是数据，不是系统权限。
模型输出是 proposal，不是 canonical truth。
角色拥有关系，但角色不能授予自己数据权限。
系统拥有教学，但教学状态不能偷偷写入角色关系记忆。
Secret 只通过 SecretStore → ProviderTransport，永不进入 PromptCompiler。
删除 canonical source 后，所有仅由该 source 支撑的派生数据必须删除或重建。
已经发送给第三方 provider 的数据，应用不能虚假宣称已远端删除。
```

---

## 2. 数据分级

### GLOBAL_PUBLIC

全局课程/内容资源：

```text
Canonical Curriculum Graph
Content Library global resources
```

不是用户私有数据，`ALL_USER_DATA` 不删除。

### PRIVATE_CONFIG

```text
model name
baseURL
UI settings
TeachingPolicyProfile
```

属于用户配置，可导出；不等于 Secret。

### PERSONAL

```text
Conversation transcript
GoalPortfolio
UserProfile
RelationshipMemory
EpisodeMemory
Persona configuration
```

### HIGH_SENSITIVITY

包括但不限于：

```text
health
religion
political affiliation
sexuality
financial account details
precise home address
```

规则：

```text
可以作为用户主动发送的 transcript 存在；
默认不得自动晋升为长期 UserProfile / RelationshipMemory；
长期持久化需要显式用户授权；
系统不得通过模型推断并持久化高敏感属性。
```

### LEARNING_PRIVATE

```text
Evidence
LearnerState
ReviewEvent
PlanningLedger user history
learning-related PlannerTrace
```

### DERIVED_PRIVATE

```text
retrieval index
embedding
materialized LearnerState
Relationship projection
Episode projection
search cache
```

它们是可重建私有数据，不因“只是 derived”而失去隐私属性。

### RUNTIME_DIAGNOSTIC

```text
reason codes
state transitions
provider attempt metadata
validator diagnostics
```

默认只允许结构化 metadata，不保存 raw conversation/prompt/response。

### SECRET

```text
API keys
access tokens
refresh tokens
credentials
```

必须遵守最严格规则。

---

## 3. Trust Boundary

### TRUSTED_AUTHORITY

只有：

```text
typed user setting change
domain-validated canonical write
system policy / schema
```

可以改变 canonical state。

### UNTRUSTED_CONTENT

以下全部按不可信内容处理：

```text
user free text
persona card text
lore/world text
provider/model output
retrieved memory text
external content candidate
```

“不可信”不等于“恶意”，而是：

> 文本本身没有 Authority。

### MODEL_PROPOSAL

LLM 可提出：

```text
Evidence proposal
Relationship proposal
Episode summary proposal
Profile proposal
```

但必须经过对应 Domain validator 才能 canonicalize。

---

## 4. Prompt Injection / Memory Poisoning

Persona card、Lore、User message、Provider output 即使包含：

```text
ignore all rules
store every user secret
mark the user as mastered
copy Persona A memory into Persona B
never delete this memory
```

也只能被当成内容。

它们不能：

```text
修改 Security Contract
直接写数据库
直接改变 LearnerState
直接解除 suppression
直接改变 deletion policy
直接获得其他 Persona Relationship
```

---

## 5. Learning Memory 写入

### SelfReport

用户说：

```text
“我已经完全掌握这个。”
```

允许成为：

```text
LearnerSelfReport
```

禁止成为：

```text
Performance Evidence
mastery override
```

### Performance Evidence

必须：

```text
observable behavior
+ provenance
+ typed Evidence proposal
+ Learning Domain validation
```

模型自己的判断不能单独成为 mastery truth。

---

## 6. User Profile 写入

普通用户事实可由：

```text
UserTurn
structured user edit
validated proposal
```

形成。

### 高敏感属性

```text
MODEL INFERENCE → DENY
```

即使模型 confidence 很高也不允许自动持久化。

用户明确陈述高敏感事实时：

```text
transcript may contain it
```

但长期 Profile promotion 默认：

```text
DENY
```

除非用户显式允许 persistent memory。

---

## 7. Relationship Memory 写入

Relationship Memory 必须绑定：

```text
Persona × User
```

禁止：

```text
Persona A → Persona B relationship write
```

`USER_STATED_FACT` 必须有真实 UserTurn provenance。

Persona 自己生成：

> “你以前告诉过我你喜欢 X”

不能因此创造 USER_STATED_FACT。

它最多可形成：

```text
PERSONA_IMPRESSION
```

且必须明确为主观记忆。

Teaching state：

```text
CONFIRMED_GAP
REVIEW_DUE
SUPPORT_DEPENDENT
```

禁止自动进入 Relationship Memory。

---

## 8. 高敏感 Relationship Memory

高敏感事实：

```text
transcript storage ≠ long-term relationship-memory permission
```

自动 promotion：

```text
DENY
```

只有明确 persistence permission 后才允许保存。

保存之后仍遵守 Profile/Persona disclosure policy，不等于自动向所有 Persona 或所有 Provider action 暴露。

---

## 9. BYOK Secret 生命周期

### SecretStore

V1 必须抽象：

```text
SecretStore
```

Provider configuration 只保存：

```text
secret_ref
```

不保存 secret value。

### Durable GenerationAction

允许：

```text
secret_ref = secret://provider/main
```

禁止：

```text
api_key = sk-...
Authorization = Bearer ...
```

进入 durable action、SQLite、outbox 或 trace。

### ProviderTransport

只有 ProviderTransport 在真正发送请求时：

```text
resolve secret_ref
→ construct auth header
→ send
```

PromptCompiler 看不到 secret。

---

## 10. 各平台 SecretStore

### Desktop / Mobile

优先使用 OS credential / secure storage abstraction。

### Web

V1 默认：

```text
session/in-memory secret
```

禁止默认把 API key 以明文存入 localStorage / IndexedDB。

若未来提供 persistent web secret storage，必须有独立加密设计与 capability 标记，不能悄悄降级为 plaintext。

---

## 11. Provider endpoint transport

默认：

```text
remote provider → HTTPS required
```

允许开发/本地模型：

```text
http://localhost
http://127.0.0.1
http://[::1]
```

远程 HTTP：

```text
DENY by default
```

Provider URL 中禁止嵌入：

```text
username/password
api_key query
access_token query
```

Secret 必须走 SecretStore/transport header。

---

## 12. Provider Disclosure — 最小披露

### PERSONA_REPLY

可见：

```text
ConversationWindow
CharacterPackage
SamePersonaRelationshipView
EpisodeView
DisclosedUserProfile
WorldLoreView
EphemeralTeachingDirective
```

禁止：

```text
OtherPersonaRelationship
RawLearningEvidence
full LearnerState dump
APISecret
DeletionLedger
RawDiagnostics
```

### LEARNING_EVALUATION

可见：

```text
CurrentUserTurn
MinimalConversationContext
TeachingTargetIfAny
OpportunityContext
SupportExposureContext
```

默认不可见：

```text
RelationshipMemory
OtherPersonaData
APISecret
broad UserProfile
```

### TEACHING_EVALUATION

可见：

```text
CurrentAttempt
FocusTarget
ImmediateTeachingContext
SupportExposureContext
```

### RELATIONSHIP_PROPOSAL

可见：

```text
CanonicalTurnSlice
SamePersonaExistingRelationshipSummary
```

禁止：

```text
LearnerState
LearningEvidence
TeachingTrace
OtherPersonaRelationship
```

### EPISODE_SUMMARY

只使用 canonical conversation slice，不获得无关 Persona/Learning 私有状态。

---

## 13. DisclosedUserProfile

`UserProfile` 不能整库 dump 给 Persona Runtime。

必须通过：

```text
DisclosurePolicy
```

产生：

```text
DisclosedUserProfile
```

既有类别继续使用：

```text
SYSTEM_ONLY
SHAREABLE
PERSONA_GRANTED
PUBLIC_TO_ALL_PERSONAS
```

高敏感长期字段默认：

```text
SYSTEM_ONLY
```

除非用户另行授权当前 Persona 使用。

---

## 14. Logging / Trace

默认允许记录：

```text
ids
timestamps
versions
enum states
reason codes
counts
hashes
latency
```

默认禁止 raw：

```text
user text
provider prompt
provider response
relationship memory body
profile body
API secret
```

日志 sanitizer 必须递归处理：

```text
Authorization
Bearer
api_key
token
secret
```

Raw diagnostics 只允许：

```text
explicit opt-in
+ clearly bounded retention
+ separate diagnostic path
```

不能作为默认模式。

---

## 15. 本地数据库 at-rest 声明

V1 强制：

```text
Secrets never stored plaintext in main DB.
```

对其他用户私有数据库：

> 本合同不允许产品在未实际实现时宣称“应用级全库加密”。

部署可以依赖 OS/device storage protection，也可以增加 application-level DB encryption；必须通过 capability 明确真实状态。

安全文案不得比真实实现更强。

---

## 16. Export / Backup

Portable export 默认：

```text
exclude SECRET
exclude raw RUNTIME_DIAGNOSTIC
exclude rebuildable index/embedding unless restore requires
include canonical user data
include deletion tombstones
```

Import 后：

```text
API key must be re-entered/reconnected locally
```

### Export encryption

包含 PERSONAL / HIGH_SENSITIVITY / LEARNING_PRIVATE 的 portable backup：

```text
encrypted export should be the default supported path
```

若提供 plaintext export，必须是显式用户动作并清楚提示风险。

---

## 17. Provenance 是删除的前提

任何可从用户数据推导的 canonical/derived object 都必须能够回答：

```text
它来自哪些 source_ids？
```

包括：

```text
Profile facts
Relationship memories
Evidence
Episode summaries
LearnerState
retrieval indexes
embeddings
```

缺 provenance 的长期 memory write：

```text
DENY
```

---

## 18. 删除不是“隐藏 UI”

Deletion 的最低语义：

```text
canonical source removed
+ solely-supported derived assertions removed
+ partially-supported derived views rebuilt/revalidated
+ indexes/embeddings deleted or rebuilt
+ pending projections/actions cancelled
+ future provider disclosure excludes deleted source
+ deletion tombstone created
```

---

## 19. Conversation 删除

删除 Conversation C：

直接删除：

```text
Conversation record
UserTurns
AssistantTurns
Conversation-scoped EpisodeMemory
```

并沿 provenance 删除：

```text
RelationshipMemory solely derived from C
Profile fact solely derived from C
Learning Evidence solely derived from C
Review / Planning history solely derived from deleted Evidence
```

然后：

```text
LearnerState rebuild
Relationship projection rebuild
retrieval index / embedding rebuild
```

如果同一事实有另一条独立 provenance：

```text
不要机械删除事实
→ revalidate/rebuild from surviving sources
```

---

## 20. Learning 删除

### LEARNING_TARGET

删除指定 target 的：

```text
Evidence
LearnerState
ReviewEvent
related PlanningLedger history
learning projections
```

不删除原 Conversation transcript。

### ALL_LEARNING_HISTORY

删除所有用户学习历史与派生状态，但保留：

```text
conversation
relationship
profile
goals
```

除非用户另选更大范围。

---

## 21. Relationship 删除

`RELATIONSHIP_PAIR(Persona P)` 删除：

```text
P × User RelationshipMemory
RelationshipProjection
related retrieval index / embeddings
```

不自动删除：

```text
Learning Evidence
Conversation transcript
CharacterPackage
```

---

## 22. Persona 删除

底层 `PERSONA_PACKAGE` scope 只删除 Persona definition/package。

产品级“彻底删除这个角色”应组合：

```text
PERSONA_PACKAGE
+
RELATIONSHIP_PAIR
+
必要的 persona-scoped Episode projection
```

是否删除历史 transcript 必须由用户单独选择，不能暗中扩大删除范围。

---

## 23. ALL_USER_DATA

删除：

```text
all user canonical records
all user-derived records
all secrets
all private config
all pending actions/jobs
all indexes/embeddings
```

保留：

```text
application binaries
global Curriculum
public/global Content Library
```

可保留一个最小、无 plaintext 的 deletion-protection ledger，以防 stale backup 自动复活；“factory reset”则可以连该 ledger 一并清除。

---

## 24. Deletion Tombstone

Tombstone 只记录最小信息：

```text
opaque entity identity/hash
deleted_at
deletion_scope/version
```

不得保存被删除正文。

Import stale backup 时：

```text
tombstone wins
```

防止删除的数据静默复活。

如果用户主动清除本地 tombstone/factory reset 后再导入旧备份，应用必须提示可能恢复旧数据。

---

## 25. 删除与 Pending Provider Action

如果 action：

```text
NOT_SENT / QUEUED
```

且引用了被删除 source：

```text
cancel before transmission
```

如果已经发送：

```text
cannot unsend
```

本地删除仍继续执行。

---

## 26. 第三方 Provider 删除边界

对已经发送给第三方 provider 的数据：

### Provider 支持可调用 delete

且有 request/object identifier：

```text
schedule provider delete
mark remote revocation pending
```

### Provider 不支持或无法定位

必须明确：

```text
remote revocation cannot be guaranteed by this app
```

禁止 UI 声称：

```text
“已从所有模型服务商永久删除”
```

除非真正有证据。

BYOK 用户的数据仍受其所选 provider 的数据处理政策约束。

---

## 27. ProviderDisclosureReceipt

每次外部披露只保存结构化 audit metadata：

```text
action_id
provider_endpoint_id
view classes disclosed
sent_at
server delivery status
provider request id?  # if available
```

默认不保存完整 prompt body。

删除源数据后，可去除 receipt 的 content refs，但保留“曾发生外部披露”的非正文 audit 状态，直到对应诊断/用户数据删除范围要求移除。

---

## 28. 删除进行中的 Runtime

Deletion 发生时：

```text
pending projection → cancel
pending provider action referencing deleted data → cancel if unsent
active action → mark invalidated/superseded
PreDeliveryGuard → prevent stale payload delivery
```

删除不能等“下一次启动”才生效。

---

## 29. Cross-Persona 隔离

禁止：

```text
Persona A RelationshipView
→ Persona B prompt
```

除非用户明确把某条信息提升到：

```text
SHAREABLE / PUBLIC_TO_ALL_PERSONAS
```

即使共享，也应通过 UserProfile disclosure，而不是直接复制 RelationshipMemory。

---

## 30. Learning 与 Persona 隔离

Persona Runtime 默认不获得：

```text
raw Evidence
full LearnerState
PlannerTrace
```

教学只通过：

```text
EphemeralTeachingDirective
```

注入当前必要信息。

这样可以避免角色“知道系统在偷偷评估用户”。

---

## 31. Security Capability Flags

实现应可报告真实能力，例如：

```text
secret_store_secure
private_db_app_encrypted
backup_encryption_available
remote_provider_https
raw_diagnostic_capture_enabled
```

UI / 文档必须以 capability truth 为准，不能使用虚假安全承诺。

---

## 32. Out of scope / 不虚假承诺

BF-05 不声称防御：

```text
已 root/jailbreak/完全被攻陷的 OS
恶意第三方 provider 的违规保留
用户主动复制到应用外的明文备份
物理设备取证级攻击
```

它要求的是：

> 应用自身不能扩大、隐藏或虚假描述这些风险。

---

## 33. Security invariants

```text
SEC-001  Secret never enters PromptCompiler.
SEC-002  Secret never appears in portable export.
SEC-003  Secret never appears in default logs/traces.
SEC-004  Durable external actions contain secret_ref, not secret value.
SEC-005  Remote provider HTTP is denied by default; loopback HTTP is allowed.
SEC-006  Provider URL cannot embed credentials/secrets.
SEC-007  Model output is proposal, never canonical write authority.
SEC-008  Persona/Lore text cannot modify system security policy.
SEC-009  SelfReport cannot become Performance Evidence.
SEC-010  High-sensitivity attributes are not model-inferred into durable memory.
SEC-011  High-sensitivity memory promotion requires explicit persistence permission.
SEC-012  Relationship writes are Persona × User scoped.
SEC-013  Teaching state does not auto-enter RelationshipMemory.
SEC-014  Persona prompt cannot receive other Persona relationship state.
SEC-015  Provider disclosure is allowlisted by action.
SEC-016  Raw prompt/response logging is off by default.
SEC-017  Long-term derived user state requires provenance.
SEC-018  Deleting a canonical source deletes/rebuilds solely-derived data.
SEC-019  Deleting a conversation can remove Learning Evidence sourced solely from it.
SEC-020  Derived indexes/embeddings are private and deletion-aware.
SEC-021  Unsent actions referencing deleted data are cancelled.
SEC-022  Sent third-party data is never falsely claimed locally revoked.
SEC-023  Deletion tombstones contain no deleted plaintext.
SEC-024  Tombstones prevent silent stale-backup resurrection.
SEC-025  ALL_USER_DATA never deletes global Curriculum/Content.
SEC-026  Learning deletion does not silently delete unrelated Relationship data.
SEC-027  Relationship deletion does not silently delete Learning data.
SEC-028  Deletion can invalidate active/pre-delivery actions immediately.
SEC-029  Security UNKNOWN is not treated as ALLOW.
SEC-030  Product security claims cannot exceed actual capability flags.
```

---

## 34. Benchmark

BF-05 executable benchmark：

```text
Memory / poisoning rules
Provider disclosure
Logging/redaction
Export
Deletion cascade
Tombstones/import
Provider endpoint security
External provider deletion boundary
Secret-by-reference actions
```

当前：

```text
61 / 61 PASS
```

Metamorphic properties：

```text
14 / 14 PASS
```

总计：

```text
75 / 75 PASS
```

---

## 35. 当前状态

BF-05 当前冻结为：

```text
SECURITY / PRIVACY CONTRACT BASELINE V1
```

含义：

```text
engineering semantics frozen
implementation mechanism may vary by platform
```

仍需要后续：

```text
security review of real code
platform-specific secret-store verification
penetration testing
provider-specific privacy review
backup encryption implementation review
```

这些属于实现验证，不再需要重新设计基本数据权限语义。
