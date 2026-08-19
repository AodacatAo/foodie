"""小红书抓取适配层（M2）。

核心方案：登录态保存在本地浏览器 profile（scripts/xhs_login.py 生成，
backend/data/xhs_profile/），抓取时用无头 Chrome 打开笔记页，从页面内嵌的
window.__INITIAL_STATE__ 提取笔记完整数据 —— 完全绕开 x-s 签名问题
（xhs 库的纯 Python 签名算法已过时，API 直连会被拒）。

对外接口：parse_note_url(url) / PlaywrightFetcher.fetch_note(url) -> NotePayload
"""
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ..config import settings

# 关键：伪装正常 Chrome UA。小红书 WAF 会把 "HeadlessChrome" 识别为自动化并触发风控
CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


@dataclass
class NotePayload:
    note_id: str
    title: str
    desc: str
    author: str
    author_id: str | None = None
    cover_image: str | None = None
    image_urls: list[str] = field(default_factory=list)
    video_url: str | None = None
    raw: dict = field(default_factory=dict)  # 原始数据（快照落盘用）


class XhsFetchError(Exception):
    """抓取失败（未登录/笔记不存在/被风控等）。"""


def parse_note_url(url: str) -> dict:
    """从各种小红书链接中提取 note_id / xsec_token / xsec_source。"""
    url = url.strip()
    m = re.search(r"/(?:explore|discovery/item|item)/([0-9a-f]{24})", url)
    if not m:
        raise XhsFetchError("无法从链接中识别笔记 ID（支持 /explore/xxx 与 /discovery/item/xxx 格式）")
    qs = parse_qs(urlparse(url).query)
    return {
        "note_id": m.group(1),
        "xsec_token": (qs.get("xsec_token") or [""])[0],
        "xsec_source": (qs.get("xsec_source") or [""])[0],
    }


def _norm_img_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if u.startswith("//"):
        u = "https:" + u
    elif u.startswith("http://"):
        u = "https://" + u[len("http://"):]
    elif not u.startswith("http"):
        u = "https://" + u
    return u


def _parse_note(note_id: str, note: dict) -> NotePayload:
    """解析页面内嵌笔记数据。

    注意：XHS 页面数据是 camelCase 键（imageList / urlDefault / urlPre / infoList）。
    """
    title = note.get("title") or ""
    desc = note.get("desc") or ""
    user = note.get("user") or {}
    type_ = note.get("type") or "normal"
    image_list = note.get("imageList") or []
    video = note.get("video") or {}

    image_urls: list[str] = []
    cover = None
    video_url = None
    if type_ == "video":
        # 视频地址：video.media.stream.<codec>[0].masterUrl（可能带签名）
        media = video.get("media") or {}
        for _codec, arr in (media.get("stream") or {}).items():
            if arr and arr[0].get("masterUrl"):
                video_url = _norm_img_url(arr[0]["masterUrl"])
                break
        cover = (video.get("cover") or {}).get("urlPre") or (video.get("cover") or {}).get("urlDefault")
    for img in image_list:
        u = _norm_img_url(
            img.get("urlDefault") or img.get("urlPre") or ""
        )
        if not u:
            # infoList 兜底：取 WB_DFT 场景
            for entry in img.get("infoList") or []:
                if entry.get("imageScene") in ("WB_DFT", "WB_ORIG"):
                    u = _norm_img_url(entry.get("url") or "")
                    if u:
                        break
        if u:
            image_urls.append(u)
    if not cover and image_urls:
        cover = image_urls[0]

    return NotePayload(
        note_id=note_id,
        title=title,
        desc=desc,
        author=user.get("nickname") or "",
        author_id=str(user.get("userId") or user.get("user_id") or "") or None,
        cover_image=_norm_img_url(cover) if cover else None,
        image_urls=image_urls,
        video_url=video_url,
        raw=note,
    )


_EXTRACT_JS = """() => {
    const s = window.__INITIAL_STATE__;
    if (!s || !s.note || !s.note.noteDetailMap) return { error: 'no_state' };
    const map = s.note.noteDetailMap;
    const nid = Object.keys(map)[0];
    if (!nid || !map[nid].note) return { error: 'no_note' };
    return { nid, note: map[nid].note };
}"""


def _extract_real_url(final_url: str) -> str:
    """短链会先跳到 website-login/error 页，真实笔记 URL 藏在 redirectPath 参数里。"""
    if "/website-login/error" in final_url:
        qs = parse_qs(urlparse(final_url).query)
        rp = (qs.get("redirectPath") or [""])[0]
        if rp:
            return rp
    return final_url


class PlaywrightFetcher:
    """首选抓取器：无头 Chrome + 登录 profile + 页面内嵌数据提取。

    支持：完整笔记链接 / 短链接（xhslink.cn 等，自动从重定向解析真实笔记 URL）。
    """

    def __init__(self, profile_dir: Path | None = None):
        self.profile_dir = Path(profile_dir or (settings.data_dir / "xhs_profile"))

    def fetch_note(self, url: str) -> NotePayload:
        try:
            parsed = parse_note_url(url)
        except XhsFetchError:
            parsed = None  # 短链接等：先导航，再从最终 URL 解析
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise XhsFetchError("未安装 playwright（pip install playwright）") from exc

        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir),
                    channel="chrome",
                    chromium_sandbox=(os.geteuid() != 0),  # 容器内以 root 运行需禁沙箱
                    headless=True,
                    ignore_default_args=["--enable-automation"],
                    user_agent=CHROME_UA,
                    viewport={"width": 1280, "height": 900},
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                if parsed is None:
                    # 短链接：等待重定向，解析真实笔记 URL（可能藏在错误页 redirectPath）
                    page.wait_for_timeout(4000)
                    real_url = _extract_real_url(page.url)
                    if real_url != page.url:
                        page.goto(real_url, wait_until="domcontentloaded", timeout=45000)
                        page.wait_for_timeout(3000)
                    parsed = parse_note_url(real_url)
                data = None
                for _ in range(12):  # 最多等 ~24s 内嵌数据注入
                    data = page.evaluate(_EXTRACT_JS)
                    if data and not data.get("error"):
                        break
                    page.wait_for_timeout(2000)
                context.close()
        except XhsFetchError:
            raise
        except Exception as exc:
            raise XhsFetchError(f"页面抓取失败: {exc}") from exc

        if parsed is None:
            raise XhsFetchError("无法从链接中识别笔记 ID（短链接未重定向到笔记页）")
        note_id = parsed["note_id"]
        if not data or data.get("error"):
            raise XhsFetchError("页面未包含笔记数据（可能未登录 / 笔记不存在 / 被风控）")
        note = data["note"]
        if note.get("note_id"):
            note_id = note["note_id"]
        return _parse_note(note_id, note)


def make_fetcher() -> PlaywrightFetcher:
    return PlaywrightFetcher()
