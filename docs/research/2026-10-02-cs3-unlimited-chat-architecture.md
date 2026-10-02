# cs-3 架构调研简报：单角色无限聊天（无限对话 × 记忆外显）

> 程序：cs-3（命题已重定）｜本文件是 cs-3 开工裁决（DEC）与任务书（TASK）的直接输入。
> 调研执行者产出（2026-10-02）；全部读数与引文来自当日仓内实读（base `4ea75a1`，工作树干净）。
> 铁律⑱合规：六 canonical（PRODUCT_CONTRACT / DOMAIN_MODEL / STATE_MACHINES / DATA_MODEL / RUNTIME_ARCHITECTURE / IMPLEMENTATION_PLAN）全文扫读完毕 + 现役实现逐文件复核；证据行号随文标注。

## 0. 命题与判定标准（用户原话钉死）

> 「上不上摘要取决于当前的对话和记忆架构支不支持单角色单对话（用户以为的单对话，实际可在系统中自动切换对话或压缩上下文）无限聊天，而不是一个显式的 20 轮的数字。」

- **命题** = 单角色无限聊天体验：用户感知一直和同一角色聊；系统内自动压缩上下文/必要时无缝换会话投影，全部对用户透明。
- **判定标准** = 与同一角色连续对话 **N≫20 轮后早期关键事实仍在 prompt 内（记忆外显）**，而非窗口数字。
- 显式非目标：不改「用户以为的单对话」的感知面；20 只是现状实现常数，不是产品契约。

## 1. 现状数据流（复核确认，全部为当日实读）

### 1.1 每轮 prompt 的实际组成（`src/elc/persona/commands.py:567-683` PromptCompiler）

| 节 | 来源 | 有界性 | 窗口外记忆？ |
|---|---|---|---|
| `[persona]` | CharacterPackage 卡 | 有界（卡） | — |
| `[profile]` | DisclosedUserProfile | 有界 | 是（用户配置域） |
| `[contract]` | GenerationContract | 有界 | — |
| `[history]` | `get_conversation_window(conversation_id, 20)`（`controller.py:278` 常数；`conversation/store.py:794-870` SQL `LIMIT`，persona-visible 过滤：命令轮 + 非普通动作轮排除） | **20 轮硬窗** | 否 |
| `[relationship]` | `RelationshipView.active_memories`（`relationship/store.py:292-318`，**无 LIMIT**，按 created_at 全量 ACTIVE 行） | 随事实数线性、无上限 | **是（持久记忆主通道）** |
| `[episode]` | EpisodeView：`summary` + `open_threads` + `recent_events`（`persona/types.py:335-353`） | 有界（见下） | **名义上是，实际只覆盖窗口尾部** |
| `[note]`/`[channel]`/`[response]` | 附笺/通道/响应约定 | 有界 | — |

### 1.2 episode 投影现形（`src/elc/relationship/episode.py`）

- `EPISODE_WINDOW_MAX_TURNS = 20`（:128，与 `CONVERSATION_WINDOW_MAX_TURNS = 20` 镜像持等——P4-G1 禁跨包 import，`tests/phase4/test_p4_3_gates.py:161-183` 持等）。**episode 投影与 prompt 窗口读同一段 20 轮**，故 `[episode]` 不提供任何窗口外信息，除 `open_threads`。
- `summary` = 窗口内**最近 4 句用户话**逐字（每句截 120 字符，:112-113）——窗口滑过后即失。
- `recent_events` = 窗口内最近 8 个 slice 的 describe（:107）。
- `open_threads` = pair 的 ACTIVE `OPEN_THREAD` 记忆（:394-414）——**今日无任何 OPEN_THREAD 生产者，恒空**。
- 站位声明（:23-44，本刀的关键先例文本）：
  - 「one conversation, one episode」——`episode_id = ep-{sha256(conversation_id)[:20]}`（:246-262），一会话一行（`migrations/0010` UNIQUE index）；
  - 「``summary`` is **extractive, verbatim** … a model-written summary would be a **different projection** (a MODEL_PROPOSAL reading of the transcript), never this one」（:33-37）；
  - **预留钩子原文**（:28-32）：「the canonical text gives **no segmentation algorithm** … a future segmentation slice will **either bump `EPISODE_PROJECTION_VERSION` or land a second projection type**」；
  - 全历史注记原文（:123-127）：「``source_turn_sequence_start``/``_end`` are the first and last slice *of that window*, not of all history. A full-history episode is **a different projection** (a rebuild over the whole transcript, **with its own cost profile**), and **the canonical text pins neither**.」

