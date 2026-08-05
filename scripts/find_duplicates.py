#!/usr/bin/env python3
"""Compatibility entry point for the installed PIHTI duplicate scanner."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(REPO_SRC) not in sys.path:
    sys.path.insert(0, str(REPO_SRC))

from pihti_dedup.legacy import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
