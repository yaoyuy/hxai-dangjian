# -*- coding: utf-8 -*-
"""临时检查：数据看板底部（党费/学习/活动参与）是否真的渲染出来了。"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    page = ctx.new_page()
    errs = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto("http://127.0.0.1:5000/dashboard", wait_until="networkidle")
    page.wait_for_timeout(1200)
    print("标题:", page.title())
    print("面板标题:", page.eval_on_selector_all(".card h3, .panel h3, section h3", "els => els.map(e => e.innerText)"))
    info = page.evaluate("""() => {
      const out = {};
      const d = document.querySelector('#duesStats');
      out.duesStats = d ? d.innerText : null;
      const t = document.querySelector('#duesTrend');
      out.duesTrend = t ? t.innerText : null;
      out.bodyScroll = document.body.scrollHeight;
      const sc = [...document.querySelectorAll('div')].map(e => e.scrollHeight).sort((a,b)=>b-a)[0];
      out.maxScroll = sc;
      return out;
    }""")
    print("duesStats:", info["duesStats"])
    print("duesTrend:", info["duesTrend"])
    print("体高:", info["bodyScroll"], "最大内部滚动:", info["maxScroll"])
    print("JS 错误:", errs if errs else "none")
    # 滚到底再拍一张，确认下半屏
    page.evaluate("""() => {
      const el = [...document.querySelectorAll('*')].find(e => e.scrollHeight > e.clientHeight + 50 && getComputedStyle(e).overflowY !== 'visible');
      if (el) el.scrollTop = el.scrollHeight;
      else window.scrollTo(0, document.body.scrollHeight);
    }""")
    page.wait_for_timeout(600)
    page.screenshot(path=r"D:\GZH\hxai_dangjian\docs\shots\dashboard_bottom.png")
    b.close()