### 1.3 CP4 投影管线（`src/elc/runtime/projections.py` + `relationship/projection.py`）

- 每轮 terminalize 后 enqueue 一个 RELATIONSHIP + 一个 EPISODE job（确定性 id `projection_id_for(type, turn_id)`），在 coordinator lease 释放后异步跑（RA CP4），失败不阻塞 turn、不回滚 transcript（RA §19/§21）。
- `EpisodeProjectionExecutor.project`（`projection.py:385-451`）：读源 slice → 解析 persona → 读 pair summary（scope 校验）→ `get_conversation_window(conversation_id, EPISODE_WINDOW_MAX_TURNS)` → `rebuild_episode` → `upsert_episode`。纯函数 + 内容版本摘要（`episode_version_for`，:265-301）→ 同真值重建 = zero-write replay。
- 删除面依赖 episode 可重建（`deletion/store.py:1106-1111` 收集 episode 重建键）——纯函数重建是删除契约的前提。

### 1.4 窗口外持久记忆的完整清单（现状诚实盘点）

1. **Relationship Memory**：17 模式确定性抽取（`relationship/candidates.py:147-248`：ZH 10 + EN 7），产出 `USER_STATED_FACT`，走 Recorder 全拒收序 + Domain Controller 门，全量 ACTIVE 行入 `[relationship]`。**这是今天唯一真正跨窗口的事实通道**——但覆盖率 = 17 个模式形状（名字/职业/居所/来自/喜好）。
2. **Episode summary**：只覆盖最近 4 句——窗口滑动后**不携带任何早期事实**。
3. 其余（`open_threads`/教学 evidence/learner state）不入角色 prompt（记忆分离，DOMAIN_MODEL §17）。

**结论（现状判定）**：连续聊到第 60 轮时，第 3 轮说的事实只有被 17 模式捕获才在 prompt 里；任何叙述性内容（计划、事件、话头、故事线）全部随窗口滑出。**「无限聊天」现状不成立；缺口 = episode 投影只读窗口。**

### 1.5 会话与角色绑定（mc-0 现状）

- 每角色一会话：`web.py:1253-1261`——Nell → `web-default`，其余角色 → `web-<character_id>`；`/api/partner` 档案「近况」面读该会话的 episode 行（`web.py:1215-1227`）。
- `ConversationStatus` 只有 `ACTIVE/CLOSED` 二值（`conversation/types.py:43-45`）；**无任何卷/段/归档生命周期**。
- 页面显示窗口 `HISTORY_TURNS = 50`（`web.py:379`，`get_user_visible_conversation_window`——与角色读面是两个过滤、同一张表）。

## 2. canonical 穷尽：已设计 / 已裁 / 未裁 三栏清单

### 2.1 已设计（canonical 明文，直接约束本刀）

