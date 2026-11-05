// 学习专栏（tabBar 页）：分类 chip + 文章列表
// 接口：GET /api/categories（分类，含已发布文章数）、GET /api/articles?category=&q=&size=
// 分类参数来源：custom-tab-bar 的子菜单（云党课 cloud / 党史学习 history）不能用
// wx.switchTab 传 query，所以通过 getApp().globalData.studyCategory 传入。
const api = require('../../utils/api.js');

const ALL = { code: '', name: '全部', count: null };

Page({
  data: {
    cats: [ALL],
    activeCode: '',
    activeName: '全部',
    keyword: '',
    list: [],
    total: 0,
    loading: true,
    errMsg: ''
  },

  onLoad() {
    this.loadCats();
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 1 });
    }
    // 接收其他页面通过全局变量传来的分类 / 搜索词（读后立即清空）
    const app = getApp();
    let changed = false;
    if (app.globalData.studyCategory !== null && app.globalData.studyCategory !== undefined) {
      const code = app.globalData.studyCategory || '';
      app.globalData.studyCategory = null;
      this.setData({ activeCode: code, keyword: '' });
      changed = true;
    }
    if (app.globalData.studyQuery !== null && app.globalData.studyQuery !== undefined) {
      const kw = app.globalData.studyQuery || '';
      app.globalData.studyQuery = null;
      this.setData({ keyword: kw, activeCode: '' });
      changed = true;
    }
    this.loadArticles().then(() => {
      if (changed || !this.data.list.length) this.syncActiveName();
    });
  },

  onPullDownRefresh() {
    this.loadArticles().then(() => wx.stopPullDownRefresh());
  },

  loadCats() {
    api.get('/api/categories', {}, { silent: true }).then((res) => {
      const cats = [ALL].concat(res.data || []);
      this.setData({ cats: cats });
      this.syncActiveName();
    }).catch(() => {});
  },

  syncActiveName() {
    const code = this.data.activeCode || '';
    const hit = (this.data.cats || []).filter((c) => (c.code || '') === code)[0];
    this.setData({ activeName: hit ? hit.name : (code || '全部') });
  },

  pickCat(e) {
    const code = e.currentTarget.dataset.code || '';
    if (code === this.data.activeCode) return;
    this.setData({ activeCode: code, keyword: '' });
    this.syncActiveName();
    this.loadArticles();
  },

  onKeyword(e) { this.setData({ keyword: e.detail.value }); },

  doSearch() {
    this.loadArticles();
  },

  loadArticles() {
    this.setData({ loading: true, errMsg: '' });
    return api.get('/api/articles', {
      category: this.data.activeCode || '',
      q: (this.data.keyword || '').trim(),
      size: 20
    }).then((res) => {
      const pg = res.pagination || {};
      this.setData({ loading: false, list: res.data || [], total: pg.total || 0 });
    }).catch((err) => {
      this.setData({ loading: false, list: [], errMsg: (err && err.msg) || '文章加载失败' });
    });
  },

  goArticle(e) {
    wx.navigateTo({ url: '/pages/article/article?id=' + e.currentTarget.dataset.id });
  }
});
