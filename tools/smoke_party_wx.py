"""党务 + 微信登录 冒烟测试（真实 HTTP，不 mock）。

覆盖方案 A 新增的四块：
1) 微信设置（存数据库、密钥脱敏、留空不覆盖、连接测试）；
2) 微信登录白名单 + openid 登录链路（含未授权时的如实报错与开发联调）；
3) 党费（批量生成、标记已缴、个人明细、看板接口）；
4) 组织关系转接（提交、防重复、审核）。

用法：
    .venv/Scripts/python.exe -X utf8 tools/smoke_party_wx.py --base http://127.0.0.1:5000
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import uuid
from pathlib import Path

import requests

BASE = "http://127.0.0.1:5000"
DB_PATH = "data/dangjian.db"
ADMIN = ("admin", "Admin@123456")
MEMBER = ("zhangsan", "Test@123456")

passed = 0
failed = 0


def check(name: str, ok: bool, extra: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"[OK]   {name}")
    else:
        failed += 1
        print(f"[FAIL] {name} {extra}")


def login(username: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"username": username, "password": password}, timeout=10)
    assert r.status_code == 200 and r.json().get("ok"), r.text[:200]
    return s


def cleanup_smoke_rows() -> None:
    """删掉上一次运行留下的 openid 测试数据，保证脚本可以反复跑。

    只删带 smoke_openid_ 前缀的行，绝不碰演示数据和真实数据。
    """
    db = Path(DB_PATH)
    if not db.exists():
        return
    con = sqlite3.connect(str(db))
    try:
        con.execute("delete from login_whitelist where openid like 'smoke_openid_%'")
        con.execute("delete from user where openid like 'smoke_openid_%' and username like 'wx_%'")
        con.commit()
    finally:
        con.close()


def whitelist_id_of(openid: str) -> int | None:
    """按 openid 精确查白名单行 id（比从 HTML 里抓更可靠）。"""
    db = Path(DB_PATH)
    if not db.exists():
        return None
    con = sqlite3.connect(str(db))
    try:
        row = con.execute("select id from login_whitelist where openid = ? order by id desc", (openid,)).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def main() -> int:
    global BASE, DB_PATH
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--db", default=DB_PATH, help="SQLite 文件路径（用于清理测试残留）")
    args = ap.parse_args()
    BASE = args.base.rstrip("/")
    DB_PATH = args.db
    cleanup_smoke_rows()

    admin = login(*ADMIN)

    # ---------- 1. 微信设置 ----------
    r = admin.get(f"{BASE}/admin/wechat", timeout=10)
    check("后台微信设置页可打开", r.status_code == 200 and "微信设置" in r.text)

    secret = "secretvalue123456"
    r = admin.post(f"{BASE}/admin/wechat", data={
        "wxapp_appid": "wxtestappid123",
        "wxapp_appsecret": secret,
        "login_mode": "both",
        "whitelist_enabled": "1",
        "oauth_scope": "snsapi_base",
        "wechat_appid": "", "wechat_appsecret": "", "wechat_token": "", "wechat_aeskey": "",
        "site_notice": "冒烟测试公告",
    }, timeout=10)
    check("保存微信设置返回 200", r.status_code == 200)
    check("密钥在页面上被脱敏（不出现完整值）", secret not in r.text and "secr****56" in r.text)

    cfg = requests.get(f"{BASE}/api/auth/config", timeout=10).json().get("data", {})
    check("保存后小程序判定为已配置", bool(cfg.get("wxapp_configured")), str(cfg))
    check("登录方式已切到 both", cfg.get("login_mode") == "both", str(cfg.get("login_mode")))
    check("测试登录仍然可用（both 模式）", cfg.get("test_login_allowed") is True)

    # 密钥留空 = 不覆盖
    r = admin.post(f"{BASE}/admin/wechat", data={
        "wxapp_appid": "wxtestappid123", "wxapp_appsecret": "",
        "login_mode": "both", "whitelist_enabled": "1", "oauth_scope": "snsapi_base",
    }, timeout=10)
    cfg2 = requests.get(f"{BASE}/api/auth/config", timeout=10).json().get("data", {})
    check("密钥留空不会清空已保存的值", cfg2.get("wxapp_configured") is True)

    r = admin.post(f"{BASE}/admin/wechat/test", timeout=20)
    check("连接测试如实返回结果（成功或失败都算通过）", r.status_code == 200 and "access_token" in r.text)

    r = admin.post(f"{BASE}/admin/wechat/menu", timeout=20)
    check("推送菜单返回可读结果（个人号 48001 属正常）", r.status_code == 200 and "菜单" in r.text)

    # ---------- 2. 白名单 + openid 登录 ----------
    r = admin.get(f"{BASE}/admin/whitelist", timeout=10)
    check("白名单页可打开", r.status_code == 200 and "白名单" in r.text)

    # 每次运行都用新的 openid，避免上一次的残留让「不在白名单」检查误判
    dev_openid = "smoke_openid_dev_" + uuid.uuid4().hex[:8]
    r = requests.post(f"{BASE}/api/auth/wechat-login", json={"type": "wxapp", "dev_openid": dev_openid}, timeout=10)
    check("不在白名单的 openid 被拒绝（403 not_in_whitelist）",
          r.status_code == 403 and r.json().get("code") == "not_in_whitelist", r.text[:200])

    r = admin.post(f"{BASE}/admin/whitelist", data={
        "name": "冒烟测试员", "phone": "13900000001", "openid": dev_openid,
        "role": "member", "note": "smoke test",
    }, timeout=10)
    check("添加白名单成功", r.status_code == 200 and "冒烟测试员" in r.text)

    r = requests.post(f"{BASE}/api/auth/wechat-login", json={"type": "wxapp", "dev_openid": dev_openid}, timeout=10)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    check("白名单内的 openid 可以登录", r.status_code == 200 and body.get("ok") is True, r.text[:200])
    session_cookie = r.cookies.get("session")
    uid1 = (body.get("data") or {}).get("user", {}).get("id") if isinstance(body.get("data"), dict) else None
    notice_text = str((body.get("data") or {}).get("notice", "")) + str(body.get("msg", ""))
    check("登录返回里注明是本地联调（非真实微信授权）",
          "非真实微信授权" in notice_text, notice_text[:140])

    r = requests.post(f"{BASE}/api/auth/wechat-login", json={"type": "wxapp", "dev_openid": dev_openid}, timeout=10)
    uid2 = (r.json().get("data") or {}).get("user", {}).get("id") if r.status_code == 200 else None
    check("同一 openid 重复登录不会重复建号", uid1 is not None and uid1 == uid2, f"{uid1} vs {uid2}")

    # 停用后立刻拒绝
    wl_id = whitelist_id_of(dev_openid)
    if wl_id:
        admin.post(f"{BASE}/admin/whitelist/{wl_id}/toggle", timeout=10)
        r = requests.post(f"{BASE}/api/auth/wechat-login", json={"type": "wxapp", "dev_openid": dev_openid}, timeout=10)
        check("停用白名单后该 openid 被拒绝（whitelist_disabled）",
              r.status_code == 403 and r.json().get("code") == "whitelist_disabled", r.text[:200])
        admin.post(f"{BASE}/admin/whitelist/{wl_id}/toggle", timeout=10)

    # 绑定 openid
    member = login(*MEMBER)
    bind_openid = "smoke_openid_bind_" + uuid.uuid4().hex[:8]
    r = member.post(f"{BASE}/api/auth/bind-openid", json={"openid": bind_openid}, timeout=10)
    check("登录后可以把 openid 绑到自己的账号", r.status_code == 200 and r.json().get("ok") is True, r.text[:200])
    other = login("lisi", "Test@123456")
    r = other.post(f"{BASE}/api/auth/bind-openid", json={"openid": bind_openid}, timeout=10)
    check("别人不能绑同一个 openid（409）", r.status_code == 409, r.text[:200])

    r = admin.post(f"{BASE}/admin/whitelist/{wl_id}/delete", timeout=10) if wl_id else None
    check("删除白名单成功", r is None or r.status_code == 200)

    # ---------- 3. 党费 ----------
    period = "2026-05"
    r = admin.post(f"{BASE}/admin/dues/generate", data={"period": period, "amount": "10"}, timeout=10)
    check("批量生成党费返回 200", r.status_code == 200)
    r = admin.get(f"{BASE}/admin/dues?period={period}", timeout=10)
    check("党费页可以按期间查看", r.status_code == 200 and period in r.text)
    check("党费页显示汇总（不是写死数字）", "缴费率" in r.text and "应缴人数" in r.text)

    stats = requests.get(f"{BASE}/api/stats/dues", timeout=10).json().get("data", {})
    trend_periods = [t.get("period") for t in (stats.get("trend") or [])]
    check("看板党费接口包含新期间", period in trend_periods, str(trend_periods))
    check("看板党费汇总字段齐全",
          all(k in (stats.get("summary") or {}) for k in ("total", "paid", "unpaid", "pay_rate", "amount_paid")))

    mine = member.get(f"{BASE}/api/dues/my", timeout=10).json().get("data", {})
    check("我的党费接口返回明细与汇总", "list" in mine and "summary" in mine)
    due_rows = mine.get("list") or []
    if due_rows:
        due_id = due_rows[0]["id"]
        before = due_rows[0]["status"]
        r = admin.post(f"{BASE}/admin/dues/{due_id}/status",
                       data={"status": "unpaid" if before != "unpaid" else "paid"}, timeout=10)
        check("可以标记党费已缴 / 改回未缴", r.status_code == 200)
        after = member.get(f"{BASE}/api/dues/my", timeout=10).json()["data"]["list"][0]["status"]
        check("状态变更后个人接口立即变化", after != before, f"{before} -> {after}")
        # 还原
        admin.post(f"{BASE}/admin/dues/{due_id}/status", data={"status": before}, timeout=10)

    overview = requests.get(f"{BASE}/api/stats/overview", timeout=10).json().get("data", {})
    check("总览接口包含党费与转接待办字段",
          all(k in overview for k in ("dues_total", "dues_paid", "dues_unpaid", "dues_paid_rate", "transfers_pending")))

    # ---------- 4. 组织关系转接 ----------
    r = member.post(f"{BASE}/api/transfers", json={
        "direction": "out", "from_org": "第一党支部", "to_org": "冒烟测试目标单位", "reason": "smoke",
    }, timeout=10)
    check("党员可以提交转接申请（201）", r.status_code == 201 and r.json().get("ok") is True, r.text[:200])
    tid = r.json().get("data", {}).get("id")
    r = member.post(f"{BASE}/api/transfers", json={
        "direction": "out", "from_org": "第一党支部", "to_org": "另一个单位", "reason": "duplicate",
    }, timeout=10)
    check("重复提交待审核申请被拒（409）", r.status_code == 409, r.text[:200])
    r = member.post(f"{BASE}/api/transfers", json={"direction": "out", "from_org": "", "to_org": ""}, timeout=10)
    check("缺单位名称被拒（400）", r.status_code == 400, r.text[:200])

    mine_t = member.get(f"{BASE}/api/transfers/my", timeout=10).json().get("data", [])
    check("我的转接申请可查", any(t.get("id") == tid for t in mine_t))
    r = admin.get(f"{BASE}/admin/transfers", timeout=10)
    check("后台转接页可打开且能看到申请", r.status_code == 200 and "冒烟测试目标单位" in r.text)

    r = admin.post(f"{BASE}/admin/transfers/{tid}/review", data={"action": "approve", "review_note": "冒烟通过"}, timeout=10)
    check("后台审核通过返回 200", r.status_code == 200)
    mine_t = member.get(f"{BASE}/api/transfers/my", timeout=10).json()["data"]
    target = [t for t in mine_t if t.get("id") == tid]
    check("审核结果前台可见（approved）", bool(target) and target[0]["status"] == "approved", str(target)[:200])
    r = admin.post(f"{BASE}/admin/transfers/{tid}/review", data={"action": "approve"}, timeout=10)
    check("重复审核被拒绝并给出提示", r.status_code == 200 and "已经处理过" in r.text)
    r = admin.post(f"{BASE}/admin/transfers/{tid}/delete", timeout=10)
    check("删除转接记录成功", r.status_code == 200)

    # ---------- 5. 权限：普通党员不能进后台新页面 ----------
    for path in ("/admin/wechat", "/admin/whitelist", "/admin/dues", "/admin/transfers"):
        r = member.get(f"{BASE}{path}", timeout=10)
        check(f"普通党员访问 {path} 被拒（403）", r.status_code == 403, str(r.status_code))

    # ---------- 6. 前台页面 ----------
    for path, keyword in (("/login", "测试登录"), ("/me", "我的党费"), ("/dashboard", "党费缴纳情况")):
        r = member.get(f"{BASE}{path}", timeout=10)
        check(f"前台 {path} 可打开且包含「{keyword}」", r.status_code == 200 and keyword in r.text, str(r.status_code))

    # 收尾：清掉本次产生的 openid 测试数据（白名单行 + 自动建的临时账号）
    cleanup_smoke_rows()

    print(f"\n结果：通过 {passed} 项，失败 {failed} 项")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
