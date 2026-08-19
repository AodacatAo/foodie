#!/usr/bin/env python3
"""大众点评自动登录：弹出 Chrome 窗口，用户手机号+验证码登录，检测成功后保存登录态。

登录态保存在 backend/data/dp_profile/（与点评抓取共用），
登录后支持：按店名搜索、店铺信息/封面抓取、坐标获取。

用法: backend/.venv/bin/python scripts/dianping_login.py
"""
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PROFILE_DIR = ROOT / "backend" / "data" / "dp_profile"
HOME_URL = "https://m.dianping.com"
MAX_WAIT_SEC = 600

CHECK_JS = """() => {
    // 登录成功标志：存在 dper 会话 cookie 或页面出现用户头像（登录按钮消失）
    const body = document.body ? document.body.innerText : '';
    const hasLoginBtn = /登录|立即登录/.test(body.slice(0, 300));
    const avatar = !!document.querySelector('img[class*="avatar"], [class*="user-info"] img, img[src*="meituan.net/avatar"]');
    return { hasLoginBtn, avatar };
}"""


def main() -> None:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    print("正在启动 Chrome 窗口…")
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
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(HOME_URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)
        print("=" * 56)
        print("  请在弹出的 Chrome 窗口中完成登录")
        print("  手机号 + 验证码即可（无需扫码）")
        print("  登录成功后自动检测并保存，无需其他操作")
        print("=" * 56)

        deadline = time.time() + MAX_WAIT_SEC
        ok = False
        while time.time() < deadline:
            time.sleep(3)
            if page.is_closed():
                print("窗口已关闭，未完成登录")
                break
            try:
                state = page.evaluate(CHECK_JS)
            except Exception:
                state = {}
            cookies = context.cookies()
            has_dper = any(c["name"] == "dper" and c.get("value") for c in cookies)
            if has_dper or (state.get("avatar") and not state.get("hasLoginBtn")):
                ok = True
                break
        context.close()

    if ok:
        print("✅ 大众点评登录态已保存（backend/data/dp_profile/），可以按店名搜索了")
    else:
        print("⚠️ 未检测到登录态（超时或未完成登录），可重新运行本脚本再试")


if __name__ == "__main__":
    main()
