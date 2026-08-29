import os
import sys
import time
from playwright.sync_api import sync_playwright

COOKIE_STR = os.environ.get("COOKIE")

if not COOKIE_STR:
    print("❌ 错误: 未检测到 COOKIE 环境变量，请在 GitHub Secrets 中配置 COOKIE")
    sys.exit(1)

# 解析 Cookie 字符串为 Playwright 适用的格式
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

        # 注入 Cookie 实现免登录
        context.add_cookies(cookies)
        page = context.new_page()

        print("1. 正在带 Cookie 直接访问服务页面...")
        page.goto("https://fridaydev.fr/services/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(6)  # 等待页面 JS 渲染卡片

        page_text = page.inner_text("body")

        # 检查是否成功登录并进入服务页
        if "Mes services" in page_text or "wabiss" in page_text:
            print("✅ Cookie 验证有效，已成功进入服务管理页面！")
        else:
            print("⚠️ 未能在页面中找到服务信息，可能是 Cookie 失效或已被重定向，请检查生成的截图。")

        # 检查续期按钮状态
        print("2. 正在检查续期状态...")
        renew_btn = page.locator("button:has-text('Renouveler'), a:has-text('Renouveler')")
        not_yet_btn = page.locator("text=/Renouvelable dans \\d+ jour\\(s\\)/i")

        if renew_btn.count() > 0 and renew_btn.first.is_visible():
            print("🎉 检测到可续期按钮，正在执行点击...")
            renew_btn.first.click()
            time.sleep(3)
            
            # 若有二次确认弹窗，尝试点击确认
            confirm_btn = page.locator("button:has-text('Confirmer'), button:has-text('Valider'), button:has-text('Oui')")
            if confirm_btn.count() > 0 and confirm_btn.first.is_visible():
                confirm_btn.first.click()
                time.sleep(2)
            print("✅ 续期操作执行完毕！")
        elif not_yet_btn.count() > 0:
            print(f"ℹ️ 当前服务尚未到达可续期时间，状态提示: {not_yet_btn.first.inner_text()}")
        else:
            print("ℹ️ 未找到续期按钮（可能尚未到期或页面元素发生变动），请查看保存的截图。")

        # 截取最终画面保存
        page.screenshot(path="result.png", full_page=True)
        print("📸 截图已保存至 result.png")
        browser.close()

if __name__ == "__main__":
    run()
