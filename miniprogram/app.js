// app.js —— 小程序入口
const store = require('./utils/store.js');

App({
  globalData: {
    // 自定义 tabBar 当前选中项：0 首页 / 1 党建学习 / 2 组织生活 / 3 支部风采
    tabIndex: 0,
    // 说明：tab 页之间不能用 URL 传参（wx.switchTab 不支持 query），
    // 所以「跳转到学习专栏并指定分类 / 带入搜索词」用这两个全局变量传递，
    // 目标页 onShow 读取后立即清空（置 null），避免下次进入被重复应用。
    studyCategory: null,   // 分类 code：'' 表示全部，cloud=云党课，history=党史学习
    studyQuery: null,      // 搜索关键词
    user: null
  },
  onLaunch() {
    // 恢复上次登录的用户信息；登录 token 单独存放，由 utils/api.js 自动带在请求头里
    this.globalData.user = store.getUser();
  }
});
