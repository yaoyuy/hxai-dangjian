"""后台管理（管理员专用）。

为什么需要它：第一阶段虽然用个人订阅号测试，但"文章状态分草稿/已发布""台账上传"
这些要求意味着必须有人能录数据。没有后台，系统就还是演示页。

设计：
1. 全部是服务端渲染的表单（<form method="post">），不依赖前端 JS，学校环境更稳。
2. 权限统一走 admin_required（super_admin / branch_admin），普通党员访问被拒。
3. 只做第一阶段够用的 CRUD：文章、活动、党员账号。文件上传复用 /api/ledger。
"""
from __future__ import annotations

from datetime import datetime

from flask import (
    Blueprint, abort, flash, redirect, render_template, request, url_for,
)

from . import settings_store
from .api.party import summarize_dues
from .auth import admin_required, current_user
from .extensions import db
from .models import (
    DUE_METHODS, DUE_STATUS_LABELS, TRANSFER_STATUS_LABELS,
    Activity, Article, Branch, Category, Enrollment, GalleryPhoto, LedgerFile,
    OrgTransfer, PartyDue, StudyRecord, SysSetting, User, Whitelist,
)
from .wechat import build_menu, create_menu, get_access_token

bp = Blueprint("admin", __name__, url_prefix="/admin")

ACTIVITY_KINDS = [
    ("meeting", "三会一课/会议"),
    ("party_day", "主题党日"),
    ("volunteer", "志愿服务"),
    ("study", "集中学习"),
]
ACTIVITY_STATUS = [("open", "进行中"), ("closed", "已截止"), ("finished", "已完成")]
ROLES = [("super_admin", "超级管理员"), ("branch_admin", "支部管理员"), ("member", "普通党员")]
AGE_GROUPS = ["35岁以下", "36-50岁", "51岁以上"]


def _parse_dt(raw: str):
    """解析 <input type="datetime-local"> 的值；空值返回 None。"""
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


@bp.get("/")
@admin_required
def index():
    """后台首页：真实数据概览 + 待办提醒。"""
    return render_template(
        "admin/index.html",
        counts={
            "published": Article.query.filter_by(status="published").count(),
            "draft": Article.query.filter_by(status="draft").count(),
            "activities": Activity.query.filter_by(status="open").count(),
            "members": User.query.count(),
            "enrollments": Enrollment.query.filter_by(status="confirmed").count(),
            "files": LedgerFile.query.count(),
            "photos": GalleryPhoto.query.count(),
            "dues": PartyDue.query.count(),
            "dues_unpaid": PartyDue.query.filter_by(status="unpaid").count(),
            "transfers_pending": OrgTransfer.query.filter_by(status="pending").count(),
            "whitelist": Whitelist.query.count(),
            "demo": Article.query.filter_by(is_demo=True).count(),
        },
        recent_articles=Article.query.order_by(Article.id.desc()).limit(5).all(),
        recent_enrollments=(
            Enrollment.query.filter_by(status="confirmed")
            .order_by(Enrollment.id.desc()).limit(6).all()
        ),
    )


# ---------------------------------------------------------------- 文章
@bp.get("/articles")
@admin_required
def articles():
    status = request.args.get("status", "all")
    query = Article.query
    if status in ("draft", "published"):
        query = query.filter_by(status=status)
    rows = query.order_by(Article.id.desc()).all()
    return render_template(
        "admin/articles.html",
        articles=rows,
        status=status,
        categories=Category.query.order_by(Category.sort_order).all(),
        draft_count=Article.query.filter_by(status="draft").count(),
    )


@bp.post("/articles")
@admin_required
def article_create():
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("标题不能为空", "error")
        return redirect(url_for("admin.articles"))

    status = request.form.get("status") or "draft"
    article = Article(
        title=title,
        summary=(request.form.get("summary") or "").strip(),
        content=request.form.get("content") or "",
        category_id=int(request.form["category_id"]) if request.form.get("category_id") else None,
        cover_url=(request.form.get("cover_url") or "").strip(),
        study_minutes=max(1, int(request.form.get("study_minutes") or 5)),
        status=status,
        is_demo=False,  # 管理员录入的是真实资料，不再打「测试数据」标签
        published_at=datetime.now() if status == "published" else None,
    )
    db.session.add(article)
    db.session.commit()
    flash(f"已保存文章《{article.title}》（{'已发布' if status == 'published' else '草稿'}）", "ok")
    return redirect(url_for("admin.articles"))


