/**
 * Zod schema for InvoiceDto — billing endpoints return dynamic Pydantic shapes.
 *
 * Per ADR-0018, this schema validates the minimal invariant: id (or invoice_id)
 * is present. Additional fields are passed through via the domain index signature.
 *
 * Note: billing endpoints are NOT in the generated OpenAPI schema, so this
 * schema is hand-written based on observed backend responses.
 */

import { z } from 'zod';

export const InvoiceDtoSchema = z.object({
  /** Id or invoice_id — at least one required */
  id: z.union([z.string(), z.number()]).optional(),
  invoice_id: z.union([z.string(), z.number()]).optional(),
  appointment_id: z.union([z.string(), z.number()]).optional(),
  patient_id: z.union([z.string(), z.number()]).optional(),
  patient_name: z.string().optional(),
  amount: z.union([z.string(), z.number()]).optional(),
  paid_amount: z.union([z.string(), z.number()]).optional(),
  discount_amount: z.union([z.string(), z.number()]).optional(),
  status: z.string().optional(),
  method: z.string().optional(),
  created_at: z.string().optional(),
  paid_at: z.string().optional(),
  // Pass-through for backend extras
}).passthrough().refine(
  (data) => data.id != null || data.invoice_id != null,
  { message: 'InvoiceDto must have either `id` or `invoice_id`' }
);

export type InvoiceDtoParsed = z.infer<typeof InvoiceDtoSchema>;

export const PaymentDtoSchema = z.object({
  id: z.union([z.string(), z.number()]).optional(),
  payment_id: z.union([z.string(), z.number()]).optional(),
  invoice_id: z.union([z.string(), z.number()]).optional(),
  patient_id: z.union([z.string(), z.number()]).optional(),
  amount: z.union([z.string(), z.number()]).optional(),
  method: z.string().optional(),
  status: z.string().optional(),
  transaction_id: z.string().optional(),
  created_at: z.string().optional(),
}).passthrough().refine(
  (data) => data.id != null || data.payment_id != null,
  { message: 'PaymentDto must have either `id` or `payment_id`' }
);

export type PaymentDtoParsed = z.infer<typeof PaymentDtoSchema>;

export default { InvoiceDtoSchema, PaymentDtoSchema };
