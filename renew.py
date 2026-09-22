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

def gentle_click_checkbox(page):
    """像真人一样只精准点击一次 Turnstile 复选框"""
    try:
        modal = page.locator("div:has-text('Vérification rapide')").last
        if modal.is_visible():
            box = modal.bounding_box()
            if box:
                # 弹窗内复选框的精准坐标
                target_x = box["x"] + (box["width"] * 0.23)
                target_y = box["y"] + (box["height"] * 0.58)
                print(f"🎯 模拟真人鼠标平滑移动至验证框: ({target_x:.1f}, {target_y:.1f})...")
                
                # 模拟真实轨迹移动与停留
                page.mouse.move(target_x - 60, target_y - 40)
                time.sleep(0.4)
                page.mouse.move(target_x, target_y)
                time.sleep(0.6)
                # 仅点击一次
                page.mouse.click(target_x, target_y)
                print("👉 已轻点验证框一次，静候 Cloudflare 响应...")
                return True
    except Exception as e:
        print(f"⚠️ 拟真点击提示: {e}")
    return False

def run():
    print("🚀 正在虚拟桌面中启动 Camoufox 真实有头浏览器...")
    with Camoufox(
        headless=False,
        humanize=True,
        os="windows"
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

        print("✅ 成功进入服务后台！")

        # 自动关闭 Cookie 提示
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

            print("🛡️ 弹窗出现，先静止等待 5 秒观察 Turnstile 自动校验...")
            time.sleep(5)
            page.screenshot(path="after_click.png", full_page=True)

            modal = page.locator("div:has-text('Vérification rapide')")
            
            # 如果 5 秒后弹窗还在，执行一次真人模式点击
            if modal.count() > 0 and modal.first.is_visible():
                print("⏳ 尝试进行一次真人模式勾选...")
                gentle_click_checkbox(page)
                
                # 留出 10 秒充足时间等待验证与提交响应
                print("⏳ 等待 Cloudflare 生成 Token 并提交...")
                time.sleep(10)

            page.screenshot(path="cf_clicked.png", full_page=True)

            # 重新刷新服务页面查看最新状态
            print("2. 正在重新加载服务列表页验证结果...")
            page.goto("https://fridaydev.fr/services/", wait_until="domcontentloaded", timeout=60000)
            time.sleep(6)

            new_dates = extract_dates(page)
            new_page_text = page.inner_text("body")
            print(f"📅 刷新后最新日期: {new_dates}")

            if "Renouvelable dans" in new_page_text:
                print("🎉🎉🎉 续期大成功！服务已成功续期并重新进入倒计时！")
            elif old_dates != new_dates:
                print(f"🎉🎉🎉 续期大成功！到期时间已更新: {old_dates} ➔ {new_dates}")
            else:
                print("ℹ️ 流程执行完毕，请查看最终截图 result.png 确认最新状态。")

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
