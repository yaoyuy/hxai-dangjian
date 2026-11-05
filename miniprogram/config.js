/**
 * 全局配置（小程序端唯一的接口地址入口）
 *
 * API_BASE：后端 Flask 服务地址。
 *   - 当前填的是「开发 / 体验版」临时地址：局域网里的 http://127.0.0.1:5000
 *     用微信开发者工具打开时，必须在「详情 → 本地设置」勾选「不校验合法域名、
 *     web-view（业务域名）、TLS 版本以及 HTTPS 证书」，否则连不上 http 地址。
 *   - 正式发布（体验版 / 正式版）必须换成已 ICP 备案的 HTTPS 域名，
 *     例如 https://dangjian.xxx.edu.cn ，并把它加入小程序后台
 *     「开发管理 → 开发设置 → 服务器域名 → request / downloadFile 合法域名」。
 *     微信不允许小程序正式版访问 IP、带端口的地址和未备案域名。
 *   - 也允许在运行时用本地缓存覆盖（不改代码切换环境）：
 *         wx.setStorageSync('api_base', 'https://dangjian.xxx.edu.cn')
 *         wx.removeStorageSync('api_base')   // 清除覆盖，回到下面这个默认值
 */
module.exports = {
  API_BASE: 'http://127.0.0.1:5000'
};