| # | 依据 | 原文/要点 | 对 cs-3 的约束 |
|---|---|---|---|
| D1 | DATA_MODEL §5.3 | Episode 十列字段表；「Episode 是 transcript-derived projection，可重建，不拥有 Conversation truth」 | 摘要方案必须保持「transcript 派生 + 可重建 + 不拥有 truth」 |
| D2 | DATA_MODEL §26 | 可重建投影清单含「Episode summary/index」「Relationship retrieval index」「FTS/vector index」；「不可把 rebuildable projection 当唯一事实来源」 | 全历史折叠投影合法且预期可重建；检索索引被 canonical 点名（远期选项的存在依据） |
| D3 | DATA_MODEL §1.4 | 「Version every derived model」 | 摘要语义变更 = `EPISODE_PROJECTION_VERSION` bump（episode.py 预留钩子的 canonical 依据） |
| D4 | DATA_MODEL §22.1 | ProjectionJob「source-aware + version-aware revalidation，不允许 blind SQL replay」 | 折叠必须是源派生纯函数；不可引入「只靠上一次摘要状态」的不可重放依赖 |
| D5 | DOMAIN_MODEL §4 + RA §11 | Persona Runtime consumes：CharacterPackage / RelationshipView / **EpisodeView** / WorldLoreView / DisclosedUserProfile / **ConversationWindow** / LanguagePolicy / GenerationPolicy / EphemeralTeachingDirective? / GenerationContract（十项） | **GenerationContext 无检索字段、无「旧卷摘要」字段**——prompt 新记忆面只能经 EpisodeView/RelationshipView 语义承载，或改 canonical |
| D6 | DOMAIN_MODEL §17 | 记忆七分：User Profile / Learning / CharacterPackage / Relationship / Episode / World-Lore / Retrieval Index；「Learning 可跨 Persona 汇总；Relationship 不跨 Persona 泄漏」 | episode 属会话/角色域，不得跨 persona；事实通道归 relationship |
| D7 | DOMAIN_MODEL §18 | proposal-only 组件（Relationship Recorder 等）；「推理调用可以物理合并，但 Authority 不合并」；Domain Controller 决定 VALIDATE/COMMIT/REJECT/ABSTAIN | 若未来做模型摘要，模型只能作 proposal 源、走 Controller 门（`projection.py:91-101` 的 MODEL_PROPOSAL 形态已是先例） |
| D8 | DOMAIN_MODEL §18.1 | 「retrieved memory text」属 UNTRUSTED_CONTENT；高敏感持久化需显式许可 | 摘要文本进 prompt 须走既有 untrusted 帧纪律（`_framed_untrusted_section`） |
| D9 | DOMAIN_MODEL §13 | ConversationPriorityView 有 `natural_break_available` | 会话内唯一 canonical「自然断点」面（B 案唯一切点依据） |
| D10 | DOMAIN_MODEL D-INV-011 | 「Relationship / Episode / RetrievalIndex 均为投影或独立域，不拥有 transcript truth」 | 同 D1，约束任何摘要方案 |
| D11 | RA §19 + §CP4 + §21 | 投影在 canonical turn 后、lease 释放后跑；「projection 延迟或失败不得阻塞下一 user-visible turn」；「Relationship/Episode failure → turn still succeeds, projection retry/rebuild」 | 全历史重建成本落在 CP4 异步位，不影响 turn 延迟 |
| D12 | RA §7 | 禁绑清单含「Transcript + retrieval index 不共事务」 | 检索索引（若做）独立事务纪律 |
| D13 | PRODUCT_CONTRACT §9 | 「Episode Memory = 当前会话/故事/近期事件/未决上下文」「Retrieval Index = 可重建，不是 source of truth」 | Episode 的产品语义 = 故事连续性（叙述），不是事实清单（事实归 Relationship Memory） |
| D14 | PRODUCT_CONTRACT §11.1 + IP DoD #25 | 删除 canonical user source 后 solely-derived Relationship/Episode/Index 必须「删除或重建」 | 折叠必须保持可重建性（同 D1/D4） |
| D15 | DATA_MODEL §3 + STATE_MACHINES | Conversation 实体只有 status ACTIVE/CLOSED；**无会话生命周期状态机**；turn_sequence/message_sequence 每会话独立 | B 案（分卷）在 canonical 无任何现成转移面可依 |

### 2.2 已裁（仓内裁决/先例，非 canonical 但有钉/有 DEC）

