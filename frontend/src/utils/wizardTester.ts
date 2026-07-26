import logger from '../utils/logger';
// UX Audit: миграция 5 raw fetch() → api/client.js.
import { api } from '../api/client';

/**
 * Утилиты для тестирования мастера регистрации
 * Можно использовать в консоли браузера для быстрой проверки функций
 */

class WizardTester {
  // Тест 1: Проверка настроек мастера
  async testWizardSettings(): Promise<Record<string, unknown> | null> {
    logger.log('🧪 Тестирование настроек мастера...');

    try {
      const response = await api.get('/registrar-wizard/admin/wizard-settings');
      logger.log('✅ Настройки мастера:', response.data);
      return response.data as Record<string, unknown>;
    } catch (error) {
      logger.error('❌ Ошибка получения настроек:', error);
      return null;
    }
  }

  // Тест 2: Проверка создания корзины
  async testCartCreation(testData: Record<string, unknown> | null = null): Promise<Record<string, unknown> | null> {
    logger.log('🧪 Тестирование создания корзины...');

    const defaultTestData: Record<string, unknown> = {
      patient: {
        full_name: 'Тестовый Пациент',
        phone: '+998901234567',
        date_of_birth: '1990-01-01',
        address: 'Тестовый адрес'
      },
      visits: [
        {
          service_id: 1,
          visit_type: 'regular',
          visit_date: new Date().toISOString().split('T')[0],
          visit_time: '10:00',
          notes: 'Тестовая запись'
        }
      ],
      payment: {
        method: 'cash',
        total_amount: 50000
      }
    };

    const data: Record<string, unknown> = testData || defaultTestData;

    try {
      const response = await api.post('/registrar-wizard/registrar/cart', data);
      logger.log('✅ Корзина создана успешно:', response.data);
      return response.data as Record<string, unknown>;
    } catch (error) {
      logger.error('❌ Ошибка запроса:', error);
      return null;
    }
  }

  // Тест 3: Проверка льготных настроек
  async testBenefitSettings(): Promise<Record<string, unknown> | null> {
    logger.log('🧪 Тестирование настроек льгот...');

    try {
      const response = await api.get('/registrar-wizard/admin/benefit-settings');
      logger.log('✅ Настройки льгот:', response.data);
      return response.data as Record<string, unknown>;
    } catch (error) {
      logger.error('❌ Ошибка получения настроек льгот:', error);
      return null;
    }
  }

  // Тест 4: Проверка заявок All Free
  async testAllFreeRequests(): Promise<Record<string, unknown> | null> {
    logger.log('🧪 Тестирование заявок All Free...');

    try {
      const response = await api.get('/registrar-wizard/admin/all-free-requests');
      logger.log('✅ Заявки All Free:', response.data);
      return response.data as Record<string, unknown>;
    } catch (error) {
      logger.error('❌ Ошибка получения заявок All Free:', error);
      return null;
    }
  }

  // Тест 5: Проверка изменений цен
  async testPriceOverrides(): Promise<Record<string, unknown> | null> {
    logger.log('🧪 Тестирование изменений цен...');

    try {
      const response = await api.get('/registrar-wizard/registrar/price-overrides');
      logger.log('✅ Изменения цен:', response.data);
      return response.data as Record<string, unknown>;
    } catch (error) {
      logger.error('❌ Ошибка получения изменений цен:', error);
      return null;
    }
  }

  // Тест 6: Проверка автосохранения
  testAutosave(): boolean {
    logger.log('🧪 Тестирование автосохранения...');

    const testData = {
      step: 2,
      patient: { full_name: 'Тест Автосохранения' },
      services: [{ id: 1, name: 'Тестовая услуга' }],
      timestamp: Date.now()
    };

    // Сохраняем тестовые данные
    localStorage.setItem('wizard_draft', JSON.stringify(testData));
    logger.log('✅ Данные сохранены в localStorage');

    // Проверяем восстановление
    const stored = localStorage.getItem('wizard_draft');
    const restored = stored ? JSON.parse(stored) : null;

    if (JSON.stringify(restored) === JSON.stringify(testData)) {
      logger.log('✅ Автосохранение работает корректно');
      return true;
    } else {
      logger.error('❌ Ошибка автосохранения');
      return false;
    }
  }

  // Тест 7: Проверка валидации данных
  validateWizardData(data: Record<string, unknown>): { valid: boolean; errors: string[] } {
    logger.log('🧪 Валидация данных мастера...');

    const errors: string[] = [];

    // Проверка пациента
    const patient = data.patient as { full_name?: unknown; phone?: unknown } | undefined;
    if (!patient) {
      errors.push('Отсутствуют данные пациента');
    } else {
      if (!patient.full_name) errors.push('Не указано ФИО пациента');
      if (!patient.phone) errors.push('Не указан телефон пациента');
    }

    // Проверка визитов
    const visits = data.visits as Array<{ service_id?: unknown; visit_date?: unknown; visit_time?: unknown }> | undefined;
    if (!visits || !Array.isArray(visits) || visits.length === 0) {
      errors.push('Не выбраны услуги');
    } else {
      visits.forEach((visit: { service_id?: unknown; visit_date?: unknown; visit_time?: unknown }, index: number) => {
        if (!visit.service_id) errors.push(`Визит ${index + 1}: не указана услуга`);
        if (!visit.visit_date) errors.push(`Визит ${index + 1}: не указана дата`);
        if (!visit.visit_time) errors.push(`Визит ${index + 1}: не указано время`);
      });
    }

    // Проверка оплаты
    const payment = data.payment as { method?: unknown; total_amount?: number } | undefined;
    if (!payment) {
      errors.push('Отсутствуют данные оплаты');
    } else {
      if (!payment.method) errors.push('Не указан способ оплаты');
      if (!payment.total_amount || payment.total_amount <= 0) {
        errors.push('Некорректная сумма оплаты');
      }
    }

    if (errors.length === 0) {
      logger.log('✅ Данные валидны');
      return { valid: true, errors: [] };
    } else {
      logger.error('❌ Найдены ошибки валидации:', errors);
      return { valid: false, errors };
    }
  }

