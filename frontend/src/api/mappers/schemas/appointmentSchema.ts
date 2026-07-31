/**
 * Zod schema for AppointmentDto — mirrors the OpenAPI Appointment schema.
 *
 * Per ADR-0018 (Runtime Validation Strategy), this schema is the single
 * validation boundary for Appointment data.
 *
 * Source: types/generated/api.ts → Schemas['Appointment']
 */

import { z } from 'zod';

export const AppointmentDtoSchema = z.object({
  /** Patient Id — required */
  patient_id: z.number(),
  /** Doctor Id */
  doctor_id: z.number().nullable().optional(),
  /** Department */
  department: z.string().nullable().optional(),
  /** Appointment Date — required (ISO date) */
  appointment_date: z.string(),
  /** Appointment Time */
  appointment_time: z.string().nullable().optional(),
  /** Notes */
  notes: z.string().nullable().optional(),
  /** Status — required (default: scheduled) */
  status: z.string(),
  /** Visit Type (default: paid) */
  visit_type: z.string().nullable(),
  /** Payment Type (default: cash) */
  payment_type: z.string().nullable(),
  /** Services */
  services: z.array(z.string()).nullable().optional(),
  /** Payment Amount */
  payment_amount: z.number().nullable().optional(),
  /** Payment Currency (default: UZS) */
  payment_currency: z.string().nullable(),
  /** Payment Provider */
  payment_provider: z.string().nullable().optional(),
  /** Payment Transaction Id */
  payment_transaction_id: z.string().nullable().optional(),
  /** Payment Webhook Id */
  payment_webhook_id: z.number().nullable().optional(),
  /** Payment Processed At */
  payment_processed_at: z.string().nullable().optional(),
  /** Id — required */
  id: z.number(),
  /** Created At — required (ISO date-time) */
  created_at: z.string(),
  /** Updated At */
  updated_at: z.string().nullable().optional(),
  /** Patient Name */
  patient_name: z.string().nullable().optional(),
});

export type AppointmentDtoParsed = z.infer<typeof AppointmentDtoSchema>;

export default AppointmentDtoSchema;
