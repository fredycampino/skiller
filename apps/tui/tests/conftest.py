from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TUI_SRC = REPO_ROOT / "apps" / "tui" / "src"

for path in (REPO_ROOT, TUI_SRC):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
