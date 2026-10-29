# 大肥鱼桌面版 · 项目接管说明（HANDOVER）

> 版本：v2.9　构建时间：2026-10-29　平台：Windows 10/11 x64
> 用途：把 hlx-halo（葫芦侠三楼）与 lingjie-halo（灵芥空间）两个 Android 项目
> 合并移植成一个 Windows 单文件桌面程序。

---

## 1. 一分钟看懂

- **一个 exe**：`HaloDesk.exe`，双击即用，无需安装 Python。
- **两个账号**：葫芦侠用 `_key`，灵芥用 Bearer JWT，各自独立登录。
- **一个“人”**：共用同一套大肥鱼人设、心情、记忆；但**主人 ID、表情、发帖额度、发帖队列按平台分开**。
- **会自己动**：每 10 秒看一次两平台消息并回复；每 N 分钟（默认 60）自由行动一次
  （逛社区 / 发帖 / 签到）；每 6 小时写生活记忆；每天 22:00 写日记。
- **本地优先**：所有数据在 exe 同级的 `data/`，不经过任何中转服务器。

---

## 2. 目录结构

```
HaloDesk/                     ← 整个文件夹可以拷到任何地方运行
├─ HaloDesk.exe               ← 主程序（PyInstaller onefile）
├─ data/                      ← 运行时自动生成/写入
│  ├─ config.json             ← 账号、AI Key、各项开关
│  ├─ files/
│  │  ├─ memory.txt           ← 通用记忆（每 1500 字自动压缩）
│  │  ├─ life.txt             ← 生活记忆（每天重置，每 1200 字压缩）
│  │  ├─ mem_hlx_u<uid>.txt   ← 葫芦侠用户记忆（每 800 字压缩）
│  │  ├─ mem_lingjie_u<uid>.txt
│  │  ├─ mood.json            ← 心情值
│  │  ├─ relations.json       ← 亲密度
│  │  ├─ activity.jsonl       ← 动态时间线（UI“动态”页）
│  │  ├─ auto_state.json      ← 消息去重、接入时间、发帖计数
│  │  ├─ roam_seen_*.json     ← 逛过的帖子
│  │  ├─ roam_commented_*.json← 评论过的帖子
│  │  └─ emoji_lingjie.json   ← 灵芥表情缓存（7 天）
│  └─ logs/debug.log          ← 调试日志（HTTP、决策、错误）
└─ docs/                      ← 提示词手册、接入示例
```

源码目录（开发用）：

```
halo-desktop/
├─ main.py                    ← 入口；--selftest 自检截图
├─ app/                       ← 全部业务代码（见第 5 节）
├─ assets/                    ← 图标、角色图
├─ tools/                     ← 测试与生成脚本
├─ docs/                      ← PROMPTS.md / prompts.json / HANDOVER.md
├─ dist/                      ← 构建产物（HaloDesk.exe）
└─ HaloDesk.spec              ← PyInstaller 配置
```

---

## 3. 运行与构建

### 直接运行
双击 `HaloDesk.exe`。首次会在同级生成 `data/`。

### 从源码构建（Windows）
```powershell
cd halo-desktop
py -3.12 -m venv .venv
.venv\Scripts\pip install PySide6 pyinstaller requests
.venv\Scripts\pyinstaller --noconfirm --clean --onefile --windowed `
  --name HaloDesk --icon assets\icon.ico `
  --add-data "assets;assets" --runtime-tmpdir "." main.py
# 产物：dist\HaloDesk.exe
```

> `--runtime-tmpdir "."` 很关键：默认解压到 `%TEMP%`，在受限环境会报
> “Could not create temporary directory”。

### 自检
```powershell
$env:HALODESK_HOME=".\.verify"; .\dist\HaloDesk.exe --selftest
# 输出 SELFTEST OK + 截图路径
```