| # | 裁决 | 位置 | 对 cs-3 的约束 |
|---|---|---|---|
| J1 | mc-0：每角色一会话（`web-<character_id>`，Nell→`web-default`） | `web.py:1253-1275` + `migrations/0019` 注释 | B 案要重写此规约（多卷/换 conversation_id 映射） |
| J2 | one conversation, one episode + 提取式逐字 summary + 「全历史是另一种投影，canonical 未钉」站位 | `episode.py:23-52`（docstring 即站位记录） | A 案 = 兑现 :28-32 预留钩子「bump EPISODE_PROJECTION_VERSION」 |
| J3 | P4-G1：`elc.relationship` 禁 import `elc.runtime`（AST 钉）→ 20 双写 + 测试持等 | `tests/phase4/test_p4_3_gates.py:161-183` | A 案把 episode 窗口改全历史后，**持等钉本身要随语义重裁**（见 §5.3 随迁面） |
| J4 | prompt 字节确定性纪律（同请求同字节；时间戳/clock 不入 prompt） | `persona/commands.py:523-526`；`episode.py:50-52` | 摘要折叠必须无 clock、无随机、跨进程可重放（PYTHONHASHSEED 双跑纪律） |
| J5 | prompt 分节版式 P4-3：每节带 prompt_version 键 | `persona/types.py:253-259,288-353` | summary 语义变更须同步 bump `EPISODE_PROMPT_SECTION_VERSION`（episode-prompt-v1→v2） |
| J6 | 模型候选 = MODEL_PROPOSAL 源非权威，全拒收序 + Controller 门 | `relationship/projection.py:89-106` | 模型摘要（若做）的信任形态已有先例，但 cs-3 首刀不引入 |
| J7 | persona-visible 过滤三消费者同源（history 节 / episode rebuild / recorder 读同一过滤窗口） | `conversation/store.py:794-870`（cs-0 注释） | 全历史折叠读面必须沿用同一过滤（命令轮/教学动作轮不进摘要） |
| J8 | 确定性投影 + 内容版本摘要 + zero-write replay 幂等 | `episode.py:265-301` + `episode_store.py:87,108` | A 案机制原样复用 |

### 2.3 未裁（canonical 与仓内均无——cs-3 开工裁决要裁的题）

| # | 题目 | 现状 |
|---|---|---|
| Q1 | 摘要的分段/折叠算法 | canonical 无 segmentation algorithm（`episode.py:28-30` 明说）；20 窗口本身是 Local V1 站位数，canonical 无窗口数值 |
| Q2 | 全历史投影的形态与成本轮廓 | `episode.py:126-127`「with its own cost profile」「canonical text pins neither」 |
| Q3 | 检索索引的实现形态与 prompt 输入面 | canonical 点名 FTS/vector 为可重建投影（D2）但 RA §11 十项无检索字段——做 = canonical 语义变更 |
| Q4 | 多会话/分卷生命周期 | canonical 无开卷/合卷/归档转移（D15）；mc-0 规约一会话一角色 |
| Q5 | 「无限聊天」的上下文策略整体 | 即 cs-3 本题 |
| Q6 | OPEN_THREAD 生产者 | 类型面齐（relationship 域 + episode open_threads 列）但全仓零生产者——话头记忆缺口的另一半 |

## 3. 架构候选对比（施工级）

### 候选 A：Episode 全历史滚动摘要链（episode 投影 v2，确定性折叠）

**一句话**：兑现 `episode.py:28-32` 预留钩子——`EPISODE_PROJECTION_VERSION` bump `episode-v1→episode-v2`，rebuild 从「读 20 轮窗口」改为「读全 transcript」，`summary` 从「最近 4 句」升级为两级确定性折叠；`CONVERSATION_WINDOW_MAX_TURNS = 20` 保持不动（`[history]` 面零变化）。

**折叠形态（建议的 v2 语义，供任务书裁）**：

```text
summary(v2) := 现势层 + 封存层
  现势层 = 窗口内最近 K 句用户话逐字（现行为原样，K=EPISODE_SUMMARY_MAX_UTTERANCES）
  封存层 = 窗口外历史按固定段折叠：
    段 = 连续 EPISODE_ARCHIVE_SEGMENT_TURNS 个 slice（建议 20 = 一窗一段，对齐现有常数语义）
    每段贡献 ≤ EPISODE_ARCHIVE_LINES_PER_SEGMENT 行（建议 2）
    行选择 = 段内确定性规则（如：段首用户话 + 段内最长用户话；逐字 + 截断标记——
    与现 summary 同为「提取式逐字」信任级，非生成式）
  时间方向：旧段在前、新段在后；段边界由 turn_sequence 确定（无 clock）
```

