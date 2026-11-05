# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    page = ctx.new_page()
    ctx.request.post("http://127.0.0.1:5000/api/auth/login", data={"username": "zhangsan", "password": "Test@123456"})
    page.goto("http://127.0.0.1:5000/me", wait_until="networkidle")
    page.wait_for_timeout(600)
    txt = page.inner_text("body")
    i = txt.find("我的党费")
    print(txt[i:i+900] if i >= 0 else "没找到「我的党费」")
    page.evaluate("""() => {
      const el = [...document.querySelectorAll('*')].find(e => e.scrollHeight > e.clientHeight + 50 && getComputedStyle(e).overflowY !== 'visible');
      if (el) el.scrollTop = el.scrollHeight; else window.scrollTo(0, document.body.scrollHeight);
    }""")
    page.wait_for_timeout(500)
    page.screenshot(path=r"D:\GZH\hxai_dangjian\docs\shots\me_bottom.png")
    b.close()
