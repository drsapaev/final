// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

/**
 * Payments API client — centralized wrapper over `api` from api/client.js.
 *
 * UX Audit Stage 3 (Payment issue 8.1):
 * Раньше в PaymentManager.jsx было 3 raw fetch() вызова к /payments/*
 * с дублированием headers/JSON-parsing/error-handling.
 *
 * Этот модуль инкапсулирует все payment-операции в одном месте.
 * Auth/CSRF/refresh-token обрабатываются централизованно через axios-interceptor
 * в api/client.js.
 */

import { api } from './client';
import logger from '../utils/logger';

// =====================================================================
// INVOICES API
// =====================================================================

/**
 * Получить список неоплаченных счетов.
 * @returns {Promise<Array<object>>} Массив счетов (может быть пустым)
 */
export async function getPendingInvoices() {
  try {
    const response = await api.get('/payments/invoices/pending');
    return response.data;
  } catch (error) {
    logger.error('[payments API] getPendingInvoices failed', {
      status: error?.response?.status,
      detail: error?.response?.data?.detail,
    });
    const wrapped = new Error(
      error?.response?.data?.detail || 'Ошибка загрузки счетов'
    );
    wrapped.status = error?.response?.status;
    wrapped.response = error?.response;
    throw wrapped;
  }
}

/**
 * Создать новый счёт для оплаты.
 * @param {object} invoiceData - { amount, currency, provider, description, patient_info }
 * @returns {Promise<object>} Created invoice with invoice_id
 */
export async function createPaymentInvoice(invoiceData) {
  try {
    const response = await api.post('/payments/invoice/create', invoiceData);
    return response.data;
  } catch (error) {
    logger.error('[payments API] createPaymentInvoice failed', {
      status: error?.response?.status,
      detail: error?.response?.data?.detail,
    });
    const wrapped = new Error(
      error?.response?.data?.detail || 'Ошибка создания счёта'
    );
    wrapped.status = error?.response?.status;
    wrapped.response = error?.response;
    throw wrapped;
  }
}

// =====================================================================
// HELPERS
// =====================================================================

/**
 * UX Audit Stage 3 (Payment issue 8.1):
 * Форматирование суммы в сумах с явной локалью.
 * Раньше использовался toLocaleString() без локали — в разных браузерах
 * давал «1,234,567» или «1 234 567» или «1.234.567».
 *
 * @param {number} amount - Сумма в сумах
 * @param {string} [locale='ru-RU'] - Локаль для форматирования
 * @returns {string} Отформатированная строка, например «1 234 567 сум»
 */
export function formatUZS(amount, locale = 'ru-RU') {
  if (!Number.isFinite(amount)) return '0 сум';
  const formatted = new Intl.NumberFormat(locale, {
    maximumFractionDigits: 0,
  }).format(amount);
  return `${formatted} сум`;
}

/**
 * UX Audit Stage 3 (Payment issue 8.1):
 * Нормализация введённой суммы — защита от NaN.
 * Раньше Number(e.target.value) при пустом инпуте давал 0, а при нечисловом
 * вводе — NaN. Проверка paymentAmount <= 0 пропускала NaN (NaN <= 0 → false),
 * и кнопка «Создать оплату» была активна.
 *
 * @param {*} value - Любое значение из input
 * @returns {number} Валидное число ≥ 0 (0 если невалидно)
 */
export function normalizePaymentAmount(value) {
  const num = Number(value);
  if (!Number.isFinite(num) || num < 0) return 0;
  return num;
}

/**
 * UX Audit Stage 3 (Payment issue 8.1):
 * Валидация суммы для создания счёта.
 * @param {number} amount
 * @returns {boolean} true если сумма валидна для создания счёта
 */
export function isValidPaymentAmount(amount) {
  return Number.isFinite(amount) && amount > 0;
}

const paymentsAPI = {
  getPendingInvoices,
  createPaymentInvoice,
  formatUZS,
  normalizePaymentAmount,
  isValidPaymentAmount,
};

export default paymentsAPI;
