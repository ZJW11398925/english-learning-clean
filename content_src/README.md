# content_src/ — Content authoring source of truth（P5-0 seed）

作者源（docs/DATA_MODEL.md §24 "Content authoring source of truth: `content_src/*`
`curriculum/*`"）。`content.db` 是 `src/elc/content/build.py` 从本目录与
`../curriculum/` **确定性生成**的 runtime artifact，**不手改**。

## 数据来源声明（P5-0 迁移口径）

本目录不是新创作的内容，而是把仓内唯一已验证语料
`tests/phase3/target_fixtures.py`（P3-1A/P3-1B 的 14 个 validated target：
`VALIDATED_TARGET_FIXTURES` + 其 `TEACHING_CONTENT`）**逐条迁移**而来
（IMPLEMENTATION_PLAN §6 "先迁移工具链与 seed，不继续盲目扩到100"）。迁移 ≠
删除：`tests/phase3/target_fixtures.py` 原件与其 Phase 3 消费者一字未动。

探索期仓 `D:\测试1` 对 `OQ-021` / `content_toolchain` / `content_src` / `*.db`
的全仓深搜零命中（P5-0 四查实证），故 §6 提到的旧工具链在仓内不存在可用副本；
本目录即 P5-0 的替代 seed 路线。**旧真值（P5-0）：内容量停留在 14 个 target
（不扩到 100）；新真值（C1/C2-a/C2-b/C3-a/C3-b，Phase 11 内容程序）**：作者源在证据面
建成之后按 §13「优先使用内容填补真实运行时测试需要」逐刀补齐，现为 **69 个实体
（64 个 res + 5 个 cap）**——**离 100 还有 36**；Calibration100 的体量门（100）
仍未过，CORE_A（42/30）与 CORE_C（22/2）按**声明读法**达到（登记与读数见
`../README.md` 与 `../curriculum/README.md` 的 C3-a / C3-b 段）。

## 文件布局

```text
content_src/
  index.json                 # 索引：content_version + 实体文档清单 + 证据文档清单（无 glob 兜底）
  entities/<entity_id>.json  # 每个 target 一份（共 69 = 5 个 cap-* + 64 个 res-*；其中 19 个由 C2-b、18 个由 C3-a、18 个由 C3-b 编写）
  evidence/<entity_id>.json  # C1：每个声明了 readiness 证据的 target 一份（可空集；现为 64 份，与 res-* 一一对应）
  README.md                  # 本文件 = 映射规则索引文档
```

## evidence 块映射规则（C1，Phase 11）

`evidence/<entity_id>.json` 是 §8.1 readiness 证据的作者源（读面 =
`elc.curriculum.store.readiness_facts`：18 键逐表读 +
`entity_row` 由前置 `get_resource` 成功证明存在；纯判定 =
`elc.curriculum.readiness`）。文件名即实体 id（不重复写；build 拒绝悬空文档）。
由 `index.json` 的 `evidence` 键逐条声明——**无 glob 兜底**，目录里存在但未入
索引的文档一律 `BuildError`；该键是**必需键**（缺键被拒，这是 C1 处置的
有意收紧——"无证据"必须显式写 `[]`，不存在"键缺席 = 键省略"的第二种
拼法）。

块规则：

- **每个块可选**：文档只声明该源携带的证据，未声明的块不落行（读面把缺席读成
  缺席，绝不读成"默认满足"）。
- **每块严格读**：未知块键 / 缺键或未知键 / 未知词表词 / 负 ordinal / 重复
  主键 / 空 JSON 数组（要表达"无行"就**省略**该块）一律 `BuildError`。
- **声明读法**：§24 给了字段表的列逐字照抄；§24 只命名概念未给字段表的表，列
  是声明读法（build.py 的表注释逐表写明 + Revisit），不冒充 canonical。

逐块列名（与 13 张证据表一一对应；`entity_id` 由文件名承载，文档不重复）：

