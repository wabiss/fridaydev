import os
import re
import sys
import asyncio
from camoufox.async_api import AsyncCamoufox

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

def extract_dates(text):
    """提取页面所有有效日期"""
    try:
        return re.findall(r"\b\d{2}/\d{2}/\d{4}\b", text)
    except Exception:
        return []

async def trigger_turnstile_box(page):
    """在真实住宅 IP 下轻点一次 Turnstile 复选框"""
    for frame in page.frames:
        if "challenges.cloudflare.com" in frame.url:
            for sel in ["input[type='checkbox']", ".ctp-checkbox-label", "#challenge-stage", "label"]:
                try:
                    target = frame.locator(sel).first
                    if await target.count() > 0 and await target.is_visible():
                        await target.hover()
                        await asyncio.sleep(0.3)
                        await target.click(timeout=1500)
                        print(f"🎯 [住宅网络] 成功触发内部复选框点击: {sel}")
                        return True
                except Exception:
                    pass

    try:
        modal = page.locator("div:has-text('Vérification rapide')").last
        if await modal.is_visible():
            box = await modal.bounding_box()
            if box:
                target_x = box["x"] + (box["width"] * 0.22)
                target_y = box["y"] + (box["height"] * 0.58)
                print(f"🎯 [住宅网络] 物理拟真点击: ({target_x:.1f}, {target_y:.1f})")
                await page.mouse.move(target_x, target_y)
                await asyncio.sleep(0.3)
                await page.mouse.click(target_x, target_y)
                return True
    except Exception:
        pass
    return False

async def run():
    print("🚀 正在通过本地 SOCKS5 住宅代理启动 Camoufox 内核...")
    
    # 修复：移除 geoip=True，保持纯净稳定启动
    async with AsyncCamoufox(
        headless=False,
        humanize=True,
        os="windows",
        disable_coop=True,
        i_know_what_im_doing=True,
        proxy={"server": "socks5://127.0.0.1:1080"}
    ) as browser:
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="fr-FR"
        )

        await context.add_cookies(cookies)
        page = await context.new_page()

        renew_success_event = asyncio.Event()

        # 严格监听后端核心续期接口
        async def on_response(res):
            url = res.url.lower()
            if "renew_free_service.php" in url:
                print(f"🌐 [核心接口响应] HTTP {res.status} {res.url}")
                if res.status == 200:
                    print("🎉🎉🎉 后端 renew 接口返回 HTTP 200 成功响应！")
                    renew_success_event.set()

        page.on("response", lambda res: asyncio.create_task(on_response(res)))

        print("1. 正在访问服务管理页面...")
        await page.goto("https://fridaydev.fr/services/", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        page_text = await page.inner_text("body")
        if "Mes services" not in page_text and "wabiss" not in page_text:
            print("❌ Cookie 已失效，请更新 Secrets 中的 COOKIE")
            await page.screenshot(path="result.png", full_page=True)
            sys.exit(1)

        print("✅ 成功进入服务后台！")

        # 自动同意 Cookie 提示
        try:
            accept_btn = page.locator("button:has-text('Accepter')")
            if await accept_btn.count() > 0 and await accept_btn.first.is_visible():
                await accept_btn.click()
                await asyncio.sleep(1)
        except Exception:
            pass

        old_dates = extract_dates(page_text)
        print(f"📅 点击前页面日期: {old_dates}")

        # 锁定续期按钮
        renew_btn = page.locator("button, a").filter(
            has_text=re.compile(r"Renouveler\s+gratuitement", re.I)
        )

        if await renew_btn.count() > 0 and await renew_btn.first.is_visible():
            target_text = (await renew_btn.first.inner_text()).strip()
            print(f"🎉 正在点击续期按钮: 【{target_text}】...")
            await renew_btn.first.click()
            await asyncio.sleep(4)

            await page.screenshot(path="after_click.png", full_page=True)
            print("🛡️ 住宅 IP 环境下，Turnstile 正在验证中...")

            # 轮询等待验证完成
            for i in range(12):
                if renew_success_event.is_set():
                    print("🎉 接口响应成功，提前退出验证循环！")
                    break

                print(f"⏳ 等待并辅助验证 ({i+1}/12)...")
                await trigger_turnstile_box(page)
                await asyncio.sleep(3)

                modal = page.locator("div:has-text('Vérification rapide')")
                if await modal.count() == 0 or not await modal.first.is_visible():
                    print("🎉🎉 Cloudflare 验证通过，弹窗已自动关闭！")
                    break

            await page.screenshot(path="cf_clicked.png", full_page=True)

            try:
                await asyncio.wait_for(renew_success_event.wait(), timeout=6)
            except asyncio.TimeoutError:
                pass

            # 重新加载服务列表页验证最终状态
            print("2. 正在刷新服务列表页验证最新状态...")
            await page.goto("https://fridaydev.fr/services/", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(6)

            new_text = await page.inner_text("body")
            new_dates = extract_dates(new_text)
            print(f"📅 刷新后最新日期: {new_dates}")

            if "Renouvelable dans" in new_text:
                print("🎉🎉🎉 续期大成功！服务已成功顺延并重新进入倒计时！")
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
