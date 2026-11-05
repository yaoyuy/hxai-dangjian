# HXAI 智慧党建

一个跑在 **Python Flask + SQLite** 上的党建信息管理系统，不是静态演示页。

- 前台按微信公众号的样子做：底部三项菜单（党建学习 / 组织生活 / 支部风采）+ 浮层子菜单 + 卡片列表
- 后台是真正的录入界面：文章、活动、党员账号、风采，全部服务端渲染表单
- 另有一套配套的**微信小程序**（miniprogram/），复用同一套后端接口

> **状态**：第一阶段，用个人订阅号在本地与校园网内跑通全流程，面向学校的正式部署尚未开始。
> 域名、AppID、密钥、数据库账号一律只从环境变量读取（见 .env.example），代码里不出现真实值。
> 首次部署请先改掉 ADMIN_PASSWORD 与 SECRET_KEY。

## 技术栈

Flask + SQLAlchemy + SQLite（可切 MySQL）· Jinja2 服务端渲染 · 微信小程序原生框架 · 微信公众号网页授权

界面结构参考过一份内部演示 HTML，但数据模型、路由、接口与数据库全部重写，未复用其代码。

以下为项目原始文档。

---

## 目录

1. [个人订阅号能测什么、不能测什么](#1-个人订阅号能测什么不能测什么)
2. [已实现 / 未实现](#2-已实现--未实现)
3. [目录结构](#3-目录结构)
4. [本地运行步骤](#4-本地运行步骤)
5. [怎么测（照着做一遍）](#5-怎么测照着做一遍)
6. [在微信里打开（个人号）](#6-在微信里打开个人号)
7. [第二阶段预留了什么](#7-第二阶段预留了什么)
8. [已知限制](#8-已知限制)
9. [方案 A：微信设置 / 小程序登录 / 党费 / 组织关系转接](#9-方案-a微信设置--小程序登录--党费--组织关系转接)

配套文档：

- [docs/个人号测试清单.md](docs/个人号测试清单.md) —— 逐项勾选，哪些现在能测、哪些要等学校号
- [docs/公众号菜单与公网访问说明.md](docs/公众号菜单与公网访问说明.md) —— 菜单是怎么挂上的、隧道怎么保活、掉线怎么办
- [docs/微信设置与小程序登录.md](docs/微信设置与小程序登录.md) —— 微信参数存哪、后台怎么填、小程序 openid 登录怎么走
- [docs/小程序开发与发布.md](docs/小程序开发与发布.md) —— 想「点一下菜单直接进系统」为什么要做小程序、注册/备案/发布/关联全流程、学校要提供什么
- [docs/部署与学校交接清单.md](docs/部署与学校交接清单.md) —— 第二阶段找学校要什么信息

---

## 1. 个人订阅号能测什么、不能测什么

这一节是硬事实，不是"应该可以"。个人订阅号（未认证）在微信开放体系里的权限非常有限：

| 能力 | 个人订阅号 | 说明 |
|---|---|---|
| 网页在微信内置浏览器打开 | ✅ 可以 | 把链接发到微信里点开就能用，这是第一阶段的测试方式 |
| 网页授权（拿 openid / 用户信息） | ❌ **没有** | `snsapi_base` / `snsapi_userinfo` 需要认证服务号（或已认证订阅号的部分能力），个人号调用会返回 `api unauthorized` |
| 自定义菜单 API | ❌ **没有** | 调 `menu/create` 返回 `48001 api unauthorized`。个人号只能在公众号后台手工加菜单（入口未必开放） |
| 模板消息 / 订阅消息 | ❌ 没有 | 无法主动推送"活动提醒" |
| 客服消息 | ❌ 没有 | 48 小时主动回复限制也不适用于个人号 |
| 微信支付 / JS-SDK 签名 | ❌ 没有 | 本项目也不需要支付 |
| 接收用户消息与事件推送 | ✅ 可以 | 在公众号后台填服务器 URL + Token 后，用户消息会转发到你的服务器，可以被动回复（启用后后台自动回复与菜单会失效） |

**所以第一阶段的登录方式是本地测试账号**，页面上明确写着：

> 测试登录，非微信身份

系统**没有**、也不会伪造微信 openid。数据库 `user.openid` 字段留空，等第二阶段接入学校已认证公众号后才会填。

> 补充（方案 A 之后）：个人订阅号拿不到 openid，但**微信小程序能拿到**——小程序 `wx.login()` 走
> `jscode2session` 换 openid，不需要网页授权权限。对应接口与白名单机制已经实现（见第 9 节），
> 缺的只是「个人小程序 + 已备案 HTTPS 域名」这两样外部条件。
`/api/wechat/status` 会如实返回 `appid_configured=false`、`capabilities.custom_menu_api=false`、`oauth_web=false`、`pay=false`。

### 个人号上可以真实验证的功能

1. 文章列表 / 分类筛选 / 文章详情 / 学习打卡（写入 `study_record` 表）
2. 三会一课与活动列表、活动详情
3. 活动报名（写入 `enrollment` 表，刷新后状态还在，人数由数据库实时统计）
4. 电子台账：分类、搜索、上传、下载（文件落盘 + 元信息入库）
5. 党建风采展示
6. 数据看板（全部实时 SQL 聚合，演示数据带「测试数据」标签）
7. 后台管理：文章/活动/党员/风采的增删改查、演示数据一键清理

### 必须等学校号才能验证的功能

1. 微信网页授权登录（openid 绑定、免密进入）
2. 自定义菜单 API 推送（`/api/wechat/menu/push` 现在会如实返回 48001 的原因）
3. 模板消息 / 订阅消息推送活动提醒
4. 服务器 URL 接入微信（需要公网 HTTPS 域名，本地 `127.0.0.1` 不行）

---

## 2. 已实现 / 未实现

### 已实现（第一阶段，本地已跑通、已自动化验证）

| 模块 | 内容 | 数据在哪 |
|---|---|---|
| 首页 | 支部信息、数据概览、功能入口六宫格、最新文章推送卡 | `article` / `activity` / `user` 表实时统计 |
| 学习专栏 | 列表、分类筛选、关键词搜索、分页、文章详情、学习打卡 | `article` + `study_record` |
| 文章状态 | 草稿 / 已发布；草稿只有管理员可见，前台匿名访问返回 404 | `article.status` |
| 三会一课 | 按类型（会议/主题党日/志愿服务/集中学习）筛选的列表 | `activity` |
| 活动报名 | 活动列表、详情、报名、取消；唯一约束防重复；名额与截止时间校验 | `enrollment`（唯一约束 `uq_enrollment_activity_user`） |
| 电子台账 | 5 类分类、文件名搜索、管理员上传落盘、登录后下载、下载计数 | `ledger_file` + `data/uploads/` |
| 党建风采 | 图片墙展示 | `gallery_photo` |
| 数据看板 | 党员数、年度活动数、学习完成率、累计学习小时、每月活动柱状图、年龄构成环形图 | 全部实时 SQL 聚合，无写死数字 |
| 后台管理 | 概览、文章增删改查+一键发布、活动增删改查+报名名单、党员账号+重置密码、风采管理、演示数据清理 | 服务端渲染表单，不需要 JS |
| 测试登录 | 本地账号登录，返回体与页面均标注 `login_mode=test`、`has_openid=false` | `user` 表 |
| 微信接入预备 | `/wechat` 验签 + 被动回复、`/api/wechat/status` 如实报告能力、`/api/wechat/menu/push` 如实返回 48001 | `backend/wechat.py` |
| 微信设置页 | 公众号 / 小程序的 AppID、AppSecret、Token、AESKey 在**后台页面**填写，存数据库，密钥脱敏显示、留空不覆盖 | `sys_setting` 表 + `backend/settings_store.py` |
| 微信登录白名单 | 只有白名单里的微信能登录；可以先填姓名+手机号、openid 留空，首次登录自动补全；可停用/删除；未授权返回 403 `not_in_whitelist` | `login_whitelist` 表 |
| 微信登录链路 | 小程序 `jscode2session`、公众号网页授权 `oauth2/access_token`、本地联调 `dev_openid` 三条路都写了；登录模式 `test / both / wechat` 可切换 | `/api/auth/wechat-login`、`/api/auth/bind-openid` |
| 党费管理 | 按「人 + 期间(YYYY-MM)」一条记录；后台按期间批量生成应缴、标记已缴/未缴、删除；前台「我的」查看明细 | `party_due` 表 + `/api/dues/my`、`/api/dues/summary` |
| 组织关系转接 | 党员自己提交转入/转出申请（重复提交 409），支部管理员后台审核通过/驳回，前台可看结果 | `org_transfer` 表 + `/api/transfers` |
| 数据库可切换 | `DB_ENGINE=sqlite / mysql` 只改 .env，缺 MySQL 参数时直接报错不回退 | `config.build_database_uri()` |
| 健康检查 | `/healthz` 返回环境、数据库类型、登录模式 | — |

自动化验证：

- `tools/smoke_admin.py` **20 项全绿**：未登录拦截 → 管理员登录 → 后台各页 → 建中文草稿 → 前台不可见 → 发布 → 前台可见 → 删除 → 建活动 → 报名 → 后台名单 → 普通党员 403。
- `tools/smoke_party_wx.py` **44 项全绿**（方案 A 新增）：微信设置保存/密钥脱敏/留空不覆盖、菜单推送 48001、白名单三种拒绝与放行、重复绑定 409、党费生成与标记已缴、转接提交与审核、后台新页 403、前台新内容。

截图 23 张，控制台无报错。

### 未实现（如实列出）

| 没做的 | 为什么 | 什么时候做 |
|---|---|---|
| 微信网页授权登录（浏览器里） | 个人订阅号没有该权限，做了也无法验证；代码已写好（`oauth_access_token` / `oauth_userinfo`），只差配置 | 第二阶段换学校已认证公众号后 |
| 小程序正式发布 | 前端页面已写好（`miniprogram/`，原生 WXML/WXSS/JS 共 13 页），并已在微信开发者工具里用**测试号**跑通、渲染真实数据库数据、生成真机预览二维码；但正式版要求**备案过的 HTTPS 域名**（内网 `http://192.168.x.x:5000` 只能用于开发版/体验版），且个人小程序不能用 web-view 套壳 | 第二阶段拿到学校域名后（后端 6 个 API 模块不用改） |
| 党费在线支付 | 你明确说了不要支付功能 | 不做 |
| 消息推送（模板消息/订阅消息） | 个人号无权限 | 第二阶段 |
| 自定义菜单 API 推送 | 个人号调 `menu/create` 必然 48001 | 第二阶段 |
| 模板消息 / 订阅消息 | 同上，无权限 | 第二阶段 |
| 富文本编辑器 | 后台用 textarea 存纯文本/简单 HTML，够用但不是专业排版 | 需要时再加 |
| 多支部数据隔离 | `Branch` 表和 `User.branch_id` 已就位，但查询没有按支部过滤 | 第二阶段（学校可能多支部） |
| 生产部署文件（nginx / gunicorn / systemd） | 缺学校服务器信息，硬写就是编造 | 第二阶段拿到服务器信息后 |
| 文件上传的病毒扫描 / 图片压缩 | 当前只校验扩展名与大小 | 按学校安全要求定 |
| 台账演示文件实体 | 初始化 8 份台账磁盘上没有真实文件，点下载提示"文件不存在"——**故意如此**，不把假文件伪装成真材料 | 管理员上传的就是真文件 |

---

## 3. 目录结构

```
hxai_dangjian/
├── app.py                  # 应用工厂：注册蓝图、错误处理、建表、初始化
├── run.py                  # 本地启动入口
├── manage.py               # 命令行工具：initdb / seed / reset / stats / accounts
├── config.py               # 全部配置从这里读（值来自 .env，代码里不写死）
├── .env.example            # 配置模板（程序首次启动会自动复制成 .env）
├── .gitignore              # 排除 .env / data/ / .venv 等
├── requirements.txt
├── 启动智慧党建.bat        # Windows 双击启动（自动设 APP_HOST=0.0.0.0 并打印访问地址）
├── backend/
│   ├── extensions.py       # db = SQLAlchemy()
│   ├── models.py           # Branch/User/Category/Article/Activity/Enrollment/StudyRecord/LedgerFile/GalleryPhoto
│   │                       # + 方案 A：SysSetting/Whitelist/PartyDue/OrgTransfer
│   ├── auth.py             # 会话、login_required、api_login_required、admin_required
│   ├── pages.py            # 前台页面路由（每个功能一个独立路由）
│   ├── admin.py            # 后台管理路由（服务端渲染表单，含微信设置/白名单/党费/转接）
│   ├── settings_store.py   # 微信等运行期参数存数据库（密钥脱敏、留空不覆盖、取值优先级）
│   ├── seed.py             # 初始化演示数据（全部 is_demo=True）
│   ├── wechat.py           # 签名校验、access_token、菜单结构、网页授权 URL、jscode2session
│   └── api/
│       ├── articles.py     # /api/articles /api/categories /api/articles/<id>/study
│       ├── activities.py   # /api/activities /enroll /cancel /enrollments
│       ├── ledger.py       # /api/ledger 上传/下载/搜索/删除
│       ├── party.py        # /api/dues/my|summary、/api/transfers
│       ├── stats.py        # /api/stats/overview|monthly|members|learning|activity-participation|dues
│       ├── auth_api.py     # /api/auth/login|logout|me|wechat-login|bind-openid
│       └── wechat_api.py   # /wechat 回调、/api/wechat/status、/api/wechat/menu/push
├── templates/
│   ├── base.html           # 微信风格外壳：标题栏 + 提示条 + 底部菜单
│   ├── index.html study.html article.html meetings.html activities.html
│   ├── activity_detail.html ledger.html gallery.html dashboard.html
│   ├── login.html me.html error.html
│   └── admin/              # 后台 12 个模板（base_admin + 概览/文章/活动/党员/风采
│                           #   + 微信设置/白名单/党费/组织关系转接）
├── static/
│   ├── css/app.css         # 前台样式（微信移动端）
│   ├── css/admin.css       # 后台样式（桌面表格）
│   └── js/app.js           # 前台交互（原生 JS，无框架、无需 Node）
├── tools/
│   ├── start_server.vbs    # 开机自启用：隐藏窗口启动服务并绑定 0.0.0.0
│   ├── keep_online.sh      # 保活：Flask 掉线拉起 + SSH 隧道重连并更新 .tunnel_url
│   ├── screenshot.py       # 用 Edge 无头模式给所有页面截图（前台 12 + 后台 11）
│   ├── smoke_admin.py      # 后台冒烟测试（真实 HTTP 请求，20 项）
│   ├── smoke_party_wx.py   # 方案 A 冒烟测试（微信设置/白名单/党费/转接，44 项）
│   ├── shot_ui.py          # 抓底部菜单浮层截图
│   └── probe_dashboard.py  # 临时检查：看板下半屏（党费/学习/活动参与）是否真的渲染 
├── miniprogram/            # 微信小程序前端（原生 WXML/WXSS/JS，不依赖 Node）
│                           #   用微信开发者工具打开本目录；连后端的地址在 config.js
│                           #   完整说明见 docs/小程序开发与发布.md
├── docs/                   # 测试清单、菜单说明、小程序说明、微信设置说明、交接清单、截图
│   └── shots/              # 页面截图
└── data/                   # SQLite 数据库（自动生成，不进版本库）
    └── uploads/            # 台账上传的文件
```

**前端不是单文件**：每个页面在 `templates/` 里有自己的模板，在 `backend/pages.py` 里有自己的路由。
**后端按模块拆**：文章、活动、报名、台账、统计各自一个文件，互不干扰。

---

## 4. 本地运行步骤

### 4.1 首次准备

```bash
cd D:\GZH\hxai_dangjian

# 1) 创建虚拟环境并装依赖
#    本机 Python 3.10 的 pip 损坏（ModuleNotFoundError: pip._vendor.rich._emoji_codes），
#    所以用 uv 装：C:\Users\xinyi\AppData\Local\Programs\Python\Python310\Scripts\uv.exe
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt

# 2) 生成配置：.env 不存在时程序首次启动会自动从 .env.example 复制，也可以手工复制
copy .env.example .env
```

按需改 `.env`（**所有可变配置都在这里，代码里没有写死任何域名/端口/账号**）：

```ini
APP_ENV=local
APP_HOST=127.0.0.1        # 改成 0.0.0.0 才能被手机/局域网访问
APP_PORT=5000
PUBLIC_BASE_URL=http://127.0.0.1:5000   # 生成绝对链接用；换域名只改这里
DB_ENGINE=sqlite          # 换 MySQL 只改这里 + 填 MYSQL_*
SQLITE_PATH=data/dangjian.db
LOGIN_MODE=test           # 第一阶段：本地测试账号
ADMIN_USERNAME=admin
ADMIN_PASSWORD=Admin@123456
AUTO_SEED=true            # 首次启动写入演示数据（可关）
```

### 4.2 启动

**已配置开机自启**：启动文件夹里有 `智慧党建.lnk` → 调用 `tools\start_server.vbs`，
开机登录后自动隐藏窗口启动服务并绑定 `0.0.0.0`（实测杀掉全部 Flask 进程后运行它，
`127.0.0.1:5000` 与局域网地址都恢复 200）。不想开机自启就删掉那个快捷方式。

**最省事（Windows 双击）**：双击项目根目录的 **`启动智慧党建.bat`**。
它已经帮你设好 `APP_HOST=0.0.0.0`（手机/局域网能访问），启动后会打印本机地址和局域网地址。
关闭那个黑窗口不影响服务；要停止就关任务栏里最小化的 python 窗口。

**命令行**：

```bash
# 想被手机访问，先让 Flask 监听所有网卡（.env 里 APP_HOST=0.0.0.0 也可以）
APP_HOST=0.0.0.0 .venv/Scripts/python.exe -X utf8 run.py

# 只在本机用
.venv/Scripts/python.exe -X utf8 run.py
```

**要连公众号菜单用（带隧道保活）**：

```bash
bash tools/keep_online.sh &     # Flask 掉线自动拉起 + SSH 隧道重连（详见第 6 节）
```

浏览器打开：

| 地址 | 说明 |
|---|---|
| <http://127.0.0.1:5000/> | 前台首页 |
| <http://127.0.0.1:5000/admin/> | 后台管理（需管理员登录） |
| <http://127.0.0.1:5000/admin/wechat> | 微信设置（填 AppID / AppSecret，存数据库，不用改 .env） |
| <http://127.0.0.1:5000/admin/whitelist> | 微信登录白名单 |
| <http://127.0.0.1:5000/admin/dues> | 党费管理 |
| <http://127.0.0.1:5000/admin/transfers> | 组织关系转接审核 |
| <http://127.0.0.1:5000/healthz> | 健康检查（返回数据库类型、环境、登录模式、对外地址） |
| <http://192.168.x.x:5000/> | 手机/局域网访问（换成你自己电脑的**内网 IP**，用 `ipconfig` 查；校园网是 DHCP，重连后 IP 可能变） |

命令行工具：

```bash
.venv/Scripts/python.exe -X utf8 manage.py initdb    # 只建表
.venv/Scripts/python.exe -X utf8 manage.py seed      # 写入演示数据
.venv/Scripts/python.exe -X utf8 manage.py stats     # 打印当前统计
.venv/Scripts/python.exe -X utf8 manage.py accounts  # 打印所有账号
.venv/Scripts/python.exe -X utf8 manage.py reset     # 清库重建（会二次确认）
```

> `-X utf8` 是给 Windows 终端用的：不加以防中文输出乱码。

### 4.3 默认账号

| 账号 | 密码 | 角色 | 能干什么 |
|---|---|---|---|
| `admin` | `Admin@123456` | 超级管理员 | 前台全部 + `/admin/` 后台 |
| `zhangsan` `lisi` `wangwu` `zhaoliu` `sunqi` | `Test@123456` | 普通党员 | 只能前台浏览、报名、打卡、下载台账 |

所有账号都标了「测试账号」，登录后顶部有横幅：**测试登录，非微信身份**。
后台「党员」页可以新建账号、重置密码。

---

## 5. 怎么测（照着做一遍）

### 5.1 测活动报名（验证"数据真的进库了"）

1. 打开 <http://127.0.0.1:5000/login>，用 `zhangsan` / `Test@123456` 登录
2. 进「活动报名」，记下某个活动的「已报名 N 人」
3. 点「我要报名」→ 提示成功，人数 +1
4. **按 F5 刷新**：仍显示"已报名"，人数没变回去 ← 说明状态在数据库里，不是前端假象
5. 再点一次 → 提示"你已经报名过了"（唯一约束在数据库层拦截，不是前端挡的）
6. 直接查库确认：

```bash
.venv/Scripts/python.exe -X utf8 -c "import sqlite3;c=sqlite3.connect('data/dangjian.db');print(list(c.execute('select activity_id,user_id,status from enrollment')))"
```

7. 换 `lisi` 登录再报名，人数再 +1 → 统计是"谁报了就加谁"
8. 进后台 <http://127.0.0.1:5000/admin/activities> → 点「编辑/名单」，能看到报名人姓名与时间

### 5.2 测电子台账上传 / 下载

1. 用 `admin` 登录（上传是管理员权限）
2. 进「电子台账」→ 选分类 → 选一个本地文件（doc/docx/pdf/xls/xlsx/ppt/pptx/txt/csv/md/图片，≤20 MB）
3. 上传成功后列表出现该文件，**信息来自数据库**
4. 点「下载」→ 文件真的下载下来，且「下载 N」+1
5. 搜索框输入"纪要" → 只显示匹配项（数据库 `LIKE` 查询，不是前端过滤）
6. 看磁盘：`ls data/uploads/` —— 文件本体在这里，库里存元信息 + uuid 文件名（避免重名覆盖）
7. 退登后点下载 → 跳登录页（台账不对外开放，`/api/ledger/<id>/download` 现在返回 401）

> 注意：初始化那 8 份演示台账磁盘上没有实体文件，点下载会提示"文件在磁盘上不存在"。这是**故意的**——不把假文件伪装成真材料。你自己上传的文件能正常下载。

### 5.3 测文章草稿 / 发布

1. 后台 → 文章 → 展开「＋ 新建文章」，状态选「草稿」→ 保存
2. 前台「学习专栏」里**看不到**（匿名看不到草稿）
3. 后台列表点「发布」→ 前台立刻出现
4. 前台点开文章 → 阅读数 +1（真实写库）→ 点「记录学习」→ 学习时长入库
5. 回后台点「转草稿」→ 前台又看不到，`/api/articles/<id>` 匿名请求返回 404

### 5.4 测数据看板

1. 先记下看板上的数字
2. 去报名一个活动、打卡一篇文章
3. 回看板刷新 → 党员数、活动数、累计学习时长、月度柱状图都跟着变
4. 顶部标「测试数据」的是初始化样例；后台「清理演示数据」后该标签自动消失

### 5.5 跑自动化测试（建议）

```bash
# 后台冒烟测试：真实 HTTP，20 项检查
.venv/Scripts/python.exe -X utf8 tools/smoke_admin.py --base http://127.0.0.1:5000

# 方案 A 冒烟测试：微信设置 / 白名单 / 党费 / 组织关系转接，44 项检查
.venv/Scripts/python.exe -X utf8 tools/smoke_party_wx.py --base http://127.0.0.1:5000

# 页面截图（需要系统 Python 里装了 playwright）
"C:/Users/xinyi/AppData/Local/Programs/Python/Python310/python.exe" -X utf8 tools/screenshot.py --base http://127.0.0.1:5000 --admin
```

截图输出在 `docs/shots/`，前台按手机宽度（390×844）拍，后台按桌面宽度（1280×820）拍。

---

## 6. 在微信里打开（个人号）—— 已实际打通

**现状（已做完，不是计划）：** 公众号 **HXAI云** 的自定义菜单已经通过公众平台后台建好并发布成功，
3 个主菜单 + 8 个子菜单；因为未认证个人订阅号不能用「跳转网页」，所以每个子菜单用的是
**「发送消息 → 文字」**，文字里带系统网址，点网址打开系统。

菜单里的网址是**校园网内网地址** `http://192.168.x.x:5000/...`：手机连上和电脑**同一个校园 WiFi**
就能打开。代价有两条：① 用流量 / 在外网打不开（外网通道见 6.1）；② 校园网是 DHCP，
**电脑 IP 变了就要把 8 条菜单内容重发一次**（实测变过一次：`10.103.21.102` → `192.168.x.x`）。

菜单能否点开取决于本机在不在线。完整说明见
[公众号菜单与公网访问说明](docs/公众号菜单与公网访问说明.md)。

### 6.1 外网通道（SSH 反向隧道，备用）

本机在运营商大内网里，做不了端口映射，所以用 localhost.run 的 SSH 反向隧道给外网用：

```bash
cd /d/GZH/hxai_dangjian
bash tools/keep_online.sh &      # 保活：Flask 掉了拉起，隧道断了重连并更新 .tunnel_url
cat .tunnel_url                  # 当前公网域名
```

**但这个域名写不进菜单**：免费匿名隧道实测约 **20 分钟**断一次、每次换域名，
而菜单发布最长 **60 分钟**才生效，追不上。要用它必须先注册 localhost.run（**只需要一个邮箱**）拿固定域名，
或者等第二阶段学校域名。所以它只适合临时给手机看一眼，不适合写进菜单。

不知道现在该用哪个域名时，访问 `http://127.0.0.1:5000/healthz`，看返回里的
`public_base_url`——那就是菜单里应该写的地址（`.env` 的 `PUBLIC_BASE_URL` 没填时会自动读
`.tunnel_url`，所以本地测试不用手改 `.env`；第二阶段在 `.env` 填学校域名后会优先用学校域名）。

> Cloudflare 免费隧道在本网络环境下不可用（api.trycloudflare.com 被墙），已实测放弃。

### 6.2 手机怎么验证（现在就能做）

1. 手机连**和电脑同一个校园 WiFi**，浏览器打开 `http://192.168.x.x:5000/`（IP 可能变，用 `ipconfig` 或双击 `启动智慧党建.bat` 会打印当前地址）。
   电脑要开着、Flask 在跑；电脑侧已实测这条地址下 8 个页面全 200、静态资源正常。
2. 等菜单生效（最长 60 分钟）后，微信里点「党建学习 → 学习专栏」，
   公众号回一条带网址的文字消息，点网址即可打开。
3. 打不开的排查表见 [公众号菜单与公网访问说明](docs/公众号菜单与公网访问说明.md) 第六节。

### 6.3 为什么菜单只能发文字

微信要求「跳转网页」的链接内容必须属于当前公众号（本号已发表文章，或已配置网页授权/业务域名的自有域名），
配置这些域名需要**已认证**公众号。个人未认证订阅号填任何外部网址，保存都会报
**「发布失败，链接内容不属于当前公众号」**（已实测）。换成学校认证号后，
`/api/wechat/menu/push` 已经写好可以直接推「跳转网页」菜单。

### 6.4 服务器回调（`/wechat`）现在接不上真微信

微信要求回调 URL 是公网 HTTPS。本地可以自测签名逻辑（验签代码是真的，能跑通）：

先在 `.env` 里随便填一个 `WECHAT_TOKEN`（比如 `localtesttoken`），重启，然后：

```bash
.venv/Scripts/python.exe -X utf8 -c "
import hashlib
token, ts, nonce = 'localtesttoken', '1700000000', '12345'
sig = hashlib.sha1(''.join(sorted([token, ts, nonce])).encode()).hexdigest()
print(f'http://127.0.0.1:5000/wechat?signature={sig}&timestamp={ts}&nonce={nonce}&echostr=hello')
"
```

把打印出的地址贴到浏览器：正确签名会返回 `hello`，错误签名返回 `signature check failed`（403）。
实测这两条都符合预期，说明验签与被动回复逻辑是对的——但真正接微信要等学校域名。

### 6.5 想让「点一下菜单直接进系统」—— 只能做小程序

个人未认证订阅号的菜单**不能用「跳转网页」**（保存必报「发布失败，链接内容不属于当前公众号」）。
公众平台后台的「消息类型」里确实有**「跳转小程序」**这一项，但要先有一个**已注册并关联到本公众号的小程序**——
现在点「选择小程序」提示「暂无关联的小程序，请在“小程序-小程序管理”内进行关联」，说明本号还没有任何小程序。

为此本项目已经写好了小程序前端（`miniprogram/`，原生 WXML/WXSS/JS，后端一行不用改；
后端新加了签名 token 鉴权，小程序用 `X-Auth-Token` 头代替浏览器 cookie）。
接下来只差用户决定两件事：**是否现在注册个人小程序**、**小程序的后端连哪台机器**。
完整流程、材料清单、时间成本与风险见 [docs/小程序开发与发布.md](docs/小程序开发与发布.md)。

**已经做到哪一步（2026-10-25 实测）**：微信开发者工具装在 `D:\RJ\微信web开发者工具\`，用它「使用测试号」
（AppID `touristappid`，已写进 `miniprogram/project.config.json`）导入了 `miniprogram/`，模拟器里
首页 / 三会一课 / 活动报名 / 活动详情都**渲染出了后端数据库的真实数据**（含「测试数据」灰标签）；
工具栏「预览」也成功生成了真机二维码（约 25 分钟有效，微信扫码即可在手机上打开开发版）。
注意：`miniprogram/config.js` 里的 `API_BASE` 是校园网内网地址 `http://192.168.x.x:5000`，**手机要连同一个校园 WiFi**，本机 IP 变了就要改这个文件。

---

## 7. 第二阶段预留了什么

系统是按"以后要搬走"设计的，第二阶段不需要重写：

| 要换的东西 | 改哪里 | 现在的状态 |
|---|---|---|
| 数据库换 MySQL | `.env` 的 `DB_ENGINE=mysql` + `MYSQL_HOST/PORT/DB/USER/PASSWORD` | 代码已支持 `mysql+pymysql`；缺参数直接 `RuntimeError`，不静默回退到 SQLite |
| 域名 / 端口 | `.env` 的 `PUBLIC_BASE_URL` / `APP_HOST` / `APP_PORT` | 代码里没有写死 localhost |
| 公众号 AppID / AppSecret | **后台「微信设置」页填写**（存数据库，优先级高于 `.env`） | 现在是空的，`/api/wechat/status` 如实显示 `appid_configured=false` |
| 微信登录 | 后台把登录方式改成 `wechat` | 小程序 `jscode2session` 与公众号网页授权回调**代码都已实现**，缺的是小程序 AppID + 已备案 HTTPS 域名 |
| 多支部 / 多角色 | `models.Branch` + `User.branch_id/role` 已就位 | 现在 1 个支部；`super_admin` / `branch_admin` / `member` 三种角色已在用 |

---

## 8. 已知限制（如实说）

1. **没有微信网页授权**：第一阶段登录是本地测试账号，不是微信身份。
2. **没有自定义菜单推送**：个人号调 `menu/create` 返回 48001，系统如实把错误返回给调用方，没有假装成功。
3. **台账演示文件是占位**：初始化的 8 份台账磁盘无实体文件，点下载提示不存在；管理员上传的是真文件。
4. **文章正文是纯文本 / 简单 HTML**：后台是 textarea，没有富文本编辑器。够用，排版不如专业编辑器。
5. **没有生产部署配置**：没写 nginx / systemd / gunicorn 的现成文件，只在交接清单里列了需要学校提供什么。
6. **没做多支部隔离**：数据结构支持，查询没按支部过滤。
7. **上传文件只校验扩展名与大小**：没有病毒扫描、没有图片压缩。
8. **公众号菜单只能发文字消息**：未认证个人订阅号不能用「跳转网页」（实测报「链接内容不属于当前公众号」），
   所以菜单点开后还要再点一次文字里的网址。
9. **公网地址是临时隧道**：localhost.run 免费版域名每次重连都会变，变了要重新发布菜单；
   本机必须开机联网，外网才打得开。
10. **`.lhr.life` 是未备案的境外域名**：微信内置浏览器可能提示风险，但不影响打开。
    上面 8–10 三条在第二阶段换成学校服务器 + 已备案域名后全部消失。
11. **微信参数现在是空的**：后台「微信设置」页显示「未配置」，所以前台登录页写的是「还没有配置微信公众号 / 小程序的 AppID 与 AppSecret」。填入真实 AppID 后界面会自动变成微信登录入口。
12. **小程序还没发布**：前端 13 个页面（`miniprogram/`）已写好并在微信开发者工具里用测试号跑通（渲染真实接口数据、可生成真机预览码），但**还没注册真实小程序**，`config.js` 指向的是校园网内网地址，正式发布要换已备案 HTTPS 域名。
13. **党费不是支付**：只登记缴纳情况，没有在线收款、没有对账接口。
14. **白名单关掉就等于开放注册**：`whitelist_enabled=0` 时任何微信都能自动建号，生产环境不要关。

## 9. 方案 A：微信设置 / 小程序登录 / 党费 / 组织关系转接

这一节是后来照着开源项目调研结论补的（调研报告见 [docs/参考项目调研.md](docs/参考项目调研.md)）。
做法是**借鉴思路、不搬代码**。四件事：

### 9.1 微信参数改成在后台填写（存数据库）

- 表：`sys_setting`；逻辑：`backend/settings_store.py`
- 页面：`/admin/wechat` —— 公众号 4 项 + 小程序 2 项 + 登录方式 + 白名单开关 + 网页授权 scope + 首页公告
- 密钥在页面上只显示脱敏值（`secr****56`），**密文输入框留空表示不改**
- 取值优先级：**后台填的 > `.env` > 代码默认**
- 页面还自动算出微信要填的回调地址：`服务器配置 URL = <公网地址>/wechat`、`网页授权回调 = <公网地址>/login?mode=wechat`
- 「测试参数」「推送菜单」两个按钮会真的请求微信：个人号推菜单返回 **48001**，页面**原样显示**并说明这是微信权限限制

> 好处：本机 `.env` 受安全策略保护改不动的问题绕开了；第二阶段换学校号只需在页面上重填一遍。

### 9.2 微信登录 + 白名单

- 接口：`POST /api/auth/wechat-login`，`type` 支持 `wxapp`（小程序 code）、`oauth`（网页授权 code）、`dev_openid`（本地联调）
- 代码：`backend/wechat.py` 的 `jscode2session()` / `oauth_access_token()` / `oauth_userinfo()`
- 白名单：`/admin/whitelist`。可以先只填**姓名 + 手机号**、openid 留空，本人首次微信登录时自动补全并建号
- 拒绝逻辑如实返回：不在白名单 `403 not_in_whitelist`、被停用 `whitelist_disabled`、重复绑定 openid `409`
- 登录模式：`test`（默认，仅测试账号）/ `both` / `wechat`（仅微信）
- **本地怎么试**：`/login` → 展开「开发联调：手工提供 openid（非真实微信授权）」→ 填 openid → 提交。
  返回体和页面上都会写明这是**手工提供的 openid，不是真实微信授权**
- 完整说明见 [docs/微信设置与小程序登录.md](docs/微信设置与小程序登录.md)

### 9.3 党费

- 表：`party_due`（一人一期间一条，`period` 形如 `2026-10`）
- 后台 `/admin/dues`：按期间批量生成应缴（重复会跳过）、手工登记、标记已缴 / 改回未缴、删除、按期间查看汇总
- 前台「我的」页看自己的明细；数据看板新增「党费缴纳情况」面板（已缴人次 / 未缴人次 / 缴费率 / 已收金额 + 最近 6 个期间走势）
- 缴费率口径写在界面上：**缴费率 =（已缴 + 补缴）记录数 ÷ 应缴记录总数**，金额同样来自数据库，没有写死数字
- **注意**：这里只登记"谁交了、交了多少"，**没有在线支付**（你明确说了不要支付功能）

### 9.4 组织关系转接

- 表：`org_transfer`（转入 / 转出、原单位、目标单位、原因、状态、审核人、审核意见、审核时间）
- 党员在前台「我的 → 我的组织关系」提交申请（已有一条待审核时再提交返回 409）
- 支部管理员在 `/admin/transfers` 审核通过 / 驳回，前台立刻能看到结果

### 9.5 方案 A 新增的路由（共 83 条路由）

```
/admin/wechat            /admin/wechat/test      /admin/wechat/menu
/admin/whitelist         /admin/whitelist/<id>/update|toggle|delete
/admin/dues              /admin/dues/generate    /admin/dues/<id>/status|delete
/admin/transfers         /admin/transfers/<id>/review|delete
/api/auth/wechat-login   /api/auth/bind-openid
/api/dues/my             /api/dues/summary       /api/stats/dues
/api/transfers           /api/transfers/my
```

---

## 安全注意

- `.env` 里有 `SECRET_KEY` 和管理员密码，**不要提交到 git**（`.gitignore` 已排除）。
- 生产环境务必改掉默认的 `ADMIN_PASSWORD` 和 `SECRET_KEY`。
- 上传目录 `data/uploads/` 不要暴露成静态目录（现在通过 `/api/ledger/<id>/download` 带权限下发）。