### 测试
```powershell
.venv\Scripts\python tools\simulate_local.py   # 49 项本地仿真，零网络
.venv\Scripts\python tools\verify_real.py      # 46 项真实接口（写操作拦截）
.venv\Scripts\python tools\ui_test.py          # 13 项界面检查
python tools\gen_prompt_docs.py                # 重新生成提示词手册
```

---

## 4. 配置说明（`data/config.json`）

| 键 | 含义 | 默认 |
|---|---|---|
| `hlx.key` / `hlx.uid` | 葫芦侠登录态 | 空 |
| `lingjie.token` / `lingjie.uid` | 灵芥 JWT 与 uid | 空 |
| `ai.key` / `ai.model*` | DeepSeek（或兼容）Key 与模型 | 空 |
| `fish.owner_uid_hlx` / `_lingjie` | **两个平台各自的主人 uid** | 0 |
| `fish.interval_min` | 自由行动间隔（分钟） | 20 |
| `fish.memory_max` / `user_mem_max` / `life_max` | 记忆压缩阈值（字） | 1500/800/1200 |
| `fish.img_proto` / `img_url` / `img_key` / `img_model` / `img_models` | 文生图配置与**模型轮换列表** | openai / 空 / 空 / gpt-image-1 / wan 系列 |
| `auto.enabled` / `poll_sec` / `max_per_pass` | 消息监听开关、轮询秒数、每轮最多回几条 | False / 10 / 3 |
| `autopost.enabled` / `daily_limit_hlx` / `daily_limit_lingjie` / `min_gap_min` | 自动发帖、两平台每日额度、最小间隔 | False / 2 / 2 / 40 |
| `autopost.diary_enabled` / `diary_time` | 每日日记（不占发帖额度） | True / 22:00 |
| `perm.*` | 各动作开关（点赞/收藏/评论/关注/送葫芦/发帖/签到/逛社区/回复/看图） | 除送葫芦外全开 |

> `config.json` 含账号凭据与 API Key，**不要直接外发**。

---

## 5. 模块地图（`app/`）

| 文件 | 职责 |
|---|---|
| `config.py` | 配置读写、数据目录选择（exe 同级 `data/` 优先） |
| `net.py` | HTTP 封装、编码/签名工具、JSON 容错提取 |
| `hlx.py` | 葫芦侠客户端：登录、板块、帖子、评论、点赞、收藏、关注、打赏、签到、通知、审核通知、上传、搜索、收藏列表 |
| `lingjie.py` | 灵芥客户端：登录、板块、帖子、评论、点赞、收藏、关注、打赏、签到、通知、上传（七牛）、收藏列表、表情 |
| `ai.py` | LLM 调用（含视觉），失败重试 |
| `brain.py` | 系统提示词拼装、看帖决策、意图决策、分层决策 |
| `capabilities.py` | **动作白名单 + 目标解析 + 执行器**（15 种帖子组合 + 独立动作） |
| `roam.py` | 逛社区：社区→板块→看几条→逐帖→换板块/换社区 |
| `automation.py` | 定时器：消息轮询、自由行动、发帖、日记、生活记忆、审核检查 |
| `autopost.py` | 生成草稿、配图、发布、审核判定、每日额度计数 |
| `publishing.py` | 发帖/评论落地（含图片上传） |
| `imaging.py` | 文生图三种协议（OpenAI / DashScope / SD），**模型失败自动换下一个** |
| `memory.py` | 通用/生活/用户记忆、**超字数自动压缩**、心情 |
| `relations.py` / `stats.py` / `activity.py` / `debuglog.py` | 亲密度 / 统计 / 动态 / 日志 |
| `emoji.py` | 两平台**独立**表情表（葫芦侠 21 个、灵芥 160 个） |
| `diary.py` | 生活记忆生成、每日日记 |
| `boards.py` | 发帖板块（葫芦侠=泳池，灵芥=闲聊）、文生图是否可用 |
| `ui/` | PySide6 界面：总览、两平台、大肥鱼、记忆、动态、自动任务、调试、设置 |

---

## 6. 核心流程

