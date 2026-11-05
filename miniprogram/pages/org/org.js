// 组织生活（tabBar 页）：三会一课 / 活动报名 / 电子台账 三个入口 + 最近活动
// 接口：GET /api/activities（最近活动）、GET /api/stats/overview（顶部数字）
const api = require('../../utils/api.js');
const STATUS_LABELS = { open: '进行中', closed: '已截止', finished: '已完成' };
Page({
  data: {
    ov: null,
    recent: [],
    loading: true
  },

  onLoad() { this.load(); },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 2 });
    }
  },

  onPullDownRefresh() {
    this.load().then(() => wx.stopPullDownRefresh());
  },

  load() {
    this.setData({ loading: true });
    const safe = (p) => p.catch(() => null);
    return Promise.all([
      safe(api.get('/api/stats/overview', {}, { silent: true, noRedirect: true })),
      safe(api.get('/api/activities', {}, { silent: true, noRedirect: true }))
    ]).then((rs) => {
      const list = ((rs[1] && rs[1].data) || []).slice(0, 3).map((it) => Object.assign({}, it, {
        statusText: STATUS_LABELS[it.status] || it.status || ''
      }));
      this.setData({
        loading: false,
        ov: (rs[0] && rs[0].data) || null,
        recent: list
      });
    });
  },

  go(e) {
    wx.navigateTo({ url: e.currentTarget.dataset.url });
  }
});
