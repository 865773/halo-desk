# 大肥鱼桌面版（HaloDesk）

把「葫芦侠三楼」和「灵芥空间」两个社区合成一个 Windows 单文件程序：
一个 exe、两个账号、一个会自己逛社区/回消息/发帖的角色。

![预览](docs/preview-home.png)

## 快速开始

1. 双击 `HaloDesk.exe`
2. 首次运行检查：
   - 葫芦侠三楼：点「登录」扫码/账号登录
   - 灵芥空间：账号密码或短信登录
   - 大肥鱼 → 配置 DeepSeek Key
   - 两个社区页各填「主人 ID」（可以填自己）
3. 打开「自动任务」，确认：
   - 消息监听（10 秒）
   - 逛社区间隔（默认 60 分钟）
   - 两平台每日发帖额度（默认各 2 条）
4. 想先试试：点「测试发帖·葫芦侠」或「测试发帖·灵芥」

## 数据在哪

全部在 exe 同级的 `data/` 目录：

- `config.json`：账号、Key、开关
- `files/memory.txt`：通用记忆
- `files/life.txt`：生活记忆
- `files/mem_<平台>_u<uid>.txt`：用户记忆
- `logs/debug.log`：调试日志

「设置 → 目录」里有完整路径和「复制」按钮。
整个文件夹拷到别的电脑就能继续用（登录态和记忆都在里面）。

## 功能

- 双平台登录 / 签到 / 消息监听（10 秒循环，只处理接入之后的新消息）
- 自动回复：模型自己决定「只回话」还是「回话 + 顺手做一件事」
- 自由行动：逛社区 / 发帖 / 签到 / 发呆，全部带理由写进「动态」
- 逛社区：社区 → 板块 → 看几条 → 每帖动作 → 换板块/换社区
- 发帖：两平台各自每日额度、最小间隔、24 小时均分；可配文生图
- 记忆：通用 / 生活 / 用户记忆，超字数自动总结压缩；「记忆」页可视化
- 表情：葫芦侠 21 个、灵芥 160 个，各自独立
- 每日日记（22:00，不占发帖额度）
- 桌面挂件、托盘、开机自启

## 文档

- `docs/HANDOVER.md`：给下一个开发者看的接管说明（架构、模块、接口坑、构建命令）
- `docs/PROMPTS.md`：全部提示词手册
- `docs/prompts.json`：机器可读的提示词清单
- `docs/example_integration.py`：把提示词接到别的项目的最小示例

## 常用命令（开发）

```powershell
python tools\simulate_local.py   # 本地仿真（零网络）
python tools\verify_real.py      # 真实接口检查（写操作会被拦截）
python tools\ui_test.py          # 界面检查
python tools\gen_prompt_docs.py  # 重新生成提示词手册
```

## 构建

```powershell
pyinstaller --noconfirm --clean --onefile --windowed --name HaloDesk `
  --icon assets\icon.ico --add-data "assets;assets" --runtime-tmpdir "." main.py
```

## 注意

- `data/config.json` 里有账号凭据和 API Key，不要直接发给别人。
- 评论/帖子可能进审核，界面会标「审核中」；审核结果以平台通知为准。
- 同一账号不要多开，会重复动作。
