"""配置向导：分步完成账号、AI、文生图、角色、行为。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from ..config import CFG, DEFAULTS
from . import common

ALIYUN_IMG_URL = ("https://dashscope.aliyuncs.com/api/v1/services/aigc/"
                  "multimodal-generation/generation")


class Wizard(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.step = 0
        self.ai_ok = False
        self.img_ok = False
        self.setWindowTitle("大肥鱼配置向导")
        self.resize(840, 700)
        lay = QVBoxLayout(self)

        self.title = QLabel("")
        self.title.setStyleSheet("font-size:17px;font-weight:700;")
        lay.addWidget(self.title)

        self.tabs = QTabWidget()
        self.tabs.tabBar().hide()
        self.tabs.addTab(self._accounts(), "1 账号")
        self.tabs.addTab(self._ai(), "2 AI")
        self.tabs.addTab(self._image(), "3 文生图")
        self.tabs.addTab(self._role(), "4 角色")
        self.tabs.addTab(self._behaviour(), "5 行为")
        lay.addWidget(self.tabs, 1)

        self.hint = QLabel("")
        self.hint.setObjectName("muted")
        lay.addWidget(self.hint)

        row = QHBoxLayout()
        row.addWidget(common.button("稍后再说", ghost=True, on_click=self._later))
        row.addStretch(1)
        self.back_btn = common.button("上一步", ghost=True, on_click=self._back)
        self.next_btn = common.button("下一步", primary=True, on_click=self._next)
        self.finish_btn = common.button("完成并启用", primary=True,
                                        on_click=self._finish)
        row.addWidget(self.back_btn)
        row.addWidget(self.next_btn)
        row.addWidget(self.finish_btn)
        lay.addLayout(row)

        self._load()
        self._sync()

    # ---------- 页面 ----------
    def _accounts(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        self.hlx_state = QLabel("—")
        self.lj_state = QLabel("—")
        f.addRow("葫芦侠", self.hlx_state)
        f.addRow("灵芥", self.lj_state)
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
        f.addRow(self.hlx_user)
        f.addRow(self.hlx_pwd)
        f.addRow(common.button("登录葫芦侠", primary=True,
                               on_click=lambda: self._login("hlx")))
        f.addRow(self.lj_user)
        f.addRow(self.lj_pwd)
        f.addRow(common.button("登录灵芥", primary=True,
                               on_click=lambda: self._login("lingjie")))
        f.addRow("", QLabel("只登录一个平台也可以；另一个留空。"))
        self.owner_hlx = QLineEdit()
        self.owner_lj = QLineEdit()
        get_btn = common.button("从粉丝获取", ghost=True,
                                on_click=self._owner_from_fans)
        r = QHBoxLayout()
        r.addWidget(self.owner_hlx, 1)
        r.addWidget(get_btn)
        f.addRow("葫芦侠主人 uid", r)
        f.addRow("灵芥主人 uid", self.owner_lj)
        return w

    def _ai(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        self.ai_provider = QComboBox()
        self.ai_provider.addItem("DeepSeek 官方（只填 Key）", "deepseek")
        self.ai_provider.addItem("自定义（OpenAI 兼容）", "custom")
        self.ai_provider.currentIndexChanged.connect(self._sync_ai)
        f.addRow("使用", self.ai_provider)

        self.ds_box = QWidget()
        dsl = QVBoxLayout(self.ds_box)
        dsl.setContentsMargins(0, 0, 0, 0)
        self.ai_key = QLineEdit()
        self.ai_key.setEchoMode(QLineEdit.Password)
        self.ai_key.setPlaceholderText("DeepSeek API Key（sk-...）")
        dsl.addWidget(self.ai_key)
        f.addRow(self.ds_box)

        self.custom_box = QWidget()
        cbl = QVBoxLayout(self.custom_box)
        cbl.setContentsMargins(0, 0, 0, 0)
        self.ai_base = QLineEdit()
        self.ai_base.setPlaceholderText("https://dashscope.aliyuncs.com/api/v1")
        cbl.addWidget(self.ai_base)
        row2 = QHBoxLayout()
        self.ai_ckey = QLineEdit()
        self.ai_ckey.setEchoMode(QLineEdit.Password)
        self.ai_ckey.setPlaceholderText("API Key")
        row2.addWidget(self.ai_ckey, 1)
        self.ai_cmodel = QLineEdit()
        self.ai_cmodel.setPlaceholderText("模型名，如 qwen-plus")
        row2.addWidget(self.ai_cmodel, 1)
        self.ai_cvision = QLineEdit()
        self.ai_cvision.setPlaceholderText("看图模型，如 qwen-vl-max")
        row2.addWidget(self.ai_cvision, 1)
        cbl.addLayout(row2)
        cbl.addWidget(common.button("一键填入阿里云", ghost=True,
                                    on_click=self._fill_ai_aliyun))
        f.addRow(self.custom_box)

        test = common.button("测试 Key 是否可用", on_click=self._test_ai)
        self.ai_state = QLabel("未测试")
        self.ai_state.setObjectName("muted")
        r = QHBoxLayout()
        r.addWidget(test)
        r.addWidget(self.ai_state, 1)
        f.addRow("", r)
        f.addRow("", QLabel(
            "1）DeepSeek：打开 platform.deepseek.com → API Keys → 创建，只填 Key；\n"
            "2）自定义：填 OpenAI 兼容地址/Key/模型；阿里云一键会填\n"
            "   https://dashscope.aliyuncs.com/api/v1\n"
            "3）必须测试通过才能下一步。"))
        return w

    def _sync_ai(self, *_a) -> None:
        custom = self.ai_provider.currentData() == "custom"
        self.ds_box.setVisible(not custom)
        self.custom_box.setVisible(custom)

    def _fill_ai_aliyun(self) -> None:
        self.ai_base.setText("https://dashscope.aliyuncs.com/api/v1")
        self.ai_cmodel.setText("qwen-plus")
        self.ai_cvision.setText("qwen-vl-max")

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
        f.addRow("", common.button("一键填入阿里云（百炼）", primary=True,
                                   on_click=self._fill_aliyun))
        self.img_state = QLabel("未测试（不配也能用）")
        self.img_state.setObjectName("muted")
        row = QHBoxLayout()
        row.addWidget(common.button("测试文生图", on_click=self._test_image))
        row.addWidget(self.img_state, 1)
        f.addRow("", row)
        f.addRow("协议", self.img_proto)
        f.addRow("接口地址", self.img_url)
        f.addRow("Key", self.img_key)
        f.addRow("当前模型", self.img_model)
        f.addRow("备用模型", self.img_models)
        f.addRow("", QLabel(
            "阿里云教程：\n"
            "1）打开 bailian.console.aliyun.com，开通「百炼」；\n"
            "2）右上角「API-KEY」→ 创建，复制 sk- 开头的 Key；\n"
            "3）点「一键填入阿里云」会把地址和模型都填好，只需贴 Key；\n"
            "4）模型额度用完会自动换备用。不配也能用，只是不带图。"))
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
        prov = "custom" if cfg.get("ai.provider", "deepseek") == "custom" else "deepseek"
        self.ai_provider.setCurrentIndex(1 if prov == "custom" else 0)
        self.ai_base.setText(cfg.get("ai.custom_base", "") or
                             "https://dashscope.aliyuncs.com/api/v1")
        self.ai_ckey.setText(cfg.get("ai.custom_key", ""))
        self.ai_cmodel.setText(cfg.get("ai.custom_model", "") or "qwen-plus")
        self.ai_cvision.setText(cfg.get("ai.custom_vision", "") or "qwen-vl-max")
        self._sync_ai()
        self.img_proto.setCurrentText(cfg.get("fish.img_proto", "dashscope"))
        self.img_url.setText(cfg.get("fish.img_url", "") or ALIYUN_IMG_URL)
        self.img_key.setText(cfg.get("fish.img_key", ""))
        self.img_model.setText(cfg.get("fish.img_model", "") or "wan2.6-t2i")
        self.img_models.setText(cfg.get("fish.img_models", ""))
        self.name_edit.setText(cfg.get("fish.name", "大肥鱼"))
        self.tags_edit.setText(cfg.get("fish.tags", ""))
        self.appear_edit.setPlainText(cfg.get("fish.appearance", ""))
        from .. import brain as _brain
        self.persona_edit.setPlainText(_brain.persona_template())
        self.interval.setValue(int(cfg.get("fish.interval_min", 20) or 20))
        self.limit_hlx.setValue(int(cfg.get("autopost.daily_limit_hlx", 2) or 2))
        self.limit_lj.setValue(int(cfg.get("autopost.daily_limit_lingjie", 2) or 2))
        self.max_reply.setValue(int(cfg.get("auto.max_per_pass", 3) or 3))
        for k, cb in self.perm_boxes.items():
            cb.setChecked(bool(cfg.get(f"perm.{k}", k != "tip")))
        if cfg.get("ai.key"):
            self.ai_state.setText("已填写，建议测试一次")

    def _save(self) -> None:
        cfg = CFG
        cfg.set("fish.owner_uid_hlx", int(self.owner_hlx.text() or 0))
        cfg.set("fish.owner_uid_lingjie", int(self.owner_lj.text() or 0))
        cfg.set("ai.provider",
                "custom" if self.ai_provider.currentData() == "custom" else "deepseek")
        cfg.set("ai.key", self.ai_key.text().strip())
        cfg.set("ai.custom_base", self.ai_base.text().strip())
        cfg.set("ai.custom_key", self.ai_ckey.text().strip())
        cfg.set("ai.custom_model", self.ai_cmodel.text().strip())
        cfg.set("ai.custom_vision", self.ai_cvision.text().strip())
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

    # ---------- 步骤 ----------
    def _sync(self) -> None:
        titles = ["1 / 5　登录账号", "2 / 5　AI 配置", "3 / 5　文生图（可选）",
                  "4 / 5　角色", "5 / 5　行为"]
        self.title.setText(titles[self.step])
        self.back_btn.setVisible(self.step > 0)
        self.next_btn.setVisible(self.step < 4)
        self.finish_btn.setVisible(self.step == 4)
        if self.step == 4:
            ok = self._ready()
            self.finish_btn.setEnabled(ok)
            self.hint.setText("" if ok else "还差：" + "、".join(self._missing()))
        else:
            self.hint.setText("")

    def _logged(self) -> list[str]:
        out = []
        if CFG.get("hlx.key", ""):
            out.append("葫芦侠")
        if CFG.get("lingjie.token", ""):
            out.append("灵芥")
        return out

    def _missing(self) -> list[str]:
        miss = []
        if not self._logged():
            miss.append("至少登录一个平台")
        if not self.ai_ok:
            miss.append("AI 接口未测试通过")
        if not self.img_ok:
            miss.append("文生图未测试通过")
        return miss

    def _ready(self) -> bool:
        return not self._missing()

    def _next(self) -> None:
        if self.step == 0 and not self._logged():
            common.toast(self.app, "先登录至少一个平台", "warn")
            return
        if self.step == 1 and not self.ai_ok:
            common.toast(self.app, "先点「测试 Key」并通过", "warn")
            return
        if self.step == 2 and not self.img_ok:
            common.toast(self.app, "文生图测试通过后才能下一步", "warn")
            return
        self._save()
        self.step = min(4, self.step + 1)
        self.tabs.setCurrentIndex(self.step)
        self._sync()

    def _back(self) -> None:
        self.step = max(0, self.step - 1)
        self.tabs.setCurrentIndex(self.step)
        self._sync()

    # ---------- 动作 ----------
    def _test_ai(self) -> None:
        self._save()
        custom = self.ai_provider.currentData() == "custom"
        key = (self.ai_ckey.text() if custom else self.ai_key.text()).strip()
        if not key:
            common.toast(self.app, "先填 API Key", "warn")
            return
        self.ai_state.setText("测试中…")
        self.ai_ok = False
        from .common import run_bg

        def work(_e):
            from .. import ai
            return ai.ask("只回复两个字：可用", "测试")

        def done(_t):
            self.ai_ok = True
            self.ai_state.setText("可用 ✔")
            common.toast(self.app, "Key 可用", "ok")

        def fail(e):
            self.ai_ok = False
            self.ai_state.setText("不可用")
            common.toast(self.app, f"不可用：{e}", "error")

        run_bg(work, done, fail)

    def _fill_aliyun(self) -> None:
        self.img_proto.setCurrentText("dashscope")
        self.img_url.setText(ALIYUN_IMG_URL)
        self.img_model.setText("wan2.6-t2i")
        self.img_models.setText("wan2.5-t2i-preview,wanx2.1-t2i-turbo")

    def _test_image(self) -> None:
        if not self.img_key.text().strip():
            common.toast(self.app, "先填文生图 Key", "warn")
            return
        self._save()
        models = [self.img_model.text().strip()] + [
            m.strip() for m in self.img_models.text().split(",") if m.strip()]
        models = [m for i, m in enumerate(models) if m and m not in models[:i]]
        self.img_state.setText("生成中…")
        self.img_ok = False
        from .common import run_bg

        def work(_e):
            from .. import imaging
            last = ""
            for m in models:
                CFG.set("fish.img_model", m)
                CFG.save()
                try:
                    png = imaging.generate(
                        "一只蓝白配色、鲸鱼耳朵的可爱少女，坐在窗边，柔和光线")
                except Exception as e:
                    last = str(e)
                    continue
                if png:
                    return m, png
                last = "空结果"
            raise RuntimeError(last or "全部模型失败")

        def done(res):
            m, png = res
            self.img_ok = True
            self.img_model.setText(m)
            CFG.set("fish.img_model", m)
            CFG.save()
            self.img_state.setText(f"{m} 可用 ✔（{len(png) // 1024} KB）")
            common.toast(self.app, f"文生图可用：{m}", "ok")

        def fail(e):
            self.img_ok = False
            self.img_state.setText("全部失败")
            common.toast(self.app, f"文生图不可用：{e}", "error")

        run_bg(work, done, fail)

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
                self.app.hlx.login(user, pwd)
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
            self._sync()
            self.app.notify_accounts()

        def fail(e):
            common.toast(self.app, f"登录失败：{e}", "error")

        run_bg(work, done, fail)

    def _owner_from_fans(self) -> None:
        if not CFG.get("hlx.key", ""):
            common.toast(self.app, "先登录葫芦侠", "warn")
            return
        from .common import run_bg
        from PySide6.QtWidgets import (QDialog, QListWidget, QListWidgetItem,
                                       QVBoxLayout as _VBox)

        def work(_e):
            return self.app.hlx.followers(100)

        def done(fans):
            if not fans:
                common.toast(self.app, "没拿到粉丝列表", "warn")
                return
            dlg = QDialog(self)
            dlg.setWindowTitle("选择主人（粉丝列表）")
            dlg.resize(420, 520)
            v = _VBox(dlg)
            lst = QListWidget()
            try:
                from . import common as _common
                _common.dark_viewport(lst)
            except Exception:
                pass
            rows = []
            for f in fans:
                u = f.get("user") or f
                uid = int(u.get("userID", 0) or 0)
                nick = u.get("nick") or f"uid={uid}"
                rows.append((uid, nick))
                it = QListWidgetItem(f"{nick}　（uid={uid}）")
                it.setData(Qt.UserRole, uid)
                lst.addItem(it)
            v.addWidget(lst)

            def choose() -> None:
                it = lst.currentItem()
                if not it:
                    return
                uid = int(it.data(Qt.UserRole) or 0)
                if uid:
                    self.owner_hlx.setText(str(uid))
                    dlg.accept()

            lst.itemDoubleClicked.connect(lambda _i: choose())
            v.addWidget(common.button("用这个当主人", primary=True, on_click=choose))
            lst.setCurrentRow(0)
            dlg.exec()

        run_bg(work, done, lambda e: common.toast(self.app, f"获取失败：{e}", "error"))

    def _later(self) -> None:
        CFG.set("general.first_run", False)
        CFG.save()
        self.accept()

    def _finish(self) -> None:
        self._save()
        if not self._ready():
            self.hint.setText("还差：" + "、".join(self._missing()))
            return
        CFG.set("fish.enabled", True)
        CFG.set("auto.enabled", True)
        CFG.save()
        self.app.autopilot.start()
        common.toast(self.app, "配置完成，大肥鱼已启用", "ok")
        self.accept()
