"""社区页里的「用户记忆」卡片：列表显示名字/uid，点进去看内容。"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QTextBrowser)

from ..config import FILES_DIR
from ..debuglog import DBG
from ..memory import mem_limit
from ..relations import REL
from . import common, theme


class UserMemoryCard(common.Card):
    def __init__(self, app, platform: str, title: str):
        super().__init__(padding=18, spacing=10)
        self.app = app
        self.platform = platform
        self.paths: dict[str, str] = {}
        self._backfilled = False

        head = QHBoxLayout()
        head.addWidget(common.card_title(title))
        head.addStretch(1)
        head.addWidget(common.button("刷新", ghost=True, on_click=self.reload))
        head.addWidget(common.button("去他主页看看", ghost=True, on_click=self._visit))
        head.addWidget(common.button("打开目录", ghost=True, on_click=self.open_dir))
        self.box.addLayout(head)
        self.box.addWidget(common.hint(
            "大肥鱼对每个人的记忆：点名单看内容；超过 "
            f"{mem_limit('user')} 字会自动总结压缩。"))

        row = QHBoxLayout()
        row.setSpacing(10)
        self.lst = QListWidget()
        self.lst.setFixedWidth(260)
        self.lst.setStyleSheet(
            f"QListWidget{{font-size:12px;background:{theme.FIELD};"
            f"color:{theme.TEXT};border:1px solid {theme.LINE};"
            f"border-radius:10px;padding:4px;outline:none;}}"
            f"QListWidget::item{{padding:6px 8px;border-radius:6px;color:{theme.TEXT};}}"
            f"QListWidget::item:selected{{background:{theme.SEL};color:{theme.TEXT};}}")
        self.lst.currentItemChanged.connect(lambda *_: self._show())
        row.addWidget(self.lst)

        self.view = QTextBrowser()
        self.view.setStyleSheet(
            f"font-size:12px;background:{theme.FIELD};color:{theme.TEXT};"
            f"border:1px solid {theme.LINE};border-radius:10px;padding:10px;")
        self.view.setPlaceholderText("左边点一个名字")
        row.addWidget(self.view, 1)
        self.box.addLayout(row)
        self.reload()

    # ---------- 数据 ----------
    def reload(self) -> None:
        cur = self.lst.currentItem().data(Qt.UserRole) if self.lst.currentItem() else None
        self.lst.clear()
        self.paths = {}
        logged = bool(self.app.cfg.get("hlx.key", "")) if self.platform == "hlx" \
            else bool(self.app.cfg.get("lingjie.token", ""))
        if not logged:
            self.view.setPlainText(
                "还没登录这个平台。\n登录对应账号后，会显示该账号自己的用户记忆。")
            return
        try:
            from .. import names
            names.ensure(self.platform)
            if not self._backfilled:
                missing = False
                try:
                    from ..memory import list_user_files
                    for p in list_user_files(self.platform):
                        uid = int(p.stem.rsplit("_u", 1)[1])
                        if uid and not names.get(self.platform, uid):
                            missing = True
                            break
                except Exception:
                    missing = False
                if missing:
                    self._backfilled = True
                    client = self.app.hlx if self.platform == "hlx" else self.app.lj

                    def work(_e):
                        return names.backfill(self.platform, client)

                    from .common import run_bg
                    run_bg(work, lambda _n: self.reload(), lambda _e: None)
        except Exception:
            pass
        from ..memory import list_user_files
        files = sorted(list_user_files(self.platform),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        for p in files:
            uid = self._uid_of(p.name)
            nick = ""
            try:
                from .. import names
                nick = names.get(self.platform, uid)
                if not nick:
                    nick = REL.nick(self.platform, uid)
            except Exception:
                nick = ""
            lines = 0
            try:
                lines = sum(1 for ln in p.read_text("utf-8").splitlines() if ln.strip())
            except Exception:
                pass
            label = f"{nick or 'uid=' + str(uid)}  ·  {uid}"
            item = QListWidgetItem(label)
            item.setToolTip(f"{lines} 条 · {p.stat().st_size} 字节")
            item.setData(Qt.UserRole, str(p))
            item.setData(Qt.UserRole + 1, uid)
            self.lst.addItem(item)
            self.paths[str(p)] = label
            if cur and str(p) == str(cur):
                self.lst.setCurrentItem(item)
        if self.lst.count() and not self.lst.currentItem():
            self.lst.setCurrentRow(0)
        elif not self.lst.count():
            self.view.setPlainText("这一边还没有用户记忆。等大肥鱼在这里和人聊过，就会出现。")

    @staticmethod
    def _uid_of(name: str) -> int:
        try:
            tail = name.rsplit("_u", 1)[1]
            return int(tail.split(".")[0])
        except Exception:
            return 0

    def _show(self) -> None:
        item = self.lst.currentItem()
        if not item:
            return
        path = item.data(Qt.UserRole)
        uid = item.data(Qt.UserRole + 1) or 0
        nick = self.paths.get(path, "").split("  ·  ")[0]
        try:
            text = open(path, encoding="utf-8").read()
        except Exception as e:
            text = f"读取失败：{e}"
        favor = 0
        try:
            favor = REL.get(self.platform, uid)
        except Exception:
            pass
        header = (f"<div style='color:{theme.MUTED};font-size:12px'>"
                  f"{nick}（uid={uid}） · 好感度 {favor}/100 · "
                  f"{len(text)}/{mem_limit('user')} 字</div>")
        self.view.setHtml(header + "<pre style='white-space:pre-wrap'>"
                          + (text or "（空）").replace("<", "&lt;") + "</pre>")

    def _visit(self) -> None:
        item = self.lst.currentItem()
        if not item:
            return
        uid = int(item.data(Qt.UserRole + 1) or 0)
        if not uid:
            return
        from .common import run_bg
        from .. import roam
        self.app.autopilot.log.emit(f"— 去看看 uid={uid} 的主页 —")
        run_bg(
            lambda _e: roam.visit_user(self.platform, uid, log=lambda s: None),
            lambda s: common.toast(
                self.app,
                f"看了 {s.get('seen', 0)} 条，动作 {len(s.get('actions') or [])} 个",
                "ok"),
            lambda e: common.toast(self.app, f"拜访失败：{e}", "error"))

    def open_dir(self) -> None:
        from .settings_page import open_local
        if not open_local(str(FILES_DIR)):
            common.toast(self.app, f"打不开，路径：{FILES_DIR}", "error")
