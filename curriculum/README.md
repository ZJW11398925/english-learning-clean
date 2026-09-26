# curriculum/ — Curriculum authoring source of truth（P5-0 seed）

作者源（docs/DATA_MODEL.md §24 "Content authoring source of truth: `content_src/*`
`curriculum/*`"）。capability registry / curriculum links / prerequisites 三类
**curriculum 面**数据在此落地，由 `src/elc/content/build.py` 与 `../content_src/`
一同确定性生成 `content.db`（§2 物理 profile 只有 `content.db`，无 curriculum.db）。

数据来源与总口径见 `../content_src/README.md`（同一迁移起点：P3-1A/P3-1B 的 14 个
validated target；Phase 11 各刀的内容与链接增量见该文件的 C1/C2/C3 登记与下文
变更记录）。

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

**C3-R1 起的可选块 `functional_definition`**（能力功能定义，五个键：`statement` /
`counts_as_realization` / `does_not_count` / `boundary_cases` / `basis`）：该
capability「是什么」的判定性一句话、什么行为算 realize（可逐条判 link 的标准
列表）、什么不算（排除标准）、边界例（≥2 条）、诚实依据（canonical 家族语义 +
本仓 authoring 判断，**非外部心理测量**）。块**存在即严格读**（未知键 / 缺键 /
空列表 / 边界例 <2 ⇒ `BuildError`），由 `elc.content.build` 装载到
`CapabilityDoc.functional_definition`，**不写进 content.db**（它是 authoring 侧
的判定标准，其用途是 C3-R1 对 §24.7 行的重审与 build 的形状规则「`CURRICULUM_MAPPING`
行命名的 capability 必须有定义」；声明读法，Revisit 已随裁决登记）。现役 5 个
节点全部携带一份。

### C2 — CurriculumLink（§24.7 / DATA_MODEL §13）

`links.json` 的 `links[]` 每行**恰好七列 + C3-R1 的第八列 `mapping_class`**
（§24.7 逐字七列 + C3-R1 声明读法新增列——§24.7 本身无此列，Revisit 随裁决登记）：

```text
resource_id / node_id / relation / strength / primary_flag /
editorial_status / mapping_class / rationale
```

- `relation` ∈ §24.7 五词表（REALIZES / SUPPORTS / EXEMPLIFIES / CONTRASTS /
  REQUIRES）；
- **`mapping_class`（C3-R1 声明读法）∈ 两词表**：`CURRICULUM_MAPPING`（真语义
  映射——资源的教学功能满足该 node 功能定义 `counts_as_realization` 的至少一条
  且不落入其 `does_not_count`）或 `COVERAGE_PLACEMENT`（覆盖记账——现役 5 个
  节点对 64 个资源的语料所迫的就近选位，**不含语义映射主张**）。build 强制两条
  形状规则：词表成员 + **`REALIZES ⇒ CURRICULUM_MAPPING`**（实现主张即映射主张）；
  另一条规则是 `CURRICULUM_MAPPING` 行命名的 capability 必须携带
  `functional_definition`（映射只对已陈述的标准有意义）；
- **现役 64 行（C3-R1 重审后）**：**16 条 `CURRICULUM_MAPPING`**（15 条 REALIZES +
  1 条 SUPPORTS）+ **48 条 `COVERAGE_PLACEMENT`**（全 SUPPORTS），m + p = 64；
  **relation 分布 15 条 REALIZES + 49 条 SUPPORTS**（C3-R1 重审把 6 条旧 REALIZES
  降级为 SUPPORTS——见下方变更记录，逐条披露）；
  **`primary_flag` 的读法自 C3-R1 起是「authoring 主张的冻结记录」**：6 条被降级
  行的 `primary_flag` 仍为 `true`（改动它们会改写历史主张；credit 读面按
  `relation = REALIZES` 过滤，降级即退出 credit 面）；
- `strength` 一律 `null`：§24.7 未给链接 strength 值域（§7 的三词只属于
  prerequisite 边），不发明；
