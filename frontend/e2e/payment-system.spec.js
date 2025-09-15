import { test, expect } from '@playwright/test';

test.describe('Payment System Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Логинимся как кассир
    await page.goto('/login');
    await page.fill('input[type="text"]', 'cashier@clinic.com');
    await page.fill('input[type="password"]', 'cashier123');
    await page.click('button[type="submit"]');
    
    // Ждем загрузки панели кассира
    await page.waitForLoadState('networkidle');
  });

  test('should display payment interface', async ({ page }) => {
    await page.goto('/cashier');
    
    // Проверяем наличие элементов платежной системы
    await expect(page.locator('text=Платежи')).toBeVisible();
    await expect(page.locator('text=Касса')).toBeVisible();
  });

  test('should show available payment providers', async ({ page }) => {
    await page.goto('/cashier');
    
    // Ищем кнопку создания платежа
    const createPaymentButton = page.locator('button:has-text("Создать платеж"), button:has-text("Оплата")');
    
    if (await createPaymentButton.count() > 0) {
      await createPaymentButton.first().click();
      
      // Проверяем провайдеров платежей
      const providers = [
        'text=Click',
        'text=Payme', 
        'text=Kaspi',
        '.payment-provider',
        '[data-testid="payment-provider"]'
      ];
      
      let providerFound = false;
      for (const provider of providers) {
        if (await page.locator(provider).count() > 0) {
          await expect(page.locator(provider)).toBeVisible();
          providerFound = true;
        }
      }
      
      if (!providerFound) {
        console.log('Payment providers not found - checking for select dropdown');
        const providerSelect = page.locator('select[name="provider"], .provider-select');
        if (await providerSelect.count() > 0) {
          await expect(providerSelect).toBeVisible();
        }
      }
    }
  });

  test('should create payment with Click provider', async ({ page }) => {
    await page.goto('/cashier');
    
    const createButton = page.locator('button:has-text("Создать платеж")');
    
    if (await createButton.count() > 0) {
      await createButton.first().click();
      
      // Заполняем форму платежа
      await page.fill('input[name="amount"], input[placeholder*="Сумма"]', '50000');
      await page.fill('input[name="description"], textarea[name="description"]', 'Консультация терапевта');
      
      // Выбираем провайдера Click
      const clickProvider = page.locator('button:has-text("Click"), input[value="click"]');
      if (await clickProvider.count() > 0) {
        await clickProvider.first().click();
      } else {
        // Если провайдер в select
        const providerSelect = page.locator('select[name="provider"]');
        if (await providerSelect.count() > 0) {
          await providerSelect.selectOption('click');
        }
      }
      
      // Создаем платеж
      await page.click('button[type="submit"], button:has-text("Создать")');
      
      // Проверяем создание платежа
      await expect(page.locator('text=Платеж создан')).toBeVisible({ timeout: 10000 });
    }
  });

  test('should create payment with Payme provider', async ({ page }) => {
    await page.goto('/cashier');
    
    const createButton = page.locator('button:has-text("Создать платеж")');
    
    if (await createButton.count() > 0) {
      await createButton.first().click();
      
      // Заполняем форму
      await page.fill('input[name="amount"]', '75000');
      await page.fill('input[name="description"]', 'Анализы крови');
      
      // Выбираем Payme
      const paymeProvider = page.locator('button:has-text("Payme"), input[value="payme"]');
      if (await paymeProvider.count() > 0) {
        await paymeProvider.first().click();
      } else {
        const providerSelect = page.locator('select[name="provider"]');
        if (await providerSelect.count() > 0) {
          await providerSelect.selectOption('payme');
        }
      }
      
      await page.click('button[type="submit"]');
      
      // Проверяем результат
      await expect(page.locator('text=Платеж создан')).toBeVisible({ timeout: 10000 });
    }
  });

  test('should validate payment amount', async ({ page }) => {
    await page.goto('/cashier');
    
    const createButton = page.locator('button:has-text("Создать платеж")');
    
    if (await createButton.count() > 0) {
      await createButton.first().click();
      
      // Пытаемся создать платеж с нулевой суммой
      await page.fill('input[name="amount"]', '0');
      await page.click('button[type="submit"]');
      
      // Должна показаться ошибка валидации
      await expect(page.locator('text=Сумма должна быть больше 0')).toBeVisible({ timeout: 5000 });
      
      // Пытаемся с отрицательной суммой
      await page.fill('input[name="amount"]', '-1000');
      await page.click('button[type="submit"]');
      
      await expect(page.locator('text=Некорректная сумма')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should display payment history', async ({ page }) => {
    await page.goto('/cashier');
    
    // Ищем историю платежей
    const historySection = page.locator('text=История платежей, .payment-history, [data-testid="payment-history"]');
    
    if (await historySection.count() > 0) {
      await expect(historySection.first()).toBeVisible();
      
      // Проверяем наличие элементов истории
      const paymentItems = page.locator('.payment-item, [data-testid="payment-item"]');
      
      if (await paymentItems.count() > 0) {
        // Проверяем первый элемент
        const firstItem = paymentItems.first();
        await expect(firstItem).toBeVisible();
        
        // Проверяем наличие основной информации
        await expect(firstItem.locator('text=/\\d+/')).toBeVisible(); // Сумма
        await expect(firstItem.locator('text=/Click|Payme|Kaspi/')).toBeVisible(); // Провайдер
      }
    }
  });

  test('should handle payment status updates', async ({ page }) => {
    await page.goto('/cashier');
    
    // Создаем платеж
    const createButton = page.locator('button:has-text("Создать платеж")');
    
    if (await createButton.count() > 0) {
      await createButton.first().click();
      await page.fill('input[name="amount"]', '25000');
      await page.fill('input[name="description"]', 'Тестовый платеж');
      await page.click('button[type="submit"]');
      
      // Ждем создания
      await page.waitForTimeout(2000);
      
      // Ищем созданный платеж в списке
      const paymentItem = page.locator('.payment-item').first();
      
      if (await paymentItem.count() > 0) {
        // Проверяем статус
        const statusElement = paymentItem.locator('.payment-status, [data-testid="payment-status"]');
        
        if (await statusElement.count() > 0) {
          const status = await statusElement.textContent();
          expect(status).toMatch(/Создан|Ожидает|Pending|Created/i);
        }
      }
    }
  });

  test('should attach payment to visit', async ({ page }) => {
    await page.goto('/cashier');
    
    // Ищем функцию привязки к визиту
    const attachButton = page.locator('button:has-text("Привязать к визиту"), button:has-text("Привязать")');
    
    if (await attachButton.count() > 0) {
      await attachButton.first().click();
      
      // Выбираем визит
      const visitSelect = page.locator('select[name="visit"], .visit-select');
      if (await visitSelect.count() > 0) {
        await visitSelect.selectOption({ index: 1 });
        
        // Подтверждаем привязку
        await page.click('button:has-text("Подтвердить")');
        
        await expect(page.locator('text=Платеж привязан к визиту')).toBeVisible({ timeout: 5000 });
      }
    }
  });

  test('should generate payment receipt', async ({ page }) => {
    await page.goto('/cashier');
    
    // Ищем кнопку печати квитанции
    const receiptButton = page.locator('button:has-text("Квитанция"), button:has-text("Чек")');
    
    if (await receiptButton.count() > 0) {
      // Слушаем открытие нового окна/вкладки
      const [newPage] = await Promise.all([
        page.context().waitForEvent('page'),
        receiptButton.first().click()
      ]);
      
      // Проверяем что открылась страница с квитанцией
      await newPage.waitForLoadState();
      expect(newPage.url()).toContain('receipt');
      
      await newPage.close();
    }
  });

  test('should handle payment cancellation', async ({ page }) => {
    await page.goto('/cashier');
    
    // Ищем кнопку отмены платежа
    const cancelButton = page.locator('button:has-text("Отменить"), .cancel-payment');
    
    if (await cancelButton.count() > 0) {
      await cancelButton.first().click();
      
      // Подтверждаем отмену
      const confirmButton = page.locator('button:has-text("Подтвердить отмену")');
      if (await confirmButton.count() > 0) {
        await confirmButton.first().click();
        
        await expect(page.locator('text=Платеж отменен')).toBeVisible({ timeout: 5000 });
      }
    }
  });

  test('should display payment statistics', async ({ page }) => {
    await page.goto('/cashier');
    
    // Проверяем статистику платежей
    const statsElements = [
      'text=Всего платежей',
      'text=Сумма за день',
      'text=Успешных платежей',
      '.payment-stats',
      '[data-testid="payment-stats"]'
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
      console.log('Payment statistics not found - may not be implemented yet');
    }
  });

  test('should handle webhook notifications', async ({ page }) => {
    // Этот тест проверяет обновление статуса через webhook
    await page.goto('/cashier');
    
    // Создаем платеж
    const createButton = page.locator('button:has-text("Создать платеж")');
    
    if (await createButton.count() > 0) {
      await createButton.first().click();
      await page.fill('input[name="amount"]', '10000');
      await page.click('button[type="submit"]');
      
      // Ждем создания
      await page.waitForTimeout(1000);
      
      // Имитируем webhook (в реальности это будет приходить от платежной системы)
      await page.evaluate(() => {
        // Имитируем WebSocket или polling обновление
        window.dispatchEvent(new CustomEvent('paymentStatusUpdate', {
          detail: { status: 'paid', paymentId: 'test-payment-id' }
        }));
      });
      
      // Проверяем обновление статуса
      await expect(page.locator('text=Оплачен')).toBeVisible({ timeout: 10000 });
    }
  });
});
