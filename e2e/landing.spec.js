import { test, expect } from '@playwright/test';

test.describe('Landing Page Global Settings', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should load the main landing page and display all app cards', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'AI Image Workbench' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Style Matcher' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Background Removal' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'AI Batch Studio' })).toBeVisible();
  });

  test('should persist AI provider selection in localStorage', async ({ page }) => {
    // Select Ollama
    const ollamaBtn = page.getByRole('button', { name: 'Ollama (Local)' });
    await ollamaBtn.click();
    
    // Check UI reflects change (button becomes primary)
    await expect(ollamaBtn).toHaveClass(/btn-primary/);
    
    // Verify local storage updated to ollama
    const provider = await page.evaluate(() => localStorage.getItem('ai_provider'));
    expect(provider).toBe('ollama');

    // Make sure Ollama fields are visible
    await expect(page.getByText('Ollama Default Model URL')).toBeVisible();
  });

  test('should persist Benchmark Directory in localStorage', async ({ page }) => {
    const defaultPath = '/Users/Test/Directory';
    
    const inputLocator = page.getByPlaceholder('/Users/Amey/Desktop/MyBestPhotos');
    await inputLocator.fill(defaultPath);
    
    // Verify it saved accurately to local storage
    const pathValue = await page.evaluate(() => localStorage.getItem('benchmark_folder'));
    expect(pathValue).toBe(defaultPath);
  });
});
