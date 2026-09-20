# Repo Run Notes — Local Runtime suite (BF-07)

本目录随基线包附带的 `test_summary.json` / `local_runtime_test_results_v1.json`
记录的是**打包作者 Windows 环境**的一次运行读数（36/43）：L24–L30 等
recovery/cleanup 检查在 Windows 上因 sqlite 连接未关闭导致 TemporaryDirectory
清理抛 `PermissionError(13)`，检查判定本身已算出、随后清理失败——这是平台
工件，不是套件语义。

仓库真相以 CI 重放读数为准：

- repo-native 接线：`tests/behavioral/test_local_runtime_reference.py`
  原样重放 `run_local_runtime_tests.py`，以子进程退出码与打印计数为判据；
  Windows 下经 `tests/_compat/sitecustomize.py` 容错驱动，POSIX 保持原语义。
- 预期读数：43/43（CI Ubuntu 与本地 Windows 均为此值）。
- 本文件是仓库侧说明（git 治理），不属于基线包哈希清单。
