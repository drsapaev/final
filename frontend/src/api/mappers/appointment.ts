/**
 * Mapper: AppointmentDto (OpenAPI transport) → Appointment (domain).
 *
 * Per ADR-0018 (Runtime Validation Strategy), this mapper is the single
 * validation boundary for Appointment data. The zod schema validates the
 * DTO shape before transformation.
 */

import type { AppointmentDto } from '../../types/api';
import type { Appointment } from '../../types/domain/clinic';
import { AppointmentDtoSchema } from './schemas/appointmentSchema';

export function mapAppointmentDto(dto: AppointmentDto | unknown): Appointment {
  // Validate the DTO shape. parse() throws ZodError on mismatch.
  const parsed = AppointmentDtoSchema.parse(dto);

  // Normalize `services: string[]` (DTO) → `services: Array<{code}>` (domain).
  const { services: _services, ...rest } = parsed;
  const serviceCodes = _services ?? [];
  const services = serviceCodes.map((code) => ({ code, name: code }));

  return {
    ...rest,
    service_codes: serviceCodes,
    services,
  } as unknown as Appointment;
}

export function mapAppointmentDtos(dtos: AppointmentDto[] | unknown): Appointment[] {
  if (!Array.isArray(dtos)) return [];
  const out: Appointment[] = [];
  for (const dto of dtos) {
    try {
      out.push(mapAppointmentDto(dto));
    } catch {
      // skip malformed
    }
  }
  return out;
}
