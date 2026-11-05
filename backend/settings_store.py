"""系统设置（表 sys_setting）的读写。

为什么要有这张表
----------------
微信公众号 / 小程序的 AppID、AppSecret、Token 属于"部署时才确定"的参数。
把它们放进数据库，就能在后台「微信设置」页直接填写、保存即生效：

- 不用改代码（第二阶段换学校公众号只改数据，不改程序）；
- 不用改 .env（.env 在部分环境里受安全策略保护、编辑不了）；
- 换服务器 / 换公众号时可复制 / 备份这些设置。

优先级：数据库 sys_setting > .env（config.py）> 代码默认值。
"""
from __future__ import annotations

from urllib.parse import quote

from flask import current_app, has_app_context

from .extensions import db
from .models import SysSetting

# key: (默认值, 分组, 中文名, 是否密文)
DEFAULTS = {
    "wechat_appid": ("", "wechat", "公众号 AppID", False),
    "wechat_appsecret": ("", "wechat", "公众号 AppSecret", True),
    "wechat_token": ("", "wechat", "服务器配置 Token", False),
    "wechat_aeskey": ("", "wechat", "消息加解密密钥 EncodingAESKey", True),
    "wxapp_appid": ("", "wxapp", "小程序 AppID", False),
    "wxapp_appsecret": ("", "wxapp", "小程序 AppSecret", True),
    "login_mode": ("test", "login", "登录方式（test=仅测试账号 / both=两者都可 / wechat=仅微信）", False),
    "whitelist_enabled": ("1", "login", "启用微信登录白名单", False),
    "oauth_scope": ("snsapi_base", "login", "网页授权 scope（snsapi_base / snsapi_userinfo）", False),
    "site_notice": ("", "site", "首页公告（可留空）", False),
}

LOGIN_MODES = {
    "test": "仅测试账号登录",
    "both": "测试账号 + 微信登录",
    "wechat": "仅微信登录（白名单）",
}

SECRET_KEYS = {k for k, v in DEFAULTS.items() if v[3]}

WECHAT_KEYS = ("wechat_appid", "wechat_appsecret", "wechat_token", "wechat_aeskey")
WXAPP_KEYS = ("wxapp_appid", "wxapp_appsecret")


def mask(value: str) -> str:
    """密文只回显首尾，避免页面 / 接口泄露完整密钥。"""
    value = value or ""
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-2:]}"


# ---------------- 基础读写 ----------------

def get(key: str, default: str | None = None) -> str:
    """读一个设置。表不存在（还没建表）时返回默认值，不抛异常。"""
    try:
        row = SysSetting.query.filter_by(key=key).first()
    except Exception:
        row = None
    if row is not None and row.value is not None:
        return row.value
    if default is not None:
        return default
    return DEFAULTS.get(key, ("", "", "", False))[0]


def get_bool(key: str, default: bool = False) -> bool:
    raw = (get(key) or "").strip().lower()
    if raw == "":
        return default
    return raw in ("1", "true", "yes", "on")


def set_value(key: str, value: str, commit: bool = True) -> SysSetting:
    row = SysSetting.query.filter_by(key=key).first()
    if row is None:
        meta = DEFAULTS.get(key, ("", "custom", key, False))
        row = SysSetting(key=key, group=meta[1], label=meta[2], is_secret=meta[3])
        db.session.add(row)
    row.value = "" if value is None else str(value)
    if commit:
        db.session.commit()
    return row


def set_many(pairs: dict, skip_empty_secret: bool = True) -> int:
    """批量保存。密文字段留空表示"不修改"，避免把已保存的密钥清空。"""
    saved = 0
    for key, value in pairs.items():
        if key not in DEFAULTS:
            continue
        if skip_empty_secret and key in SECRET_KEYS and not (value or "").strip():
            continue
        set_value(key, value, commit=False)
        saved += 1
    db.session.commit()
    return saved


def ensure_defaults() -> int:
    """把缺失的默认键补进数据库（启动 / 初始化时调用）。不覆盖已有值。"""
    created = 0
    try:
        existing = {row.key for row in SysSetting.query.all()}
    except Exception:
        return 0
    for key, (default, group, label, is_secret) in DEFAULTS.items():
        if key in existing:
            continue
        db.session.add(SysSetting(key=key, value=default, group=group, label=label, is_secret=is_secret))
        created += 1
    if created:
        db.session.commit()
    return created


