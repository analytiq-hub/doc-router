import fs from 'fs';
import puppeteer from 'puppeteer';

declare global {
  var browser: puppeteer.Browser;
  var page: puppeteer.Page;
}

function resolveChromeExecutable(): string | undefined {
  const fromEnv = process.env.PUPPETEER_EXECUTABLE_PATH?.trim();
  if (fromEnv && fs.existsSync(fromEnv)) return fromEnv;

  try {
    const bundled = puppeteer.executablePath();
    if (typeof bundled === 'string' && fs.existsSync(bundled)) return bundled;
  } catch {
    // Puppeteer has no cached build for this platform yet.
  }

  const systemCandidates = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
  ];
  return systemCandidates.find((p) => fs.existsSync(p));
}

beforeAll(async () => {
  const executablePath = resolveChromeExecutable();
  global.browser = await puppeteer.launch({
    ...(executablePath ? { executablePath } : {}),
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