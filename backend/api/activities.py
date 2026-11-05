"""三会一课 / 活动报名接口。

报名真正写库，刷新后状态还在；人数一律实时 count，不缓存。
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from ..auth import api_login_required, current_user
from ..extensions import db
from ..models import Activity, Enrollment

bp = Blueprint("api_activities", __name__, url_prefix="/api")

KIND_LABELS = {
    "meeting": "三会一课",
    "party_day": "主题党日",
    "volunteer": "志愿服务",
    "study": "集中学习",
}


@bp.get("/activities")
def list_activities():
    """活动列表：可按类型、状态、关键词筛选。"""
    kind = request.args.get("kind", "").strip()
    status = request.args.get("status", "").strip()
    keyword = request.args.get("q", "").strip()

    query = Activity.query
    if kind and kind != "all":
        query = query.filter(Activity.kind == kind)
    if status and status != "all":
        query = query.filter(Activity.status == status)
    if keyword:
        query = query.filter(Activity.title.like(f"%{keyword}%"))

    rows = query.order_by(Activity.start_at.desc().nullslast(), Activity.id.desc()).all()
    user = current_user()
    enrolled_ids = set()
    if user:
        enrolled_ids = {
            e.activity_id
            for e in Enrollment.query.filter_by(user_id=user.id, status="confirmed").all()
        }
    data = []
    for a in rows:
        item = a.to_dict()
        item["kind_label"] = KIND_LABELS.get(a.kind, a.kind)
        item["enrolled"] = a.id in enrolled_ids
        item["full"] = bool(a.capacity) and a.enrolled_count >= a.capacity
        data.append(item)
    return jsonify({"ok": True, "data": data})


@bp.get("/activities/<int:activity_id>")
def activity_detail(activity_id: int):
    """活动详情，附带当前用户报名状态。"""
    activity = Activity.query.get_or_404(activity_id)
    user = current_user()
    item = activity.to_dict()
    item["kind_label"] = KIND_LABELS.get(activity.kind, activity.kind)
    item["content"] = activity.content
    item["signup_deadline"] = (
        activity.signup_deadline.strftime("%Y-%m-%d %H:%M") if activity.signup_deadline else ""
    )
    item["enrolled"] = False
    item["my_enrollment"] = None
    if user:
        e = Enrollment.query.filter_by(activity_id=activity.id, user_id=user.id).first()
        if e:
            item["enrolled"] = e.status == "confirmed"
            item["my_enrollment"] = e.to_dict()
    item["full"] = bool(activity.capacity) and activity.enrolled_count >= activity.capacity
    return jsonify({"ok": True, "data": item})


@bp.post("/activities/<int:activity_id>/enroll")
@api_login_required
def enroll(activity_id: int):
    """报名：写数据库；重复报名、超员、已截止都会真实报错。"""
    activity = Activity.query.get_or_404(activity_id)
    user = current_user()
    payload = request.get_json(silent=True) or {}

    if activity.status != "open":
        return jsonify({"ok": False, "msg": "活动当前不接受报名"}), 400
    if activity.signup_deadline and datetime.now() > activity.signup_deadline:
        return jsonify({"ok": False, "msg": "报名已截止"}), 400
    if activity.capacity and activity.enrolled_count >= activity.capacity:
        return jsonify({"ok": False, "msg": "名额已满"}), 400

    existing = Enrollment.query.filter_by(activity_id=activity.id, user_id=user.id).first()
    if existing:
        if existing.status == "confirmed":
            return jsonify({"ok": False, "msg": "你已经报名过了", "data": existing.to_dict()}), 409
        # 取消过的人可以重新报名
        existing.status = "confirmed"
        existing.remark = (payload.get("remark") or "")[:300]
        db.session.commit()
        return jsonify({"ok": True, "data": existing.to_dict(), "msg": "已重新报名"})

    enrollment = Enrollment(
        activity_id=activity.id,
        user_id=user.id,
        remark=(payload.get("remark") or "")[:300],
        status="confirmed",
    )
    db.session.add(enrollment)
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "data": {**enrollment.to_dict(), "enrolled_count": activity.enrolled_count},
            "msg": "报名成功，已写入数据库",
        }
    )


@bp.post("/activities/<int:activity_id>/cancel")
@api_login_required
def cancel(activity_id: int):
    """取消报名：状态改为 cancelled，人数实时减少。"""
    user = current_user()
    enrollment = Enrollment.query.filter_by(
        activity_id=activity_id, user_id=user.id, status="confirmed"
    ).first()
    if not enrollment:
        return jsonify({"ok": False, "msg": "没有找到你的报名记录"}), 404

    enrollment.status = "cancelled"
    db.session.commit()
    activity = Activity.query.get(activity_id)
    return jsonify(
        {
            "ok": True,
            "data": {"enrolled_count": activity.enrolled_count},
            "msg": "已取消报名",
        }
    )


@bp.get("/activities/<int:activity_id>/enrollments")
@api_login_required
def list_enrollments(activity_id: int):
    """报名名单（管理员）。"""
    user = current_user()
    if not user.is_admin:
        return jsonify({"ok": False, "msg": "需要管理员权限"}), 403
    rows = (
        Enrollment.query.filter_by(activity_id=activity_id)
        .order_by(Enrollment.created_at.asc())
        .all()
    )
    return jsonify({"ok": True, "data": [e.to_dict() for e in rows]})