@bp.get("/articles/<int:article_id>")
@admin_required
def article_edit(article_id: int):
    article = db.session.get(Article, article_id)
    if article is None:
        abort(404)
    return render_template(
        "admin/article_edit.html",
        article=article,
        categories=Category.query.order_by(Category.sort_order).all(),
    )


@bp.post("/articles/<int:article_id>")
@admin_required
def article_update(article_id: int):
    article = db.session.get(Article, article_id)
    if article is None:
        abort(404)

    was_published = article.status == "published"
    article.title = (request.form.get("title") or article.title).strip()
    article.summary = (request.form.get("summary") or "").strip()
    article.content = request.form.get("content") or ""
    article.cover_url = (request.form.get("cover_url") or "").strip()
    article.study_minutes = max(1, int(request.form.get("study_minutes") or 5))
    if request.form.get("category_id"):
        article.category_id = int(request.form["category_id"])

    new_status = request.form.get("status") or article.status
    article.status = new_status
    # 首次发布时记录发布时间，取消发布则清空
    if new_status == "published" and not was_published:
        article.published_at = datetime.now()
    elif new_status == "draft":
        article.published_at = None

    db.session.commit()
    flash("已保存修改", "ok")
    return redirect(url_for("admin.articles"))


@bp.post("/articles/<int:article_id>/status")
@admin_required
def article_toggle_status(article_id: int):
    """一键发布 / 转回草稿。"""
    article = db.session.get(Article, article_id)
    if article is None:
        abort(404)
    if article.status == "published":
        article.status = "draft"
        article.published_at = None
        flash(f"《{article.title}》已转为草稿，前台不可见", "ok")
    else:
        article.status = "published"
        article.published_at = datetime.now()
        flash(f"《{article.title}》已发布", "ok")
    db.session.commit()
    return redirect(request.referrer or url_for("admin.articles"))


@bp.post("/articles/<int:article_id>/delete")
@admin_required
def article_delete(article_id: int):
    article = db.session.get(Article, article_id)
    if article is None:
        abort(404)
    # 先删学习记录，避免外键悬空
    StudyRecord.query.filter_by(article_id=article.id).delete()
    title = article.title
    db.session.delete(article)
    db.session.commit()
    flash(f"已删除《{title}》", "ok")
    return redirect(url_for("admin.articles"))


# ---------------------------------------------------------------- 活动
@bp.get("/activities")
@admin_required
def activities():
    rows = Activity.query.order_by(Activity.start_at.desc().nullslast()).all()
    return render_template(
        "admin/activities.html",
        activities=rows,
        kinds=ACTIVITY_KINDS,
        statuses=ACTIVITY_STATUS,
    )


@bp.post("/activities")
@admin_required
def activity_create():
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("活动标题不能为空", "error")
        return redirect(url_for("admin.activities"))

    activity = Activity(
        title=title,
        kind=request.form.get("kind") or "meeting",
        summary=(request.form.get("summary") or "").strip(),
        content=request.form.get("content") or "",
        location=(request.form.get("location") or "").strip(),
        start_at=_parse_dt(request.form.get("start_at")),
        signup_deadline=_parse_dt(request.form.get("signup_deadline")),
        capacity=int(request.form.get("capacity") or 0),
        target=(request.form.get("target") or "全体党员、入党积极分子").strip(),
        status=request.form.get("status") or "open",
        is_demo=False,
    )
    db.session.add(activity)
    db.session.commit()
    flash(f"已创建活动《{activity.title}》", "ok")
    return redirect(url_for("admin.activities"))


@bp.get("/activities/<int:activity_id>")
@admin_required
def activity_edit(activity_id: int):
    activity = db.session.get(Activity, activity_id)
    if activity is None:
        abort(404)
    return render_template(
        "admin/activity_edit.html",
        activity=activity,
        kinds=ACTIVITY_KINDS,
        statuses=ACTIVITY_STATUS,
        enrollments=(
            Enrollment.query.filter_by(activity_id=activity.id)
            .order_by(Enrollment.created_at.asc()).all()
        ),
    )


@bp.post("/activities/<int:activity_id>")
@admin_required
def activity_update(activity_id: int):
    activity = db.session.get(Activity, activity_id)
    if activity is None:
        abort(404)
    activity.title = (request.form.get("title") or activity.title).strip()
    activity.kind = request.form.get("kind") or activity.kind
    activity.summary = (request.form.get("summary") or "").strip()
    activity.content = request.form.get("content") or ""
    activity.location = (request.form.get("location") or "").strip()
    activity.start_at = _parse_dt(request.form.get("start_at"))
    activity.signup_deadline = _parse_dt(request.form.get("signup_deadline"))
    activity.capacity = int(request.form.get("capacity") or 0)
    activity.target = (request.form.get("target") or "").strip()
    activity.status = request.form.get("status") or activity.status
    db.session.commit()
    flash("已保存活动", "ok")
    return redirect(url_for("admin.activities"))