  // Запуск всех тестов
  async runAllTests(): Promise<Record<string, unknown>> {
    logger.log('🚀 Запуск всех тестов мастера регистрации...');
    logger.log('='.repeat(50));

    const results: Record<string, unknown> = {};

    // Тест настроек
    results.wizardSettings = await this.testWizardSettings();

    // Тест льготных настроек
    results.benefitSettings = await this.testBenefitSettings();

    // Тест заявок All Free
    results.allFreeRequests = await this.testAllFreeRequests();

    // Тест изменений цен
    results.priceOverrides = await this.testPriceOverrides();

    // Тест автосохранения
    results.autosave = this.testAutosave();

    // Тест создания корзины (только если есть тестовые данные)
    logger.log('ℹ️ Тест создания корзины пропущен (требует реальные service_id)');

    logger.log('='.repeat(50));
    logger.log('📊 Результаты тестирования:', results);

    const passedTests = Object.values(results).filter(result => result !== null && result !== false).length;
    const totalTests = Object.keys(results).length;

    logger.log(`✅ Пройдено тестов: ${passedTests}/${totalTests}`);

    return results;
  }

  // Генерация тестовых данных для разных сценариев
  generateTestData(scenario: string = 'basic'): Record<string, unknown> {
    const scenarios = {
      basic: {
        patient: {
          full_name: 'Иванов Иван Иванович',
          phone: '+998901234567',
          date_of_birth: '1985-05-15',
          address: 'г. Ташкент, ул. Тестовая, 123'
        },
        visits: [
          {
            service_id: 1,
            visit_type: 'regular',
            visit_date: new Date().toISOString().split('T')[0],
            visit_time: '10:00',
            notes: 'Плановый осмотр'
          }
        ],
        payment: {
          method: 'cash',
          total_amount: 50000
        }
      },

      repeat: {
        patient: {
          full_name: 'Петров Петр Петрович',
          phone: '+998901234568',
          date_of_birth: '1980-03-20'
        },
        visits: [
          {
            service_id: 2, // Консультация кардиолога
            visit_type: 'repeat',
            visit_date: new Date().toISOString().split('T')[0],
            visit_time: '11:00',
            notes: 'Повторная консультация'
          }
        ],
        payment: {
          method: 'cash',
          total_amount: 0 // Бесплатно для повторного
        }
      },

      benefit: {
        patient: {
          full_name: 'Сидоров Сидор Сидорович',
          phone: '+998901234569',
          date_of_birth: '1975-12-10'
        },
        visits: [
          {
            service_id: 2,
            visit_type: 'benefit',
            visit_date: new Date().toISOString().split('T')[0],
            visit_time: '12:00',
            notes: 'Льготная консультация'
          }
        ],
        payment: {
          method: 'cash',
          total_amount: 0 // Бесплатно для льготного
        }
      },

      cart: {
        patient: {
          full_name: 'Многоуслугов Много Услугович',
          phone: '+998901234570',
          date_of_birth: '1990-07-25'
        },
        visits: [
          {
            service_id: 1, // ЭКГ
            visit_type: 'regular',
            visit_date: new Date().toISOString().split('T')[0],
            visit_time: '09:00',
            notes: 'ЭКГ'
          },
          {
            service_id: 3, // ЭхоКГ
            doctor_id: 1,
            visit_type: 'regular',
            visit_date: new Date().toISOString().split('T')[0],
            visit_time: '10:00',
            notes: 'ЭхоКГ с кардиологом'
          },
          {
            service_id: 4, // Анализы
            visit_type: 'regular',
            visit_date: new Date().toISOString().split('T')[0],
            visit_time: '08:00',
            notes: 'Лабораторные анализы'
          }
        ],
        payment: {
          method: 'online_click',
          total_amount: 150000
        }
      }
    };

    return scenarios[scenario as keyof typeof scenarios] || scenarios.basic;
  }
}

// Экспорт для использования в консоли
if (typeof window !== 'undefined') {
  (window as unknown as { WizardTester?: unknown }).WizardTester = WizardTester;
  (window as unknown as { wizardTester?: WizardTester }).wizardTester = new WizardTester();

  logger.log('🧪 WizardTester загружен!');
  logger.log('Используйте: wizardTester.runAllTests() для запуска всех тестов');
  logger.log('Или: wizardTester.testCartCreation(wizardTester.generateTestData("cart")) для тестирования корзины');
}

export default WizardTester;
