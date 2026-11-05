// utils/auth.js —— 登录态与鉴权工具
// 注意：本地测试账号登录返回的 notice 一定是「测试登录，非微信身份」，
// 本模块不会伪造 openid，也不会假装已经拿到微信授权。
const api = require('./api.js');
const store = require('./store.js');

const CONFIG_KEY = 'hxai_config';

function getToken() { return store.getToken(); }
function setToken(token) { store.setToken(token); }
function clearToken() { store.clearToken(); }
function getUser() { return store.getUser(); }
function setUser(user) { store.setUser(user); }

// 退出登录：只清本地登录态（后端 /api/auth/logout 只清 Flask session，小程序用 token，无需调用）
function logout() {
  store.clearToken();
  store.clearUser();
  const app = getApp();
  if (app && app.globalData) app.globalData.user = null;
}

function isLoggedIn() { return !!store.getToken(); }

// 读取公开配置 /api/auth/config（登录方式、公告、微信是否已配置）
// force=true 时强制刷新，否则先用本地缓存
function fetchConfig(force) {
  if (!force) {
    const cached = store.getConfigCache();
    if (cached) return Promise.resolve(cached);
  }
  return api.get('/api/auth/config', {}, { silent: true }).then(function (res) {
    const data = res.data || {};
    store.setConfigCache(data);
    return data;
  });
}

// 本地测试账号登录（账号密码，非微信身份）
function testLogin(username, password) {
  return api.post('/api/auth/login', { username: username, password: password }).then(function (res) {
    const d = res.data || {};
    store.setToken(d.token || '');
    store.setUser(d.user || null);
    const app = getApp();
    if (app && app.globalData) app.globalData.user = d.user || null;
    return d;
  });
}

// 微信一键登录：wx.login 拿临时 code → POST /api/auth/wechat-login 换 openid
// 不在白名单会被后端拒绝（403 not_in_whitelist），这里把后端 msg 原样抛出
function wechatLogin() {
  return new Promise(function (resolve, reject) {
    wx.login({
      success: function (loginRes) {
        if (!loginRes || !loginRes.code) {
          reject({ msg: '未获取到微信登录 code，请重试' });
          return;
        }
        api.post('/api/auth/wechat-login', { type: 'wxapp', code: loginRes.code })
          .then(function (res) {
            const d = res.data || {};
            store.setToken(d.token || '');
            store.setUser(d.user || null);
            const app = getApp();
            if (app && app.globalData) app.globalData.user = d.user || null;
            resolve(d);
          })
          .catch(function (err) {
            reject(err);
          });
      },
      fail: function () {
        reject({ msg: '微信登录失败：wx.login 调用出错' });
      }
    });
  });
}

// 读取当前登录用户（带 token 请求 /api/auth/me）
function fetchMe() {
  return api.get('/api/auth/me', {}, { silent: true }).then(function (res) {
    const d = res.data || {};
    if (d.user) {
      store.setUser(d.user);
      const app = getApp();
      if (app && app.globalData) app.globalData.user = d.user;
    }
    return d;
  });
}

// 需要登录才能做的操作：未登录就跳登录页并返回 false
function requireLogin() {
  if (isLoggedIn()) return true;
  wx.showToast({ title: '请先登录', icon: 'none' });
  setTimeout(function () {
    wx.navigateTo({ url: '/pages/login/login' });
  }, 500);
  return false;
}

module.exports = {
  getToken: getToken,
  setToken: setToken,
  clearToken: clearToken,
  getUser: getUser,
  setUser: setUser,
  logout: logout,
  isLoggedIn: isLoggedIn,
  fetchConfig: fetchConfig,
  testLogin: testLogin,
  wechatLogin: wechatLogin,
  fetchMe: fetchMe,
  requireLogin: requireLogin
};