- 两级折叠是**结构确定的纯函数** `fold(transcript)`：同 transcript 同字节（J4），重建可重放（D1/D4），`episode_version_for` 内容摘要与 zero-write replay 机制原样有效（J8）。
- prompt 有界增长：1000 轮 ≈ 50 段 × 2 行 × ≤120 字符 ≈ 12 KB——线性但有界；远期若需要「摘要的摘要」再折叠，仍是纯函数（版本 bump v3）。

**数据流**：

```text
turn N terminalize（不变）
→ CP4 enqueue EPISODE job（不变，确定性 id）
→ EpisodeProjectionExecutor：读源 slice（不变）→ scope 校验（不变）
→ 读全 transcript（改造点①：新读面 get_full_persona_visible_history 或显式 read-all 参数，
   沿用同一 persona-visible 过滤，J7）
→ rebuild_episode v2：确定性两级折叠（改造点②：episode.py 折叠体 + 版本 bump）
→ upsert（内容版本变化才写；机制不变）
→ 下一轮 PromptCompiler 的 [episode] 节即携带全历史折叠（读面零改动，D5 满足）
```

**涉及文件与函数清单**：

| 文件 | 改动 |
|---|---|
| `src/elc/relationship/episode.py` | 主刀：`EPISODE_PROJECTION_VERSION="episode-v2"`；新常量 `EPISODE_ARCHIVE_SEGMENT_TURNS`/`EPISODE_ARCHIVE_LINES_PER_SEGMENT`；`_extractive_summary` → 两级折叠；`EPISODE_WINDOW_MAX_TURNS` 语义退役或重定义（见随迁面 §5.3）；docstring 站位全面改写 |
| `src/elc/relationship/projection.py` | `EpisodeProjectionExecutor` 窗口参数改全历史读；`EpisodeConversationSource` 协议加全历史读 face |
| `src/elc/conversation/store.py`（+`queries.py` 协议） | 全历史 persona-visible 读 face（复用现有过滤 SQL 去掉 LIMIT，或 `max_turns` 上不设限的显式方法） |
| `src/elc/persona/types.py` | `EPISODE_PROMPT_SECTION_VERSION = "episode-prompt-v2"`（J5） |
| `src/elc/runtime/controller.py` | `CONVERSATION_WINDOW_MAX_TURNS` 镜像注释句更新（20 数值不动） |
| `tests/phase4/test_p4_3_gates.py` 等 | 持等钉/窗口断言随迁（§5.3） |
| `tests/host/`（新） | cs-3 验收钉（§5） |

**canonical 相容性逐条**：D1 满足（仍是 transcript 派生投影）；D2/D14 满足（纯函数可重建，删除面重建键不变）；D3 满足（version bump 即本刀）；D4 满足（源派生可重放）；D5 **零改动**（仍走 EpisodeView）；D6 满足（会话内、persona 域不跨界）；D8 满足（`[episode]` 已在 untrusted 帧）；D11 满足（成本落 CP4 异步位）；D13 满足（叙述连续性归 episode）。**零迁移**（episode 表列不变，version 字符串变化即作废旧语义行——D3 机制）；**零新信任面**；**零 provider 成本**。

**失败模式**：
1. 折叠配额漏（早期关键事实没进段配额行）→ 记忆外显对「未被选中的句子」失败——缓解：段选择规则本身是记忆政策（与 17 模式同哲学：小而诚实的记忆优于大而虚构的）；配额常量 calibratable（先例：`EPISODE_RECENT_EVENT_LIMIT` 注释「Calibratable (this is a Local V1 position, not a canonical number)」）；
2. prompt 体积长尾（千轮级 12 KB 可接受；万轮级需要 v3 再折叠）；
3. O(N) 每轮重建——SQLite 读数千行毫秒级、CP4 异步不阻塞 turn（D11）；万轮级可加段级 checkpoint 复用（重投影只重算尾段——仍是纯函数，不必第一刀做）。

**成本**：src 约 150–250 行 + 测试随迁；无迁移、无 provider、无 canonical 变更。**B 案相比：全部改动集中在 relationship + conversation 只读面 + prompt 版本号，blast radius 最小。**

**判定满足度**：直接满足——第 3 轮的叙述事实在 60 轮时位于封存层行内（`[episode]` 节）；模式可捕事实同时走 `[relationship]`。双通道与 DOMAIN_MODEL §17 记忆分离同构：**事实归 Relationship，叙述归 Episode**。

