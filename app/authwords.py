"""登录/发言状态判定：区分「登录失效」「账号受限」「网络抖动」。"""
from __future__ import annotations

# 明确要求重新登录 / 令牌失效；命中就退出登录
LOGIN_BAD_WORDS = (
    "存在风险", "修改密码", "重新登录", "登录失效", "登录已过期",
    "登录过期", "未授权", "token无效", "token 无效", "invalid token",
    "请先登录", "登录状态无效", "授权失败", "401",
)

# 账号被锁定/禁言/禁止发言：仍算登录，但不能回复，要显示原因并停手
RESTRICT_WORDS = (
    "锁定", "封禁", "禁言", "无法回复", "无法评论", "无法发帖",
    "禁止回复", "禁止发言", "禁止评论", "限制发言", "已被限制",
    "账号已被", "权限不足",
)

# 网络/服务端临时问题：不能据此退出登录
TRANSIENT_WORDS = (
    "超时", "timed out", "timeout", "网络", "连接失败", "连接超时",
    "502", "503", "504", "服务不可用", "系统繁忙", "请稍后",
)


def is_login_bad(msg: str) -> bool:
    s = str(msg or "")
    return bool(s) and any(k.lower() in s.lower() for k in LOGIN_BAD_WORDS)


def is_restricted(msg: str) -> bool:
    s = str(msg or "")
    return bool(s) and any(k in s for k in RESTRICT_WORDS)


def is_transient(msg: str) -> bool:
    s = str(msg or "")
    return any(k.lower() in s.lower() for k in TRANSIENT_WORDS)


# 兼容旧调用
def is_auth_bad(msg: str) -> bool:
    return is_login_bad(msg)
