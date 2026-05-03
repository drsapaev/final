// @ts-check
import { test, expect } from '@playwright/test';

const QA_ADMIN_USERNAME = process.env.QA_ADMIN_USERNAME || 'admin';
const QA_ADMIN_PASSWORD = process.env.QA_ADMIN_PASSWORD;

function requireAdminCredentials() {
  test.skip(!QA_ADMIN_PASSWORD, 'Set QA_ADMIN_PASSWORD to run authenticated admin navigation e2e checks.');
}

test.describe('Admin navigation', () => {
  test.beforeEach(async ({ page }) => {
    requireAdminCredentials();
    await page.goto('/login');
    await page.fill('input[name="username"]', QA_ADMIN_USERNAME);
    await page.fill('input[name="password"]', QA_ADMIN_PASSWORD);
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


