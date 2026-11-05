#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""小程序前端静态自检（不依赖微信开发者工具）。

用途：写完 miniprogram/ 之后，快速确认工程结构和接口路径没写错。
检查项：
  1. 必备工程文件是否存在（project.config.json / app.json / app.js / app.wxss / config.js / custom-tab-bar / utils）
  2. app.json 是合法 JSON，pages 列出的每个页面都有 .js/.json/.wxml 文件
  3. tabBar.custom == true，且 tabBar.list 里的页面都在 pages 里
  4. project.config.json 是合法 JSON，urlCheck == false
  5. 全仓（.js/.wxml）里出现的 /api/... 路径都能在后端真实路由表里对上
  6. 前端文案里没有伪造微信身份的字眼

用法：.venv/Scripts/python.exe -X utf8 tools/check_miniprogram.py
"""
import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MP_DIR = BASE_DIR / "miniprogram"

# 后端真实存在的接口路径（2026-10-25 用 Flask url_map 导出）
KNOWN_APIS = {
    "/api/activities", "/api/activities/<id>", "/api/activities/<id>/cancel",
    "/api/activities/<id>/enroll", "/api/activities/<id>/enrollments",
    "/api/articles", "/api/articles/<id>", "/api/articles/<id>/study",
    "/api/auth/bind-openid", "/api/auth/config", "/api/auth/login",
    "/api/auth/logout", "/api/auth/me", "/api/auth/wechat-login",
    "/api/categories", "/api/dues/my", "/api/dues/summary", "/api/gallery",
    "/api/ledger", "/api/ledger/categories", "/api/ledger/<id>/download",
    "/api/stats/activity-participation", "/api/stats/dues", "/api/stats/learning",
    "/api/stats/members", "/api/stats/monthly", "/api/stats/overview",
    "/api/transfers", "/api/transfers/my",
    "/api/wechat/menu/push", "/api/wechat/status",
}
# 允许以「前缀 + 动态 id」形式出现的路径
API_PREFIXES = ["/api/articles/", "/api/activities/", "/api/ledger/"]

INTERP = "${"  # 小程序里的字符串插值标记（由脚本自动替换）

ok_count = 0
fail_count = 0
warnings = []


def ok(msg: str) -> None:
    global ok_count
    ok_count += 1
    print("[OK]   " + msg)


def fail(msg: str) -> None:
    global fail_count
    fail_count += 1
    print("[FAIL] " + msg)


def warn(msg: str) -> None:
    warnings.append(msg)
    print("[WARN] " + msg)


def main() -> int:
    if not MP_DIR.is_dir():
        fail("目录不存在：" + str(MP_DIR))
        print("\n结果：通过 0 项，失败 1 项")
        return 1

    required = [
        "project.config.json", "app.json", "app.js", "app.wxss", "config.js",
        "utils/api.js", "utils/auth.js",
        "custom-tab-bar/index.js", "custom-tab-bar/index.json",
        "custom-tab-bar/index.wxml", "custom-tab-bar/index.wxss",
        "README.md",
    ]
    for rel in required:
        if (MP_DIR / rel).is_file():
            ok("存在 " + rel)
        else:
            fail("缺少 " + rel)

    app_json_path = MP_DIR / "app.json"
    pages = []
    if app_json_path.is_file():
        try:
            app_cfg = json.loads(app_json_path.read_text(encoding="utf-8"))
            ok("app.json 是合法 JSON")
        except Exception as exc:  # noqa: BLE001
            fail("app.json 解析失败：" + str(exc))
            app_cfg = {}
        pages = app_cfg.get("pages", []) or []
        if pages:
            ok("app.json 声明了 " + str(len(pages)) + " 个页面")
        else:
            fail("app.json 的 pages 为空")
        for page in pages:
            missing = [ext for ext in (".js", ".json", ".wxml") if not (MP_DIR / (page + ext)).is_file()]
            if missing:
                fail("页面 " + page + " 缺少文件：" + ", ".join(missing))
            elif not (MP_DIR / (page + ".wxss")).is_file():
                warn("页面 " + page + " 没有 .wxss（样式若都在 app.wxss 可接受）")
        tab = app_cfg.get("tabBar") or {}
        if tab.get("custom") is True:
            ok("tabBar.custom = true（自定义 tabBar）")
        else:
            fail("tabBar.custom 不是 true，底部菜单不会按样例那样弹子菜单")
        for item in tab.get("list", []) or []:
            pg = str(item.get("pagePath", "")).lstrip("/")
            if pg and pg not in pages:
                fail("tabBar.list 里的 " + pg + " 不在 pages 里")
            elif pg:
                ok("tabBar.list 页面 " + pg + " 已声明")

    pc_path = MP_DIR / "project.config.json"
    if pc_path.is_file():
        try:
            pc = json.loads(pc_path.read_text(encoding="utf-8"))
            ok("project.config.json 是合法 JSON")
        except Exception as exc:  # noqa: BLE001
            fail("project.config.json 解析失败：" + str(exc))
            pc = {}
        setting = pc.get("setting") or {}
        if setting.get("urlCheck") is False:
            ok("project.config.json 已关闭 urlCheck（可连 http:// 内网地址）")
        else:
            warn("project.config.json 的 setting.urlCheck 不是 false，需在开发者工具里手动勾选“不校验合法域名”")
        if pc.get("appid"):
            ok("appid = " + str(pc.get("appid")))
        else:
            warn("project.config.json 没有 appid")

    api_re = re.compile(r"/api/[A-Za-z0-9_\-/<>$]*")
    bad = set()
    seen = set()
    for path in MP_DIR.rglob("*"):
        if path.suffix not in (".js", ".wxml"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for raw in api_re.findall(text):
            cleaned = raw.split("?")[0].rstrip("/")
            if not cleaned.startswith("/api/") and cleaned != "/api":
                continue
            if cleaned in KNOWN_APIS:
                seen.add(cleaned)
                continue
            if any(cleaned.startswith(p) for p in API_PREFIXES) or INTERP in cleaned:
                seen.add(cleaned)
                continue
            bad.add(str(path.relative_to(BASE_DIR)) + " -> " + cleaned)
    if bad:
        for item in sorted(bad):
            fail("接口路径不在后端路由表里：" + item)
    else:
        ok("所有 /api/ 路径都能在后端路由表里对上")
    if seen:
        ok("用到了 " + str(len(seen)) + " 个接口路径")

    for path in MP_DIR.rglob("*.js"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "已获取微信授权" in text or "真实openid" in text:
            warn(str(path.relative_to(BASE_DIR)) + " 里出现疑似伪造微信身份的字眼")

    print("\n结果：通过 " + str(ok_count) + " 项，失败 " + str(fail_count) + " 项，警告 " + str(len(warnings)) + " 条")
    return 1 if fail_count else 0


if __name__ == "__main__":
    sys.exit(main())
