"""微信接入（公众号 + 小程序）。

能力边界（如实说明，不假装更强）：
- 个人未认证订阅号：可以配置服务器地址接收消息 / 事件、被动回复文本；**不能**网页授权、
  不能调用自定义菜单接口（返回 48001）、不能发模板 / 客服消息、不能支付、不能 JS-SDK 签名。
- 已认证服务号（第二阶段学校号）：可以网页授权拿 openid、可以用 API 推送菜单。
- 小程序（含个人主体）：`wx.login` 拿 code，服务端用 jscode2session 换 openid，这条不受认证限制。

参数来源：后台「微信设置」页（数据库 sys_setting）优先，其次 .env（config.py）。
"""
from __future__ import annotations

import hashlib
import time

import requests
from flask import current_app

from . import settings_store

WECHAT_API = "https://api.weixin.qq.com"


def check_signature(signature: str, timestamp: str, nonce: str) -> bool:
    """校验消息确实来自微信服务器：token / timestamp / nonce 字典序排序后 sha1。

    token 取自后台「微信设置」页；没填就读 .env 的 WECHAT_TOKEN。
    两者都没配时返回 False（不伪造成功）。
    """
    token = settings_store.get_wechat_config().get("token") or ""
    if not token:
        return False
    raw = "".join(sorted([token, timestamp or "", nonce or ""]))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest() == signature


def _access_token_cache() -> dict:
    """进程内 access_token 缓存（简单够用；学校环境可换成 Redis）。"""
    app = current_app._get_current_object()
    if not hasattr(app, "_wx_token_cache"):
        app._wx_token_cache = {"token": None, "expires_at": 0}
    return app._wx_token_cache


def get_access_token(force: bool = False) -> tuple[str | None, str]:
    """获取公众号 access_token。返回 (token, 错误说明)。未配置时返回 (None, 原因)。"""
    cfg = settings_store.get_wechat_config()
    appid, secret = cfg.get("appid") or "", cfg.get("secret") or ""
    if not appid or not secret:
        return None, "未配置公众号 AppID / AppSecret（可在后台「微信设置」页填写）"

    cache = _access_token_cache()
    if not force and cache["token"] and cache["expires_at"] > time.time():
        return cache["token"], ""

    try:
        resp = requests.get(
            f"{WECHAT_API}/cgi-bin/token",
            params={"grant_type": "client_credential", "appid": appid, "secret": secret},
            timeout=10,
        )
        data = resp.json()
    except Exception as exc:  # 网络异常也要如实返回，不能假装成功
        return None, f"请求微信接口失败：{exc}"

    token = data.get("access_token")
    if not token:
        return None, f"微信返回错误：{data.get('errcode')} {data.get('errmsg')}"
    cache["token"] = token
    cache["expires_at"] = time.time() + int(data.get("expires_in", 7200)) - 200
    return token, ""


def create_menu(buttons: list[dict]) -> tuple[bool, str]:
    """尝试用接口创建自定义菜单。

    未认证个人订阅号调用会返回 48001（api unauthorized），这是微信侧权限限制，
    本函数如实返回失败原因，不做任何伪装。第一阶段菜单请在公众号后台手动配置。
    """
    token, err = get_access_token()
    if not token:
        return False, err
    try:
        resp = requests.post(
            f"{WECHAT_API}/cgi-bin/menu/create",
            params={"access_token": token},
            json={"button": buttons},
            timeout=10,
        )
        data = resp.json()
    except Exception as exc:
        return False, f"请求失败：{exc}"
    if data.get("errcode") == 0:
        return True, "菜单创建成功"
    return False, f"{data.get('errcode')} {data.get('errmsg')}"


