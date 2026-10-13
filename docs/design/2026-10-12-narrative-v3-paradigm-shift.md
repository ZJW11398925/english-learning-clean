# 叙事引擎重构（Narrative V3）· 范式转折设计篇 + 旧范式映射审计

> **性质**：`living-world-spec.md`（v2.1）与 `cognition-and-narrative-quality.md`（v1.1）的**补充收敛篇**（模式同 cognition 篇——同一套设计的组成部分，不是并行新总体设计）。本稿承接用户 2026-10-12 范式转折交接，把「世界自行发展的持续小说」定为产品核心，把信件驱动/World Run/停点协议降为 legacy 路径。
> **归属**：范式与职责分离为用户主创（交接原文逐条在案）；体系化收敛、与现役仓库事实的对接、审计与 slicing 为总控设计。
> **状态**：设计收口稿 **v3.1（V3-0R，2026-10-12）**——外评 PASS WITH DESIGN CORRECTION 六项已处置（结算两级 / World Bible 权威独立 / WorldActorProfile 入 V3-3 / Reader Exposure 本体 / tick 语义与 planned≠actual / canonical legacy 隔离），外加 Blueprint 措辞与 V3-8 结构验收、刀序微调。**待复核冻结 V3.0 后再进入实现（未复核前不写代码、不续 E 程序）。**
> 日期：2026-10-12 · 版本：v3.0（首版）/ **v3.1（V3-0R 修订）**

---

## 一、范式声明

### 1.1 新核心循环（产品）

```
创建 / 选择世界 → 创建世界主要角色（AI） → 创建用户角色 → 进入世界
→ 世界以持续小说的形式发展：
   章内：SEGMENT / SCENE COMMIT（每段落即入正史）→ 用户意志点停（User Gate）→ 继续
      → 章末 CHAPTER SETTLEMENT（压缩与收束；不负责第一次落地）
→ 章间：作者层（让世界自行发展 / 几个故事方向 / 用户输入下一章基调）
→ 下一章 Blueprint → 循环
```

产品核心定义（用户原话）：**一个持续存在、能够自己发展剧情的小说世界；用户本人是其中一个真实角色，同时可以在章与章之间有限地参与故事方向。**

### 1.2 旧理解废止（不再决定未来架构；legacy 保留）

| # | 旧理解 | 处置 |
|---|---|---|
| 1 | 信件/回信是世界运行的核心发动机 | **废止**（信件降为 UI/narrative presentation element） |
| 2 | 用户主要身份是通信者/笔友 | **废止**（用户是世界里的真实角色） |
| 3 | World Run 由用户回信启动、再生成若干 beats | **legacy**（旧生产链保留，退出新主线） |
| 4 | NOTICE / RESPONSE / DIRECTION 停点是长期核心交互模型 | **legacy** |
| 5 | 世界运行的主要产品形式是世界事件 + 信件混排时间线 | **废止**（等 Chapter/Story Reader 出现后重设 presentation） |
| 6 | 导演模式需要在每个较小世界步中频繁出现 | **废止**（方向选择升格为**章间**作者层） |
| 7 | WorldNarrator 同时决定剧情、生成正文、决定交互停点 | **废止**（拆为 §二 的职责分离） |

**legacy 三条纪律**：①不立即删除；②旧链继续全绿（测试不拆）；③直到 Narrative V3 有完整纵向切片后，再讨论退役。

### 1.3 保持不变（本项目其余部分全部继续有效）

教学系统（三天线/五砝码/三层/延迟教学/学习闭环）、用户配置与安全边界、persona 生成基础、provider 面、content/curriculum、Scheduler/Planner/Gate、Local V1 运行时纪律、AOCI 认知层与各刀纪律。

---

## 二、运行模型的职责分离（权力边界）

未来不再由单体 Narrator 完成所有事情。七个角色的权力边界与输入输出：

### 2.1 World Director（全知导演）

**知道**：World Bible；世界历史；当前世界状态；所有重要人物及其秘密、长期目标；角色关系；活跃与已结束剧情线；当前章节之前的历史；用户希望的故事风格/节奏/基调。
**负责回答**：**下一章应该发生什么？**
**产出**：Chapter Blueprint（PLAN，见 2.2）。
**不做**：正式文学行文（正文本属 POV Writer）；不直接把任何内容写入 Canon。

### 2.2 Chapter Blueprint（章规划，PLAN 对象）

每章首先生成详细 Blueprint，不能只是「今天用户和莉亚第一次见面」。至少包括：

- `chapter_goal` / `dramatic_question` / 时间范围（**`planned_start_tick` / `planned_end_tick`**——Plan 时间，见 §四）；
- 本章重点剧情线；`opening_state` / **软期望集：`closing_pressure`（收束压力）/ `desired_development` / `soft_outcomes` / `chapter_questions_to_advance`**；
- `scenes[]`：每场含 purpose / 时间（planned）/ 地点 / POV / 参与人物 / 人物进入场景前的目标 / `required_beats` / `optional_beats` / 可揭示信息 / 必须隐藏的信息 / 用户是否在场 / 可能出现的 User Gate / scene exit / elasticity；
- 三档可变更性（§三）：required narrative objectives / optional development / flexible scene arrangement。

