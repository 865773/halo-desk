"""离屏渲染各页面，用于快速视觉检查。

用法：QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:\\Windows\\Fonts python tools/shots.py
"""
import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "docs", "shots")
os.makedirs(OUT, exist_ok=True)


def main() -> None:
    from app.ui import theme
    from app.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(theme.QSS)
    win = MainWindow()
    win.resize(1120, 760)
    win.show()

    order = ["home", "hlx", "lingjie", "fish", "activity", "auto", "debug", "settings"]
    state = {"i": 0}

    def shot():
        if state["i"] >= len(order):
            win.open_pet(True)
            if win.pet is not None:
                win.pet.grab().save(os.path.join(OUT, "pet.png"))
                win.pet.bubble.close()
                win.pet.close()
            app.quit()
            return
        key = order[state["i"]]
        win.show_page(key)
        app.processEvents()
        QTimer.singleShot(350, lambda: _save(key))

    def _save(key):
        win.grab().save(os.path.join(OUT, f"{key}.png"))
        state["i"] += 1
        QTimer.singleShot(150, shot)

    QTimer.singleShot(600, shot)
    app.exec()
    os._exit(0)


if __name__ == "__main__":
    main()
