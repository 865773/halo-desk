"""登录异常判定：区分「账号被风控/封禁」与「网络抖动」。"""
from __future__ import annotations

# 明确要求重新登录 / 账号被限制的提示；命中就退出登录
AUTH_BAD_WORDS = (
    "存在风险", "紧急封禁", "封禁", "冻结", "修改密码",
    "账号异常", "账号被", "异地登录", "禁止登录",
    "重新登录", "登录失效", "登录已过期", "登录过期",
    "未授权", "token无效", "token 无效", "invalid token",
    "请先登录", "登录状态无效", "授权失败", "401",
)

# 网络/服务端临时问题：不能据此退出登录
TRANSIENT_WORDS = (
    "超时", "timed out", "timeout", "网络", "连接失败", "连接超时",
    "502", "503", "504", "服务不可用", "系统繁忙", "请稍后",
)


def is_auth_bad(msg: str) -> bool:
    s = str(msg or "")
    return bool(s) and any(k.lower() in s.lower() for k in AUTH_BAD_WORDS)


def is_transient(msg: str) -> bool:
    s = str(msg or "")
    return any(k.lower() in s.lower() for k in TRANSIENT_WORDS)