### 候选 B：会话分卷（一卷满自动开新卷 + episode 跨卷延续 + 用户透明切卷）

**一句话**：卷满（轮数阈值或自然断点）自动 CLOSED 旧卷、开新卷；旧卷的 episode 变成「卷摘要」，新卷 prompt 携带旧卷摘要；`web-<character_id>` 一对一映射改为一角色多卷。

**数据流**：

```text
turn N terminalize → 卷满判定（阈值/ConversationPriorityView.natural_break_available，D9）
→ 合卷事务：旧卷 status=CLOSED + 旧卷 episode 定格 + 新卷 open（新 conversation_id）
→ 下一 turn 的 DecisionCycle 绑新 conversation_id
→ prompt：[history] = 新卷窗口；旧卷记忆 = ？（GenerationContext 无此输入面，D5）
   ⇒ 必须新增「prior volume digests」视图或扩 EpisodeView 语义 = canonical 变更
→ web 层：/api/history、信封沓、档案统计、observations 全部跨卷统一
```

**涉及文件**：conversation 域（合卷/开卷命令 + 生命周期状态）、runtime/controller（切卷编排 + 边界时机 + lease 跨卷 handoff）、host.py（装配）、web.py（会话映射/历史/档案/统计全链）、prompt compiler（新节或 EpisodeView 扩语义）、新投影类型（卷摘要）、`migrations/`（新列或新表）、上述全部既有钉随迁。

**canonical 相容性张力**：
- D5/RA §11：GenerationContext 十项是 canonical 列举——「旧卷摘要」无合法输入位，**必须 canonical 变更**（或把 EpisodeView 扭曲成跨会话对象，违反 D1「episode 是 conversation 的投影」与 §5.3 列集）；
- D15：合卷/开卷在 STATE_MACHINES 无任何转移面——要新增 canonical 状态机；
- J1：mc-0 规约重写；
- 切卷时机只能靠 D9 的 `natural_break_available`（canonical 面存在但全仓零消费者，且其生产者今日同样无真实现）。

**失败模式**：接缝质量（卷边界切在话题中段 → 模型上下文断崖，用户可感——直接违反「对用户透明」命题）；跨卷瞬间的一致性（同 turn 内切卷的归属、lease handoff、teaching lock 跨卷）；web 显示统一（历史/沓/档案跨卷拼接的前端刀量不小）；测试矩阵暴涨（每个会话级既有测试都要考虑多卷态）。

**成本**：src 数百行 + 迁移 + web 前后端 + **canonical 六文档变更裁决** + 大面积钉随迁。三者中最高。

**判定满足度**：满足但绕远——「同一角色连续对话」由卷接续合成，体验上限受接缝质量制约；对「记忆外显」判定标准本身**没有比 A 更强的保证**（旧卷事实同样只能靠摘要携带——那是 A 的折叠问题，不是分卷问题）。分卷解决的唯一真问题是「单 transcript 行数增长」，而 SQLite 千行级毫无压力（现状 `HISTORY_TURNS=50` 的显示读与 20 轮 prompt 读都是 LIMIT 查询，与总行数无关）。

### 候选 C：组合与其它

- **A+B 组合**：B 的跨卷摘要与 A 的折叠是同一个问题（跨卷也要靠摘要携带记忆），A 落地后 B 只剩下「控制单 transcript 行数」这个不存在的收益。**否**。
- **检索增强（FTS/vector index，D2 点名的可重建投影）**：价值真实（「按需回忆」特定旧事实），但 (i) RA §11 无 prompt 检索输入面 = canonical 变更；(ii) 检索命中率不构成「早期关键事实在场」的保证（判定标准要求**始终在 prompt**，检索只在查到时在）；(iii) 新投影类型 + 查询面 + D12 事务纪律。**cs-3 不做，登记远期刀**（触发条件：dogfood 出现「记得吗」类回忆失败聚集）。
- **模型辅助滚动摘要（生成式 summary chain）**：`episode.py:33-37` 明文「a model-written summary would be a **different projection**, never this one」——须落第二投影类型 + MODEL_PROPOSAL 信任面（D7/J6 先例在）+ provider 调用进 CP4 + 非确定性对内容摘要/幂等/重建的冲击（重建 N 段 = N 次模型调用，需段级 checkpoint 才能收敛）。价值在叙述质量，成本/风险为 A 的数倍。**cs-3 首刀不做；作为 v2 折叠质量不足时的既定升级路径登记**（届时 A 的段结构直接成为 checkpoint 链骨架——A 不封闭这条路线）。
- **OPEN_THREAD 生产者（Q6）**：episode 的 `open_threads` 列与 relationship 的 `OPEN_THREAD` 类型面全齐、零生产者。「未完话头」是 D13 Episode Memory 语义（「未决上下文」）的另一半，且是 17 模式之外最自然的第二记忆通道。**建议作为 cs-3 同程序的第二刀或并入本刀候选**（裁决点：确定性话头抽取的规则形状）。

