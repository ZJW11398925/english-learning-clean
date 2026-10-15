# 一级新仓随迁冻结面（DEC `OPI-f45d1976-…11`，2026-10-15）

源仓：`english-learning-clean`（冻结于 tip，终末交接块见 AGENTS.md）。「引擎随迁不重写」的具体清单。文件级边界在迁移刀开刀时按此清单裁取。

## 随迁（引擎中层，原样）

| 模块 | 内容 |
|---|---|
| `src/elc/world/turns.py` | 回合脊柱：三拍型、DS-3 四律、节奏律（护栏 3 拍/20 调）、恢复语义 |
| `src/elc/world/harness.py` | 权限表（Principal/Tool/authorize） |
| `src/elc/world/action.py` | 裁定链门禁＋ResolverContext＋canon_delta 三验 |
| `src/elc/world/store.py` / `narrative/store.py` | 世界事件/正史与段落存储 |
| `src/elc/world/memory.py` / `cast.py` / `bible.py` | 角色记忆／演员卡／世界圣经 |
| `src/elc/world/llm_providers.py`（DS 臂族） | 情境计划臂/调度臂/角色臂/裁定臂/叙述臂＋主权句/保真句/停点标记 |
| `src/elc/persona/openai_provider.py` | 传输层（SSE 流式、值非异常边界） |
| `src/elc/ds_web.py` 的 `RetryingTextCompletion` | transport 单次自动重试 |
| `src/elc/world/ds_situation.py` | 情境计划机（四问合同、幂等、残章复用） |
| `src/elc/world/ds_opening.py` | 开局种子「灰隼要塞·龙焰夜」（草稿待定调） |
| `src/elc/platform/db/`（按需裁取） | SQLite/迁移/epoch/SecretStore |
| `src/elc/ds_web.py` 的状态/控制位推导 | 据浅场状态回收逻辑（HTTP 路由层不迁） |

## 不迁（本仓历史）

- V3 阅读面全族：`narrative_web.py`、`web.py`、`webui/reader.*`
- `/ds` POC 调试台：`webui/dualseat.*`（被新呈现层取代）
- 门机件、gold 剧本、blueprint 机（测试面）
- V3 专属臂（旧 planner/resolver/writer/director 形态）
- 旧产品面（chat/信件/teaching/phase 机制）

## 新仓新建

1. **呈现层全族**（设计轮先行——判词 DEC `OPI-f45d1976-…2` 为设计输入与验收基准）
2. **per-role 模型配置**：服务商列表（设置中增删改）＋各角色模型列表选择（DEC `…9` 终形）
3. **交互边界**：引擎进程内直连 UI vs 引擎服务化（新仓第一呈裁件）