### 6.1 消息监听（10 秒）
1. 拉两平台通知（只处理「接入时间点」之后、未回复过的）。
2. 灵芥注意 `at_comment`（@ 我）类型，内容里有 `<at uid="..">@名字</at>` 要清洗。
3. 服务端二次校验：该评论下是否已有我的回复（防重复）。
4. 交给模型：只回话，或回话 + 执行一个动作（动作清单在 `capabilities.py`）。
5. 随机等 0–15 秒再发，记动态。

### 6.2 自由行动（每 `fish.interval_min` 分钟）
模型选 `roam / post / signin / idle`；发帖时按「两平台各自额度 + 最小间隔 + 24 小时均分」挑平台。

### 6.3 逛社区
社区 → 板块 → 看几条 → 每帖决策（动作清单）→ 换板块/换社区。
已评论过的帖子直接跳过（本地记录 + 服务端校验），不再浪费决策。

### 6.4 发帖
写标题正文 → 需要时按**生活记忆 + 随机场景**生成配图 → 上传 → 发布 →
2 秒后查「我的帖子」判断是否审核中 → 记动态、计数。

### 6.5 记忆
- 通用记忆每 1500 字、用户记忆每 800 字、生活记忆每 1200 字，
  超限自动让模型总结成「关键节点」后覆盖，带 `[压缩]` 前缀。
- 「记忆」页可查看/清空/手动压缩，显示字数与上限百分比。

### 6.6 文生图
按 `img_model` → `img_models` 列表依次尝试，失败（余额/额度/模型下线）自动换下一个，
成功的模型写回配置并在日志记「换到可用模型」。

---

## 7. 接口要点与坑

| 事项 | 说明 |
|---|---|
| 葫芦侠签名 | `_key` + md5(SECRET `fa1c28a5b62e79c3e63d9030b6142e4b`)，GET 用大写、POST 用小写 |
| 灵芥鉴权 | `Authorization: Bearer <token>`，401 时用 refresh 或重登 |
| 灵芥帖子 id | `themeId` / `tid`；葫芦侠是 `postID` |
| 灵芥时间 | `create_time` 是「11分钟前」这类文本，要转时间戳 |
| 灵芥 @ | `notification_type=at_comment`，内容是 HTML `<at>` 标签 |
| 灵芥上传 | `/upload/token` 返回 `uploadHost`（七牛 Kodo 加速域名），失败退回 `up-z0.qiniup.com` |
| 葫芦侠审核 | `type_id=1` 通知：「您的评论【…】已审核通过/未通过」 |
| 评论审核 | 接口返回成功 ≠ 立刻可见；发完复查，看不到标「审核中」 |

---

## 8. 已知限制 / 建议后续

1. 灵芥没有「审核结果」接口，只能靠发完复查判断是否可见。
2. 葫芦侠表情接口返回空，用的是源码常量；灵芥表情 160 个来自接口缓存。
3. 消息监听只覆盖评论/@/回复，不含私信。
4. 同一账号多开会导致重复动作（去重是进程内 + 文件，不是分布式锁）。
5. 生图轮换只换模型，不换 Key；多 Key 需要自己扩。
6. 建议下一步：把 `capabilities.py` 的动作表做成插件式注册，接新平台只加执行器。

---

## 9. 提示词

所有提示词原文、变量、迁移步骤见 `docs/PROMPTS.md`（由 `tools/gen_prompt_docs.py`
从代码导出）。核心 12 条：人设、身份环境、动作清单、看帖上下文、回复消息、
自由行动、分层单选、发帖、日记、生活记忆、配图、评论兜底。

---

## 10. 交接清单

- [x] 可运行 exe 与数据目录（本包 `data/` 已含当前账号登录态与记忆）
- [x] 源码 zip（`src/`）
- [x] 提示词手册与 JSON
- [x] 构建/测试命令
- [x] 接口坑位与已知限制
- [ ] 新机器首次运行：检查两平台登录、主人 uid、AI Key、文生图配置
