"""学习专栏接口：分类、列表、详情、学习打卡。"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from ..auth import api_login_required, current_user
from ..extensions import db
from ..models import Article, Category, StudyRecord

bp = Blueprint("api_articles", __name__, url_prefix="/api")


@bp.get("/categories")
def list_categories():
    """学习专栏分类（带已发布文章数）。"""
    rows = Category.query.order_by(Category.sort_order).all()
    data = []
    for c in rows:
        published = Article.query.filter_by(category_id=c.id, status="published").count()
        data.append({**c.to_dict(), "count": published})
    return jsonify({"ok": True, "data": data})


@bp.get("/articles")
def list_articles():
    """文章列表：支持分类筛选、关键词搜索、分页。只返回已发布文章。"""
    category = request.args.get("category", "").strip()
    keyword = request.args.get("q", "").strip()
    page = max(int(request.args.get("page", 1) or 1), 1)
    size = min(max(int(request.args.get("size", 20) or 20), 1), 100)

    query = Article.query.filter(Article.status == "published")
    if category and category != "all":
        query = query.join(Category).filter(Category.code == category)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(Article.title.like(like), Article.summary.like(like)))

    total = query.count()
    rows = (
        query.order_by(Article.published_at.desc().nullslast(), Article.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return jsonify(
        {
            "ok": True,
            "data": [a.to_dict() for a in rows],
            "pagination": {"page": page, "size": size, "total": total},
        }
    )


@bp.get("/articles/<int:article_id>")
def article_detail(article_id: int):
    """文章详情。草稿只有管理员能看。"""
    article = Article.query.get_or_404(article_id)
    user = current_user()
    if article.status != "published" and not (user and user.is_admin):
        return jsonify({"ok": False, "code": 404, "msg": "文章不存在或未发布"}), 404

    article.view_count = (article.view_count or 0) + 1
    db.session.commit()
    return jsonify({"ok": True, "data": article.to_dict(with_content=True)})


@bp.post("/articles/<int:article_id>/study")
@api_login_required
def record_study(article_id: int):
    """学习打卡：写入学习记录，看板据此统计学习时长与完成率。"""
    article = Article.query.get_or_404(article_id)
    if article.status != "published":
        return jsonify({"ok": False, "msg": "文章未发布"}), 400

    payload = request.get_json(silent=True) or {}
    minutes = payload.get("minutes") or article.study_minutes or 5
    try:
        minutes = max(1, min(int(minutes), 600))
    except (TypeError, ValueError):
        minutes = article.study_minutes or 5

    user = current_user()
    record = StudyRecord(user_id=user.id, article_id=article.id, minutes=minutes)
    db.session.add(record)
    db.session.commit()

    total = (
        db.session.query(db.func.coalesce(db.func.sum(StudyRecord.minutes), 0))
        .filter(StudyRecord.user_id == user.id)
        .scalar()
    )
    return jsonify(
        {
            "ok": True,
            "data": {
                "record_id": record.id,
                "minutes": minutes,
                "my_total_minutes": int(total),
                "recorded_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            },
            "msg": f"已记录本次学习 {minutes} 分钟",
        }
    )
