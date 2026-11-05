// utils/api.js —— 统一网络请求封装
// 约定：所有后端接口都返回 {ok:true, data:...} 或 {ok:false, msg:"..."}
//   - 自动带上登录头 X-Auth-Token（从本地缓存取）
//   - ok:false 自动 wx.showToast 提示后 reject
//   - 401 自动清 token 并跳登录页
//   - 全部返回 Promise，方便 .then(...)/.catch(...) 串联
const config = require('../config.js');
const store = require('./store.js');

// 取接口根地址：优先用本地缓存覆盖值（wx.setStorageSync('api_base', ...)），否则用 config.js
function getBase() {
  const custom = store.getBaseOverride();
  const base = custom || config.API_BASE || '';
  return String(base).replace(/\/+$/, '');   // 去掉结尾的 /
}

// 统一请求
// method ：GET / POST / PUT / DELETE
// path   ：以 / 开头的接口路径，例如 /api/articles
// data   ：GET 会作为 query，其它方法作为 JSON body
// options：{ silent:true 不弹错误提示, noRedirect:true 401 时不跳登录页 }
function request(method, path, data, options) {
  const opts = options || {};
  return new Promise(function (resolve, reject) {
    const header = { 'content-type': 'application/json' };
    const token = store.getToken();
    if (token) header['X-Auth-Token'] = token;

    wx.request({
      url: getBase() + path,
      method: method || 'GET',
      data: data || {},
      header: header,
      success: function (res) {
        const body = res.data;
        // 未登录 / 登录态失效
        if (res.statusCode === 401) {
          store.clearToken();
          store.clearUser();
          if (!opts.silent) {
            wx.showToast({ title: (body && body.msg) || '请先登录', icon: 'none' });
          }
          if (!opts.noRedirect) {
            setTimeout(function () {
              wx.navigateTo({ url: '/pages/login/login' });
            }, 600);
          }
          reject({ statusCode: 401, body: body, msg: (body && body.msg) || '请先登录' });
          return;
        }
        // 业务成功
        if (res.statusCode >= 200 && res.statusCode < 300 && body && body.ok) {
          resolve(body);
          return;
        }
        // 其它错误：把后端 msg 原样提示出来，绝不编造成功
        const msg = (body && body.msg) || ('请求失败（HTTP ' + res.statusCode + '）');
        if (!opts.silent) wx.showToast({ title: msg, icon: 'none' });
        reject({ statusCode: res.statusCode, body: body, msg: msg });
      },
      fail: function (err) {
        if (!opts.silent) {
          wx.showToast({ title: '网络异常：请检查接口地址（config.js）与网络', icon: 'none' });
        }
        reject(err);
      }
    });
  });
}

// 直接取回原始文本：用于后端「服务端渲染」的 HTML 页面（当前只有 /gallery）
function requestText(path) {
  return new Promise(function (resolve, reject) {
    wx.request({
      url: getBase() + path,
      method: 'GET',
      dataType: 'text',   // 不要让基础库去 JSON.parse
      success: function (res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(String(res.data || ''));
        } else {
          reject({ statusCode: res.statusCode });
        }
      },
      fail: reject
    });
  });
}

module.exports = {
  getBase: getBase,
  request: request,
  get: function (path, data, opts) { return request('GET', path, data, opts); },
  post: function (path, data, opts) { return request('POST', path, data, opts); },
  requestText: requestText
};
