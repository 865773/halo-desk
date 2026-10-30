"""设置页：目录、开机自启、数据清理、关于。"""
from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QSlider, QSpinBox, QVBoxLayout, QWidget)

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
        accounts = str(data_dir() / "账号")

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
        self.pet_size = QSlider(Qt.Horizontal)
        self.pet_size.setRange(80, 320)
        self.pet_size.setValue(int(CFG.get("fish.size", 150) or 150))
        self.pet_size.setMinimumWidth(240)
        self.pet_size_lb = QLabel(f"{self.pet_size.value()} px")
        self.pet_size_lb.setFixedWidth(60)
        self.pet_size.valueChanged.connect(self._pet_size_changed)
        prow.addWidget(self.pet_size, 1)
        prow.addWidget(self.pet_size_lb)
        pet.box.addLayout(prow)
        pet.box.addWidget(common.button("查看所有形象 / 动作", ghost=True,
                                        on_click=self.show_pet_gallery))
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
        self.ds_box = QWidget()
        ds_lay = QVBoxLayout(self.ds_box)
        ds_lay.setContentsMargins(0, 0, 0, 0)
        ds_lay.addWidget(self.ai_key)
        ai.box.addWidget(self.ds_box)

        self.custom_box = QWidget()
        cb_lay = QVBoxLayout(self.custom_box)
        cb_lay.setContentsMargins(0, 0, 0, 0)
        self.ai_base = QLineEdit(CFG.get("ai.custom_base", ""))
        self.ai_base.setPlaceholderText("自定义接口地址，例如 https://api.openai.com/v1")
        self.ai_base.editingFinished.connect(self._save_ai)
        cb_lay.addWidget(self.ai_base)
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
        cb_lay.addWidget(self.ai_cvision, 1)
        cb_lay.addLayout(crow2)
        cb_lay.addWidget(common.button("一键填入阿里云", ghost=True,
                                       on_click=self._fill_ai_aliyun))
        ai.box.addWidget(self.custom_box)
        self.think_model = QLineEdit(CFG.get("ai.think_model", ""))
        self.think_model.setPlaceholderText(
            "深度思考模型（可选）：只用于逛社区决策、长记忆压缩；留空=不用")
        self.think_model.editingFinished.connect(self._save_ai)
        ai.box.addWidget(self.think_model)
        self._sync_ai_boxes()
        trow = QHBoxLayout()
        trow.addWidget(common.button("测试 AI", primary=True, on_click=self._test_ai))
        self.ai_state = common.muted("")
        trow.addWidget(self.ai_state, 1)
        ai.box.addLayout(trow)
        self.mem_gate = QCheckBox("让大肥鱼自己判断哪些内容值得记住")
        self.mem_gate.setChecked(bool(CFG.get("fish.mem_gate", True)))
        self.mem_gate.stateChanged.connect(
            lambda s: (CFG.set("fish.mem_gate", bool(s)), CFG.save()))
        ai.box.addWidget(self.mem_gate)
        ai.box.addWidget(common.hint(
            "开启后：长期稳定、纠正反馈、明确约定才存入；一次性任务、临时状态不存，"
            "拿不准优先不存。关闭则恢复全部保存。"))
        self.body.addWidget(ai)

        # ---------- 文生图 ----------
        img = common.Card(padding=20, spacing=10)
        img.box.addWidget(common.card_title("文生图"))
        img.box.addWidget(common.hint(
            "默认阿里云百炼：一键填入地址和模型，只贴 Key；"
            "不配也能用，只是发帖不带图。"))
        img.box.addWidget(common.button("一键填入阿里云（百炼）", primary=True,
                                        on_click=self._fill_aliyun))
        self.img_proto = QComboBox()
        for value, label in (("dashscope", "阿里云 DashScope"),
                             ("openai", "OpenAI 兼容"),
                             ("sd", "Stable Diffusion")):
            self.img_proto.addItem(label, value)
        cur = CFG.get("fish.img_proto", "dashscope")
        self.img_proto.setCurrentIndex(max(0, self.img_proto.findData(cur)))
        img.box.addWidget(self.img_proto)
        self.img_url = QLineEdit(CFG.get("fish.img_url", ""))
        self.img_url.setPlaceholderText("接口地址")
        self.img_url.editingFinished.connect(self._save_image)
        img.box.addWidget(self.img_url)
        irow = QHBoxLayout()
        self.img_key = QLineEdit(CFG.get("fish.img_key", ""))
        self.img_key.setEchoMode(QLineEdit.Password)
        self.img_key.setPlaceholderText("生图 API Key")
        self.img_key.editingFinished.connect(self._save_image)
        irow.addWidget(self.img_key, 2)
        self.img_model = QLineEdit(CFG.get("fish.img_model", "wan2.6-t2i"))
        self.img_model.setPlaceholderText("当前模型")
        self.img_model.editingFinished.connect(self._save_image)
        irow.addWidget(self.img_model, 1)
        img.box.addLayout(irow)
        self.img_models = QLineEdit(CFG.get("fish.img_models", ""))
        self.img_models.setPlaceholderText("备用模型，逗号分隔")
        self.img_models.editingFinished.connect(self._save_image)
        img.box.addWidget(self.img_models)
        itest = QHBoxLayout()
        itest.addWidget(common.button("测试文生图", primary=True,
                                      on_click=self._test_image))
        self.img_state = common.muted("")
        itest.addWidget(self.img_state, 1)
        img.box.addLayout(itest)
        self.body.addWidget(img)

        paths = common.Card(padding=20, spacing=10)
        paths.box.addWidget(common.card_title("目录"))
        paths.box.addWidget(common.line())
        paths.box.addLayout(_PathRow("数据目录", root))
        paths.box.addLayout(_PathRow("账号记忆目录", accounts))
        paths.box.addLayout(_PathRow("公共文件（生活记忆等）", files))
        paths.box.addLayout(_PathRow("日志目录", logs))
        paths.box.addLayout(_PathRow("调试日志", str(DBG.path), open_file=True))
        paths.box.addWidget(common.hint(
            "通用记忆、用户记忆、动态、心情都在「账号记忆目录」下，"
            "按 平台/uid 分开；生活记忆是共享的，在公共文件里。"))
        self.body.addWidget(paths)

        data = common.Card(padding=20, spacing=12)
        data.box.addWidget(common.card_title("数据"))
        data.box.addWidget(common.hint(
            "记忆在「账号记忆目录/平台/uid/」下：memory.txt（通用记忆）、"
            "mem_<平台>_u<uid>.txt（用户记忆）、activity.jsonl（动态）、mood.json（心情）；"
            "生活记忆和全局关系在公共文件里。"))
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
            '作者：<a style="color:{c}" href="https://gitee.com/guo-wenlong">dudu</a><br>'
            '本项目：<a style="color:{c}" href="https://gitee.com/guo-wenlong/halo-desk">'
            'gitee.com/guo-wenlong/halo-desk</a><br>'
            '葫芦侠大肥鱼：<a style="color:{c}" href="https://gitee.com/guo-wenlong/hlx-halo">'
            'gitee.com/guo-wenlong/hlx-halo</a><br>'
            '灵芥助手：<a style="color:{c}" href="https://gitee.com/guo-wenlong/lingjie-halo">'
            'gitee.com/guo-wenlong/lingjie-halo</a><br>'
            '葫芦侠地址：<a style="color:{c}" href="https://www.huluxia.com">'
            'www.huluxia.com</a><br>'
            '灵芥空间地址：<a style="color:{c}" href="https://www.lingjie888.cn">'
            'www.lingjie888.cn</a>'.replace("{c}", theme.ACCENT))
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

    def show_pet_gallery(self) -> None:
        """预览所有形象/动作；关闭对话框恢复默认待机。"""
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QListWidget, QListWidgetItem
        from ..paths import resource

        faces = [("idle", "待机呼吸", "默认状态、无操作时"),
                 ("happy", "开心跃动", "被摸头、收到消息/回复、心情好"),
                 ("shy", "害羞惊讶", "被夸、被夸可爱时"),
                 ("angry", "傲娇生气", "被凶、心情低于 35 时"),
                 ("drag", "被拖拽悬空", "按住左键拖动挂件时"),
                 ("eat", "偷吃零食", "右键「喂白米饭」时")]
        dlg = QDialog(self)
        dlg.setWindowTitle("所有形象 / 动作")
        dlg.resize(560, 480)
        lay = QVBoxLayout(dlg)
        body = QHBoxLayout()
        lst = QListWidget()
        lst.setFixedWidth(180)
        for key, name, trig in faces:
            it = QListWidgetItem(f"{name}\n{trig}")
            it.setData(Qt.UserRole, key)
            it.setToolTip(trig)
            lst.addItem(it)
        body.addWidget(lst)
        preview = QLabel("选一个看看")
        preview.setAlignment(Qt.AlignCenter)
        preview.setMinimumSize(300, 340)
        preview.setStyleSheet(f"background:{theme.CARD2};"
                              f"border:1px solid {theme.LINE};border-radius:10px;")
        body.addWidget(preview, 1)
        lay.addLayout(body)
        tip = QLabel("关闭或点「恢复默认」会回到待机状态。")
        tip.setObjectName("muted")
        lay.addWidget(tip)

        frames: list[QPixmap] = []
        idx = {"i": 0}

        def load(key: str) -> None:
            nonlocal frames
            frames = []
            for i in range(16):
                pm = QPixmap(resource(f"assets/pet/shenshen/{key}_{i}.png"))
                if pm.isNull():
                    break
                frames.append(pm)
            idx["i"] = 0
            show()

        def show() -> None:
            if not frames:
                preview.setText("没有找到这个动作")
                return
            pm = frames[idx["i"] % len(frames)]
            preview.setPixmap(pm.scaled(preview.width() - 12,
                                        preview.height() - 12,
                                        Qt.KeepAspectRatio,
                                        Qt.SmoothTransformation))

        timer = QTimer(dlg)
        timer.setInterval(140)
        timer.timeout.connect(lambda: (idx.__setitem__("i", idx["i"] + 1), show()))
        timer.start()

        def on_select(_row: int) -> None:
            it = lst.currentItem()
            if not it:
                return
            key = it.data(Qt.UserRole)
            load(key)
            if self.app.pet is not None:
                self.app.pet.set_face(key, 0)

        def restore() -> None:
            if self.app.pet is not None:
                self.app.pet.reset_face()
            dlg.reject()

        lst.currentRowChanged.connect(on_select)
        lst.setCurrentRow(0)
        dlg.rejected.connect(
            lambda: self.app.pet.reset_face() if self.app.pet is not None else None)
        brow = QHBoxLayout()
        brow.addStretch(1)
        brow.addWidget(common.button("恢复默认", primary=True, on_click=restore))
        brow.addWidget(common.button("关闭", ghost=True, on_click=restore))
        lay.addLayout(brow)
        dlg.exec()

    def _fill_ai_aliyun(self) -> None:
        self.ai_base.setText("https://dashscope.aliyuncs.com/api/v1")
        self.ai_cmodel.setText("qwen-plus")
        self.ai_cvision.setText("qwen-vl-max")
        self._save_ai()

    def refresh(self) -> None:
        """从配置重新读一遍，避免向导改完这里还显示旧值。"""
        self.dark.setChecked(bool(CFG.get("general.dark_mode", False)))
        self.autostart.setChecked(autostart_enabled())
        self.pet_on.setChecked(bool(CFG.get("fish.pet_on", True)))
        self.pet_size.setValue(int(CFG.get("fish.size", 150) or 150))
        self.ai_provider.setCurrentIndex(
            1 if CFG.get("ai.provider", "deepseek") == "custom" else 0)
        self.ai_key.setText(CFG.get("ai.key", ""))
        self.ai_base.setText(CFG.get("ai.custom_base", ""))
        self.ai_ckey.setText(CFG.get("ai.custom_key", ""))
        self.ai_cmodel.setText(CFG.get("ai.custom_model", ""))
        self.ai_cvision.setText(CFG.get("ai.custom_vision", ""))
        self.think_model.setText(CFG.get("ai.think_model", ""))
        cur = CFG.get("fish.img_proto", "dashscope")
        self.img_proto.setCurrentIndex(max(0, self.img_proto.findData(cur)))
        self.img_url.setText(CFG.get("fish.img_url", ""))
        self.img_key.setText(CFG.get("fish.img_key", ""))
        self.img_model.setText(CFG.get("fish.img_model", ""))
        self.img_models.setText(CFG.get("fish.img_models", ""))
        self._sync_ai_boxes()

    def _sync_ai_boxes(self) -> None:
        custom = self.ai_provider.currentIndex() == 1
        self.ds_box.setVisible(not custom)
        self.custom_box.setVisible(custom)

    def _pet_size_changed(self, v: int) -> None:
        self.pet_size_lb.setText(f"{int(v)} px")
        CFG.set("fish.size", int(v))
        CFG.save()
        self.app.pet_resize()

    def _fill_aliyun(self) -> None:
        self.img_proto.setCurrentIndex(max(0, self.img_proto.findData("dashscope")))
        self.img_url.setText(
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/"
            "multimodal-generation/generation")
        self.img_model.setText("wan2.6-t2i")
        self.img_models.setText("wan2.5-t2i-preview,wanx2.1-t2i-turbo")
        self._save_image()
        common.toast(self.app, "已填入阿里云地址和模型，贴 Key 即可", "ok")

    def _save_image(self, *_a) -> None:
        CFG.set("fish.img_proto", self.img_proto.currentData())
        CFG.set("fish.img_url", self.img_url.text().strip())
        CFG.set("fish.img_key", self.img_key.text().strip())
        CFG.set("fish.img_model", self.img_model.text().strip())
        CFG.set("fish.img_models", self.img_models.text().strip())
        CFG.save()

    def _test_image(self) -> None:
        self._save_image()
        self.img_state.setText("生成中…")
        from .common import run_bg

        def work(_e):
            from .. import imaging
            return imaging.generate("一只蓝白配色、鲸鱼耳朵的可爱少女，柔和光线")

        def done(png):
            self.img_state.setText(f"可用 ✔（{len(png) // 1024} KB）" if png
                                   else "生成失败")

        def fail(e):
            self.img_state.setText(f"失败：{e}")

        run_bg(work, done, fail)

    def _save_ai(self, *_a) -> None:
        self._sync_ai_boxes()
        CFG.set("ai.provider",
                "custom" if self.ai_provider.currentIndex() == 1 else "deepseek")
        CFG.set("ai.key", self.ai_key.text().strip())
        CFG.set("ai.custom_base", self.ai_base.text().strip())
        CFG.set("ai.custom_key", self.ai_ckey.text().strip())
        CFG.set("ai.custom_model", self.ai_cmodel.text().strip())
        CFG.set("ai.custom_vision", self.ai_cvision.text().strip())
        CFG.set("ai.think_model", self.think_model.text().strip())
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