**措辞律（V3-0R）**：软期望**不是 postcondition**——`closing_pressure` 表达「这一章朝哪里压」，不表达「必须到达哪里」。
**硬条件只允许**：**世界规则 / 已发生因果 / 不可撤销事实**。「作者希望本章结束时用户和莉亚成为朋友」不是硬条件——否则 Resolver 再强，Director 也会偷偷把关系绕回去（铁路化）。

**第一原则**：**Chapter Blueprint 是 PLAN，不是 CANON。规划过但实际没有发生的内容绝不能进入世界历史。**

### 2.3 Scene Planner / Scene Dossier（场景执行规划）

执行每一场之前，依据：Blueprint + 当前最新世界状态 + 前一场的**真实结果** + 用户刚刚做出的行为 + 当前 POV 的认知，生成 Scene Dossier——告诉 Writer：**当前这一场具体应该怎样展开**（它是对 Blueprint 的即时再规划，不是另起计划）。

### 2.4 POV Writer（正文写作者）

**只负责**：把已经规划并经过世界规则允许发生的事情**写好**（Narrative Passage 正文）。
**纪律**：
- 一场一个主 POV；禁止无控制 head hopping；只有明确 scene transition 才可切主视角；
- 必须遵守当前 POV 的**限知**；World Director 知道的秘密不自动泄漏给 POV Writer；
- Writer 不是世界规则裁判——世界规则裁定在 §2.6（用户行为）与 Director/Scene 层（世界侧）。

### 2.5 User Gate（用户意志门）

用户是世界里的真实角色。**当继续生成会替用户决定「有意义的意志行为」时，故事必须停止。**

| 可自动（不停） | 必须 User Gate（停） |
|---|---|
| 用户已经选择跟随某人，后续正常走路 | 说什么 / 是否答应 / 是否拒绝 |
| 自然身体动作 | 是否攻击 / 是否表白 / 是否撒谎 |
| 不影响人格与重大关系的小动作 | 是否透露秘密 / 重大感情反应 |
| | 会明显改变关系或剧情的行为 |

**判据**：只在「如果系统替用户决定，用户可能会介意」时停。
**呈现**：2–4 个自然行为选项 + 自由输入。**用户选项表达的是角色行为，不是剧情纲要。**

### 2.6 Action Resolver（行为裁定器）

**用户输入只表示 USER INTENT，绝不自动等于 WORLD FACT。**
例：用户输入「我拔剑刺向卫兵」——系统必须根据用户角色是否有剑、能力、身体状态、当前地点、世界规则、对方状态、环境，裁定真实结果。
**输出**至少：`interpretation` / `outcome` / `actual_action` / `consequences` / `state_effects` / `participants` / `replan_scope`。
`replan_scope` 第一版只三值：**NONE | SCENE | CHAPTER**。
裁定结果**不悬空**：经 **ACTION OUTCOME COMMIT**（§2.7 微观结算的 User Action 臂）立即落地为 Canon——用户行为的后果与正文段同级入史，不等到章末。

### 2.7 结算两级：SEGMENT / SCENE COMMIT（微观，落地）与 CHAPTER SETTLEMENT（章末，压缩与收束）

**微观结算（V3-0R 修订——唯一的事实落地边界）**：每一段真正落地的 narrative segment、每一次 User Action 的裁定结果、每一个 Scene 边界，都**立即**以 **SEGMENT COMMIT / SCENE COMMIT** 把「事情现在已经真的发生了」写进 Canon：

```
Narrative Segment（正文段） / User Action 裁定结果
      ↓ SEGMENT COMMIT（一个事务）
Canon 立即成立：
  ├─ narrative_passage（正文，不可变）
  ├─ world_event（沉淀事实）+ current_state effects
  ├─ actor_memory / belief 增量（亲历者）
  ├─ user action outcome（经 Action Resolver 裁定）
  └─ story_tick 推进（actual ticks）
      ↓ 下一段 / 下一 Scene（读得到刚 commit 的一切）
...
      ↓ CHAPTER SETTLEMENT（章末；压缩与收束——不做第一次落地）
  chapter summary / narrative memory 压缩 / storyline 推进·收束 /
  hooks / 记忆显著性 / 章状态关闭 / 下一章输入包
```

**反例（为什么不能只留章末）**：Scene 2 里用户回答「我父亲刚去世」——Scene 3 的莉亚认知、世界状态、后续 Scene Planner 必须**立刻**把它当正式事实。若等到章末才落地，场与场之间就活在「未被承认的事实」上，运行链断裂。

**Chapter Settlement 只负责**：「这一章结束以后，我们怎样整理已经发生过的东西」——摘要、压缩、线推进/收束、hooks、显著性、章关闭、下一章输入包；**它不负责第一次让事实成为事实**（那是 SEGMENT/SCENE COMMIT 的职责）。

**下一章 Director 主要读取**：World Bible + Current State + Chapter Summaries + Active Storylines + relevant Actor Memories——**而不是把整本小说全文重新塞入上下文**。

---

## 三、规划必须允许被用户真正改变（反铁路剧情）

