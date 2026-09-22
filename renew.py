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
        print("🚀 启动无头浏览器...")
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )

        # 自动接受浏览器的原生 confirm/alert 弹窗
        context.on("dialog", lambda dialog: (print(f"🔔 触发原生弹窗: {dialog.message}"), dialog.accept()))

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

        # 定位续期按钮
        renew_btn = page.locator("button, a").filter(
            has_text=re.compile(r"Renouveler\s+gratuitement", re.I)
        )

        if renew_btn.count() > 0 and renew_btn.first.is_visible():
            target_text = renew_btn.first.inner_text().strip()
            print(f"🎉 正在点击续期按钮: 【{target_text}】...")
            
            # 点击续期按钮
            renew_btn.first.click()
            time.sleep(2)

            # 保存点击后的实时截图，查看是否有弹窗弹出
            page.screenshot(path="after_click.png", full_page=True)
            print("📸 已保存点击后的瞬间截图至 after_click.png")

            # 智能检测并点击弹窗中的确认按钮（排除删除相关）
            confirm_selectors = [
                ".modal button:visible",
                "[role='dialog'] button:visible",
                ".swal2-modal button:visible",
                "button:has-text('Confirmer'):visible",
                "button:has-text('Valider'):visible",
                "button:has-text('Oui'):visible",
                "button:has-text('Renouveler'):visible"
            ]

            for sel in confirm_selectors:
                elements = page.locator(sel).all()
                for el in elements:
                    try:
                        el_text = el.inner_text().strip()
                        # 避免误点取消或关闭
                        if el_text and not any(k in el_text.lower() for k in ["annuler", "fermer", "close", "cancel", "supprimer", "suppression", "résilier"]):
                            print(f"👉 检测到确认弹窗/按钮: 【{el_text}】，正在点击确认...")
                            el.click(timeout=3000)
                            time.sleep(3)
                            break
                    except Exception:
                        pass

            # 等待网络请求完成
            time.sleep(5)

            # 刷新页面验证
            print("2. 正在刷新页面验证最新状态...")
            page.reload(wait_until="domcontentloaded")
            time.sleep(5)

            new_dates = extract_dates(page)
            new_page_text = page.inner_text("body")
            print(f"📅 刷新后页面日期: {new_dates}")

            if "Renouvelable dans" in new_page_text:
                print("🎉🎉 续期成功！已进入下一次倒计时状态！")
            elif old_dates != new_dates:
                print(f"🎉🎉 续期成功！到期时间已更新: {old_dates} ➔ {new_dates}")
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
