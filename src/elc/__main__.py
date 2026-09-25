"""``python -m elc`` — the package's process entry (prep-1).

Everything this entry does lives in :mod:`elc.cli` (the usage text, the host
assembly and the REPL); this module exists so the package can be *run*, which
is what makes "one real process" true rather than a claim about an importable
callable. It starts no server and listens on no port.
"""

from __future__ import annotations

import sys

from elc.cli import main

if __name__ == "__main__":
    sys.exit(main())
