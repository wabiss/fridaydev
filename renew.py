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

def solve_turnstile(page):
    """在开启 disable_coop 模式下精准触发 Turnstile 校验"""
    # 策略 1: 直接穿透 iframe 内部点击真正的复选框
    try:
        cf_frame = page.frame_locator("iframe[src*='cloudflare.com'], iframe[src*='turnstile']").first
        checkbox = cf_frame.locator("input[type='checkbox'], .cb-lb, #challenge-stage")
        if checkbox.count() > 0 and checkbox.is_visible():
            print("🎯 [成功穿透] 锁定 Turnstile 内部复选框，正在真实点击...")
            checkbox.click()
            return True
    except Exception as e:
        print(f"⚠️ 穿透点击提示: {e}")

    # 策略 2: 遍历所有 frame
    for frame in page.frames:
        if "challenges.cloudflare" in frame.url:
            try:
                for sel in ["input[type='checkbox']", ".cb-lb", "#challenge-stage"]:
                    loc = frame.locator(sel)
                    if loc.count() > 0 and loc.first.is_visible():
                        print(f"🎯 [Frame内部] 点击元素: {sel}")
                        loc.first.click()
                        return True
            except Exception:
                pass

    # 策略 3: 弹窗物理坐标点击
    modal = page.locator("div:has-text('Vérification rapide')").last
    try:
        if modal.is_visible():
            box = modal.bounding_box()
            if box:
                click_x = box["x"] + (box["width"] * 0.23)
                click_y = box["y"] + (box["height"] * 0.58)
                print(f"🎯 [物理坐标] 点击验证框: ({click_x:.1f}, {click_y:.1f})")
                page.mouse.click(click_x, click_y)
                return True
    except Exception:
        pass

    return False

def run():
    print("🚀 正在启动 Camoufox (已启用 disable_coop 解除跨域隔离)...")
    # 关键参数：disable_coop=True 允许与 Cloudflare iframe 产生真实交互
    with Camoufox(
        headless=False,
        humanize=True,
        os="windows",
        disable_coop=True
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
            print("🛡️ 正在进行 Cloudflare 人机验证...")

            # 轮询验证（只进行轻柔交互，绝不暴力连点）
            verified = False
            for i in range(12):
                print(f"⏳ 正在等待/处理人机验证 ({i+1}/12)...")
                
                # 尝试点击复选框
                solve_turnstile(page)
                time.sleep(3)

                # 检测弹窗是否已消失（消失说明验证通过并提交）
                modal = page.locator("div:has-text('Vérification rapide')")
                if modal.count() == 0 or not modal.first.is_visible():
                    print("🎉🎉 Cloudflare 验证成功通过！弹窗已关闭！")
                    verified = True
                    break

            page.screenshot(path="cf_clicked.png", full_page=True)

            if not verified:
                print("⚠️ 正在重新加载页面以确认后台是否已自动更新...")

            time.sleep(5)

            # 重新加载服务列表页验证最终状态
            print("2. 正在刷新服务列表页验证最新状态...")
            page.goto("https://fridaydev.fr/services/", wait_until="domcontentloaded", timeout=60000)
            time.sleep(6)

            new_dates = extract_dates(page)
            new_page_text = page.inner_text("body")
            print(f"📅 刷新后最新日期: {new_dates}")

            if "Renouvelable dans" in new_page_text:
                print("🎉🎉🎉 续期大成功！服务已成功顺延并进入下一次倒计时！")
            elif old_dates != new_dates:
                print(f"🎉🎉🎉 续期大成功！到期时间已更新: {old_dates} ➔ {new_dates}")
            else:
                print("ℹ️ 流程执行完毕，请查看生成的 result.png 确认最新状态。")

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
