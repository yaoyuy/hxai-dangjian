# HXAI 云 · 智慧党建 —— 微信小程序前端（miniprogram）

本目录是**智慧党建系统的微信小程序端**，使用**微信原生** WXML / WXSS / JS 编写：
不依赖任何前端框架（不用 uni-app / Taro / mpvue），**不需要 npm、不需要 Node 构建**，
后端是已经跑起来的 Flask + SQLite 服务，**本目录没有修改后端任何一行代码、也没有新增后端接口**。

---

## 一、用微信开发者工具打开

1. 打开「微信开发者工具」→ **导入项目**。
2. **目录选择本目录**：`D:\GZH\hxai_dangjian\miniprogram`（注意是 miniprogram 这一层，不是仓库根目录）。
3. AppID 选择「**测试号**」，或先随便填（见第二节）。
4. 后端要处于运行状态（Flask 默认监听 `http://192.168.x.x:5000`）。

> 如果你的后端不是跑在 192.168.x.x:5000，请改 `config.js` 里的 `API_BASE`，
> 或在开发者工具控制台执行一次 `wx.setStorageSync('api_base', 'http://你的地址:端口')` 临时覆盖。

## 二、AppID 与 project.config.json

`project.config.json` 里的 `appid` 目前是占位值：

```json
"appid": "touristappid"
```

- `touristappid` 是**游客/测试模式**，可以打开体验、真机调试，但**不能上传体验版**。
- 你在微信公众平台注册小程序（个人或企业主体）之后，会在「开发管理 → 开发设置」看到真实 AppID，
  把它替换到 `project.config.json` 的 `appid` 字段即可（`projectname` 保持 `hxai-dangjian`）。

## 三、必须勾选「不校验合法域名」

当前接口地址是 **http 明文 IP**，微信正式环境不允许请求。所以开发/体验阶段必须在开发者工具里：

> **右上角「详情」→「本地设置」→ 勾选「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」**

否则所有请求都会失败（`request:fail url not in domain list`）。`project.config.json` 里已经写了
`"urlCheck": false`，但**以工具里的勾选状态为准**，换机器时要重新勾一次。

> 真机预览/真机调试也受限：真机默认**不受**「不校验合法域名」影响，如果真机连不上 http 接口，
> 请用「真机调试」模式，或先完成第五节的 HTTPS 域名替换。

## 四、预览 / 真机调试 / 体验版

| 目标 | 操作 | 前提 |
| --- | --- | --- |
| 模拟器预览 | 工具里直接看，改代码自动刷新 | 勾了「不校验合法域名」 |
| 真机预览 | 工具栏「预览」→ 手机扫码 | AppID 可用；http 接口可能被拦，建议「真机调试」 |
| 真机调试 | 工具栏「真机调试」→ 扫码 | 同上，可在手机上看到 console |
| 上传体验版 | 工具栏「上传」→ 填版本号 → 公众平台「版本管理」设为体验版 | **必须是真实 AppID**，http 接口会被拦（需先做第五节） |
| 正式发布 | 公众平台「提交审核」→ 审核通过后「发布」 | 见第五节（备案 + HTTPS 域名） |

## 五、正式发布前必须做的事（重要）

1. **小程序备案**：在微信公众平台完成小程序备案（ICP 备案），未备案无法发布。
2. **换 HTTPS 域名**：把 `config.js` 里的 `API_BASE` 从
   `http://192.168.x.x:5000` 改为**已备案的 HTTPS 域名**，例如：

   ```js
   module.exports = {
     API_BASE: 'https://dangjian.example.com'   // 已 ICP 备案 + 已配置 HTTPS 证书
   };
   ```

3. **在公众平台配置服务器域名**：「开发管理 → 开发设置 → 服务器域名」，
   把该 HTTPS 域名同时加入 **request 合法域名** 和 **downloadFile 合法域名**
   （电子台账的「查看/下载」用的是 `wx.downloadFile`，必须加 downloadFile 白名单）。
4. 之后才能去掉「不校验合法域名」的勾选，上传体验版 / 提交审核。

## 六、登录说明（不伪造微信身份）

- 本项目后端**同时支持微信登录和本地测试账号登录**，登录方式由后端配置决定，
  小程序启动时读 `GET /api/auth/config`，登录页按后端返回的
  `login_mode / test_login_allowed / wechat_login_allowed / whitelist_enabled` 展示。
- **本地测试账号登录**成功后，后端原文案是「**测试登录，非微信身份**」，
  登录页与「我的」页都会**原样展示这句话**，小程序不会伪造 openid，也不会假装已获得微信授权。
