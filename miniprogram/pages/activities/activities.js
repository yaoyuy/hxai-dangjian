// 活动报名列表：按活动类型筛选
// 接口：GET /api/activities?kind=
const api = require('../../utils/api.js');

// 与后端 backend/models.py 的 Activity.STATUS_LABELS / KIND_LABELS 保持一致（只用于中文显示）
const STATUS_LABELS = { open: '进行中', closed: '已截止', finished: '已完成' };
const KIND_LABELS = { meeting: '三会一课', party_day: '主题党日', volunteer: '志愿服务', study: '集中学习' };

// 类型 chip：value 是后端真实枚举，name 与后端中文名一致
const KINDS = [
  { value: '', name: '全部' },
  { value: 'meeting', name: '三会一课' },
  { value: 'party_day', name: '主题党日' },
  { value: 'volunteer', name: '志愿服务' },
  { value: 'study', name: '集中学习' }
];

Page({
  data: {
    kinds: KINDS,
    kind: '',
    list: [],
    loading: true,
    errMsg: ''
  },

  onLoad() { this.load(); },

  onPullDownRefresh() {
    this.load().then(() => wx.stopPullDownRefresh());
  },

  pickKind(e) {
    const v = e.currentTarget.dataset.value || '';
    if (v === this.data.kind) return;
    this.setData({ kind: v });
    this.load();
  },

  load() {
    this.setData({ loading: true, errMsg: '' });
    const data = this.data.kind ? { kind: this.data.kind } : {};
    return api.get('/api/activities', data).then((res) => {
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
  }
});
