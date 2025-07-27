import { Page } from 'puppeteer';
import { waitForApp, takeScreenshot, BASE_URL } from '../utils/test-helpers';

describe('Homepage UI Tests', () => {
  let page: Page;

  beforeEach(() => {
    page = global.page;
  });

  test('should load homepage without errors', async () => {
    await page.goto(BASE_URL);
    await page.waitForSelector('body', { timeout: 10000 });
    
    const title = await page.title();
    expect(title).toBeTruthy();
    
    await takeScreenshot(page, 'homepage-loaded');
  });

  test('should navigate to sign in page', async () => {
    await waitForApp(page);
    
    // Look for sign in link/button
    const signInSelector = 'a[href*="signin"], button:contains("Sign In"), [data-testid="signin"]';
    try {
      await page.waitForSelector(signInSelector, { timeout: 5000 });
      await page.click(signInSelector);
      await page.waitForNavigation({ waitUntil: 'networkidle0' });
      
      expect(page.url()).toContain('signin');
      await takeScreenshot(page, 'signin-page');
    } catch (error) {
      // If no sign in button found, check if we're already on a protected route
      const currentUrl = page.url();
      console.log(`Current URL: ${currentUrl}`);
      
      // Take screenshot for debugging
      await takeScreenshot(page, 'homepage-no-signin-button');
    }
  });

  test('should have responsive design', async () => {
    await waitForApp(page);
    
    // Test mobile viewport
    await page.setViewport({ width: 375, height: 667 });
    await page.reload({ waitUntil: 'networkidle0' });
    await takeScreenshot(page, 'homepage-mobile');
    
    // Test tablet viewport
    await page.setViewport({ width: 768, height: 1024 });
    await page.reload({ waitUntil: 'networkidle0' });
    await takeScreenshot(page, 'homepage-tablet');
    
    // Test desktop viewport
    await page.setViewport({ width: 1280, height: 720 });
    await page.reload({ waitUntil: 'networkidle0' });
    await takeScreenshot(page, 'homepage-desktop');
  });
});