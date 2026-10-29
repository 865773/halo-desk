# 大肥鱼桌面版（HaloDesk）

把 **葫芦侠三楼** 和 **灵芥空间** 两个社区合成一个 Windows 单文件程序：
一个 exe、两个账号、一个会自己逛社区 / 回消息 / 发帖的角色。

- 单文件，免安装，不依赖 Python / Java / 模拟器
- 数据全在本地 `data/`，便携，换电脑整个文件夹拷走即可
- 两个平台账号、主人、表情、发帖额度、发帖队列**各自独立**

![预览](docs/preview-home.png)

---

## 快速开始

1. 双击 `HaloDesk.exe`（首次会在旁边生成 `data/`）
2. 登录两个平台：
   - 葫芦侠三楼 → 登录（扫码 / 账号）
   - 灵芥空间 → 账号密码 / 短信
3. 配置 AI：**大肥鱼 → DeepSeek Key**
4. 两个社区页各填「主人 ID」（可以填自己）
5. 打开「自动任务」，按需开启：
   - 消息监听（默认 10 秒一轮）
   - 逛社区间隔（默认 60 分钟）
   - 两平台每日发帖额度（默认各 2 条）
6. 想先试：点「测试发帖·葫芦侠」/「测试发帖·灵芥」

> 只把 `HaloDesk.exe` 发给别人也能用（对方用自己的账号登录）；
> **不要**把带 `data/` 的整包发给别人，里面有账号凭据和 API Key。

---

## 功能

| 模块 | 能力 |
|---|---|
| 登录 / 签到 | 双平台登录态、一键签到、每日自动签到（已签的跳过） |
| 消息监听 | 10 秒轮询，只处理接入之后的新消息；评论 / 回复 / @ 都能收到 |
| 自动回复 | 模型自己决定「只回话」还是「回话 + 顺手做一件事」，回复前随机等 0–15 秒 |
| 逛社区 | 社区 → 板块 → 看几条 → 每帖动作 → 换板块 / 换社区，每步都写理由 |
| 发帖 | 只发泳池/闲聊；两平台各自额度 + 最小间隔 + 24 小时均分；可配文生图；发完判审核 |
| 用户请求 | 「给我主页第一个帖子点赞收藏」这类，模型解析成动作 + 目标后执行 |
| 记忆 | 通用 / 生活 / 用户记忆；超字数自动总结压缩；「记忆」页可视化 |
| 表情 | 葫芦侠 21 个、灵芥 160 个，各自独立，自创表情自动剔除 |
| 动态 | 所有决策、动作、理由都进时间线，同一帖子的动作合并成一条 |
| 形象 | 配图用形象可自定义（默认蓝发鲸鱼娘） |
| 桌面挂件 | 悬浮窗 + 气泡、托盘、开机自启 |
| 日记 | 每天 23:00 两个平台各发一篇（带图），不占发帖额度 |

---

## 数据目录

全部在 exe 同级的 `data/`：

```
data/
├─ config.json                 账号、Key、开关（含凭据，别外发）
├─ files/
│  ├─ memory.txt               通用记忆（1500 字自动压缩）
│  ├─ life.txt                 生活记忆（1200 字，每天重置）
│  ├─ mem_hlx_u<uid>.txt       葫芦侠用户记忆（800 字）
│  ├─ mem_lingjie_u<uid>.txt   灵芥用户记忆
│  ├─ names_hlx.json            uid → 昵称索引
│  ├─ relations.json           好感度
│  ├─ activity.jsonl           动态时间线
│  ├─ auto_state.json          消息去重 / 发帖计数
│  └─ emoji_lingjie.json       表情缓存
└─ logs/debug.log              调试日志
```

「设置 → 目录」可查看完整路径并一键复制。

---

## 文档

| 文件 | 内容 |
|---|---|
| [docs/HANDOVER.md](docs/HANDOVER.md) | 接管说明：架构、模块、流程、接口坑、构建、测试 |
| [docs/PROMPTS.md](docs/PROMPTS.md) | 12 条提示词的作用、时机、原文、变量 |
| [docs/prompts.json](docs/prompts.json) | 机器可读的提示词清单 |
| [docs/example_integration.py](docs/example_integration.py) | 把提示词接到别的项目的最小示例 |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | 版本变更记录 |

---

## 构建

```powershell
py -3.12 -m venv .venv
.venv\Scripts\pip install PySide6 pyinstaller
.venv\Scripts\pyinstaller --noconfirm --clean --onefile --windowed `
  --name HaloDesk --icon assets\icon.ico `
  --add-data "assets;assets" --runtime-tmpdir "." main.py
```

`--runtime-tmpdir "."` 必须保留：默认解压到 `%TEMP%`，在受限环境会报
“Could not create temporary directory”。

### 测试

```powershell
python tools\simulate_local.py   # 本地仿真，零网络
python tools\verify_real.py      # 真实接口（写操作会被拦截）
python tools\ui_test.py          # 界面检查
python tools\gen_prompt_docs.py  # 重新生成提示词手册
```

---

## 常见问题

**双击提示“应用程序无法正常启动”？**
一般是杀软拦截或下载不完整。把 exe 所在文件夹加入白名单，或重新解压。

**评论/帖子发了但看不到？**
平台审核。程序会复查可见性，动态里标「审核中」；葫芦侠的审核结果会通过通知回来。

**列表里用户只有 uid？**
启动后会在后台补昵称（`files/names_*.json`）；没网时先显示 uid，下次启动再补。

**能不能多开？**
不建议。去重是本地文件级，多开会重复回复/重复发帖。

---

## 许可与声明

仅供个人学习与自用。自动操作会调用社区官方接口，请保持合理频率；
因使用产生的账号风险由使用者自行承担。