| 块 | 表 | 列 |
| --- | --- | --- |
| `assessment_membership` | `content_assessment_membership` | assessment_id / membership_status / source（§24.8 未给字段表 ⇒ 声明读法） |
| `lexical_entry` | `content_lexical_entry` | lemma / pos（§24.2 两列逐字；**声明读法（C1 处置）**：§24.2 的第三个区分项 morphological paradigm **未建列**——语义单位的词形变化由 §24.2 Form 行（`content_form`，R1 `forms` 证据）承载，不在 entry 行上；Revisit = 首个需要在 entry 本身携带 paradigm 字段的源） |
| `senses` | `content_sense` | sense_id / ordinal（§24.3 未给字段表 ⇒ 声明读法） |
| `texts` | `content_text` | sense_id(可空) / language / role / ordinal / text（role ∈ §24.3 六词表；**声明读法（C1 处置）**：主键 `(entity_id, role, ordinal)` **不含 language**——单语言语料的最小列集，第二语言在同 (role, ordinal) 上会撞主键；Revisit = 首个多语言源出现时扩主键） |
| `forms` | `content_form` | form_id / written / normalized / form_type / morph_features(可空) / pronunciation(可空)（§24.2 五列 + form_id） |
| `pedagogical_profile` | `content_pedagogical_profile` | §24.7 十一列逐字（default_target_mode 校 §11 词表、editorial_status 校 §24.11 词表） |
| `pack_overlays` | `content_pack_overlay` | pack_id / weight / rationale（§24.8 未给字段表 ⇒ 声明读法） |
| `resource_labels` | `content_resource_label` | ordinal + §24.7 七列（register / usage_modality / genre / context / style / domain / variety，均可空） |
| `example_policy` | `content_example_policy` | policy_version / policy（§24 未给字段表 ⇒ 声明读法） |
| `typical_error_required` | `content_meta`（键 `typical_error_required:<entity_id>`） | 布尔：源级声明"该 target 需要 TypicalError"（§24.6 未落地 ⇒ 声明读法，Revisit = 迁回 §24.6 assertion 载体） |
| `typical_errors` | `content_typical_error` | ordinal / learner_l1(可空) / error_type / error_pattern / corrected_pattern / explanation / severity / detection_policy（§24.9 七列 + ordinal） |
| `detection_policy` | `content_detection_policy` | policy_version / policy（§24.10 未给字段表 ⇒ 声明读法） |
| `detection_rules` | `content_detection_rule` | ordinal / rule |
| `detection_fixtures` | `content_detection_fixture` | ordinal / kind（`NEGATIVE` \| `FALSE_POSITIVE_BOUNDARY`，声明读法）/ text / expected |

R4 可测性规则（本仓现役语料的自约束，build 不校验语义、只校验词表）：每条
detection rule 的 ordinal 应有同 ordinal 的 fixture 兜底；fixture 的 `expected`
非空且与 `text` 语义一致；不使用模型自报置信（§8.1 "V1 不把'模型自称高置信'
自动视为 R4 等价认证"）。**登记（C1 处置，F8）**：R4 的「可测试」在本语料中是
**结构性**的——policy/rules/fixtures 落库为 TEXT + 声明的 `expected` 串，仓内
**没有执行者**（`NO_MATCH` / `NO_MATCH_BOUNDARY` 只活在本语料策略散文与测试
字面量里）；本登记不声称任何 detector 已存在。

**登记（C2-a，`resource_labels` 的值域）**：`register` 的取值来自 canonical
词表（PRODUCT_CONTRACT §4.6 CASUAL / NEUTRAL / POLITE / …）；其余六列
（`usage_modality` / `genre` / `context` / `style` / `domain` / `variety`）
canonical 未给值域，故其值一律是**声明读法**（C1 起用的 `WRITTEN_AND_SPOKEN` /
`PLAIN` / `GENERAL` / `EN-US` / `EN-GB` 与 C2-a 逐 target 的 `context` 词同属
这一列，不冒充 §24.7 的固定词表）。Revisit = §24.7 给出值域时。

**登记（C2-a，九份 evidence 文档的分布）**：C1 编写 1 份
（`res-colloc-make-a-decision.json`），C2-a 编写其余 8 份；5 个 `cap-*`
target **不写** evidence（开工裁决 ③：cap 侧的 None 是构造性的——无 resource
侧 link、词法面语义拉伸），因此现役真产物上 = 9×R4_DETECTION_READY +
5×None。

**登记（C2-b，十九份新 evidence 文档与语料规模）**：C2-b（Phase 11 第三段）新增
19 个 **res** 实体（`res-colloc-*` 5 / `res-phrasal-*` 3 / `res-idiom-*` 2 /
`res-discourse-*` 2 / `res-frame-*` 2 / `res-hedge-*` 2 / `res-softener-a-bit`
1 / `res-pragmatic-*` 2），每个实体一份 entity 文档 + 一份 19 键 evidence 文档，
并各配一条 §24.7 link（见 `../curriculum/README.md` C2-b 段）。语料规模：
**33 实体 / 28 份 evidence / 28 条 link**；C2-b 结束时真产物上 =
**28×R4_DETECTION_READY + 5×None**，`resource_count`（`res-*` 实体）= **28**。
**这不是 Calibration100 的通过**：IP §13 的「28 → 100 resource calibration」
把 28 记作**起点第一档**，三门中的体量门（`resource_count ≥ 100`）在 C2-b 结束时
未过（28/100），CORE_A / CORE_C 当时的家族计数读法为 0/30、0/2（该读法已被
C3-a 取代，见下条登记）。

