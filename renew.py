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

def extract_dates(page):
    """提取页面上的所有日期 (DD/MM/YYYY)"""
    try:
        text = page.inner_text("body")
        dates = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", text)
        return dates
    except Exception:
        return []

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
            print("❌ Cookie 已失效，请更新 Secrets 中的 COOKIE")
            page.screenshot(path="result.png", full_page=True)
            browser.close()
            sys.exit(1)

        print("✅ Cookie 有效，进入服务列表！")

        # 自动点击底部 Cookie 授权按钮（如果有）
        try:
            accept_cookie_btn = page.locator("button:has-text('Accepter')")
            if accept_cookie_btn.count() > 0 and accept_cookie_btn.first.is_visible():
                accept_cookie_btn.first.click()
                print("🍪 已关闭底部 Cookie 提示条")
                time.sleep(1)
        except Exception:
            pass

        old_dates = extract_dates(page)
        print(f"📅 当前页面检测到日期: {old_dates}")

        print("2. 正在精确定位卡片中的续期按钮...")

        # 1. 优先匹配 "Renouveler gratuitement"（免费续期）
        # 2. 其次匹配纯 "Renouveler" 按钮
        # 3. 坚决排除 "À renouveler" (顶部标签) 和 "Renouvelable dans" (倒计时)
        renew_btn = page.locator("button, a").filter(
            has_text=re.compile(r"Renouveler\s+gratuitement|^Renouveler$", re.I)
        ).filter(
            has_not_text="À renouveler"
        ).filter(
            has_not_text="Renouvelable dans"
        )

        not_yet_btn = page.locator("text=/Renouvelable dans \\d+ jour/i")

        if renew_btn.count() > 0 and renew_btn.first.is_visible():
            target_text = renew_btn.first.inner_text().strip()
            print(f"🎉【成功锁定续期按钮】: 【{target_text}】，正在执行点击！")
            
            # 点击续费按钮
            renew_btn.first.click()
            time.sleep(4)

            # 确认弹窗处理（如果有）
            try:
                modal_confirm = page.locator(".modal.show button, .modal.active button, .swal2-confirm, button:has-text('Confirmer'), button:has-text('Valider')").filter(has_not_text="suppression").filter(has_not_text="Résilier")
                if modal_confirm.count() > 0 and modal_confirm.first.is_visible():
                    modal_confirm.first.click(timeout=3000)
                    print("✅ 已点击确认弹窗")
                    time.sleep(3)
            except Exception:
                pass

            # 刷新页面验证结果
            print("3. 正在刷新页面验证结果...")
            page.reload(wait_until="domcontentloaded")
            time.sleep(5)

            new_dates = extract_dates(page)
            new_page_text = page.inner_text("body")
            
            print(f"📅 刷新后页面日期: {new_dates}")

            if "Actif" in new_page_text and "Suspendu" not in new_page_text:
                print("🎉🎉 成功！服务状态已由暂停恢复为 【Actif (正常运行)】！")
            elif "Renouvelable dans" in new_page_text:
                print("🎉🎉 续期成功！按钮已进入下一次续期倒计时状态。")
            else:
                print("✅ 续期流程已完成，请查看最终截图确认。")

        elif not_yet_btn.count() > 0:
            status_text = not_yet_btn.first.inner_text().strip()
            print(f"🔒【暂不可续期】倒计时状态: 【{status_text}】")
        else:
            print("ℹ️ 未发现续期按钮，当前可能已成功续期。")

        page.screenshot(path="result.png", full_page=True)
        print("📸 最终截图已保存至 result.png")
        browser.close()

if __name__ == "__main__":
    run()
