// 文章详情 + 「记录学习时长」
// 接口：GET /api/articles/<id>（content 为 HTML 字符串）、POST /api/articles/<id>/study
const api = require('../../utils/api.js');
const auth = require('../../utils/auth.js');

Page({
  data: {
    id: 0,
    a: null,
    contentIsHtml: false,
    paragraphs: [],
    loading: true,
    errMsg: '',
    submitting: false,
    myTotalMinutes: 0,
    recorded: false
  },

  onLoad(options) {
    const id = Number(options && options.id) || 0;
    if (!id) {
      this.setData({ loading: false, errMsg: '缺少文章 id，请从列表进入' });
      return;
    }
    this.setData({ id: id });
    this.load(id);
  },

  load(id) {
    this.setData({ loading: true, errMsg: '' });
    api.get('/api/articles/' + id).then((res) => {
      const a = res.data || {};
      const content = a.content || '';
      // 后端 content 存的是 HTML（例如 <p>…</p>），检测到标签就用 rich-text 渲染；
      // 纯文本按换行拆段，避免把 < 当成标签。
      const isHtml = /<[a-z][\s\S]*>/i.test(content);
      const paragraphs = isHtml ? [] : content.split(/\n+/).filter((s) => s.trim());
      this.setData({
        loading: false,
        a: a,
        contentIsHtml: isHtml,
        paragraphs: paragraphs
      });
    }).catch((err) => {
      this.setData({ loading: false, errMsg: (err && err.msg) || '文章加载失败' });
    });
  },

  // 记录学习时长：写学习记录，看板据此统计
  recordStudy() {
    if (!auth.requireLogin()) return;
    const a = this.data.a || {};
    // minutes 传 0 时后端会回退到文章自身的 study_minutes，再兜底 5 分钟
    this.setData({ submitting: true });
    api.post('/api/articles/' + this.data.id + '/study', { minutes: Number(a.study_minutes) || 0 })
      .then((res) => {
        const d = res.data || {};
        this.setData({
          submitting: false,
          recorded: true,
          myTotalMinutes: d.my_total_minutes || 0
        });
        wx.showToast({ title: (res && res.msg) || '已记录学习时长', icon: 'none' });
      })
      .catch(() => this.setData({ submitting: false }));
  },

  goStudy() {
    getApp().globalData.studyCategory = null;
    wx.switchTab({ url: '/pages/study/study' });
  }
});