**登记（C3-a，十八份新 evidence 文档与读法落地）**：C3-a（Phase 11 第四段）
新增 18 个 **res** 实体（`res-colloc-*` 5 / `res-phrasal-*` 3 / `res-idiom-*` 2 /
`res-discourse-*` 2 / `res-frame-*` 2 / `res-hedge-*` 2 / `res-softener-to-be-fair`
1 / `res-pragmatic-could-i-ask` 1），每个实体一份 entity 文档 + 一份 19 键
evidence 文档，并各配一条 §24.7 link。语料规模：
**51 实体 / 46 份 evidence / 46 条 link**；真产物上 =
**46×R4_DETECTION_READY + 5×None**，`resource_count` = **46**。C3-a 同时把
CORE_A / CORE_C 从 `curriculum_capability.family` 计数改为**声明读法**
（用户 2026-09-26 裁决）：level ∈ {R3, R4} 的 res 实体按
`content_pedagogical_profile.core_utility` 分档（HIGH → CORE_A，MEDIUM/LOW →
CORE_C）；现读数 **CORE_A 32/30 达到、CORE_C 14/2 达到、体量门 46/100 未过**
（三门分开断言，见 `tests/phase5/test_c3a_readface_and_expansion.py`；Revisit =
canonical Calibration100 定义落地时）。**这不是 Calibration100 的通过**：体量门
仍未过，真实 rollout 仍 HOLD（零开闸声称）。

**登记（C3-b，十八份新 evidence 文档与语料规模）**：C3-b（Phase 11 第五段）
新增 18 个 **res** 实体（`res-colloc-*` 5 / `res-phrasal-*` 3 / `res-idiom-*` 2 /
`res-discourse-*` 2 / `res-frame-*` 2 / `res-hedge-*` 2 / `res-softener-if-anything`
1 / `res-pragmatic-no-offense-but` 1），每个实体一份 entity 文档 + 一份 19 键
evidence 文档，并各配一条 §24.7 link。语料规模：
**69 实体 / 64 份 evidence / 64 条 link**；真产物上 =
**64×R4_DETECTION_READY + 5×None**，`resource_count` = **64**。CORE_A / CORE_C
沿用 C3-a 的**声明读法**（用户 2026-09-26 裁决）：level ∈ {R3, R4} 的 res 实体按
`content_pedagogical_profile.core_utility` 分档（HIGH → CORE_A，MEDIUM/LOW →
CORE_C）；现读数 **CORE_A 42/30 达到、CORE_C 22/2 达到、体量门 64/100 未过**
（三门分开断言，见 `tests/phase5/test_c3b_resource_expansion.py`；Revisit =
canonical Calibration100 定义落地时）。**这不是 Calibration100 的通过**：体量门
仍未过，真实 rollout 仍 HOLD（零开闸声称）。本刀的语义诚实面另有两处登记：
`res-phrasal-work-out` / `res-phrasal-bring-up` / `res-phrasal-put-off` 三条的
`required_slots` 是**小写 token 组**（与全语料一致；slot 匹配按词形归一，大写
会让 `test_p5_2_target_resolution.py` 的 slot 渲染钉失配）；`res-discourse-long-story-short`
的 `alternative_realizations` 特意写成不含本实体 canonical 句的另一句，因为
resolver 先按 canonical 形式做整句命中、再按 alternative（一条替代实现若**包含**
自己的 canonical 整句，会以 `CANONICAL_FORM` 命中而违反 `ALTERNATIVE_REALIZATION`
钉）。

**登记（C2-b，19 个新实体的来源口径）**：这 19 个实体**不是** P3-1A/P3-1B
fixture 的迁移（那 14 个 target 的迁移见下），而是 C2-b 这一刀按 §24.1/§24.2/
§24.3/§24.4 的列与词表**新编写**的内容；因此 evidence 文档的
`assessment_membership.source` 逐份写明「声明由本刀的编辑评审作出，本仓无外部
评测导出」，`content_meta` 的 `typical_error_required:<id>` 键也随每份文档
逐条落库（`typical_error_required: true` + ≥1 条 `typical_errors`）。

## 映射规则（显式声明；不发明列名）

### R1 — 每个 target 一条 ContentEntity（§24.1 七列逐字）

