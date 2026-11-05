// 党建风采（图墙）：数据解析逻辑在 utils/gallery.js（解析后端 /gallery 的 HTML）
const gallery = require('../../utils/gallery.js');

Page({
  data: {
    list: [],
    loading: true,
    errMsg: ''
  },

  onLoad() { this.load(); },

  onPullDownRefresh() {
    this.load().then(() => wx.stopPullDownRefresh());
  },

  load() {
    this.setData({ loading: true, errMsg: '' });
    return gallery.fetchGallery().then((list) => {
      this.setData({ loading: false, list: list });
    }).catch(() => {
      this.setData({ loading: false, list: [], errMsg: '风采页加载失败：请检查接口地址与网络' });
    });
  }
});
