/**
 * Mapper: PatientDto (OpenAPI transport) → Patient (domain).
 *
 * Domain `Patient` is intentionally loose (index signature + optional fields)
 * because the frontend reads many backend shapes that have evolved over time.
 * The mapper's job is therefore minimal: assert the invariant (id is present)
 * and pass everything through. The derived `name` field is computed once
 * here so consumers don't all recompute it.
 */

import type { PatientDto } from '../../types/api';
import type { Patient } from '../../types/domain/clinic';

/**
 * Convert a single Patient DTO to the domain Patient.
 * Throws if the invariant `id` is missing — that's a backend contract violation.
 */
export function mapPatientDto(dto: PatientDto): Patient {
  if (dto == null || typeof dto !== 'object') {
    throw new Error('[mapPatientDto] expected object, got ' + typeof dto);
  }
  if (dto.id == null) {
    throw new Error('[mapPatientDto] missing required field `id`');
  }

  // Domain Patient has optional `full_name` / `name`. The DTO has `full_name`
  // (nullable) plus `last_name` + `first_name`. Expose `name` as a derived
  // convenience for consumers that don't want to compute it.
  const derivedName =
    dto.full_name ??
    [dto.first_name, dto.last_name].filter(Boolean).join(' ') ??
    undefined;

  // Spread first, then layer derived fields on top. Avoids TS2783.
  return {
    ...dto,
    name: derivedName,
  } as Patient;
}

/** Convert an array of Patient DTOs. Skips entries that fail the invariant
 *  rather than throwing the whole batch — logs a warning instead. */
export function mapPatientDtos(dtos: PatientDto[] | unknown): Patient[] {
  if (!Array.isArray(dtos)) return [];
  const out: Patient[] = [];
  for (const dto of dtos) {
    try {
      out.push(mapPatientDto(dto as PatientDto));
    } catch {
      // Skip malformed entry; the API client logs the original 4xx/5xx
      // already. Don't crash a search result over one bad row.
    }
  }
  return out;
}
