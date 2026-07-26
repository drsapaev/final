/**
 * Mapper: DoctorDto (OpenAPI transport) → Doctor (domain).
 *
 * DoctorDto is `app__schemas__clinic__DoctorOut` from OpenAPI — a flat row
 * from the doctors table. The domain Doctor adds optional UI-facing fields
 * (full_name, specialty_display, is_active alias) that may come from joins
 * in other endpoints; the mapper normalizes the canonical fields and lets
 * extras ride along via the index signature.
 *
 * The one real transformation: `price_default` arrives as a string (Decimal
 * from Python) but the domain expects `number`. We parse it here so every
 * consumer gets a ready-to-use number.
 */

import type { DoctorDto } from '../../types/api';
import type { Doctor } from '../../types/domain/clinic';

export function mapDoctorDto(dto: DoctorDto): Doctor {
  if (dto == null || typeof dto !== 'object') {
    throw new Error('[mapDoctorDto] expected object, got ' + typeof dto);
  }
  if (dto.id == null) {
    throw new Error('[mapDoctorDto] missing required field `id`');
  }

  // price_default comes as a string (Decimal) from the backend; parse to number.
  // NaN becomes undefined so consumers can safely check `if (doctor.price_default)`.
  const priceDefaultRaw = dto.price_default;
  const priceDefaultNum =
    priceDefaultRaw != null && priceDefaultRaw !== ''
      ? Number(priceDefaultRaw)
      : undefined;
  const priceDefault =
    Number.isFinite(priceDefaultNum) ? priceDefaultNum : undefined;

  // Spread first (carries full_name, department_name from joins), then layer
  // the normalized fields on top. Avoids TS2783 ("specified more than once").
  return {
    ...dto,
    is_active: dto.active,
    price_default: priceDefault,
  } as Doctor;
}

export function mapDoctorDtos(dtos: DoctorDto[] | unknown): Doctor[] {
  if (!Array.isArray(dtos)) return [];
  const out: Doctor[] = [];
  for (const dto of dtos) {
    try {
      out.push(mapDoctorDto(dto as DoctorDto));
    } catch {
      // skip malformed
    }
  }
  return out;
}