- `editorial_status` ∈ §24.11 词表；**C3-b 后的状态**：64 行全部为
  `CANONICAL_APPROVED` —— C1（Phase 11）编辑评审批准了
  `res-colloc-make-a-decision` 一行，C2-a 在为其余 8 个 res target 编写 readiness
  证据时逐条批准了其余 8 行，C2-b 在为 19 个新实体编写 readiness 证据时批准了那
  19 行，C3-a 在为它的 18 个新实体编写 readiness 证据时批准了那 18 行，C3-b 在为
  它的 18 个新实体编写 readiness 证据时批准了那 18 行。P5-R 的规则
  对**未批准**行不变：行既然只是候选映射（`CURRICULUM_MAPPED`），便不得计入
  capability 证据（读面门见 `elc.content.store.CAPABILITY_CREDIT_EDITORIAL_STATUS`
  ——未审 link 在 `get_teaching_content().capability_linkage` 读作 `None`，但仍是
  可读的 link 行；被批准的 link 则读出其 node——门读的就是 link 自身的
  editorial_status，门本身从未改动）。**现役语料自 C2-a 起不再携带未批准行**，
  故"未批准 ⇒ 不计入"这一方向由 variant 钉住（`tests/phase5/
  test_p5_r_curriculum_truth.py` 的 demoted variant / `test_p5_1_readiness.py` 的
  同题变体）；"已批准但 `SUPPORTS` ⇒ 不计入 credit"（credit 读面只认
  `relation = REALIZES`）与"已批准但 `COVERAGE_PLACEMENT` ⇒ 不满足 §8.1 R2"
  （R2 读面见下）两条都由现役语料自己钉住。

  **已批准行的口径（C1 处置定谳的体裁，C2-a / C2-b / C3-a / C3-b 逐行沿用）**——① 每一条批准
  **覆盖**：该行的 provenance（C1/C2-a 的 9 行 = P3-1A/P3-1B fixture 声明，未改；
  C2-b 的 19 行、C3-a 的 18 行与 C3-b 的 18 行 = 无 fixture 声明、由各自那一刀自己作出，
  rationale
  逐条写明）、该
  target 的证据文档（`../content_src/evidence/<entity_id>.json`，C1 一份 / C2-a
  八份 / C2-b 十九份 / C3-a 十八份 / C3-b 十八份），以及「此批准使 §8.1 R2 的 `curriculum_link` 事实可读」；
  ② 每一条批准**不覆盖**：被 link 命名的 capability 在本仓无功能定义，capability
  语义审计**未做**，批准不构成能力认证——64 条映射的课程语义仍如 C2 所记未审；
  ③ **credit 的限度**：`CAPABILITY_CREDIT_EDITORIAL_STATUS` 门据此放行，故
  **15 个** RESOURCE target 的 `ALTERNATIVE_SUCCESS` 可铸 CAPABILITY/POSITIVE
  学习者证据——**已知并接受的行为变更链**：C1 时为 1 条、C2-a 后为 9 条、
  C2-b 后为 15 条、C3-a 后为 18 条、C3-b 后为 21 条、**C3-R1 重审后回落为 15 条**
  （6 条降级行退出 credit 面，逐条见变更记录）；C2-b/C3-a/C3-b 的
  SUPPORTS 行 **不进 credit 面**（读面按 relation 过滤）；
  ④ **Revisit（C3-R1 已触发并执行）**：capability 功能定义已随 C3-R1 落地
  （5 份，见上文 C1 段），对全部 64 条批准的**能力语义重审**已完成——结果即
  `mapping_class` 列与本文件的变更记录；**重审后 credit 面缩为 15 条，活风险
  `R-C1-credit` 随之收窄为这 15 个 target**（15 条现役 REALIZES 行仍自认
  「本映射以本仓 authoring 判断的功能定义为据」而非外部认证；canonical 定义
  落地时仍须复审），台账见 `AGENTS.md` 的 C1/C2-a/C2-b/C3-a/C3-b/C3-R1 处置条目。

#### R2 读法变化（C3-R1，src 行为改动）

§8.1 R2 的 `curriculum_link` 事实（`elc.curriculum.store.readiness_facts`）在
C3-R1 前读「≥1 条 approved 行」（不问 relation / mapping 语义——外评 HIGH-1 的
根源：纯词汇资源凭就近 SUPPORTS 即过 R2）；**C3-R1 起改读「≥1 条 approved ∧
`mapping_class = CURRICULUM_MAPPING`」**（`elc.content.store.
has_approved_curriculum_mapping`，一条查询、同样以 §24.11 批准为门）。其余 18 个
§8.1 事实键零改动。后果即**真值诚实回落**：R4 资源数 = 真映射资源数 **16**（与
links 的 `CURRICULUM_MAPPING` 行集逐 id 一致，一致性钉在
`tests/phase5/test_c3r1_capability_semantics.py`），其余 48 个 res 停在
**R1_LEXICALLY_RESOLVED**（词汇资源身份、19 键齐全、`curriculum_link` 是第一
缺键——可区分于「无证据」），5 个 cap 仍 None。**回落是裁决目的，不是事故**：
readiness 阶梯重新有区分度。四行内容门仍 GO（≥1 个 R4）。planner 的节点解析
（`elc.planner.supply`）**未同改**：它读 `REALIZES`（「哪个节点」而非「是否
映射」），而 build 的 `REALIZES ⇒ CURRICULUM_MAPPING` 规则保证 supply 所依的每
一行都满足新 R2——两读法不会在不安全方向分裂；语料里唯一一条
`SUPPORTS ∧ CURRICULUM_MAPPING`（`res-hedge-not-really`）满足 R2 但无可解析
节点，其 prerequisites 答 UNKNOWN（fail-closed），由同文件 ⑤ 组测试钉住。

