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
- 本 seed 的 9 行全部是 RESOURCE → CAPABILITY 的 `REALIZES`，
  `primary_flag = true`（该 resource 自己声明的 linkage 即其 primary 链接；
  canonical 未固定节点侧基数，故同一 node 可被多个 resource 声明）；
- `strength` 一律 `null`：§24.7 未给链接 strength 值域（§7 的三词只属于
  prerequisite 边），不发明；
- `editorial_status` ∈ §24.11 词表；**C1 后的状态**：9 行中 8 行仍为
  `CURRICULUM_MAPPED`，`res-colloc-make-a-decision` 一行由 C1（Phase 11）
  编辑评审改为 `CANONICAL_APPROVED`。`CURRICULUM_MAPPED` 行的依据仅为
  P3-1A/P3-1B 测试语料设计（fixture 的 `capability_linkage`），**未经课程
  语义审核**，在 capability 功能定义存在且作者审核通过前**不得计入
  capability 证据**（P5-R；读面门见
  `elc.content.store.CAPABILITY_CREDIT_EDITORIAL_STATUS`——未审 link 在
  `get_teaching_content().capability_linkage` 读作 `None`，但仍是可读的
  link 行；被批准的 link 则读出其 node——门读的就是 link 自身的
  editorial_status，门本身从未改动）。

#### link 状态变更记录（C1）

| 变更 | 行 | 理由与范围 |
| --- | --- | --- |
| `CURRICULUM_MAPPED` → `CANONICAL_APPROVED` | `res-colloc-make-a-decision` → `cap-eval-hedged-opinion` | C1 编辑评审在为该 target 编写 readiness 证据（`../content_src/evidence/res-colloc-make-a-decision.json`）时一并作出：批准**只**覆盖该行的来源事实（P3-1A/P3-1B fixture 声明，未改）、该 target 的证据文档本身、以及"此批准使 §8.1 R2 的 curriculum_link 事实可读"这一句。**未覆盖**（rationale 原文写明）：`cap-eval-hedged-opinion` 在本仓无功能定义，故无法做 capability 语义审计；其余 8 行维持 `CURRICULUM_MAPPED`；9 条映射的课程语义仍如 C2 所记未审。Revisit = capability 功能定义落地时。 |
| 其余 8 行 | 未动 | 维持 P5-R 原判（映射 ≠ 证据，理由句原文不变）。 |

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