- 后端默认测试账号（来自后端仓库 README）：

  | 账号 | 密码 | 角色 |
  | --- | --- | --- |
  | `admin` | `Admin@123456` | 超级管理员 |
  | `zhangsan` / `lisi` / `wangwu` / `zhaoliu` / `sunqi` | `Test@123456` | 普通党员 |

- 「微信一键登录」按钮走 `wx.login` 拿 code → `POST /api/auth/wechat-login`（载荷 `{type:'wxapp', code}`）。
  若你的 openid 不在后端白名单，后端会返回 403 `not_in_whitelist`，
  小程序会**原样提示后端的 msg**（不会假装登录成功）。

## 七、目录结构

```
miniprogram/
├── app.js / app.json / app.wxss      # 全局逻辑 / 页面与 tabBar 配置 / 全局样式
├── config.js                         # API_BASE（开发期临时地址，见注释）
├── project.config.json / sitemap.json
├── custom-tab-bar/                   # 自定义 tabBar（主菜单 + 弹出子菜单）
├── utils/
│   ├── store.js                      # 本地缓存（token / 用户 / 配置 / api_base 覆盖）
│   ├── api.js                        # 统一请求：X-Auth-Token、ok:false 提示、401 跳登录
│   ├── auth.js                       # 登录态、测试登录、微信登录、requireLogin
│   └── gallery.js                    # 党建风采数据（解析后端 /gallery 页面）
└── pages/                            # 13 个页面，每页 4 个文件
    ├── home/       首页（宣传图占位 + 搜索 + 最近文章）
    ├── study/      学习专栏（分类 chip + 文章列表）
    ├── article/    文章详情（+ 记录学习时长）
    ├── meetings/   三会一课（kind=meeting）
    ├── activities/ 活动报名列表
    ├── activity/   活动详情（报名 / 取消报名）
    ├── ledger/     电子台账（分类 + 搜索 + 文件下载预览）
    ├── gallery/    党建风采图墙
    ├── dashboard/  数据看板（柱状图用 view 高度模拟，未用第三方图表库）
    ├── org/        组织生活（tab 页：三个功能入口 + 最近活动）
    ├── style/      支部风采（tab 页：两个入口 + 风采预览）
    ├── me/         我的（登录状态、党费、组织关系、退出）
    └── login/      登录（测试账号 + 微信一键登录）
```

## 八、页面 ↔ 后端接口对应关系

所有数据都来自下表这些**真实接口**，页面上不存在写死的业务数字（只有字段缺省兜底与空态文案）。

| 页面 | 文件 | 调用的后端接口 |
| --- | --- | --- |
| 首页 | pages/home/home | `GET /api/auth/config`、`GET /api/articles?size=6` |
| 学习专栏 | pages/study/study | `GET /api/categories`、`GET /api/articles?category=&q=&size=` |
| 文章详情 | pages/article/article | `GET /api/articles/<id>`、`POST /api/articles/<id>/study` |
| 三会一课 | pages/meetings/meetings | `GET /api/activities?kind=meeting` |
| 活动报名 | pages/activities/activities | `GET /api/activities?kind=` |
| 活动详情 | pages/activity/activity | `GET /api/activities/<id>`、`POST /api/activities/<id>/enroll`、`POST /api/activities/<id>/cancel` |
| 电子台账 | pages/ledger/ledger | `GET /api/ledger/categories`、`GET /api/ledger?category=&q=`、`GET /api/ledger/<id>/download`（wx.downloadFile + X-Auth-Token） |
| 党建风采 | pages/gallery/gallery | `GET /gallery`（服务端渲染 HTML，用正则解析，见下） |
| 数据看板 | pages/dashboard/dashboard | `GET /api/stats/overview`、`/api/stats/monthly`、`/api/stats/members`、`/api/stats/learning`、`/api/stats/dues`、`/api/stats/activity-participation` |
| 组织生活 | pages/org/org | `GET /api/stats/overview`、`GET /api/activities` |
| 支部风采 | pages/style/style | `GET /gallery`（解析）、`GET /api/stats/overview` |
| 我的 | pages/me/me | `GET /api/auth/me`、`GET /api/dues/my`、`GET /api/transfers/my`、`POST /api/transfers`、`POST /api/auth/logout`（本地清登录态） |
| 登录 | pages/login/login | `GET /api/auth/config`、`POST /api/auth/login`、`POST /api/auth/wechat-login` |

