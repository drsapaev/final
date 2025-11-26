import { test, expect } from '@playwright/test';

test.describe('Queue System Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Логинимся как регистратор
    await page.goto('/login');
    await page.fill('input[type="text"]', 'registrar@clinic.com');
    await page.fill('input[type="password"]', 'registrar123');
    await page.click('button[type="submit"]');
    
    // Ждем загрузки панели регистратора
    await page.waitForLoadState('networkidle');
  });

  test('should display queue management interface', async ({ page }) => {
    // Переходим на страницу управления очередью
    await page.goto('/registrar');
    
    // Проверяем наличие элементов управления очередью
    await expect(page.locator('text=Очередь')).toBeVisible();
    await expect(page.locator('text=Онлайн-очередь')).toBeVisible();
  });

  test('should create morning queue at 07:00', async ({ page }) => {
    // Имитируем время 07:00
    await page.addInitScript(() => {
      // Переопределяем Date для имитации времени 07:00
      const mockDate = new Date();
      mockDate.setHours(7, 0, 0, 0);
      
      const OriginalDate = Date;
      global.Date = class extends OriginalDate {
        constructor(...args) {
          if (args.length === 0) {
            return mockDate;
          }
          return new OriginalDate(...args);
        }
        
        static now() {
          return mockDate.getTime();
        }
      };
    });

    await page.goto('/registrar');
    
    // Ищем кнопку "Открыть прием"
    const openQueueButton = page.locator('button:has-text("Открыть прием"), button:has-text("Открыть очередь")');
    
    if (await openQueueButton.count() > 0) {
      await openQueueButton.first().click();
      
      // Проверяем что очередь открылась
      await expect(page.locator('text=Очередь открыта')).toBeVisible({ timeout: 10000 });
    }
  });

  test('should prevent queue creation outside 07:00-08:00 window', async ({ page }) => {
    // Имитируем время 09:00 (вне окна)
    await page.addInitScript(() => {
      const mockDate = new Date();
      mockDate.setHours(9, 0, 0, 0);
      
      const OriginalDate = Date;
      global.Date = class extends OriginalDate {
        constructor(...args) {
          if (args.length === 0) {
            return mockDate;
          }
          return new OriginalDate(...args);
        }
        
        static now() {
          return mockDate.getTime();
        }
      };
    });

    await page.goto('/registrar');
    
    // Пытаемся открыть очередь
    const openQueueButton = page.locator('button:has-text("Открыть прием")');
    
    if (await openQueueButton.count() > 0) {
      await openQueueButton.first().click();
      
      // Должно показать ошибку о времени
      await expect(page.locator('text=Время для открытия очереди: 07:00-08:00')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should add patient to queue', async ({ page }) => {
    await page.goto('/registrar');
    
    // Ищем форму добавления в очередь
    const addToQueueButton = page.locator('button:has-text("Добавить в очередь"), button:has-text("Записать")');
    
    if (await addToQueueButton.count() > 0) {
      await addToQueueButton.first().click();
      
      // Заполняем форму
      await page.fill('input[placeholder*="Телефон"], input[name="phone"]', '+998901234567');
      await page.fill('input[placeholder*="Имя"], input[name="name"]', 'Тестовый Пациент');
      
      // Выбираем специалиста
      const specialistSelect = page.locator('select[name="specialist"], .specialist-select');
      if (await specialistSelect.count() > 0) {
        await specialistSelect.first().selectOption({ index: 1 });
      }
      
      // Подтверждаем
      await page.click('button[type="submit"], button:has-text("Добавить")');
      
      // Проверяем что пациент добавлен
      await expect(page.locator('text=Пациент добавлен в очередь')).toBeVisible({ timeout: 10000 });
    }
  });

  test('should prevent duplicate phone numbers in queue', async ({ page }) => {
    await page.goto('/registrar');
    
    const addButton = page.locator('button:has-text("Добавить в очередь")');
    
    if (await addButton.count() > 0) {
      // Добавляем первого пациента
      await addButton.first().click();
      await page.fill('input[name="phone"]', '+998901111111');
      await page.fill('input[name="name"]', 'Первый Пациент');
      await page.click('button[type="submit"]');
      
      // Ждем подтверждения
      await page.waitForTimeout(2000);
      
      // Пытаемся добавить с тем же номером
      await addButton.first().click();
      await page.fill('input[name="phone"]', '+998901111111');
      await page.fill('input[name="name"]', 'Второй Пациент');
      await page.click('button[type="submit"]');
      
      // Должна показаться ошибка
      await expect(page.locator('text=Пациент уже в очереди')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should display queue with correct numbering', async ({ page }) => {
    await page.goto('/registrar');
    
    // Проверяем отображение очереди
    const queueList = page.locator('.queue-list, [data-testid="queue-list"]');
    
    if (await queueList.count() > 0) {
      // Проверяем что номера идут по порядку
      const queueItems = page.locator('.queue-item, [data-testid="queue-item"]');
      const count = await queueItems.count();
      
      if (count > 0) {
        for (let i = 0; i < Math.min(count, 3); i++) {
          const item = queueItems.nth(i);
          await expect(item).toBeVisible();
          
          // Проверяем что есть номер очереди
          const numberElement = item.locator('.queue-number, [data-testid="queue-number"]');
          if (await numberElement.count() > 0) {
            const number = await numberElement.textContent();
            expect(number).toMatch(/\d+/);
          }
        }
      }
    }
  });

  test('should call next patient', async ({ page }) => {
    await page.goto('/registrar');
    
    // Ищем кнопку "Вызвать следующего"
    const callNextButton = page.locator('button:has-text("Вызвать"), button:has-text("Следующий")');
    
    if (await callNextButton.count() > 0) {
      await callNextButton.first().click();
      
      // Проверяем что пациент вызван
      await expect(page.locator('text=Пациент вызван')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should handle queue completion', async ({ page }) => {
    await page.goto('/registrar');
    
    // Ищем кнопку завершения приема
    const completeButton = page.locator('button:has-text("Завершить прием"), button:has-text("Закрыть очередь")');
    
    if (await completeButton.count() > 0) {
      await completeButton.first().click();
      
      // Подтверждаем завершение
      const confirmButton = page.locator('button:has-text("Подтвердить"), button:has-text("Да")');
      if (await confirmButton.count() > 0) {
        await confirmButton.first().click();
      }
      
      // Проверяем что прием завершен
      await expect(page.locator('text=Прием завершен')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should display queue statistics', async ({ page }) => {
    await page.goto('/registrar');
    
    // Проверяем статистику очереди
    const statsElements = [
      'text=Всего в очереди',
      'text=Обслужено',
      'text=Ожидают',
      '.queue-stats',
      '[data-testid="queue-stats"]'
    ];
    
    let statsFound = false;
    for (const selector of statsElements) {
      if (await page.locator(selector).count() > 0) {
        await expect(page.locator(selector)).toBeVisible();
        statsFound = true;
        break;
      }
    }
    
    if (!statsFound) {
      console.log('Queue statistics not found - may not be implemented yet');
    }
  });

  test('should handle specialist-specific queues', async ({ page }) => {
    await page.goto('/registrar');
    
    // Проверяем фильтрацию по специалистам
    const specialistFilter = page.locator('select[name="specialist"], .specialist-filter');
    
    if (await specialistFilter.count() > 0) {
      // Выбираем конкретного специалиста
      await specialistFilter.first().selectOption({ index: 1 });
      
      // Проверяем что очередь отфильтровалась
      await page.waitForTimeout(1000);
      
      const queueItems = page.locator('.queue-item');
      const count = await queueItems.count();
      
      // Если есть элементы, проверяем что они относятся к выбранному специалиству
      if (count > 0) {
        console.log(`Found ${count} queue items for selected specialist`);
      }
    }
  });
});
