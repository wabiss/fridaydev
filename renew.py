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
    """提取页面上所有有效日期"""
    try:
        text = page.inner_text("body")
        return re.findall(r"\b\d{2}/\d{2}/\d{4}\b", text)
    except Exception:
        return []

def run():
    with sync_playwright() as p:
        print("🚀 启动反检测浏览器...")
        # 配置抗 Cloudflare 检测参数
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--window-size=1920,1080"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="fr-FR"
        )

        # 隐藏 webdriver 特征，避免被 Turnstile 识别为自动化工具
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

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

        print("✅ Cookie 有效，进入后台！")

        # 自动关闭 Cookie 提示条
        try:
            accept_btn = page.locator("button:has-text('Accepter')")
            if accept_btn.count() > 0 and accept_btn.first.is_visible():
                accept_btn.first.click()
                time.sleep(1)
        except Exception:
            pass

        old_dates = extract_dates(page)
        print(f"📅 点击前页面日期: {old_dates}")

        # 精确定位续期按钮
        renew_btn = page.locator("button, a").filter(
            has_text=re.compile(r"Renouveler\s+gratuitement", re.I)
        )

        if renew_btn.count() > 0 and renew_btn.first.is_visible():
            target_text = renew_btn.first.inner_text().strip()
            print(f"🎉 正在点击续期按钮: 【{target_text}】...")
            renew_btn.first.click()
            time.sleep(3)

            # 保存点击后的截图
            page.screenshot(path="after_click.png", full_page=True)

            print("🛡️ 检测到 Cloudflare 人机验证弹窗，正在处理 Turnstile 验证...")

            # 循环 30 秒等待并尝试通过 Cloudflare Turnstile 验证
            verified = False
            for i in range(15):
                print(f"⏳ 正在等待 Cloudflare 验证中 ({i+1}/15)...")
                try:
                    # 尝试寻找 Turnstile iframe 并点击复选框
                    cf_frame = page.frame_locator("iframe[src*='cloudflare.com'], iframe[src*='turnstile']")
                    checkbox = cf_frame.locator("input[type='checkbox'], .cb-lb, #challenge-stage")
                    if checkbox.count() > 0 and checkbox.first.is_visible():
                        print("👉 尝试点击 Turnstile 验证框...")
                        checkbox.first.click()
                except Exception:
                    pass

                time.sleep(2)

                # 检查弹窗是否已经成功关闭（说明验证通过并提交了）
                modal = page.locator("text='Vérification rapide'")
                if modal.count() == 0 or not modal.first.is_visible():
                    print("🎉 Cloudflare 验证通过，弹窗已自动关闭并提交！")
                    verified = True
                    break

            if not verified:
                print("⚠️ 验证耗时较长，尝试继续刷新验证状态...")

            time.sleep(4)

            # 刷新页面验证最新状态
            print("2. 正在刷新页面验证续期结果...")
            page.reload(wait_until="domcontentloaded")
            time.sleep(5)

            new_dates = extract_dates(page)
            new_page_text = page.inner_text("body")
            print(f"📅 刷新后页面日期: {new_dates}")

            if "Renouvelable dans" in new_page_text:
                print("🎉🎉🎉 续期成功！已进入下一次续期倒计时！")
            elif old_dates != new_dates:
                print(f"🎉🎉🎉 续期成功！到期时间已更新: {old_dates} ➔ {new_dates}")
            else:
                print("ℹ️ 页面已刷新，请查看最终截图 result.png 确认最新状态。")

        else:
            not_yet = page.locator("text=/Renouvelable dans/i")
            if not_yet.count() > 0:
                print(f"🔒【暂不可续期】状态: 【{not_yet.first.inner_text().strip()}】")
            else:
                print("ℹ️ 未发现可点击的续期按钮。")

        page.screenshot(path="result.png", full_page=True)
        print("📸 最终截图已保存至 result.png")
        browser.close()

if __name__ == "__main__":
    run()
