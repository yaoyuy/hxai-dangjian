/* ============================================================
   智慧党建系统 · 前端交互（原生 JS，无框架、无需 Node）
   注意：所有数据来自后端接口，前端不写死任何业务数据。
   ============================================================ */
(function () {
  "use strict";

  var CFG = window.__APP__ || {};

  /* ---------------- 基础工具 ---------------- */
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function toast(msg) {
    var el = $("#toast");
    if (!el) { alert(msg); return; }
    el.textContent = msg;
    el.classList.add("on");
    clearTimeout(el._t);
    el._t = setTimeout(function () { el.classList.remove("on"); }, 2200);
  }

  function api(url, options) {
    options = options || {};
    var opts = { method: options.method || "GET", headers: {}, credentials: "same-origin" };
    if (options.body instanceof FormData) {
      opts.body = options.body;
    } else if (options.body) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(options.body);
    }
    return fetch(url, opts).then(function (r) {
      return r.json().catch(function () { return { ok: false, msg: "服务器返回异常" }; })
        .then(function (data) {
          if (r.status === 401 && data.code === 401) {
            toast("请先登录");
            var next = encodeURIComponent(location.pathname + location.search);
            setTimeout(function () { location.href = "/login?next=" + next; }, 700);
            throw new Error("unauthorized");
          }
          return data;
        });
    });
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* ---------------- 底部菜单（结构照样例：党建学习 / 组织生活 / 支部风采） ---------------- */
  var MENU = [
    { key: "study", name: "党建学习", items: [
        { name: "学习专栏", path: "/study" },
        { name: "云党课", path: "/study?category=cloud" },
        { name: "党史学习", path: "/study?category=history" }
      ] },
    { key: "life", name: "组织生活", items: [
        { name: "三会一课", path: "/meetings" },
        { name: "活动报名", path: "/activities" },
        { name: "电子台账", path: "/ledger" }
      ] },
    { key: "style", name: "支部风采", items: [
        { name: "党建风采", path: "/gallery" },
        { name: "数据看板", path: "/dashboard" },
        { name: "我的", path: "/me" }
      ] }
  ];

  function buildMenuBar() {
    var bar = $("#menubar");
    if (!bar) return;
    var html = '<button class="kb" type="button" aria-label="切换到键盘">⌨</button>';
    MENU.forEach(function (m, idx) {
      html += '<button class="mbtn" type="button" data-menu="' + idx + '">' +
        m.name + '<span class="car">▲</span></button>';
    });
    bar.innerHTML = html;

    // 子菜单（浮层）
    var sub = document.createElement("div");
    sub.className = "submenu";
    sub.id = "submenu";
    document.body.appendChild(sub);

    $$(".mbtn", bar).forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        var idx = Number(btn.dataset.menu);
        var menu = MENU[idx];
        var rect = btn.getBoundingClientRect();

        // 再次点击同一个按钮 = 收起
        if (btn.classList.contains("open")) { closeSub(); return; }
        closeSub();
        btn.classList.add("open");

        sub.innerHTML = menu.items.map(function (it) {
          var cur = location.pathname + location.search === it.path ||
                    location.pathname === it.path.split("?")[0];
          return '<button type="button" data-path="' + it.path + '" class="' + (cur ? "cur" : "") + '">' +
            it.name + "</button>";
        }).join("");

        // 定位到按钮上方
        sub.classList.add("on");
        var w = sub.offsetWidth, h = sub.offsetHeight;
        var left = rect.left + rect.width / 2 - w / 2;
        left = Math.max(8, Math.min(left, window.innerWidth - w - 8));
        sub.style.left = left + "px";
        sub.style.top = (rect.top - h - 10) + "px";

        $$("button", sub).forEach(function (b) {
          b.addEventListener("click", function () {
            closeSub();
            location.href = b.dataset.path;
          });
        });
      });
    });

    document.addEventListener("click", closeSub);
    window.addEventListener("scroll", closeSub, true);

    // 键盘按钮：微信里提示，浏览器里聚焦搜索
    var kb = $(".kb", bar);
    if (kb) kb.addEventListener("click", function () {
      var input = $(".lsearch input, .searchbar input");
      if (input) { input.focus(); } else { toast("点击底部菜单切换栏目"); }
    });
  }

  function closeSub() {
    var sub = $("#submenu");
    if (sub) sub.classList.remove("on");
    $$(".mbtn").forEach(function (b) { b.classList.remove("open"); });
  }

  /* ---------------- 返回按钮 ---------------- */
  function bindBack() {
    var back = $("#navBack");
    if (!back) return;
    back.addEventListener("click", function () {
      if (document.referrer && history.length > 1) history.back();
      else location.href = "/";
    });
  }

  /* ---------------- 首页：加载真实数据 ---------------- */
  function initHome() {
    var feed = $("#homeFeed");
    if (!feed) return;
    Promise.all([
      api("/api/articles?size=3"),
      api("/api/stats/overview")
    ]).then(function (res) {
      var arts = (res[0] && res[0].data) || [];
      var st = (res[1] && res[1].data) || {};
      renderHomeFeed(feed, arts);
      var meta = $("#acctMeta");
      if (meta) {
        meta.innerHTML =
          "<span><b>" + (st.total_articles || 0) + "</b> 篇已发布</span>" +
          "<span><b>" + (st.year_activities || 0) + "</b> 场年度活动</span>" +
          "<span><b>" + (st.total_members || 0) + "</b> 名党员</span>";
      }
    }).catch(function () {
      feed.innerHTML = '<div class="card" style="padding:20px;text-align:center;color:#999">数据加载失败，请确认后端已启动</div>';
    });
  }

  function renderHomeFeed(el, arts) {
    if (!arts.length) {
      el.innerHTML = '<div class="card" style="padding:20px;text-align:center;color:#999">还没有已发布的文章</div>';
      return;
    }
    var main = arts[0], rest = arts.slice(1);
    var html = '<div class="push-date">' + new Date().toLocaleDateString("zh-CN") + " · 最新发布</div>";
    html += '<div class="card" style="margin-top:8px">';
    html += '<a class="push-cover" href="/article/' + main.id + '">' +
      (main.cover_url ? '<img src="' + escapeHtml(main.cover_url) + '" alt="">' :
        '<div style="width:100%;height:100%;display:grid;place-items:center;color:rgba(255,255,255,.9);font-size:15px">' +
        escapeHtml(main.category || "党建") + "</div>") +
      '<span class="cap">' + escapeHtml(main.title) + "</span></a>";
    rest.forEach(function (a) {
      html += '<a class="push-item" href="/article/' + a.id + '">' +
        '<span class="t">' + escapeHtml(a.title) + "</span>" +
        (a.cover_url ? '<img src="' + escapeHtml(a.cover_url) + '" alt="">' :
          '<span class="thumb-ph" style="width:52px;height:52px;font-size:11px">' +
          escapeHtml(a.category || "党建") + "</span>") +
        "</a>";
    });
    html += '<div class="push-foot"><span>阅读 ' + (main.view_count || 0) + "</span>" +
      "<span>" + escapeHtml(main.category || "") + "</span></div>";
    html += "</div>";
    el.innerHTML = html;
  }

  /* ---------------- 学习专栏列表：分类筛选 + 搜索 ---------------- */
  function initStudy() {
    var list = $("#studyList");
    if (!list) return;
    var state = { category: CFG.category || "all", q: "" };

    function load() {
      list.innerHTML = '<div style="padding:20px;text-align:center;color:#999">加载中…</div>';
      var url = "/api/articles?category=" + encodeURIComponent(state.category) +
        "&q=" + encodeURIComponent(state.q) + "&size=50";
      api(url).then(function (res) {
        var rows = res.data || [];
        $("#studyCount") && ($("#studyCount").textContent = "共 " + ((res.pagination || {}).total || rows.length) + " 篇");
        if (!rows.length) {
          list.innerHTML = '<div class="empty on">没有匹配的文章</div>';
          return;
        }
        list.innerHTML = rows.map(function (a) {
          return '<a class="acard" href="/article/' + a.id + '">' +
            (a.cover_url ? '<img src="' + escapeHtml(a.cover_url) + '" alt="">' :
              '<span class="thumb-ph">' + escapeHtml(a.category || "党建") + "</span>") +
            "<div><div class=\"tt\">" + escapeHtml(a.title) + "</div>" +
            '<div class="dd">' + escapeHtml(a.summary || "") + "</div>" +
            '<div class="mm"><span>' + escapeHtml(a.category || "") + "</span>" +
            "<span>" + escapeHtml(a.published_at || "") + "</span>" +
            "<span>阅读 " + (a.view_count || 0) + "</span></div></div></a>";
        }).join("");
      }).catch(function () {
        list.innerHTML = '<div class="empty on">加载失败</div>';
      });
    }

    $$(".tab").forEach(function (t) {
      t.addEventListener("click", function () {
        $$(".tab").forEach(function (x) { x.classList.remove("on"); });
        t.classList.add("on");
        state.category = t.dataset.cat;
        history.replaceState(null, "", "/study" + (state.category === "all" ? "" : "?category=" + state.category));
        load();
      });
    });

    var search = $("#studySearch");
    if (search) {
      var timer;
      search.addEventListener("input", function () {
        clearTimeout(timer);
        timer = setTimeout(function () { state.q = search.value.trim(); load(); }, 300);
      });
    }
    load();
  }

  /* ---------------- 文章详情：学习打卡 ---------------- */
  function initArticle() {
    var btn = $("#studyBtn");
    if (!btn) return;
    var id = btn.dataset.id;
    btn.addEventListener("click", function () {
      btn.disabled = true;
      api("/api/articles/" + id + "/study", { method: "POST", body: {} })
        .then(function (res) {
          if (res.ok) {
            toast(res.msg || "已记录学习");
            $("#myStudyTotal") && ($("#myStudyTotal").textContent = res.data.my_total_minutes + " 分钟");
          } else {
            toast(res.msg || "记录失败");
          }
        })
        .catch(function () {})
        .then(function () { btn.disabled = false; });
    });
  }

  /* ---------------- 活动报名 ---------------- */
  function initActivities() {
    var wrap = $("#actList");
    if (!wrap) return;
    var state = { kind: "all", status: "all" };

    function load() {
      var url = "/api/activities?kind=" + state.kind + "&status=" + state.status;
      api(url).then(function (res) {
        var rows = res.data || [];
        $("#actCount") && ($("#actCount").textContent = "共 " + rows.length + " 场");
        if (!rows.length) {
          wrap.innerHTML = '<div class="empty on">暂无活动</div>';
          return;
        }
        wrap.innerHTML = rows.map(renderActivity).join("");
        bindJoinButtons();
      }).catch(function () {
        wrap.innerHTML = '<div class="empty on">加载失败</div>';
      });
    }

    function renderActivity(a) {
      var pct = a.capacity ? Math.min(100, Math.round(a.enrolled_count / a.capacity * 100)) : 0;
      var btnClass = a.enrolled ? "joined" : (a.full ? "full" : "");
      var btnText = a.enrolled ? "已报名" : (a.full ? "名额已满" : "我要报名");
      return '<div class="act">' +
        (a.cover_url ? '<img class="cover" src="' + escapeHtml(a.cover_url) + '" alt="">' : "") +
        '<div class="body"><h3><a href="/activity/' + a.id + '">' + escapeHtml(a.title) + "</a></h3>" +
        '<div class="info"><span>时间：</span>' + escapeHtml(a.start_at || "待定") +
        "<br><span>地点：</span>" + escapeHtml(a.location || "待定") +
        "<br><span>对象：</span>" + escapeHtml(a.target || "") + "</div>" +
        (a.capacity ? '<div class="bar"><i style="width:' + pct + '%"></i></div>' : "") +
        '<div class="foot"><span class="left">已报名 ' + a.enrolled_count +
        (a.capacity ? " / " + a.capacity : "") + " 人</span>" +
        '<button class="btn-join ' + btnClass + '" data-id="' + a.id + '" data-enrolled="' +
        (a.enrolled ? 1 : 0) + '" ' + (a.full && !a.enrolled ? "disabled" : "") + ">" + btnText + "</button>" +
        "</div></div></div>";
    }

    function bindJoinButtons() {
      $$(".btn-join", wrap).forEach(function (btn) {
        btn.addEventListener("click", function () {
          var id = btn.dataset.id;
          var enrolled = btn.dataset.enrolled === "1";
          var url = "/api/activities/" + id + (enrolled ? "/cancel" : "/enroll");
          btn.disabled = true;
          api(url, { method: "POST", body: {} }).then(function (res) {
            toast(res.msg || (res.ok ? "操作成功" : "操作失败"));
            if (res.ok) load();
            else btn.disabled = false;
          }).catch(function () { btn.disabled = false; });
        });
      });
    }

    $$(".tab").forEach(function (t) {
      t.addEventListener("click", function () {
        var group = t.dataset.group;
        $$('.tab[data-group="' + group + '"]').forEach(function (x) { x.classList.remove("on"); });
        t.classList.add("on");
        state[group] = t.dataset.val;
        load();
      });
    });
    load();
  }

  /* ---------------- 活动详情页报名 ---------------- */
  function initActivityDetail() {
    var btn = $("#detailJoin");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var id = btn.dataset.id, enrolled = btn.dataset.enrolled === "1";
      btn.disabled = true;
      api("/api/activities/" + id + (enrolled ? "/cancel" : "/enroll"), { method: "POST", body: {} })
        .then(function (res) {
          toast(res.msg || "操作完成");
          if (res.ok) setTimeout(function () { location.reload(); }, 700);
          else btn.disabled = false;
        }).catch(function () { btn.disabled = false; });
    });
  }

  /* ---------------- 电子台账：搜索 / 分类 / 上传 ---------------- */
  function initLedger() {
    var list = $("#ledgerList");
    if (!list) return;
    var state = { category: "all", q: "" };

    function load() {
      var url = "/api/ledger?category=" + encodeURIComponent(state.category) +
        "&q=" + encodeURIComponent(state.q);
      api(url).then(function (res) {
        var rows = res.data || [];
        $("#ledgerTotal") && ($("#ledgerTotal").textContent = "共 " + (res.all_total || 0) + " 份资料");
        if (!rows.length) { list.innerHTML = '<div class="empty on">没有匹配的资料</div>'; return; }
        list.innerHTML = rows.map(function (f) {
          var cls = { pdf: "pdf", doc: "doc", docx: "doc", ppt: "ppt", pptx: "ppt",
                      xls: "xls", xlsx: "xls" }[f.ext] || "txt";
          return '<div class="frow"><span class="fic ' + cls + '">' + escapeHtml((f.ext || "").toUpperCase()) + "</span>" +
            '<div class="ft"><div class="fn">' + escapeHtml(f.title) + "</div>" +
            '<div class="fm">' + escapeHtml(f.category) + " · " + escapeHtml(f.size_text) +
            " · " + escapeHtml(f.created_at) + " · 下载 " + f.download_count + "</div></div>" +
            (window.__APP__ && window.__APP__.loggedIn
              ? '<a class="dl" href="/api/ledger/' + f.id + '/download">下载</a>'
              : '<a class="dl" href="/login?next=/ledger">登录后下载</a>') + "</div>";
        }).join("");
      }).catch(function () { list.innerHTML = '<div class="empty on">加载失败</div>'; });
    }

    $$(".tab").forEach(function (t) {
      t.addEventListener("click", function () {
        $$(".tab").forEach(function (x) { x.classList.remove("on"); });
        t.classList.add("on");
        state.category = t.dataset.cat;
        load();
      });
    });

    var search = $("#ledgerSearch");
    if (search) {
      var timer;
      search.addEventListener("input", function () {
        clearTimeout(timer);
        timer = setTimeout(function () { state.q = search.value.trim(); load(); }, 300);
      });
    }

    var form = $("#uploadForm");
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var fd = new FormData(form);
        var file = fd.get("file");
        if (!file || !file.name) { toast("请选择文件"); return; }
        var btn = $("#uploadBtn");
        btn.disabled = true;
        api("/api/ledger", { method: "POST", body: fd }).then(function (res) {
          toast(res.msg || (res.ok ? "上传成功" : "上传失败"));
          if (res.ok) { form.reset(); load(); }
          btn.disabled = false;
        }).catch(function () { btn.disabled = false; });
      });
    }
    load();
  }

  /* ---------------- 数据看板：实时拉取并绘图 ---------------- */
  function initDashboard() {
    var wrap = $("#dashStats");
    if (!wrap) return;

    Promise.all([
      api("/api/stats/overview"),
      api("/api/stats/monthly"),
      api("/api/stats/members"),
      api("/api/stats/learning"),
      api("/api/stats/activity-participation"),
      api("/api/stats/dues")
    ]).then(function (res) {
      var ov = res[0].data || {}, monthly = res[1].data || [],
          members = res[2].data || [], learning = res[3].data || [],
          participation = res[4].data || [], dues = res[5].data || {};

      wrap.innerHTML = [
        stat(ov.total_members, "党员总数"),
        stat(ov.year_activities, "年度活动(次)"),
        stat(ov.completion_rate + "%", "本月学习完成率"),
        stat(ov.study_hours, "累计学习(小时)")
      ].join("");

      $("#genAt") && ($("#genAt").textContent = "统计时间：" + (ov.generated_at || ""));

      // 每月活动柱状图（纯 CSS，无需图表库）
      var max = Math.max.apply(null, monthly.map(function (m) { return m.count; }).concat([1]));
      $("#monthlyChart").innerHTML = monthly.map(function (m) {
        var h = Math.round(m.count / max * 100);
        var peak = m.count === max && m.count > 0 ? " peak" : "";
        return '<div class="col' + peak + '" title="' + m.label + "：" + m.count + '次">' +
          "<em>" + m.count + "</em><i style=\"height:" + Math.max(h, 2) + '%\"></i>' +
          "<span>" + m.label + "</span></div>";
      }).join("");

      // 党员构成：环形图 + 图例
      var total = members.reduce(function (s, x) { return s + x.count; }, 0) || 1;
      var colors = ["#b01e23", "#c9a227", "#8c8c8c", "#576b95"];
      var acc = 0, segs = [];
      members.forEach(function (m, i) {
        var from = acc / total * 100;
        acc += m.count;
        var to = acc / total * 100;
        segs.push(colors[i % colors.length] + " " + from + "% " + to + "%");
      });
      $("#donut").style.background = "conic-gradient(" + (segs.join(",") || "#eee 0% 100%") + ")";
      $("#donutLabel").textContent = total;
      $("#memberLegend").innerHTML = members.map(function (m, i) {
        return '<div><i style="background:' + colors[i % colors.length] + '"></i>' +
          escapeHtml(m.group) + "<b>" + m.count + " 人</b></div>";
      }).join("");

      // 学习情况
      $("#learningTable").innerHTML = learning.length ? learning.map(function (l) {
        return '<div class="row-line"><span class="grow">' + escapeHtml(l.category) + "</span>" +
          "<b>" + l.study_times + " 人次 / " + l.hours + " 小时</b></div>";
      }).join("") : '<div class="empty">暂无学习记录</div>';

      // 活动参与
      $("#participation").innerHTML = participation.length ? participation.map(function (p) {
        return '<div class="row-line"><span class="grow">' + escapeHtml(p.title) + "</span>" +
          "<b>" + p.enrolled + (p.capacity ? " / " + p.capacity : "") + " 人</b></div>";
      }).join("") : '<div class="empty">暂无活动</div>';

      // 党费缴纳情况（来自 /api/stats/dues，全部实时聚合）
      var dsum = dues.summary || {}, trend = dues.trend || [];
      var duesWrap = $("#duesStats");
      if (duesWrap) {
        duesWrap.innerHTML = [
          stat(dsum.paid || 0, "已缴人次"),
          stat(dsum.unpaid || 0, "未缴人次"),
          stat((dsum.pay_rate == null ? 0 : dsum.pay_rate) + "%", "缴费率"),
          stat("¥" + (dsum.amount_paid == null ? 0 : dsum.amount_paid), "已收党费")
        ].join("");
      }
      var trendWrap = $("#duesTrend");
      if (trendWrap) {
        trendWrap.innerHTML = trend.length ? trend.map(function (t) {
          // trend 里只有 paid / unpaid 两个计数（后端按期间聚合），不要用不存在的 late 字段
          var donePct = t.total ? Math.round((t.paid || 0) / t.total * 100) : 0;
          return '<div class="row-line"><span class="grow">' + escapeHtml(t.period) + "</span>" +
            "<b>" + (t.paid || 0) + " / " + (t.total || 0) + " 人（" + donePct + "%）· ¥" + (t.amount_paid || 0) + "</b></div>";
        }).join("") : '<div class="empty">暂无党费记录（支部在后台登记后显示）</div>';
      }
    }).catch(function (e) {
      wrap.innerHTML = '<div class="empty on">看板数据加载失败</div>';
    });

    function stat(v, label) {
      return '<div class="stat"><b>' + (v == null ? "—" : v) + "</b><span>" + label + "</span></div>";
    }
  }

  /* ---------------- 登录页 ---------------- */
  function initLogin() {
    // 微信网页授权入口（参数没配好时不跳转，如实提示）
    var wxBtn = $("#wxLoginBtn");
    if (wxBtn) {
      wxBtn.addEventListener("click", function () {
        var url = wxBtn.getAttribute("data-oauth-url");
        if (!url) { toast("公众号或小程序参数还没配置，暂时不能用微信登录"); return; }
        location.href = url;
      });
    }

    // 开发联调：手工给一个 openid（只在测试模式可用，后端会标明"非真实微信授权"）
    var devForm = $("#devWxForm");
    if (devForm) {
      devForm.addEventListener("submit", function (e) {
        e.preventDefault();
        var btn = $("#devWxBtn");
        btn.disabled = true;
        api("/api/auth/wechat-login", {
          method: "POST",
          body: {
            type: "wxapp",
            dev_openid: $("#devOpenid").value.trim(),
            nickname: $("#devNickname").value.trim()
          }
        }).then(function (res) {
          if (res.ok) {
            toast(res.notice || "本地联调登录成功");
            setTimeout(function () { location.href = "/me"; }, 600);
          } else {
            toast(res.msg || "登录失败");
            btn.disabled = false;
          }
        }).catch(function () { btn.disabled = false; });
      });
    }

    var form = $("#loginForm");
    if (!form) return;
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var btn = $("#loginBtn");
      btn.disabled = true;
      api("/api/auth/login", {
        method: "POST",
        body: {
          username: $("#username").value.trim(),
          password: $("#password").value
        }
      }).then(function (res) {
        if (res.ok) {
          toast("登录成功（测试登录，非微信身份）");
          var next = new URLSearchParams(location.search).get("next") || "/";
          setTimeout(function () { location.href = next; }, 500);
        } else {
          toast(res.msg || "登录失败");
          btn.disabled = false;
        }
      }).catch(function () { btn.disabled = false; });
    });
  }

  /* ---------------- 我的：组织关系转接申请 ---------------- */
  function initMe() {
    var form = $("#transferForm");
    if (!form) return;
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var btn = $("#transferBtn");
      btn.disabled = true;
      api("/api/transfers", {
        method: "POST",
        body: {
          direction: $("#trDirection").value,
          from_org: $("#trFrom").value.trim(),
          to_org: $("#trTo").value.trim(),
          reason: $("#trReason").value.trim()
        }
      }).then(function (res) {
        if (res.ok) {
          toast(res.msg || "申请已提交，等待支部审核");
          setTimeout(function () { location.reload(); }, 700);
        } else {
          toast(res.msg || "提交失败");
          btn.disabled = false;
        }
      }).catch(function () { btn.disabled = false; });
    });
  }

  /* ---------------- 启动 ---------------- */
  document.addEventListener("DOMContentLoaded", function () {
    buildMenuBar();
    bindBack();
    initHome();
    initStudy();
    initArticle();
    initActivities();
    initActivityDetail();
    initLedger();
    initDashboard();
    initLogin();
    initMe();
  });
})();
