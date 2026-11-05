# -*- coding: utf-8 -*-
"""用 Edge 无头模式给每个页面截图，做视觉回归检查。

用法：
    python -X utf8 tools/screenshot.py                       # 默认前台 12 张
    python -X utf8 tools/screenshot.py --base http://127.0.0.1:5099 --admin

前台按手机宽度（390x844）拍，因为最终是在微信里打开的；
后台按桌面宽度（1280x800）拍，因为管理员是在电脑上录入数据。
"""
import argparse
import sys

from playwright.sync_api import sync_playwright

PAGES = [
    ("index", "/"),
    ("study", "/study"),
    ("article", "/article/1"),
    ("meetings", "/meetings"),
    ("activities", "/activities"),
    ("activity_detail", "/activity/1"),
    ("ledger", "/ledger"),
    ("gallery", "/gallery"),
    ("dashboard", "/dashboard"),
    ("login", "/login"),
    ("me", "/me"),
]

ADMIN_PAGES = [
    ("admin_index", "/admin/"),
    ("admin_articles", "/admin/articles"),
    ("admin_article_edit", "/admin/articles/1"),
    ("admin_activities", "/admin/activities"),
    ("admin_activity_edit", "/admin/activities/1"),
    ("admin_users", "/admin/users"),
    ("admin_gallery", "/admin/gallery"),
    # 方案 A 新增的四个后台页
    ("admin_wechat", "/admin/wechat"),
    ("admin_whitelist", "/admin/whitelist"),
    ("admin_dues", "/admin/dues"),
    ("admin_transfers", "/admin/transfers"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5099")
    ap.add_argument("--out", default=r"D:\GZH\hxai_dangjian\docs\shots")
    ap.add_argument("--admin", action="store_true", help="同时拍后台页面（会先登录）")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default="Admin@123456")
    args = ap.parse_args()

    base = args.base.rstrip("/")
    out = args.out
    errs = []

    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)

        # ---------- 前台（手机宽度） ----------
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        page = ctx.new_page()
        page.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))

        for name, path in PAGES:
            page.goto(base + path, wait_until="networkidle")
            page.wait_for_timeout(600)
            page.screenshot(path=out + "\\" + name + ".png", full_page=True)
            print("shot", name, path)

        # 底部菜单浮层
        page.goto(base + "/", wait_until="networkidle")
        page.click('button[data-menu="0"]')
        page.wait_for_timeout(400)
        page.screenshot(path=out + "\\menu_submenu.png")
        print("shot menu_submenu")

        # ---------- 后台（桌面宽度） ----------
        if args.admin:
            actx = b.new_context(viewport={"width": 1280, "height": 820})
            apage = actx.new_page()
            apage.on("pageerror", lambda e: errs.append("admin pageerror: " + str(e)))

            # 用接口登录，浏览器上下文自带 cookie
            resp = actx.request.post(
                base + "/api/auth/login",
                data={"username": args.user, "password": args.password},
            )
            if not resp.ok:
                print("后台登录失败", resp.status, resp.text()[:200])
                return 1

            for name, path in ADMIN_PAGES:
                apage.goto(base + path, wait_until="networkidle")
                apage.wait_for_timeout(400)
                apage.screenshot(path=out + "\\" + name + ".png", full_page=True)
                print("shot", name, path)

        print("ERRORS:", errs if errs else "none")
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
