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
    """提取页面所有有效日期"""
    try:
        text = page.inner_text("body")
        return re.findall(r"\b\d{2}/\d{2}/\d{4}\b", text)
    except Exception:
        return []

def click_turnstile_box(page):
    """通过物理屏幕坐标精准点击 Cloudflare Turnstile 复选框"""
    try:
        iframes = page.locator("iframe[src*='challenges.cloudflare.com'], iframe[src*='turnstile'], iframe[title*='Cloudflare']").all()
        for frame in iframes:
            if frame.is_visible():
                box = frame.bounding_box()
                if box:
                    # 复选框位于 iframe 左侧 28-32px 位置，垂直居中
                    click_x = box["x"] + 28
                    click_y = box["y"] + box["height"] / 2
                    print(f"🎯 定位到 Cloudflare 验证框坐标: ({click_x:.1f}, {click_y:.1f})，正在模拟真实鼠标点击...")
                    
                    page.mouse.move(click_x - 40, click_y - 20)
                    time.sleep(0.3)
                    page.mouse.move(click_x, click_y)
                    time.sleep(0.2)
                    page.mouse.click(click_x, click_y)
                    return True
    except Exception as e:
        print(f"⚠️ 模拟点击异常: {e}")
    return False

def run():
    with sync_playwright() as p:
        print("🚀 启动反检测浏览器...")
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

        # 原生注入完整的 anti-detect 特征伪装
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['fr-FR', 'fr', 'en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
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

        # 自动关闭底部 Cookie 提示条
        try:
            accept_btn = page.locator("button:has-text('Accepter')")
            if accept_btn.count() > 0 and accept_btn.first.is_visible():
                accept_btn.first.click()
                time.sleep(1)
        except Exception:
            pass

        old_dates = extract_dates(page)
        print(f"📅 点击前页面日期: {old_dates}")

        # 锁定续期按钮
        renew_btn = page.locator("button, a").filter(
            has_text=re.compile(r"Renouveler\s+gratuitement", re.I)
        )

        if renew_btn.count() > 0 and renew_btn.first.is_visible():
            target_text = renew_btn.first.inner_text().strip()
            print(f"🎉 正在点击续期按钮: 【{target_text}】...")
            renew_btn.first.click()
            time.sleep(3)

            page.screenshot(path="after_click.png", full_page=True)

            print("🛡️ 正在攻克 Cloudflare Turnstile 人机验证...")

            # 循环等待并触发坐标点击
            verified = False
            for i in range(12):
                print(f"⏳ 正在处理验证 ({i+1}/12)...")
                
                # 点击复选框
                click_turnstile_box(page)
                time.sleep(3)

                # 检查验证弹窗是否消失
                modal = page.locator("text='Vérification rapide'")
                if modal.count() == 0 or not modal.first.is_visible():
                    print("🎉🎉 Cloudflare 验证通过，续期请求已自动提交！")
                    verified = True
                    break

            page.screenshot(path="cf_clicked.png", full_page=True)

            if not verified:
                print("⚠️ 验证超时或在后台处理中，正在刷新检查...")

            time.sleep(5)

            # 刷新页面验证最新状态
            print("2. 正在刷新页面验证最新状态...")
            page.reload(wait_until="domcontentloaded")
            time.sleep(5)

            new_dates = extract_dates(page)
            new_page_text = page.inner_text("body")
            print(f"📅 刷新后页面日期: {new_dates}")

            if "Renouvelable dans" in new_page_text:
                print("🎉🎉🎉 续期大成功！已更新并重新进入倒计时！")
            elif old_dates != new_dates:
                print(f"🎉🎉🎉 续期成功！到期时间已更新: {old_dates} ➔ {new_dates}")
            else:
                print("ℹ️ 流程执行完毕，请查看生成的截图确认具体状态。")

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
