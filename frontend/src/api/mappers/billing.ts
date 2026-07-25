/**
 * Mappers: billing DTOs → domain Invoice / Payment.
 *
 * The backend payment endpoints (/payments/invoices/*, /payments/*) return
 * dynamic Pydantic shapes. These mappers normalize the canonical fields
 * the UI reads and let extras ride along via the domain index signature.
 */

import type { Invoice, Payment } from '../../types/domain/billing';

// Transport shape — the backend returns this loose form. We don't have a
// strict OpenAPI *Dto for these endpoints (they're not in the generated
// schema), so we accept `unknown` and assert the minimal invariant at runtime.
type InvoiceDtoLike = Record<string, unknown>;
type PaymentDtoLike = Record<string, unknown>;

export function mapInvoiceDto(dto: InvoiceDtoLike): Invoice {
  if (dto == null || typeof dto !== 'object') {
    throw new Error('[mapInvoiceDto] expected object, got ' + typeof dto);
  }
  // Invariant: an invoice must have either an `id` or an `invoice_id`.
  // Some endpoints return `invoice_id` instead of `id`; normalize.
  const id = (dto.id ?? dto.invoice_id) as string | number | undefined;
  if (id == null) {
    throw new Error('[mapInvoiceDto] missing required field `id` or `invoice_id`');
  }

  return {
    id,
    appointment_id: dto.appointment_id as string | number | undefined,
    patient_id: dto.patient_id as string | number | undefined,
    patient_name: dto.patient_name as string | undefined,
    amount: dto.amount != null ? Number(dto.amount) : undefined,
    paid_amount: dto.paid_amount != null ? Number(dto.paid_amount) : undefined,
    discount_amount: dto.discount_amount != null ? Number(dto.discount_amount) : undefined,
    status: dto.status as Invoice['status'],
    method: dto.method as Invoice['method'],
    created_at: dto.created_at as string | undefined,
    paid_at: dto.paid_at as string | undefined,
    ...dto,
  };
}

export function mapInvoiceDtos(dtos: unknown): Invoice[] {
  if (!Array.isArray(dtos)) return [];
  const out: Invoice[] = [];
  for (const dto of dtos) {
    try {
      out.push(mapInvoiceDto(dto as InvoiceDtoLike));
    } catch {
      // skip malformed
    }
  }
  return out;
}

export function mapPaymentDto(dto: PaymentDtoLike): Payment {
  if (dto == null || typeof dto !== 'object') {
    throw new Error('[mapPaymentDto] expected object, got ' + typeof dto);
  }
  const id = (dto.id ?? dto.payment_id) as string | number | undefined;
  if (id == null) {
    throw new Error('[mapPaymentDto] missing required field `id` or `payment_id`');
  }

  return {
    id,
    invoice_id: dto.invoice_id as string | number | undefined,
    amount: dto.amount != null ? Number(dto.amount) : undefined,
    method: dto.method as Payment['method'],
    status: dto.status as Payment['status'],
    transaction_id: dto.transaction_id as string | undefined,
    created_at: dto.created_at as string | undefined,
    ...dto,
  };
}
