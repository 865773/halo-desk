"""调试日志页。"""
from __future__ import annotations

import os

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QTextBrowser

from ..debuglog import DBG
from . import common, theme
from .base import Page


def open_path(path: str) -> bool:
    p = os.path.abspath(path)
    if os.path.isfile(p):
        return QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(p)))
    return QDesktopServices.openUrl(QUrl.fromLocalFile(p))


class DebugPage(Page):
    key = "debug"

    def __init__(self, app):
        super().__init__(app, "调试日志", "所有请求、AI 调用、异常都会记在这里，排查问题用。")
        bar = common.Card(padding=14, spacing=8)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.path_lb = QLabel(str(DBG.path))
        self.path_lb.setObjectName("muted")
        self.path_lb.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(QLabel("日志文件"))
        row.addWidget(self.path_lb, 1)
        row.addWidget(common.button("打开目录", ghost=True,
                                    on_click=lambda: open_path(str(DBG.path))))
        row.addWidget(common.button("查看提示词", ghost=True, on_click=self.show_prompts))
        row.addWidget(common.button("清空", ghost=True, on_click=self.clear))
        bar.box.addLayout(row)
        self.body.addWidget(bar)

        card = common.Card(padding=8, spacing=0)
        self.view = QTextBrowser()
        f = QFont("Consolas")
        f.setPointSize(9)
        self.view.setFont(f)
        self.view.setStyleSheet(
            f"background:#0B1220;border:1px solid {theme.LINE};"
            f"border-radius:10px;padding:8px;font-size:12px;")
        card.box.addWidget(self.view)
        self.body.addWidget(card)

        DBG.line.connect(self.append)
        for ln in DBG.tail(300):
            self.append(ln, False)

    def append(self, line: str, autoscroll: bool = True) -> None:
        color = theme.MUTED
        if "[ERROR]" in line:
            color = theme.ERR
        elif "[WARN " in line or "[WARN]" in line:
            color = theme.WARN
        self.view.append(f"<span style='color:{color}'>{line}</span>")
        if autoscroll:
            sb = self.view.verticalScrollBar()
            sb.setValue(sb.maximum())

    def show_prompts(self) -> None:
        """把喂给大肥鱼的所有系统提示词列出来。"""
        from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                                       QTextBrowser, QVBoxLayout)
        from ..prompts import all_prompts

        prompts = all_prompts()
        dlg = QDialog(self)
        dlg.setWindowTitle("大肥鱼的系统提示词")
        dlg.resize(860, 640)
        lay = QVBoxLayout(dlg)
        combo = QComboBox()
        for name, _ in prompts:
            combo.addItem(name)
        lay.addWidget(combo)
        view = QTextBrowser()
        view.setStyleSheet("font-size:12px;background:#0B1220;color:#E6EDF7;")
        lay.addWidget(view, 1)

        def _show(idx: int) -> None:
            view.setPlainText(prompts[idx][1])

        combo.currentIndexChanged.connect(_show)
        _show(0)
        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.rejected.connect(dlg.reject)
        lay.addWidget(box)
        dlg.exec()

    def clear(self) -> None:
        DBG.clear()
        self.view.clear()

    def refresh(self) -> None:
        self.path_lb.setText(str(DBG.path))
