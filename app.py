"""应用工厂：智慧党建系统（第一阶段 / 个人订阅号 HXAI云 测试）。

启动：
    python run.py            # 读取 .env，监听 APP_HOST:APP_PORT
或：
    flask --app app:create_app run

要点：
1. 所有可变配置都来自 .env（见 config.py），代码里不写死域名、端口、账号。
2. 数据库走 SQLAlchemy，SQLite / MySQL 只改 DB_ENGINE。
3. 蓝图按模块拆分：页面（pages）+ 接口（articles/activities/ledger/stats/auth/wechat）。
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from config import BASE_DIR, Config
from backend.admin import bp as admin_bp
from backend.api import ALL_BLUEPRINTS
from backend.extensions import db
from backend.pages import bp as pages_bp


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_object)

    # ---------- 中文 JSON ----------
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    # ---------- 扩展 ----------
    db.init_app(app)

    # ---------- 蓝图 ----------
    app.register_blueprint(pages_bp)
    app.register_blueprint(admin_bp)
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    # ---------- 模板全局变量 ----------
    @app.context_processor
    def inject_globals():
        from backend.auth import current_user
        from backend.models import Category, Article, User, Activity

        user = current_user()
        # 只有"存在测试数据"时才显示「测试数据」提示，避免上线后还挂着演示标签
        demo_exists = (
            Article.query.filter_by(is_demo=True).count()
            + Activity.query.filter_by(is_demo=True).count()
        ) > 0
        return {
            "current_user": user,
            "show_test_login_banner": bool(user and user.is_test_account),
            "demo_data_exists": demo_exists,
            "categories": Category.query.order_by(Category.sort_order).all(),
            "nav_categories": Category.query.order_by(Category.sort_order).all(),
        }

    # ---------- 错误处理 ----------
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "code": 404, "msg": "接口不存在"}), 404
        return render_template("error.html", code=404, message="页面不存在"), 404

    @app.errorhandler(403)
    def forbidden(e):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "code": 403, "msg": "没有权限"}), 403
        return render_template("error.html", code=403, message="没有权限访问"), 403

    @app.errorhandler(413)
    def too_large(e):
        limit_mb = int(app.config["MAX_CONTENT_LENGTH"] / 1024 / 1024)
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "msg": f"文件超过 {limit_mb} MB 上限"}), 413
        return render_template("error.html", code=413, message=f"文件超过 {limit_mb} MB 上限"), 413

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("服务器内部错误")
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "code": 500, "msg": "服务器内部错误"}), 500
        return render_template("error.html", code=500, message="服务器内部错误"), 500

    # ---------- 建表 + 初始化数据 ----------
    with app.app_context():
        db.create_all()
        # 补齐系统设置默认键（微信参数 / 登录方式等，后台「微信设置」页可改）
        from backend.settings_store import ensure_defaults

        try:
            ensure_defaults()
        except Exception:  # 设置初始化失败不阻断启动
            app.logger.exception("初始化系统设置失败")
        if app.config.get("AUTO_SEED", True):
            from backend.seed import seed

            try:
                seed(app)
            except Exception:  # 初始化失败不阻断启动，日志里能看到
                app.logger.exception("初始化数据失败")

    # ---------- 请求日志（便于学校运维排查） ----------
    if not app.debug:
        logging.basicConfig(level=logging.INFO)

    return app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "5000"))
    app.run(host=host, port=port, debug=os.getenv("APP_ENV", "local") == "local")
