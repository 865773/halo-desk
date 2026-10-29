"""自动任务页：双平台巡检 + 大肥鱼自动回复 + 每日签到。"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QTime, QTimer, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel,
                               QSpinBox, QTextBrowser, QTimeEdit, QVBoxLayout)

from .. import memory
from ..config import CFG
from . import common, theme
from .base import Page


class AutoPage(Page):
    key = "auto"

    def __init__(self, app):
        super().__init__(app, "自动任务",
                         "让大肥鱼自己看着两个平台：有人评论就回一句，到点自动签到。")
        ap = app.autopilot

        run = common.Card(padding=20, spacing=12)
        top = QHBoxLayout()
        top.addWidget(common.card_title("运行状态"))
        top.addStretch(1)
        run.box.addLayout(top)
        run.box.addWidget(common.line())

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel("监听间隔"))
        self.interval = QSpinBox()
        self.interval.setRange(5, 300)
        self.interval.setSuffix(" 秒")
        self.interval.setValue(int(CFG.get("auto.poll_sec", 10) or 10))
        self.interval.valueChanged.connect(self._save_interval)
        row.addWidget(self.interval)
        row.addSpacing(12)
        self.run_btn = common.button("立即巡检一次", primary=True)
        self.run_btn.clicked.connect(self.run_now)
        row.addWidget(self.run_btn)
        row.addStretch(1)
        self.state_lb = common.muted("")
        row.addWidget(self.state_lb)
        run.box.addLayout(row)
        row2 = QHBoxLayout()
        row2.setSpacing(10)
        row2.addWidget(QLabel("每次最多回"))
        self.maxn = QSpinBox()
        self.maxn.setRange(1, 10)
        self.maxn.setSuffix(" 条")
        self.maxn.setValue(int(CFG.get("auto.max_per_pass", 3) or 3))
        self.maxn.valueChanged.connect(self._save_max)
        row2.addWidget(self.maxn)
        row2.addStretch(1)
        run.box.addLayout(row2)
        run.box.addWidget(common.hint(
            "这里只管消息：每 10 秒循环拉一次两个平台的通知，有新的就回；"
            "只处理「接入时间点」之后的消息，回复前随机等 0–15 秒。"
            "逛社区多久一次在下面的「逛社区间隔」里设。"))
        self.body.addWidget(run)

        roam = common.Card(padding=20, spacing=12)
        rhead = QHBoxLayout()
        rhead.addWidget(common.card_title("自动逛社区"))
        rhead.addStretch(1)
        roam.box.addLayout(rhead)
        roam.box.addWidget(common.line())
        roam.box.addWidget(common.hint(
            "逛不逛、去哪个社区、哪个板块、看几条、做什么，全部由大肥鱼自己决定；"
            "「逛社区间隔」控制隔多久才能再出来逛一次（关掉程序也会记住上次时间）。"))

        rowr = QHBoxLayout()
        rowr.setSpacing(8)
        rowr.addWidget(QLabel("逛社区间隔"))
        self.wake = QSpinBox()
        self.wake.setRange(5, 360)
        self.wake.setSuffix(" 分钟")
        self.wake.setValue(int(CFG.get("fish.interval_min", 20) or 20))
        self.wake.valueChanged.connect(self._save_wake)
        rowr.addWidget(self.wake)
        rowr.addSpacing(6)
        rowr.addWidget(QLabel("葫芦侠每天"))
        self.daily_hlx = QSpinBox()
        self.daily_hlx.setRange(1, 10)
        self.daily_hlx.setSuffix(" 条")
        self.daily_hlx.setValue(int(CFG.get("autopost.daily_limit_hlx", 2) or 2))
        self.daily_hlx.valueChanged.connect(
            lambda v: self._save_daily("hlx", int(v)))
        rowr.addWidget(self.daily_hlx)
        rowr.addWidget(QLabel("灵芥每天"))
        self.daily_lj = QSpinBox()
        self.daily_lj.setRange(1, 10)
        self.daily_lj.setSuffix(" 条")
        self.daily_lj.setValue(int(CFG.get("autopost.daily_limit_lingjie", 2) or 2))
        self.daily_lj.valueChanged.connect(
            lambda v: self._save_daily("lingjie", int(v)))
        rowr.addWidget(self.daily_lj)
        rowr.addStretch(1)
        rowr.addWidget(common.button("立即逛一次", primary=True,
                                     on_click=lambda: self._roam(False)))
        rowr.addWidget(common.button("试运行（不执行动作）", ghost=True,
                                     on_click=lambda: self._roam(True)))
        roam.box.addLayout(rowr)

        rowt = QHBoxLayout()
        rowt.setSpacing(10)
        rowt.addWidget(QLabel("测试发帖"))
        rowt.addWidget(common.button("测试发帖·葫芦侠", ghost=True,
                                     on_click=lambda: self._test_post("hlx")))
        rowt.addWidget(common.button("测试发帖·灵芥", ghost=True,
                                     on_click=lambda: self._test_post("lingjie")))
        rowt.addSpacing(12)
        rowt.addWidget(common.button("测试日记", ghost=True,
                                     on_click=self._test_diary))
        rowt.addStretch(1)
        roam.box.addLayout(rowt)

        perms = QHBoxLayout()
        perms.setSpacing(14)
        perms.addWidget(QLabel("允许的动作"))
        self.perm_boxes = {}
        for key, label in (("like", "点赞"), ("favorite", "收藏"),
                           ("comment", "评论"), ("follow", "关注"),
                           ("tip", "送葫芦/芥子"), ("post", "发帖"),
                           ("signin", "签到"), ("roam", "逛社区"),
                           ("reply", "回复")):
            cb = QCheckBox(label)
            cb.setChecked(bool(CFG.get(f"perm.{key}", key != "tip")))
            cb.stateChanged.connect(
                lambda s, k=key: (CFG.set(f"perm.{k}", bool(s)), CFG.save()))
            perms.addWidget(cb)
            self.perm_boxes[key] = cb
        self.auto_follow = QCheckBox("亲密度 ≥70 自动关注")
        self.auto_follow.setChecked(bool(CFG.get("fish.auto_follow", True)))
        self.auto_follow.stateChanged.connect(
            lambda s: (CFG.set("fish.auto_follow", bool(s)), CFG.save()))
        perms.addWidget(self.auto_follow)
        perms.addStretch(1)
        roam.box.addLayout(perms)
        self.body.addWidget(roam)

        log_card = common.Card(padding=20, spacing=10)
        ltop = QHBoxLayout()
        ltop.addWidget(common.card_title("运行日志"))
        ltop.addStretch(1)
        clear = common.button("清空", ghost=True)
        clear.clicked.connect(lambda: self.log_view.clear())
        ltop.addWidget(clear)
        log_card.box.addLayout(ltop)
        self.log_view = QTextBrowser()
        self.log_view.setMinimumHeight(200)
        self.log_view.setStyleSheet("font-size:12px;")
        log_card.box.addWidget(self.log_view)
        self.body.addWidget(log_card)
        self.body.addStretch(1)

        ap.log.connect(self.append_log)
        ap.state_changed.connect(self.refresh)
        self.refresh()

    # ---------- 设置 ----------
    def toggle(self, state) -> None:
        on = bool(state)
        CFG.set("auto.enabled", on)
        CFG.save()
        if on:
            self.app.autopilot.start()
            common.toast(self.app, "自动任务已开启", "ok")
        else:
            self.app.autopilot.stop()
            common.toast(self.app, "自动任务已暂停", "info")
        self.refresh()

    def _save_interval(self, v) -> None:
        CFG.set("auto.poll_sec", int(v))
        CFG.save()
        if CFG.get("auto.enabled", False):
            self.app.autopilot.start()

    def _save_wake(self, v) -> None:
        CFG.set("fish.interval_min", int(v))
        CFG.save()

    def _save_daily(self, platform: str, v: int) -> None:
        CFG.set(f"autopost.daily_limit_{platform}", int(v))
        CFG.save()

    def _test_post(self, platform: str = "hlx") -> None:
        self.app.autopilot.run_test_post(platform)

    def _test_diary(self) -> None:
        self.app.autopilot.run_test_diary()

    def _toggle_roam(self, state) -> None:
        on = bool(state)
        CFG.set("roam.enabled", on)
        CFG.save()
        self.app.autopilot.start()      # 重新按配置启停各定时器
        if on and not CFG.get("hlx.key", ""):
            common.toast(self.app, "逛社区需要先登录葫芦侠", "warn")
        elif on:
            common.toast(self.app, "已开启自动逛社区", "ok")

    def _roam(self, dry: bool) -> None:
        if not CFG.get("hlx.key", ""):
            common.toast(self.app, "请先登录葫芦侠", "warn")
            return
        if not CFG.get("ai.key", ""):
            common.toast(self.app, "请先在「大肥鱼」页配置 DeepSeek Key", "warn")
            return
        self.app.autopilot.run_roam_now(dry_run=dry)

    def _save_max(self, v) -> None:
        CFG.set("auto.max_per_pass", int(v))
        CFG.save()

    def _save_reply(self, s) -> None:
        CFG.set("auto.reply_enabled", bool(s))
        CFG.save()

    def _save_sign(self, s) -> None:
        CFG.set("auto.daily_signin", bool(s))
        CFG.save()

    def _save_time(self, t) -> None:
        CFG.set("auto.signin_time", t.toString("HH:mm"))
        CFG.save()

    def run_now(self) -> None:
        if not CFG.get("fish.enabled", False):
            common.toast(self.app, "先在总览打开「大肥鱼」总开关", "warn")
            return
        if not self.app.cfg.get("hlx.key", "") and not self.app.cfg.get("lingjie.token", ""):
            common.toast(self.app, "两个平台都还没登录", "warn")
            return
        if not CFG.get("ai.key", ""):
            common.toast(self.app, "还没配置 DeepSeek Key，只能签到不能回复", "warn")
        self.append_log("— 手动触发一次巡检 —")
        self.app.autopilot.run_now()

    # ---------- 展示 ----------
    def append_log(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"<span style='color:{theme.MUTED}'>[{ts}]</span> {text}")

    def refresh(self) -> None:
        ap = self.app.autopilot
        sent = int(ap.state.get("sent", 0))
        last = ap.state.get("last_signin", "") or "—"
        self.state_lb.setText(
            f"已回 {sent} 条 · 总开关{'开' if CFG.get('fish.enabled', False) else '关'}")