@bp.post("/activities/<int:activity_id>/delete")
@admin_required
def activity_delete(activity_id: int):
    activity = db.session.get(Activity, activity_id)
    if activity is None:
        abort(404)
    Enrollment.query.filter_by(activity_id=activity.id).delete()
    title = activity.title
    db.session.delete(activity)
    db.session.commit()
    flash(f"已删除活动《{title}》", "ok")
    return redirect(url_for("admin.activities"))


# ---------------------------------------------------------------- 党员
@bp.get("/users")
@admin_required
def users():
    rows = User.query.order_by(User.id.asc()).all()
    return render_template(
        "admin/users.html",
        users=rows,
        roles=ROLES,
        age_groups=AGE_GROUPS,
        branches=Branch.query.all(),
    )


@bp.post("/users")
@admin_required
def user_create():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    if not username or not password:
        flash("账号和密码都必须填写", "error")
        return redirect(url_for("admin.users"))
    if User.query.filter_by(username=username).first():
        flash(f"账号 {username} 已存在", "error")
        return redirect(url_for("admin.users"))

    branch = Branch.query.first()
    user = User(
        username=username,
        real_name=(request.form.get("real_name") or username).strip(),
        role=request.form.get("role") or "member",
        branch_id=branch.id if branch else None,
        age_group=request.form.get("age_group") or AGE_GROUPS[0],
        phone=(request.form.get("phone") or "").strip(),
        is_test_account=True,  # 第一阶段都是本地测试账号
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f"已创建账号 {username}（测试账号，非微信身份）", "ok")
    return redirect(url_for("admin.users"))


