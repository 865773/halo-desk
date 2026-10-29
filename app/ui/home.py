"""总览页。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QVBoxLayout,
                               QWidget)

from .. import memory
from . import common, theme
from .base import Page


def _stats_text() -> str:
    try:
        from ..stats import summary
        return summary()
    except Exception:
        return "—"


def _avatar(text: str, color: str) -> QLabel:
    lb = QLabel(text)
    lb.setFixedSize(46, 46)
    lb.setAlignment(Qt.AlignCenter)
    lb.setStyleSheet(
        f"background:{color};color:#06121F;border-radius:23px;"
        f"font-size:18px;font-weight:800;")
    return lb


class AccountCard(common.Card):
    def __init__(self, page: Page, platform: str):
        super().__init__(padding=20, spacing=12)
        self.page = page
        self.platform = platform
        head = QHBoxLayout()
        head.setSpacing(12)
        self.avatar = _avatar("葫", theme.ACCENT if platform == "hlx" else "#A78BFA")
        head.addWidget(self.avatar)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.name = QLabel("未登录")
        self.name.setStyleSheet("font-size:15px;font-weight:700;")
        self.sub = QLabel("—")
        self.sub.setObjectName("muted")
        col.addWidget(self.name)
        col.addWidget(self.sub)
        head.addLayout(col, 1)
        self.badge = common.Badge("未登录", "muted")
        head.addWidget(self.badge, 0, Qt.AlignTop)
        self.box.addLayout(head)

        self.box.addWidget(common.line())
        row = QHBoxLayout()
        self.btn = common.button("去登录", primary=True)
        self.btn.clicked.connect(self.on_btn)
        row.addWidget(self.btn)
        row.addStretch(1)
        self.box.addLayout(row)

    def on_btn(self) -> None:
        app = self.page.app
        app.show_page(self.platform)
        target = app.page(self.platform)
        logged = bool(app.cfg.get("hlx.key", "")) if self.platform == "hlx" \
            else bool(app.cfg.get("lingjie.token", ""))
        if logged and target and hasattr(target, "start_signin"):
            target.start_signin()

    def refresh(self) -> None:
        app = self.page.app
        if self.platform == "hlx":
            cfg = app.cfg
            key = cfg.get("hlx.key", "")
            if key:
                self.name.setText(cfg.get("hlx.nick", "") or "葫芦侠用户")
                self.sub.setText(f"UID {cfg.get('hlx.uid', 0)} · Lv.{cfg.get('hlx.level', 0)}")
                self.badge.setText("已登录")
                self.badge.set_kind("ok")
                self.btn.setText("一键签到")
            else:
                self.name.setText("未登录")
                self.sub.setText("手机号 + 密码登录")
                self.badge.setText("未登录")
                self.badge.set_kind("muted")
                self.btn.setText("去登录")
        else:
            cfg = app.cfg
            if cfg.get("lingjie.token", ""):
                self.name.setText(cfg.get("lingjie.nickname", "") or "灵芥用户")
                self.sub.setText(f"UID {cfg.get('lingjie.uid', 0)}")
                self.badge.setText("已登录")
                self.badge.set_kind("ok")
                self.btn.setText("一键签到")
            else:
                self.name.setText("未登录")
                self.sub.setText("灵芥空间账号")
                self.badge.setText("未登录")
                self.badge.set_kind("muted")
                self.btn.setText("去登录")


class HomePage(Page):
    key = "home"

    def __init__(self, app):
        super().__init__(app, "总览", "两个平台，一只大肥鱼 —— 葫芦侠三楼 + 灵芥空间，合在一个窗口里。")
        grid = QGridLayout()
        grid.setSpacing(16)
        self.hlx_card = AccountCard(self, "hlx")
        self.lj_card = AccountCard(self, "lingjie")
        grid.addWidget(self.hlx_card, 0, 0)
        grid.addWidget(self.lj_card, 0, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        holder = QWidget()
        holder.setLayout(grid)
        self.body.addWidget(holder)

        status = common.Card(padding=20, spacing=14)
        top = QHBoxLayout()
        top.addWidget(common.card_title("今日状态"))
        top.addStretch(1)
        self.mood = QLabel()
        self.mood.setObjectName("muted")
        top.addWidget(self.mood)
        status.box.addLayout(top)
        status.box.addWidget(common.line())
        self.stats = QLabel("—")
        self.stats.setWordWrap(True)
        self.stats.setStyleSheet("font-size:13px;line-height:170%;")
        status.box.addWidget(self.stats)
        self.body.addWidget(status)

        quick = common.Card(padding=20, spacing=14)
        quick.box.addWidget(common.card_title("快捷操作"))
        quick.box.addWidget(common.line())
        row = QHBoxLayout()
        row.setSpacing(10)
        b1 = common.button("两个平台都签到", primary=True)
        b1.clicked.connect(self.signin_both)
        b2 = common.button("打开大肥鱼挂件")
        b2.clicked.connect(lambda: self.app.open_pet())
        b3 = common.button("和大肥鱼聊天", ghost=True)
        b3.clicked.connect(lambda: self.app.show_page("fish"))
        row.addWidget(b1)
        row.addWidget(b2)
        row.addWidget(b3)
        row.addStretch(1)
        quick.box.addLayout(row)
        self.body.addWidget(quick)
        self.body.addStretch(1)

    def signin_both(self) -> None:
        app = self.app
        if app.cfg.get("hlx.key", ""):
            app.show_page("hlx")
            app.page("hlx").start_signin()
        if app.cfg.get("lingjie.token", ""):
            app.show_page("lingjie")
            app.page("lingjie").start_signin()
        if not app.cfg.get("hlx.key", "") and not app.cfg.get("lingjie.token", ""):
            common.toast(app, "两个平台都还没登录", "warn")

    def refresh(self) -> None:
        self.hlx_card.refresh()
        self.lj_card.refresh()
        hlx = "已登录" if self.app.cfg.get("hlx.key", "") else "未登录"
        lj = "已登录" if self.app.cfg.get("lingjie.token", "") else "未登录"
        ai = "已配置" if self.app.cfg.get("ai.key", "") else "未配置"
        self.stats.setText(
            f"葫芦侠：{hlx}　·　灵芥空间：{lj}　·　DeepSeek：{ai}<br>"
            f"今日签到：葫芦侠 {self.app.cfg.get('stats.hlx_signin', 0)} 个板块，"
            f"灵芥 {self.app.cfg.get('stats.lj_signin', 0)} 个板块<br>"
            f"今日互动：{_stats_text()}<br>"
            f"对话次数：{self.app.cfg.get('stats.chat', 0)}")
        self.mood.setText(f"心情：{memory.mood_label()}（{memory.get_mood()}）")
