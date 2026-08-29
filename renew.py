import os
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
        time.sleep(5)  # 等待数据加载

        page_text = page.inner_text("body")

        if "Mes services" in page_text or "wabiss" in page_text:
            print("✅ Cookie 验证有效，已成功进入服务管理页面！")
        else:
            print("⚠️ 未识别到服务管理页面，可能 Cookie 已过期，请检查截图。")
            page.screenshot(path="result.png", full_page=True)
            browser.close()
            return

        print("2. 正在检查续期按钮状态...")

        # 精确匹配可续期按钮（仅匹配 Renouveler，排除 Résilier/Supprimer 等危险按钮）
        renew_btn = page.locator("button:text-is('Renouveler'), a:text-is('Renouveler'), button:has-text('Renouveler'):not(:has-text('dans'))")
        not_yet_btn = page.locator("text=/Renouvelable dans \\d+ jour\\(s\\)/i")

        if renew_btn.count() > 0 and renew_btn.first.is_visible():
            print("🎉 检测到【Renouveler】续期按钮，正在点击...")
            # 点击续期按钮
            renew_btn.first.click()
            time.sleep(3)

            # 仅在弹出专门的续期确认弹窗且可见时才尝试点击确认，避开删除弹窗
            try:
                modal_confirm = page.locator(".modal.show button, .modal.active button, .swal2-confirm").filter(has_not_text="suppression").filter(has_not_text="Résilier")
                if modal_confirm.count() > 0 and modal_confirm.first.is_visible():
                    modal_confirm.first.click(timeout=3000)
                    print("✅ 已点击弹窗确认")
                    time.sleep(2)
            except Exception:
                pass

            print("✅ 续期操作执行完成！")

        elif not_yet_btn.count() > 0:
            status_text = not_yet_btn.first.inner_text()
            print(f"ℹ️ 当前不可续期，状态提示: 【{status_text}】")
        else:
            print("ℹ️ 未发现续期动作按钮，请查看截图。")

        # 截图保存当前最终状态
        page.screenshot(path="result.png", full_page=True)
        print("📸 最终截图已保存至 result.png")
        browser.close()

if __name__ == "__main__":
    run()