1. **三档可变更性**：Blueprint 区分 required narrative objectives（章目标——如「莉亚与用户第一次真正认识」）、optional development、flexible scene arrangement（候选实现方式——如「一起去镇里」只是候选之一）。
1.5 **硬条件只允许**：世界规则 / 已发生因果 / 不可撤销事实——软期望（`closing_pressure` / `desired_development` / `soft_outcomes` / `chapter_questions_to_advance`，§2.2）**永远不是 postcondition**；「必须让用户和莉亚成为朋友」这类作者愿望不得把 Director 变成铁路调度。
2. 用户行为使某场景不成立时，**改剧情，不是把用户拉回原计划**（禁止铁路剧情）。
3. **三层吸收**：
   - 小变化 → Writer 自然吸收；
   - 场景级变化 → 重规划 Scene（replan_scope=SCENE）；
   - 章节级变化 → World Director 重规划**剩余 Chapter**（replan_scope=CHAPTER）。
4. **已完成正文与已发生世界事实永远不重写**（append-only；修正以后续事件到达）。

---

## 四、时间模型：story_tick / story time（统一刻度）

现状（dogfood 已暴露混乱）：ISO calendar + real clock + run 时间三套混成用户时间线（详见附录 A 审计 §A4）。

新架构**不围绕旧时间线打补丁**，逐渐引入统一刻度：

```
底层：story_tick —— 只记录故事世界已经经过多少时间
显示层：World Calendar（属于 World Bible）决定怎样展示
  例①：story_tick → 帝国历105年10月1日上午9点
  例②：story_tick → 霜月第十八日
```

纪律：
- **tick 语义（V3-0R 裁定）**：`story_tick` = **整数世界时间单位**（数据层唯一形态，单位粒度与含义由该世界的 World Calendar 解释——**数据库不得依赖地球公历**）。MVP（Gold Scenario 帝国历）在 V3-1 落表前钉死具体粒度（建议 1 tick = 1 分钟；历法只做解释，不参与排序）；
- **Plan 时间 ≠ Canon 时间**：Blueprint/Dossier 携带 `planned_start_tick` / `planned_end_tick`（Plan）；真正落地时写 `actual_start_tick` / `actual_end_tick`（Canon）——用户行为可以把计划 10:00 的场拖到 11:20，**两套字段不许共用一个「story_tick 起止」**（这也是 Plan≠Canon 的时间版本）；
- **排序与因果基于 story time**（同一世界内单调、可比较）；
- 世界日期格式属于 World Bible（每世界自己的历法，可完全虚构）；
- wall clock **只用于系统 bookkeeping**（行时间戳、审计），不进入用户时间线；
- **不允许三套时间混成一个用户时间线**（旧链的数据面保持现状不改写，新链自始单一刻度）。

---

## 五、世界真相与小说正文分离

现有 `world_event` 不应承担整篇小说正文。新链至少区分：

| 对象 | 回答的问题 | 内容 |
|---|---|---|
| **Narrative Passage** | 当时**具体怎样**发生的？ | 用户真实看过的正式小说正文（POV Writer 产出，不可变） |
| **World Event** | **到底发生了什么**？ | 从正文**沉淀**出的结构化历史事实；带 participants / significant effects / story time |

例：正文「莉亚站在石阶上第一次看见刚下马车的艾伦……」（passage）→ 世界事件「莉亚与艾伦第一次在宅邸前见面」（event）。
**准入律**：不是正文所有细节都变成 state；**只有对未来连续性真正重要的事实才进入 Current State**。

---

## 六、记忆体系六分、「三种知道」与角色记忆域

不要把所有东西叫 memory。新分类（原 §5 双投影与记忆温度的对照见附录 A）：

| # | 类别 | 语义 | 与旧面的关系 |
|---|---|---|---|
| 1 | **World Bible** | 稳定世界规则、设定、历史背景（版本化） | **权威独立（V3-0R）**：`world_bible_revision` 自带 `world_id` + `revision`（premise / genre / tone / calendar / physics / magic_rules / geography / society / politics / technology / religion / history / hard_rules / narrative_preferences）。**`world_lore_fact`（0020 无 world_id、`scope=world` 是「所有会话共有」的旧语义）不作 per-world Bible 存储**——只复用其 authority/proposal 思想；方向 = **World Bible → projection/adapter → legacy lore view**，不许反 |
| 2 | **Event History** | 真正发生过的事情，append-only | = 现 `world_event`（语义收窄为「沉淀事实」，见 §五） |
| 3 | **Current State** | 当前仍然为真的事实 | = 现 `world_state_fact`（CURRENT/SUPERSEDED 语义直接复用） |
| 4 | **Actor Memory / Belief** | 某个 actor 经历过、听说过、相信、误解、推断出的内容 | 域一「亲历/听闻」的正式化 + 新增 belief；**新域** |
| 5 | **Narrative Memory** | 剧情线、伏笔、开放问题、章节总结、未完成承诺 | `world_storyline` 是其结构半；新增 chapter summary/hooks |
| 6 | **Chapter / Scene Plan** | 未来规划，**不是真实历史** | **新域**（Blueprint/Dossier） |

