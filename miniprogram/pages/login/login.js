// 登录页
// 后端：GET /api/auth/config（登录方式公开配置）、POST /api/auth/login（测试账号）、
//       POST /api/auth/wechat-login（微信小程序 wx.login 换 openid）
// 说明：当前是测试账号登录，页面如实显示后端返回的「测试登录，非微信身份」，
//       不会伪造 openid，也不会假装已经拿到微信授权。
const auth = require('../../utils/auth.js');

Page({
  data: {
    cfg: null,
    username: '',
    password: '',
    loading: false,
    errMsg: '',
    notice: ''   // 由后端 /api/auth/config 的 notice 字段填充，不本地硬编码
  },

  onLoad() {
    this.loadConfig();
  },

  loadConfig() {
    auth.fetchConfig(true).then((cfg) => {
      this.setData({
        cfg: cfg || null,
        notice: (cfg && cfg.notice) || '',   // 原文案来自后端，后台改成微信登录时会自动变
        errMsg: ''
      });
    }).catch(() => {
      this.setData({ errMsg: '读取登录配置失败：请检查 config.js 里的接口地址与网络' });
    });
  },

  onUser(e) { this.setData({ username: e.detail.value }); },
  onPwd(e) { this.setData({ password: e.detail.value }); },

  // 测试账号登录（账号密码，非微信身份）
  doTestLogin() {
    const u = (this.data.username || '').trim();
    const p = this.data.password || '';
    if (!u || !p) {
      wx.showToast({ title: '请填写账号和密码', icon: 'none' });
      return;
    }
    this.setData({ loading: true });
    auth.testLogin(u, p).then(() => {
      this.setData({ loading: false });
      wx.showToast({ title: '登录成功', icon: 'success' });
      setTimeout(() => { this.backOrHome(); }, 700);
    }).catch(() => {
      this.setData({ loading: false });   // 失败原因由 utils/api.js 统一 toast 后端 msg
    });
  },

  // 微信一键登录：wx.login 拿 code → POST /api/auth/wechat-login
  // 不在白名单会被后端 403 拒绝，这里把后端 msg 原样展示出来
  doWechatLogin() {
    this.setData({ loading: true });
    auth.wechatLogin().then((d) => {
      this.setData({ loading: false });
      wx.showModal({
        title: '登录成功',
        content: (d && d.notice) || '已登录',
        showCancel: false,
        success: () => this.backOrHome()
      });
    }).catch((err) => {
      this.setData({ loading: false });
      wx.showModal({
        title: '微信登录未成功',
        content: (err && err.msg) || '后端未返回可用的微信身份，请改用测试账号登录',
        showCancel: false
      });
    });
  },

  backOrHome() {
    const pages = getCurrentPages();
    if (pages.length > 1) wx.navigateBack();
    else wx.switchTab({ url: '/pages/home/home' });
  }
});
