"""党务接口：党费、组织关系转接。

数据全部来自数据库，不写死数字。
- 党费：按"人 + 期间（YYYY-MM）"一条记录；后台可批量生成应缴、标记已缴。
- 组织关系转接：党员自己提交申请，支部管理员审核。
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from ..auth import api_login_required, current_user
from ..extensions import db
from ..models import DUE_METHODS, OrgTransfer, PartyDue

bp = Blueprint("api_party", __name__, url_prefix="/api")

MAX_AMOUNT = 100000.0
DIRECTIONS = ("in", "out")


def current_period() -> str:
    return datetime.now().strftime("%Y-%m")


def summarize_dues(rows: list[PartyDue]) -> dict:
    """按记录列表算党费汇总（全部实时计算，不存冗余字段）。"""
    total = len(rows)
    paid = [r for r in rows if r.status == "paid"]
    late = [r for r in rows if r.status == "late"]
    unpaid = [r for r in rows if r.status == "unpaid"]
    amount_total = round(sum(r.amount_float for r in rows), 2)
    amount_paid = round(sum(r.amount_float for r in paid + late), 2)
    return {
        "total": total,
        "paid": len(paid),
        "late": len(late),
        "unpaid": len(unpaid),
        "amount_total": amount_total,
        "amount_paid": amount_paid,
        "amount_unpaid": round(amount_total - amount_paid, 2),
        "pay_rate": round((len(paid) + len(late)) / total * 100, 1) if total else 0.0,
        "period": current_period(),
        "formula": "缴费率 = （已缴 + 补缴）记录数 ÷ 应缴记录总数",
    }


@bp.get("/dues/my")
@api_login_required
def my_dues():
    """我的党费：明细 + 汇总。"""
    user = current_user()
    rows = (
        PartyDue.query.filter_by(user_id=user.id)
        .order_by(PartyDue.period.desc())
        .limit(36)
        .all()
    )
    return jsonify({
        "ok": True,
        "data": {
            "list": [r.to_dict() for r in rows],
            "summary": summarize_dues(rows),
            "user": user.real_name or user.username,
        },
    })


@bp.get("/dues/summary")
@api_login_required
def dues_summary():
    """支部党费汇总 + 最近 6 个期间的走势（不含个人明细）。"""
    rows = PartyDue.query.all()
    periods: dict[str, list[PartyDue]] = {}
    for r in rows:
        periods.setdefault(r.period, []).append(r)
    trend = []
    for period in sorted(periods.keys(), reverse=True)[:6]:
        item = summarize_dues(periods[period])
        item["period"] = period
        trend.append(item)
    trend.reverse()
    return jsonify({"ok": True, "data": {"summary": summarize_dues(rows), "trend": trend}})


@bp.get("/transfers/my")
@api_login_required
def my_transfers():
    user = current_user()
    rows = (
        OrgTransfer.query.filter_by(user_id=user.id)
        .order_by(OrgTransfer.created_at.desc())
        .limit(20)
        .all()
    )
    return jsonify({"ok": True, "data": [r.to_dict() for r in rows]})


@bp.post("/transfers")
@api_login_required
def create_transfer():
    """党员自己提交组织关系转接申请。"""
    user = current_user()
    payload = request.get_json(silent=True) or request.form
    direction = (payload.get("direction") or "in").strip()
    from_org = (payload.get("from_org") or "").strip()
    to_org = (payload.get("to_org") or "").strip()
    reason = (payload.get("reason") or "").strip()

    if direction not in DIRECTIONS:
        return jsonify({"ok": False, "msg": "转接方向不正确"}), 400
    if not from_org or not to_org:
        return jsonify({"ok": False, "msg": "请填写转出单位和接收单位"}), 400
    if len(from_org) > 120 or len(to_org) > 120:
        return jsonify({"ok": False, "msg": "单位名称过长"}), 400

    pending = OrgTransfer.query.filter_by(user_id=user.id, status="pending").first()
    if pending is not None:
        return jsonify({"ok": False, "code": 409, "msg": "你已有一条待审核的申请，请等待支部处理"}), 409

    row = OrgTransfer(
        user_id=user.id, direction=direction, from_org=from_org, to_org=to_org,
        reason=reason[:300], status="pending", is_demo=False,
    )
    db.session.add(row)
    db.session.commit()
    return jsonify({"ok": True, "data": row.to_dict(), "msg": "申请已提交，等待支部审核"}), 201
