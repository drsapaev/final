import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Переходим на страницу логина
    await page.goto('/login');
  });

  test('should display login form', async ({ page }) => {
    // Проверяем наличие формы логина
    await expect(page.locator('form')).toBeVisible();
    await expect(page.locator('input[type="text"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('should show validation errors for empty fields', async ({ page }) => {
    // Пытаемся войти с пустыми полями
    await page.click('button[type="submit"]');
    
    // Проверяем валидацию
    await expect(page.locator('text=Обязательное поле')).toBeVisible();
  });

  test('should show error for invalid credentials', async ({ page }) => {
    // Вводим неверные данные
    await page.fill('input[type="text"]', 'invalid@example.com');
    await page.fill('input[type="password"]', 'wrongpassword');
    await page.click('button[type="submit"]');
    
    // Ждем сообщение об ошибке
    await expect(page.locator('text=Неверный логин или пароль')).toBeVisible({ timeout: 10000 });
  });

  test('should login successfully with valid credentials', async ({ page }) => {
    // Вводим валидные данные (тестовый пользователь)
    await page.fill('input[type="text"]', 'admin@clinic.com');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button[type="submit"]');
    
    // Проверяем редирект на дашборд
    await expect(page).toHaveURL(/\/(dashboard|admin|doctor|registrar)/);
    
    // Проверяем наличие элементов интерфейса
    await expect(page.locator('header')).toBeVisible();
    await expect(page.locator('nav, aside')).toBeVisible(); // Сайдбар
  });

  test('should handle role-based routing', async ({ page }) => {
    // Логинимся как админ
    await page.fill('input[type="text"]', 'admin@clinic.com');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button[type="submit"]');
    
    // Ждем загрузки
    await page.waitForLoadState('networkidle');
    
    // Проверяем доступ к админ функциям
    const adminLinks = page.locator('text=Пользователи, text=Настройки, text=Аудит');
    await expect(adminLinks.first()).toBeVisible({ timeout: 10000 });
  });

  test('should logout successfully', async ({ page }) => {
    // Логинимся
    await page.fill('input[type="text"]', 'admin@clinic.com');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button[type="submit"]');
    
    // Ждем загрузки дашборда
    await page.waitForLoadState('networkidle');
    
    // Ищем кнопку выхода (может быть в меню пользователя)
    const logoutButton = page.locator('button:has-text("Выход"), button:has-text("Выйти"), [data-testid="logout"]');
    
    if (await logoutButton.count() > 0) {
      await logoutButton.first().click();
      
      // Проверяем редирект на логин
      await expect(page).toHaveURL('/login');
    } else {
      console.log('Logout button not found, checking for user menu');
      
      // Пытаемся найти меню пользователя
      const userMenu = page.locator('[data-testid="user-menu"], .user-menu, button:has-text("admin")');
      if (await userMenu.count() > 0) {
        await userMenu.first().click();
        await page.locator('text=Выход, text=Выйти').first().click();
        await expect(page).toHaveURL('/login');
      }
    }
  });

  test('should handle session expiration', async ({ page }) => {
    // Логинимся
    await page.fill('input[type="text"]', 'admin@clinic.com');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button[type="submit"]');
    
    // Ждем загрузки
    await page.waitForLoadState('networkidle');
    
    // Очищаем localStorage (имитация истечения сессии)
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
    
    // Обновляем страницу
    await page.reload();
    
    // Должны быть перенаправлены на логин
    await expect(page).toHaveURL('/login');
  });

  test('should remember user preference (if implemented)', async ({ page }) => {
    // Проверяем чекбокс "Запомнить меня"
    const rememberCheckbox = page.locator('input[type="checkbox"]');
    
    if (await rememberCheckbox.count() > 0) {
      await rememberCheckbox.check();
      
      await page.fill('input[type="text"]', 'admin@clinic.com');
      await page.fill('input[type="password"]', 'admin123');
      await page.click('button[type="submit"]');
      
      // Проверяем что данные сохранились
      await page.goto('/login');
      const savedEmail = await page.locator('input[type="text"]').inputValue();
      expect(savedEmail).toBe('admin@clinic.com');
    }
  });
});
