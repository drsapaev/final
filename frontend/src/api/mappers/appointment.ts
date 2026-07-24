/**
 * Mapper: AppointmentDto (OpenAPI transport) → Appointment (domain).
 *
 * The domain Appointment is intentionally permissive (most fields optional,
 * index signature for backend extras) because the frontend consumes multiple
 * appointment-like shapes (queue entries, grouped records, etc.) through the
 * same component code paths. The mapper therefore normalizes the canonical
 * backend Appointment DTO into the domain shape and lets extras ride along.
 *
 * Note on `null` vs `undefined`: OpenAPI marks optional backend fields as
 * `T | null`. The domain type uses `T | undefined` (idiomatic TS). The
 * spread `...rest` carries these `null` values through unchanged; the
 * domain index signature `[key: string]: unknown` accepts both. Consumers
 * that need to disambiguate should check `== null` (covers both).
 */

import type { AppointmentDto } from '../../types/api';
import type { Appointment } from '../../types/domain/clinic';

export function mapAppointmentDto(dto: AppointmentDto): Appointment {
  if (dto == null || typeof dto !== 'object') {
    throw new Error('[mapAppointmentDto] expected object, got ' + typeof dto);
  }
  if (dto.id == null) {
    throw new Error('[mapAppointmentDto] missing required field `id`');
  }

  // Normalize `services: string[]` (DTO) → `services: Array<{code}>` (domain).
  // Keep service_codes as a separate convenience field the domain allows.
  // We strip `services` from the rest spread so the normalized array wins.
  const { services: _services, ...rest } = dto;
  const serviceCodes = _services ?? [];
  const services = serviceCodes.map((code) => ({ code, name: code }));

  // Spread rest first, then add normalized fields on top. This avoids
  // TS2783 ("specified more than once") and lets the domain index signature
  // absorb the `null`-typed DTO fields without complaint.
  return {
    ...rest,
    service_codes: serviceCodes,
    services,
  } as Appointment;
}

export function mapAppointmentDtos(dtos: AppointmentDto[] | unknown): Appointment[] {
  if (!Array.isArray(dtos)) return [];
  const out: Appointment[] = [];
  for (const dto of dtos) {
    try {
      out.push(mapAppointmentDto(dto as AppointmentDto));
    } catch {
      // skip malformed
    }
  }
  return out;
}
