// 三会一课：按 kind=meeting 拉取会议/党课活动
// 接口：GET /api/activities?kind=meeting
const api = require('../../utils/api.js');

// 与后端 backend/models.py 的 Activity.STATUS_LABELS / KIND_LABELS 保持一致（只用于中文显示）
const STATUS_LABELS = { open: '进行中', closed: '已截止', finished: '已完成' };
const KIND_LABELS = { meeting: '三会一课', party_day: '主题党日', volunteer: '志愿服务', study: '集中学习' };

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
    return api.get('/api/activities', { kind: 'meeting' }).then((res) => {
      const list = (res.data || []).map((it) => Object.assign({}, it, {
        statusText: STATUS_LABELS[it.status] || it.status || '',
        kindText: it.kind_label || KIND_LABELS[it.kind] || it.kind || ''
      }));
      this.setData({ loading: false, list: list });
    }).catch((err) => {
      this.setData({ loading: false, list: [], errMsg: (err && err.msg) || '活动加载失败' });
    });
  },

  goDetail(e) {
    wx.navigateTo({ url: '/pages/activity/activity?id=' + e.currentTarget.dataset.id });
  },

  goActivities() {
    wx.navigateTo({ url: '/pages/activities/activities' });
  }
});
