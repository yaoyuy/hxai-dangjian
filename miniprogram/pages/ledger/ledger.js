// 电子台账：分类 chip + 搜索 + 文件列表 + 下载/预览
// 接口：GET /api/ledger/categories、GET /api/ledger?category=&q=、GET /api/ledger/<id>/download
const api = require('../../utils/api.js');
const store = require('../../utils/store.js');
const auth = require('../../utils/auth.js');

// 小程序 wx.openDocument 能直接预览的类型；其它类型给出如实提示
const OPENABLE = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'];
const ALL = { name: '全部', count: null };

Page({
  data: {
    cats: [ALL],
    activeCat: '',
    keyword: '',
    list: [],
    total: 0,
    allTotal: 0,
    loading: true,
    errMsg: '',
    downloading: 0
  },

  onLoad() {
    this.loadCats();
    this.load();
  },

  onPullDownRefresh() {
    this.load().then(() => wx.stopPullDownRefresh());
  },

  loadCats() {
    api.get('/api/ledger/categories', {}, { silent: true }).then((res) => {
      this.setData({ cats: [ALL].concat(res.data || []) });
    }).catch(() => {});
  },

  pickCat(e) {
    const name = e.currentTarget.dataset.name || '';
    if (name === this.data.activeCat) return;
    this.setData({ activeCat: name });
    this.load();
  },

  onKeyword(e) { this.setData({ keyword: e.detail.value }); },
  doSearch() { this.load(); },

  load() {
    this.setData({ loading: true, errMsg: '' });
    return api.get('/api/ledger', {
      category: this.data.activeCat || '',
      q: (this.data.keyword || '').trim()
    }).then((res) => {
      this.setData({
        loading: false,
        list: res.data || [],
        total: res.total || 0,
        allTotal: res.all_total || 0
      });
    }).catch((err) => {
      this.setData({ loading: false, list: [], errMsg: (err && err.msg) || '台账加载失败' });
    });
  },

  // 下载并预览：下载接口需要登录（无 token 返回 401），所以手动带 X-Auth-Token
  download(e) {
    const id = e.currentTarget.dataset.id;
    const ext = String(e.currentTarget.dataset.ext || '').toLowerCase();
    if (!auth.requireLogin()) return;
    if (OPENABLE.indexOf(ext) < 0) {
      wx.showToast({ title: '小程序无法直接预览 .' + ext + '，请在电脑端打开下载', icon: 'none' });
      return;
    }
    const url = api.getBase() + '/api/ledger/' + id + '/download';
    this.setData({ downloading: id });
    wx.downloadFile({
      url: url,
      header: { 'X-Auth-Token': store.getToken() },
      success: (res) => {
        if (res.statusCode !== 200) {
          this.setData({ downloading: 0 });
          wx.showToast({ title: '下载失败（HTTP ' + res.statusCode + '），请确认已登录', icon: 'none' });
          return;
        }
        wx.openDocument({
          filePath: res.tempFilePath,
          fileType: ext,
          showMenu: true,
          success: () => this.setData({ downloading: 0 }),
          fail: () => {
            this.setData({ downloading: 0 });
            wx.showToast({ title: '预览失败，可在开发者工具里用「保存文件」查看', icon: 'none' });
          }
        });
      },
      fail: () => {
        this.setData({ downloading: 0 });
        wx.showToast({ title: '下载失败：请检查接口地址与网络', icon: 'none' });
      }
    });
  }
});
