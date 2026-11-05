// 支部风采（tabBar 页）：党建风采 / 数据看板 入口 + 几张风采图预览
// 风采数据来自 utils/gallery.js（解析后端服务端渲染的 /gallery 页面）
const api = require('../../utils/api.js');
const gallery = require('../../utils/gallery.js');

Page({
  data: {
    preview: [],
    stats: null,
    loading: true
  },

  onLoad() { this.load(); },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 3 });
    }
  },

  onPullDownRefresh() {
    this.load().then(() => wx.stopPullDownRefresh());
  },

  load() {
    this.setData({ loading: true });
    return Promise.all([
      gallery.fetchGallery().catch(() => []),
      api.get('/api/stats/overview', {}, { silent: true, noRedirect: true }).catch(() => null)
    ]).then((rs) => {
      this.setData({
        loading: false,
        preview: (rs[0] || []).slice(0, 3),
        stats: (rs[1] && rs[1].data) || null
      });
    });
  },

  go(e) {
    wx.navigateTo({ url: e.currentTarget.dataset.url });
  }
});
