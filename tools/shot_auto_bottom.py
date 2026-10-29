import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QScrollArea

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main() -> None:
    from app.ui import theme
    from app.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(theme.QSS)
    win = MainWindow()
    win.resize(1120, 760)
    win.show()
    win.show_page("auto")
    app.processEvents()

    def scroll():
        page = win.pages["auto"]
        area = page.findChild(QScrollArea)
        if area:
            bar = area.verticalScrollBar()
            bar.setValue(bar.maximum())
        app.processEvents()
        QTimer.singleShot(300, save)

    def save():
        win.grab().save(os.path.join(ROOT, "docs", "shots", "auto_bottom.png"))
        app.quit()

    QTimer.singleShot(800, scroll)
    app.exec()
    os._exit(0)


if __name__ == "__main__":
    main()
