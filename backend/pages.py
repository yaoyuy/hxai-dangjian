"""页面路由（服务端渲染）。

设计要点：
1. 每个功能一个独立路由，不再是一个 HTML 塞所有页面。
2. 页面只负责输出首屏骨架，列表类数据由 static/js/app.js 调 /api/* 拿真实数据。
3. 文章详情、活动详情这类需要 SEO / 直接分享的页面，首屏就用数据库数据渲染。
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, abort, redirect, render_template, request, session, url_for
from sqlalchemy import func, or_

from config import resolve_public_base_url

from . import settings_store
from .api.ledger import LEDGER_CATEGORIES
from .api.party import summarize_dues
from .auth import current_user
from .extensions import db
from .models import (
    Activity,
    Article,
    Category,
    Enrollment,
    GalleryPhoto,
    OrgTransfer,
    PartyDue,
    StudyRecord,
)

bp = Blueprint("pages", __name__)


def _categories():
    return Category.query.order_by(Category.sort_order).all()


@bp.get("/")
def index():
    """首页：公众号主页样式 + 最新发布。"""
    return render_template("index.html")


@bp.get("/study")
def study():
    """学习专栏列表页：分类筛选 + 搜索（前端调接口）。"""
    return render_template("study.html", categories=_categories())


@bp.get("/article/<int:article_id>")
def article(article_id: int):
    """文章详情：首屏服务端渲染，阅读量真实累加。"""
    article = db.session.get(Article, article_id)
    if article is None:
        abort(404)
    user = current_user()
    # 草稿只有管理员能预览
    if article.status != "published" and not (user and user.is_admin):
        abort(404)

    article.view_count = (article.view_count or 0) + 1
    db.session.commit()

    my_total = 0
    if user:
        my_total = (
            db.session.query(func.coalesce(func.sum(StudyRecord.minutes), 0))
            .filter(StudyRecord.user_id == user.id)
            .scalar()
        ) or 0
    return render_template("article.html", article=article, my_total_minutes=int(my_total))


@bp.get("/meetings")
def meetings():
    """三会一课：会议、主题党日、党课等组织生活记录。"""
    rows = (
        Activity.query.filter(Activity.kind.in_(["meeting", "party_day", "study"]))
        .order_by(Activity.start_at.desc().nullslast(), Activity.id.desc())
        .all()
    )
    return render_template("meetings.html", meetings=rows)


@bp.get("/activities")
def activities():
    """活动报名列表。"""
    return render_template("activities.html")


@bp.get("/activity/<int:activity_id>")
def activity_detail(activity_id: int):
    """活动详情：显示真实报名人数、当前用户报名状态。"""
    activity = db.session.get(Activity, activity_id)
    if activity is None:
        abort(404)
    user = current_user()
    my_enrolled = False
    if user:
        e = Enrollment.query.filter_by(activity_id=activity.id, user_id=user.id).first()
        my_enrolled = bool(e and e.status == "confirmed")
    enrolled_count = activity.enrolled_count
    full = bool(activity.capacity) and enrolled_count >= activity.capacity
    return render_template(
        "activity_detail.html",
        activity=activity,
        enrolled_count=enrolled_count,
        my_enrolled=my_enrolled,
        full=full,
    )


@bp.get("/ledger")
def ledger():
    """电子台账：分类、搜索、上传、下载。"""
    return render_template(
        "ledger.html",
        categories=[{"name": n} for n in LEDGER_CATEGORIES],
        ledger_total=0,
    )


@bp.get("/gallery")
def gallery():
    """党建风采图片墙。"""
    photos = GalleryPhoto.query.order_by(GalleryPhoto.id.desc()).all()
    return render_template("gallery.html", photos=photos)


@bp.get("/dashboard")
def dashboard():
    """数据看板：所有数字由 /api/stats/* 实时聚合，模板里不写死。"""
    return render_template("dashboard.html")


@bp.get("/login")
def login():
    """登录页。

    页面上显示哪种登录方式，由后台「微信设置」页的 login_mode 决定：
    测试账号登录（个人号现状）还是微信授权登录（小程序 / 学校认证号）。
    """
    return render_template("login.html", wx=settings_store.public_config())


@bp.get("/logout")
def logout():
    """退出登录：清 session 后回到首页。

    为什么不用接口 /api/auth/logout：后台是服务端渲染页面，
    退出应该走普通跳转，而不是让浏览器停在 JSON 上。
    """
    from .auth import logout_user

    logout_user()
    return redirect(url_for("pages.index"))


@bp.get("/me")
def me():
    """个人中心：我的学习时长、我的报名、我的党费、我的组织关系转接。"""
    user = current_user()
    if user is None:
        return render_template(
            "me.html", enrollments=[], total_minutes=0,
            dues=[], dues_summary=None, transfers=[],
        )
    enrollments = (
        Enrollment.query.filter_by(user_id=user.id)
        .order_by(Enrollment.created_at.desc())
        .all()
    )
    total = (
        db.session.query(func.coalesce(func.sum(StudyRecord.minutes), 0))
        .filter(StudyRecord.user_id == user.id)
        .scalar()
    ) or 0
    due_rows = (
        PartyDue.query.filter_by(user_id=user.id)
        .order_by(PartyDue.period.desc())
        .all()
    )
    transfers = (
        OrgTransfer.query.filter_by(user_id=user.id)
        .order_by(OrgTransfer.created_at.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "me.html",
        enrollments=enrollments,
        total_minutes=int(total),
        dues=due_rows[:6],
        dues_summary=summarize_dues(due_rows),
        transfers=transfers,
    )


@bp.get("/healthz")
def healthz():
    """健康检查：给运维/学校信息中心看服务是否活着，并回显当前数据库类型。"""
    from flask import current_app

    uri = str(db.engine.url)
    engine = "mysql" if uri.startswith("mysql") else "sqlite"
    return {
        "ok": True,
        "app": "hxai-dangjian",
        "env": current_app.config.get("APP_ENV", "local"),
        "site": current_app.config.get("SITE_NAME", ""),
        "db_engine": engine,
        "login_mode": current_app.config.get("LOGIN_MODE", "test"),
        # 对外地址：每次请求重新解析，隧道换域名后这里立刻跟上（见 config.resolve_public_base_url）
        "public_base_url": resolve_public_base_url(),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
