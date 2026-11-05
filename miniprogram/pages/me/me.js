// 我的：登录状态、我的党费、我的组织关系、退出登录
// 接口：GET /api/auth/me、GET /api/dues/my、GET /api/transfers/my、POST /api/transfers
const api = require('../../utils/api.js');
const auth = require('../../utils/auth.js');

// 与后端 backend/models.py 的 ROLE_LABELS 保持一致（只做中文显示，不做权限判断）
const ROLE_LABELS = { super_admin: '超级管理员', branch_admin: '支部管理员', member: '普通党员' };

Page({
  data: {
    logged: false,
    user: null,
    roleLabel: '',
    avatarText: '',
    notice: '',          // 后端原文案，例如「测试登录，非微信身份」
    loginMode: '',
    hasOpenid: false,
    loading: false,
    errMsg: '',
    duesList: [],
    duesSummary: null,
    duesUserName: '',
    transfers: [],
    showTransfer: false,
    directions: ['转入', '转出'],
    directionIndex: 0,
    form: { from_org: '', to_org: '', reason: '' },
    submitting: false
  },

  onShow() {
    this.refresh();
  },

  onPullDownRefresh() {
    this.refresh().then(() => wx.stopPullDownRefresh());
  },

  refresh() {
    const logged = auth.isLoggedIn();
    const cached = auth.getUser();
    this.setData({
      logged: logged,
      user: cached,
      roleLabel: (cached && ROLE_LABELS[cached.role]) || (cached && cached.role) || '',
      avatarText: this.avatarOf(cached)
    });
    if (!logged) {
      this.setData({
        notice: '',
        loginMode: '',
        hasOpenid: false,
        duesList: [], duesSummary: null, transfers: [], errMsg: ''
      });
      // 未登录也能读到公开配置里的身份说明（后端原文案，例如「测试登录，非微信身份」），
      // 这样「我的」页显示的一直是后端说法，而不是小程序自己编的。
      return auth.fetchConfig(true).then((cfg) => {
        this.setData({ notice: (cfg && cfg.notice) || '' });
      }).catch(() => {});
    }
    this.setData({ loading: true, errMsg: '' });
    return Promise.all([this.loadMe(), this.loadDues(), this.loadTransfers()])
      .then(() => this.setData({ loading: false }))
      .catch(() => this.setData({ loading: false }));
  },

  avatarOf(user) {
    const name = (user && (user.real_name || user.username)) || '';
    return name ? name.slice(0, 1) : '党';
  },

  // 登录状态 / 后端身份说明
  loadMe() {
    return auth.fetchMe().then((d) => {
      const user = d.user || null;
      this.setData({
        notice: d.notice || '',
        loginMode: d.login_mode || '',
        hasOpenid: !!d.has_openid,
        user: user,
        roleLabel: (user && ROLE_LABELS[user.role]) || (user && user.role) || '',
        avatarText: this.avatarOf(user)
      });
    }).catch(() => {});
  },

  // 我的党费
  loadDues() {
    return api.get('/api/dues/my', {}, { silent: true }).then((res) => {
      const d = res.data || {};
      this.setData({
        duesList: d.list || [],
        duesSummary: d.summary || null,
        duesUserName: d.user || ''
      });
    }).catch(() => {});
  },

  // 我的组织关系转接
  loadTransfers() {
    return api.get('/api/transfers/my', {}, { silent: true }).then((res) => {
      this.setData({ transfers: res.data || [] });
    }).catch(() => {});
  },

  goLogin() { wx.navigateTo({ url: '/pages/login/login' }); },

  doLogout() {
    wx.showModal({
      title: '退出登录',
      content: '退出后需要重新登录才能查看党费与组织关系。',
      success: (r) => {
        if (!r.confirm) return;
        auth.logout();
        wx.showToast({ title: '已退出', icon: 'success' });
        this.refresh();
      }
    });
  },

  toggleTransfer() {
    if (!auth.requireLogin()) return;
    this.setData({ showTransfer: !this.data.showTransfer });
  },

  onDirection(e) { this.setData({ directionIndex: Number(e.detail.value) }); },
  onFrom(e) { this.setData({ 'form.from_org': e.detail.value }); },
  onTo(e) { this.setData({ 'form.to_org': e.detail.value }); },
  onReason(e) { this.setData({ 'form.reason': e.detail.value }); },

  submitTransfer() {
    const f = this.data.form;
    if (!f.from_org.trim() || !f.to_org.trim()) {
      wx.showToast({ title: '请填写转出单位和接收单位', icon: 'none' });
      return;
    }
    this.setData({ submitting: true });
    api.post('/api/transfers', {
      direction: this.data.directionIndex === 0 ? 'in' : 'out',
      from_org: f.from_org.trim(),
      to_org: f.to_org.trim(),
      reason: f.reason.trim()
    }).then((res) => {
      this.setData({ submitting: false, showTransfer: false, form: { from_org: '', to_org: '', reason: '' } });
      wx.showToast({ title: (res && res.msg) || '已提交', icon: 'none' });
      this.loadTransfers();
    }).catch(() => this.setData({ submitting: false }));
  }
});
