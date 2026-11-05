"""微信服务器对接入口 + 菜单/诊断接口。

/wechat 这个地址就是公众号后台"服务器配置"里填的 URL。
个人订阅号可以配置（这一步不受认证限制），但配置后公众号后台的自动回复和
菜单会失效，所以第一阶段建议先用"菜单链接 + 公众号文章阅读原文"的方式测试。
"""
from __future__ import annotations

import time
from xml.etree import ElementTree as ET

from flask import Blueprint, Response, current_app, jsonify, request

from ..wechat import build_menu, check_signature, create_menu, get_access_token

bp = Blueprint("wechat", __name__)


def _base_url() -> str:
    """对外地址：优先用 .env 的 PUBLIC_BASE_URL，否则按当前请求推断（不写死域名）。"""
    configured = current_app.config.get("PUBLIC_BASE_URL") or ""
    if configured:
        return configured.rstrip("/")
    return request.host_url.rstrip("/")


@bp.route("/wechat", methods=["GET", "POST"])
def wechat_entry():
    """微信服务器接入点。

    GET：微信验证服务器地址（原样返回 echostr）
    POST：接收用户消息/事件，被动回复一条图文或文本，把用户引到系统里
    """
    signature = request.args.get("signature", "")
    timestamp = request.args.get("timestamp", "")
    nonce = request.args.get("nonce", "")

    if not check_signature(signature, timestamp, nonce):
        # 未配置 Token 或验签失败：如实返回，不假装接入成功
        return Response("signature check failed", status=403, mimetype="text/plain")

    if request.method == "GET":
        echostr = request.args.get("echostr", "")
        return Response(echostr, mimetype="text/plain")

    # POST：解析明文模式的 XML 消息
    xml_text = request.get_data(as_text=True) or ""
    reply = _build_reply(xml_text)
    return Response(reply, mimetype="application/xml")


def _build_reply(xml_text: str) -> str:
    """被动回复：把用户引导到系统首页。个人号支持被动回复文本/图文。"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return "success"

    msg_type = (root.findtext("MsgType") or "").strip()
    from_user = (root.findtext("FromUser") or "").strip()
    to_user = (root.findtext("ToUser") or "").strip()
    base = _base_url()

    if msg_type == "event":
        event = (root.findtext("Event") or "").lower()
        if event == "subscribe":
            text = f"欢迎关注{current_app.config['SITE_NAME']}！\n点击下方链接进入智慧党建系统：\n{base}/"
            return _text_reply(from_user, to_user, text)
        return "success"

    text = (
        f"你好，这里是{current_app.config['SITE_NAME']}。\n"
        f"学习专栏：{base}/study\n"
        f"活动报名：{base}/activities\n"
        f"电子台账：{base}/ledger\n"
        f"数据看板：{base}/dashboard"
    )
    return _text_reply(from_user, to_user, text)


def _text_reply(to_user: str, from_user: str, content: str) -> str:
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{content}]]></Content>"
        "</xml>"
    )


@bp.get("/api/wechat/status")
def wechat_status():
    """诊断：当前公众号配置到什么程度、哪些能力可用/不可用。"""
    token, err = get_access_token()
    return jsonify(
        {
            "ok": True,
            "data": {
                "appid_configured": bool(current_app.config.get("WECHAT_APPID")),
                "secret_configured": bool(current_app.config.get("WECHAT_APPSECRET")),
                "token_configured": bool(current_app.config.get("WECHAT_TOKEN")),
                "login_mode": current_app.config.get("LOGIN_MODE"),
                "server_url": _base_url() + "/wechat",
                "access_token_ok": bool(token),
                "access_token_error": err,
                "capabilities": {
                    "server_callback": True,
                    "passive_reply": True,
                    "custom_menu_api": False,
                    "oauth_web": False,
                    "js_sdk": False,
                    "pay": False,
                },
                "note": "以上能力判定基于个人订阅号；认证服务号可在第二阶段开启 oauth_web。",
            },
        }
    )


@bp.post("/api/wechat/menu/push")
def push_menu():
    """尝试用接口推送菜单（个人号会失败，返回真实错误码）。"""
    base = _base_url()
    ok, msg = create_menu(build_menu(base))
    return jsonify({"ok": ok, "msg": msg, "base_url": base, "menu": build_menu(base)})