def build_menu(base_url: str) -> list[dict]:
    """生成菜单结构（view 型链接）。

    注意：个人订阅号没有 view 型菜单权限（48001），此结构供学校认证号使用。
    """
    base = base_url.rstrip("/")
    return [
        {
            "name": "党建学习",
            "sub_button": [
                {"type": "view", "name": "学习专栏", "url": f"{base}/study"},
                {"type": "view", "name": "云党课", "url": f"{base}/study?category=cloud"},
                {"type": "view", "name": "党史学习", "url": f"{base}/study?category=history"},
            ],
        },
        {
            "name": "组织生活",
            "sub_button": [
                {"type": "view", "name": "三会一课", "url": f"{base}/meetings"},
                {"type": "view", "name": "活动报名", "url": f"{base}/activities"},
                {"type": "view", "name": "电子台账", "url": f"{base}/ledger"},
            ],
        },
        {
            "name": "支部风采",
            "sub_button": [
                {"type": "view", "name": "党建风采", "url": f"{base}/gallery"},
                {"type": "view", "name": "数据看板", "url": f"{base}/dashboard"},
                {"type": "view", "name": "我的", "url": f"{base}/me"},
            ],
        },
    ]


def build_oauth_url(redirect_uri: str, scope: str | None = None) -> str:
    """生成网页授权链接。需要已认证服务号（或已认证的政府 / 事业单位 / 媒体订阅号）。"""
    cfg = settings_store.get_wechat_config()
    appid = cfg.get("appid") or ""
    if not appid:
        return ""
    from urllib.parse import quote

    scope = scope or settings_store.get("oauth_scope") or "snsapi_base"
    return (
        "https://open.weixin.qq.com/connect/oauth2/authorize"
        f"?appid={appid}&redirect_uri={quote(redirect_uri, safe='')}"
        f"&response_type=code&scope={scope}&state=hxai#wechat_redirect"
    )


def jscode2session(code: str) -> tuple[dict | None, str]:
    """小程序登录：code 换 openid / session_key。返回 (data, 错误说明)。

    这一步不受"是否认证"限制（个人主体小程序也可以用），但需要先注册小程序
    并在后台「微信设置」里填小程序 AppID / AppSecret。
    """
    cfg = settings_store.get_wxapp_config()
    if not cfg.get("appid") or not cfg.get("secret"):
        return None, "未配置小程序 AppID / AppSecret（可在后台「微信设置」页填写）"
    if not code:
        return None, "缺少 code（小程序端需要先调用 wx.login 获取）"
    try:
        resp = requests.get(
            f"{WECHAT_API}/sns/jscode2session",
            params={
                "appid": cfg["appid"], "secret": cfg["secret"],
                "js_code": code, "grant_type": "authorization_code",
            },
            timeout=10,
        )
        data = resp.json()
    except Exception as exc:
        return None, f"请求微信接口失败：{exc}"
    if data.get("openid"):
        return data, ""
    return None, f"微信返回错误：{data.get('errcode')} {data.get('errmsg')}"


def oauth_access_token(code: str) -> tuple[dict | None, str]:
    """公众号网页授权：code 换 openid。返回 (data, 错误说明)。

    个人未认证订阅号调用会返回 48001 / 40164 之类的错误，这里如实返回，不伪装成功。
    """
    cfg = settings_store.get_wechat_config()
    if not cfg.get("appid") or not cfg.get("secret"):
        return None, "未配置公众号 AppID / AppSecret（可在后台「微信设置」页填写）"
    if not code:
        return None, "缺少 code（需要先跳转微信授权链接并拿到回调 code）"
    try:
        resp = requests.get(
            f"{WECHAT_API}/sns/oauth2/access_token",
            params={
                "appid": cfg["appid"], "secret": cfg["secret"],
                "code": code, "grant_type": "authorization_code",
            },
            timeout=10,
        )
        data = resp.json()
    except Exception as exc:
        return None, f"请求微信接口失败：{exc}"
    if data.get("openid"):
        return data, ""
    return None, f"微信返回错误：{data.get('errcode')} {data.get('errmsg')}"


def oauth_userinfo(access_token: str, openid: str) -> tuple[dict | None, str]:
    """snsapi_userinfo 授权后拉取昵称 / 头像（需要用户点确认，个人号无此权限）。"""
    try:
        resp = requests.get(
            f"{WECHAT_API}/sns/userinfo",
            params={"access_token": access_token, "openid": openid, "lang": "zh_CN"},
            timeout=10,
        )
        data = resp.json()
    except Exception as exc:
        return None, f"请求微信接口失败：{exc}"
    if data.get("openid"):
        return data, ""
    return None, f"微信返回错误：{data.get('errcode')} {data.get('errmsg')}"
