"""首次配置向导：账号、AI、文生图、角色、行为，一次配完。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from ..config import CFG, DEFAULTS
from . import common


class Wizard(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.setWindowTitle("大肥鱼配置向导")
        self.resize(820, 680)
        lay = QVBoxLayout(self)
        title = QLabel("一次把账号、AI、形象、行为配好，然后启用")
        title.setStyleSheet("font-size:17px;font-weight:700;")
        lay.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._accounts(), "1 账号")
        tabs.addTab(self._ai(), "2 AI")
        tabs.addTab(self._image(), "3 文生图")
        tabs.addTab(self._role(), "4 角色")
        tabs.addTab(self._behaviour(), "5 行为")
        lay.addWidget(tabs, 1)

        self.hint = QLabel("")
        self.hint.setObjectName("muted")
        lay.addWidget(self.hint)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(common.button("稍后再说", ghost=True, on_click=self._later))
        row.addWidget(common.button("保存", ghost=True, on_click=self._save_only))
        row.addWidget(common.button("保存并启用", primary=True, on_click=self._finish))
        lay.addLayout(row)
        self._load()

    # ---------- 页面 ----------
    def _accounts(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        self.hlx_state = QLabel("—")
        self.lj_state = QLabel("—")
        f.addRow("葫芦侠状态", self.hlx_state)
        f.addRow("灵芥状态", self.lj_state)
        self.hlx_user = QLineEdit()
        self.hlx_user.setPlaceholderText("葫芦侠账号 / 手机号")
        self.hlx_pwd = QLineEdit()
        self.hlx_pwd.setEchoMode(QLineEdit.Password)
        self.hlx_pwd.setPlaceholderText("密码")
        self.lj_user = QLineEdit()
        self.lj_user.setPlaceholderText("灵芥手机号")
        self.lj_pwd = QLineEdit()
        self.lj_pwd.setEchoMode(QLineEdit.Password)
        self.lj_pwd.setPlaceholderText("密码")
        f.addRow("葫芦侠登录", self.hlx_user)
        f.addRow("", self.hlx_pwd)
        f.addRow("", common.button("登录葫芦侠", primary=True,
                                   on_click=lambda: self._login("hlx")))
        f.addRow("灵芥登录", self.lj_user)
        f.addRow("", self.lj_pwd)
        f.addRow("", common.button("登录灵芥", primary=True,
                                   on_click=lambda: self._login("lingjie")))
        f.addRow("", QLabel("只登录一个平台也可以；另一个留空即可。"))
        self.owner_hlx = QLineEdit()
        self.owner_lj = QLineEdit()
        get_btn = common.button("从粉丝获取", ghost=True,
                                on_click=self._owner_from_fans)
        row = QHBoxLayout()
        row.addWidget(self.owner_hlx, 1)
        row.addWidget(get_btn)
        f.addRow("葫芦侠主人 uid", row)
        f.addRow("灵芥主人 uid", self.owner_lj)
        f.addRow("", QLabel("两个社区是同一个主人时，只填一个会自动沿用。"))
        return w

    def _ai(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        self.ai_key = QLineEdit()
        self.ai_key.setEchoMode(QLineEdit.Password)
        self.ai_model = QLineEdit()
        self.ai_vision = QLineEdit()
        f.addRow("API Key", self.ai_key)
        f.addRow("日常对话模型", self.ai_model)
        f.addRow("看图模型", self.ai_vision)
        f.addRow("", QLabel(
            "1）打开 platform.deepseek.com，注册后在「API Keys」创建 Key；\n"
            "2）日常用 deepseek-chat 这种便宜模型即可；\n"
            "3）看图时自动换「看图模型」，留空则用日常模型；\n"
            "4）Key 不填，大肥鱼不会说话。"))
        return w

    def _image(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        self.img_proto = QComboBox()
        self.img_proto.addItems(["dashscope", "openai", "sd"])
        self.img_url = QLineEdit()
        self.img_key = QLineEdit()
        self.img_key.setEchoMode(QLineEdit.Password)
        self.img_model = QLineEdit()
        self.img_models = QLineEdit()
        preset = common.button("一键填入阿里云（百炼）", primary=True,
                               on_click=self._fill_aliyun)
        f.addRow("", preset)
        f.addRow("协议", self.img_proto)
        f.addRow("接口地址", self.img_url)
        f.addRow("Key", self.img_key)
        f.addRow("当前模型", self.img_model)
        f.addRow("备用模型", self.img_models)
        f.addRow("", QLabel(
            "阿里云教程：\n"
            "1）打开 bailian.console.aliyun.com，登录后开通「百炼」；\n"
            "2）右上角「API-KEY」→ 创建，复制 sk- 开头的 Key；\n"
            "3）把 Key 填到上面，接口地址留空即可；\n"
            "4）模型默认 wan2.6-t2i，额度用完自动换备用。\n"
            "不配也能用，只是发帖不带图。"))
        return w

    def _role(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        self.name_edit = QLineEdit()
        self.tags_edit = QLineEdit()
        self.appear_edit = QPlainTextEdit()
        self.appear_edit.setMinimumHeight(110)
        self.persona_edit = QPlainTextEdit()
        self.persona_edit.setMinimumHeight(120)
        f.addRow("名字", self.name_edit)
        f.addRow("标签", self.tags_edit)
        f.addRow("形象（配图）", self.appear_edit)
        f.addRow("人设（说话风格）", self.persona_edit)
        f.addRow("", QLabel("形象会原样写进文生图提示词；人设留空用默认。"))
        return w

    def _behaviour(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        self.interval = QSpinBox()
        self.interval.setRange(5, 360)
        self.interval.setSuffix(" 分钟")
        self.limit_hlx = QSpinBox()
        self.limit_hlx.setRange(1, 10)
        self.limit_lj = QSpinBox()
        self.limit_lj.setRange(1, 10)
        self.max_reply = QSpinBox()
        self.max_reply.setRange(1, 10)
        f.addRow("自由行动间隔", self.interval)
        f.addRow("葫芦侠每天发帖", self.limit_hlx)
        f.addRow("灵芥每天发帖", self.limit_lj)
        f.addRow("每轮最多回复", self.max_reply)
        perms = QHBoxLayout()
        self.perm_boxes = {}
        for key, label in (("like", "点赞"), ("favorite", "收藏"),
                           ("comment", "评论"), ("follow", "关注"),
                           ("tip", "送葫芦/芥子"), ("post", "发帖"),
                           ("signin", "签到"), ("roam", "逛社区"),
                           ("reply", "回复")):
            cb = QCheckBox(label)
            self.perm_boxes[key] = cb
            perms.addWidget(cb)
        f.addRow("允许的动作", perms)
        return w

    # ---------- 数据 ----------
    def _load(self) -> None:
        cfg = CFG
        self.hlx_state.setText(
            f"已登录：{cfg.get('hlx.nick') or cfg.get('hlx.uid')}" if cfg.get("hlx.key")
            else "未登录")
        self.lj_state.setText(
            f"已登录：{cfg.get('lingjie.nickname') or cfg.get('lingjie.uid')}"
            if cfg.get("lingjie.token") else "未登录")
        self.owner_hlx.setText(str(cfg.get("fish.owner_uid_hlx", 0) or ""))
        self.owner_lj.setText(str(cfg.get("fish.owner_uid_lingjie", 0) or ""))
        self.ai_key.setText(cfg.get("ai.key", ""))
        self.ai_model.setText(cfg.get("ai.model_basic", "") or DEFAULTS["ai"]["model_basic"])
        self.ai_vision.setText(cfg.get("ai.model_vision", "") or cfg.get("ai.model_basic", ""))
        self.img_proto.setCurrentText(cfg.get("fish.img_proto", "dashscope"))
        self.img_url.setText(cfg.get("fish.img_url", ""))
        self.img_key.setText(cfg.get("fish.img_key", ""))
        self.img_model.setText(cfg.get("fish.img_model", ""))
        self.img_models.setText(cfg.get("fish.img_models", ""))
        self.name_edit.setText(cfg.get("fish.name", "大肥鱼"))
        self.tags_edit.setText(cfg.get("fish.tags", ""))
        self.appear_edit.setPlainText(cfg.get("fish.appearance", ""))
        from ..persona import DEFAULT_PERSONA
        self.persona_edit.setPlainText(cfg.get("fish.persona", "") or DEFAULT_PERSONA)
        self.interval.setValue(int(cfg.get("fish.interval_min", 20) or 20))
        self.limit_hlx.setValue(int(cfg.get("autopost.daily_limit_hlx", 2) or 2))
        self.limit_lj.setValue(int(cfg.get("autopost.daily_limit_lingjie", 2) or 2))
        self.max_reply.setValue(int(cfg.get("auto.max_per_pass", 3) or 3))
        for k, cb in self.perm_boxes.items():
            cb.setChecked(bool(cfg.get(f"perm.{k}", k != "tip")))

    def _save(self) -> None:
        cfg = CFG
        cfg.set("fish.owner_uid_hlx", int(self.owner_hlx.text() or 0))
        cfg.set("fish.owner_uid_lingjie", int(self.owner_lj.text() or 0))
        cfg.set("ai.key", self.ai_key.text().strip())
        cfg.set("ai.model_basic", self.ai_model.text().strip())
        cfg.set("ai.model_vision", self.ai_vision.text().strip())
        cfg.set("fish.img_proto", self.img_proto.currentText())
        cfg.set("fish.img_url", self.img_url.text().strip())
        cfg.set("fish.img_key", self.img_key.text().strip())
        cfg.set("fish.img_model", self.img_model.text().strip())
        cfg.set("fish.img_models", self.img_models.text().strip())
        cfg.set("fish.name", self.name_edit.text().strip() or "大肥鱼")
        cfg.set("fish.tags", self.tags_edit.text().strip())
        cfg.set("fish.appearance", self.appear_edit.toPlainText().strip())
        cfg.set("fish.persona", self.persona_edit.toPlainText().strip())
        cfg.set("fish.interval_min", self.interval.value())
        cfg.set("autopost.daily_limit_hlx", self.limit_hlx.value())
        cfg.set("autopost.daily_limit_lingjie", self.limit_lj.value())
        cfg.set("auto.max_per_pass", self.max_reply.value())
        for k, cb in self.perm_boxes.items():
            cfg.set(f"perm.{k}", cb.isChecked())
        cfg.set("general.first_run", False)
        cfg.save()
        self.app.pages["home"].refresh()

    # ---------- 动作 ----------
    def _fill_aliyun(self) -> None:
        self.img_proto.setCurrentText("dashscope")
        self.img_url.setText("")
        self.img_model.setText("wan2.6-t2i")
        self.img_models.setText("wan2.5-t2i-preview,wanx2.1-t2i-turbo")

    def _login(self, platform: str) -> None:
        if platform == "hlx":
            user, pwd = self.hlx_user.text().strip(), self.hlx_pwd.text()
        else:
            user, pwd = self.lj_user.text().strip(), self.lj_pwd.text()
        if not user or not pwd:
            common.toast(self.app, "先填账号和密码", "warn")
            return
        from .common import run_bg

        def work(_e):
            if platform == "hlx":
                self.app.hlx.login(user, pwd)   # 成功会自己写 config，失败抛异常
            else:
                self.app.lj.login_password(user, pwd)
                info = self.app.lj.me()
                CFG.set("lingjie.uid", int(info.get("uid", 0) or 0))
                CFG.set("lingjie.nickname", info.get("nickname", ""))
                CFG.set("lingjie.level", int(info.get("currentLv", 0) or 0))
            CFG.save()
            return True

        def done(_ok):
            common.toast(self.app, "登录成功", "ok")
            self._load()
            self.app.notify_accounts()

        def fail(e):
            common.toast(self.app, f"登录失败：{e}", "error")

        run_bg(work, done, fail)

    def _owner_from_fans(self) -> None:
        if not CFG.get("hlx.key", ""):
            common.toast(self.app, "先登录葫芦侠", "warn")
            return
        from .common import run_bg

        def work(_e):
            return self.app.hlx.followers(30)

        def done(fans):
            if not fans:
                common.toast(self.app, "没有拿到粉丝列表", "warn")
                return
            first = fans[0]
            u = first.get("user") or first
            uid = int(u.get("userID", 0) or 0)
            nick = u.get("nick", "")
            if uid:
                self.owner_hlx.setText(str(uid))
                common.toast(self.app, f"已填入 {nick or uid}，可手动改", "ok")

        run_bg(work, done, lambda e: common.toast(self.app, f"获取失败：{e}", "error"))

    def _go(self, platform: str) -> None:
        self.app.show_page(platform)
        self.accept()

    def _later(self) -> None:
        CFG.set("general.first_run", False)
        CFG.save()
        self.accept()

    def _save_only(self) -> None:
        self._save()
        common.toast(self.app, "已保存", "ok")
        self.accept()

    def _finish(self) -> None:
        self._save()
        home = self.app.pages.get("home")
        miss = home.missing_items() if home else []
        if miss:
            self.hint.setText("还差：" + "、".join(miss))
            common.toast(self.app, "还差：" + "、".join(miss), "warn")
            return
        CFG.set("fish.enabled", True)
        CFG.save()
        self.app.autopilot.start()
        common.toast(self.app, "配置完成，大肥鱼已启用", "ok")
        self.accept()
