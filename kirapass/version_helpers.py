"""Small helpers that keep the package importable from any location."""

from __future__ import annotations

import os


def package_dir(*parts: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts)
