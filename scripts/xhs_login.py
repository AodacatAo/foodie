#!/usr/bin/env python3
"""小红书自动登录 v3（隐身化）：去自动化标记、新配置目录、预热浏览、严格登录态检测。

检测登录成功（任一）：
  1. 页面内 API（带 _webmsxyw 签名）返回 code==0 且含用户信息
  2. 页面无「登录」按钮、URL 不是错误页、出现头像且 web_session 存在
成功 → 保存 cookie 到 backend/data/xhs_cookies.json
"""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PROFILE_DIR = ROOT / "backend" / "data" / "xhs_profile"
COOKIE_FILE = ROOT / "backend" / "data" / "xhs_cookies.json"
HOME_URL = "https://www.xiaohongshu.com"
MAX_WAIT_SEC = 900  # 15 分钟

API_CHECK_JS = """async () => {
  // 登录态接口 /v2/user/me（正确接口），签名取 _webmsxyw 返回的 {X-s, X-t}
  try {
    const t = Date.now();
    const path = '/api/sns/web/v2/user/me';
    const query = 'aid=6383';
    let headers = {};
    if (window._webmsxyw) {
      const s = window._webmsxyw(t, 'GET', path, query, '');
      headers = { 'x-s': s['X-s'] || s['x-s'], 'x-t': s['X-t'] || String(t) };
    }
    const res = await fetch('https://edith.xiaohongshu.com' + path + '?' + query, {
      credentials: 'include', headers,
    });
    const data = await res.json();
    if (data && data.code === 0 && data.data && data.data.nickname) {
      return { api: true, nickname: data.data.nickname };
    }
    return { api: false, code: data && data.code };
  } catch (e) { return { api: false, error: String(e).slice(0, 80) }; }
}"""

DOM_CHECK_JS = """() => {
  const url = location.href;
  const isErrorPage = url.includes('website-login/error') || url.includes('error_msg');
  const loginBtn = [...document.querySelectorAll('button, a, span, div')]
    .find(el => el.textContent.trim() === '登录' && el.offsetParent !== null && el.offsetWidth > 0);
  const avatars = [...document.querySelectorAll('img')]
    .map(i => i.currentSrc || i.src || '')
    .filter(s => s.includes('avatar') && s.length > 40);
  return { isErrorPage, loginBtnVisible: !!loginBtn, avatar: avatars[0] ? avatars[0].slice(0, 100) : '' };
}"""


def save_cookies(context) -> None:
    cookies = context.cookies()
    COOKIE_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  已保存 {len(cookies)} 条 cookie → {COOKIE_FILE}")


def main() -> None:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    print("正在启动 Chrome（隐身化模式）…")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            channel="chrome",
            headless=False,
            viewport={"width": 1280, "height": 900},
            ignore_default_args=["--enable-automation"],
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(HOME_URL, wait_until="domcontentloaded", timeout=45000)
        # 预热：浏览一会，建立会话信任
        print("预热浏览页面…")
        for i in range(5):
            page.mouse.wheel(0, 1200)
            time.sleep(2)
        print("=" * 56)
        print("  请在弹出的 Chrome 窗口中完成登录")
        print("  ⚠️ 若扫码提示风险/失败，请改用【手机号登录】")
        print("     （点登录框下方的「手机号登录」→ 输入手机号 → 验证码）")
        print("  检测到真实登录态后自动保存并关闭")
        print("=" * 56)

        deadline = time.time() + MAX_WAIT_SEC
        ok = False
        while time.time() < deadline:
            time.sleep(4)
            if page.is_closed():
                print("窗口已关闭，未完成登录")
                break
            try:
                api = page.evaluate(API_CHECK_JS)
                dom = page.evaluate(DOM_CHECK_JS)
            except Exception:
                continue
            state = {"api": api.get("api"), "nick": api.get("nickname", ""),
                     "err_page": dom.get("isErrorPage"), "login_btn": dom.get("loginBtnVisible")}
            print("  检测:", state)
            if api.get("api"):
                ok = True
                break
            if not dom.get("isErrorPage") and not dom.get("loginBtnVisible") and dom.get("avatar"):
                cookies = context.cookies()
                if any(c["name"] == "web_session" and c.get("value") for c in cookies):
                    ok = True
                    break
        save_cookies(context)
        context.close()

    if ok:
        print("✅ 真实登录态确认，cookie 已保存，可以开始 M2 抓取")
    else:
        print("⚠️ 未检测到登录态（超时或未登录），已保存当前 cookie 供排查")
        print("   可重新运行本脚本再试一次")


if __name__ == "__main__":
    main()
