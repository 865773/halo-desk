"""版本号集中管理。"""
from __future__ import annotations

import re

VERSION = "10.16"


def as_tuple(text: str) -> tuple:
    nums = re.findall(r"\d+", str(text or ""))
    return tuple(int(n) for n in nums[:3]) or (0,)


def is_newer(remote: str) -> bool:
    return as_tuple(remote) > as_tuple(VERSION)
