import asyncio
from playwright.async_api import async_playwright  # 1.56.x 版本对应 141.0.7390.37
from playwright_stealth import Stealth
async def capture_full_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path='/Users/mrpzx/.cache/playwright-chromium-141/chrome-mac/Chromium.app/Contents/MacOS/Chromium',
            args=[
                '--disable-web-security',
                '--ignore-certificate-errors',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-dev-shm-usage',
                '--disable-background-networking',
                '--disable-default-apps',
                '--disable-sync',
                '--disable-blink-features=AutomationControlled',
                '--disable-translate',
                '--mute-audio',
                '--no-first-run',
                '--no-sandbox'
            ]
        )
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 900},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        stealth = Stealth()
        await stealth.apply_stealth_async(page)
        # 打印浏览器信息
        ua = await page.evaluate('() => navigator.userAgent')
        brands = await page.evaluate('() => JSON.stringify(navigator.userAgentData?.brands)')
        print(f'UA: {ua}')
        print(f'Brands: {brands}')
        print('正在访问页面...')
        await page.goto('https://hk.trip.com/flights', wait_until='networkidle', timeout=60000)
        # await page.goto('https://hk.trip.com/flights/showfarefirst?dcity=tyo&acity=sel&ddate=2026-02-01&rdate=2026-02-04&triptype=ow&class=ys&lowpricesource=searchform&quantity=1&searchboxarg=t&nonstoponly=off&locale=zh-HK&curr=BRL', wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(10000)
        print('正在截图...')
        await page.screenshot(path='screenshot.png', full_page=True)
        print('截图已保存至: screenshot.png')
        await browser.close()
        print('完成!')

if __name__ == '__main__':
    asyncio.run(capture_full_page())