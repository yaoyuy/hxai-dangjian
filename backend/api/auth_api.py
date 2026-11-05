"""登录相关接口。

三种登录方式，放行与否由后台「微信设置」页的 login_mode 决定：
1. 测试账号登录（login_mode = test / both）
   个人订阅号没有网页授权权限，本地测试只能用账号密码；返回体里明确标注
   "测试登录，非微信身份"，绝不伪造 openid。
2. 微信小程序登录（小程序 wx.login → code → jscode2session → openid）
   个人主体小程序也能用这条；openid 换系统账号时会查白名单。
3. 公众号网页授权登录（code → sns/oauth2/access_token → openid）
   需要已认证服务号（或已认证的政府 / 事业单位 / 媒体类订阅号），第二阶段学校号用这条。

白名单（表 login_whitelist）：只有名单里的微信才允许进系统；名单在后台「白名单」页维护。
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from .. import settings_store
from ..auth import api_login_required, current_user, issue_token, login_user, logout_user
from ..extensions import db
from ..models import User, Whitelist
from ..wechat import jscode2session, oauth_access_token, oauth_userinfo

bp = Blueprint("api_auth", __name__, url_prefix="/api/auth")


def _notice_for(user: User) -> str:
    return "测试登录，非微信身份" if user.is_test_account else "微信身份（已获取 openid）"


@bp.get("/config")
def config():
    """登录页 / 小程序端读取的公开配置（不含任何密钥）。"""
    return jsonify({"ok": True, "data": settings_store.public_config()})


@bp.post("/login")
def login():
    """测试账号登录。"""
    payload = request.get_json(silent=True) or request.form
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    if not settings_store.test_login_allowed():
        return jsonify({
            "ok": False,
            "msg": "当前登录方式已设为「仅微信登录」，测试账号不可用；"
                   "可在后台「微信设置」页把登录方式改回 test 或 both。",
        }), 403

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"ok": False, "msg": "账号或密码错误"}), 401

    user.last_login_at = datetime.now()
    db.session.commit()
    login_user(user)

    return jsonify(
        {
            "ok": True,
            "data": {
                "user": user.to_dict(),
                "login_mode": "test",
                "notice": "测试登录，非微信身份",
                # 小程序端拿这个 token 放 X-Auth-Token 头里；浏览器端用不到（走 cookie）
                "token": issue_token(user),
            },
            "msg": "登录成功（测试登录，非微信身份）",
        }
    )


def _resolve_openid_user(openid: str, nickname: str = "") -> tuple[User | None, str, str]:
    """把 openid 换成系统账号。返回 (user, 错误信息, 错误码)。

    顺序：白名单校验 → 已绑定账号 → 手机号匹配 → 新建账号。
    白名单关闭时，任何微信都可以自动建号（配置页有风险提示）。
    """
    wl = Whitelist.query.filter_by(openid=openid).first()
    if settings_store.whitelist_enabled():
        if wl is None:
            return None, "你的微信不在白名单内，请联系支部管理员把你的 openid 加入白名单", "not_in_whitelist"
        if not wl.is_active:
            return None, "你的白名单已被停用，请联系支部管理员", "whitelist_disabled"

    user = User.query.filter_by(openid=openid).first()
    if user is None and wl is not None and wl.user_id:
        user = db.session.get(User, wl.user_id)
    if user is None and wl is not None and wl.phone:
        user = User.query.filter_by(phone=wl.phone).first()
    if user is None:
        # 新账号：账号名用 openid 片段，保证唯一且不暴露完整 openid
        base_name = f"wx_{openid[-10:]}"
        idx = 1
        username = base_name
        while User.query.filter_by(username=username).first() is not None:
            idx += 1
            username = f"{base_name}{idx}"
        user = User(
            username=username,
            real_name=(wl.name if wl else (nickname or "微信用户")),
            role=(wl.role if wl else "member"),
            branch_id=(wl.branch_id if wl else None),
            phone=(wl.phone if wl else ""),
            openid=openid,
            is_test_account=False,
        )
        user.set_password(openid[-8:] + "Wx@1")  # 占位密码：微信用户不需要账号密码
        db.session.add(user)
        db.session.flush()

    if user.openid != openid:
        user.openid = openid
    if wl is not None:
        wl.user_id = user.id
        if not wl.openid:
            wl.openid = openid
        wl.last_login_at = datetime.now()
    return user, "", ""


@bp.post("/wechat-login")
def wechat_login():
    """微信登录：小程序 code / 公众号网页授权 code / （本地联调用的 dev_openid）。"""
    payload = request.get_json(silent=True) or request.form
    code = (payload.get("code") or "").strip()
    login_type = (payload.get("type") or "wxapp").strip().lower()
    dev_openid = (payload.get("dev_openid") or "").strip()
    nickname = (payload.get("nickname") or "").strip()

    if not settings_store.wechat_login_allowed():
        return jsonify({
            "ok": False,
            "msg": "当前登录方式未开放微信登录（请在后台「微信设置」页填写 AppID / AppSecret，"
                   "并把登录方式改为 both 或 wechat）",
        }), 403

    source = login_type
    if dev_openid:
        # 本地联调：不请求微信，直接用一个 openid 走白名单逻辑；
        # 仅当测试登录仍然允许时才开放，且返回体里明确标注是模拟，绝不冒充真实授权。
        if not settings_store.test_login_allowed():
            return jsonify({"ok": False, "msg": "仅微信登录模式下不允许用 dev_openid 联调"}), 403
        openid, err = dev_openid, ""
        source = "dev_openid"
    elif login_type == "oauth":
        data, err = oauth_access_token(code)
        openid = (data or {}).get("openid", "")
        if not err and settings_store.get("oauth_scope") == "snsapi_userinfo" and data:
            info, info_err = oauth_userinfo(data.get("access_token", ""), openid)
            if not info_err and info:
                nickname = nickname or info.get("nickname", "")
    else:
        data, err = jscode2session(code)
        openid = (data or {}).get("openid", "")

    if not openid:
        return jsonify({"ok": False, "code": "wechat_error", "msg": err or "微信登录失败"}), 400

    user, err, code_err = _resolve_openid_user(openid, nickname)
    if user is None:
        status = 403 if code_err in ("not_in_whitelist", "whitelist_disabled") else 400
        return jsonify({"ok": False, "code": code_err or "denied", "msg": err}), status

    if source != "dev_openid":
        user.is_test_account = False
    user.last_login_at = datetime.now()
    db.session.commit()
    login_user(user)

    notice = "微信身份（已获取 openid）" if source != "dev_openid" else "本地联调登录（openid 由开发者手工提供，非真实微信授权）"
    return jsonify({
        "ok": True,
        "data": {
            "user": user.to_dict(),
            "login_mode": source,
            "openid_tail": openid[-6:],
            "has_openid": True,
            "notice": notice,
            # 小程序端拿这个 token 放 X-Auth-Token 头里
            "token": issue_token(user),
        },
        "msg": "登录成功：" + notice,
    })


@bp.post("/bind-openid")
@api_login_required
def bind_openid():
    """把 openid 绑到当前登录账号（联调用：比如先在浏览器用测试账号登录，再绑小程序 openid）。"""
    user = current_user()
    payload = request.get_json(silent=True) or request.form
    openid = (payload.get("openid") or "").strip()
    if not openid:
        return jsonify({"ok": False, "msg": "请填写 openid"}), 400

    other = User.query.filter_by(openid=openid).first()
    if other is not None and other.id != user.id:
        return jsonify({"ok": False, "code": 409, "msg": "该 openid 已绑定到其它账号"}), 409

    user.openid = openid
    wl = Whitelist.query.filter_by(openid=openid).first()
    if wl is not None:
        wl.user_id = user.id
    else:
        wl = Whitelist(
            name=user.real_name or user.username, phone=user.phone or "", openid=openid,
            branch_id=user.branch_id, role=user.role, note="由账号绑定生成", user_id=user.id,
        )
        db.session.add(wl)
    db.session.commit()
    return jsonify({"ok": True, "data": user.to_dict(), "msg": "openid 已绑定"})


@bp.post("/logout")
def logout():
    logout_user()
    return jsonify({"ok": True, "msg": "已退出登录"})


@bp.get("/me")
def me():
    user = current_user()
    if not user:
        return jsonify({"ok": False, "code": 401, "msg": "未登录", "data": None}), 401
    return jsonify(
        {
            "ok": True,
            "data": {
                "user": user.to_dict(),
                "login_mode": "test" if user.is_test_account else "wechat",
                "notice": _notice_for(user),
                "has_openid": bool(user.openid),
            },
        }
    )
