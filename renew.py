import os
import re
import sys
import asyncio
from camoufox.async_api import AsyncCamoufox
from playwright_captcha import ClickSolver, CaptchaType, FrameworkType

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

async def extract_dates(page):
    """提取页面所有有效日期"""
    try:
        text = await page.inner_text("body")
        return re.findall(r"\b\d{2}/\d{2}/\d{4}\b", text)
    except Exception:
        return []

async def run():
    print("🚀 正在以 Async 异步模式启动 Camoufox 反检测内核...")
    async with AsyncCamoufox(
        headless=False,
        humanize=True,
        os="windows",
        disable_coop=True,
        i_know_what_im_doing=True
    ) as browser:
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="fr-FR"
        )

        await context.add_cookies(cookies)
        page = await context.new_page()

        print("1. 正在访问服务管理页面...")
        await page.goto("https://fridaydev.fr/services/", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        page_text = await page.inner_text("body")
        if "Mes services" not in page_text and "wabiss" not in page_text:
            print("❌ Cookie 已失效，请更新 Secrets 中的 COOKIE")
            await page.screenshot(path="result.png", full_page=True)
            sys.exit(1)

        print("✅ 成功进入服务后台！")

        # 自动关闭 Cookie 提示条
        try:
            accept_btn = page.locator("button:has-text('Accepter')")
            if await accept_btn.count() > 0 and await accept_btn.first.is_visible():
                await accept_btn.first.click()
                await asyncio.sleep(1)
        except Exception:
            pass

        old_dates = await extract_dates(page)
        print(f"📅 点击前页面日期: {old_dates}")

        # 锁定续期按钮
        renew_btn = page.locator("button, a").filter(
            has_text=re.compile(r"Renouveler\s+gratuitement", re.I)
        )

        if await renew_btn.count() > 0 and await renew_btn.first.is_visible():
            target_text = (await renew_btn.first.inner_text()).strip()
            print(f"🎉 正在点击续期按钮: 【{target_text}】...")
            await renew_btn.first.click()
            await asyncio.sleep(3)

            await page.screenshot(path="after_click.png", full_page=True)
            print("🛡️ 正在调用专业求解引擎处理 Cloudflare Turnstile...")

            # 初始化异步验证码求解器
            solver = ClickSolver(framework=FrameworkType.CAMOUFOX, page=page)

            verified = False
            for i in range(10):
                print(f"⏳ 正在执行人机验证异步求解 ({i+1}/10)...")
                try:
                    # 正确 await 执行求解操作
                    await solver.solve_captcha(captcha_container=page, captcha_type=CaptchaType.CLOUDFLARE_TURNSTILE)
                except Exception as e:
                    print(f"ℹ️ Solver 执行提示: {e}")

                await asyncio.sleep(3)

                # 检查验证弹窗是否已消失（消失表示通过并提交）
                modal = page.locator("div:has-text('Vérification rapide')")
                if await modal.count() == 0 or not await modal.first.is_visible():
                    print("🎉🎉 Cloudflare 验证通过！弹窗已自动关闭并提交！")
                    verified = True
                    break

            await page.screenshot(path="cf_clicked.png", full_page=True)

            if not verified:
                print("⚠️ 正在重新加载页面以确认后台状态...")

            await asyncio.sleep(5)

            # 重新加载服务列表页验证最终状态
            print("2. 正在重新加载服务列表页验证结果...")
            await page.goto("https://fridaydev.fr/services/", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(6)

            new_dates = await extract_dates(page)
            new_page_text = await page.inner_text("body")
            print(f"📅 刷新后最新日期: {new_dates}")

            if "Renouvelable dans" in new_page_text:
                print("🎉🎉🎉 续期大成功！服务已成功顺延并进入下一次倒计时！")
            elif old_dates != new_dates:
                print(f"🎉🎉🎉 续期大成功！到期时间已更新: {old_dates} ➔ {new_dates}")
            else:
                print("ℹ️ 流程执行完毕，请查看生成的 result.png 确认最新状态。")

        else:
            not_yet = page.locator("text=/Renouvelable dans/i")
            if await not_yet.count() > 0:
                print(f"🔒【暂不可续期】状态: 【{(await not_yet.first.inner_text()).strip()}】")
            else:
                print("ℹ️ 未发现可点击的续期按钮。")

        await page.screenshot(path="result.png", full_page=True)
        print("📸 最终截图已保存至 result.png")

if __name__ == "__main__":
    asyncio.run(run())
