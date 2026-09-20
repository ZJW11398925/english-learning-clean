# AGENTS.md — english-learning-clean（Clean Rewrite · Implementation Baseline V1）

## 项目一句话

成人英语学习应用「英语客厅」的 **Clean Rewrite**：以 Implementation Baseline V1（用户主导的更高智力讨论收敛，2026-09-20 交回）为唯一规范权威，从零实现。**规范优先级：本仓 `docs/` 六 canonical 文档 > `behavioral_baselines/` 行为基线资产 > 其他一切**（旧仓 `D:\测试1` 整体为 exploration archive，其全部设计仅作历史参考）。实现栈已裁：**Python 内核 + SQLite**（app.db 可变 / content.db 只读 / SecretStore；客户端边界已裁 `DEC-…d7937fd7.12`：进程内 Python API，交互面推迟 Phase 8 末后）。

## 🔴 dmcp 段（新会话续接第一入口）

- **workspace_id**：`ws-7585bd9c-f6ec-4c73-be14-d2e635a37033`（**schema 5**；旧工作区 `ws-db58afd2-…` 已随旧仓归档，别用）
- **续接顺序**：①读本文件 → ②`design_status` 刷基 → ③`design_get` `DEC-OPI-d7937fd7-2f4e-4e4b-940e-25a8b32143f4.12`（**PHASE 1 COMPLETE** + 客户端边界裁定 + P1B 六项偏差处置）→ ④`git log --oneline` → ⑤开工前读 `docs/IMPLEMENTATION_PLAN.md` §5（Phase 2 Detail Block）与 §1.5（normative 顺序），再按派单协议铸 Phase 2 任务书（四查+VAL+TASK 同铸）
- **当前状态**（2026-09-20 第三会话末）：**PHASE 1 COMPLETE**（rev 17）——P1A 对话持久核心（commit `fe7317f`，`VR-…d7937fd7.5` PASS）+ P1B persona 生成管线（commit `9c73854`，`VR-…d7937fd7.11` PASS），总控双独立复核（109→128 passed 0 skipped、ruff/mypy、CI 四门绿×2）；§3 六场景全过、「不需要 retry whole turn」成立；GenerationActionStatus 已纠正为 STATE_MACHINES §14 七值。**下一步 = Phase 2 开工**（Learning Evidence Kernel + Estimator Behavioral Baseline V1，基线 §5/§1.5；第一条 vertical slice 见 §1.5：Basic Persona Conversation → canonical Evidence → Estimator LearnerState → explicit TeachingMoment → user attempt → new Evidence → updated LearnerState）
- **对象索引**（全 id 可直接 design_get；OPI 前缀 `d7937fd7-2f4e-4e4b-940e-25a8b32143f4`）：
  - `DEC-…d7937fd7.12` **PHASE 1 COMPLETE** + 客户端边界（进程内 API，交互面推迟）+ P1B 六项偏差处置（含一次 executor Bash 直写 .py 违规训诫留痕）
  - `VR-…d7937fd7.5` / `VR-…d7937fd7.11` P1A / P1B 验收 PASS
  - `VAL-…d7937fd7.6` / `TASK-…d7937fd7.9` P1B 验收定义与任务书（四查在 TASK.9 的 why）
  - `DEC-…091f35c3.7` Phase 1 开工（切分 P1A/P1B + flash/pro 选型 + 四查留痕 + 两处悬题裁定：delivery_state 词汇 SM §13 派生 / decision_cycle_id 过渡 nullable Phase 2 收紧）
  - `VAL-…091f35c3.9` / `TASK-…091f35c3.11` P1A 验收定义与任务书；`DEC-…091f35c3.13` 派单阻塞处置（thoughtLevel: max 修复，已生效）
  - `DEC-…9dc4e77f.4` 基线归位+技术栈（Python+SQLite）+四查留痕（其「客户端边界 Phase 1 末再裁」revisit 已由 `DEC-…d7937fd7.12` 兑现）
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
- **测试**：`python -m pytest`（当前 128/0/0）；静态：ruff + mypy（77 文件）；migrations 到 0003（schema_version 3）
- **Mimosa 安全钩子**：Bash 直写源码/配置被拦——**.py/.sql/.yml/.toml 一律 Write/Edit 工具落盘**（P1B 执行者曾一次 Bash 直写 .py 未被钩子拦但违反明令，已在 `DEC-…d7937fd7.12` 训诫留痕——总控与执行者均不得再犯）；SQL 一律参数绑定或全字面量（标识符用白名单全字面量），禁任何拼接
- **基线冻结**：`behavioral_baselines/` 的 .py 一字节不改（例外须按 `DEC-…d5b616bf.3` 范式：显式决策+最小改动+manifest 重钉）；六 canonical 文档只许 `DECISION_REGISTER.md` 的版本条目
- **不做**（纪律）：未到位次的域逻辑/域表提前实现（位次见基线 §1.5：Phase 2=Learning Evidence Kernel 已解锁，其余域仍禁）；Redis/Kafka/分布式锁/TTL/heartbeat（Local V1 §24.1 永禁）；自动教学（Phase 8 才开）；`decision_cycle_id` 等 Phase 2 收紧钩子见 `DEC-…091f35c3.7` 裁定 b
- docs/run_post_bf_regression.py 的 ROOT 自相矛盾是原件冻结缺陷，永久不可修——repo-native 七套件是长期替代；勿再尝试修它
- Windows：core.autocrlf 与 blob 有字节差，哈希校验须 CRLF 归一；建议后续加 .gitattributes（勿扰动冻结文件行尾）

## 常用命令

```bash
python -m pytest          # 全量（含架构门与七套件行为基线）
ruff check . && mypy src  # 静态门
git push                  # CI 自动跑四门
```
