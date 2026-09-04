import os
import re
import sys
import time
from playwright.sync_api import sync_playwright

COOKIE_STR = os.environ.get("COOKIE")

if not COOKIE_STR:
    print("❌ 错误: 未在 GitHub Secrets 中设置 COOKIE")
    sys.exit(1)

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
    """提取到期时间 DD/MM/YYYY"""
    try:
        text = page.inner_text("body")
        match = re.search(r"Renouvellement\s*:\s*(\d{2}/\d{2}/\d{4})", text)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None

def run():
    with sync_playwright() as p:
        print("🚀 启动无头浏览器...")
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )

        context.add_cookies(cookies)
        page = context.new_page()

        print("1. 正在访问服务页面...")
        page.goto("https://fridaydev.fr/services/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)

        page_text = page.inner_text("body")
        if "Mes services" not in page_text and "wabiss" not in page_text:
            print("❌ Cookie 已失效，请重新更新 Secrets 中的 COOKIE")
            page.screenshot(path="result.png", full_page=True)
            browser.close()
            sys.exit(1)

        print("✅ Cookie 有效，进入服务列表！")

        current_expiry = extract_renewal_date(page)
        print(f"📅 当前到期时间为: 【{current_expiry or '未知'}】")

        print("2. 正在精确判断续期按钮...")

        # 精确匹配可续期按钮（以 Renouveler 开头，例如 "Renouveler", "Renouveler gratuitement (5 jours)"）
        # 排除倒计时按钮 "Renouvelable dans..."
        renew_btn = page.locator("button:has-text('Renouveler'), a:has-text('Renouveler')").filter(has_not_text="Renouvelable dans")
        not_yet_btn = page.locator("text=/Renouvelable dans \\d+ jour/i")

        if renew_btn.count() > 0 and renew_btn.first.is_visible():
            btn_text = renew_btn.first.inner_text().strip()
            print(f"🎉【检测到可续期按钮】: 【{btn_text}】，正在执行点击续期...")
            renew_btn.first.click()
            time.sleep(4)

            # 确认弹窗处理（排除危险按钮）
            try:
                modal_confirm = page.locator(".modal.show button, .modal.active button, .swal2-confirm, button:has-text('Confirmer'), button:has-text('Valider')").filter(has_not_text="suppression").filter(has_not_text="Résilier")
                if modal_confirm.count() > 0 and modal_confirm.first.is_visible():
                    modal_confirm.first.click(timeout=3000)
                    print("✅ 已点击确认弹窗")
                    time.sleep(3)
            except Exception:
                pass

            # 刷新页面验证
            print("3. 正在刷新页面验证续期结果...")
            page.reload(wait_until="domcontentloaded")
            time.sleep(5)

            new_expiry = extract_renewal_date(page)
            new_page_text = page.inner_text("body")
            
            print(f"📅 续期后到期时间为: 【{new_expiry or '未知'}】")

            if "Actif" in new_page_text:
                print("🎉 服务状态已恢复为: 【Actif (正常运行)】")

            if current_expiry and new_expiry and current_expiry != new_expiry:
                print(f"🎉 续期成功！到期时间已更新: {current_expiry} ➔ {new_expiry}")
            else:
                print("✅ 续期点击完成，请查看最终截图。")

        elif not_yet_btn.count() > 0:
            status_text = not_yet_btn.first.inner_text().strip()
            print(f"🔒【暂不可续期】倒计时提示: 【{status_text}】")
        else:
            print("ℹ️ 未发现续期按钮，当前可能已在最新状态。")

        # 截图留存
        page.screenshot(path="result.png", full_page=True)
        print("📸 最终截图已保存至 result.png")
        browser.close()

if __name__ == "__main__":
    run()
