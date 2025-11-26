// @ts-check
import { test, expect } from '@playwright/test';

test.describe('Admin navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    // Try default admin credentials
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button:has-text("Войти")');
    // Graceful: if login fails, navigate directly (CI may have auto-login)
    await page.waitForLoadState('networkidle');
  });

  test('should open admin dashboard', async ({ page }) => {
    await page.goto('/admin');
    await expect(page).toHaveURL(/\/admin\/?$/);
    await expect(page.getByText('Панель администратора')).toBeVisible();
  });

  test('should navigate to users subpage', async ({ page }) => {
    await page.goto('/admin');
    await page.click('button:has-text("Пользователи")');
    await expect(page).toHaveURL(/\/admin\/users$/);
    await expect(page.getByRole('table', { name: 'Таблица пользователей' })).toBeVisible();
  });

  test('should navigate to analytics subpage', async ({ page }) => {
    await page.goto('/admin');
    await page.click('button:has-text("Аналитика")');
    await expect(page).toHaveURL(/\/admin\/analytics$/);
    await expect(page.getByRole('group', { name: 'Фильтры аналитики' })).toBeVisible();
  });
});


