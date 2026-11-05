"""初始化数据脚本（可重复执行，不会重复插入）。

用途：本地第一次跑起来就有真实可点的数据。
注意：所有自动生成的内容都打 is_demo=True，页面会显示「测试数据」标签，
      管理员录入真实资料后可以删掉这些演示数据。

用法：
    python -m backend.seed          # 只在库为空时插入
    python -m backend.seed --force  # 强制补齐缺失的演示数据
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta

from .extensions import db
from .models import (
    Activity,
    Article,
    Branch,
    Category,
    Enrollment,
    GalleryPhoto,
    LedgerFile,
    OrgTransfer,
    PartyDue,
    StudyRecord,
    User,
    Whitelist,
)

# 学习专栏分类（与前端 tab 的 code 一一对应）
CATEGORIES = [
    ("理论学习", "theory", 1),
    ("党史学习", "history", 2),
    ("云党课", "cloud", 3),
    ("重要文件", "doc", 4),
]

# 台账分类与 api/ledger.py 的 LEDGER_CATEGORIES 保持一致
LEDGER_CATS = ["会议记录", "活动资料", "学习材料", "制度文件", "其他"]


def _days_ago(n: int, hour: int = 9) -> datetime:
    """n 天前（n 为负数时表示 n 天后）。"""
    d = datetime.now() - timedelta(days=n)
    return d.replace(hour=hour, minute=0, second=0, microsecond=0)


def _month_ago(n: int) -> str:
    """n 个月前的期间（YYYY-MM），用于演示党费记录。"""
    year, month = datetime.now().year, datetime.now().month
    month -= n
    while month <= 0:
        month += 12
        year -= 1
    return f"{year}-{month:02d}"


def seed(app=None, force: bool = False) -> dict:
    """写入初始化数据。返回统计信息，方便命令行输出。"""
    created = {"branch": 0, "users": 0, "categories": 0, "articles": 0,
               "activities": 0, "files": 0, "photos": 0, "enrollments": 0,
               "settings": 0, "whitelist": 0, "dues": 0, "transfers": 0}

    # ---------- 支部 ----------
    branch = Branch.query.filter_by(code="default").first()
    if branch is None:
        branch = Branch(name=app.config["BRANCH_NAME"] if app else "第一党支部", code="default")
        db.session.add(branch)
        db.session.flush()
        created["branch"] = 1

    # ---------- 管理员账号（账号密码来自 .env，不写死） ----------
    admin_username = app.config.get("ADMIN_USERNAME", "admin") if app else "admin"
    admin_password = app.config.get("ADMIN_PASSWORD", "Admin@123456") if app else "Admin@123456"
    admin_real = app.config.get("ADMIN_REAL_NAME", "系统管理员") if app else "系统管理员"

    admin = User.query.filter_by(username=admin_username).first()
    if admin is None:
        admin = User(
            username=admin_username,
            real_name=admin_real,
            role="super_admin",
            branch_id=branch.id,
            age_group="36-50岁",
            is_test_account=True,
        )
        admin.set_password(admin_password)
        db.session.add(admin)
        created["users"] += 1

    # ---------- 几个测试党员（用于看板党员构成有真实分布） ----------
    demo_members = [
        ("zhangsan", "张三", "35岁以下", "13800000001"),
        ("lisi", "李四", "36-50岁", "13800000002"),
        ("wangwu", "王五", "51岁以上", "13800000003"),
        ("zhaoliu", "赵六", "35岁以下", "13800000004"),
        ("sunqi", "孙七", "36-50岁", "13800000005"),
    ]
    member_users = []
    for username, real_name, age_group, phone in demo_members:
        u = User.query.filter_by(username=username).first()
        if u is None:
            u = User(
                username=username,
                real_name=real_name,
                role="member",
                branch_id=branch.id,
                age_group=age_group,
                phone=phone,
                is_test_account=True,
            )
            u.set_password("Test@123456")
            db.session.add(u)
            created["users"] += 1
        member_users.append(u)
    db.session.flush()

    # ---------- 分类 ----------
    cat_map = {}
    for name, code, order in CATEGORIES:
        c = Category.query.filter_by(code=code).first()
        if c is None:
            c = Category(name=name, code=code, sort_order=order)
            db.session.add(c)
            created["categories"] += 1
        cat_map[code] = c
    db.session.flush()

    # ---------- 文章 ----------
    articles_data = [
        ("theory", "读原著、学原文、悟原理：本月必读书目导读",
         "配套学习要点 6 条，读完可在文末打卡记录学习时长。", 8, 12),
        ("cloud", "第 12 讲：从党史故事里看初心",
         "主讲：支部特邀讲师。支持倍速与续播，观看计入学习时长。", 18, 8),
        ("history", "一图读懂：本地红色教育基地参观路线",
         "3 个点位、1 条路线，附开放时间与预约方式说明。", 6, 6),
        ("doc", "本支部年度学习计划与考核办法（试行）",
         "文件全文已同步到电子台账，可下载留存。", 5, 4),
        ("theory", "微党课：5 分钟讲清“三会一课”到底怎么开",
         "新党员必看系列第 3 集，动画讲解 + 图文对照。", 5, 3),
    ]
    article_rows = []
    for i, (code, title, summary, minutes, days) in enumerate(articles_data):
        exists = Article.query.filter_by(title=title).first()
        if exists:
            article_rows.append(exists)
            continue
        a = Article(
            title=title,
            summary=summary,
            content=(
                f"<p>{summary}</p>"
                "<p>（本段为初始化演示内容，标注为「测试数据」，管理员可在后台替换为真实材料。）</p>"
                "<p>学习要求：结合本职工作谈一次体会，形成不少于 300 字的学习笔记，"
                "在支部集中学习时交流。</p>"
            ),
            category_id=cat_map[code].id,
            cover_url="",
            study_minutes=minutes,
            duration_min=minutes,
            media_type="video" if code == "cloud" else "text",
            status="published",
            is_demo=True,
            view_count=100 + i * 47,
            published_at=_days_ago(days),
        )
        db.session.add(a)
        article_rows.append(a)
        created["articles"] += 1
    db.session.flush()

    # 一篇草稿，用来验证「草稿不对外可见」
    draft_title = "（草稿）11 月主题党日方案（待审）"
    if not Article.query.filter_by(title=draft_title).first():
        db.session.add(Article(
            title=draft_title,
            summary="这是一篇草稿，前台列表看不到，只有管理员能预览。",
            content="<p>草稿内容，用于验证状态区分。</p>",
            category_id=cat_map["doc"].id,
            status="draft",
            is_demo=True,
            study_minutes=5,
        ))
        created["articles"] += 1
    db.session.flush()

    # ---------- 活动 / 三会一课 ----------
    # start_offset：正数=已经办过的天数；负数=还有几天开始（未来活动才能报名）
    # signup_offset：报名截止时间相对今天的天数（未来活动给未来时间，否则会被判"报名已截止"）
    # (kind, 标题, 简介, 地点, 开始偏移天数, 名额, 状态, 报名截止偏移天数)
    # 偏移为负数表示"未来"，正数表示"过去"。
    activities_data = [
        ("party_day", "支部 10 月主题党日：学习、议事、志愿服务一次讲清",
         "红色教育基地参观学习", "本地红色教育基地（示例点位）", -5, 32, "open", -2),
        ("meeting", "支部党员大会：讨论发展党员与年度评优",
         "支部党员大会", "支部会议室（示例）", -12, 0, "open", -9),
        ("volunteer", "党员志愿服务：社区助老集中行动",
         "志愿服务", "社区服务中心（示例）", -9, 20, "open", -6),
        ("study", "党课学习：党章专题辅导",
         "党课学习", "支部活动室（示例）", 6, 0, "finished", 4),
        ("meeting", "支委会：研究 11 月组织生活安排",
         "支委会", "线上会议（示例）", 13, 0, "finished", 11),
    ]
    act_rows = []
    for (kind, title, summary, location, start_offset, capacity, status,
         signup_offset) in activities_data:
        exists = Activity.query.filter_by(title=title).first()
        if exists:
            act_rows.append(exists)
            continue
        a = Activity(
            title=title,
            kind=kind,
            summary=summary,
            content=(
                "<p>1. 集中学习（30 分钟）<br>"
                "2. 议事讨论（20 分钟）<br>"
                "3. 志愿服务安排（10 分钟）</p>"
                "<p>（演示内容，标注为「测试数据」。）</p>"
            ),
            location=location,
            start_at=_days_ago(start_offset, 19),
            signup_deadline=_days_ago(signup_offset, 18),
            capacity=capacity,
            target="全体党员、入党积极分子",
            status=status,
            is_demo=True,
        )
        db.session.add(a)
        act_rows.append(a)
        created["activities"] += 1
    db.session.flush()

    # ---------- 报名记录（让看板和人数有真实来源） ----------
    for idx, a in enumerate(act_rows):
        if a.status != "open":
            continue
        for j, u in enumerate(member_users[: (idx % 3) + 2]):
            exists = Enrollment.query.filter_by(activity_id=a.id, user_id=u.id).first()
            if exists:
                continue
            db.session.add(Enrollment(
                activity_id=a.id, user_id=u.id, status="confirmed",
                created_at=_days_ago(max(1, idx + 1)),
            ))
            created["enrollments"] += 1
    db.session.flush()

    # ---------- 学习记录 ----------
    for idx, a in enumerate(article_rows[:4]):
        for u in member_users[: 3 + (idx % 3)]:
            has = StudyRecord.query.filter_by(user_id=u.id, article_id=a.id).first()
            if has:
                continue
            db.session.add(StudyRecord(
                user_id=u.id, article_id=a.id, minutes=a.study_minutes,
                created_at=_days_ago(idx + 1),
            ))
    db.session.flush()

    # ---------- 台账文件元信息（磁盘上没有真实文件，下载会明确提示） ----------
    if LedgerFile.query.count() == 0:
        ledger_data = [
            ("2026年10月支委会会议纪要.docx", "docx", "会议记录", 131072, 7),
            ("第三季度党员大会记录.pdf", "pdf", "会议记录", 2202010, 14),
            ("10月主题党日活动方案与签到表.docx", "docx", "活动资料", 98304, 5),
            ("党员志愿服务结对名单.xlsx", "xlsx", "活动资料", 46080, 4),
            ("云党课第12讲课件.pptx", "pptx", "学习材料", 8808038, 3),
            ("本月必读书目导读.pdf", "pdf", "学习材料", 1363149, 6),
            ("支部年度学习计划与考核办法（试行）.pdf", "pdf", "制度文件", 880640, 12),
            ("三会一课制度汇编.docx", "docx", "制度文件", 215040, 30),
        ]
        for title, ext, cat, size, days in ledger_data:
            db.session.add(LedgerFile(
                title=title,
                filename=f"demo-placeholder.{ext}",   # 占位，磁盘上无实体文件
                original_name=title,
                category=cat if cat in LEDGER_CATS else "其他",
                ext=ext,
                size_bytes=size,
                uploader_id=admin.id,
                is_demo=True,
                download_count=(days * 3) % 17,
                created_at=_days_ago(days),
            ))
            created["files"] += 1

    # ---------- 党建风采 ----------
    if GalleryPhoto.query.count() == 0:
        photos = [
            ("支部党员大会现场", "2026 年第三季度党员大会"),
            ("主题党日 · 重温入党誓词", "10 月主题党日活动"),
            ("党员志愿服务进社区", "结对帮扶、助老服务"),
            ("党课学习研讨", "支部集中学习研讨"),
        ]
        for i, (title, desc) in enumerate(photos):
            db.session.add(GalleryPhoto(
                title=title, image_url="", description=desc,
                is_demo=True, created_at=_days_ago(i * 5 + 2),
            ))
            created["photos"] += 1

    # ---------- 微信登录白名单（对应 5 个测试党员；openid 留空，等本人首次微信登录自动补） ----------
    # 说明：个人订阅号拿不到 openid，这里先把名单建好，第二阶段 / 小程序接入后可直接用。
    if Whitelist.query.count() == 0:
        for u in member_users:
            db.session.add(Whitelist(
                name=u.real_name or u.username,
                phone=u.phone or "",
                openid=None,
                branch_id=branch.id,
                role="member",
                note="初始化演示白名单：openid 留空，首次微信登录时自动补全",
                is_active=True,
                user_id=u.id,
                is_demo=True,
            ))
            created["whitelist"] += 1

    # ---------- 党费记录（最近 3 个期间；当月留几条未缴，便于看板看出差异） ----------
    if PartyDue.query.count() == 0:
        for offset in range(3):
            period = _month_ago(offset)
            for idx, u in enumerate(member_users):
                unpaid_current = (offset == 0 and idx >= 3)   # 当月最后两位演示"未缴"
                status = "unpaid" if unpaid_current else "paid"
                db.session.add(PartyDue(
                    user_id=u.id,
                    period=period,
                    amount=10,
                    method="微信" if status == "paid" else "现金",
                    status=status,
                    paid_at=None if unpaid_current else _days_ago(offset * 28 + idx + 1, hour=10),
                    note="初始化演示数据" if status == "unpaid" else "",
                    operator_id=admin.id,
                    is_demo=True,
                    created_at=_days_ago(offset * 28 + 2),
                ))
                created["dues"] += 1

    # ---------- 组织关系转接（1 条待审核 + 1 条已通过） ----------
    if OrgTransfer.query.count() == 0 and len(member_users) >= 3:
        db.session.add(OrgTransfer(
            user_id=member_users[2].id,
            direction="out",
            from_org=branch.name,
            to_org="绵阳城市学院党委",
            reason="工作调动，申请转出组织关系（演示数据）",
            status="pending",
            is_demo=True,
            created_at=_days_ago(2),
        ))
        created["transfers"] += 1
        db.session.add(OrgTransfer(
            user_id=member_users[1].id,
            direction="in",
            from_org="中共XX大学委员会",
            to_org=branch.name,
            reason="毕业入职，申请转入（演示数据）",
            status="approved",
            apply_at=_days_ago(20),
            review_at=_days_ago(18),
            reviewer_id=admin.id,
            review_note="材料齐全，同意转入",
            is_demo=True,
            created_at=_days_ago(20),
        ))
        created["transfers"] += 1

    # ---------- 系统设置默认键（微信参数等；已存在的不覆盖） ----------
    try:
        from .settings_store import ensure_defaults
        created["settings"] = ensure_defaults()
    except Exception:  # 设置表异常不应导致初始化失败
        created["settings"] = 0

    db.session.commit()
    return created