### 6.1 三种「知道」（V3-0R 立本体；实现可后置）

```
WORLD TRUTH      世界真实发生了什么（event / state）
ACTOR KNOWLEDGE  每个 actor（莉亚 / 用户角色 / 主角 2…）各自知道、相信、误解什么
READER EXPOSURE  现实用户作为读者已经看到了什么（passage 级暴露面）
```

- 多 POV 一落地必然出现 **Reader Knowledge ≠ Player Character Knowledge**：第二章切到主角 2，读者看见莉亚父亲参与政变——但世界里的「表弟」**不知道**。
- 用户的输入始终是对**用户角色**的 intent：系统不得因为玩家知道，就把知识塞进用户角色（metagame 规则可后置，**本体必须先对**——否则多 POV 落地即重构 cognition）。
- **narrative passage exposure ≠ actor cognition**：`reader_exposure`（读者看过哪些 passage）是独立记录面，**绝不自动写入** Player Character Memory / Actor Memory。

- **hot / warm / cold 降级为 retrieval policy**（未来检索策略），不再是 memory 类型本身。
- **角色记忆独立成域**：莉亚对用户角色的记忆、莉亚对母亲的记忆、父亲对莉亚的判断、主角 2 对某事件的误解、用户角色对别人知道什么——都属于虚构世界，**绝不污染**：现实 User Profile、现实用户隐私、现有 Persona × User `relationship_memory`。

---

## 七、角色实体模型

### 7.1 用户角色：从 package declaration 升格为 durable world entity

现状（D-1）：`WorldPackage.user_character` 只是 prompt material——无 store row、无 persona、无完整状态。**只适合旧版**。
新系统：用户进入每个世界时创建自己的角色，拥有独立身份：背景 / 外貌 / 能力 / 限制 / 位置 / 状态 / 关系 / 自己知道什么。⇒ 需要 **durable player-character 模型**。
**边界**：不为统一概念大改现 `world_actor`（继续代表 AI-controlled actor）；新建独立的 user-controlled durable entity，再统一进入 participant namespace（见 §八/§九）。

### 7.2 WorldActorProfile：叙事职责与 CharacterCard 分离

- `CharacterCard` 回答：**她是谁**（现役 0019 表，保留）。
- `WorldActorProfile` 回答：**她在当前世界/小说中的作用**——`story_role`（PROTAGONIST / MAJOR / SUPPORTING）、`pov_eligible`、`pov_weight`、`long_term_drive`、`current_arc_seed`、`private_context`。
- 同一个角色模板在不同 world fork 中可以拥有不同故事身份（模板 fork = `template_world_id`，现役复用）。
- **落地位置（V3-0R）**：`world_actor_profile` 与 durable player character **同归 V3-3（World Cast & Player Identity）**——Director 第一次规划莉亚时必须知道「她是主角不是普通居民 / 她能作 POV / 她这部小说里的长期弧是什么」；**不许把这些塞回 CharacterCard**（卡回答「她是谁」，档案回答「她在本世界里是什么人」）。

---

## 八、Narrative Domain 实体清单（研究级；不立刻落最终 schema）

- `world_bible_revision`（World Bible 版本化）
- durable player character（用户角色）
- `world_actor_profile`（叙事职责）
- `world_chapter` / `world_chapter_plan`（章与章规划）
- `world_scene`（场；含 dossier）
- `narrative_passage`（正文）
- `user_gate`（停点与选项）/ `user_action`（用户行为与裁定结果）
- actor memory / belief
- `reader_exposure`（读者暴露面；**≠ actor cognition**，见 §6.1）
- chapter summary / narrative memory（线/伏笔/开放问题/承诺）

**硬要求**：**Plan 与 Canon 必须物理或语义分离**——绝不能让「World Director 计划过」自动成为「世界已经发生」。（落地建议：Plan 类表带 `plan_status`；事实写进 `world_event` / `world_state_fact` / memory 面**只经 SEGMENT/SCENE COMMIT 事务**——章末 Settlement **不是**落地边界，见 §2.7。）

---

## 九、工程迁移原则（并行新链）

1. **并行新链**：不直接把现 `run_generated_step()` 改成新系统。旧生产链暂时继续存在、继续全绿。
2. **新增明确 Narrative V3 模块**（建议名）：
   - `elc/world/director.py`（Director + Blueprint）
   - `elc/world/scene.py`（Scene + Dossier）
   - `elc/world/writer.py`（POV Writer）
   - `elc/world/action.py`（User Gate + Action Resolver）
   - `elc/world/settlement.py`（结算两级：**SEGMENT/SCENE COMMIT 事务** + Chapter Settlement 压缩收束）
   - 配套：`elc/world/time.py`（story_tick / World Calendar）、`elc/world/bible.py`、actor profile / player character 面。
3. **当新纵向切片真正完成后，才逐步切 UI 和退役旧逻辑**（旧链退役本身是一次显式裁决，不在本稿预设）。
4. 迁移编号接现 head（0028 之后）；新表一律走现 store 纪律（幂等/值语义拒收/append-first）。

### 9.1 直接复用（不改动、不重写）

