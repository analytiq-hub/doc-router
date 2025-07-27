import { Page } from 'puppeteer';

export const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
export const API_URL = process.env.API_URL || 'http://localhost:8000';

export async function waitForApp(page: Page) {
  await page.goto(BASE_URL);
  await page.waitForSelector('body', { timeout: 10000 });
}

export async function login(page: Page, email: string = 'test@example.com', password: string = 'testpassword') {
  await page.goto(`${BASE_URL}/auth/signin`);
  await page.waitForSelector('input[type="email"]');
  
  await page.type('input[type="email"]', email);
  await page.type('input[type="password"]', password);
  
  await page.click('button[type="submit"]');
  await page.waitForNavigation({ waitUntil: 'networkidle0' });
}

export async function takeScreenshot(page: Page, name: string) {
  if (process.env.SCREENSHOTS === 'true') {
    await page.screenshot({
      path: `tests/screenshots/${name}-${Date.now()}.png`,
      fullPage: true
    });
  }
}

export async function waitForSelector(page: Page, selector: string, timeout: number = 5000) {
  return page.waitForSelector(selector, { timeout });
}

export async function isElementVisible(page: Page, selector: string): Promise<boolean> {
  try {
    const element = await page.$(selector);
    if (!element) return false;
    
    const isVisible = await element.isIntersectingViewport();
    return isVisible;
  } catch {
    return false;
  }
}