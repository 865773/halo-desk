"""记忆页：通用 / 生活 / 用户记忆的可视化、字数统计与手动压缩。"""
from __future__ import annotations

import os

from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QMessageBox,
                               QTextBrowser)

from .. import memory
from ..config import FILES_DIR
from ..debuglog import DBG
from . import common, theme
from .base import Page


class MemoryPage(Page):
    key = "memory"

    def __init__(self, app):
        super().__init__(app, "记忆", "大肥鱼记住的东西：通用记忆、生活记忆、对每个人的用户记忆。")
        self.paths: dict[str, str] = {}

        bar = common.Card(padding=14, spacing=10)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel("账号"))
        self.plat = QComboBox()
        self.plat.addItem("葫芦侠", "hlx")
        self.plat.addItem("灵芥", "lingjie")
        if not self.app.cfg.get("hlx.key", ""):
            self.plat.setCurrentIndex(1)
        self.plat.currentIndexChanged.connect(lambda _i: self.reload())
        row.addWidget(self.plat)
        row.addWidget(QLabel("查看"))
        self.which = QComboBox()
        self.which.setMinimumWidth(260)
        self.which.currentIndexChanged.connect(self._load)
        row.addWidget(self.which, 1)
        row.addWidget(common.button("刷新", ghost=True, on_click=self.reload))
        row.addWidget(common.button("立即压缩", ghost=True, on_click=self.compress))
        row.addWidget(common.button("清空这份", ghost=True, on_click=self.clear))
        row.addWidget(common.button("打开目录", ghost=True, on_click=self.open_dir))
        bar.box.addLayout(row)

        self.stat = QLabel("")
        self.stat.setStyleSheet(f"color:{theme.MUTED};font-size:12px;")
        bar.box.addWidget(self.stat)
        self.body.addWidget(bar)

        card = common.Card(padding=10, spacing=0)
        self.view = QTextBrowser()
        self.view.setStyleSheet("font-size:13px;")
        card.box.addWidget(self.view)
        self.body.addWidget(card)
        self.reload()

    # ---------- 数据 ----------
    def reload(self) -> None:
        cur = self.which.currentText()
        self.which.blockSignals(True)
        self.which.clear()
        self.paths = {}
        cfg = self.app.cfg
        platform = self.plat.currentData() or "hlx"
        logged = (cfg.get("hlx.key", "") if platform == "hlx"
                  else cfg.get("lingjie.token", ""))
        if not logged:
            self.which.blockSignals(False)
            self.view.setPlainText(
                "还没登录。\n登录账号后，这里显示该账号的通用记忆和生活记忆；"
                "切换账号会换成对应账号的内容。")
            self.stat.setText("")
            return

        def add(label: str, path, allow_missing: bool = False):
            if path is None:
                return
            if not os.path.exists(path) and not allow_missing:
                return
            name = f"{label}（{os.path.basename(str(path))}）"
            self.paths[name] = str(path)
            self.which.addItem(name)

        add("通用记忆", memory.general_file(platform), allow_missing=True)
        add("生活记忆（共享）", memory.LIFE_FILE, allow_missing=True)
        # 用户记忆放到各自社区页里，这里只留通用/生活

        if cur in self.paths:
            self.which.setCurrentIndex(list(self.paths).index(cur))
        self.which.blockSignals(False)
        self._load()

    def _current(self) -> tuple[str, str, str]:
        name = self.which.currentText()
        path = self.paths.get(name, "")
        kind = "general"
        if name.startswith("生活"):
            kind = "life"
        elif name.startswith("用户"):
            kind = "user"
        return name, path, kind

    def _load(self) -> None:
        name, path, kind = self._current()
        if not path:
            self.view.setPlainText("还没有记忆文件。多用用大肥鱼，它会慢慢记住事情。")
            self.stat.setText("")
            return
        try:
            text = open(path, encoding="utf-8").read()
        except Exception:
            text = ""
        if not text:
            text = ("还没有生活记录。大肥鱼每 6 小时会写一次，"
                    "也可以去「自动任务」里手动触发。" if kind == "life"
                    else "还没有记忆。多用用大肥鱼，它会慢慢记住事情。")
        self.view.setPlainText(text or "（空）")
        limit = memory.mem_limit(kind)
        n = len(text)
        pct = min(100, int(n * 100 / max(1, limit)))
        color = theme.WARN if pct >= 100 else theme.MUTED
        self.stat.setText(
            f"<span style='color:{color}'>{n} / {limit} 字（{pct}%）</span>"
            f"<span style='color:{theme.MUTED}'>　超过上限会自动让大肥鱼总结压缩；"
            f"也可以点「立即压缩」</span>")

    # ---------- 操作 ----------
    def compress(self) -> None:
        name, path, kind = self._current()
        if not path:
            return
        self.stat.setText("正在让大肥鱼总结…（可能要十几秒）")
        common.run_bg(
            lambda _e: memory.compress(path, kind, force=True),
            lambda ok: (self._load(),
                        common.toast(self.app, "已压缩" if ok else "还没到上限，不用压缩",
                                     "ok" if ok else "")),
            lambda e: common.toast(self.app, f"压缩失败：{e}", "error"))

    def clear(self) -> None:
        name, path, _kind = self._current()
        if not path:
            return
        if QMessageBox.question(self, "清空记忆", f"确定清空「{name}」？") != QMessageBox.Yes:
            return
        try:
            open(path, "w", encoding="utf-8").write("")
            DBG.log("MEM", f"清空记忆：{name}")
        except Exception as e:
            common.toast(self.app, f"清空失败：{e}", "error")
        self._load()

    def open_dir(self) -> None:
        from .settings_page import open_local
        if not open_local(str(FILES_DIR)):
            QMessageBox.information(
                self, "目录位置",
                f"资源管理器没能打开，路径是：\n{FILES_DIR}")
