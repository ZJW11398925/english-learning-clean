"""Windows-compat shim injected into behavioral-baseline subprocess runs.

Context: behavioral_baselines/runtime/run_local_runtime_tests.py keeps sqlite
connections open while its file-backed checks run inside
`tempfile.TemporaryDirectory()`. On Windows, unlinking an open file fails
(PermissionError 13), so the temporary directory CLEANUP raises after a
check body has already produced its (correct) verdict — the original POSIX
run never sees this because POSIX defers the deletion to the OS. The
baseline files themselves are byte-pinned evidence and must not be edited.

This module is placed on the child interpreter's PYTHONPATH as
`sitecustomize.py`, so Python imports it automatically at startup. On
win32 it replaces tempfile.TemporaryDirectory with a best-effort-cleanup
subclass; on every other platform it is a no-op and the child runs the
pristine baseline semantics. A leftover directory in the OS temp space
mirrors what POSIX already tolerates; no baseline check asserts on
temp-directory removal.
"""

import gc
import os
import tempfile

if os.name == "nt":  # pragma: no cover - platform-dependent by definition

    class _BestEffortCleanupTempDir(tempfile.TemporaryDirectory):
        """TemporaryDirectory tolerating Windows open-file unlink failures."""

        def cleanup(self) -> None:
            try:
                super().cleanup()
            except OSError:
                gc.collect()  # release lingering sqlite connections, retry
                try:
                    super().cleanup()
                except OSError:
                    pass

    tempfile.TemporaryDirectory = _BestEffortCleanupTempDir
