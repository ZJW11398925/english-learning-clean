# AOCI-CODE 调研评估（2026-10-03，用户指令驱动）

> 对象：`aoci-spec/aoci-code`（GitHub）——「A persistent, Git-versioned codebase map for AI coding agents」
> 配套论文：AOCI: Symbolic-Semantic Indexing for Practical Repository-Scale Code Understanding with LLMs（arXiv, J. Liu 2026）
> 许可证 FSL-1.1-MIT（Fair Source，等待期后转 MIT）；版本 v0.1.0-rc17（756★/126 fork/193 commits，中英双 README，活跃）

## 1. 它是什么

AI 编程代理的**代码库认知基础设施**：为整个代码库（+ 数据库 schema）维护一份**持久化、Git 版本化的纯文本索引**，agent 读一遍即掌握全系统，不必每任务重搜重读。口号原文："Agents read it once and know the system, instead of re-reading the repo on every task."

- 形态：单 Go CLI（`aoci`）+ stdio MCP server（九工具：读四/维护二/辅助三）；本地优先、无守护进程、无 CGO。
- 索引 = Cognition Volumes v1：`aoci.txt`（Root 入口）/`aoci.meta.txt`（标签字典与预算）/`aoci.code.txt`（代码条目）/`aoci.database.txt`（可选表级条目）——纯文本进仓随 Git 版本化。
- 条目 = FRAS 四字段一行一对象：**F** 职责 / **R** 必须一起看的强关联 / **A** 对外契约 / **S** 非显性约束（代码推不出来的必须知识）+ 紧凑标签 `[CG9L]`（架构层/模块/重要性/规模）。
- 分工哲学："The model owns meaning, AOCI-CODE owns governance"——模型撰写语义，工具管治理（SHA-256 绑定、CAS 原子写、verify/check、账本恢复）。
- 规模：1–3 万行起有收益，上限约 50 万行（70 万行商业系统实测，索引约 300K tokens）；首次建索引约 1 小时/20 万行，分批可续跑；MCP 维护增量（任务后顺带更新对应条目）。
- 数据库面：PG/MySQL/openGauss 只读 schema 元数据（不读业务数据零 DDL/DML）。

## 2. 对本仓的适配评估

### 痛点直击（价值面）

| 我们的痛点 | AOCI 的对应 |
|---|---|
| 每个新上下文执行者四查成本高（读 AGENTS 巨块 + spec + 源码定位） | `aoci_overview`/`aoci_search` 一次定位相关文件 + S 字段承载非显性约束 |
| 铁律⑱研读先行的执行成本 | 索引 = 地图加速研读（先索引后原文） |
| AGENTS 交接块持续膨胀（本会话又 +3 大段） | 机制事实/先例/随迁点知识落到 S 字段（跟着代码单元走），交接块可瘦身 |
| 「钉随迁点」「此文件动了必须迁 XXX」知识散落 | S 字段天然承载（一行一对象的强制关联 R + 约束 S） |
| content.db 25 表 + app.db 的 schema 认知 | Database 卷表级条目 |
| 仓规模（elc 源 + tests 数万行级） | 正处建议区间（1–3 万行起） |

### 风险与纪律面（必须铸裁决）

1. **仓内洁净**：`dependencies = []` 是 runtime 约束——AOCI 是**开发时工具**，不进 runtime 零冲突；但索引文件（根目录 4 个 txt）进仓 = 新增顶层文件——`tests/architecture` 的 census/根文件钉需四查（预期不冲突，census 管 webui 包面）。
2. **索引是地图不是证据**：铁律⑱的「原文引文」义务**不因索引减免**——索引条目指向原文，裁决引文仍须读原文（防索引语义漂移 = 防「读索引代替读 canonical」的新形态违反⑱）。此条写进采用裁决。
3. **执行者集成形态**：执行者（子代理）无自己的 MCP 配置——但**索引是纯文本**，任务书写「先读 aoci.code.txt 相关条目再四查原文」即可零 MCP 使用；MCP server 只挂总控宿主做增量维护。
4. **许可证**：FSL-1.1-MIT 对内部开发工具使用通常无碍（非竞争性再分发）；登记不动 runtime。
5. **RC 版本**：v0.1.0-rc17——开发辅助不进产品 runtime，风险可控；升级轴有版本检查（48 项/版本）。
6. **治理对齐**：SHA-256 绑定 + CAS + verify 的治理面与本仓钉链纪律同构——索引条目可被钉（test 断言关键文件的 F/R/S 条目在场）。

## 3. 采用方案（建议两步）

**第一步试点（四候选期间并行，不占写刀串行位）**：
1. 仓外装 CLI（Releases 签名包，稳定绝对路径）；
2. `aoci init` + `scan` → 派执行者建 **src/elc 核心包**的 Code 卷（tests 后续）+ app/content schema 的 Database 卷；
3. `aoci verify/check` 过 → 索引文件入仓（首个含索引的提交）+ census 四查 + 采用 DEC 铸件（纪律三条：索引是地图不是证据 / 索引文件属冻结面新成员由 aoci_maintain 维护 / 任务书模板加「读索引」义务位）；
4. **试刀对照**：A 前端升级刀的任务书加「先读 aoci.code.txt 相关条目」，收刀后对比（执行者 token 消耗 / 四查耗时 / 遗漏率）。

**第二步（试点达标后）**：
- MCP server 挂总控宿主（增量维护）；
- AGENTS 交接块瘦身计划（机制事实/随迁点迁 S 字段，交接块回归「程序状态 + 链件索引」）；
- 关键文件 FRAS 条目入钉面。

**不采用的情形**：试点对照无显著收益（token/遗漏未改善）→ 登记 Revisit 关闭。