69 个 target（P3-1A/P3-1B 迁移的 14 个 + C2-b 编写的 19 个 + C3-a 编写的 18 个 +
C3-b 编写的 18 个）每个对应**恰好一个**
`entities/<target_id>.json`，`entity_id` = target id 原文（`res-*` 64 个、`cap-*`
5 个；无派生、无哈希重命名）。文档内
`entity` 块**恰好**是 §24.1 的七列，顺序与拼写逐字：

```text
entity_id / entity_type / language / lifecycle_status /
entity_revision / created_in_version / updated_in_version
```

- `entity_type` 只取 §24.1 六词表（LEXICAL_ENTRY / FORM / SENSE / EXPRESSION /
  CONSTRUCTION / EXAMPLE）。本语料全部是 **EXPRESSION**：14 个 target 的可教学内容
  都是多词表达（collocation / phrasal verb / idiom / discourse marker / sentence
  frame / pragmatic formula / functional expression）。
- `language` = `en`（语料为英语，与索引 `language` 一致）。
- `lifecycle_status` 取 §24.11 词表，本语料全部 `CANONICAL_APPROVED`：这些实体来自
  P3-1A/P3-1B 已验收语料（`content_status=VALID`，非 model-generated candidate——
  §24.11 "Model-generated candidate 默认不是 CANONICAL_APPROVED" 的反面）。
- `entity_revision` 为整数修订计数，本 seed 全为 `1`；`created_in_version` /
  `updated_in_version` = 本发布 `content_version`（见 `index.json`）。

### R2 — 表达子类型映射（§24.4）

`expression` 块**恰好**三个字段，值域全部来自 §24.4：

```text
expression_type      # §24.4 八个 first-class type
fixedness            # §24.4 FIXED | SEMI_FIXED | SLOT_BASED
recognition_policy   # §24.4 EXACT | LEMMA_SEQUENCE | SLOT_PATTERN | MODEL_ASSISTED
```

作者规则（规则清单在此逐条写明；实体文档只落值、不逐字段解释；build 逐条校验
词表成员，不校验语义）：

- `expression_type` 按该 target 的语言学性质取 §24.4 八词之一（如 idiom →
  IDIOM、phrasal verb → PHRASAL_VERB、collocation → COLLOCATION、discourse
  marker → DISCOURSE_MARKER、frame → SENTENCE_FRAME、politeness/hedge formula →
  PRAGMATIC_FORMULA、function word 类 → FUNCTIONAL_EXPRESSION）；
- `fixedness`：整体固定 → FIXED；词形可变但搭配固定 → SEMI_FIXED；含开放槽位 →
  SLOT_BASED；
- `recognition_policy`：固定 lemma 序列可识别 → LEMMA_SEQUENCE；需要槽位填充
  才算识别 → SLOT_PATTERN。§24.4 "Recognition proposes a match；不等于 mastery"
  ——该字段不承载任何掌握度语义。

### R3 — target 默认值（§11 + §24.14）

`target` 块**恰好**四字段，迁移自 fixture 的 `TeachingTargetView`：

```text
target_type         # RESOURCE | CAPABILITY（DOMAIN_MODEL §6 两族）
target_mode         # DOMAIN_MODEL §11 五词表
learning_intent     # DOMAIN_MODEL §11 七词表
evidence_modality   # DATA_MODEL §24.14 V1 两词表
```

fixture 的 `target_status` / `content_status`（`VALID`）是解析期的**有效性判定**
（`elc.teaching.targets` 端口语义），不是内容数据，故不落库：`content_status=VALID`
映射为实体已存在于本 release 且 `lifecycle_status` 为 live 值（CANONICAL_APPROVED），
`target_status=VALID` 映射为该解析结论本身。这是本迁移**唯一**未逐字落库的
fixture 字段（逐项见 §"fixture 字段 → 落库位置"）。

### R4 — 教学内容载荷（P3-1B 形状，字段名逐字）

`teaching_content` 块**恰好**五字段，字段名逐字取自
`elc.teaching.targets.TeachingTargetView`（P3-1B 已验收形状，canonical §24 未定义
ladder/answer-key 表，故按 P3 形状迁移，不另起列名）：

```text
hint_ladder              # 有序提示阶梯（semantic → structural → partial form）
reveal_form              # 揭示用 canonical form（build 强制 ∈ canonical_forms）
canonical_forms          # 答案键：可作为正确实现的形式，逐字
alternative_realizations # 同一 target 的其他合法实现（§5 ALTERNATIVE_SUCCESS）
required_slots           # PARTIAL 判定需覆盖的 token 组
```

