"""总览页。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox, QGridLayout, QHBoxLayout, QLabel,
                               QMessageBox, QProgressBar, QVBoxLayout, QWidget)

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

        # 总开关（顶部主卡）
        master = common.Card(padding=22, spacing=12)
        top = QHBoxLayout()
        top.setSpacing(16)
        big = _avatar("鱼", theme.ACCENT2)
        big.setFixedSize(64, 64)
        big.setStyleSheet(
            f"background:{theme.ACCENT2};color:#06121F;border-radius:32px;"
            "font-size:24px;font-weight:800;")
        top.addWidget(big)
        col = QVBoxLayout()
        col.setSpacing(2)
        name = QLabel("大肥鱼")
        name.setStyleSheet("font-size:20px;font-weight:800;")
        sub = QLabel("葫芦侠三楼 + 灵芥空间")
        sub.setObjectName("muted")
        col.addWidget(name)
        col.addWidget(sub)
        top.addLayout(col, 1)
        self.master = QCheckBox()
        self.master.setObjectName("switch")
        self.master.setToolTip("总开关：开启后所有自动功能才生效")
        self.master.stateChanged.connect(self._toggle_master)
        lb = QLabel("总开关")
        lb.setObjectName("muted")
        top.addWidget(lb, 0, Qt.AlignVCenter)
        top.addWidget(self.master, 0, Qt.AlignVCenter)
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
        top2.addWidget(common.card_title("心情"))
        top2.addStretch(1)
        self.mood = QLabel()
        self.mood.setObjectName("muted")
        top2.addWidget(self.mood)
        status.box.addLayout(top2)
        status.box.addWidget(common.line())
        self.mood_bar = QProgressBar()
        self.mood_bar.setRange(0, 100)
        self.mood_bar.setTextVisible(False)
        status.box.addWidget(self.mood_bar)
        self.mood_log = QLabel("—")
        self.mood_log.setWordWrap(True)
        self.mood_log.setObjectName("hint")
        status.box.addWidget(self.mood_log)
        status.box.addWidget(common.hint("被夸、被哄会涨；被凶、被冷落会掉；"
                                         "大约 3 小时慢慢回到平常 60。"))
        self.body.addWidget(status)

        # 今日各平台小卡片
        cards = QHBoxLayout()
        cards.setSpacing(16)
        self.pcards = {}
        for p, title in (("hlx", "葫芦侠"), ("lingjie", "灵芥")):
            c = common.Card(padding=18, spacing=8)
            c.box.addWidget(common.card_title(f"今天在{title}"))
            c.box.addWidget(common.line())
            grid = QGridLayout()
            grid.setHorizontalSpacing(18)
            grid.setVerticalSpacing(4)
            labels = {}
            for i, key in enumerate(("post", "comment", "reply", "follow", "favorite")):
                name = {"post": "发帖", "comment": "评论", "reply": "回复",
                        "follow": "关注", "favorite": "收藏"}[key]
                lb = QLabel("0")
                lb.setStyleSheet("font-size:19px;font-weight:800;")
                nm = QLabel(name)
                nm.setObjectName("muted")
                grid.addWidget(lb, 0, i)
                grid.addWidget(nm, 1, i)
                labels[key] = lb
            c.box.addLayout(grid)
            self.pcards[p] = labels
            cards.addWidget(c, 1)
        holder2 = QWidget()
        holder2.setLayout(cards)
        self.body.addWidget(holder2)

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
            cfg.set("auto.enabled", False)
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
        cfg.set("auto.enabled", True)
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
        # 心情 + 今日各平台
        try:
            mood = memory.get_mood("hlx")
            self.mood_bar.setValue(mood)
            self.mood.setText(f"{memory.mood_label(mood, 'hlx')}（{mood}/100）")
            logs = memory.mood_log("hlx", 3) + memory.mood_log("lingjie", 3)
            self.mood_log.setText("　".join(x.strip() for x in logs[-4:]) or
                                  "今天心情还挺平稳")
        except Exception:
            pass
        from ..activity import ACT
        from ..stats import today_platform
        for p, labels in self.pcards.items():
            counts = dict(today_platform(p))
            try:
                acts = ACT.today_counts(p)
            except Exception:
                acts = {}
            for key, lb in labels.items():
                n = counts.get(key, 0) or acts.get(key, 0)
                if key == "reply":
                    n = counts.get("reply", 0)
                lb.setText(str(int(n or 0)))
