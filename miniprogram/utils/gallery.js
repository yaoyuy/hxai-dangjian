// utils/gallery.js —— 党建风采数据获取
// 优先走后端 JSON 接口 GET /api/gallery（返回 {ok,data,total}）；
// 若该接口不可用（老版本后端 404），自动退回解析服务端渲染页 GET /gallery 的 HTML。
// 返回 Promise<[{id, wide, img, title, sub, is_demo}]>
const api = require('./api.js');

// 简单的 HTML 实体解码 + 去标签（HTML 兜底解析时用）
function decode(s) {
  return String(s || '')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .replace(/<[^>]+>/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

// 把后端 JSON 的图片路径补成完整地址（后端可能存相对路径 /static/...）
function fullUrl(src) {
  if (!src) return '';
  if (src.indexOf('http://') === 0 || src.indexOf('https://') === 0) return src;
  if (src.charAt(0) !== '/') src = '/' + src;
  return api.getBase() + src;
}

// JSON 接口：GET /api/gallery
function fetchGalleryJson() {
  return api.request('GET', '/api/gallery').then(function (res) {
    const rows = (res && res.data) || [];
    return rows.map(function (p, i) {
      return {
        id: p.id || i,
        wide: i === 0,                       // 与后端模板一致：第一张是宽幅
        img: fullUrl(p.image_url),
        title: p.title || ('风采照片 ' + (i + 1)),
        sub: p.description || p.created_at || '',
        is_demo: !!p.is_demo
      };
    });
  });
}

// HTML 兜底：解析 GET /gallery 里的 <figure>/<figcaption>
function fetchGalleryHtml() {
  return api.requestText('/gallery').then(function (html) {
    const list = [];
    const blocks = String(html).match(/<figure[\s\S]*?<\/figure>/gi) || [];
    blocks.forEach(function (b, i) {
      const imgM = b.match(/<img[^>]*src="([^"]*)"/i);
      const capM = b.match(/<figcaption[^>]*>([\s\S]*?)<\/figcaption>/i);
      const capRaw = capM ? capM[1] : '';
      const smallM = capRaw.match(/<small[^>]*>([\s\S]*?)<\/small>/i);
      list.push({
        id: i,
        wide: i === 0,
        img: fullUrl(imgM ? imgM[1] : ''),
        title: decode(capRaw.replace(/<small[\s\S]*?<\/small>/i, '')) || ('风采照片 ' + (i + 1)),
        sub: decode(smallM ? smallM[1] : ''),
        is_demo: /测试数据/.test(capRaw)
      });
    });
    return list;
  });
}

// 对外统一入口：先 JSON，失败或空结果再退回 HTML
function fetchGallery() {
  return fetchGalleryJson().then(function (list) {
    if (list && list.length) return list;
    return fetchGalleryHtml();
  }).catch(function () {
    return fetchGalleryHtml();
  });
}

module.exports = { fetchGallery: fetchGallery, decode: decode };
