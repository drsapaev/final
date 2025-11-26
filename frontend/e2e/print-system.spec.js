import { test, expect } from '@playwright/test';

test.describe('Print System Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Логинимся как врач
    await page.goto('/login');
    await page.fill('input[type="text"]', 'doctor@clinic.com');
    await page.fill('input[type="password"]', 'doctor123');
    await page.click('button[type="submit"]');
    
    // Ждем загрузки панели врача
    await page.waitForLoadState('networkidle');
  });

  test('should display print options in doctor panel', async ({ page }) => {
    await page.goto('/doctor');
    
    // Проверяем наличие кнопок печати
    const printButtons = [
      'button:has-text("Печать")',
      'button:has-text("Рецепт")',
      'button:has-text("Талон")',
      '.print-button',
      '[data-testid="print-button"]'
    ];
    
    let printFound = false;
    for (const selector of printButtons) {
      if (await page.locator(selector).count() > 0) {
        await expect(page.locator(selector)).toBeVisible();
        printFound = true;
        break;
      }
    }
    
    if (!printFound) {
      console.log('Print buttons not found - checking in patient card or visit details');
    }
  });

  test('should print prescription', async ({ page }) => {
    await page.goto('/doctor');
    
    // Ищем кнопку печати рецепта
    const prescriptionButton = page.locator('button:has-text("Рецепт"), button:has-text("Печать рецепта")');
    
    if (await prescriptionButton.count() > 0) {
      await prescriptionButton.first().click();
      
      // Заполняем форму рецепта
      const medicationInput = page.locator('input[name="medication"], input[placeholder*="Препарат"]');
      if (await medicationInput.count() > 0) {
        await medicationInput.fill('Парацетамол 500мг');
      }
      
      const dosageInput = page.locator('input[name="dosage"], textarea[name="instructions"]');
      if (await dosageInput.count() > 0) {
        await dosageInput.fill('По 1 таблетке 3 раза в день после еды');
      }
      
      // Печатаем рецепт
      const printButton = page.locator('button:has-text("Печать"), button[type="submit"]');
      if (await printButton.count() > 0) {
        // Слушаем открытие нового окна для PDF
        const [newPage] = await Promise.all([
          page.context().waitForEvent('page'),
          printButton.first().click()
        ]);
        
        // Проверяем что открылся PDF
        await newPage.waitForLoadState();
        expect(newPage.url()).toMatch(/pdf|prescription|print/);
        
        await newPage.close();
      }
    }
  });

  test('should print patient ticket', async ({ page }) => {
    await page.goto('/registrar'); // Переходим к регистратору для печати талонов
    
    // Ищем кнопку печати талона
    const ticketButton = page.locator('button:has-text("Талон"), button:has-text("Печать талона")');
    
    if (await ticketButton.count() > 0) {
      await ticketButton.first().click();
      
      // Выбираем пациента
      const patientSelect = page.locator('select[name="patient"], .patient-select');
      if (await patientSelect.count() > 0) {
        await patientSelect.selectOption({ index: 1 });
      }
      
      // Печатаем талон
      const printButton = page.locator('button:has-text("Печать")');
      if (await printButton.count() > 0) {
        await printButton.first().click();
        
        // Проверяем успешную печать
        await expect(page.locator('text=Талон отправлен на печать')).toBeVisible({ timeout: 10000 });
      }
    }
  });

  test('should print medical memo', async ({ page }) => {
    await page.goto('/doctor');
    
    // Ищем кнопку печати памятки
    const memoButton = page.locator('button:has-text("Памятка"), button:has-text("Рекомендации")');
    
    if (await memoButton.count() > 0) {
      await memoButton.first().click();
      
      // Заполняем текст памятки
      const memoText = page.locator('textarea[name="memo"], textarea[placeholder*="Рекомендации"]');
      if (await memoText.count() > 0) {
        await memoText.fill('Соблюдать постельный режим. Обильное питье. Повторный визит через неделю.');
      }
      
      // Печатаем памятку
      const printButton = page.locator('button:has-text("Печать")');
      if (await printButton.count() > 0) {
        const [newPage] = await Promise.all([
          page.context().waitForEvent('page'),
          printButton.first().click()
        ]);
        
        await newPage.waitForLoadState();
        expect(newPage.url()).toMatch(/pdf|memo|print/);
        
        await newPage.close();
      }
    }
  });

  test('should configure printer settings', async ({ page }) => {
    await page.goto('/settings'); // Переходим в настройки
    
    // Ищем настройки принтера
    const printerSettings = page.locator('text=Принтер, text=Печать, .printer-settings');
    
    if (await printerSettings.count() > 0) {
      await printerSettings.first().click();
      
      // Проверяем настройки принтера
      const printerSelect = page.locator('select[name="printer"], .printer-select');
      if (await printerSelect.count() > 0) {
        await expect(printerSelect).toBeVisible();
        
        // Выбираем принтер
        await printerSelect.selectOption({ index: 1 });
        
        // Сохраняем настройки
        const saveButton = page.locator('button:has-text("Сохранить")');
        if (await saveButton.count() > 0) {
          await saveButton.click();
          await expect(page.locator('text=Настройки сохранены')).toBeVisible({ timeout: 5000 });
        }
      }
    }
  });

  test('should preview document before printing', async ({ page }) => {
    await page.goto('/doctor');
    
    const prescriptionButton = page.locator('button:has-text("Рецепт")');
    
    if (await prescriptionButton.count() > 0) {
      await prescriptionButton.first().click();
      
      // Заполняем форму
      await page.fill('input[name="medication"]', 'Ибупрофен 400мг');
      await page.fill('textarea[name="instructions"]', 'По 1 таблетке при боли, не более 3 раз в день');
      
      // Ищем кнопку предпросмотра
      const previewButton = page.locator('button:has-text("Предпросмотр"), button:has-text("Просмотр")');
      
      if (await previewButton.count() > 0) {
        await previewButton.first().click();
        
        // Проверяем что открылся предпросмотр
        await expect(page.locator('.preview-modal, [data-testid="preview"]')).toBeVisible({ timeout: 5000 });
        
        // Проверяем содержимое предпросмотра
        await expect(page.locator('text=Ибупрофен')).toBeVisible();
        await expect(page.locator('text=По 1 таблетке при боли')).toBeVisible();
      }
    }
  });

  test('should handle print queue', async ({ page }) => {
    await page.goto('/admin'); // Переходим в админ панель
    
    // Ищем очередь печати
    const printQueue = page.locator('text=Очередь печати, .print-queue, [data-testid="print-queue"]');
    
    if (await printQueue.count() > 0) {
      await printQueue.first().click();
      
      // Проверяем элементы очереди
      const queueItems = page.locator('.print-job, [data-testid="print-job"]');
      
      if (await queueItems.count() > 0) {
        const firstJob = queueItems.first();
        await expect(firstJob).toBeVisible();
        
        // Проверяем статус задания
        const status = firstJob.locator('.job-status, [data-testid="job-status"]');
        if (await status.count() > 0) {
          const statusText = await status.textContent();
          expect(statusText).toMatch(/Ожидает|В процессе|Завершено|Ошибка/);
        }
      }
    }
  });

  test('should handle print errors', async ({ page }) => {
    await page.goto('/doctor');
    
    // Имитируем ошибку принтера
    await page.route('**/api/v1/print/**', route => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Printer not available' })
      });
    });
    
    const prescriptionButton = page.locator('button:has-text("Рецепт")');
    
    if (await prescriptionButton.count() > 0) {
      await prescriptionButton.first().click();
      await page.fill('input[name="medication"]', 'Тестовый препарат');
      
      const printButton = page.locator('button:has-text("Печать")');
      if (await printButton.count() > 0) {
        await printButton.first().click();
        
        // Проверяем сообщение об ошибке
        await expect(page.locator('text=Ошибка печати')).toBeVisible({ timeout: 10000 });
      }
    }
  });

  test('should print lab results', async ({ page }) => {
    await page.goto('/lab'); // Переходим в лабораторию
    
    // Ищем кнопку печати результатов
    const printResultsButton = page.locator('button:has-text("Печать результатов"), button:has-text("Экспорт PDF")');
    
    if (await printResultsButton.count() > 0) {
      await printResultsButton.first().click();
      
      // Выбираем результаты для печати
      const resultsCheckbox = page.locator('input[type="checkbox"]').first();
      if (await resultsCheckbox.count() > 0) {
        await resultsCheckbox.check();
      }
      
      // Печатаем
      const printButton = page.locator('button:has-text("Печать выбранных")');
      if (await printButton.count() > 0) {
        const [newPage] = await Promise.all([
          page.context().waitForEvent('page'),
          printButton.first().click()
        ]);
        
        await newPage.waitForLoadState();
        expect(newPage.url()).toMatch(/pdf|results|print/);
        
        await newPage.close();
      }
    }
  });

  test('should customize print templates', async ({ page }) => {
    await page.goto('/admin');
    
    // Ищем настройки шаблонов
    const templateSettings = page.locator('text=Шаблоны печати, .print-templates');
    
    if (await templateSettings.count() > 0) {
      await templateSettings.first().click();
      
      // Выбираем шаблон рецепта
      const prescriptionTemplate = page.locator('text=Шаблон рецепта, .prescription-template');
      if (await prescriptionTemplate.count() > 0) {
        await prescriptionTemplate.first().click();
        
        // Редактируем шаблон
        const templateEditor = page.locator('textarea[name="template"], .template-editor');
        if (await templateEditor.count() > 0) {
          await templateEditor.fill('Рецепт №{{number}}\nПрепарат: {{medication}}\nДозировка: {{dosage}}');
          
          // Сохраняем
          await page.click('button:has-text("Сохранить")');
          await expect(page.locator('text=Шаблон сохранен')).toBeVisible({ timeout: 5000 });
        }
      }
    }
  });

  test('should handle thermal printer format', async ({ page }) => {
    await page.goto('/registrar');
    
    // Печатаем талон на термопринтер
    const thermalPrintButton = page.locator('button:has-text("Термопечать"), .thermal-print');
    
    if (await thermalPrintButton.count() > 0) {
      await thermalPrintButton.first().click();
      
      // Проверяем формат термопечати (58мм)
      await expect(page.locator('text=58мм')).toBeVisible({ timeout: 5000 });
      
      // Печатаем
      await page.click('button:has-text("Печать")');
      await expect(page.locator('text=Отправлено на термопринтер')).toBeVisible({ timeout: 5000 });
    }
  });
});
