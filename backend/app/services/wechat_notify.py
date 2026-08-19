"""微信主动推送（iLink Bot 官方协议）：下单等事件即时通知微信。

账号凭据位于 data/wechat_account.json（登录产物迁移而来，字段：token/userId/baseUrl）。
协议参考腾讯官方 openclaw-weixin SDK（@tencent-weixin/openclaw-weixin v2.4.6）。
"""
import base64
import json
import os
import random
import string
import time

import httpx

from ..config import settings

_ACCOUNT_FILE = settings.data_dir / "wechat_account.json"

# iLink 协议常量（与官方 SDK 2.4.6 对齐）
_ILINK_APP_ID = "bot"
_ILINK_APP_CLIENT_VERSION = (2 << 16) | (4 << 8) | 6  # 2.4.6
_CHANNEL_VERSION = "2.4.6"
_DEFAULT_BOT_AGENT = "OpenClaw"


def _load_account() -> dict | None:
    try:
        data = json.loads(_ACCOUNT_FILE.read_text(encoding="utf-8"))
        if data.get("token") and data.get("userId"):
            return data
    except Exception:
        pass
    return None


def _wechat_uin() -> str:
    """随机 uint32 → 十进制字符串 → base64。"""
    return base64.b64encode(str(random.getrandbits(32)).encode()).decode()


def _client_id() -> str:
    return f"openclaw-weixin:{int(time.time() * 1000)}-{''.join(random.choices(string.hexdigits[:16], k=8))}"


def send_wechat_text(text: str) -> bool:
    """向登录者微信推送一条文本消息。账号未配置或发送失败返回 False（不抛异常）。"""
    account = _load_account()
    if not account:
        print("[wechat-notify] 未配置微信账号凭据（data/wechat_account.json），跳过推送")
        return False
    base = account.get("baseUrl") or "https://ilinkai.weixin.qq.com"
    body = {
        "msg": {
            "from_user_id": "",
            "to_user_id": account["userId"],
            "client_id": _client_id(),
            "message_type": 2,  # BOT
            "message_state": 2,  # FINISH
            "item_list": [{"type": 1, "text_item": {"text": text}}],  # TEXT
        },
        "base_info": {
            "channel_version": _CHANNEL_VERSION,
            "bot_agent": _DEFAULT_BOT_AGENT,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "Authorization": f"Bearer {account['token']}",
        "X-WECHAT-UIN": _wechat_uin(),
        "iLink-App-Id": _ILINK_APP_ID,
        "iLink-App-ClientVersion": str(_ILINK_APP_CLIENT_VERSION),
    }
    try:
        with httpx.Client(timeout=15) as client:
            r = client.post(f"{base}/ilink/bot/sendmessage", json=body, headers=headers)
        if r.status_code == 200:
            resp = r.json()
            if resp.get("ret", 0) == 0:
                print(f"[wechat-notify] 推送成功: {text[:40]}")
                return True
            print(f"[wechat-notify] 推送失败 ret={resp.get('ret')} errmsg={resp.get('errmsg')}")
            return False
        print(f"[wechat-notify] HTTP {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"[wechat-notify] 异常: {e}")
        return False