`world` / `template_world_id` / `world_actor` / `character_card` / voice library / `world_event` / `world_state_fact` / `world_storyline` / participants / 角色认知视图（C1，host 世界端口）/ 世界规则面 / Persona 生成基础（provider、validator、streaming）/ 教学系统 / 用户配置与安全边界。

### 9.2 legacy 保留、退出新主线（不删）

letter-triggered `world_run`；NOTICE/RESPONSE 停点语义；`world_reveal_item` 作为核心推进机制；parked turn 作为世界运行中心；每步 direction；「letter is the only world starter」；WorldNarrator 单体（其 prompt 构造与严格解析能力被新链拆分复用，不再承担停点决策）。

### 9.3 现役表处置一览

| 现役表 | 处置 |
|---|---|
| `world` / `world_actor` / `world_conversation` | **直接复用** |
| `character_card` | **直接复用**（+ 新 `world_actor_profile` 分离叙事职责） |
| `world_event` | **复用升格**（语义收窄为「沉淀事实」；正文另落 `narrative_passage`） |
| `world_state_fact` | **直接复用**（Current State） |
| `world_storyline` | **复用升格**（Narrative Memory 的结构半；接章总结/伏笔队列） |
| `world_lore_fact` | **legacy 保留**（0020 无 `world_id`、`scope=world` 是「所有会话共有」的旧语义——**不作 per-world Bible 存储**；只复用其 authority/proposal 思想。权威方向 = World Bible → projection/adapter → legacy lore view） |
| `world_run` / `world_reveal_item` | **legacy 保留**（退出新主线，不删、不迁） |
| 新增（MVP 最小集） | `world_chapter` / `world_chapter_plan` / `world_scene` / `narrative_passage` / `user_gate` / `user_action` / `world_actor_profile` / player character / actor memory（belief）/ `reader_exposure` / chapter settlement/summary |

---

## 十、第一阶段 slicing（MVP：一个世界、一名 AI 主角、一名用户角色、一章）

### 10.1 不先做（规模纪律）

多世界完整 UI；十几个主角；复杂遗忘系统；学习桥（P17 维持待命）；多种 World Template。

### 10.2 Gold Scenario（固定验收剧本）

**帝国历 105 年 10 月 1 日**：
- 主角 1：莉亚；用户角色：远房表弟；
- 莉亚父亲凌晨赴帝都；莉亚母亲上午从乡下带用户回来；
- 用户与莉亚第一次见面；**至少一次自由 User Gate**；
- ActionResolver 裁定；故事根据用户选择继续；
- 第一章结束；Settlement；生成第二章 Blueprint。

**完整验收链**：
```
创建世界 → 创建角色 → Chapter Blueprint → Scene Dossier → POV prose
→ User Gate → User Action → Action Resolver → 必要时 Replan → 继续正文（每段 SEGMENT COMMIT）
→ Chapter Settlement → Chapter 2 Blueprint
```

**结构验收 12 条（V3-0R 补齐——「好玩」是用户门，不作唯一工程门）**：

```
① Director 产出完整 Blueprint
② Writer 正确保持莉亚 POV
③ 秘密没有提前泄漏
④ User Gate 只在真实意志点触发
⑤ 用户自由输入被 Resolver 裁定
⑥ 一个用户选择真正让原计划失效
⑦ Replan 后没有强行绕回旧计划
⑧ Scene 3 能读取 Scene 2 已 commit 的事实
⑨ 第一章实际结果与 Blueprint 可以明显不同
⑩ Chapter Settlement 生成摘要
⑪ Chapter 2 使用真实 Chapter 1 结果，而不是原计划
⑫ 重启后能够从最新 narrative state 恢复
```

**门**：12 条结构验收全绿 **+** 用户亲验「是否有趣」——两者同时，才不扩大规模。

### 10.3 刀序（V3-0R 微调版，供总控复核）

| 刀 | 内容 | 门/兑现面 |
|---|---|---|
| **V3-0R** | 本修订（单一评分：结算两级 / Bible 权威 / V3-3 扩面 / Reader Exposure / tick 语义 / canonical 隔离）——**复核通过即冻结 V3.0** | 复核通过才开 V3-1 |
| **V3-1** | **Narrative foundations**：story_tick（整数刻度 + 粒度裁定）+ **chapter/scene 生命周期类型** + **Plan/Canon 边界类型**（不只 Calendar） | tick 单调可比较；计划时间与事实时间类型分离可测 |
| **V3-2** | World Bible（`world_bible_revision` 权威面 + 读取；**权威方向 = Bible → projection → legacy lore**） | Bible 版本化、可引用；与 legacy lore 不双权威 |
| **V3-3** | **World Cast & Player Identity**：`world_actor_profile`（PROTAGONIST/POV/drive）+ durable player character + participant namespace | Director 的 cast 输入齐备（谁是主角/可 POV/长期弧）；旧 `world_actor` 不动 |
| **V3-4** | Director + `world_chapter(_plan)`（Blueprint 严格 schema；软期望集 + 硬条件律；Plan≠Canon 落表） | 计划不上屏入史；`closing_pressure` 非 postcondition 有钉 |
| **V3-5** | Scene + Dossier + POV Writer + `narrative_passage` + **SEGMENT COMMIT（event/state 即时落地）** | 正文入 passage；一场一 POV；秘密不泄漏；commit 后下一场立即可读 |
| **V3-6** | User Gate + `user_action` + Action Resolver + **OUTCOME COMMIT** + SCENE/CHAPTER replan | 拔剑例：裁定≠意图；用户选择让原计划失效后不许绕回 |
| **V3-7** | Actor Memory/Belief + **Chapter Settlement** + chapter summary + Narrative Memory | 章末只做压缩/收束；下一章只读摘要面 |
| **V3-8** | Gold Scenario 端到端 + 最小阅读面 + **结构验收 12 条** | 12 条全绿 + 用户亲验「好玩」；通过后才议 UI 切换与旧链退役 |