def all_items(with_secret: bool = False) -> list[dict]:
    ensure_defaults()
    rows = {row.key: row for row in SysSetting.query.all()}
    items = []
    for key, (default, group, label, is_secret) in DEFAULTS.items():
        row = rows.get(key)
        value = row.value if row is not None else default
        items.append({
            "key": key,
            "value": value if (with_secret or not is_secret) else mask(value),
            "group": group,
            "label": label or (row.label if row else key),
            "is_secret": is_secret,
            "updated_at": row.updated_at.strftime("%Y-%m-%d %H:%M") if (row and row.updated_at) else "",
        })
    return items


# ---------------- 微信参数（数据库优先，.env 兜底） ----------------

def _env(key: str) -> str:
    if not has_app_context():
        return ""
    return str(current_app.config.get(key) or "")


def get_wechat_config() -> dict:
    cfg = {k: (get(k) or "") for k in WECHAT_KEYS}
    env = {
        "wechat_appid": _env("WECHAT_APPID"),
        "wechat_appsecret": _env("WECHAT_APPSECRET"),
        "wechat_token": _env("WECHAT_TOKEN"),
        "wechat_aeskey": _env("WECHAT_AES_KEY"),
    }
    result = {k: (cfg[k] or env.get(k, "")) for k in WECHAT_KEYS}
    appid_from_db = bool(cfg["wechat_appid"])
    secret_from_db = bool(cfg["wechat_appsecret"])
    if appid_from_db or secret_from_db:
        result["source"] = "后台微信设置"
    elif result["wechat_appid"]:
        result["source"] = ".env"
    else:
        result["source"] = "未配置"
    return result


def get_wxapp_config() -> dict:
    cfg = {k: (get(k) or "") for k in WXAPP_KEYS}
    result = dict(cfg)
    result["source"] = "后台微信设置" if cfg["wxapp_appid"] else "未配置"
    return result


def login_mode() -> str:
    """登录方式：test / both / wechat。数据库没填时回退 .env 的 LOGIN_MODE。"""
    mode = (get("login_mode") or "").strip().lower()
    if mode not in LOGIN_MODES:
        mode = (_env("LOGIN_MODE") or "test").strip().lower()
    return mode if mode in LOGIN_MODES else "test"


def test_login_allowed() -> bool:
    if not has_app_context():
        return True
    if not current_app.config.get("ALLOW_TEST_LOGIN", True):
        return False
    return login_mode() in ("test", "both")


def wechat_login_allowed() -> bool:
    """只要配了公众号或小程序的 AppID+Secret，就允许微信登录入口。"""
    wx = get_wechat_config()
    wxapp = get_wxapp_config()
    if login_mode() == "test":
        return False
    return bool((wx["wechat_appid"] and wx["wechat_appsecret"]) or (wxapp["wxapp_appid"] and wxapp["wxapp_appsecret"]))


def whitelist_enabled() -> bool:
    return get_bool("whitelist_enabled", True)


def public_config() -> dict:
    """给前台/登录页看的配置（绝不含密钥）。"""
    wx = get_wechat_config()
    wxapp = get_wxapp_config()
    base = ""
    try:
        from config import resolve_public_base_url
        base = resolve_public_base_url()
    except Exception:
        base = ""
    scope = get("oauth_scope") or "snsapi_base"
    oauth_url = ""
    if wx["wechat_appid"]:
        redirect = f"{base}/login?mode=wechat" if base else "/login?mode=wechat"
        oauth_url = (
            "https://open.weixin.qq.com/connect/oauth2/authorize"
            f"?appid={wx['wechat_appid']}&redirect_uri={quote(redirect, safe='')}"
            f"&response_type=code&scope={scope}&state=hxai#wechat_redirect"
        )
    mode = login_mode()
    return {
        "login_mode": mode,
        "login_mode_label": LOGIN_MODES.get(mode, mode),
        "test_login_allowed": test_login_allowed(),
        "wechat_login_allowed": wechat_login_allowed(),
        "wechat_configured": bool(wx["wechat_appid"] and wx["wechat_appsecret"]),
        "wechat_appid": wx["wechat_appid"],
        "wechat_source": wx["source"],
        "wxapp_configured": bool(wxapp["wxapp_appid"] and wxapp["wxapp_appsecret"]),
        "wxapp_appid": wxapp["wxapp_appid"],
        "whitelist_enabled": whitelist_enabled(),
        "oauth_scope": scope,
        "oauth_url": oauth_url,
        "public_base_url": base,
        "notice": "" if mode != "test" else "测试登录，非微信身份",
    }
