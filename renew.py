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

def click_turnstile_checkbox(page):
    """全方位穿透并点击 Cloudflare Turnstile 复选框"""
    clicked = False

    # 1. 深度遍历所有 Frame 内部触发
    for frame in page.frames:
        if any(k in frame.url for k in ["challenges.cloudflare", "turnstile", "cloudflare"]):
            try:
                print(f"👉 探测到 Turnstile Frame: {frame.url[:45]}...")
                for sel in ["input[type='checkbox']", ".cb-lb", "#challenge-stage", "body"]:
                    loc = frame.locator(sel)
                    if loc.count() > 0:
                        loc.first.click(timeout=1500)
                        print(f"🎯 [Frame内部点击成功] 命中选择器: {sel}")
                        clicked = True
                        break
            except Exception:
                pass

    # 2. 通过 FrameLocator 穿透点击
    try:
        cf_locator = page.frame_locator("iframe").locator("input[type='checkbox'], .cb-lb, #challenge-stage, label")
        if cf_locator.count() > 0:
            cf_locator.first.click(timeout=1500)
            print("🎯 [FrameLocator 穿透点击成功]")
            clicked = True
    except Exception:
        pass

    # 3. 弹窗绝对坐标物理点击（最稳兜底）
    try:
        modal = page.locator("div:has-text('Vérification rapide')").last
        if modal.is_visible():
            box = modal.bounding_box()
            if box:
                # 弹窗内验证框左侧复选框的大致物理坐标
                target_x = box["x"] + (box["width"] * 0.22)
                target_y = box["y"] + (box["height"] * 0.58)
                print(f"🎯 [物理坐标点击] 弹窗基准坐标: ({target_x:.1f}, {target_y:.1f})")
                page.mouse.move(target_x - 30, target_y - 20)
                time.sleep(0.2)
                page.mouse.click(target_x, target_y)
                clicked = True
    except Exception:
        pass

    return clicked

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

        print("✅ 成功进入服务管理后台！")

        # 自动同意 Cookie 提示
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
            print("🛡️ 正在执行 Cloudflare Turnstile 穿透点击...")

            verified = False
            for i in range(15):
                print(f"⏳ 正在处理验证第 ({i+1}/15) 次尝试...")
                click_turnstile_checkbox(page)
                time.sleep(3)

                # 检查验证弹窗是否已消失（消失代表验证通过）
                modal = page.locator("div:has-text('Vérification rapide')")
                if modal.count() == 0 or not modal.first.is_visible():
                    print("🎉🎉 Cloudflare 验证完全通过！弹窗已自动关闭并提交续期！")
                    verified = True
                    break

            page.screenshot(path="cf_clicked.png", full_page=True)

            if not verified:
                print("⚠️ 验证可能已在后台完成，正在重新加载服务列表...")

            time.sleep(5)

            # 重新加载服务页面验证结果
            print("2. 正在重新加载服务列表页验证结果...")
            page.goto("https://fridaydev.fr/services/", wait_until="domcontentloaded", timeout=60000)
            time.sleep(5)

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
