"""数据看板接口。

所有数字都是实时聚合 SQL，没有写死常量。
口径说明（页面上也标注）：
- 党员总数 = user 表记录数
- 年度活动数 = 本年度 activity 表记录数
- 学习完成率 = 本月有学习记录的党员数 / 党员总数
- 累计学习小时 = study_record.minutes 求和 / 60
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models import (
    Activity, Article, Enrollment, LedgerFile, OrgTransfer, PartyDue, StudyRecord, User,
)

bp = Blueprint("api_stats", __name__, url_prefix="/api/stats")

AGE_GROUPS = ["35岁以下", "36-50岁", "51岁以上"]


@bp.get("/overview")
def overview():
    year = int(request.args.get("year", datetime.now().year))
    month_start = datetime(datetime.now().year, datetime.now().month, 1)

    total_members = User.query.count()
    year_activities = Activity.query.filter(
        db.extract("year", Activity.start_at) == year
    ).count()
    active_learners = (
        db.session.query(func.count(func.distinct(StudyRecord.user_id)))
        .filter(StudyRecord.created_at >= month_start)
        .scalar()
        or 0
    )
    completion = round(active_learners / total_members * 100) if total_members else 0
    total_minutes = db.session.query(func.coalesce(func.sum(StudyRecord.minutes), 0)).scalar() or 0

    # 党费 / 组织关系（复用同一套实时聚合口径，不写死数字）
    due_rows = PartyDue.query.all()
    due_total = len(due_rows)
    due_paid = len([r for r in due_rows if r.status in ("paid", "late")])
    due_rate = round(due_paid / due_total * 100, 1) if due_total else 0.0
    transfers_pending = OrgTransfer.query.filter_by(status="pending").count()

    return jsonify(
        {
            "ok": True,
            "data": {
                "total_members": total_members,
                "year_activities": year_activities,
                "completion_rate": completion,
                "study_hours": round(int(total_minutes) / 60, 1),
                "total_study_minutes": int(total_minutes),
                "active_learners_this_month": active_learners,
                "total_enrollments": Enrollment.query.filter_by(status="confirmed").count(),
                "total_articles": Article.query.filter_by(status="published").count(),
                "total_files": LedgerFile.query.count(),
                "dues_total": due_total,
                "dues_paid": due_paid,
                "dues_unpaid": due_total - due_paid,
                "dues_paid_rate": due_rate,
                "transfers_pending": transfers_pending,
                "year": year,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "formula": {
                    "completion_rate": "本月有学习记录的党员数 ÷ 党员总数",
                    "study_hours": "学习记录分钟数合计 ÷ 60",
                    "dues_paid_rate": "（已缴 + 补缴）党费记录数 ÷ 应缴记录总数",
                    "transfers_pending": "组织关系转接表中状态为待审核的记录数",
                },
            },
        }
    )


@bp.get("/monthly")
def monthly():
    """每月组织生活开展次数（按 activity.start_at 的真实月份聚合）。"""
    year = int(request.args.get("year", datetime.now().year))
    rows = (
        db.session.query(
            db.extract("month", Activity.start_at).label("m"),
            func.count(Activity.id),
        )
        .filter(db.extract("year", Activity.start_at) == year)
        .group_by("m")
        .all()
    )
    counts = {int(m): int(c) for m, c in rows if m is not None}
    data = [{"month": i, "label": f"{i}月", "count": counts.get(i, 0)} for i in range(1, 13)]
    return jsonify({"ok": True, "data": data, "year": year, "total": sum(counts.values())})


@bp.get("/members")
def members():
    """党员构成：按年龄段统计（真实分组查询）。"""
    rows = (
        db.session.query(User.age_group, func.count(User.id))
        .group_by(User.age_group)
        .all()
    )
    counted = {g: int(c) for g, c in rows}
    data = [{"group": g, "count": counted.get(g, 0)} for g in AGE_GROUPS]
    other = sum(c for g, c in counted.items() if g not in AGE_GROUPS)
    if other:
        data.append({"group": "未填写", "count": other})
    return jsonify({"ok": True, "data": data, "total": sum(counted.values())})


@bp.get("/learning")
def learning():
    """学习情况：按分类统计阅读量、学习人次、时长。"""
    rows = (
        db.session.query(
            Article.category_id,
            func.count(func.distinct(StudyRecord.id)),
            func.coalesce(func.sum(StudyRecord.minutes), 0),
        )
        .outerjoin(StudyRecord, StudyRecord.article_id == Article.id)
        .filter(Article.status == "published")
        .group_by(Article.category_id)
        .all()
    )
    from ..models import Category

    cats = {c.id: c.name for c in Category.query.all()}
    data = [
        {
            "category": cats.get(cid, "未分类"),
            "study_times": int(times),
            "minutes": int(minutes),
            "hours": round(int(minutes) / 60, 1),
        }
        for cid, times, minutes in rows
    ]
    return jsonify({"ok": True, "data": data})


@bp.get("/dues")
def dues():
    """党费缴纳情况：总体 + 最近 6 个期间（数据来自 party_due 表，实时聚合）。"""
    rows = PartyDue.query.all()
    periods: dict[str, dict] = {}
    for r in rows:
        p = periods.setdefault(
            r.period,
            {"period": r.period, "total": 0, "paid": 0, "unpaid": 0, "amount_total": 0.0, "amount_paid": 0.0},
        )
        p["total"] += 1
        p["amount_total"] += r.amount_float
        if r.status in ("paid", "late"):
            p["paid"] += 1
            p["amount_paid"] += r.amount_float
        else:
            p["unpaid"] += 1
    trend = sorted(periods.values(), key=lambda x: x["period"])[-6:]
    for p in trend:
        p["amount_total"] = round(p["amount_total"], 2)
        p["amount_paid"] = round(p["amount_paid"], 2)
        p["pay_rate"] = round(p["paid"] / p["total"] * 100, 1) if p["total"] else 0.0
    paid = len([r for r in rows if r.status in ("paid", "late")])
    summary = {
        "total": len(rows),
        "paid": paid,
        "late": len([r for r in rows if r.status == "late"]),
        "unpaid": len([r for r in rows if r.status == "unpaid"]),
        "amount_total": round(sum(r.amount_float for r in rows), 2),
        "amount_paid": round(sum(r.amount_float for r in rows if r.status in ("paid", "late")), 2),
        "pay_rate": round(paid / len(rows) * 100, 1) if rows else 0.0,
        "formula": "缴费率 = （已缴 + 补缴）记录数 ÷ 应缴记录总数",
    }
    return jsonify({
        "ok": True,
        "data": {
            "summary": summary,
            "trend": trend,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    })


@bp.get("/activity-participation")
def activity_participation():
    """活动参与：每场活动的报名人数（实时 count）。"""
    rows = (
        db.session.query(Activity.id, Activity.title, Activity.capacity)
        .order_by(Activity.start_at.desc().nullslast())
        .limit(12)
        .all()
    )
    data = []
    for aid, title, capacity in rows:
        enrolled = Enrollment.query.filter_by(activity_id=aid, status="confirmed").count()
        data.append(
            {
                "activity_id": aid,
                "title": title,
                "enrolled": enrolled,
                "capacity": capacity,
                "rate": round(enrolled / capacity * 100) if capacity else None,
            }
        )
    return jsonify({"ok": True, "data": data})
