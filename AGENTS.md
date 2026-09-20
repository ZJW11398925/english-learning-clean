# AGENTS.md — english-learning-clean（Clean Rewrite · Implementation Baseline V1）

## 项目一句话

成人英语学习应用「英语客厅」的 **Clean Rewrite**：以 Implementation Baseline V1（用户主导的更高智力讨论收敛，2026-09-20 交回）为唯一规范权威，从零实现。**规范优先级：本仓 `docs/` 六 canonical 文档 > `behavioral_baselines/` 行为基线资产 > 其他一切**（旧仓 `D:\测试1` 整体为 exploration archive，其全部设计仅作历史参考）。实现栈已裁：**Python 内核 + SQLite**（app.db 可变 / content.db 只读 / SecretStore；客户端边界 Phase 1 末再裁）。

## 🔴 dmcp 段（新会话续接第一入口）

- **workspace_id**：`ws-7585bd9c-f6ec-4c73-be14-d2e635a37033`（**schema 5**；旧工作区 `ws-db58afd2-…` 已随旧仓归档，别用）
- **续接顺序**：①读本文件 → ②`design_status` 刷基 → ③`design_get` `DEC-OPI-091f35c3-937c-4116-be83-918527451d8c.7`（Phase 1 开工：切分+选型+四查）与 `DEC-OPI-091f35c3-937c-4116-be83-918527451d8c.13`（派单阻塞与处置）→ ④`git log --oneline` → ⑤开工前读 `docs/IMPLEMENTATION_PLAN.md` §3 与 `TASK-OPI-091f35c3-937c-4116-be83-918527451d8c.11`（P1A 任务书全文即简报蓝本）
- **当前状态**（2026-09-20 第二会话末）：**PHASE 0 COMPLETE 不变；Phase 1 已开工未执行**——P1A 任务书三件已铸（开工决策 `DEC-…091f35c3.7` / 验收 `VAL-…091f35c3.9` / 任务书 `TASK-…091f35c3.11`，rev 14），**派单被环境阻塞**：新 harness 要求子代理模型带思考档位，executor-flash/pro 定义缺 `thoughtLevel` 拒启（`DEC-…091f35c3.13` 留痕）；两 agent 文件已补 `thoughtLevel: max`（正确键，查实宿主 bundle），**须宿主重启生效**。**下一步 = 重启后新会话立即派 executor-flash 执行 P1A**（简报全文在 `TASK-…091f35c3.11` 的 expected_output；P1A 验收后铸 P1B 任务书派 executor-pro——persona 生成管线 + §3 六场景）
- **对象索引**（全 id 可直接 design_get）：
  - `DEC-…091f35c3.7` Phase 1 开工（切分 P1A/P1B + flash/pro 选型 + 四查留痕 + Phase 0 遗留偏差：GenerationActionStatus 六值非 STATE_MACHINES §14 原文七值，P1B 纠正）
  - `VAL-…091f35c3.9` / `TASK-…091f35c3.11` P1A 验收定义与任务书（**已铸未派**）
  - `DEC-…091f35c3.13` 派单阻塞处置（thoughtLevel 修复+重启后续派；禁 general-purpose 兜底）
  - `DEC-…9dc4e77f.4` 基线归位+技术栈（Python+SQLite）+四查留痕
  - `TASK-…9dc4e77f.6` / `VAL-…9dc4e77f.8` Phase 0 骨架（VR PASS）
  - `DEC-…d5b616bf.3` 基线 v1.0.1 例外修订（两行 SQL 白名单化+manifest 重钉）——**例外修订范式**：显式决策+最小改动+重钉+验证，不许静默扩大
  - `DEC-…d5b616bf.7` 外部评审采纳（五 blocker：XOR 语义/枚举缩水/回归未闭环/双重事实/world_lore 断层）
  - `TASK-…d5b616bf.9` / `VAL-…d5b616bf.11` Phase 0 Repair（R1–R8）
  - `DEC-…7bf80972.2` + `VR-…7bf80972.4` **PHASE 0 COMPLETE**（含总控两错认领：9/10 态转写错、v1.0.1 错钉两哈希）

## 派单协议（用户明令，2026-09-20）

- **执行者 = `executor-flash`（一般任务）/ `executor-pro`（难题）**——用户安装在 `~/.zcode/agents/`（model 钉 GLM-5.3-Flash / GLM-5.3，**须带 `thoughtLevel: max` 键**——2026-09-20 补，缺则新 harness 拒启，见 `DEC-…091f35c3.13`）。**禁止用内置 `general-purpose` 做执行任务**。
- 总控不亲自执行（写代码/测试/探针/部署一律派执行者，先 `task_build` 铸任务书）；设计类任务书先过 grilling 前沿；**任务书四查 + VAL 与任务书同铸**（前沿/实现设计条目/计划时效/预算算术；交付后补盖 VAL 视同无效验收）。红线全文 0–31 见旧仓 `D:\测试1\AGENTS.md`（红线 28/29/30/31 尤其要读）。

## 工程事实与红线（本仓特有）

- **远程**：github.com/ZJW11398925/english-learning-clean（public）；**CI 四门**：ruff → mypy → compileall → pytest（push+PR，Ubuntu，0 skipped 为准）
- **测试**：`python -m pytest`（当前 85/0/0）；静态：ruff + mypy（70 文件）
- **Mimosa 安全钩子**：Bash 直写源码/配置被拦——**.py/.yml/.toml 一律 Write/Edit 工具落盘**；SQL 一律参数绑定或全字面量（标识符用白名单全字面量），禁任何拼接
- **基线冻结**：`behavioral_baselines/` 的 .py 一字节不改（例外须按 `DEC-…d5b616bf.3` 范式：显式决策+最小改动+manifest 重钉）；六 canonical 文档只许 `DECISION_REGISTER.md` 的版本条目
- **不做**（Phase 0–1 纪律）：业务逻辑提前实现、域表提前建、Redis/Kafka/分布式锁、自动教学（Phase 8 才开）
- docs/run_post_bf_regression.py 的 ROOT 自相矛盾是原件冻结缺陷，永久不可修——repo-native 七套件是长期替代；勿再尝试修它
- Windows：core.autocrlf 与 blob 有字节差，哈希校验须 CRLF 归一；建议后续加 .gitattributes（勿扰动冻结文件行尾）

## 常用命令

```bash
python -m pytest          # 全量（含架构门与七套件行为基线）
ruff check . && mypy src  # 静态门
git push                  # CI 自动跑四门
```
