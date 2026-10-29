"""签到日期状态：保证「每天只自动签一次」，避免重复请求。"""
from __future__ import annotations

from datetime import date

from .config import CFG

PLATFORMS = ("hlx", "lingjie")


def today() -> str:
    return date.today().strftime("%Y-%m-%d")


def signed_today(platform: str) -> bool:
    return (CFG.get(f"{platform}.signin_day", "") or "") == today()


def mark_signed(platform: str) -> None:
    CFG.set(f"{platform}.signin_day", today())
    CFG.save()


def reset(platform: str) -> None:
    CFG.set(f"{platform}.signin_day", "")
    CFG.save()
