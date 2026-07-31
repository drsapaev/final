/**
 * Zod schema for PatientDto — mirrors the OpenAPI Patient schema.
 *
 * Per ADR-0018 (Runtime Validation Strategy), this schema is the single
 * validation boundary for Patient data. The mapper calls `parse()` before
 * transforming to the domain `Patient` type. Any backend contract drift
 * (field rename, type change, missing required field) is caught here
 * instead of silently propagating to components.
 *
 * Source: types/generated/api.ts → Schemas['Patient']
 */

import { z } from 'zod';

export const PatientDtoSchema = z.object({
  /** Полное ФИО (alternative to last_name+first_name) */
  full_name: z.string().nullable().optional(),
  /** Last Name — required */
  last_name: z.string(),
  /** First Name — required */
  first_name: z.string(),
  /** Middle Name */
  middle_name: z.string().nullable().optional(),
  /** Birth Date (ISO date string) */
  birth_date: z.string().nullable().optional(),
  /** Sex */
  sex: z.string().nullable().optional(),
  /** Phone */
  phone: z.string().nullable().optional(),
  /** Email */
  email: z.string().nullable().optional(),
  /** Document Type */
  doc_type: z.string().nullable().optional(),
  /** Document Number */
  doc_number: z.string().nullable().optional(),
  /** Address */
  address: z.string().nullable().optional(),
  /** Id — required (number) */
  id: z.number(),
  /** Created At — required (ISO date-time) */
  created_at: z.string(),
});

export type PatientDtoParsed = z.infer<typeof PatientDtoSchema>;

export default PatientDtoSchema;
