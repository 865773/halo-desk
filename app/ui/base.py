"""页面基类：标题 + 可滚动内容区。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QVBoxLayout, QWidget)

from . import common, theme


class Page(QWidget):
    key = ""

    def __init__(self, app, title: str, sub: str = ""):
        super().__init__()
        self.setObjectName("pageShell")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.app = app
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 24, 18)
        outer.setSpacing(14)

        head = QWidget()
        hl = QHBoxLayout(head)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(common.title(title, sub), 1)
        self.head_extra = hl
        outer.addWidget(head)

        from PySide6.QtWidgets import QScrollArea
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        inner.setObjectName("pageBody")
        self.body = QVBoxLayout(inner)
        self.body.setContentsMargins(0, 0, 6, 10)
        self.body.setSpacing(16)
        area.setWidget(inner)
        vp = area.viewport()
        if getattr(theme, "WALL", False):
            vp.setAutoFillBackground(False)
            vp.setObjectName("wallViewport")
            vp.setStyleSheet(
                "QWidget#wallViewport { background: transparent; }")
        else:
            vp.setAutoFillBackground(True)
            from PySide6.QtGui import QColor, QPalette
            pal = vp.palette()
            pal.setColor(QPalette.Window, QColor(theme.BG2))
            vp.setPalette(pal)
        outer.addWidget(area, 1)

    def paintEvent(self, _e) -> None:  # noqa: N802
        if getattr(theme, "WALL", False):
            from PySide6.QtGui import QColor, QPainter
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(8, 16, 32, 120))
            p.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 18, 18)
            p.end()
        super().paintEvent(_e)

    def refresh(self) -> None:  # pragma: no cover - 由子类覆盖
        pass
