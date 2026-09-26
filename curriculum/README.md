# curriculum/ — Curriculum authoring source of truth（P5-0 seed）

作者源（docs/DATA_MODEL.md §24 "Content authoring source of truth: `content_src/*`
`curriculum/*`"）。capability registry / curriculum links / prerequisites 三类
**curriculum 面**数据在此落地，由 `src/elc/content/build.py` 与 `../content_src/`
一同确定性生成 `content.db`（§2 物理 profile 只有 `content.db`，无 curriculum.db）。

数据来源与总口径见 `../content_src/README.md`（同一迁移：P3-1A/P3-1B 的 14 个
validated target；不扩内容）。

## 文件布局

```text
curriculum/
  index.json                    # 索引：curriculum_version + 能力清单 + 链接/前置文件
  capabilities/<capability_id>.json
  links.json                    # CurriculumLink（§24.7 七列逐字）
  prerequisites.json            # prerequisite 边（§7：edge_type + strength）
  README.md                     # 本文件
```

## 映射规则

### C1 — 能力注册表（DOMAIN_MODEL §7）

`capabilities/<capability_id>.json` 是一个 capability registry 节点，字段**恰好**
四列，形状即 `elc.curriculum.types.CapabilityNodeRecord`：

```text
curriculum_node_id   # V1 registry：一个 capability 一个节点，节点 id = capability id
capability_id        # fixture 的 CAPABILITY target id 逐字（cap-*）
family               # DOMAIN_MODEL §7 十四族词表
level                # capability 层级；本语料为 Level-2 能力（§7 registry 所述层级）
```

`family` 由 fixture target id 的语义段逐条**显式写明**（`cap-ref-*` → REF、
`cap-stance-*` → STANCE、`cap-disc-*` → DISC、`cap-eval-*` → EVAL、
`cap-interact-*` → INTERACT）；build 只校验词表成员，不替作者推断。

### C2 — CurriculumLink（§24.7 / DATA_MODEL §13）

`links.json` 的 `links[]` 每行**恰好**七列（§24.7 逐字）：

```text
resource_id / node_id / relation / strength / primary_flag /
editorial_status / rationale
```

- `relation` ∈ §24.7 五词表（REALIZES / SUPPORTS / EXEMPLIFIES / CONTRASTS /
  REQUIRES）；
- **现役 28 行**（旧真值：P5-0 迁移的 9 行，全部 RESOURCE → CAPABILITY 的
  `REALIZES`）：**15 条 REALIZES**（迁移的 9 条 + C2-b 新写的 6 条，逐条
  capability 语义真实现，`primary_flag = true`）+ **13 条 SUPPORTS**（C2-b 新写，
  支撑关系而非实现，**`primary_flag = false`**）。canonical 未固定节点侧基数，
  故同一 node 可被多个 resource 声明；`primary_flag` 在现役语料里的读法是
  「该 resource 的 primary REALIZES 链接」（build 只对 `REALIZES` 检查
  「至多一条 primary」，见 `elc.content.build._check_references`）——所以
  SUPPORTS 行的 `primary_flag` 是 `false`；
- `strength` 一律 `null`：§24.7 未给链接 strength 值域（§7 的三词只属于
  prerequisite 边），不发明；
