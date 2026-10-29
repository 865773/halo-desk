"""总览页。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox, QGridLayout, QHBoxLayout, QLabel,
                               QMessageBox, QVBoxLayout, QWidget)

from .. import memory
from ..config import data_dir
from . import common, theme
from .base import Page


def _stats_text() -> str:
    try:
        from ..stats import summary
        return summary()
    except Exception:
        return "—"


def _avatar_file(platform: str):
    d = data_dir() / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"avatar_{platform}.png"


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
        self.avatar = _avatar("葫" if platform == "hlx" else "灵",
                              theme.ACCENT if platform == "hlx" else "#A78BFA")
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
        self.sign = QLabel("")
        self.sign.setObjectName("muted")
        row.addWidget(self.btn)
        row.addWidget(self.sign)
        row.addStretch(1)
        self.box.addLayout(row)

    def on_btn(self) -> None:
        self.page.app.show_page(self.platform)

    def _apply_avatar(self) -> None:
        p = _avatar_file(self.platform)
        if p.exists():
            pix = QPixmap(str(p))
            if not pix.isNull():
                self.avatar.setPixmap(pix.scaled(
                    46, 46, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
                self.avatar.setText("")
                self.avatar.setStyleSheet("border-radius:23px;")
                return
        self.avatar.setText("葫" if self.platform == "hlx" else "灵")
        self.avatar.setStyleSheet(
            f"background:{theme.ACCENT if self.platform == 'hlx' else '#A78BFA'};"
            "color:#06121F;border-radius:23px;font-size:18px;font-weight:800;")

    def refresh(self) -> None:
        app = self.page.app
        cfg = app.cfg
        self._apply_avatar()
        if self.platform == "hlx":
            logged = bool(cfg.get("hlx.key", ""))
            name = cfg.get("hlx.nick", "") or "葫芦侠用户"
            level = int(cfg.get("hlx.level", 0) or 0)
            sub = f"UID {cfg.get('hlx.uid', 0)}" + (f" · Lv.{level}" if level else "")
            signed = bool(cfg.get("stats.hlx_signin", 0))
        else:
            logged = bool(cfg.get("lingjie.token", ""))
            name = cfg.get("lingjie.nickname", "") or "灵芥用户"
            lv = int(cfg.get("lingjie.level", 0) or 0)
            exp = int(cfg.get("lingjie.exp", 0) or 0)
            nxt = int(cfg.get("lingjie.next_exp", 0) or 0)
            lv_txt = f"Lv.{lv}" + (f"（{exp}/{nxt}）" if nxt else "")
            sub = f"UID {cfg.get('lingjie.uid', 0)}" + (f" · {lv_txt}" if lv else "")
            signed = bool(cfg.get("stats.lj_signin", 0))
        self.name.setText(name if logged else "未登录")
        self.sub.setText(sub if logged else
                         ("手机号 + 密码登录" if self.platform == "hlx" else "账号密码 / 短信登录"))
        self.badge.setText("已登录" if logged else "未登录")
        self.badge.set_kind("ok" if logged else "muted")
        self.btn.setText("进主页" if logged else "去登录")
        self.sign.setText("今日已签到" if signed else ("今日未签到" if logged else ""))


class HomePage(Page):
    key = "home"

    def __init__(self, app):
        super().__init__(app, "总览", "两个平台，一只大肥鱼 —— 葫芦侠三楼 + 灵芥空间，合在一个窗口里。")

        # 总开关
        master = common.Card(padding=20, spacing=10)
        top = QHBoxLayout()
        top.addWidget(common.card_title("启用大肥鱼"))
        top.addStretch(1)
        self.master = QCheckBox("启用")
        self.master.stateChanged.connect(self._toggle_master)
        top.addWidget(self.master)
        master.box.addLayout(top)
        master.box.addWidget(common.line())
        self.ready = QLabel("—")
        self.ready.setWordWrap(True)
        self.ready.setTextFormat(Qt.RichText)
        master.box.addWidget(self.ready)
        master.box.addWidget(common.hint(
            "开启后才会执行消息监听、自动回复、逛社区、发帖、签到等所有功能；"
            "关掉就是纯手动。"))
        self.body.addWidget(master)

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
        top2 = QHBoxLayout()
        top2.addWidget(common.card_title("今日状态"))
        top2.addStretch(1)
        self.mood = QLabel()
        self.mood.setObjectName("muted")
        top2.addWidget(self.mood)
        status.box.addLayout(top2)
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
        b2 = common.button("打开大肥鱼挂件")
        b2.clicked.connect(lambda: self.app.open_pet())
        b3 = common.button("和大肥鱼聊天", ghost=True)
        b3.clicked.connect(lambda: self.app.show_page("fish"))
        b4 = common.button("首次配置向导", ghost=True)
        b4.clicked.connect(lambda: self.app.show_wizard())
        row.addWidget(b2)
        row.addWidget(b3)
        row.addWidget(b4)
        row.addStretch(1)
        quick.box.addLayout(row)
        self.body.addWidget(quick)
        self.body.addStretch(1)

    # ---------- 总开关 ----------
    def missing_items(self) -> list[str]:
        cfg = self.app.cfg
        miss = []
        if not cfg.get("hlx.key", ""):
            miss.append("葫芦侠未登录")
        if not cfg.get("lingjie.token", ""):
            miss.append("灵芥未登录")
        if not cfg.get("ai.key", ""):
            miss.append("DeepSeek Key 未配置")
        return miss

    def _toggle_master(self, state) -> None:
        cfg = self.app.cfg
        if not state:
            cfg.set("fish.enabled", False)
            cfg.save()
            self.app.autopilot.stop()
            self.app.close_pet()
            self.refresh()
            return
        miss = self.missing_items()
        if miss:
            self.master.blockSignals(True)
            self.master.setChecked(False)
            self.master.blockSignals(False)
            QMessageBox.warning(
                self, "还不能启动",
                "先把这些配置好再启用：\n\n· " + "\n· ".join(miss) +
                "\n\n可以点「首次配置向导」按步骤来。")
            return
        cfg.set("fish.enabled", True)
        cfg.save()
        self.app.autopilot.start()
        common.toast(self.app, "大肥鱼已启动", "ok")
        self.refresh()

    def refresh(self) -> None:
        cfg = self.app.cfg
        for c in (self.hlx_card, self.lj_card):
            c.refresh()
        miss = self.missing_items()
        enabled = bool(cfg.get("fish.enabled", False))
        self.master.blockSignals(True)
        self.master.setChecked(enabled)
        self.master.blockSignals(False)
        if miss:
            self.ready.setText("<span style='color:#FBBF24'>还差：</span>" +
                               "、".join(miss))
        else:
            self.ready.setText("<span style='color:#34D399'>配置齐全，可以启用</span>"
                               + ("（当前已启用）" if enabled else ""))
        hlx = "已登录" if cfg.get("hlx.key", "") else "未登录"
        lj = "已登录" if cfg.get("lingjie.token", "") else "未登录"
        ai = "已配置" if cfg.get("ai.key", "") else "未配置"
        self.stats.setText(
            f"葫芦侠：{hlx}　·　灵芥空间：{lj}　·　DeepSeek：{ai}　·　"
            f"大肥鱼：{'运行中' if enabled else '未启用'}<br>"
            f"今日互动：{_stats_text()}<br>"
            f"对话次数：{cfg.get('stats.chat', 0)}")
        self.mood.setText(f"心情：{memory.mood_label()}（{memory.get_mood()}）")
