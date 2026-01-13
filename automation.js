const { chromium } = require('playwright-extra');
const stealth = require('puppeteer-extra-plugin-stealth');

// 添加 stealth 插件
chromium.use(stealth());

async function captureFullPage() {
  const browser = await chromium.launch({
    headless: false,
    executablePath: '/Users/mrpzx/.cache/playwright-chromium-141/chrome-mac/Chromium.app/Contents/MacOS/Chromium',
    args: [
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
  });

  try {
    const context = await browser.newContext({
      viewport: { width: 1280, height: 900 },
    //   userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    });

    const page = await context.newPage();

    console.log('正在访问页面...');

    // 访问目标页面
    await page.goto('https://hk.trip.com/flights', {
      waitUntil: 'networkidle',
      timeout: 60000
    });
    // await page.goto('https://hk.trip.com/flights/showfarefirst?dcity=tyo&acity=sel&ddate=2026-02-01&rdate=2026-02-04&triptype=ow&class=ys&lowpricesource=searchform&quantity=1&searchboxarg=t&nonstoponly=off&locale=zh-HK&curr=BRL', {
    //   waitUntil: 'networkidle',
    //   timeout: 60000
    // });

    // 等待页面加载完成
    await page.waitForTimeout(3000);

    console.log('正在截图...');

    // 全屏截图
    const screenshotPath = 'screenshot.png';
    await page.screenshot({
      path: screenshotPath,
      fullPage: true
    });

    console.log(`截图已保存至: ${screenshotPath}`);

    return screenshotPath;
  } catch (error) {
    console.error('发生错误:', error.message);
    throw error;
  } finally {
    // await browser.close();
  }
}

// 执行
captureFullPage()
  .then((path) => {
    console.log('完成!');
    // process.exit(0);
  })
  .catch((err) => {
    console.error('失败:', err);
    process.exit(1);
  });
