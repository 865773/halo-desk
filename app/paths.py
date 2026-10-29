"""资源路径。"""
from __future__ import annotations

import os
import sys


def resource(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, rel)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, rel)


def icon_path() -> str:
    for name in ("assets/icon.ico", "assets/fish.png"):
        p = resource(name)
        if os.path.exists(p):
            return p
    return ""