#### link 状态变更记录（C1 + C2-a + C2-b + C3-a + C3-b + C3-R1）

| 变更 | 行 | 理由与范围 |
| --- | --- | --- |
| `CURRICULUM_MAPPED` → `CANONICAL_APPROVED` | `res-colloc-make-a-decision` → `cap-eval-hedged-opinion` | C1 编辑评审在为该 target 编写 readiness 证据（`../content_src/evidence/res-colloc-make-a-decision.json`）时一并作出：批准**只**覆盖该行的来源事实（P3-1A/P3-1B fixture 声明，未改）、该 target 的证据文档本身、以及"此批准使 §8.1 R2 的 curriculum_link 事实可读"这一句。**未覆盖**（rationale 原文写明）：`cap-eval-hedged-opinion` 在本仓无功能定义，故无法做 capability 语义审计，批准不构成能力认证。Revisit = capability 功能定义落地时。 |
| `CURRICULUM_MAPPED` → `CANONICAL_APPROVED` | 其余 8 行（`res-hedge-i-think` / `res-softener-kind-of` / `res-colloc-pay-attention-to` / `res-frame-id-like-to` / `res-discourse-by-the-way` / `res-phrasal-look-forward-to` / `res-pragmatic-could-you` / `res-idiom-break-the-ice`） | C2-a（Phase 11）编辑评审在为这些 target 编写 readiness 证据时逐条批准，rationale 体裁与 C1 那条相同（覆盖 / 不覆盖 / credit 限度 / Revisit / 活风险 `R-C1-credit`）。五字段（resource_id / node_id / relation / strength / primary_flag）零改动；9 条映射的课程语义仍未审。 |
| 新增 19 行（6 REALIZES + 13 SUPPORTS，`editorial_status = CANONICAL_APPROVED`） | C2-b（Phase 11）的 19 个新实体各一行 | C2-b 在为这 19 个新实体编写 readiness 证据时一并作出。**REALIZES 6 行**（`res-discourse-to-be-honest` / `res-discourse-anyway` / `res-hedge-im-not-sure` / `res-hedge-it-depends` → `cap-eval-hedged-opinion`、`cap-disc-topic-shift`；`res-softener-a-bit` / `res-pragmatic-thats-a-good-point-but` → `cap-stance-soften-disagreement`，`primary_flag = true`）是 capability 语义层面的"真实现"主张，rationale 逐条含"未经能力语义审计（capability 无功能定义）"+ 覆盖/不覆盖 + 活风险 `R-C1-credit`，**并另加一句"本行无 fixture 声明、由 C2-b 自己作出"的限度**。**SUPPORTS 13 行**（`primary_flag = false`）是支撑关系：这些 resource 大多不带人际/立场功能（`res-colloc-heavy-rain` 一类纯词汇项尤其如此），rationale 逐条写明「placement 是本刀在现役 5 个节点中就近选取的决定，课程语义未审」，且**因 relation 不是 REALIZES 而不进 credit 面**（读面只认 `REALIZES`），即它们是**无 credit 风险的** §8.1 R2 载体。19 行的 `strength` 一律 `null`。 |
| 新增 18 行（3 REALIZES + 15 SUPPORTS，`editorial_status = CANONICAL_APPROVED`） | C3-a（Phase 11）的 18 个新实体各一行 | C3-a 在为这 18 个新实体编写 readiness 证据时一并作出。**REALIZES 3 行**（`res-hedge-sort-of` / `res-softener-to-be-fair` / `res-discourse-having-said-that` → `cap-stance-soften-disagreement`，`primary_flag = true`）是 capability 语义层面的"真实现"主张，rationale 逐条含"未经能力语义审计（capability 无功能定义）"+ 覆盖/不覆盖 + 活风险 `R-C1-credit` + **本行无 fixture 声明、由 C3-a 自己作出**的限度，并逐条写明该映射比节点名更宽的地方（软化的是一句描述/评估或一次让步，而非一定是"分歧"本身）。**SUPPORTS 15 行**（`primary_flag = false`）是支撑关系：rationale 逐条写明「placement 是本刀在现役 5 个节点中就近选取的决定，课程语义未审」及为何是"就近"而非语义匹配，且**因 relation 不是 REALIZES 而不进 credit 面**。18 行的 `strength` 一律 `null`。 |
| 新增 18 行（3 REALIZES + 15 SUPPORTS，`editorial_status = CANONICAL_APPROVED`） | C3-b（Phase 11）的 18 个新实体各一行 | C3-b 在为这 18 个新实体编写 readiness 证据时一并作出，体裁与 C3-a 相同。**REALIZES 3 行**（`res-discourse-that-reminds-me` → `cap-disc-topic-shift`、`res-hedge-i-guess` → `cap-eval-hedged-opinion`、`res-pragmatic-no-offense-but` → `cap-stance-soften-disagreement`，`primary_flag = true`）是 capability 语义层面的"真实现"主张 —— 取法是同一把尺子的继续：「说出口即执行该动作」的语用单位（话题引入标记、弱化断言的 hedge、批评前的软化语）算实现，而命名该动作的实词（`bring up` 一类）只算支撑。rationale 逐条含"未经能力语义审计（capability 无功能定义）"+ 覆盖/不覆盖 + 活风险 `R-C1-credit` + **本行无 fixture 声明、由 C3-b 自己作出**的限度，并逐条写明该映射比节点名更宽的地方（例如 `that reminds me` 的 shift 是**联想式**的：它引入被刚说过的话唤起的新话题；`I guess` 标记的是说话人确信度更低而非评估性意见；`No offense, but` 软化的是对该**事**的批评而非一定是分歧本身）。**SUPPORTS 15 行**（`primary_flag = false`）是支撑关系：rationale 逐条写明「placement 是本刀在现役 5 个节点中就近选取的决定，课程语义未审」及为何是"就近"而非语义匹配（`bring up` 尤其写明「引入话题 ≠ 移开话题」这一限度），且**因 relation 不是 REALIZES 而不进 credit 面**。18 行的 `strength` 一律 `null`。 |
| **relation 变更 6 行：`REALIZES` → `SUPPORTS`（`mapping_class = COVERAGE_PLACEMENT`）** | `res-colloc-make-a-decision` → `cap-eval-hedged-opinion`；`res-colloc-pay-attention-to` → `cap-ref-ask-clarification`；`res-frame-id-like-to` → `cap-interact-backchannel`；`res-phrasal-look-forward-to` → `cap-interact-backchannel`；`res-pragmatic-could-you` → `cap-ref-ask-clarification`；`res-idiom-break-the-ice` → `cap-disc-topic-shift` | **C3-R1（Phase 11）能力语义重审**：五份功能定义落地后，这 6 行对照其 node 的 `functional_definition.counts_as_realization` 逐条重验**不过**、且落入 `does_not_count`——collocation 命名「做出选择」这一行为（`make-a-decision`：产出是关于行为的命题，无任何说话人断言的弱化，落 `cap-eval` 的 does_not_count 1）；请求框架与请求语（`id-like-to` / `could-you`）的请求对象是行为或物品而非对话者的话语（说话人在**要**东西，不是在**接收**话语或**求解**其义）；`look-forward-to` 是关于态度的命题（不是听者的接收信号）；`break-the-ice` 管理社交场合而非话题（落 `cap-disc` 的 does_not_count 3）。6 行的 node_id / strength / primary_flag / editorial_status **零改动**（`primary_flag` 冻结为 authoring 主张的记录），rationale 逐条改写为重审体裁并自述「corrected from REALIZES to SUPPORTS」；credit 面随之 21 → 15。 |
| **全 64 行 `mapping_class` 定级（16 `CURRICULUM_MAPPING` + 48 `COVERAGE_PLACEMENT`）** | 64 行各一行 | C3-R1 重审的另一半：15 条幸存 REALIZES 全部为真映射（build 规则 `REALIZES ⇒ CURRICULUM_MAPPING` 所迫，且逐条引用 `counts_as_realization` 具体条目）；**1 条 SUPPORTS 判为真映射**（`res-hedge-not-really` → `cap-stance-soften-disagreement`：答话的温和否定是一次立场行动，满足该 node counts_as 1/2——relation 保持 SUPPORTS 强度不变；`mapping_class` 判语义真值、relation 判强度，二者正交）；其余 48 条判 `COVERAGE_PLACEMENT`（就近选位、无语义映射主张），rationale 逐条改写为重审体裁（点名 node + 引用其定义文件 + 引用判定所依条目 + 自述 provenance + Revisit）。 |

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
