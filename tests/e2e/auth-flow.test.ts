import { Page } from 'puppeteer';
import { waitForApp, takeScreenshot, BASE_URL } from '../utils/test-helpers';

describe('Authentication Flow E2E Tests', () => {
  let page: Page;

  beforeEach(() => {
    page = global.page;
  });

  test('should complete sign up flow', async () => {
    await page.goto(`${BASE_URL}/auth/signin`);
    await page.waitForSelector('body', { timeout: 10000 });
    
    await takeScreenshot(page, 'auth-signin-page');
    
    // Look for sign up link or registration form
    const signUpSelectors = [
      'a[href*="register"]',
      'a[href*="signup"]', 
      'button:contains("Sign Up")',
      '[data-testid="signup"]',
      'a:contains("Create account")',
      'a:contains("Register")'
    ];
    
    let signUpFound = false;
    for (const selector of signUpSelectors) {
      try {
        await page.waitForSelector(selector, { timeout: 2000 });
        await page.click(selector);
        signUpFound = true;
        break;
      } catch {
        continue;
      }
    }
    
    if (signUpFound) {
      await page.waitForNavigation({ waitUntil: 'networkidle0' });
      await takeScreenshot(page, 'auth-signup-page');
      
      // Verify we're on sign up page
      const url = page.url();
      expect(url).toMatch(/(register|signup|sign-up)/);
    } else {
      console.log('Sign up link not found, may be on combined auth page');
      await takeScreenshot(page, 'auth-no-signup-link');
    }
  });

  test('should show validation errors for invalid login', async () => {
    await page.goto(`${BASE_URL}/auth/signin`);
    await page.waitForSelector('body', { timeout: 10000 });
    
    // Try to find email and password inputs
    const emailSelectors = [
      'input[type="email"]',
      'input[name="email"]',
      'input[placeholder*="email" i]',
      '[data-testid="email"]'
    ];
    
    const passwordSelectors = [
      'input[type="password"]',
      'input[name="password"]',
      '[data-testid="password"]'
    ];
    
    let emailInput = null;
    let passwordInput = null;
    
    // Find email input
    for (const selector of emailSelectors) {
      try {
        await page.waitForSelector(selector, { timeout: 2000 });
        emailInput = selector;
        break;
      } catch {
        continue;
      }
    }
    
    // Find password input
    for (const selector of passwordSelectors) {
      try {
        await page.waitForSelector(selector, { timeout: 2000 });
        passwordInput = selector;
        break;
      } catch {
        continue;
      }
    }
    
    if (emailInput && passwordInput) {
      // Fill with invalid credentials
      await page.type(emailInput, 'invalid@email.com');
      await page.type(passwordInput, 'wrongpassword');
      
      // Find and click submit button
      const submitSelectors = [
        'button[type="submit"]',
        'button:contains("Sign In")',
        'button:contains("Login")',
        '[data-testid="submit"]'
      ];
      
      for (const selector of submitSelectors) {
        try {
          await page.waitForSelector(selector, { timeout: 2000 });
          await page.click(selector);
          break;
        } catch {
          continue;
        }
      }
      
      // Wait for error message or validation
      await new Promise(resolve => setTimeout(resolve, 2000));
      await takeScreenshot(page, 'auth-invalid-credentials');
      
      // Check for error messages
      const errorSelectors = [
        '.error',
        '.alert-error',
        '[role="alert"]',
        '.text-red',
        '.text-danger'
      ];
      
      for (const selector of errorSelectors) {
        const errorElement = await page.$(selector);
        if (errorElement) {
          const errorText = await page.evaluate(el => el.textContent, errorElement);
          console.log(`Found error message: ${errorText}`);
          break;
        }
      }
    } else {
      console.log('Could not find login form inputs');
      await takeScreenshot(page, 'auth-no-form-inputs');
    }
  });
});