### 10.4 真实模型接线基线（V3-8f 补写，2026-10-13）

**来源**：V3-8e 收口后的首次真实凭证亲验（「好玩」门）暴露「连流程都跑不通」——三处接线缺陷（时延上限 / 值类型合同 / 长驱动等待），本基线把该面补进同一套设计（基准纪律：在方案内定义并完善，不另起炉灶）；后续真实接线刀必须据此校准：

1. **时延预算与时限校准**：真实模型的一次写作是「数十秒至数分钟」量级的往返（实测 43–72s/次，推理 token 占大头）；此前世界驱动沿用通用 egress 默认时限 30s ⇒ 每次驱动必死。**世界驱动的 egress 时限独立校准**：由装配层从 live egress 派生（同坐标、同密钥源、仅覆盖 timeout；默认 180s），页面仍以轮询呈现进度（不引入 streaming；异步驱动 / streaming 都是后刀的显式重开项）。
2. **值类型合同（prompt 面）**：四臂 prompt 列举字段名时必须**逐字段写明 JSON 值类型**；文本型字段是**单个字符串**（多条目并入同一字符串、以换行分隔——与 `must_hide` 的碎片分割律同源），数组 / 整数 / 三词枚举逐处点名。缺此合同 ⇒ 模型对复数语义字段自然输出数组、严格解析拒收（`bad-shape`）。**canonical 类型与落库形态不变**（照 DATA §26.2.1 与机件逐字）；解析器在严格之外仅对「文本字段收到字符串数组」做确定性连接（宽容方向、REGISTER 成文）。
3. **失败码不得压平**：缝与 persona 适配器的短码（`timeout` / `http-<status>` / `missing-secret` / `not-configured` / …）必须透传到用户面并译成可行动人话；一律压成 `transport-error` 会把「超时」误说成「去检查端点 / 密钥」。
4. **长驱动不误报**：单次驱动可含多次模型往返（`submit` ≈ 裁定 + 重规划 + 续写）；服务端对 V3 写路由的 host 等待必须覆盖该预算（≥ 单次时限 × 驱动内最大真实调用数）。故事仍在推进时，用户面不得出现「失败」假象（页面轮询已呈现进度）。
5. **等待可见与语言可切（V3-8g 补写，用户亲验反馈）**：**等待必须可见**——驱动期间页面给出可见进行态（动效 / 已用时 / 阶段提示），且**忙碌期间的任何点击必须得到明确反馈**（绝不静默吞掉）；「数十秒至数分钟」的等待不得留白（仍以轮询呈现进度；streaming 保持后刀显式重开项）。**正文语言随阅读面设置**——世界正文及蓝图 / 场计划 / 裁定的自然语言内容随阅读面语言设置（默认 `en`＝学习产品本意；可切 `zh` 供测试与产品选择），JSON 键、身份串与三词枚举不受影响；**已入正史的段落永不改写**（切语言只影响此后新写的段落）。
6. **正文连续律（V3-8g 补写）**：写作者臂的事件列表是**已发生且已被叙述**的事实——新段必须**推进**故事（新的节拍与知觉），**绝不复述**列表中已有的叙述；相邻段落不得近重复（验收以相似度观察为准）。

**纪律不变**：双门（12 条结构验收全绿 + 用户亲验「好玩」）；两者同时通过前不切主 UI、不退役 Legacy V2。

### 10.5 阅读面核心循环落法（V3-8h 补写，2026-10-13）

**来源**：用户亲验反馈两条（「模型运行一次，会在没有任何剧情需求点停下……用户无需做任何选择」「用户根本无法决定章节走向」）——两者都是 **§1.1 核心循环的已写条款**，此前只落了骨架（一段一停；章间无输入面）。本落法定两面的实现口径：

1. **停点律（章内）**：一次驱动（页面「继续」/「提交」）**跑到下一个真停点**才停；真停点取三——①**User Gate 打开**（用户意志点，§2.5 判定表为据）；②**章内计划尽**（可结章，停在「结束本章」前）；③**单次驱动上限**（段数上限；触顶时页面必须给明确说明句——「本次已连写 N 段，点『继续』接上」——有故之停，不得无解释之停）。段与段、场与场之间**自动续写**（SEGMENT / SCENE COMMIT 后不停）；「提交」同样在裁定与续段之后继续跑到下一停点。**章节边界本身是真停点**（新章计划落成 / 结算待发），一次驱动不跨章。
2. **章间作者层（章与章之间）**：结算之后、计划下一章之前，用户以作者层参与方向，形态先落**两式**（「导演给几个故事方向建议」式登记后刀）：①**让世界自行发展**（默认——直接下一章）；②**用户输入下一章基调 / 方向**（自由文本）。所输方向作为**软期望**注入下一章 Director 计划（措辞律：方向表达「朝哪里压」，**绝非 postcondition**；不得替用户发明剧情事实）；作者层输入只影响**计划面**，**不写入正史**。

