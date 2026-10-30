# 后台管理 App 提示词（给手机 AGI）

把下面整段复制给手机上的 AGI，让它生成一个 Android 后台管理 App。

---

你是一名资深 Android 工程师。请用 **Kotlin + Jetpack Compose + Material 3** 写一个完整的「HaloDesk 生态后台管理」App，包名 `com.guo.duduhalo.admin`，最低 Android 10，中文界面，深色/浅色跟随系统，代码要能直接在 Android Studio 打开构建。

## 一、它管理的三个项目

| 项目 | Gitee 仓库 | 版本文件 | 统计文件 |
|---|---|---|---|
| 葫芦侠大肥鱼 | `guo-wenlong/hlx-halo` | `version.txt` | `lingjie-misc` 仓库 `assets/data/.cache/hlx.dat` |
| 灵芥助手 | `guo-wenlong/lingjie-halo` | `version.txt` | `lingjie-misc` 仓库 `assets/data/.cache/lingjie.dat` |
| HaloDesk 桌面版 | `guo-wenlong/halo-desk` | `version.txt` | `lingjie-misc` 仓库 `assets/data/.cache/halodesk.dat` |

统计文件都在同一个 Gitee 仓库 `guo-wenlong/lingjie-misc`，只是文件名不同。

## 二、登录与安全（重要）

1. 首次打开让管理员粘贴一个 **Gitee 私人令牌**，只存 `EncryptedSharedPreferences`，不要写死在代码里，不要上传到公开仓库，不要打印到日志。
2. 令牌只保存在本机；提供「退出并清除令牌」。
3. 所有写操作（改公告、改版本、强更开关）必须二次确认，并显示将要修改的仓库、文件、字段。
4. 不要读取或展示任何用户的账号密码、AI Key、聊天内容。

## 三、统计数据格式

Gitee Contents API 返回的 `content` 是 **文件内容的 Base64**；文件本身的字节又是 **Base64(JSON)**。所以读取时要解码两次：

```
api.content --Base64解码--> 文件文本 --Base64解码--> JSON 数组
```

写回时反向：

```
JSON 数组 --Base64--> 文件文本 --Base64--> PUT 的 content 字段
```

### 三个文件的字段

- 手机端（`hlx.dat` / `lingjie.dat`）：
  `uid: Long`、`nickname: String`、`device: String`、`first: String`
- 桌面端（`halodesk.dat`）：
  `id: String`（安装 id）、`platform: String`（葫芦侠 / 灵芥）、
  `uid: Long`、`nickname: String`、`version: String`、`device: String`、`first: String`

去重规则：手机按 `uid`；桌面按 `platform + uid`，同一安装的两个平台账号各算一条。

## 四、统计看板

1. 首页三张卡片：葫芦侠用户数、灵芥用户数、桌面安装数。
2. 每个项目详情页：
   - 总用户数；
   - 本周新增（按 `first` 日期）；
   - 版本分布（如果有 version）；
   - 设备分布；
   - 搜索 uid / id / 昵称；
   - 列表分页或懒加载；
   - 导出 CSV 到系统分享。
3. 支持下拉刷新、加载中/空状态/失败重试。
4. 只做只读，不提供删除用户统计的入口。

## 五、更新与公告管理

每个项目一个编辑页，读写仓库根目录 `version.txt`，格式：

```
version=10.6
update_force=0
announcement=
announcement_force=0
download_url=https://gitee.com/guo-wenlong/halo-desk
notes=
```

界面要求：

- 当前版本、下载地址可编辑；
- 「强制更新」开关（`update_force`）；
- 公告多行输入，支持预览；
- 「强制公告」开关（`announcement_force`）；
- 保存前显示 diff，确认后调用 Gitee API PUT；
- PUT 必须带当前文件的 `sha`，防止覆盖别人的修改；
- 保存成功/失败都有明确提示；
- 提供「恢复上次内容」按钮。

## 六、Gitee API

读取：

```
GET https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{path}?access_token={token}
```

写入：

```
PUT https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{path}
{
  "access_token": token,
  "content": "Base64(文件内容)",
  "message": "admin: update version.txt",
  "sha": "当前文件 sha"
}
```

文件不存在时用 POST 创建。所有请求 10 秒超时，错误要转成中文可读提示（401 令牌无效、404 文件不存在、409 sha 冲突等）。

## 七、界面结构

底部导航三个 Tab：

1. **概览**：三个项目卡片、总用户数、最近更新时间、快捷入口；
2. **统计**：三个项目切换，搜索、版本/设备分布、CSV 导出；
3. **发布**：三个项目切换，版本/下载地址/强更开关/公告/强公告，保存按钮。

设置页：令牌管理、主题、缓存清理、关于、开源地址。

## 八、交付要求

1. 完整 Gradle 工程，不要只给代码片段；
2. 使用 Retrofit/OkHttp + kotlinx.serialization 或 Gson；
3. 所有字符串放 `strings.xml`，中文；
4. 处理深色模式、横竖屏、错误状态；
5. 不要引入任何统计/广告 SDK；
6. 代码里不出现真实令牌、真实用户数据、真实仓库密码；
7. 最后给出：
   - 项目结构树；
   - 如何构建 APK；
   - 如何第一次登录；
   - 安全注意事项。

请直接开始写工程。
