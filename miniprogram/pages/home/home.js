// 首页：宣传图占位 + 搜索框 + 最近文章列表
// 数据来源：GET /api/articles?size=6（最近已发布文章）。
// 说明：后端公开配置 /api/auth/config 里没有「首页公告」字段（settings_store.public_config()
//      只返回登录方式相关字段），所以首页不再显示公告横幅，避免引用不存在的字段。
const api = require('../../utils/api.js');

Page({
  data: {
    // 宣传图占位文案（当前没有宣传图资源，先用渐变横幅占位）
    heroTitle: 'HXAI云 · 智慧党建',
    heroDesc: '学习教育 · 组织生活 · 支部风采',
    keyword: '',
    loading: true,
    first: null,         // 最近一篇文章（大图卡展示）
    rest: [],            // 其余文章
    errMsg: ''
  },

  onLoad() {
    this.loadArticles();
  },

  onShow() {
    // 自定义 tabBar 选中态：0 = 首页
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 0 });
    }
  },

  onPullDownRefresh() {
    this.loadArticles().then(() => wx.stopPullDownRefresh());
  },

  loadArticles() {
    this.setData({ loading: true, errMsg: '' });
    return api.get('/api/articles', { size: 6 }).then((res) => {
      const list = (res.data || []).slice();
      this.setData({
        loading: false,
        first: list.length ? list[0] : null,
        rest: list.length > 1 ? list.slice(1) : []
      });
    }).catch((err) => {
      this.setData({ loading: false, errMsg: (err && err.msg) || '文章加载失败，请下拉重试' });
    });
  },

  onSearchInput(e) { this.setData({ keyword: e.detail.value }); },

  // 搜索：学习专栏是 tabBar 页，wx.switchTab 不支持 URL 参数，
  // 所以关键词通过 globalData.studyQuery 传给 pages/study/study
  doSearch(e) {
    const kw = ((e.detail && e.detail.value) || this.data.keyword || '').trim();
    getApp().globalData.studyQuery = kw || null;
    wx.switchTab({ url: '/pages/study/study' });
  },

  goArticle(e) {
    wx.navigateTo({ url: '/pages/article/article?id=' + e.currentTarget.dataset.id });
  },

  goPage(e) {
    const url = e.currentTarget.dataset.url;
    if (url === '/pages/study/study') { wx.switchTab({ url: url }); return; }
    wx.navigateTo({ url: url });
  }
});
