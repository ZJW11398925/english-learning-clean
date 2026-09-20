# AGENTS.md — english-learning-clean（Clean Rewrite · Implementation Baseline V1）

## 项目一句话

成人英语学习应用「英语客厅」的 **Clean Rewrite**：以 Implementation Baseline V1（用户主导的更高智力讨论收敛，2026-09-20 交回）为唯一规范权威，从零实现。**规范优先级：本仓 `docs/` 六 canonical 文档 > `behavioral_baselines/` 行为基线资产 > 其他一切**（旧仓 `D:\测试1` 整体为 exploration archive，其全部设计仅作历史参考）。实现栈已裁：**Python 内核 + SQLite**（app.db 可变 / content.db 只读 / SecretStore；客户端边界 Phase 1 末再裁）。

## 🔴 dmcp 段（新会话续接第一入口）

- **workspace_id**：`ws-7585bd9c-f6ec-4c73-be14-d2e635a37033`（**schema 5**；旧工作区 `ws-db58afd2-…` 已随旧仓归档，别用）
- **续接顺序**：①读本文件 → ②`design_status` 刷基 → ③`design_get` `DEC-OPI-9dc4e77f-337d-4ad1-829e-be180ab0474e.4`（基线+技术栈裁决，四查留痕）与 `DEC-OPI-7bf80972-819d-4367-bc87-20f1cf1ae46f.2`（PHASE 0 COMPLETE）→ ④`git log --oneline` → ⑤开工前读 `docs/IMPLEMENTATION_PLAN.md` 对应 Phase 章
- **当前状态**（2026-09-20 会话末）：**PHASE 0 COMPLETE**（骨架+外部评审八项修复全过；`b4c68bf`，Actions run 35487833782 success；pytest **85 passed / 0 skipped / 0 failed**；本地与 CI 双绿）。**下一步 = Phase 1**（基线 §3：Conversation + Persona buffered 最小运行时，明确不做自动教学）
- **对象索引**（全 id 可直接 design_get）：
  - `DEC-…9dc4e77f.4` 基线归位+技术栈（Python+SQLite）+四查留痕
  - `TASK-…9dc4e77f.6` / `VAL-…9dc4e77f.8` Phase 0 骨架（VR PASS）
  - `DEC-…d5b616bf.3` 基线 v1.0.1 例外修订（两行 SQL 白名单化+manifest 重钉）——**例外修订范式**：显式决策+最小改动+重钉+验证，不许静默扩大
  - `DEC-…d5b616bf.7` 外部评审采纳（五 blocker：XOR 语义/枚举缩水/回归未闭环/双重事实/world_lore 断层）
  - `TASK-…d5b616bf.9` / `VAL-…d5b616bf.11` Phase 0 Repair（R1–R8）
  - `DEC-…7bf80972.2` + `VR-…7bf80972.4` **PHASE 0 COMPLETE**（含总控两错认领：9/10 态转写错、v1.0.1 错钉两哈希）

## 派单协议（用户明令，2026-09-20）

- **执行者 = `executor-flash`（一般任务）/ `executor-pro`（难题）**——用户安装在 `~/.zcode/agents/`（model 字段分别钉 GLM-5.3-Flash / GLM-5.3）。**禁止用内置 `general-purpose` 做执行任务**。
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
