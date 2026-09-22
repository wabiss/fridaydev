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

def solve_turnstile_with_solver(page):
    """使用专业 solver 与精准 DOM 注入自动穿透 Cloudflare Turnstile"""
    # 策略 1: 尝试调用专业的 playwright_captcha ClickSolver
    try:
        from playwright_captcha import ClickSolver, CaptchaType, FrameworkType
        print("🤖 启动 playwright_captcha 专业求解引擎...")
        solver = ClickSolver(framework=FrameworkType.CAMOUFOX, page=page)
        solver.solve_captcha(captcha_container=page, captcha_type=CaptchaType.CLOUDFLARE_TURNSTILE)
        print("🎯 专业引擎已执行穿透处理！")
        return True
    except Exception as e:
        print(f"ℹ️ 自适应模式介入 (详情: {e})")

    # 策略 2: 精准穿透 Shadow-DOM 与 Frame 内复选框
    try:
        for f in page.frames:
            if "challenges.cloudflare.com" in f.url:
                print(f"👉 定位到 Cloudflare 交互 Frame: {f.url[:50]}...")
                # 寻找内部真实的 checkbox 容器
                for target_sel in [".ctp-checkbox-label", "input[type='checkbox']", "#challenge-stage", "label"]:
                    elem = f.locator(target_sel).first
                    if elem.count() > 0 and elem.is_visible():
                        print(f"🎯 命中内部元素: {target_sel}，正在模拟真人平滑点击...")
                        elem.hover()
                        time.sleep(0.3)
                        elem.click()
                        return True
    except Exception as err:
        print(f"⚠️ Frame 交互提示: {err}")

    # 策略 3: 弹窗精准坐标轻点
    try:
        modal = page.locator("div:has-text('Vérification rapide')").last
        if modal.is_visible():
            box = modal.bounding_box()
            if box:
                # 命中复选框中心
                target_x = box["x"] + (box["width"] * 0.22)
                target_y = box["y"] + (box["height"] * 0.58)
                print(f"🎯 [备用坐标点击]: ({target_x:.1f}, {target_y:.1f})")
                page.mouse.move(target_x, target_y)
                time.sleep(0.3)
                page.mouse.click(target_x, target_y)
                return True
    except Exception:
        pass

    return False

def run():
    print("🚀 正在虚拟桌面中启动 Camoufox 真实有头浏览器...")
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
            time.sleep(4)

            page.screenshot(path="after_click.png", full_page=True)
            print("🛡️ 正在进行 Cloudflare 人机验证求解...")

            # 轮询验证（使用专业 Solver 处理）
            verified = False
            for i in range(12):
                print(f"⏳ 正在处理人机验证 ({i+1}/12)...")
                solve_turnstile_with_solver(page)
                time.sleep(3)

                # 检查验证弹窗是否已关闭
                modal = page.locator("div:has-text('Vérification rapide')")
                if modal.count() == 0 or not modal.first.is_visible():
                    print("🎉🎉 Cloudflare 验证完全通过！弹窗已自动提交！")
                    verified = True
                    break

            page.screenshot(path="cf_clicked.png", full_page=True)

            if not verified:
                print("⚠️ 正在重新加载页面以确认后台状态...")

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