### 对比总表

| 维度 | A 折叠 v2 | B 分卷 | C 检索 / 模型摘要 |
|---|---|---|---|
| canonical 变更 | **零** | 六文档级（RA §11 / §3 / 状态机） | RA §11 加输入面 |
| 迁移 | 零 | 有 | 有（索引表） |
| 新信任面 | 零 | 零/低 | MODEL_PROPOSAL 面 |
| provider 成本 | 零 | 零 | 每轮/每段一次 |
| src 量级 | ~150–250 + 随迁 | 数百 + web 全链 + 随迁 | 中–大 |
| 判定满足度 | 直接（始终在 prompt） | 绕远（接缝风险） | 不保证始终在场 |
| 用户透明性 | 天然（无任何可见切换） | 需要精心做接缝与显示统一 | 天然 |
| 主要风险 | 折叠配额漏（可测可调） | 接缝质量 + canonical 变更连锁 | 非确定性 × 幂等体系 |

## 4. 推荐定稿

**主案 = A（Episode 全历史两级确定性折叠，`episode-v1→v2`）；B 不做；检索与模型摘要登记为远期升级路径；OPEN_THREAD 生产者列为第二刀候选。**

理由（三条）：

1. **贴 canonical 程度最高**：§5.3 列集零改动、§26 可重建直读满足、`episode.py:28-32` 自己预留的「bump EPISODE_PROJECTION_VERSION or land a second projection type」钩子按第一分支兑现、RA §11 十项输入面零改动、零迁移、零新信任面、零 provider。B 需要 canonical 六文档级变更（RA §11 输入面 + 会话状态机 + mc-0 重写），与「Clean Rewrite 以 canonical 为唯一规范权威」的纪律成本完全不匹配。
2. **判定标准直接命中**：「N≫20 轮后早期关键事实仍在 prompt 内」——A 的封存层让早期叙述事实**恒在** `[episode]` 节（非概率性检索），模式事实恒在 `[relationship]` 节；双通道分工与 DOMAIN_MODEL §17 记忆分离（事实=Relationship / 叙述=Episode，D13）同构。B 对同一判定没有更强保证。
3. **风险最低且不封闭未来**：纯确定性纯函数，失败模式只有「折叠配额漏」一类，可被验收钉直接测、被 calibratable 常量直接调；段结构天然是未来模型摘要 checkpoint 链与段级增量重建的骨架——升级路线全部开放。

**留给开工裁决（DEC）的裁点**（本简报不代裁）：① 段选择规则形状（段首+最长句 vs 其它确定性规则）；② 段/行/截断常量值（建议 20/2/120 起步，calibratable）；③ `EPISODE_WINDOW_MAX_TURNS` 常数的处置（退役 or 重定义为「现势层深度」——影响 P4-G1 持等钉的存废）；④ OPEN_THREAD 生产者是否并入 cs-3；⑤ 全历史读面形态（显式 read-all 方法 vs `max_turns` 哨兵值）。

## 5. 验收命题草案（N≫20 轮记忆外显，可执行测试形态）

**测试位置**：`tests/host/`（或 `tests/cs3/`），沿用 phase4 stress 夹具形态（`tests/phase4/test_p4_4_stress.py` 的 ROUNDS 循环 + 假 provider）与 host 既有 prompt 捕获缝（`tests/host/test_cs1_character_activation.py:131-139,360-362`：scripted provider `self.prompts` 记录 `prompt.prompt_text`）。

