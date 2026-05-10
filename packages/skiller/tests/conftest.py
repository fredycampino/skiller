"""Shared pytest config for all tests.

Keep this file minimal. Place test-type-specific fixtures in:
- packages/skiller/tests/unit/conftest.py
- packages/skiller/tests/integration/conftest.py
- packages/skiller/tests/e2e/conftest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))
