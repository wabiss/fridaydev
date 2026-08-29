import os
import re
import sys
import time
from playwright.sync_api import sync_playwright

COOKIE_STR = os.environ.get("COOKIE")

if not COOKIE_STR:
    print("❌ 错误: 未在 GitHub Secrets 中设置 COOKIE")
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

def extract_renewal_date(page):
    """提取当前到期时间 DD/MM/YYYY"""
    try:
        text = page.inner_text("body")
        match = re.search(r"Renouvellement\s*:\s*(\d{2}/\d{2}/\d{4})", text)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None

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
            print("❌ 未进入后台，Cookie 已失效，请更新 GitHub Secret 中的 COOKIE")
            page.screenshot(path="result.png", full_page=True)
            browser.close()
            sys.exit(1)

        print("✅ Cookie 有效，成功进入服务后台！")

        # 1. 抓取当前到期日期
        current_expiry = extract_renewal_date(page)
        print(f"📅 当前服务到期时间为: 【{current_expiry or '未知'}】")

        # 2. 检查续期状态
        print("2. 正在判断是否满足续期条件...")

        # 查找服务卡片中的所有按钮
        buttons = page.locator(".services-page button, .services-page a, main button, main a").all()
        
        can_renew = False
        renew_target_btn = None
        countdown_text = None

        for btn in buttons:
            try:
                txt = btn.inner_text().strip()
                # 情况A: 处于不可续期的倒计时状态 (例如: "Renouvelable dans 3 jour(s)")
                if "Renouvelable dans" in txt or "dans" in txt:
                    countdown_text = txt
                # 情况B: 真正可续期的按钮 (文字严格为 "Renouveler")
                elif txt == "Renouveler":
                    can_renew = True
                    renew_target_btn = btn
                    break
            except Exception:
                continue

        # 3. 执行判断与操作
        if can_renew and renew_target_btn:
            print("🎉【判定结果：可续期】检测到【Renouveler】按钮，准备执行续期...")
            renew_target_btn.click()
            time.sleep(3)

            # 处理弹窗确认（如果有）
            try:
                modal_confirm = page.locator(".modal.show button, .modal.active button, .swal2-confirm").filter(has_not_text="suppression").filter(has_not_text="Résilier")
                if modal_confirm.count() > 0 and modal_confirm.first.is_visible():
                    modal_confirm.first.click(timeout=3000)
                    time.sleep(3)
            except Exception:
                pass

            # 刷新页面验证时间
            print("3. 正在刷新页面验证是否续期成功...")
            page.reload(wait_until="domcontentloaded")
            time.sleep(5)

            new_expiry = extract_renewal_date(page)
            print(f"📅 续期后到期时间为: 【{new_expiry or '未知'}】")

            if current_expiry and new_expiry and current_expiry != new_expiry:
                print(f"✅ 续期成功！到期时间已从 {current_expiry} 顺延至 {new_expiry}")
            else:
                print(f"⚠️ 续期已点击，但时间暂未变化，请查看截图确认。")

        elif countdown_text:
            print(f"🔒【判定结果：暂不可续期】")
            print(f"⏳ 状态提示: 【{countdown_text}】")
            print(f"ℹ️ 无需执行点击操作，定时任务每天会自动检测，到期开放时会自动续期。")
        else:
            # 备用方案：判断顶部 "0 À renouveler"
            if "0 À renouveler" in page_text:
                print("🔒【判定结果：暂不可续期】顶部显示【0 À renouveler】，当前无需续期。")
            else:
                print("ℹ️ 未检测到续期相关按钮，请查看截图排查。")

        # 保存截图
        page.screenshot(path="result.png", full_page=True)
        print("📸 截图已保存")
        browser.close()

if __name__ == "__main__":
    run()
