// utils/store.js —— 本地缓存读写（登录态、用户信息、接口地址覆盖、公开配置）
// 所有 key 都带 hxai_ 前缀，避免和别的小程序/组件冲突。
const TOKEN_KEY = 'hxai_token';     // 登录 token（后端 X-Auth-Token）
const USER_KEY = 'hxai_user';       // 当前登录用户（/api/auth/me 的 user）
const CONFIG_KEY = 'hxai_config';   // /api/auth/config 的公开配置缓存
const BASE_KEY = 'api_base';        // 运行时覆盖的接口根地址（见 config.js 注释）

function getToken() {
  return wx.getStorageSync(TOKEN_KEY) || '';
}
function setToken(token) {
  if (token) wx.setStorageSync(TOKEN_KEY, token);
  else wx.removeStorageSync(TOKEN_KEY);
}
function clearToken() {
  wx.removeStorageSync(TOKEN_KEY);
}

function getUser() {
  return wx.getStorageSync(USER_KEY) || null;
}
function setUser(user) {
  if (user) wx.setStorageSync(USER_KEY, user);
  else wx.removeStorageSync(USER_KEY);
}
function clearUser() {
  wx.removeStorageSync(USER_KEY);
}

function getConfigCache() {
  return wx.getStorageSync(CONFIG_KEY) || null;
}
function setConfigCache(cfg) {
  if (cfg) wx.setStorageSync(CONFIG_KEY, cfg);
  else wx.removeStorageSync(CONFIG_KEY);
}

function getBaseOverride() {
  return wx.getStorageSync(BASE_KEY) || '';
}
function setBaseOverride(url) {
  if (url) wx.setStorageSync(BASE_KEY, url);
  else wx.removeStorageSync(BASE_KEY);
}

module.exports = {
  getToken: getToken,
  setToken: setToken,
  clearToken: clearToken,
  getUser: getUser,
  setUser: setUser,
  clearUser: clearUser,
  getConfigCache: getConfigCache,
  setConfigCache: setConfigCache,
  getBaseOverride: getBaseOverride,
  setBaseOverride: setBaseOverride
};
