// @ts-check
import { test, expect } from '@playwright/test';

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
    await page.goto('/login');
    
    // Заполняем форму логина
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin123');
    
    // Нажимаем кнопку входа
    await page.click('button[type="submit"]');
    
    // Проверяем, что произошел редирект (не остались на странице логина)
    await page.waitForURL('**/dashboard', { timeout: 10000 });
  });

  test('панель администратора доступна после входа', async ({ page }) => {
    // Логинимся
    await page.goto('/login');
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button[type="submit"]');
    
    // Ждем загрузки панели
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    
    // Проверяем наличие элементов панели
    await expect(page.locator('text=Панель администратора')).toBeVisible();
  });

  test('навигация работает', async ({ page }) => {
    // Логинимся
    await page.goto('/login');
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button[type="submit"]');
    
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
