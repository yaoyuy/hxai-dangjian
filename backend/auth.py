"""登录与会话。

第一阶段（个人订阅号）：个人号没有网页授权权限，所以用本地测试账号登录，
页面上必须明确显示「测试登录，非微信身份」，绝不伪造 openid。
第二阶段（学校已认证公众号）：把 LOGIN_MODE 改成 wechat，走 OAuth2 网页授权拿 openid。
"""
from __future__ import annotations

from functools import wraps

from flask import abort, current_app, g, jsonify, redirect, request, session, url_for
from itsdangerous import BadSignature, URLSafeSerializer

from .models import User

# 小程序端没有浏览器 cookie 那么方便，用签名 token 走 X-Auth-Token 头。
# token 用 SECRET_KEY 签名，不落库、可随时通过换 SECRET_KEY 全部失效。
TOKEN_SALT = "hxai-dangjian-api-token"


def _token_serializer() -> URLSafeSerializer:
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt=TOKEN_SALT)


def issue_token(user: User) -> str:
    """给小程序端签发登录 token。"""
    return _token_serializer().dumps({"uid": user.id})


def _user_from_token(token: str) -> User | None:
    try:
        data = _token_serializer().loads(token)
    except BadSignature:
        return None
    uid = data.get("uid") if isinstance(data, dict) else None
    return User.query.get(uid) if uid else None


def _user_from_request_token() -> User | None:
    """从请求头 X-Auth-Token（或 ?token=）里解析用户；无请求上下文时返回 None。"""
    try:
        token = request.headers.get("X-Auth-Token", "")
        if not token:
            token = request.args.get("token", "")
    except RuntimeError:  # 没有请求上下文（例如命令行脚本）
        return None
    return _user_from_token(token) if token else None


def current_user() -> User | None:
    """当前登录用户：先看浏览器 session，再看小程序 token 头。"""
    if "user" in g:
        return g.user
    uid = session.get("uid")
    user = User.query.get(uid) if uid else None
    if user is None:
        user = _user_from_request_token()
    g.user = user
    return user


def login_user(user: User) -> None:
    session.clear()
    session["uid"] = user.id
    session["login_mode"] = "test" if user.is_test_account else "wechat"
    g.user = user


def logout_user() -> None:
    session.clear()
    g.pop("user", None)


def login_required(view):
    """页面级登录校验：未登录跳登录页。"""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("pages.login", next=_safe_next()))
        return view(*args, **kwargs)

    return wrapper


def api_login_required(view):
    """接口级登录校验：未登录返回 401 JSON。"""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return jsonify({"ok": False, "code": 401, "msg": "请先登录"}), 401
        return view(*args, **kwargs)

    return wrapper


def admin_required(view):
    """管理员校验（预留多角色扩展）。"""

    @wraps(view)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return redirect(url_for("pages.login", next=_safe_next()))
        if not user.is_admin:
            # 后台是 HTML 页面，交给 app.py 的 403 处理器渲染友好页面；
            # /api/ 路径的 403 处理器仍会返回 JSON。
            abort(403)
        return view(*args, **kwargs)

    return wrapper


def _safe_next() -> str:
    from flask import request

    nxt = request.args.get("next") or request.path
    if not nxt.startswith("/"):
        return "/"
    return nxt
