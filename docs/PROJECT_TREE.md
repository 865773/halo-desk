# 项目树（HaloDesk v9.9）

```
halo-desktop/
├─ main.py                    启动入口：单实例、主题、启动页/开场视频、主窗口
├─ HaloDesk.spec              PyInstaller 打包配置
├─ README.md                  功能介绍、快速开始、数据目录、构建
├─ assets/                    图片、音视频、图标（全部打包进 exe）
│  ├─ icon.ico                程序图标
│  ├─ dafeiyu.png             默认头像
│  ├─ fish.png                挂件/装饰图
│  ├─ wallpaper.jpg           流光壁纸（w05）
│  ├─ splash.png / 无         角色启动页（由代码 + 帧绘制）
│  ├─ dingdong.mp3            消息提示音（原版）
│  ├─ dingdong.wav            提示音备用
│  ├─ startup.wav             启动页音效
│  └─ pet/shenshen/           桌宠逐帧动画（idle/happy/shy/angry/drag/eat）
│
├─ app/                       业务逻辑（不含界面）
│  ├─ config.py               配置默认值、data 目录、读写
│  ├─ paths.py                资源路径（打包/源码兼容）
│  ├─ net.py                  HTTP 封装与签名工具
│  ├─ hlx.py                  葫芦侠三楼接口（登录/帖子/评论/通知/关注）
│  ├─ lingjie.py              灵芥空间接口（登录/主题/评论/通知/关注）
│  ├─ ai.py                   DeepSeek / OpenAI 兼容对话 + 生图协议
│  ├─ brain.py                系统提示词、意图/回复/逛社区决策
│  ├─ capabilities.py         固定动作白名单、target 解析、执行
│  ├─ automation.py           10 秒消息轮询、回复、意图、日记调度、防互刷
│  ├─ autopost.py             自动发帖（额度、间隔、审核复查）
│  ├─ diary.py                每日日记 + 生活记忆时间线
│  ├─ roam.py                 逛社区/拜访主页（模型逐层决策）
│  ├─ publishing.py           发帖写作与上传
│  ├─ memory.py               通用/生活/用户记忆、压缩、心情
│  ├─ memgate.py              模型判断「值不值得存入记忆」
│  ├─ names.py                uid → 昵称索引与补全
│  ├─ relations.py            好感度（按平台+账号隔离）
│  ├─ follow.py               亲密度到阈值自动关注
│  ├─ bots.py                 疑似机器人标记（高频互刷）
│  ├─ activity.py             动态时间线（按账号存）
│  ├─ stats.py                今日动作统计（按平台）
│  ├─ emoji.py                表情白名单（葫芦侠 21 / 灵芥 160）
│  ├─ imaging.py              文生图（阿里云/OpenAI/SD）
│  ├─ persona.py              默认人设模板（{name}/{appearance}）
│  ├─ prompts.py              提示词汇总（供查看/对照）
│  ├─ boards.py               发帖板块（泳池/闲聊）
│  ├─ signin_state.py         签到状态
│  └─ debuglog.py             调试日志
│
├─ app/ui/                    界面
│  ├─ main_window.py          无边框主窗口、自绘窗口按钮、侧栏、托盘、单实例、登录失效处理
│  ├─ theme.py                三套主题（流光壁纸/纯白/黑夜）与 QSS
│  ├─ common.py               卡片、按钮、提示等通用组件
│  ├─ base.py                 页面基类（滚动区/玻璃面板）
│  ├─ splash.py               角色启动页（帧动画 + 启动音）
│  ├─ video_splash.py         dsh-video-skin 开场短片（有声、可跳过）
│  ├─ wizard.py               5 步配置向导
│  ├─ home.py                 总览（总开关、心情、两平台今日卡片）
│  ├─ hlx_page.py             葫芦侠登录/签到/账号/用户记忆
│  ├─ lingjie_page.py         灵芥登录/签到/账号/用户记忆
│  ├─ fish_page.py            角色人设、聊天、发帖、管理
│  ├─ memory_page.py          通用/生活记忆查看与压缩
│  ├─ memcard.py              用户记忆列表（搜索、机器人标记）
│  ├─ activity_page.py        动态（平台筛选、动作人话化）
│  ├─ auto_page.py            自动任务（监听、额度、测试、防互刷）
│  ├─ debug_page.py           调试日志、提示词查看
│  ├─ settings_page.py        设置（主题、挂件、AI、文生图、关于、备份）
│  └─ pet.py                  桌面挂件（逐帧动画、气泡、右键菜单）
│
├─ tools/                     开发/验证工具
│  ├─ simulate_local.py       本地仿真（零网络，66 项）
│  ├─ verify_real.py          真实接口（写操作拦截）
│  ├─ ui_test.py              界面回归
│  ├─ gen_prompt_docs.py      生成提示词文档
│  ├─ api_probe.py            接口探针
│  ├─ notif_dump.py           通知抓取
│  ├─ roam_dry.py             逛社区试运行
│  └─ shots.py                截图工具
│
├─ docs/
│  ├─ HANDOVER.md             架构/流程/踩坑/构建说明
│  ├─ PROJECT_TREE.md         本文件
│  ├─ PROMO.md                分享文案与口播脚本
│  ├─ PROMPTS.md              提示词手册
│  ├─ prompts.json            机器可读提示词
│  ├─ CHANGELOG.md            版本变更
│  └─ *.png                   预览图
│
└─ data/                      运行时生成（不提交、不外发）
   ├─ config.json             账号/Key/开关
   ├─ 账号/<平台>/<uid>/      记忆、动态、心情、好感、昵称
   ├─ files/                  生活记忆、去重状态、机器人标记、表情缓存
   └─ logs/debug.log          调试日志
```
