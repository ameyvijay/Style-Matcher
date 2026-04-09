import { test, expect } from '@playwright/test';

test.describe('Router Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should navigate to Style Matcher and render successfully', async ({ page }) => {
    await page.getByRole('heading', { name: 'Style Matcher' }).click();
    // Validate we routed to /style-match
    await expect(page).toHaveURL(/\/style-match/);
    // Note: Depends on what is inside /style-match, but ensuring it didn't crash
    await expect(page.locator('body')).toBeVisible();
  });

  test('should navigate to Background Removal and render successfully', async ({ page }) => {
    await page.getByRole('heading', { name: 'Background Removal' }).click();
    // Validate we routed to /remove-bg
    await expect(page).toHaveURL(/\/remove-bg/);
    await expect(page.locator('body')).toBeVisible();
  });

  test('should navigate to AI Batch Studio and render successfully', async ({ page }) => {
    await page.getByRole('link', { name: /AI Batch Studio/ }).click();
    // Validate we routed to /batch-studio
    await expect(page).toHaveURL(/\/batch-studio/);
    await expect(page.locator('body')).toBeVisible();
  });
});