统一约定：所有 `/api/*` 接口都返回 `{ok:true, data:...}` 或 `{ok:false, msg:"..."}`；
小程序在 `utils/api.js` 里统一处理——自动带 `X-Auth-Token`，`ok:false` 直接 toast 后端的 `msg`，
401 清 token 并跳登录页。**绝不把失败当成功展示。**

## 九、自定义 tabBar 与「子菜单」的实现说明

需求样例是：底部 3 个主菜单「党建学习 / 组织生活 / 支部风采」，点主菜单在 tabBar 上方**弹出子菜单**，
点子菜单项再进入具体页面。小程序原生 tabBar 做不到「弹出子菜单」，因此用 `tabBar.custom = true` + `custom-tab-bar/` 组件实现：

- `app.json` 的 `tabBar.list` 有 4 项：`pages/home/home`（首页）、`pages/study/study`（党建学习）、
  `pages/org/org`（组织生活）、`pages/style/style`（支部风采）。
- 组件左侧是「首页」，点击 `wx.reLaunch` 回首页；右侧三个主菜单点击**展开/收起子菜单浮层**：
  - 党建学习 → 学习专栏 `/pages/study/study`、云党课 `/pages/study/study?category=cloud`、党史学习 `/pages/study/study?category=history`
  - 组织生活 → 三会一课 `/pages/meetings/meetings`、活动报名 `/pages/activities/activities`、电子台账 `/pages/ledger/ledger`
  - 支部风采 → 党建风采 `/pages/gallery/gallery`、数据看板 `/pages/dashboard/dashboard`、我的 `/pages/me/me`
- 选中态：每个 tab 页在自己的 `onShow` 里调用 `this.getTabBar().setData({selected:N})`
  （0 首页 / 1 党建学习 / 2 组织生活 / 3 支部风采）。

### ⚠️ 与题目原文的一处偏差（有意为之，必须说明）

题目原文要求子菜单项用 `wx.navigateTo` 跳转。但 **`pages/study/study` 是 tabBar 页**，
`wx.navigateTo` 跳到 tabBar 页**一定失败**（报 `navigateTo:fail can not navigateTo a tabbar page`）。
因此实际实现是：

- 子菜单里的「学习专栏 / 云党课 / 党史学习」用 **`wx.switchTab`** 跳到 `pages/study/study`，
  分类通过 `getApp().globalData.studyCategory`（`cloud` / `history` / `''`）传递
  ——因为 `wx.switchTab` 也**不支持 query 参数**（题目里的 `?category=cloud` 实际传不进去）。
- 其余普通页面（三会一课、活动报名、电子台账、党建风采、数据看板、我的）仍按原要求用 `wx.navigateTo`。
- 相关原因已写在 `custom-tab-bar/index.js` 与 `pages/study/study.js` 的中文注释里。

## 十、其他实现说明

- **党建风采页**：优先走后端的 JSON 接口 `GET /api/gallery`（返回 `{ok,data,total}`，
  每项含 `id/title/image_url/description/created_at/is_demo`）；
  若该接口不可用（例如连的是老版本后端，返回 404），`utils/gallery.js` 会自动退回解析
  服务端渲染页 `GET /gallery` 的 HTML（`dataType:'text'` + 正则解析 `<figure>`/`<figcaption>`）。
  图片地址为空时按后端逻辑显示红金渐变占位，不做假图。
- **「测试数据」灰标签**：接口返回 `is_demo === true` 的记录（文章、活动、台账文件、党费/组织关系记录）
  都会显示灰色小标签「测试数据」。
- **活动人数**：`capacity === 0` 表示**不限人数**，页面显示「不限人数」，不会显示成 `X/0`；
  参与率在 `capacity === 0` 时后端返回 `null`，页面显示「—」。
- **文章正文**：后端 `content` 存的是 HTML 字符串，页面用 `rich-text` 渲染；若是纯文本则按换行分段。
  视频课（`media_type='video'`）只有在后端给出 `video_url` 时才渲染播放器，否则如实提示「后端未提供视频地址」。
- **电子台账下载**：`GET /api/ledger/<id>/download` 需要登录，小程序用 `wx.downloadFile` 手动带上
  `X-Auth-Token`，再用 `wx.openDocument` 预览；`.pptx/.docx/.xlsx/.pdf` 等可预览，其它类型如实提示在电脑端下载。
- **错误处理**：接口失败一律显示后端 `msg` 或「加载失败」空态，不做假数据兜底。