**纪律不变**：双门（12 条结构验收全绿 + 用户亲验「好玩」）；两者同时通过前不切主 UI、不退役 Legacy V2。

---

## 附录 A：旧范式 → 新范式映射审计（对现役设计/表/代码逐面）

### A1. living-world-spec 逐节处置

> **V3-0R 落地**：spec 已同步执行结构隔离——§2 与 §4 重标题为 **【Legacy V2 Runtime】**（非 V3 产品定义）、术语表拆为 **V3 术语（第一权威）** 与 **Legacy V2 术语** 两表、受影响节加【v3 处置】标注；**旧文不删**（历史与旧链对照用）。

| 节 | 处置 | 说明 |
|---|---|---|
| §1 愿景 | **修订** | 「用户为世界而来，把英语学会了带走」保留；「世界在用户每次回信后运转一步」废止（已加处置标注） |
| §2 核心体验循环 | **废止→Legacy 节** | 信件循环不再是核心；新循环见本稿 §1.1；原节重标题为 Legacy V2 Runtime |
| §3.1 世界构成 | **保留升格** | 设定→World Bible；时间→story_tick/World Calendar；阵容/事件树/记忆→新实体面 |
| §3.2 角色与关系/用户角色 | **保留升格** | 亲历/听闻→Actor Memory（域一正式化）；v2.2 用户角色款→durable player character（§七） |
| §3.3 多世界 | **冻结至 MVP 后** | 互不影响/一次住一个/template fork 保留设计；不先做 UI（已加处置标注） |
| §4.1 双启动条件 | **废止** | 世界不再依赖回信启动；揭示降为 legacy |
| §4.2 World Run 七步/checkpoint | **legacy→Legacy 节** | 旧链运行语义保留；新主线走章/场；原节重标题为 Legacy V2 Runtime |
| §4.3 事件池 | **修订** | 池不再驱动生产；事件由 Director 规划、经 Scene 落地（**SEGMENT COMMIT**）沉淀（池可作为素材） |
| §4.4 走向选项 | **升格** | 高频步内操作废止；方向选择成为**章间**作者层 |
| §4.5 可见性 | **保留** | 焦点视角 = 场景 POV 的天然前身；四档梯度保留为渲染设置候选 |
| §4.6 特殊时刻协议 | **legacy** | NOTICE/RESPONSE/DIRECTION 保留于旧链 |
| §4.7 密度 | **修订** | 由 chapter/scene 节奏（Blueprint 内）取代；用户亲调转为偏好输入 |
| §5 记忆系统双投影 | **重构为六分 + 三种知道** | 记忆温度→retrieval policy；状态投影=Current State（保留）；新增 Actor Memory/Narrative Memory/Plan/Reader Exposure |
| §6 教学系统咬合 | **保留** | 三天线/五砝码/三层/延迟/闭环全部有效；咬合点从「信/走向」扩展到「章/场/User Gate」 |
| §7 IA | **修订** | 世界第一层保留；案头/沓/信箱降 legacy 呈现；新 IA = 世界书架→世界主页→Chapter/Story Reader（等切片后设计） |
| §7.2 新手路径 | **修订** | 首开 = 创建世界/角色（原「Nell 第一封信」路径降 legacy，已加处置标注） |
| §7.3 世界创建三档 | **升格** | 创建世界 + 创建角色成为核心路径 |
| §7.4 多世界 UI | **保留（MVP 后）** | 世界架设计保留 |
| §8 设置面 | **修订** | 世界级设置映射到新模型（风格/节奏/基调成为章间偏好） |
| §9 世界包与语言供给 | **保留升格** | 包升格为 World Bible 载体；affordance 与组合覆盖保留；教学贴合面重定位到新咬合点 |

### A2. cognition-and-narrative-quality 逐域处置

| 域 | 处置 | 说明 |
|---|---|---|
| 域一 认知模型 | **修订 v1.3** | 三源（公共/亲历/听闻）保留；温度框架→六分记忆；新增 Actor Memory/Belief 独立域；传闻失真后置项 P1 语义随新域重挂 |
| 域二 剧情线 | **保留升格** | storyline 结构直接进入 Narrative Memory；收束/伏笔/线龄语义保留 |
| 域三 声音库 | **保留** | voice 库照旧（prompt 材料）；POV Writer 的「声音像她」沿用 |
| 域四 叙事工艺 | **保留** | 三铁律 + 反 AI 味负例无条件注入原则沿用（改为注入 POV Writer 面） |

### A3. 代码模块处置

