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

def click_turnstile_challenge(page):
    """三重策略：精准点击 Cloudflare Turnstile 复选框"""
    # 策略 1: 扫描页面上所有可见的 iframe
    all_iframes = page.locator("iframe").all()
    for frame in all_iframes:
        try:
            if frame.is_visible():
                box = frame.bounding_box()
                if box and box["width"] > 100 and box["height"] > 30:
                    # 复选框位于 iframe 内部左侧约 30px
                    click_x = box["x"] + 30
                    click_y = box["y"] + (box["height"] / 2)
                    print(f"🎯 [策略1-Iframe] 锁定验证框坐标: ({click_x:.1f}, {click_y:.1f})，正在模拟真实鼠标点击...")
                    page.mouse.move(click_x - 30, click_y - 20)
                    time.sleep(0.2)
                    page.mouse.click(click_x, click_y)
                    return True
        except Exception:
            pass

    # 策略 2: 扫描包含 turnstile/cf- 的验证容器
    cf_containers = page.locator("[class*='turnstile'], [class*='cf-'], [data-sitekey]").all()
    for container in cf_containers:
        try:
            if container.is_visible():
                box = container.bounding_box()
                if box and box["width"] > 100:
                    click_x = box["x"] + 30
                    click_y = box["y"] + (box["height"] / 2)
                    print(f"🎯 [策略2-容器] 锁定验证容器坐标: ({click_x:.1f}, {click_y:.1f})，正在点击...")
                    page.mouse.click(click_x, click_y)
                    return True
        except Exception:
            pass

    # 策略 3: 兜底方案 - 直接定位弹窗几何中心的人机验证区域
    modal = page.locator("div:has-text('Vérification rapide')").last
    try:
        if modal.is_visible():
            box = modal.bounding_box()
            if box:
                # 弹窗内验证框大致位于弹窗水平偏左、垂直居中偏下的位置
                click_x = box["x"] + (box["width"] * 0.35)
                click_y = box["y"] + (box["height"] * 0.58)
                print(f"🎯 [策略3-弹窗定位] 针对弹窗区域点击: ({click_x:.1f}, {click_y:.1f})...")
                page.mouse.click(click_x, click_y)
                return True
    except Exception:
        pass

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

        # 伪装真人浏览器环境
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

            # 轮询点击并等待验证通过
            verified = False
            for i in range(15):
                print(f"⏳ 正在处理验证第 ({i+1}/15) 次尝试...")
                
                # 触发多重精准定位点击
                hit = click_turnstile_challenge(page)
                time.sleep(3)

                # 检查弹窗是否已经成功关闭
                modal = page.locator("div:has-text('Vérification rapide')")
                if modal.count() == 0 or not modal.first.is_visible():
                    print("🎉🎉 Cloudflare 验证通过！弹窗已自动关闭并提交！")
                    verified = True
                    break

            page.screenshot(path="cf_clicked.png", full_page=True)

            if not verified:
                print("⚠️ 验证可能已在后台完成，正在刷新页面检查最新状态...")

            time.sleep(5)

            # 刷新页面验证最新状态
            print("2. 正在刷新页面验证最新状态...")
            page.reload(wait_until="domcontentloaded")
            time.sleep(5)

            new_dates = extract_dates(page)
            new_page_text = page.inner_text("body")
            print(f"📅 刷新后页面日期: {new_dates}")

            if "Renouvelable dans" in new_page_text:
                print("🎉🎉🎉 续期大成功！服务已恢复并进入倒计时！")
            elif old_dates != new_dates:
                print(f"🎉🎉🎉 续期成功！到期时间已从 {old_dates} 更新至 {new_dates}")
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
