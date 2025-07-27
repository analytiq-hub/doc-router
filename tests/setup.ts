import puppeteer from 'puppeteer';

declare global {
  var browser: puppeteer.Browser;
  var page: puppeteer.Page;
}

beforeAll(async () => {
  global.browser = await puppeteer.launch({
    headless: process.env.HEADLESS !== 'false',
    slowMo: process.env.SLOW_MO ? parseInt(process.env.SLOW_MO) : 0,
    devtools: process.env.DEVTOOLS === 'true',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
});

beforeEach(async () => {
  global.page = await global.browser.newPage();
  await global.page.setViewport({ width: 1280, height: 720 });
});

afterEach(async () => {
  if (global.page) {
    await global.page.close();
  }
});

afterAll(async () => {
  if (global.browser) {
    await global.browser.close();
  }
});