@bp.post("/users/<int:user_id>/reset")
@admin_required
def user_reset_password(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    new_password = (request.form.get("password") or "").strip()
    if len(new_password) < 6:
        flash("密码至少 6 位", "error")
        return redirect(url_for("admin.users"))
    user.set_password(new_password)
    db.session.commit()
    flash(f"已重置 {user.username} 的密码", "ok")
    return redirect(url_for("admin.users"))


# ---------------------------------------------------------------- 风采
@bp.get("/gallery")
@admin_required
def gallery():
    return render_template("admin/gallery.html", photos=GalleryPhoto.query.order_by(GalleryPhoto.id.desc()).all())


@bp.post("/gallery")
@admin_required
def gallery_create():
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("图片标题不能为空", "error")
        return redirect(url_for("admin.gallery"))
    db.session.add(GalleryPhoto(
        title=title,
        image_url=(request.form.get("image_url") or "").strip(),
        description=(request.form.get("description") or "").strip(),
        is_demo=False,
    ))
    db.session.commit()
    flash("已添加风采图片", "ok")
    return redirect(url_for("admin.gallery"))


@bp.post("/gallery/<int:photo_id>/delete")
@admin_required
def gallery_delete(photo_id: int):
    photo = db.session.get(GalleryPhoto, photo_id)
    if photo is None:
        abort(404)
    db.session.delete(photo)
    db.session.commit()
    flash("已删除", "ok")
    return redirect(url_for("admin.gallery"))


# ---------------------------------------------------------------- 演示数据清理
@bp.post("/demo/clear")
@admin_required
def demo_clear():
    """一键删除所有 is_demo=True 的演示数据（录入真实资料前用）。"""
    if (request.form.get("confirm") or "") != "yes":
        flash("请输入 yes 确认清理", "error")
        return redirect(url_for("admin.index"))

    articles = Article.query.filter_by(is_demo=True).all()
    for a in articles:
        StudyRecord.query.filter_by(article_id=a.id).delete()
        db.session.delete(a)
    acts = Activity.query.filter_by(is_demo=True).all()
    for a in acts:
        Enrollment.query.filter_by(activity_id=a.id).delete()
        db.session.delete(a)
    files = LedgerFile.query.filter_by(is_demo=True).count()
    for f in LedgerFile.query.filter_by(is_demo=True).all():
        db.session.delete(f)
    photos = GalleryPhoto.query.filter_by(is_demo=True).count()
    for p in GalleryPhoto.query.filter_by(is_demo=True).all():
        db.session.delete(p)
    dues = PartyDue.query.filter_by(is_demo=True).count()
    for d in PartyDue.query.filter_by(is_demo=True).all():
        db.session.delete(d)
    transfers = OrgTransfer.query.filter_by(is_demo=True).count()
    for t in OrgTransfer.query.filter_by(is_demo=True).all():
        db.session.delete(t)
    wls = Whitelist.query.filter_by(is_demo=True).count()
    for w in Whitelist.query.filter_by(is_demo=True).all():
        db.session.delete(w)
    db.session.commit()
    flash(
        f"已清理演示数据：文章 {len(articles)} 篇、活动 {len(acts)} 场、台账 {files} 份、"
        f"风采 {photos} 张、党费 {dues} 条、转接 {transfers} 条、白名单 {wls} 条",
        "ok",
    )
    return redirect(url_for("admin.index"))

# =====================================================================
# 微信设置（参数存数据库 sys_setting，后台页面可改）
# 这样换公众号 / 换服务器只改数据不改代码，也不再依赖受保护的 .env。
# =====================================================================

@bp.get("/wechat")
@admin_required
def wechat_settings():
    """微信设置页：公众号参数、小程序参数、登录方式、白名单开关。"""
    items = settings_store.all_items()
    groups: dict[str, list[dict]] = {}
    for item in items:
        groups.setdefault(item["group"], []).append(item)
    public = settings_store.public_config()
    base = public.get("public_base_url") or ""
    return render_template(
        "admin/wechat.html",
        groups=groups,
        public=public,
        login_modes=settings_store.LOGIN_MODES,
        server_url=(base + "/wechat") if base else "（未配置 PUBLIC_BASE_URL，暂时无法给出服务器地址）",
        whitelist_total=Whitelist.query.count(),
        whitelist_active=Whitelist.query.filter_by(is_active=True).count(),
        oauth_redirect=(base + "/login?mode=wechat") if base else "",
        secret_keys=settings_store.SECRET_KEYS,
    )


@bp.post("/wechat")
@admin_required
def wechat_save():
    """保存微信设置。密文字段留空 = 不修改（避免误清空已保存的密钥）。"""
    pairs = {key: (request.form.get(key) or "") for key in settings_store.DEFAULTS}
    saved = settings_store.set_many(pairs)
    flash(f"已保存 {saved} 项设置。修改登录方式会立即生效；密文字段留空表示保持原值。", "ok")
    return redirect(url_for("admin.wechat_settings"))


@bp.post("/wechat/test")
@admin_required
def wechat_test():
    """测试微信参数。调用真实微信接口，把错误原样显示出来，不伪装成功。"""
    token, err = get_access_token(force=True)
    if token:
        flash(f"公众号 access_token 获取成功（{token[:10]}…，有效期约 7200 秒）", "ok")
    else:
        flash(f"公众号 access_token 获取失败：{err}", "error")

    wxapp = settings_store.get_wxapp_config()
    if wxapp.get("appid") and wxapp.get("secret"):
        flash("小程序 AppID / AppSecret 已填写。真实换 openid 需要小程序端 wx.login 的 code，这里不做假校验。", "ok")
    else:
        flash("小程序 AppID / AppSecret 未填写，小程序登录不可用。", "error")
    return redirect(url_for("admin.wechat_settings"))


@bp.post("/wechat/menu")
@admin_required
def wechat_menu_push():
    """用接口推送自定义菜单。个人未认证订阅号固定返回 48001，这里如实显示。"""
    base = settings_store.public_config().get("public_base_url") or ""
    if not base:
        flash("没有可用的公网地址：菜单里的链接需要能公网访问，请先配置 PUBLIC_BASE_URL。", "error")
        return redirect(url_for("admin.wechat_settings"))
    ok, msg = create_menu(build_menu(base))
    if ok:
        flash(f"菜单推送成功：{msg}", "ok")
    else:
        flash(f"菜单推送失败：{msg}（未认证个人订阅号属正常结果，请在公众号后台手工配置菜单）", "error")
    return redirect(url_for("admin.wechat_settings"))


# =====================================================================
# 微信登录白名单
# =====================================================================

@bp.get("/whitelist")
@admin_required
def whitelist():
    rows = Whitelist.query.order_by(Whitelist.is_active.desc(), Whitelist.id.desc()).all()
    return render_template(
        "admin/whitelist.html",
        rows=rows,
        roles=ROLES,
        users=User.query.order_by(User.id).all(),
        enabled=settings_store.whitelist_enabled(),
        login_mode=settings_store.LOGIN_MODES.get(settings_store.login_mode(), ""),
    )


@bp.post("/whitelist")
@admin_required
def whitelist_create():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("请填写姓名", "error")
        return redirect(url_for("admin.whitelist"))
    openid = (request.form.get("openid") or "").strip()
    if openid and Whitelist.query.filter_by(openid=openid).first() is not None:
        flash("该 openid 已在白名单里", "error")
        return redirect(url_for("admin.whitelist"))

    branch = Branch.query.filter_by(code="default").first()
    row = Whitelist(
        name=name,
        phone=(request.form.get("phone") or "").strip(),
        openid=openid or None,
        role=request.form.get("role") or "member",
        note=(request.form.get("note") or "").strip(),
        is_active=True,
        user_id=request.form.get("user_id", type=int),
        branch_id=branch.id if branch else None,
        is_demo=False,
    )
    db.session.add(row)
    db.session.commit()
    flash(f"已加入白名单：{name}（openid 可留空，等本人第一次微信登录时自动补上）", "ok")
    return redirect(url_for("admin.whitelist"))


@bp.post("/whitelist/<int:wl_id>/update")
@admin_required
def whitelist_update(wl_id: int):
    row = Whitelist.query.get_or_404(wl_id)
    openid = (request.form.get("openid") or "").strip()
    if openid:
        other = Whitelist.query.filter_by(openid=openid).first()
        if other is not None and other.id != row.id:
            flash("该 openid 已属于白名单里的其它人", "error")
            return redirect(url_for("admin.whitelist"))
    row.name = (request.form.get("name") or row.name).strip()
    row.phone = (request.form.get("phone") or "").strip()
    row.openid = openid or row.openid
    row.role = request.form.get("role") or row.role
    row.user_id = request.form.get("user_id", type=int)
    row.note = (request.form.get("note") or "").strip()
    db.session.commit()
    flash(f"已更新白名单：{row.name}", "ok")
    return redirect(url_for("admin.whitelist"))


@bp.post("/whitelist/<int:wl_id>/toggle")
@admin_required
def whitelist_toggle(wl_id: int):
    row = Whitelist.query.get_or_404(wl_id)
    row.is_active = not row.is_active
    db.session.commit()
    flash(f"白名单「{row.name}」已{'启用' if row.is_active else '停用'}", "ok")
    return redirect(url_for("admin.whitelist"))


@bp.post("/whitelist/<int:wl_id>/delete")
@admin_required
def whitelist_delete(wl_id: int):
    row = Whitelist.query.get_or_404(wl_id)
    name = row.name
    db.session.delete(row)
    db.session.commit()
    flash(f"已从白名单移除：{name}", "ok")
    return redirect(url_for("admin.whitelist"))


# =====================================================================
# 党费
# =====================================================================

@bp.get("/dues")
@admin_required
def dues():
    period = request.args.get("period") or datetime.now().strftime("%Y-%m")
    rows = (
        PartyDue.query.filter_by(period=period)
        .order_by(PartyDue.status, PartyDue.id)
        .all()
    )
    periods = [
        p[0] for p in
        db.session.query(PartyDue.period).distinct().order_by(PartyDue.period.desc()).all()
    ]
    return render_template(
        "admin/dues.html",
        rows=rows,
        period=period,
        periods=periods,
        summary=summarize_dues(PartyDue.query.all()),
        period_summary=summarize_dues(rows),
        members=User.query.order_by(User.id).all(),
        methods=DUE_METHODS,
        status_labels=DUE_STATUS_LABELS,
        current_period=datetime.now().strftime("%Y-%m"),
    )


@bp.post("/dues/generate")
@admin_required
def dues_generate():
    """按期间为全体账号生成应缴记录；已存在的（同一人同一期间）自动跳过。"""
    period = (request.form.get("period") or "").strip()
    try:
        amount = float(request.form.get("amount") or 0)
    except ValueError:
        flash("金额格式不正确", "error")
        return redirect(url_for("admin.dues"))
    if len(period) != 7 or period[4] != "-":
        flash("期间格式应为 YYYY-MM，例如 2026-10", "error")
        return redirect(url_for("admin.dues"))

    created = 0
    for user in User.query.all():
        exists = PartyDue.query.filter_by(user_id=user.id, period=period).first()
        if exists is not None:
            continue
        db.session.add(PartyDue(
            user_id=user.id, period=period, amount=amount, method="现金",
            status="unpaid", operator_id=current_user().id,
        ))
        created += 1
    db.session.commit()
    flash(f"{period} 应缴记录已生成 {created} 条（已存在的跳过）", "ok")
    return redirect(url_for("admin.dues", period=period))


@bp.post("/dues")
@admin_required
def dues_create():
    """手工登记一条党费（例如新入党 / 补缴）。"""
    user_id = request.form.get("user_id", type=int)
    period = (request.form.get("period") or "").strip()
    if not user_id or len(period) != 7:
        flash("请选择党员并填写 YYYY-MM 期间", "error")
        return redirect(url_for("admin.dues"))
    if PartyDue.query.filter_by(user_id=user_id, period=period).first() is not None:
        flash("该党员这个期间的党费已存在", "error")
        return redirect(url_for("admin.dues", period=period))
    try:
        amount = float(request.form.get("amount") or 0)
    except ValueError:
        flash("金额格式不正确", "error")
        return redirect(url_for("admin.dues", period=period))

    status = request.form.get("status") or "unpaid"
    if status not in DUE_STATUS_LABELS:
        status = "unpaid"
    row = PartyDue(
        user_id=user_id, period=period, amount=amount,
        method=request.form.get("method") or "现金", status=status,
        paid_at=datetime.now() if status in ("paid", "late") else None,
        note=(request.form.get("note") or "").strip()[:200],
        operator_id=current_user().id,
    )
    db.session.add(row)
    db.session.commit()
    flash("党费记录已添加", "ok")
    return redirect(url_for("admin.dues", period=period))


@bp.post("/dues/<int:due_id>/status")
@admin_required
def dues_status(due_id: int):
    """切换党费状态：未缴 ↔ 已缴（补缴）。"""
    row = PartyDue.query.get_or_404(due_id)
    new_status = request.form.get("status") or ("unpaid" if row.status != "unpaid" else "paid")
    if new_status not in DUE_STATUS_LABELS:
        flash("状态不正确", "error")
        return redirect(url_for("admin.dues", period=row.period))
    row.status = new_status
    row.paid_at = datetime.now() if new_status in ("paid", "late") else None
    row.operator_id = current_user().id
    db.session.commit()
    flash(f"已把 {row.user.real_name if row.user else ''} {row.period} 的党费标记为「{DUE_STATUS_LABELS[new_status]}」", "ok")
    return redirect(url_for("admin.dues", period=row.period))


@bp.post("/dues/<int:due_id>/delete")
@admin_required
def dues_delete(due_id: int):
    row = PartyDue.query.get_or_404(due_id)
    period = row.period
    db.session.delete(row)
    db.session.commit()
    flash("党费记录已删除", "ok")
    return redirect(url_for("admin.dues", period=period))


# =====================================================================
# 组织关系转接
# =====================================================================

@bp.get("/transfers")
@admin_required
def transfers():
    rows = (
        OrgTransfer.query
        .order_by(OrgTransfer.status, OrgTransfer.created_at.desc())
        .all()
    )
    return render_template(
        "admin/transfers.html",
        rows=rows,
        status_labels=TRANSFER_STATUS_LABELS,
        pending=OrgTransfer.query.filter_by(status="pending").count(),
    )


@bp.post("/transfers/<int:transfer_id>/review")
@admin_required
def transfer_review(transfer_id: int):
    row = OrgTransfer.query.get_or_404(transfer_id)
    action = request.form.get("action")
    if action not in ("approve", "reject"):
        flash("审核动作不正确", "error")
        return redirect(url_for("admin.transfers"))
    if row.status != "pending":
        flash("该申请已经处理过了", "error")
        return redirect(url_for("admin.transfers"))
    row.status = "approved" if action == "approve" else "rejected"
    row.review_at = datetime.now()
    row.reviewer_id = current_user().id
    row.review_note = (request.form.get("review_note") or "").strip()[:200]
    db.session.commit()
    flash(f"已{'通过' if action == 'approve' else '驳回'} {row.user.real_name if row.user else ''} 的{row.direction_label}申请", "ok")
    return redirect(url_for("admin.transfers"))


@bp.post("/transfers/<int:transfer_id>/delete")
@admin_required
def transfer_delete(transfer_id: int):
    row = OrgTransfer.query.get_or_404(transfer_id)
    db.session.delete(row)
    db.session.commit()
    flash("转接记录已删除", "ok")
    return redirect(url_for("admin.transfers"))

