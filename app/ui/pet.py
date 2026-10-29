"""桌面悬浮挂件：置顶、可拖动、点击互动。"""
from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QPoint, QRect, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QColor, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QMenu, QWidget

from .. import ai, memory, persona
from ..config import CFG
from ..paths import resource


class Bubble(QWidget):
    """挂件头顶的对话气泡（独立窗口，可以超出挂件范围）。"""

    def __init__(self, app):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.label.setMaximumWidth(260)
        self.label.setStyleSheet(
            "background: rgba(20,31,53,0.96); color:#E6EDF7;"
            "border:1px solid #38BDF8; border-radius:12px;"
            "padding:9px 12px; font-size:12px;")
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def say(self, text: str, ms: int = 7000) -> None:
        self.label.setText(text)
        self.label.adjustSize()
        self.resize(self.label.size())
        self.move(self.pos())
        self.show()
        self.raise_()
        self._timer.start(ms)

    def move(self, pos):  # noqa: N802
        super().move(pos)


class PetWindow(QWidget):
    clicked = Signal()
    open_main = Signal()

    def __init__(self, app):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setContextMenuPolicy(Qt.DefaultContextMenu)

        self._pix = QPixmap(resource("assets/dafeiyu.png"))
        self._base = int(CFG.get("fish.size", 150))
        self._pad = 18
        self._bob = 0.0
        self._drag_from = None
        self._win_from = None
        self._moved = False
        self.bubble = Bubble(app)
        self.setWindowOpacity(float(CFG.get("fish.alpha", 1.0)))

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(50)
        self._apply_size()

    # ---------- 尺寸 / 位置 ----------
    def _apply_size(self) -> None:
        self._base = int(CFG.get("fish.size", 150))
        side = self._base + self._pad * 2
        self.setFixedSize(side, side)
        self.setWindowOpacity(float(CFG.get("fish.alpha", 1.0)))
        self.update()

    def apply_settings(self) -> None:
        self._apply_size()

    def show_near_default(self) -> None:
        x = CFG.get("fish.pos_x", -1)
        y = CFG.get("fish.pos_y", -1)
        screen = self.screen().availableGeometry() if self.screen() else QRect(0, 0, 1920, 1080)
        if x is None or int(x) < 0 or y is None or int(y) < 0:
            x = screen.right() - self.width() - 40
            y = screen.bottom() - self.height() - 80
        self.move(int(x), int(y))
        self.show()
        self.raise_()

    def _place_bubble(self) -> None:
        if not self.bubble.isVisible():
            return
        g = self.frameGeometry()
        bw = self.bubble.width()
        x = g.center().x() - bw // 2
        y = g.top() - self.bubble.height() - 6
        self.bubble.move(QPoint(x, y))

    # ---------- 绘制 ----------
    def _animate(self) -> None:
        self._bob += 0.09
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        side = self._base
        ox = self._pad
        oy = self._pad + int(math.sin(self._bob) * 4)

        # 影子
        p.setBrush(QColor(0, 0, 0, 70))
        p.setPen(Qt.NoPen)
        p.drawEllipse(ox + side // 5, oy + side - 14, side * 3 // 5, 16)

        if not self._pix.isNull():
            pm = self._pix.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p.drawPixmap(ox + (side - pm.width()) // 2, oy + (side - pm.height()), pm)

    # ---------- 交互 ----------
    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.LeftButton:
            self._drag_from = e.globalPosition().toPoint()
            self._win_from = self.pos()
            self._moved = False
        elif e.button() == Qt.RightButton:
            self._menu(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        if self._drag_from is None:
            return
        cur = e.globalPosition().toPoint()
        delta = cur - self._drag_from
        if abs(delta.x()) + abs(delta.y()) > 4:
            self._moved = True
        self.move(self._win_from + delta)
        self._place_bubble()

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if e.button() != Qt.LeftButton:
            return
        self._drag_from = None
        if self._moved:
            CFG.set("fish.pos_x", self.x())
            CFG.set("fish.pos_y", self.y())
            CFG.save()
            self._place_bubble()
            return
        self.pet()

    def mouseDoubleClickEvent(self, e) -> None:  # noqa: N802
        self.open_main.emit()

    def pet(self) -> None:
        memory.nudge_mood(random.choice([1, 2, 2, 3]))
        if not CFG.get("ai.key", ""):
            self.say(random.choice(persona.PET_REPLIES))
            return
        self.say("…", 900)
        system = self._system()
        seed = random.choice(persona.PET_REPLIES)

        def work(_e):
            return ai.ask(system, "主人摸了摸你的头。用一句话回应，10-25字，口语。", 
                          CFG.get("ai.model_basic"))

        def done(text):
            text = (text or "").strip()
            self.say(text if text else seed)

        def fail(_m):
            self.say(seed)

        from .common import run_bg
        run_bg(work, done, fail)

    def say(self, text: str, ms: int = 7000) -> None:
        self._place_bubble()
        self.bubble.say(text, ms)
        self._place_bubble()

    def _system(self) -> str:
        p = CFG.get("fish.persona", "") or persona.DEFAULT_PERSONA
        mood = memory.get_mood()
        parts = [p, f"【心情】{memory.mood_label(mood)}（{mood}/100）"]
        mem = memory.recent(6)
        if mem:
            parts.append("【最近的记忆】\n" + mem)
        return "\n".join(parts)

    def _menu(self, global_pos: QPoint) -> None:
        m = QMenu()
        a1 = QAction("说句话", m)
        a1.triggered.connect(self.pet)
        a2 = QAction("打开主界面", m)
        a2.triggered.connect(self.open_main.emit)
        a3 = QAction("两个平台签到", m)
        a3.triggered.connect(lambda: self.app.signin_all())
        a4 = QAction("隐藏挂件", m)
        a4.triggered.connect(lambda: self.app.open_pet(False))
        m.addAction(a1)
        m.addAction(a2)
        m.addAction(a3)
        m.addSeparator()
        m.addAction(a4)
        m.exec(global_pos)

    def hideEvent(self, e) -> None:  # noqa: N802
        self.bubble.hide()
        super().hideEvent(e)
