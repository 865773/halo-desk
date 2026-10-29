"""动态页：大肥鱼做过的事，按「帖子」合并成一条时间线。"""
from __future__ import annotations

import re

from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QTextBrowser)

from ..activity import ACT, KIND_LABEL, PLATFORM_LABEL
from . import common, theme
from .base import Page

KIND_COLOR = {
    "decision": "#F59E0B",
    "signin": "#38BDF8",
    "reply": "#34D399",
    "post": "#A78BFA",
    "genimg": "#F472B6",
    "chat": "#FBBF24",
    "error": "#F87171",
    "system": "#94A3B8",
}
ACTION_KINDS = ("like", "favorite", "comment", "follow", "tip", "post", "signin")
ACTION_LABEL = {"like": "点赞", "favorite": "收藏", "comment": "评论",
                "follow": "关注", "tip": "送葫芦", "post": "发帖", "signin": "签到"}

KIND_COLOR_LIGHT = {
    "decision": "#B45309",
    "signin": "#0369A1",
    "reply": "#047857",
    "post": "#6D28D9",
    "genimg": "#BE185D",
    "chat": "#92400E",
    "error": "#B91C1C",
    "system": "#475569",
}


def _title_of(text: str) -> str:
    m = re.search(r"《(.+?)》", text or "")
    return m.group(1) if m else ""


def _comment_of(text: str) -> str:
    m = re.search(r"》：(.+)$", text or "")
    return m.group(1).strip() if m else ""


def _groups(items: list[dict]) -> list[list[dict]]:
    """同一个帖子的多条动作合并成一组。"""
    buckets: dict[str, list[dict]] = {}
    order: list[str] = []
    for i, it in enumerate(items):
        meta = it.get("meta") or {}
        pid = meta.get("pid") or meta.get("post")
        key = f"{it.get('platform')}:{pid}" if pid else f"_solo_{i}"
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(it)
    return [buckets[k] for k in order]


class ActivityPage(Page):
    key = "activity"

    def __init__(self, app):
        super().__init__(app, "动态", "大肥鱼的行动记录：决策、签到、回复、发帖、生图、聊天。")
        bar = common.Card(padding=14, spacing=10)
        row = QHBoxLayout()
        row.setSpacing(10)
        from PySide6.QtWidgets import QLabel
        row.addWidget(QLabel("筛选"))
        self.filter = QComboBox()
        self.filter.addItems(["全部", "葫芦侠", "灵芥"])
        self.filter.currentIndexChanged.connect(self.render)
        row.addWidget(self.filter)
        row.addStretch(1)
        row.addWidget(common.button("刷新", ghost=True, on_click=self.render))
        row.addWidget(common.button("清空", ghost=True, on_click=self.clear))
        bar.box.addLayout(row)
        self.body.addWidget(bar)

        card = common.Card(padding=8, spacing=0)
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        self.view.setStyleSheet("font-size:13px;")
        card.box.addWidget(self.view)
        self.body.addWidget(card)
        ACT.added.connect(lambda _item: self.render())

    def clear(self) -> None:
        ACT.clear()
        self.render()
        common.toast(self.app, "动态已清空", "ok")

    def render(self) -> None:
        idx = self.filter.currentIndex()
        platform = {1: "hlx", 2: "lingjie"}.get(idx, "")
        items = ACT.recent(300, platform)
        if not items:
            self.view.setHtml(
                f"<div style='color:{theme.MUTED};padding:20px'>还没有动态。"
                f"去签到、发帖或让大肥鱼回一条消息，这里就会热闹起来。</div>")
            return
        rows = []
        for group in _groups(items):
            head = group[0]
            title = ""
            reason = ""
            actions: list[str] = []
            comment = ""
            extra_text = ""
            for it in group:
                text = it.get("text", "")
                title = title or _title_of(text)
                meta = it.get("meta") or {}
                reason = reason or meta.get("reason", "")
                kind = it.get("kind", "")
                if kind in ACTION_KINDS:
                    label = ACTION_LABEL.get(kind, KIND_LABEL.get(kind, kind))
                    if label not in actions:
                        actions.append(label)
                    if kind == "comment":
                        comment = comment or _comment_of(text)
                elif kind == "decision":
                    if not actions and not extra_text:
                        extra_text = text
            plat = PLATFORM_LABEL.get(head.get("platform", ""), "")
            dark = theme.is_dark()
            if dark:
                color = KIND_COLOR.get(head.get("kind", ""), theme.ACCENT)
                chip_bg = "#1B2942"
            else:
                color = KIND_COLOR_LIGHT.get(head.get("kind", ""), theme.ACCENT)
                chip_bg = theme.SEL
            if title:
                head_line = (f"<span style='color:{theme.TEXT};font-weight:700'>《{title}》</span>")
            else:
                base = extra_text or head.get("text", "")
                base = re.sub(r"（理由：.*?）$", "", base)
                head_line = f"<span style='color:{theme.TEXT}'>{base}</span>"
            chips = ""
            if actions:
                chips = " ".join(
                    f"<span style='background:{chip_bg};color:{color};border-radius:8px;"
                    f"padding:1px 8px;font-size:11px'>{a}</span>" for a in actions)
            comment_html = (f"<div style='color:{theme.TEXT};margin-top:3px'>评论：{comment}</div>"
                            if comment else "")
            reason_html = (f"<div style='color:{theme.MUTED};font-size:11px;margin-top:2px'>"
                           f"理由：{reason}</div>" if reason else "")
            tag = (f"<span style='background:{chip_bg};color:{color};"
                   f"border-radius:6px;padding:1px 6px;font-size:10px'>"
                   f"{plat or '大肥鱼'}</span> ")
            rows.append(
                f"<div style='margin:6px 0;padding:8px 10px;background:{theme.CARD2};"
                f"border-radius:8px'>"
                f"<span style='color:{theme.MUTED};font-size:11px'>{head.get('ts','')}</span> "
                f"{tag}{head_line} {chips}{comment_html}{reason_html}</div>")
        self.view.setHtml("".join(rows))

    def refresh(self) -> None:
        self.render()
