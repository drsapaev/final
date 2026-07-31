/**
 * Mappers: billing DTOs → domain Invoice / Payment.
 *
 * Per ADR-0018, zod schemas validate the DTO shape before transformation.
 */

import type { Invoice, Payment } from '../../types/domain/billing';
import { toInvoiceId, toAppointmentId, toPatientId, toPaymentId } from '../../types/domain/branded';
import { InvoiceDtoSchema, PaymentDtoSchema } from './schemas/billingSchema';

export function mapInvoiceDto(dto: Record<string, unknown> | unknown): Invoice {
  const parsed = InvoiceDtoSchema.parse(dto);
  const id = parsed.id ?? parsed.invoice_id;
  if (id == null) {
    throw new Error('[mapInvoiceDto] missing required field `id` or `invoice_id`');
  }

  return {
    id: toInvoiceId(id),
    appointment_id: parsed.appointment_id != null ? toAppointmentId(parsed.appointment_id) : undefined,
    patient_id: parsed.patient_id != null ? toPatientId(parsed.patient_id) : undefined,
    patient_name: parsed.patient_name,
    amount: parsed.amount != null ? Number(parsed.amount) : undefined,
    paid_amount: parsed.paid_amount != null ? Number(parsed.paid_amount) : undefined,
    discount_amount: parsed.discount_amount != null ? Number(parsed.discount_amount) : undefined,
    status: parsed.status as Invoice['status'],
    method: parsed.method as Invoice['method'],
    created_at: parsed.created_at,
    paid_at: parsed.paid_at,
    ...parsed,
  } as unknown as Invoice;
}

export function mapInvoiceDtos(dtos: unknown): Invoice[] {
  if (!Array.isArray(dtos)) return [];
  const out: Invoice[] = [];
  for (const dto of dtos) {
    try {
      out.push(mapInvoiceDto(dto));
    } catch {
      // skip malformed
    }
  }
  return out;
}

export function mapPaymentDto(dto: Record<string, unknown> | unknown): Payment {
  const parsed = PaymentDtoSchema.parse(dto);
  const id = parsed.id ?? parsed.payment_id;
  if (id == null) {
    throw new Error('[mapPaymentDto] missing required field `id` or `payment_id`');
  }

  return {
    id: toPaymentId(id),
    invoice_id: parsed.invoice_id != null ? toInvoiceId(parsed.invoice_id) : undefined,
    patient_id: parsed.patient_id != null ? toPatientId(parsed.patient_id) : undefined,
    amount: parsed.amount != null ? Number(parsed.amount) : undefined,
    method: parsed.method as Payment['method'],
    status: parsed.status as Payment['status'],
    transaction_id: parsed.transaction_id,
    created_at: parsed.created_at,
    ...parsed,
  } as unknown as Payment;
}
