// Phase 1 — typed wrapper for errors enriched with axios-like fields.
interface WrappedApiError extends Error {
  status?: number;
  detail?: string;
  response?: { status?: number; data?: { detail?: unknown } };
}

function createWrappedError(message: string, extras: { status?: number; detail?: string; response?: unknown }): WrappedApiError {
  const err = new Error(message) as WrappedApiError;
  err.status = extras.status;
  err.detail = extras.detail;
  err.response = extras.response as WrappedApiError['response'];
  return err;
}

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
import type { Invoice } from '../types/domain/billing';
import { mapInvoiceDtos, mapInvoiceDto } from './mappers';

// =====================================================================
// INVOICES API
// =====================================================================

/**
 * Получить список неоплаченных счетов.
 * @returns {Promise<Invoice[]>} Массив счетов (домен)
 */
export async function getPendingInvoices(): Promise<Invoice[]> {
  try {
    const response = await api.get('/payments/invoices/pending');
    return mapInvoiceDtos(response.data);
  } catch (error) {
    logger.error('[payments API] getPendingInvoices failed', {
      status: (error as WrappedApiError)?.response?.status,
      detail: (error as WrappedApiError)?.response?.data?.detail,
    });
    throw createWrappedError(String((error as WrappedApiError)?.response?.data?.detail || 'Ошибка загрузки счетов'), { status: (error as WrappedApiError)?.response?.status as number | undefined, response: (error as WrappedApiError)?.response });
  }
}

/**
 * Создать новый счёт для оплаты.
 * @param invoiceData - { amount, currency, provider, description, patient_info }
 * @returns {Promise<Invoice>} Created invoice (домен)
 */
export async function createPaymentInvoice(invoiceData: Record<string, unknown>): Promise<Invoice> {
  try {
    const response = await api.post('/payments/invoice/create', invoiceData);
    return mapInvoiceDto(response.data as Record<string, unknown>);
  } catch (error) {
    logger.error('[payments API] createPaymentInvoice failed', {
      status: (error as WrappedApiError)?.response?.status,
      detail: (error as WrappedApiError)?.response?.data?.detail,
    });
    throw createWrappedError(String((error as WrappedApiError)?.response?.data?.detail || 'Ошибка создания счёта'), { status: (error as WrappedApiError)?.response?.status as number | undefined, response: (error as WrappedApiError)?.response });
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
export function formatUZS(amount: number | string, locale: string = 'ru-RU'): string {
  const num = Number(amount);
  if (!Number.isFinite(num)) return '0 сум';
  const formatted = new Intl.NumberFormat(locale, {
    maximumFractionDigits: 0,
  }).format(num);
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
export function normalizePaymentAmount(value: unknown): number {
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
export function isValidPaymentAmount(amount: unknown): boolean {
  const num = Number(amount);
  return Number.isFinite(num) && num > 0;
}

const paymentsAPI = {
  getPendingInvoices,
  createPaymentInvoice,
  formatUZS,
  normalizePaymentAmount,
  isValidPaymentAmount,
};

export default paymentsAPI;
