import { api } from './client';
import { getRegistrarPaymentSummary } from './registrarPayments';
import type { RegistrarBenefitApprovalDto, RegistrarBenefitDecisionDto } from '../types/api';

export interface RegistrarBenefitOption {
  id: number;
  name: string;
}

export interface SavedRegistrarBenefitCart {
  invoiceId: number;
  visitIds: number[];
  originalTotal: string;
  currency: string | null;
}

function isDatabaseId(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value > 0 && value <= 2147483647;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function parseMoney(value: unknown): string | null {
  if (typeof value !== 'number' && typeof value !== 'string') return null;
  const text = String(value);
  return /^\d{1,10}(?:\.\d{1,2})?$/.test(text) ? text : null;
}

function toCents(amount: string): number {
  return Math.round(Number(amount) * 100);
}

export function getSavedRegistrarBenefitCart(
  response: unknown,
  currency: unknown,
): SavedRegistrarBenefitCart | null {
  const cart = asRecord(response);
  if (cart?.success !== true) return null;
  const originalTotal = parseMoney(cart.total_amount);
  if (
    !isDatabaseId(cart.invoice_id) ||
    !Array.isArray(cart.visit_ids) || !cart.visit_ids.length ||
    !cart.visit_ids.every(isDatabaseId) || new Set(cart.visit_ids).size !== cart.visit_ids.length ||
    originalTotal === null || toCents(originalTotal) <= 0
  ) return null;

  return {
    invoiceId: cart.invoice_id,
    visitIds: [...cart.visit_ids],
    originalTotal,
    currency: typeof currency === 'string' && /^[A-Z]{3}$/.test(currency) ? currency : null,
  };
}

export async function listRegistrarPatientBenefits(
  patientId: number,
  signal?: AbortSignal,
): Promise<RegistrarBenefitOption[]> {
  const { data } = await api.get<{ patient_benefits: unknown[] }>(
    `/discount-benefits/benefits/patient/${patientId}`, { params: { active_only: true }, signal },
  );
  if (!Array.isArray(data?.patient_benefits)) throw new Error('Invalid patient benefit list');

  return data.patient_benefits.flatMap((entry) => {
    const assignment = asRecord(entry);
    if (!assignment || assignment.is_active !== true || assignment.verified !== true) return [];
    const name = asRecord(assignment.benefit)?.name;
    return isDatabaseId(assignment.id) && typeof name === 'string' && name.trim()
      ? [{ id: assignment.id, name: name.trim() }]
      : [];
  });
}

export async function approveRegistrarCartBenefit(
  cart: SavedRegistrarBenefitCart,
  selectedBenefitId: number,
): Promise<{ total: string; discount: string }> {
  const request: RegistrarBenefitApprovalDto = {
    invoice_id: cart.invoiceId,
    patient_benefit_id: selectedBenefitId,
  };
  const { data } = await api.post<RegistrarBenefitDecisionDto>('/discount-benefits/benefits/encounter/apply', request);
  const original = parseMoney(data?.gross_total);
  const discount = parseMoney(data?.benefit_total);
  const total = parseMoney(data?.total_amount);
  if (
    data?.invoice_id !== cart.invoiceId || !isDatabaseId(data.application_id) ||
    original === null || discount === null || total === null ||
    toCents(original) !== toCents(cart.originalTotal) || toCents(discount) <= 0 ||
    toCents(original) !== toCents(discount) + toCents(total)
  ) throw new Error('Invalid benefit receipt');
  return { total, discount };
}

export async function readRegistrarBenefitBalance(cart: SavedRegistrarBenefitCart) {
  const summary = await getRegistrarPaymentSummary({
    grouped_record_refs: cart.visitIds.map((id) => ({ record_kind: 'visit', record_id: id })),
  });
  if (!Array.isArray(summary?.visits) || summary.visits.length !== cart.visitIds.length) {
    throw new Error('Invalid registrar visit group');
  }
  const summaryIds = new Set(summary.visits.map((visit) => visit.visit_id));
  if (summaryIds.size !== cart.visitIds.length || !cart.visitIds.every((id) => summaryIds.has(id))) {
    throw new Error('Invalid registrar visit group');
  }

  const total = parseMoney(summary.total_amount);
  const paid = parseMoney(summary.paid_amount);
  const remaining = parseMoney(summary.remaining_amount);
  if (total === null || paid === null || remaining === null || typeof summary.can_pay !== 'boolean') {
    throw new Error('Invalid registrar balance');
  }
  const canPay = summary.can_pay && toCents(remaining) > 0;
  return {
    total,
    canContinue: canPay || (toCents(total) === 0 && toCents(paid) === 0),
    canRetry: canPay && toCents(paid) === 0 && toCents(total) === toCents(cart.originalTotal),
  };
}
