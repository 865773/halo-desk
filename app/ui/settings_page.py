"""设置页：目录、开机自启、数据清理、关于。"""
from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QSpinBox, QVBoxLayout)

from .. import memory
from ..config import CFG, data_dir
from ..debuglog import DBG
from . import common, theme
from .base import Page


def _to_int(text: str) -> int:
    try:
        return int((text or "").strip())
    except Exception:
        return 0


def open_local(path: str, reveal_file: bool = False) -> bool:
    """用资源管理器打开目录 / 定位文件。失败返回 False，由调用方提示。"""
    p = os.path.abspath(path)
    if not os.path.exists(p):
        try:
            os.makedirs(p, exist_ok=True)
        except Exception:
            return False
    if sys.platform == "win32":
        try:
            if reveal_file and os.path.isfile(p):
                subprocess.Popen(["explorer.exe", "/select,", os.path.normpath(p)])
                return True
            os.startfile(os.path.normpath(p))  # noqa: S606
            return True
        except Exception:
            pass
    try:
        return QDesktopServices.openUrl(QUrl.fromLocalFile(p))
    except Exception:
        return False

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_ID = "HaloDesk"


def autostart_enabled() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_ID)
        return True
    except Exception:
        return False


def set_autostart(on: bool) -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            if on:
                cmd = f'"{sys.executable}"' if getattr(sys, "frozen", False) \
                    else f'"{sys.executable}" "{os.path.join(os.getcwd(), "main.py")}"'
                winreg.SetValueEx(k, APP_ID, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(k, APP_ID)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False


class _PathRow(QHBoxLayout):
    def __init__(self, title: str, path: str, open_file: bool = False):
        super().__init__()
        self.setSpacing(8)
        name = QLabel(title)
        name.setFixedWidth(72)
        lb = QLabel(path)
        lb.setObjectName("muted")
        lb.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lb.setWordWrap(True)
        self.addWidget(name)
        self.addWidget(lb, 1)
        btn = common.button("打开", ghost=True)
        btn.clicked.connect(lambda: self._open(path, open_file))
        self.addWidget(btn)
        cp = common.button("复制", ghost=True)
        cp.clicked.connect(lambda: QApplication.clipboard().setText(path))
        self.addWidget(cp)

    @staticmethod
    def _open(path: str, open_file: bool) -> None:
        ok = open_local(path, reveal_file=open_file and os.path.isfile(path))
        if not ok:
            QMessageBox.information(
                QApplication.activeWindow(), "打不开",
                "系统没有响应打开操作，路径是：\n\n" + path + "\n\n可以手动复制到资源管理器。")


class SettingsPage(Page):
    key = "settings"

    def __init__(self, app):
        super().__init__(app, "设置", "数据都存在本机，不会上传到任何服务器。")
        root = str(data_dir())
        files = str(data_dir() / "files")
        logs = str(data_dir() / "logs")

        general = common.Card(padding=20, spacing=12)
        general.box.addWidget(common.card_title("通用"))
        general.box.addWidget(common.line())
        self.autostart = QCheckBox("开机自动启动")
        self.autostart.setChecked(autostart_enabled())
        self.autostart.stateChanged.connect(self._toggle_autostart)
        general.box.addWidget(self.autostart)
        self.dark = QCheckBox("黑夜模式")
        self.dark.setChecked(bool(CFG.get("general.dark_mode", False)))
        self.dark.stateChanged.connect(self._toggle_dark)
        general.box.addWidget(self.dark)
        general.box.addWidget(common.hint(
            "默认浅色；打开黑夜模式后重启程序完全生效。"))
        general.box.addWidget(common.hint(
            "写入当前用户的注册表启动项（HKCU\\...\\Run），不需要管理员权限。"))
        self.body.addWidget(general)

        pet = common.Card(padding=20, spacing=12)
        pet.box.addWidget(common.card_title("桌面挂件"))
        self.pet_on = QCheckBox("启用桌面挂件（默认开启）")
        self.pet_on.setChecked(bool(CFG.get("fish.pet_on", True)))
        self.pet_on.stateChanged.connect(
            lambda s: (CFG.set("fish.pet_on", bool(s)), CFG.save(),
                       self.app.open_pet(bool(s))))
        pet.box.addWidget(self.pet_on)
        prow = QHBoxLayout()
        prow.addWidget(QLabel("大小"))
        self.pet_size = QSpinBox()
        self.pet_size.setRange(80, 320)
        self.pet_size.setSuffix(" px")
        self.pet_size.setValue(int(CFG.get("fish.size", 150) or 150))
        self.pet_size.valueChanged.connect(
            lambda v: (CFG.set("fish.size", int(v)), CFG.save(),
                       self.app.pet_resize()))
        prow.addWidget(self.pet_size)
        prow.addStretch(1)
        pet.box.addLayout(prow)
        pet.box.addWidget(common.hint(
            "左键拖动；双击打开主界面；右键菜单：摸摸头（心情+3）、喂白米饭（心情+5）、"
            "和她说句话、两个平台签到、隐藏挂件。挂件独立于总开关，关掉总开关也会留着。"))
        self.body.addWidget(pet)

        # ---------- AI 配置 ----------
        ai = common.Card(padding=20, spacing=10)
        ai.box.addWidget(common.card_title("AI 配置"))
        ai.box.addWidget(common.hint(
            "日常文字用 deepseek-chat；有图片时自动换看图模型。"
            "也可以在下面接任意 OpenAI 兼容接口（中转站/其他厂商）。"))
        prow2 = QHBoxLayout()
        prow2.addWidget(QLabel("使用"))
        self.ai_provider = QComboBox()
        self.ai_provider.addItems(["DeepSeek 官方", "自定义（OpenAI 兼容）"])
        self.ai_provider.setCurrentIndex(
            1 if CFG.get("ai.provider", "deepseek") == "custom" else 0)
        self.ai_provider.currentIndexChanged.connect(self._save_ai)
        prow2.addWidget(self.ai_provider)
        prow2.addStretch(1)
        ai.box.addLayout(prow2)
        self.ai_key = QLineEdit(CFG.get("ai.key", ""))
        self.ai_key.setEchoMode(QLineEdit.Password)
        self.ai_key.setPlaceholderText("DeepSeek API Key（sk-...）")
        self.ai_key.editingFinished.connect(self._save_ai)
        ai.box.addWidget(self.ai_key)
        crow = QHBoxLayout()
        self.ai_base = QLineEdit(CFG.get("ai.custom_base", ""))
        self.ai_base.setPlaceholderText("自定义接口地址，例如 https://api.openai.com/v1")
        self.ai_base.editingFinished.connect(self._save_ai)
        crow.addWidget(self.ai_base, 1)
        ai.box.addLayout(crow)
        crow2 = QHBoxLayout()
        self.ai_ckey = QLineEdit(CFG.get("ai.custom_key", ""))
        self.ai_ckey.setEchoMode(QLineEdit.Password)
        self.ai_ckey.setPlaceholderText("自定义 API Key")
        self.ai_ckey.editingFinished.connect(self._save_ai)
        crow2.addWidget(self.ai_ckey, 1)
        self.ai_cmodel = QLineEdit(CFG.get("ai.custom_model", ""))
        self.ai_cmodel.setPlaceholderText("自定义模型名")
        self.ai_cmodel.editingFinished.connect(self._save_ai)
        crow2.addWidget(self.ai_cmodel, 1)
        self.ai_cvision = QLineEdit(CFG.get("ai.custom_vision", ""))
        self.ai_cvision.setPlaceholderText("看图模型名（可空）")
        self.ai_cvision.editingFinished.connect(self._save_ai)
        crow2.addWidget(self.ai_cvision, 1)
        ai.box.addLayout(crow2)
        trow = QHBoxLayout()
        trow.addWidget(common.button("测试 AI", primary=True, on_click=self._test_ai))
        self.ai_state = common.muted("")
        trow.addWidget(self.ai_state, 1)
        ai.box.addLayout(trow)
        self.body.addWidget(ai)

        paths = common.Card(padding=20, spacing=10)
        paths.box.addWidget(common.card_title("目录"))
        paths.box.addWidget(common.line())
        paths.box.addLayout(_PathRow("数据目录", root))
        paths.box.addLayout(_PathRow("记忆文件", files))
        paths.box.addLayout(_PathRow("日志目录", logs))
        paths.box.addLayout(_PathRow("调试日志", str(DBG.path), open_file=True))
        paths.box.addWidget(common.hint(
            "用户记忆按平台分开：mem_hlx_u<uid>.txt / mem_lingjie_u<uid>.txt；"
            "通用记忆和生活记忆两个社区共用。"))
        self.body.addWidget(paths)

        data = common.Card(padding=20, spacing=12)
        data.box.addWidget(common.card_title("数据"))
        data.box.addWidget(common.hint(
            "记忆文件在 files/ 目录下：memory.txt（通用记忆）、mem_<平台>_u<uid>.txt（用户记忆）、"
            "life.txt（生活记录）、mood.json（心情）、relations.json（亲密度）、"
            "activity.jsonl（动态）、auto_state.json（消息去重）。"))
        row = QHBoxLayout()
        b1 = common.button("清空大肥鱼记忆")
        b1.clicked.connect(self.clear_memory)
        b2 = common.button("打开数据文件夹", ghost=True)
        b2.clicked.connect(lambda: open_local(files))
        b3 = common.button("打开调试日志", ghost=True)
        b3.clicked.connect(lambda: open_local(str(DBG.path)) or open_local(str(DBG.path.parent)))
        b4 = common.button("清除去重记录", ghost=True)
        b4.clicked.connect(self.clear_dedupe)
        b5 = common.button("导出数据备份", ghost=True)
        b5.clicked.connect(self.export_backup)
        b6 = common.button("退出全部账号", ghost=True)
        b6.clicked.connect(self.logout_all)
        b7 = common.button("清空所有数据", ghost=True)
        b7.clicked.connect(self.clear_all_data)
        row.addWidget(b1)
        row.addWidget(b2)
        row.addWidget(b3)
        row.addWidget(b4)
        row.addWidget(b5)
        row.addWidget(b6)
        row.addWidget(b7)
        row.addStretch(1)
        data.box.addLayout(row)
        self.body.addWidget(data)


        about = common.Card(padding=20, spacing=10)
        about.box.addWidget(common.card_title("关于"))
        about.box.addWidget(common.hint(
            "大肥鱼桌面版是把 hlx-halo（葫芦侠三楼）和 lingjie-halo（灵芥空间）"
            "两个 Android 项目合并移植成的 Windows 桌面程序。"))
        link = QLabel(
            '本项目：<a style="color:{c}" href="https://gitee.com/guo-wenlong/halo-desk">'
            'gitee.com/guo-wenlong/halo-desk</a><br>'
            '葫芦侠三楼主页：<a style="color:{c}" href="https://www.huluxia.com">'
            'www.huluxia.com</a><br>'
            '灵芥助手主页：<a style="color:{c}" href="https://gitee.com/guo-wenlong/lingjie-halo">'
            'gitee.com/guo-wenlong/lingjie-halo</a><br>'
            '作者：<b>dudu</b>'.replace("{c}", theme.ACCENT))
        link.setOpenExternalLinks(True)
        link.setTextInteractionFlags(Qt.TextBrowserInteraction)
        about.box.addWidget(link)
        arow = QHBoxLayout()
        arow.addWidget(common.button("赞赏支持", primary=True,
                                     on_click=self.show_reward))
        arow.addStretch(1)
        about.box.addLayout(arow)
        about.box.addWidget(common.hint(
            "自动签到等操作会调用社区官方接口，请保持合理频率，避免账号风控。"))
        self.body.addWidget(about)
        self.body.addStretch(1)

    def _toggle_autostart(self, state) -> None:
        ok = set_autostart(bool(state))
        if ok:
            common.toast(self.app, "已更新开机启动设置", "ok")
        else:
            common.toast(self.app, "设置失败（可能被安全软件拦截）", "err")

    def _toggle_dark(self, state) -> None:
        CFG.set("general.dark_mode", bool(state))
        CFG.save()
        from . import theme
        theme.apply(self.app.window(), bool(state))
        common.toast(self.app, "已切换，部分界面重启后完全生效", "ok")

    def clear_all_data(self) -> None:
        """重置配置（账号/Key/开关），但保留 data/账号/<平台>/<uid> 下的记忆。"""
        import copy
        from PySide6.QtWidgets import QMessageBox
        from ..config import DEFAULTS
        if QMessageBox.question(
                self, "清空所有数据",
                "会重置所有配置和登录态（记忆按账号保留在 data/账号/ 里，"
                "登录后恢复）。确定重新开始？") != QMessageBox.Yes:
            return
        CFG.data = copy.deepcopy(DEFAULTS)
        CFG.data.setdefault("general", {})["first_run"] = True
        CFG.save()
        try:
            self.app.autopilot.stop()
            self.app.close_pet()
        except Exception:
            pass
        self.app.notify_accounts()
        common.toast(self.app, "已重置，重启后从向导开始", "ok")

    def logout_all(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(self, "退出全部账号",
                                "会清掉两个平台的登录态并停用大肥鱼，确定？") \
                != QMessageBox.Yes:
            return
        for k in ("hlx.key", "hlx.uid", "hlx.nick", "hlx.level",
                  "lingjie.token", "lingjie.uid", "lingjie.nickname",
                  "lingjie.level", "lingjie.exp", "lingjie.next_exp"):
            CFG.set(k, 0 if k.endswith(("uid", "level", "exp", "next_exp")) else "")
        CFG.set("fish.enabled", False)
        CFG.save()
        try:
            self.app.autopilot.stop()
            self.app.close_pet()
        except Exception:
            pass
        self.app.notify_accounts()
        common.toast(self.app, "已退出全部账号", "ok")

    def export_backup(self) -> None:
        """把 data 目录打包到桌面，换机或备份用。"""
        import shutil
        import time
        from pathlib import Path
        from PySide6.QtCore import QStandardPaths
        root = data_dir()
        desk = QStandardPaths.writableLocation(QStandardPaths.DesktopLocation) or str(Path.home())
        out = Path(desk) / f"HaloDesk-backup-{time.strftime('%Y%m%d-%H%M')}.zip"
        common.toast(self.app, "正在打包…", "info")

        def work(_e):
            return shutil.make_archive(str(out.with_suffix("")), "zip", str(root))

        def done(path):
            common.toast(self.app, f"已导出：{path}", "ok")
            open_local(str(Path(path).parent))

        def fail(e):
            common.toast(self.app, f"导出失败：{e}", "error")

        common.run_bg(work, done, fail)

    def show_reward(self) -> None:
        import os as _os
        from ..paths import resource
        p = resource("assets/reward.png")
        dlg = QDialog(self)
        dlg.setWindowTitle("赞赏支持 dudu")
        lay = QVBoxLayout(dlg)
        lb = QLabel()
        pix = QPixmap(p)
        if not pix.isNull():
            lb.setPixmap(pix.scaled(320, 420, Qt.KeepAspectRatio,
                                    Qt.SmoothTransformation))
        else:
            lb.setText("没找到赞赏码图片")
        lb.setAlignment(Qt.AlignCenter)
        lay.addWidget(lb)
        lay.addWidget(QLabel("谢谢支持～"))
        dlg.exec()

    def _save_ai(self, *_a) -> None:
        CFG.set("ai.provider",
                "custom" if self.ai_provider.currentIndex() == 1 else "deepseek")
        CFG.set("ai.key", self.ai_key.text().strip())
        CFG.set("ai.custom_base", self.ai_base.text().strip())
        CFG.set("ai.custom_key", self.ai_ckey.text().strip())
        CFG.set("ai.custom_model", self.ai_cmodel.text().strip())
        CFG.set("ai.custom_vision", self.ai_cvision.text().strip())
        CFG.save()

    def _test_ai(self) -> None:
        self._save_ai()
        self.ai_state.setText("测试中…")
        from .common import run_bg

        def work(_e):
            from .. import ai
            return ai.ask("只回复两个字：可用", "测试")

        def done(t):
            self.ai_state.setText(f"可用 ✔（{str(t)[:8]}）")

        def fail(e):
            self.ai_state.setText(f"不可用：{e}")

        run_bg(work, done, fail)

    def clear_dedupe(self) -> None:
        """清掉「已评论/已回复」记录（评论卡在审核时可以用它重试）。"""
        import json
        from PySide6.QtWidgets import QMessageBox
        from ..config import FILES_DIR
        if QMessageBox.question(self, "清除去重记录",
                                "清掉之后可能对同一帖子/消息再评论一次，确定？") \
                != QMessageBox.Yes:
            return
        removed = 0
        for p in FILES_DIR.glob("roam_commented_*.json"):
            try:
                p.unlink()
                removed += 1
            except Exception:
                pass
        state_path = FILES_DIR / "auto_state.json"
        try:
            data = json.loads(state_path.read_text("utf-8"))
            data["hlx"] = []
            data["lj"] = []
            state_path.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
            removed += 1
        except Exception:
            pass
        common.toast(self.app, f"已清除去重记录（{removed} 处）", "ok")

    def clear_memory(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        ret = QMessageBox.question(self, "清空记忆", "确定要清空大肥鱼的所有记忆吗？此操作不可恢复。")
        if ret != QMessageBox.Yes:
            return
        for p in memory.FILES_DIR.glob("mem*.txt"):
            try:
                p.write_text("", "utf-8")
            except Exception:
                pass
        common.toast(self.app, "记忆已清空", "ok")

    def refresh(self) -> None:
        self.autostart.setChecked(autostart_enabled())
