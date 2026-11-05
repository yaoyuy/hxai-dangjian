// custom-tab-bar/index.js —— 自定义 tabBar
// 结构：左侧「首页」，右侧三个主菜单「党建学习 / 组织生活 / 支部风采」。
// 点主菜单 → 在 tabBar 上方弹出子菜单浮层（再点收起）；点子菜单项进对应页面。
//
// 注意：小程序 wx.navigateTo 不能跳转 tabBar 页面（会报
// "can not navigateTo a tabbar page"），所以：
//   - 目标页是 tab 页（学习专栏 /pages/study/study）→ 用 wx.switchTab；
//     分类参数（云党课 / 党史学习）用 app.globalData.studyCategory 传递，
//     因为 wx.switchTab 不支持 URL query；
//   - 目标页是普通页（三会一课 / 活动报名 / 电子台账 / 党建风采 / 数据看板 / 我的）
//     → 按题目要求用 wx.navigateTo。
const TAB_PAGE_INDEX = {
  '/pages/home/home': 0,
  '/pages/study/study': 1,
  '/pages/org/org': 2,
  '/pages/style/style': 3
};

Component({
  data: {
    selected: 0,   // 当前选中的 tab（各 tab 页 onShow 里用 this.getTabBar().setData 更新）
    current: '',   // 当前展开的主菜单 key，'' 表示收起
    menus: [
      {
        key: 'study',
        name: '党建学习',
        page: '/pages/study/study',
        items: [
          { name: '学习专栏', url: '/pages/study/study', category: '' },
          { name: '云党课', url: '/pages/study/study', category: 'cloud' },
          { name: '党史学习', url: '/pages/study/study', category: 'history' }
        ]
      },
      {
        key: 'life',
        name: '组织生活',
        page: '/pages/org/org',
        items: [
          { name: '三会一课', url: '/pages/meetings/meetings', category: '' },
          { name: '活动报名', url: '/pages/activities/activities', category: '' },
          { name: '电子台账', url: '/pages/ledger/ledger', category: '' }
        ]
      },
      {
        key: 'style',
        name: '支部风采',
        page: '/pages/style/style',
        items: [
          { name: '党建风采', url: '/pages/gallery/gallery', category: '' },
          { name: '数据看板', url: '/pages/dashboard/dashboard', category: '' },
          { name: '我的', url: '/pages/me/me', category: '' }
        ]
      }
    ]
  },

  methods: {
    // 点主菜单：展开 / 收起子菜单
    toggleMenu(e) {
      const key = e.currentTarget.dataset.key;
      this.setData({ current: this.data.current === key ? '' : key });
    },

    // 点遮罩收起
    closeMenu() {
      this.setData({ current: '' });
    },

    // 回首页（首页是 tab 页，用 reLaunch 保证不残留页面栈）
    goHome() {
      this.setData({ current: '' });
      wx.reLaunch({ url: '/pages/home/home' });
    },

    // 点子菜单项 / 子菜单顶部的「总览」
    goItem(e) {
      const url = e.currentTarget.dataset.url;
      const category = e.currentTarget.dataset.category || '';
      this.setData({ current: '' });
      if (!url) return;
      if (url === '/pages/study/study') {
        // 学习专栏是 tab 页：用全局变量带分类，再 switchTab
        getApp().globalData.studyCategory = category;
        wx.switchTab({ url: url });
        return;
      }
      if (TAB_PAGE_INDEX[url] !== undefined) {
        wx.switchTab({ url: url });
        return;
      }
      wx.navigateTo({ url: url });
    }
  }
});
