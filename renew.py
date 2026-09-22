import os
import re
import sys
import time
from camoufox.sync_api import Camoufox

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
    """物理坐标精准点击 Cloudflare Turnstile 复选框"""
    # 策略 1: 扫描可见 iframe
    for frame in page.locator("iframe").all():
        try:
            if frame.is_visible():
                box = frame.bounding_box()
                if box and box["width"] > 80 and box["height"] > 25:
                    click_x = box["x"] + 30
                    click_y = box["y"] + (box["height"] / 2)
                    print(f"🎯 [定位成功] 验证框坐标: ({click_x:.1f}, {click_y:.1f})，模拟真人点击...")
                    page.mouse.move(click_x - 30, click_y - 20)
                    time.sleep(0.3)
                    page.mouse.click(click_x, click_y)
                    return True
        except Exception:
            pass

    # 策略 2: 弹窗中心区域点击
    modal = page.locator("div:has-text('Vérification rapide')").last
    try:
        if modal.is_visible():
            box = modal.bounding_box()
            if box:
                click_x = box["x"] + (box["width"] * 0.35)
                click_y = box["y"] + (box["height"] * 0.58)
                print(f"🎯 [弹窗兜底] 点击验证区域: ({click_x:.1f}, {click_y:.1f})...")
                page.mouse.click(click_x, click_y)
                return True
    except Exception:
        pass

    return False

def run():
    print("🚀 正在启动 Camoufox 反检测浏览器内核...")
    with Camoufox(
        headless=True,
        humanize=True,
        screen={"width": 1920, "height": 1080}
    ) as browser:
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="fr-FR"
        )

        context.add_cookies(cookies)
        page = context.new_page()

        print("1. 正在访问服务管理页面...")
        page.goto("https://fridaydev.fr/services/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)

        page_text = page.inner_text("body")
        if "Mes services" not in page_text and "wabiss" not in page_text:
            print("❌ Cookie 已失效，请更新 Secrets 中的 COOKIE")
            page.screenshot(path="result.png", full_page=True)
            sys.exit(1)

        print("✅ 成功进入服务管理后台！")

        # 自动同意 Cookie 弹窗
        try:
            accept_btn = page.locator("button:has-text('Accepter')")
            if accept_btn.count() > 0 and accept_btn.first.is_visible():
                accept_btn.first.click()
                time.sleep(1)
        except Exception:
            pass

        old_dates = extract_dates(page)
        print(f"📅 当前到期时间: {old_dates}")

        # 定位续期按钮
        renew_btn = page.locator("button, a").filter(
            has_text=re.compile(r"Renouveler\s+gratuitement", re.I)
        )

        if renew_btn.count() > 0 and renew_btn.first.is_visible():
            target_text = renew_btn.first.inner_text().strip()
            print(f"🎉 正在点击续期按钮: 【{target_text}】...")
            renew_btn.first.click()
            time.sleep(3)

            page.screenshot(path="after_click.png", full_page=True)

            print("🛡️ 正在通过 Cloudflare Turnstile 验证...")

            # 轮询点击并等待验证通过
            verified = False
            for i in range(12):
                print(f"⏳ 正在处理人机验证 ({i+1}/12)...")
                click_turnstile_challenge(page)
                time.sleep(3)

                # 检查验证弹窗是否消失
                modal = page.locator("div:has-text('Vérification rapide')")
                if modal.count() == 0 or not modal.first.is_visible():
                    print("🎉🎉 Cloudflare 验证完全通过！弹窗已自动关闭并提交！")
                    verified = True
                    break

            page.screenshot(path="cf_clicked.png", full_page=True)

            if not verified:
                print("⚠️ 验证可能已在后台完成，正在刷新页面检查结果...")

            time.sleep(5)

            # 刷新页面验证最新状态
            print("2. 正在刷新页面验证最新状态...")
            page.reload(wait_until="domcontentloaded")
            time.sleep(5)

            new_dates = extract_dates(page)
            new_page_text = page.inner_text("body")
            print(f"📅 刷新后最新日期: {new_dates}")

            if "Renouvelable dans" in new_page_text:
                print("🎉🎉🎉 续期大成功！服务已成功续期并重新进入倒计时！")
            elif old_dates != new_dates:
                print(f"🎉🎉🎉 续期大成功！到期时间已更新: {old_dates} ➔ {new_dates}")
            else:
                print("ℹ️ 流程执行完毕，请查看生成的截图确认最新状态。")

        else:
            not_yet = page.locator("text=/Renouvelable dans/i")
            if not_yet.count() > 0:
                print(f"🔒【暂不可续期】状态: 【{not_yet.first.inner_text().strip()}】")
            else:
                print("ℹ️ 未发现可点击的续期按钮。")

        page.screenshot(path="result.png", full_page=True)
        print("📸 最终截图已保存至 result.png")

if __name__ == "__main__":
    run()
