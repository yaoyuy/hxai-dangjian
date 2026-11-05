// 数据看板：概览数字 + 每月活动柱状图 + 党员构成 + 党费情况 + 学习情况 + 活动参与率
// 接口（全部来自后端真实统计，不写死任何数字）：
//   GET /api/stats/overview、/api/stats/monthly、/api/stats/members、
//   GET /api/stats/learning、/api/stats/dues、/api/stats/activity-participation
const api = require('../../utils/api.js');

const CHART_MAX = 220;   // 柱状图最高柱的高度（rpx），仅用于视觉换算

Page({
  data: {
    loading: true,
    errMsg: '',
    ov: null,
    monthly: [],
    monthYear: '',
    monthTotal: 0,
    members: [],
    memberTotal: 0,
    learning: [],
    dues: null,
    trend: [],
    parts: [],
    generatedAt: ''
  },

  onLoad() { this.load(); },

  onPullDownRefresh() {
    this.load().then(() => wx.stopPullDownRefresh());
  },

  load() {
    this.setData({ loading: true, errMsg: '' });
    const safe = (p) => p.catch(() => null);
    return Promise.all([
      safe(api.get('/api/stats/overview', {}, { silent: true, noRedirect: true })),
      safe(api.get('/api/stats/monthly', {}, { silent: true, noRedirect: true })),
      safe(api.get('/api/stats/members', {}, { silent: true, noRedirect: true })),
      safe(api.get('/api/stats/learning', {}, { silent: true, noRedirect: true })),
      safe(api.get('/api/stats/dues', {}, { silent: true, noRedirect: true })),
      safe(api.get('/api/stats/activity-participation', {}, { silent: true, noRedirect: true }))
    ]).then((rs) => {
      const ovRes = rs[0], monRes = rs[1], memRes = rs[2], learnRes = rs[3], duesRes = rs[4], partRes = rs[5];
      if (!ovRes && !monRes && !memRes && !learnRes && !duesRes) {
        this.setData({ loading: false, errMsg: '看板数据加载失败：请检查接口地址与网络' });
        return;
      }

      // —— 每月活动柱状图：count 转成柱高（count 为 0 就不画柱）——
      const monthlyRaw = (monRes && monRes.data) || [];
      let max = 0;
      monthlyRaw.forEach((m) => { if (Number(m.count) > max) max = Number(m.count); });
      const monthly = monthlyRaw.map((m) => {
        const c = Number(m.count) || 0;
        return {
          label: m.label || (m.month + '月'),
          count: c,
          h: max > 0 && c > 0 ? Math.max(10, Math.round(c / max * CHART_MAX)) : 0,
          peak: max > 0 && c === max && c > 0
        };
      });

      // —— 党员构成：按最大人数换算条宽百分比 ——
      const membersRaw = (memRes && memRes.data) || [];
      let mmax = 0;
      membersRaw.forEach((m) => { if (Number(m.count) > mmax) mmax = Number(m.count); });
      const members = membersRaw.map((m) => ({
        group: m.group,
        count: m.count,
        w: mmax > 0 ? Math.round((Number(m.count) || 0) / mmax * 100) : 0
      }));

      // —— 党费 ——
      const dues = (duesRes && duesRes.data) || null;

      // —— 活动参与率（capacity=0 时后端 rate 为 null → 显示不限人数）——
      const parts = ((partRes && partRes.data) || []).map((p) => ({
        title: p.title,
        enrolled: p.enrolled,
        capacity: p.capacity,
        rate: p.rate
      }));

      this.setData({
        loading: false,
        ov: (ovRes && ovRes.data) || null,
        monthly: monthly,
        monthYear: (monRes && monRes.year) || '',
        monthTotal: (monRes && monRes.total) || 0,
        members: members,
        memberTotal: (memRes && memRes.total) || 0,
        learning: (learnRes && learnRes.data) || [],
        dues: dues,
        trend: (dues && dues.trend) || [],
        parts: parts,
        generatedAt: (ovRes && ovRes.data && ovRes.data.generated_at) || (dues && dues.generated_at) || ''
      });
    });
  },

  goActivity(e) {
    wx.navigateTo({ url: '/pages/activity/activity?id=' + e.currentTarget.dataset.id });
  },

  fmtRate(v) {
    return (v === null || v === undefined) ? '—' : v + '%';
  }
});
