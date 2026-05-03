// @ts-check
import { test, expect } from '@playwright/test';

const QA_ADMIN_USERNAME = process.env.QA_ADMIN_USERNAME || 'admin';
const QA_ADMIN_PASSWORD = process.env.QA_ADMIN_PASSWORD;

function requireAdminCredentials() {
  test.skip(!QA_ADMIN_PASSWORD, 'Set QA_ADMIN_PASSWORD to run authenticated admin e2e checks.');
}

async function loginAsAdmin(page) {
  requireAdminCredentials();
  await page.goto('/login');
  await page.fill('input[type="text"]', QA_ADMIN_USERNAME);
  await page.fill('input[type="password"]', QA_ADMIN_PASSWORD);
  await page.click('button[type="submit"]');
}

test.describe('Базовая функциональность клиники', () => {
  test('главная страница загружается', async ({ page }) => {
    await page.goto('/');
    
    // Проверяем, что страница загрузилась
    await expect(page).toHaveTitle(/Клиника/);
  });

  test('страница логина доступна', async ({ page }) => {
    await page.goto('/login');
    
    // Проверяем наличие элементов формы логина
    await expect(page.locator('input[type="text"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('можно войти в систему', async ({ page }) => {
    await loginAsAdmin(page);
    
    // Проверяем, что произошел редирект (не остались на странице логина)
    await page.waitForURL('**/dashboard', { timeout: 10000 });
  });

  test('панель администратора доступна после входа', async ({ page }) => {
    await loginAsAdmin(page);
    
    // Ждем загрузки панели
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    
    // Проверяем наличие элементов панели
    await expect(page.locator('text=Панель администратора')).toBeVisible();
  });

  test('навигация работает', async ({ page }) => {
    await loginAsAdmin(page);
    
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    
    // Проверяем навигацию по разделам
    const navItems = ['Пациенты', 'Записи', 'Очередь', 'Отчеты'];
    
    for (const item of navItems) {
      if (await page.locator(`text=${item}`).isVisible()) {
        await page.click(`text=${item}`);
        await page.waitForTimeout(1000); // Ждем загрузки
      }
    }
  });
});
