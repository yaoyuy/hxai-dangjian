"""后台管理冒烟测试（真实 HTTP 请求，不 mock）。

为什么单独写：手工用 curl 测中文时，Git Bash 会把中文按 GBK 发出去，
服务端存进来就是乱码——那是终端编码问题，不是系统问题。
用 requests 显式 UTF-8 发请求，才能验证"中文能正确入库/显示"。

运行：
    .venv/Scripts/python.exe -X utf8 tools/smoke_admin.py --base http://127.0.0.1:5099
"""
from __future__ import annotations

import argparse
import sys

import requests

OK = "\033[32m✓\033[0m"
BAD = "\033[31m✗\033[0m"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5099")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default="Admin@123456")
    args = ap.parse_args()

    s = requests.Session()
    base = args.base.rstrip("/")
    failures: list[str] = []

    def check(name: str, cond: bool, extra: str = "") -> None:
        print(f"{OK if cond else BAD} {name}{(' — ' + extra) if extra else ''}")
        if not cond:
            failures.append(name)

    # 1. 未登录访问后台应跳登录
    r = s.get(f"{base}/admin/", allow_redirects=False)
    check("未登录访问 /admin/ 会跳转登录", r.status_code == 302 and "/login" in r.headers.get("Location", ""),
          f"{r.status_code} {r.headers.get('Location','')}")

    # 2. 登录
    r = s.post(f"{base}/api/auth/login", json={"username": args.user, "password": args.password})
    check("管理员登录成功", r.status_code == 200 and r.json().get("ok"), r.text[:120])

    # 3. 后台各页面可访问
    for path in ["/admin/", "/admin/articles", "/admin/activities", "/admin/users", "/admin/gallery"]:
        r = s.get(f"{base}{path}")
        check(f"{path} 返回 200", r.status_code == 200, str(r.status_code))

    # 4. 创建中文草稿 → 前台不可见 → 发布 → 前台可见 → 删除
    title = "测试用例：11 月支部学习安排（自动化）"
    r = s.post(f"{base}/admin/articles", data={
        "title": title,
        "summary": "自动化测试写入的摘要，含中文。",
        "content": "第一段内容。\n第二段内容。",
        "category_id": "1",
        "study_minutes": "6",
        "status": "draft",
    }, allow_redirects=False)
    check("创建草稿成功（302 回列表）", r.status_code == 302, str(r.status_code))

    listing = s.get(f"{base}/api/articles", params={"size": 100}).json()["data"]
    titles = [a["title"] for a in listing]
    check("中文标题未乱码（草稿不在前台列表）", title not in titles, "草稿不应出现在前台")

    # 从后台草稿页找出刚创建的 id
    html = s.get(f"{base}/admin/articles", params={"status": "draft"}).text
    check("后台草稿页能看到该中文标题", title in html)

    import re
    ids = re.findall(r"/admin/articles/(\d+)", html)
    new_id = None
    # 找到标题后紧跟的那个 id —— 用更稳的办法：逐个比较
    for aid in sorted({int(i) for i in ids}):
        page = s.get(f"{base}/admin/articles/{aid}").text
        if title in page:
            new_id = aid
            break
    check("能定位到新建文章的 id", new_id is not None, str(new_id))

    if new_id:
        s.post(f"{base}/admin/articles/{new_id}/status", allow_redirects=False)
        listing = s.get(f"{base}/api/articles", params={"size": 100}).json()["data"]
        check("发布后出现在前台列表", any(a["title"] == title for a in listing))
        check("前台详情页中文正常", title in s.get(f"{base}/article/{new_id}").text)

        s.post(f"{base}/admin/articles/{new_id}/delete", allow_redirects=False)
        listing = s.get(f"{base}/api/articles", params={"size": 100}).json()["data"]
        check("删除后前台列表不再包含", not any(a["title"] == title for a in listing))

    # 5. 创建活动 + 后台看到报名名单
    r = s.post(f"{base}/admin/activities", data={
        "title": "测试活动：志愿服务（自动化）",
        "kind": "volunteer",
        "start_at": "2027-01-10T09:00",
        "signup_deadline": "2027-01-05T18:00",
        "location": "社区服务中心",
        "target": "全体党员",
        "capacity": "20",
        "summary": "自动化测试创建",
        "content": "1. 集合\n2. 服务",
        "status": "open",
    }, allow_redirects=False)
    check("创建活动成功", r.status_code == 302, str(r.status_code))

    acts = s.get(f"{base}/api/activities", params={"size": 100}).json()["data"]
    act = next((a for a in acts if a["title"].startswith("测试活动：志愿服务")), None)
    check("活动出现在前台接口且中文正常", act is not None)
    if act:
        # 报名（当前 admin 身份）
        r = s.post(f"{base}/api/activities/{act['id']}/enroll")
        check("能报名", r.status_code == 200, r.text[:120])
        # 后台名单里能看到
        html = s.get(f"{base}/admin/activities/{act['id']}").text
        check("后台报名名单显示报名人", "系统管理员" in html)
        # 清理
        s.post(f"{base}/admin/activities/{act['id']}/delete", allow_redirects=False)
        acts = s.get(f"{base}/api/activities", params={"size": 100}).json()["data"]
        check("删除活动成功", not any(a["id"] == act["id"] for a in acts))

    # 6. 普通党员访问后台应 403
    s2 = requests.Session()
    s2.post(f"{base}/api/auth/login", json={"username": "zhangsan", "password": "Test@123456"})
    r = s2.get(f"{base}/admin/", allow_redirects=False)
    check("普通党员访问后台被拒（403）", r.status_code == 403, str(r.status_code))

    print()
    if failures:
        print(f"失败 {len(failures)} 项：" + "、".join(failures))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
