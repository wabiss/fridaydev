import os
import re
import sys
import time
from playwright.sync_api import sync_playwright

COOKIE_STR = os.environ.get("COOKIE")

if not COOKIE_STR:
    print("❌ 错误: 未检测到 COOKIE 环境变量，请在 GitHub Secrets 中配置 COOKIE")
    sys.exit(1)

# 解析 Cookie
cookies = []
for item in COOKIE_STR.split(";"):
    if "=" in item:
        name, value = item.strip().split("=", 1)
        cookies.append({
            "name": name,
            "value": value,
            "domain": "fridaydev.fr",
            "path": "/"
        })

def extract_renewal_date(page):
    """从页面中提取 Renouvellement 到期时间 (格式如: DD/MM/YYYY)"""
    try:
        page_text = page.inner_text("body")
        # 匹配页面中的 Renouvellement : 03/09/2026 或直接的日期
        match = re.search(r"Renouvellement\s*:\s*(\d{2}/\d{2}/\d{4})", page_text)
        if not match:
            match = re.search(r"(\d{2}/\d{2}/\d{4})", page_text)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"⚠️ 提取时间时出错: {e}")
    return None

def run():
    with sync_playwright() as p:
        print("🚀 正在启动无头浏览器...")
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )

        context.add_cookies(cookies)
        page = context.new_page()

        print("1. 正在带 Cookie 访问服务页面...")
        page.goto("https://fridaydev.fr/services/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)  # 等待页面加载

        page_text = page.inner_text("body")
        if "Mes services" not in page_text and "wabiss" not in page_text:
            print("❌ 未识别到服务页面，Cookie 可能已失效，请重新获取 Cookie！")
            page.screenshot(path="result.png", full_page=True)
            browser.close()
            sys.exit(1)

        print("✅ 登录状态有效！")

        # 获取当前的到期时间
        old_date = extract_renewal_date(page)
        print(f"📅 当前服务到期时间为: 【{old_date or '未知'}】")

        print("2. 正在检查续期按钮...")
        renew_btn = page.locator("button:text-is('Renouveler'), a:text-is('Renouveler'), button:has-text('Renouveler'):not(:has-text('dans'))")
        not_yet_btn = page.locator("text=/Renouvelable dans \\d+ jour\\(s\\)/i")

        if renew_btn.count() > 0 and renew_btn.first.is_visible():
            print("🎉 检测到【Renouveler】续期按钮，正在点击...")
            renew_btn.first.click()
            time.sleep(3)

            # 尝试处理续期确认弹窗（如果有）
            try:
                modal_confirm = page.locator(".modal.show button, .modal.active button, .swal2-confirm").filter(has_not_text="suppression").filter(has_not_text="Résilier")
                if modal_confirm.count() > 0 and modal_confirm.first.is_visible():
                    modal_confirm.first.click(timeout=3000)
                    print("✅ 已确认续期弹窗")
                    time.sleep(3)
            except Exception:
                pass

            # 3. 重新刷新页面验证时间是否更新
            print("3. 正在刷新页面，检查到期时间是否更新...")
            page.reload(wait_until="domcontentloaded")
            time.sleep(5)

            new_date = extract_renewal_date(page)
            print(f"📅 续期后到期时间为: 【{new_date or '未知'}】")

            if old_date and new_date:
                if old_date != new_date:
                    print(f"🎉 续期成功！到期时间已从 {old_date} 更新至 {new_date}")
                else:
                    print(f"⚠️ 续期已点击，但时间仍为 {new_date}（可能是后台有延迟或限制），请查看最终截图。")
            else:
                print("✅ 续期动作已执行完成。")

        elif not_yet_btn.count() > 0:
            print(f"ℹ️ 当前服务尚未到达可续期时间，状态提示: 【{not_yet_btn.first.inner_text()}】")
        else:
            print("ℹ️ 未发现可点击的续期按钮，保持当前状态。")

        # 截图留存
        page.screenshot(path="result.png", full_page=True)
        print("📸 最终截图已保存至 result.png")
        browser.close()

if __name__ == "__main__":
    run()
