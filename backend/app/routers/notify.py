"""通用微信即时通知接口：供脚本/技能/其他系统向用户微信发消息。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services import wechat_notify

router = APIRouter(prefix="/api/notify", tags=["notify"])


class NotifyBody(BaseModel):
    text: str


@router.post("")
def send_notification(body: NotifyBody):
    """向登录者微信推送一条文本消息。

    安全：受全局鉴权中间件保护——非局域网来源需登录（Cookie）。
    账号未配置或推送失败时返回 503（不重试语义由调用方决定）。
    """
    text = body.text.strip()[:500]
    if not text:
        raise HTTPException(400, "消息内容不能为空")
    if wechat_notify.send_wechat_text(text):
        return {"ok": True, "sent": True}
    return {"ok": False, "sent": False, "detail": "推送失败（账号未配置或网络错误）"}
