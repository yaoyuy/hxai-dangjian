
# -*- coding: utf-8 -*-
import sys
from playwright.sync_api import sync_playwright

base = "http://127.0.0.1:5000"
out = r"D:\GZH\hxai_dangjian\docs\shots"

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")
    ctx = b.new_context(viewport={"width":390,"height":844}, device_scale_factor=2)
    pg = ctx.new_page()
    pg.goto(base + "/", wait_until="networkidle")
    pg.wait_for_timeout(500)
    pg.screenshot(path=out + r"\ui_home.png")
    # 点底部“党建学习”，让子菜单弹出来
    try:
        pg.click('button[data-menu="0"]', timeout=8000)
        pg.wait_for_timeout(700)
        pg.screenshot(path=out + r"\ui_home_submenu.png")
        print("submenu shot ok")
    except Exception as e:
        print("submenu click failed:", e)
    # 切到学习专栏
    try:
        pg.goto(base + "/study", wait_until="networkidle")
        pg.wait_for_timeout(400)
        pg.screenshot(path=out + r"\ui_study.png")
    except Exception as e:
        print("study failed:", e)
    b.close()
print("done")
