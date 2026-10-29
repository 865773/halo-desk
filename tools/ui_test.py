"""界面冒烟测试：不需要账号，验证点击、提示、挂件等交互路径。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel

results = []


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL", name, extra))


def main() -> int:
    from app.ui import theme
    from app.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(theme.QSS)
    win = MainWindow()
    win.show()
    app.processEvents()

    check("启动页是已知页面", win.stack.currentWidget() in win.pages.values(),
          win.stack.currentWidget().key)

    for key in ("hlx", "lingjie", "fish", "activity", "auto", "debug", "settings", "home"):
        win.show_page(key)
        app.processEvents()
        check(f"导航到 {key}", win.stack.currentWidget() is win.pages[key],
              win.stack.currentWidget().key)

    # 未登录点签到，应弹提示而不是崩
    win.show_page("hlx")
    app.processEvents()
    win.pages["hlx"].start_signin()
    app.processEvents()
    toasts = [w.text() for w in win.findChildren(QLabel)
              if "登录" in w.text() and w.isVisible()]
    check("未登录签到有提示", any("请先登录" in t for t in toasts), str(toasts[:3]))

    # 未配置 Key 时点“测试连接”，应该走失败提示
    win.show_page("fish")
    app.processEvents()
    win.pages["fish"].test_ai()
    app.processEvents()
    QTimer.singleShot(1500, app.quit)

    # 挂件
    win.open_pet(True)
    app.processEvents()
    check("挂件已打开", win.pet is not None and win.pet.isVisible())
    win.pet.pet()
    app.processEvents()
    check("挂件能说话", win.pet.bubble.isVisible() and bool(win.pet.bubble.label.text()),
          win.pet.bubble.label.text()[:40])

    def finish():
        win.pet.bubble.close()
        win.pet.close()
        app.quit()

    QTimer.singleShot(1200, finish)
    app.exec()

    for status, name, extra in results:
        print(f"{status}\t{name}\t{extra}")
    bad = [r for r in results if r[0] == "FAIL"]
    print(f"\n{len(results) - len(bad)}/{len(results)} 通过")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
