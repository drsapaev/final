/**
 * usePaymentsApi — hook wrapper for the payments API module.
 *
 * Per ADR-0015, components must NOT import from `api/payments` directly.
 * This hook is the sanctioned entry point for:
 *   - getPendingInvoices / createPaymentInvoice (REST)
 *   - formatUZS / normalizePaymentAmount / isValidPaymentAmount (utilities)
 *
 * The utilities are pure functions but live in api/payments.ts because they
 * are tightly coupled to the payment domain (UZS formatting, amount
 * validation). Re-exporting them via the hook keeps the import boundary
 * clean without splitting the file.
 */

import {
  getPendingInvoices,
  createPaymentInvoice,
  formatUZS,
  normalizePaymentAmount,
  isValidPaymentAmount,
} from '../api/payments';

export interface UsePaymentsApiReturn {
  getPendingInvoices: typeof getPendingInvoices;
  createPaymentInvoice: typeof createPaymentInvoice;
  formatUZS: typeof formatUZS;
  normalizePaymentAmount: typeof normalizePaymentAmount;
  isValidPaymentAmount: typeof isValidPaymentAmount;
}

export function usePaymentsApi(): UsePaymentsApiReturn {
  return {
    getPendingInvoices,
    createPaymentInvoice,
    formatUZS,
    normalizePaymentAmount,
    isValidPaymentAmount,
  };
}

export default usePaymentsApi;
