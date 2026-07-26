/**
 * Mappers that convert raw OpenAPI DTOs (from src/types/api.ts, suffix *Dto)
 * into canonical domain types (from src/types/domain/*).
 *
 * Architecture (per Wave 4 of Domain Adoption 100%):
 *
 *     Server JSON  →  DTO (types/api.ts)  →  mapper (this dir)  →  Domain (types/domain/*)
 *                                                                    ↑
 *                                                                    │
 *                                                            React components
 *
 * Rules:
 *   1. Components MUST NOT import from src/types/api.ts or src/types/generated/api.ts.
 *      They import only from src/types/domain/*.
 *   2. src/api/*.ts functions MUST return domain types, not DTOs or `any`.
 *      They achieve this by calling a mapper from this directory.
 *   3. Mappers are pure functions. They never throw on extra backend fields —
 *      the domain index signature `[key: string]: unknown` lets extras ride
 *      along. They only normalize field names where DTO and domain disagree.
 *   4. Mappers MAY throw if a hard invariant is violated (e.g. missing `id`).
 *
 * Pattern (Patient example):
 *
 *     // src/api/patients.ts
 *     import { mapPatientDto } from './mappers';
 *     export async function getPatient(id): Promise<Patient> {
 *       const resp = await api.get<PatientDto>(`/patients/${id}`);
 *       return mapPatientDto(resp.data);
 *     }
 */

export * from './patient';
export * from './appointment';
export * from './doctor';
export * from './billing';
export * from './queue';
export * from './chat';