**场景构造**：
1. 开一个角色会话（真实 host 装配或 phase4 同构装配）；
2. 跑 **R = 60 轮**（= 3× 窗口，满足 N≫20）；
3. 第 3 轮植入**叙事事实**（刻意不匹配 17 模式：如 `"I'm adopting a puppy next month."`）；
4. 第 5 轮植入**模式事实**（如 `"my name is Mary"`）；
5. 中段轮填充中性内容（确定性脚本对话，无随机）。

**断言组（对第 60 轮捕获的 `prompt_text`）**：
- ① **记忆外显（叙事）**：第 3 轮事实句出现在 prompt 的 `[episode]` 节封存层（`episode-prompt-v2` 版本键下）；
- ② **记忆外显（事实）**：`"The user's name is Mary."` 出现在 `[relationship]` 节；
- ③ **非窗口残余**：第 3 轮原文**不在** `[history]` 节（证明 ① 走的是记忆通道而非窗口——`[history]` 只含最近 20 轮）;
- ④ **prompt 有界性**：`len(prompt_text)` 有上界断言（段配额生效；随轮数对数级/线性受控增长，而非全 transcript 逐字入 prompt）；
- ⑤ **确定性**：同一 transcript 重建 episode 两次字节同一（跨进程 `PYTHONHASHSEED` 双跑——仓内既有纪律），`episode_version_for` 幂等（zero-write replay 仍成立）;
- ⑥ **用户透明性**：`conversation` 表该角色行数恒为 1（无切卷事件；status 恒 ACTIVE）；
- ⑦ **投影不阻塞**：第 60 轮 turn 延迟与第 1 轮同量级（CP4 异步位不变，D11 回归钉）。

**变异组（RED 证明钉承重）**：折叠配额归零（封存层禁用）→ ① RED；版本不 bump（v1 语义混跑）→ 确定性/幂等钉 RED；`CONVERSATION_WINDOW_MAX_TURNS` 擅改 → 持等/窗口钉 RED。

**随迁面（本刀必然触碰的既有钉，任务书须预写）**：
- `tests/phase4/test_p4_3_gates.py:161-183` 双常数持等钉——A 落地后「episode 窗口 = prompt 窗口」语义不再成立，持等钉须按裁决 ③ 重写（建议改为「`[history]` 深度 = 20 保持；episode 封存层覆盖全历史」的新等式）;
- `tests/phase4/test_p4_4_stress.py:252-264` episode 窗口断言（`episode[3] == ROUNDS - EPISODE_WINDOW_MAX_TURNS + 1`）→ v2 下 `source_turn_sequence_start == 1`（全历史）;
- `episode.py` docstring 站位（§1.2 引文）全面改写——「A full-history episode is a different projection」句在 v2 落地后成为假句，必须同刀清扫（prep-0/c2-b 先例：src 假句当刀扫全义务）。

## 6. 遗留与登记建议

- **R-cs3-1**：判定标准只保证「在 prompt」，不保证模型**运用**——「模型是否引用早期事实」属 provider 质量，不可钉死；本刀钉的是**供给面**（事实恒在 prompt），运用面留给 dogfood 观察。
- **R-cs3-2**：折叠行选择规则 = 记忆政策，天然有漏检面（同 17 模式哲学「a small honest memory beats a large invented one」，`candidates.py:12-14`）；假阳/漏检审计与 c3 系 detector 假阳审计同构，触发条件 = dogfood 信号。
- **R-cs3-3**：远期路线登记——(a) 模型辅助叙述摘要（第二投影类型 + MODEL_PROPOSAL，触发 = v2 提取质量不足）；(b) FTS/vector 检索（触发 = 「按需回忆」失败聚集，需 RA §11 canonical 变更）；(c) OPEN_THREAD 生产者（触发 = cs-3 第二刀）。
- **R-cs3-4**：`HISTORY_TURNS = 50`（web 显示窗）与本刀无关，保持不动；`/api/history` 跨全量分页属前端面，非 cs-3。
