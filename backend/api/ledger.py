"""电子台账接口：分类、搜索、上传、下载。

文件元信息入库，文件本体存到 UPLOAD_DIR（可配置，学校服务器可换成挂载盘）。
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from ..auth import api_login_required, current_user
from ..extensions import db
from ..models import LedgerFile

bp = Blueprint("api_ledger", __name__, url_prefix="/api")

LEDGER_CATEGORIES = ["会议记录", "活动资料", "学习材料", "制度文件", "其他"]


@bp.get("/ledger/categories")
def ledger_categories():
    data = []
    for name in LEDGER_CATEGORIES:
        data.append({"name": name, "count": LedgerFile.query.filter_by(category=name).count()})
    return jsonify({"ok": True, "data": data, "total": LedgerFile.query.count()})


@bp.get("/ledger")
def list_files():
    """台账列表：分类筛选 + 文件名/标题搜索。"""
    category = request.args.get("category", "").strip()
    keyword = request.args.get("q", "").strip()

    query = LedgerFile.query
    if category and category != "all":
        query = query.filter(LedgerFile.category == category)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(LedgerFile.title.like(like), LedgerFile.original_name.like(like))
        )

    rows = query.order_by(LedgerFile.created_at.desc()).all()
    return jsonify(
        {
            "ok": True,
            "data": [f.to_dict() for f in rows],
            "total": len(rows),
            "all_total": LedgerFile.query.count(),
        }
    )


@bp.post("/ledger")
@api_login_required
def upload_file():
    """上传台账文件（管理员）。真实落盘 + 入库。"""
    user = current_user()
    if not user.is_admin:
        return jsonify({"ok": False, "msg": "只有管理员可以上传台账"}), 403

    if "file" not in request.files:
        return jsonify({"ok": False, "msg": "没有选择文件"}), 400
    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"ok": False, "msg": "文件名为空"}), 400

    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    allowed = current_app.config["ALLOWED_UPLOAD_EXT"]
    if ext not in allowed:
        return jsonify({"ok": False, "msg": f"不支持的文件类型 .{ext}"}), 400

    original = secure_filename(f.filename) or f"file.{ext}"
    stored = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = Path(current_app.config["UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / stored
    f.save(target)

    category = request.form.get("category") or "其他"
    if category not in LEDGER_CATEGORIES:
        category = "其他"
    title = (request.form.get("title") or os.path.splitext(f.filename)[0])[:200]

    record = LedgerFile(
        title=title,
        filename=stored,
        original_name=f.filename,
        category=category,
        ext=ext,
        size_bytes=target.stat().st_size,
        uploader_id=user.id,
        is_demo=False,
    )
    db.session.add(record)
    db.session.commit()
    return jsonify({"ok": True, "data": record.to_dict(), "msg": "上传成功"})


@bp.get("/ledger/<int:file_id>/download")
@api_login_required
def download(file_id: int):
    """下载台账文件，下载次数写库。

    要求登录：台账里是会议纪要、党员名单这类材料，不能对匿名访客开放。
    未登录的浏览器会拿到 401 JSON，前端会跳登录页。
    """
    record = LedgerFile.query.get_or_404(file_id)
    upload_dir = Path(current_app.config["UPLOAD_DIR"])
    target = upload_dir / record.filename
    if not target.exists():
        return jsonify({"ok": False, "msg": "文件在磁盘上不存在，可能已被清理"}), 404

    record.download_count = (record.download_count or 0) + 1
    db.session.commit()
    return send_file(
        target,
        as_attachment=True,
        download_name=record.original_name or target.name,
    )


@bp.delete("/ledger/<int:file_id>")
@api_login_required
def delete_file(file_id: int):
    """删除台账（管理员）。同时删磁盘文件。"""
    user = current_user()
    if not user.is_admin:
        return jsonify({"ok": False, "msg": "需要管理员权限"}), 403
    record = LedgerFile.query.get_or_404(file_id)
    target = Path(current_app.config["UPLOAD_DIR"]) / record.filename
    if target.exists():
        target.unlink()
    db.session.delete(record)
    db.session.commit()
    return jsonify({"ok": True, "msg": "已删除"})
