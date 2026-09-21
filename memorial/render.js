const { chromium } = require('playwright');
const path = require('path');
const variants = ['deep', 'soft'];
(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--no-sandbox', '--force-color-profile=srgb', '--font-render-hinting=none']
  });
  for (const v of variants) {
    const html = 'file://' + path.resolve(`build/memorial_${v}.html`);
    const page = await browser.newPage({ viewport: { width: 1080, height: 1620 }, deviceScaleFactor: 2 });
    await page.goto(html, { waitUntil: 'networkidle' });
    await page.evaluate(async () => { await document.fonts.ready; });
    await page.waitForTimeout(400);
    const el = await page.$('#f');
    await el.screenshot({ path: `build/memorial_${v}.png` });
    await page.close();
    console.log(`rendered build/memorial_${v}.png`);
  }
  await browser.close();
})();
