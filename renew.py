import os
import sys
import time
from playwright.sync_api import sync_playwright

USERNAME = os.environ.get("USERNAME")
PASSWORD = os.environ.get("PASSWORD")

if not USERNAME or not PASSWORD:
    print("❌ 错误: 请先在 GitHub Secrets 中设置 USERNAME 和 PASSWORD")
    sys.exit(1)

def run():
    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("1. 正在访问登录页面...")
        page.goto("https://fridaydev.fr/login", wait_until="networkidle", timeout=60000)

        # 填写登录表单（若输入框 selector 不同可在浏览器 F12 确认）
        try:
            page.fill("input[name='email'], input[name='username'], input[type='email'], input[type='text']", USERNAME)
            page.fill("input[name='password'], input[type='password']", PASSWORD)
            # 点击登录提交按钮
            page.click("button[type='submit'], input[type='submit']")
            page.wait_for_load_state("networkidle")
            print("✅ 登录提交完成")
        except Exception as e:
            print(f"⚠️ 登录步骤提示: {e}")

        # 跳转到服务页面
        print("2. 进入服务列表页面...")
        page.goto("https://fridaydev.fr/services/", wait_until="networkidle", timeout=60000)
        time.sleep(3)

        # 查找可续期按钮
        print("3. 检查续期按钮状态...")
        
        # 匹配包含 "Renouveler" 的按钮（当可续期时通常变为 Renouveler）
        renew_btn = page.locator("button:has-text('Renouveler'), a:has-text('Renouveler')")
        
        # 如果当前还没到期，显示的是类似 "Renouvelable dans X jour(s)"
        not_yet_btn = page.locator("text=/Renouvelable dans \\d+ jour\\(s\\)/i")

        if renew_btn.count() > 0 and renew_btn.first.is_visible():
            print("🎉 检测到可续期按钮，正在点击...")
            renew_btn.first.click()
            time.sleep(3)
            # 如果点击后有弹窗确认，可尝试确认
            confirm_btn = page.locator("button:has-text('Confirmer'), button:has-text('Valider')")
            if confirm_btn.count() > 0 and confirm_btn.first.is_visible():
                confirm_btn.first.click()
                time.sleep(2)
            print("✅ 续期操作执行完成！")
        elif not_yet_btn.count() > 0:
            status_text = not_yet_btn.first.inner_text()
            print(f"ℹ️ 当前不可续期，状态提示: {status_text}")
        else:
            print("⚠️ 未找到续期相关按钮，请检查页面结构或截图确认。")

        # 截图保存状态，便于排查
        page.screenshot(path="result.png", full_page=True)
        browser.close()

if __name__ == "__main__":
    run()
