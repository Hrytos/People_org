"""
Pytest configuration and shared fixtures.

Adds project root to path so tests use src.* imports (same as running from project root).
This allows src.fullenrich.client to use relative imports (..core) correctly.
"""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
