/**
 * Mappers: queue transport shapes → domain queue types.
 *
 * The queue endpoints (/queue/*, /registrar/queues/*, /registrar/cart/*)
 * return a mix of dynamic shapes. The canonical domain types are in
 * types/domain/queue.ts: QueueSpecialist, QueueData, QrData,
 * QueueActionResponse, QueueEntry.
 *
 * Some queue endpoints return free-form dicts (queue settings, edit-delta
 * responses) that don't have a stable domain type yet — for those we
 * return `Record<string, unknown>` explicitly rather than smuggling an
 * `any` through the type system.
 */

import type {
  QueueSpecialist,
  QueueData,
  QueuePayload,
  QrData,
  QueueActionResponse,
} from '../../types/domain/queue';

type QueueDtoLike = Record<string, unknown>;

export function mapQueueSpecialistDto(dto: QueueDtoLike): QueueSpecialist {
  if (dto == null || typeof dto !== 'object') {
    throw new Error('[mapQueueSpecialistDto] expected object, got ' + typeof dto);
  }
  const id = dto.id as QueueSpecialist['id'];
  if (id == null) {
    throw new Error('[mapQueueSpecialistDto] missing required field `id`');
  }
  return { ...(dto as QueueSpecialist) };
}

export function mapQueueSpecialistDtos(dtos: unknown): QueueSpecialist[] {
  if (!Array.isArray(dtos)) return [];
  const out: QueueSpecialist[] = [];
  for (const dto of dtos) {
    try {
      out.push(mapQueueSpecialistDto(dto as QueueDtoLike));
    } catch {
      // skip malformed
    }
  }
  return out;
}

export function mapQrDataDto(dto: QueueDtoLike): QrData {
  if (dto == null || typeof dto !== 'object') {
    throw new Error('[mapQrDataDto] expected object, got ' + typeof dto);
  }
  return { ...(dto as QrData) };
}

export function mapQueueDataDto(dto: QueueDtoLike): QueueData {
  if (dto == null || typeof dto !== 'object') {
    throw new Error('[mapQueueDataDto] expected object, got ' + typeof dto);
  }
  return { ...(dto as QueueData) };
}

export function mapQueuePayloadDto(dto: QueueDtoLike): QueuePayload {
  if (dto == null || typeof dto !== 'object') {
    return { queues: [] };
  }
  return { ...(dto as QueuePayload) };
}

export function mapQueueActionResponseDto(dto: QueueDtoLike): QueueActionResponse {
  if (dto == null || typeof dto !== 'object') {
    throw new Error('[mapQueueActionResponseDto] expected object, got ' + typeof dto);
  }
  return { ...(dto as QueueActionResponse) };
}