| 模块 | 处置 |
|---|---|
| `world/store.py`（world/actor/event/state/storyline 面） | **直接复用**（新表按同纪律扩面） |
| `world/package.py`（v7 包） | **复用升格**（升为 World Bible 载体；`user_character` 节迁 durable 面） |
| `world/narrator.py` | **legacy 单体拆分**：prompt 构造/严格解析/声音区/工艺护栏被新链（Writer/Director）复用；停点决策退役 |
| `world/engine/*` + `orchestrate.run_*` | **legacy 保留**（引擎面测试在册） |
| `world_reveal_item` 链 + web 的 inbox/direction/continue 端点 | **legacy 保留** |
| `host.py` 认知视图（C1） | **直接复用**（升级为 Actor Memory 的读面基础） |
| persona provider/validator/streaming、teaching、user_config、deletion、安全边界 | **直接复用** |
| 新链 | 见 §九 2（director/scene/writer/action/settlement/time/bible + actor profile/player character） |

### A4. dogfood 取证与旧范式病根的对应（E 取证吸收）

| dogfood 现象 | 旧范式病根 | 新范式处置 |
|---|---|---|
| 最新剧情显示错位（精确臂钉旧位） | 以「run 触发信」为归属的混排时间线 | 章/场结构取代 run 归属；story_tick 单一刻度 |
| 日期混乱/跨度不表达 | 三时间制混排 + 步内多日折叠 | §四：单一刻度 + Calendar 显示层；场景自带时间 |
| 选择行无日期/假回退句 | 走向选择被当「便条」渲染 | 走向升格为章间作者层（不再混入正文时间线） |
| 卡轮（seq23 GENERATING 三日） | letter 生产链单点故障无用户面 | 新链不依赖信件链；卡轮处置随 legacy 链维护刀 |
| 三线失衡/用户代称在场 | 无用户 durable 实体、无配比设计 | §七 durable player character + Blueprint 场景级参与设计 |
| 前端产品级视角 | 混排时间线无产品语义 | Chapter/Story Reader 重新设计（切片后） |

---

## 附录 B：十问自检（实现前必须答清）

1. **新核心循环**：创建/选择世界 → 创建主角与用户角色 → 进入世界 → 世界以持续小说发展（章内：POV 正文段即时 COMMIT、User Gate 停点；章末 Chapter Settlement 压缩收束；章间作者层）。
2. **权力**：Director=决定下一章发生什么（产出 Blueprint，不写正文）；Scene Planner=把章规划落为本场 dossier；POV Writer=按限知把已允许之事写成正文；Action Resolver=把用户 intent 裁定为 world fact（含 consequences 与 replan_scope）。另有两条边界权：**User Gate** 决定何时必须停下问用户；**SEGMENT/SCENE COMMIT** 决定「什么已经发生」，**Chapter Settlement 只决定「怎么整理已经发生的东西」**（§2.7，V3-0R 修订）。
3. **Plan vs Canon**：Plan 是未来意图（Blueprint/Dossier，含 planned ticks），Canon 是已发生事实（passage/event/state/memory/actual ticks）；计划过而未发生不得入史。**落地边界 = SEGMENT/SCENE COMMIT（微观、即时）**；Chapter Settlement 只做压缩与收束，不是唯一沉淀边界（V3-0R 修订）。
4. **User Gate 时机**：继续生成会替用户决定「有意义的意志行为」（说什么/答应拒绝/攻击/表白/撒谎/透露秘密/重大感情反应/明显改变关系或剧情）时必须停；可自动的是已选定跟随、自然身体动作、不影响人格与重大关系的小动作。
5. **用户输入≠World Event**：输入只是 intent；须经 Action Resolver 按能力/物品/身体/地点/规则/对方/环境裁定，产出实际发生的后果后，经 **ACTION OUTCOME COMMIT** 立即落地为事件（与正文段同级，不等章末）。
6. **Passage vs Event**：passage 回答「当时具体怎样发生」（正文，不可变）；event 回答「到底发生了什么」（结构化事实 + participants/effects/story time）；只有对未来连续性重要的事实进 Current State。
7. **Current State vs Actor Memory**：Current State 是世界层面「现在仍为真」的事实（无视角）；Actor Memory 是某一 actor 的经历/听闻/相信/误解/推断（有视角、可失真、可错误）。**第三种知道是 Reader Exposure**（读者看过哪些 passage）——独立记录面，绝不自动写入角色记忆（§6.1）。
8. **为何不改 world_run**：它是 letter-triggered 单发条的生命周期（触发信归属、停点语义），与新章/场生命周期不同构；原地改造会让旧链测试全红且混两套语义——并行新链、旧链保留才是正解。
9. **可直接复用**：world/template_world_id/world_actor/character_card/voice/world_event/world_state_fact/world_storyline/participants/C1 认知视图/世界规则/persona 生成基础/教学系统/用户配置与安全边界（§9.1）。**`world_lore_fact` 不在其列**——legacy 保留、不作 per-world Bible 存储（§六/§9.3）。
10. **第一条 vertical slice**：Gold Scenario（帝国历105年10月1日，莉亚/远房表弟/初见）沿 §10.2 验收链从「创建世界」跑到「第二章 Blueprint」；验收 = **结构验收 12 条全绿 + 用户亲验「好玩」**（两者同时）。