落库形态：`canonical_forms` → `content_example` 行（role = §24.5 ExampleLink
角色 `PRIMARY_TARGET`），`alternative_realizations` → `content_example` 行（role
= §24.5 `SUPPORTING`）——表名取 §24.5 的 Example 概念，**不叫** `content_form`
（§24.2 的 `Form` 是另一个 canonical 概念：written/normalized/form_type/
morph_features）；`hint_ladder` → `content_hint_rung`（ordinal 保序）；
`required_slots` → `content_slot`（group_ordinal + token_ordinal 保序）；
`reveal_form` → `content_teaching.reveal_form`。

### R5 — capability linkage / prerequisite（curriculum 面，§24.7 / §7）

capability linkage **不进 content_src**，进 `../curriculum/links.json`：
resource → capability node 的 `CurriculumLink`（§24.7 七列逐字：resource_id /
node_id / relation / strength / primary_flag / editorial_status / rationale）。
9 条 REALIZES 链接 = 9 个 RESOURCE target 的 fixture `capability_linkage` 逐条迁移；
C2-b 另写 19 条（6 条 REALIZES + 13 条 SUPPORTS）给 19 个新实体，C3-a 再写 18 条
（3 条 REALIZES + 15 条 SUPPORTS）给 18 个新实体，C3-b 再写 18 条
（3 条 REALIZES + 15 条 SUPPORTS）给 18 个新实体，其语义与
credit 面限度见 `../curriculum/README.md` 的 C2-b / C3-a / C3-b 段——**node_id 只取现役 5 个
cap-* 节点**（build 的引用完整性要求 `node_id` 必须是已声明的 capability，
`content_src/README.md` 与 `elc.content.build._check_references` 同一条）。

`strength` 在 canonical 中**只有 prerequisite 边**给了词表（§7
HARD/SOFT/SCAFFOLDABLE）；§24.7 未给 CurriculumLink 的 strength 值域，故本语料
一律写 `null`（不发明词表），build 允许 `null` 或 §7 三词。前置边
（`../curriculum/prerequisites.json`）本语料为空集：P3-1B 语料未声明任何
prerequisite，**不替作者发明**。

CAPABILITY target（`cap-*` 5 个）的迁移规则：`entities/cap-*.json` 是该 capability
的 canonical realization 表达（同 id）；`curriculum/capabilities/cap-*.json` 是
capability registry 节点（同 id，两个 id 空间）。节点 ↔ realization 由 id 同一性
对应（§24.5 的"通过 CurriculumLink 连接"约束的是**不同**实体；此处两者是同一
target 的两个域视图，故不造自环链接行）。

### fixture 字段 → 落库位置（14 × 逐字段）

| fixture 字段 | 落库位置 |
| --- | --- |
| `target_type` | `content_target.target_type` + （CAPABILITY 时）`curriculum_capability` 行 |
| `target_id` | `content_entity.entity_id`（逐字） |
| `target_status` | 不落库（解析期有效性判定；映射见 R3） |
| `content_status` | 不落库（同上） |
| `target_mode` | `content_target.target_mode` |
| `learning_intent` | `content_target.learning_intent` |
| `evidence_modality` | `content_target.evidence_modality` |
| `hint_ladder` | `content_hint_rung`（ordinal 0..n-1） |
| `reveal_form` | `content_teaching.reveal_form` |
| `canonical_forms` | `content_example`（role=PRIMARY_TARGET） |
| `alternative_realizations` | `content_example`（role=SUPPORTING） |
| `required_slots` | `content_slot`（group/token ordinal） |
| `capability_linkage` | `curriculum_link`（relation=REALIZES, primary_flag=1） |

## 确定性规则

- 构建顺序：实体/能力/链接一律按 id 排序后写入（`entity_id` / `capability_id` /
  `(resource_id, node_id, relation)`），与文件系统遍历顺序、索引清单顺序无关；
- **无墙钟入内容**：内容不含任何时间戳/构建时间（§26.1 的 `updated_at` 在
  content.db 中**有意不写**——它会让同源重建不字节一致；版本由
  `content_version` / `curriculum_version` 表达）；
- 源缺失、清单不一致（索引列出但文件不存在 / 目录里存在但未入索引）、词表越界、
  引用悬空（link 指向不存在的 resource/node）**一律拒绝构建**（`BuildError`），
  不静默跳过。

## 重建

```bash
PYTHONPATH=src python -m elc.content.build --out build/content.db
```

产物元数据：`content_meta.content_db_version = "2"`（docs/DATA_MODEL.md §26.1；
C1 把表集 11 → 24，C1 处置据此显式 bump，禁止依赖代码猜 schema）。

ADR：`content.db` 是生成物（`.gitignore` 已含 `*.db`），由 CI/本地按需重建；
本目录与 `../curriculum/` 是版本控制内的唯一作者源。