- `editorial_status` ∈ §24.11 词表；**C2-b 后的状态**：28 行全部为
  `CANONICAL_APPROVED` —— C1（Phase 11）编辑评审批准了
  `res-colloc-make-a-decision` 一行，C2-a 在为其余 8 个 res target 编写 readiness
  证据时逐条批准了其余 8 行，C2-b 在为 19 个新实体编写 readiness 证据时批准了那
  19 行（同一体裁的 rationale：批准覆盖什么、不覆盖什么、活风险、Revisit；
  C2-b 的行另加一句「本行由 C2-b 自己作出、无 fixture 声明」的限度）。P5-R 的规则
  对**未批准**行不变：行既然只是候选映射（`CURRICULUM_MAPPED`），便不得计入
  capability 证据（读面门见 `elc.content.store.CAPABILITY_CREDIT_EDITORIAL_STATUS`
  ——未审 link 在 `get_teaching_content().capability_linkage` 读作 `None`，但仍是
  可读的 link 行；被批准的 link 则读出其 node——门读的就是 link 自身的
  editorial_status，门本身从未改动）。**现役语料自 C2-a 起不再携带未批准行**，
  故"未批准 ⇒ 不计入"这一方向由 variant 钉住（`tests/phase5/
  test_p5_r_curriculum_truth.py` 的 demoted variant / `test_p5_1_readiness.py` 的
  同题变体）；**C2-b 新增的另一方向由现役语料自己钉住**："已批准但 `SUPPORTS`
  ⇒ 不计入 credit"（credit 读面只认 `relation = REALIZES AND primary_flag = 1
  AND editorial_status = CANONICAL_APPROVED`）。

  **已批准行的口径（C1 处置定谳的体裁，C2-a / C2-b 逐行沿用）**——① 每一条批准
  **覆盖**：该行的 provenance（C1/C2-a 的 9 行 = P3-1A/P3-1B fixture 声明，未改；
  C2-b 的 19 行 = 无 fixture 声明、由 C2-b 自己作出，rationale 逐条写明）、该
  target 的证据文档（`../content_src/evidence/<entity_id>.json`，C1 一份 / C2-a
  八份 / C2-b 十九份），以及「此批准使 §8.1 R2 的 `curriculum_link` 事实可读」；
  ② 每一条批准**不覆盖**：被 link 命名的 capability 在本仓无功能定义，capability
  语义审计**未做**，批准不构成能力认证——28 条映射的课程语义仍如 C2 所记未审；
  ③ **credit 的限度**：`CAPABILITY_CREDIT_EDITORIAL_STATUS` 门据此放行，故
  **15 个** RESOURCE target 的 `ALTERNATIVE_SUCCESS` 可铸 CAPABILITY/POSITIVE
  学习者证据——**这是行为变更，C1 时为 1 条、C2-a 后为 9 条、C2-b 后为 15 条，
  已知并接受**，其影响面受真实 rollout HOLD（无真实教学运行）限制；C2-b 的 13 条
  SUPPORTS **不进 credit 面**（读面按 relation 过滤），是**无 credit 风险的**
  §8.1 R2 载体；④ **Revisit**：capability 功能定义落地时重审全部 28 条批准。
  活风险登记 `R-C1-credit`（*一个未经能力语义审计的 link 批准现可铸学习者能力
  证据*；owner = 用户/总控；影响面 = 15 个 RESOURCE target 的
  `ALTERNATIVE_SUCCESS` 路径；Revisit = 功能定义落地 / 首次真实教学运行前
  **必须**重审），台账见 `AGENTS.md` 的 C1/C2-a/C2-b 处置条目。

#### link 状态变更记录（C1 + C2-a）

| 变更 | 行 | 理由与范围 |
| --- | --- | --- |
| `CURRICULUM_MAPPED` → `CANONICAL_APPROVED` | `res-colloc-make-a-decision` → `cap-eval-hedged-opinion` | C1 编辑评审在为该 target 编写 readiness 证据（`../content_src/evidence/res-colloc-make-a-decision.json`）时一并作出：批准**只**覆盖该行的来源事实（P3-1A/P3-1B fixture 声明，未改）、该 target 的证据文档本身、以及"此批准使 §8.1 R2 的 curriculum_link 事实可读"这一句。**未覆盖**（rationale 原文写明）：`cap-eval-hedged-opinion` 在本仓无功能定义，故无法做 capability 语义审计，批准不构成能力认证。Revisit = capability 功能定义落地时。 |
| `CURRICULUM_MAPPED` → `CANONICAL_APPROVED` | 其余 8 行（`res-hedge-i-think` / `res-softener-kind-of` / `res-colloc-pay-attention-to` / `res-frame-id-like-to` / `res-discourse-by-the-way` / `res-phrasal-look-forward-to` / `res-pragmatic-could-you` / `res-idiom-break-the-ice`） | C2-a（Phase 11）编辑评审在为这些 target 编写 readiness 证据时逐条批准，rationale 体裁与 C1 那条相同（覆盖 / 不覆盖 / credit 限度 / Revisit / 活风险 `R-C1-credit`）。五字段（resource_id / node_id / relation / strength / primary_flag）零改动；9 条映射的课程语义仍未审。 |
| 新增 19 行（6 REALIZES + 13 SUPPORTS，`editorial_status = CANONICAL_APPROVED`） | C2-b（Phase 11）的 19 个新实体各一行 | C2-b 在为这 19 个新实体编写 readiness 证据时一并作出。**REALIZES 6 行**（`res-discourse-to-be-honest` / `res-discourse-anyway` / `res-hedge-im-not-sure` / `res-hedge-it-depends` → `cap-eval-hedged-opinion`、`cap-disc-topic-shift`；`res-softener-a-bit` / `res-pragmatic-thats-a-good-point-but` → `cap-stance-soften-disagreement`，`primary_flag = true`）是 capability 语义层面的"真实现"主张，rationale 逐条含"未经能力语义审计（capability 无功能定义）"+ 覆盖/不覆盖 + 活风险 `R-C1-credit`，**并另加一句"本行无 fixture 声明、由 C2-b 自己作出"的限度**。**SUPPORTS 13 行**（`primary_flag = false`）是支撑关系：这些 resource 大多不带人际/立场功能（`res-colloc-heavy-rain` 一类纯词汇项尤其如此），rationale 逐条写明「placement 是本刀在现役 5 个节点中就近选取的决定，课程语义未审」，且**因 relation 不是 REALIZES 而不进 credit 面**（读面只认 `REALIZES`），即它们是**无 credit 风险的** §8.1 R2 载体。19 行的 `strength` 一律 `null`。 |

### C3 — Prerequisite 边（DOMAIN_MODEL §7）

`prerequisites.json` 的 `edges[]` 每行形状即 `elc.curriculum.types.
CurriculumEdgeRecord`：

```text
from_node / to_node / edge_type / prerequisite_strength
```

- `edge_type` ∈ §7 十一词表；`prerequisite_strength` ∈ §7 三词表
  （HARD / SOFT / SCAFFOLDABLE）或 `null`；
- **本 seed 为空集**：P3-1B 语料未声明任何前置关系，迁移不补齐、不猜测；
  本文件是该事实的 canonical 落点（后续 p5-1+ 作者在真实语料上补）。

## 拒绝规则（与 content_src 同）

索引不一致（列出但缺失 / 存在但未入索引）、词表越界、边/链接指向不存在的
node 或 resource → `BuildError`，构建拒绝而非降级。
