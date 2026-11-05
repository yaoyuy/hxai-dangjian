// 活动详情 + 报名 / 取消报名
// 接口：GET /api/activities/<id>、POST /api/activities/<id>/enroll、POST /api/activities/<id>/cancel
const api = require('../../utils/api.js');
const auth = require('../../utils/auth.js');

// 与后端 backend/models.py 的 Activity.STATUS_LABELS / KIND_LABELS 保持一致（只用于中文显示）
const STATUS_LABELS = { open: '进行中', closed: '已截止', finished: '已完成' };
const KIND_LABELS = { meeting: '三会一课', party_day: '主题党日', volunteer: '志愿服务', study: '集中学习' };

Page({
  data: {
    id: 0,
    a: null,
    contentIsHtml: false,
    paragraphs: [],
    statusText: '',
    loading: true,
    errMsg: '',
    acting: false,
    enrolled: false,
    full: false
  },

  onLoad(options) {
    const id = Number(options && options.id) || 0;
    if (!id) {
      this.setData({ loading: false, errMsg: '缺少活动 id，请从列表进入' });
      return;
    }
    this.setData({ id: id });
    this.load();
  },

  onPullDownRefresh() {
    this.load().then(() => wx.stopPullDownRefresh());
  },

  load() {
    this.setData({ loading: true, errMsg: '' });
    return api.get('/api/activities/' + this.data.id).then((res) => {
      const a = res.data || {};
      const content = a.content || '';
      const isHtml = /<[a-z][\s\S]*>/i.test(content);
      this.setData({
        loading: false,
        a: a,
        contentIsHtml: isHtml,
        paragraphs: isHtml ? [] : content.split(/\n+/).filter((s) => s.trim()),
        statusText: STATUS_LABELS[a.status] || a.status || '',
        enrolled: !!a.enrolled,
        full: !!a.full
      });
    }).catch((err) => {
      this.setData({ loading: false, errMsg: (err && err.msg) || '活动加载失败' });
    });
  },

  // 报名：需要登录；超员 / 已截止 / 重复报名都由后端返回真实错误
  doEnroll() {
    if (!auth.requireLogin()) return;
    this.setData({ acting: true });
    api.post('/api/activities/' + this.data.id + '/enroll', {}).then((res) => {
      this.setData({ acting: false });
      wx.showToast({ title: (res && res.msg) || '报名成功', icon: 'none' });
      this.load();
    }).catch(() => this.setData({ acting: false }));
  },

  doCancel() {
    if (!auth.requireLogin()) return;
    wx.showModal({
      title: '取消报名',
      content: '确定取消这次活动的报名吗？',
      success: (r) => {
        if (!r.confirm) return;
        this.setData({ acting: true });
        api.post('/api/activities/' + this.data.id + '/cancel', {}).then((res) => {
          this.setData({ acting: false });
          wx.showToast({ title: (res && res.msg) || '已取消报名', icon: 'none' });
          this.load();
        }).catch(() => this.setData({ acting: false }));
      }
    });
  },

  goLogin() { wx.navigateTo({ url: '/pages/login/login' }); }
});
