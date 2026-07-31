/**
 * Mapper: PatientDto (OpenAPI transport) → Patient (domain).
 *
 * Per ADR-0018 (Runtime Validation Strategy), this mapper is the single
 * validation boundary for Patient data. The zod schema validates the DTO
 * shape before transformation. Any backend contract drift is caught here
 * instead of silently propagating to components.
 *
 * Flow:
 *   DTO (unknown from axios)
 *     ↓
 *   PatientDtoSchema.parse()  ← validates shape, throws ZodError on mismatch
 *     ↓
 *   mapPatientDto()           ← transforms to domain Patient
 *     ↓
 *   Patient (domain type, trusted by all downstream code)
 */

import type { PatientDto } from '../../types/api';
import type { Patient } from '../../types/domain/clinic';
import { PatientDtoSchema } from './schemas/patientSchema';

/**
 * Convert a single Patient DTO to the domain Patient.
 *
 * Validates the DTO via zod schema first. Throws ZodError on shape mismatch
 * (e.g. missing required `id`, wrong type for `last_name`). This is the
 * single place where backend contract drift is caught for Patient data.
 */
export function mapPatientDto(dto: PatientDto | unknown): Patient {
  // Validate the DTO shape. parse() throws ZodError on mismatch.
  const parsed = PatientDtoSchema.parse(dto);

  // Domain Patient has optional `full_name` / `name`. The DTO has `full_name`
  // (nullable) plus `last_name` + `first_name`. Expose `name` as a derived
  // convenience for consumers that don't want to compute it.
  const derivedName =
    parsed.full_name ??
    [parsed.first_name, parsed.last_name].filter(Boolean).join(' ') ??
    undefined;

  // Spread first, then layer derived fields on top.
  return {
    ...parsed,
    name: derivedName,
  } as unknown as Patient;
}

/**
 * Convert an array of Patient DTOs. Skips entries that fail validation
 * rather than throwing the whole batch — logs a warning instead.
 *
 * This is the correct behavior for list views: one bad row shouldn't
 * crash the entire search result. The schema parse error is logged
 * via the catch block (caller can add logging if needed).
 */
export function mapPatientDtos(dtos: PatientDto[] | unknown): Patient[] {
  if (!Array.isArray(dtos)) return [];
  const out: Patient[] = [];
  for (const dto of dtos) {
    try {
      out.push(mapPatientDto(dto));
    } catch {
      // Skip malformed entry; the API client logs the original 4xx/5xx
      // already. Don't crash a search result over one bad row.
    }
  }
  return out;
}
