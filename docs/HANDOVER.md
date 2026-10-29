# 接管说明（HANDOVER）

> 版本 **v3.3** · 2026-10-29 · Windows 10/11 x64
> 仓库：<https://gitee.com/guo-wenlong/halo-desk>（私有）
> 前身：hlx-halo（葫芦侠三楼）+ lingjie-halo（灵芥空间），两个 Android 项目合并移植为 Windows 桌面程序。

---

## 1. 一句话架构

**模型只做决策，代码负责执行。**
模型从固定动作清单里选一个 `action` + `target`，返回 JSON；
代码解析目标、调用对应社区接口、记录结果与理由到「动态」。

---

## 2. 目录

```
HaloDesk/
├─ HaloDesk.exe            单文件程序（PyInstaller onefile）
├─ data/                   运行时数据（与 exe 同级，便携）
└─ docs/                   HANDOVER / PROMPTS / CHANGELOG / 示例

halo-desktop/              源码
├─ main.py                 入口（--selftest 自检）
├─ app/                    业务代码
├─ assets/                 图标、角色图
├─ tools/                  测试与文档生成
├─ docs/                   文档
└─ HaloDesk.spec           PyInstaller 配置
```

`data_dir()` 选择顺序：`HALODESK_HOME` → `exe 同级/data` → `%APPDATA%/HaloDesk`
→ `~/.halodesk` → `cwd/halodesk-data`，保证任何环境都能落盘。

---

## 3. 模块地图

| 文件 | 职责 |
|---|---|
| `config.py` | 配置读写、数据目录选择 |
| `net.py` | HTTP、编码/签名、JSON 容错提取 |
| `hlx.py` | 葫芦侠客户端（登录/板块/帖子/评论/点赞/收藏/关注/打赏/签到/通知/审核/上传/搜索/用户信息） |
| `lingjie.py` | 灵芥客户端（同上 + 七牛上传 + 表情 + 收藏列表 + 打赏） |
| `ai.py` | LLM 调用（含视觉） |
| `brain.py` | 系统提示词拼装、看帖/意图/分层决策 |
| `capabilities.py` | **动作白名单 + 目标解析 + 执行器**（15 种帖子组合 + 独立动作） |
| `roam.py` | 逛社区：社区→板块→看几条→逐帖→换板块/换社区 |
| `automation.py` | 定时器：消息轮询、自由行动、发帖、日记、生活记忆、审核检查 |
| `autopost.py` / `publishing.py` | 生成草稿、配图、发布、审核判定、额度计数 |
| `imaging.py` | 文生图三协议，模型失败自动轮换 |
| `memory.py` | 通用/生活/用户记忆、超字数压缩、心情 |
| `names.py` | uid → 昵称索引（用户记忆显示名字） |
| `emoji.py` | 两平台独立表情白名单 + 发送前过滤 |
| `relations.py` / `stats.py` / `activity.py` / `debuglog.py` | 好感度 / 统计 / 动态 / 日志 |
| `diary.py` | 生活记忆生成、每日日记 |
| `boards.py` | 发帖板块（葫芦侠=泳池，灵芥=闲聊） |
| `ui/` | 总览、两平台、大肥鱼、记忆、动态、自动任务、调试、设置 |

---

## 4. 五条核心流程

### 4.1 消息监听（10 秒）
拉两平台通知 → 过滤（接入时间之后、未回复、服务端二次校验）→
模型返回 `{reply, action, target}` → 执行动作 → 随机等 0–15 秒 → 回复 → 记动态。

灵芥注意：`notification_type=at_comment` 是 @ 我，正文里有 `<at uid="..">@名字</at>`。

### 4.2 自由行动（每 `fish.interval_min` 分钟）
模型选 `roam / post / signin / idle`。
发帖时按「平台额度 + 最小间隔 + 24h 均分」挑平台；没到点就跳过并写理由。

### 4.3 逛社区
社区 → 板块 → 看几条 → 每帖决策 → 换板块/换社区。
已评论过的帖子直接跳过（本地 + 服务端双查）。

### 4.4 发帖
写标题正文 → 需要时按生活记忆生成配图 → 上传 → 发布 →
2 秒后查「我的帖子」判断是否审核中 → 记动态、计数。

### 4.5 记忆
- 通用 1500 字 / 用户 800 字 / 生活 1200 字，超限让模型总结成关键节点；
- 只有**别人主动找你**（评论/回复/@）才写用户记忆；
- 自己的评论、点赞、关注只进动态和好感度。

---

## 5. 配置要点（`data/config.json`）

| 键 | 说明 |
|---|---|
| `hlx.key` / `lingjie.token` | 登录态 |
| `ai.key` / `ai.model*` | LLM |
| `fish.owner_uid_hlx` / `_lingjie` | 两平台各自主人 |
| `fish.interval_min` | 自由行动间隔 |
| `fish.memory_max` / `user_mem_max` / `life_max` | 记忆压缩阈值 |
| `fish.img_model` / `img_models` | 文生图模型与轮换列表 |
| `auto.poll_sec` / `max_per_pass` | 消息轮询秒数 / 每轮最多回几条 |
| `autopost.daily_limit_hlx` / `_lingjie` / `min_gap_min` | 各平台每日额度与最小间隔 |
| `autopost.diary_enabled` / `diary_time` | 日记（默认 22:00，不占额度） |
| `perm.*` | 各动作开关 |

---

## 6. 接口坑位

| 事项 | 说明 |
|---|---|
| 葫芦侠签名 | `_key` + md5(SECRET)，GET 大写、POST 小写 |
| 灵芥鉴权 | `Authorization: Bearer <token>` |
| 灵芥帖子 id | `themeId` / `tid`；葫芦侠 `postID` |
| 灵芥时间 | `create_time` 是「11分钟前」，需转时间戳 |
| 灵芥上传 | `/upload/token` 的 `uploadHost` 优先，失败退 `up-z0.qiniup.com` |
| 葫芦侠审核 | `type_id=1` 通知「您的评论已审核通过/未通过」 |
| 评论可见性 | 发完复查，看不到标「审核中」 |
| 表情 | 葫芦侠 21 个来自源码常量；灵芥 160 个来自 `/emoji/list`，发送前过滤 |

---

## 7. 构建与测试

```powershell
pyinstaller --noconfirm --clean --onefile --windowed --name HaloDesk `
  --icon assets\icon.ico --add-data "assets;assets" --runtime-tmpdir "." main.py
```

```powershell
python tools\simulate_local.py   # 本地仿真（零网络）
python tools\verify_real.py      # 真实接口（写操作拦截）
python tools\ui_test.py          # 界面
python tools\gen_prompt_docs.py  # 生成 PROMPTS.md / prompts.json
```

`--runtime-tmpdir "."` 必须保留（否则受限环境报临时目录错误）。

---

## 8. 已知限制

1. 灵芥无审核结果接口，只能靠复查可见性。
2. 消息监听覆盖评论/回复/@，不含私信。
3. 去重是进程内 + 文件，多开会重复动作。
4. 生图轮换只换模型，不换 Key。
5. 葫芦侠表情接口返回空，用源码常量。
6. 灵芥部分字段（收藏/关注列表）靠实测接口，后续可能变动。

---

## 9. 接手第一步

1. 跑一次 `simulate_local.py`，确认 50 项全过；
2. 用测试账号跑 `verify_real.py`，看接口是否仍兼容；
3. 打开界面走一遍：登录 → 测试发帖 → 逛一次社区 → 看「动态」；
4. 改提示词前先读 `docs/PROMPTS.md`，改动作表前先读 `capabilities.py`。
