"""党建风采接口：图片墙列表。

后端原先只有服务端渲染的 GET /gallery（HTML 页面），小程序端解析 HTML 不便，
这里补一个只读 JSON 接口；H5 前台页面仍走服务端渲染模板。

接口约定（与其它模块一致）：{ok, data, total}
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..models import GalleryPhoto

bp = Blueprint("api_gallery", __name__, url_prefix="/api")


@bp.get("/gallery")
def list_photos():
    """党建风采图片列表（公开只读）。

    查询参数：
        size  可选，最多返回多少条（不传或 <=0 表示全部）
    """
    size = request.args.get("size", type=int) or 0

    query = GalleryPhoto.query.order_by(GalleryPhoto.id.desc())
    total = query.count()
    rows = query.limit(size).all() if size > 0 else query.all()

    data = []
    for photo in rows:
        item = photo.to_dict()
        # to_dict() 不含 is_demo，这里补上，前端据此显示「测试数据」标签
        item["is_demo"] = bool(photo.is_demo)
        data.append(item)

    return jsonify({"ok": True, "data": data, "total": total})
