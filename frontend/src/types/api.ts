// src/types/api.ts
// Phase 0.5 — Re-export + aliases from generated/api.ts.
// Plan: JS-to-TS-Migration-Plan v3, section 0.5.2
//
// Frontend code should import from '@/types/api' (this file), NOT from
// '@/types/generated/api' directly. ESLint rule `no-restricted-imports`
// will be added in Phase 9 to enforce this.
//
// SSOT: backend/openapi.json (auto-generated via openapi-typescript)
//
// ============================================================================
// ARCHITECTURE — DTO vs Domain types (per code review 2026-07-17)
// ============================================================================
//
// This file re-exports the RAW transport shapes from OpenAPI as `*Raw` aliases
// (LoginResponseRaw, TwoFactorVerifyResponseRaw, etc.). They reflect the
// backend's transport contract one-to-one — including all nullable fields
// and the flat superset shape that Pydantic produces.
//
// For DOMAIN types that encode business invariants (e.g. the 2FA-flow
// invariant from AUTHENTICATION_LAWS_FOR_AI.md ЗАКОН 2), see:
//   - src/types/auth.ts        — domain types (discriminated unions)
//   - src/types/auth-mapper.ts — runtime validators that convert DTO → domain
//
// Rule: generated files in src/types/generated/ are READ-ONLY. Domain
// invariants are NEVER baked into generated types — they are enforced by
// mappers at the boundary.
// ============================================================================

import type { components } from './generated/api';

type Schemas = components['schemas'];

// ============================================================================
// Transport DTOs (from OpenAPI)
// ============================================================================
// NOTE (Wave 3): Domain entity names (Patient, Doctor, Appointment, etc.) are
// suffixed with `Dto` here to avoid collision with the canonical domain
// types in src/types/domain/*.ts. Components MUST consume the domain types,
// not these DTOs — mapping happens at the API boundary (Wave 4 will
// formalize this with src/types/api-mapper.ts).
//
// The `*Dto` suffix is a deliberate signal: "this is the raw transport shape,
// a mapper must convert it to the domain type before the UI sees it".

export type UserDto = Schemas['UserResponse'];
export type PatientDto = Schemas['Patient'];
export type PatientCreateDto = Schemas['PatientCreate'];
export type PatientUpdateDto = Schemas['PatientUpdate'];
export type PatientProfileOutDto = Schemas['PatientProfileOut'];
export type PatientSearchResultDto = Schemas['PatientSearchResult'];

export type AppointmentDto = Schemas['Appointment'];
export type AppointmentCreateDto = Schemas['AppointmentCreate'];
export type AppointmentUpdateDto = Schemas['AppointmentUpdate'];
export type AppointmentUpcomingOutDto = Schemas['AppointmentUpcomingOut'];
export type AppointmentDoctorInfoResponseDto = Schemas['AppointmentDoctorInfoResponse'];

export type ServiceDto = Schemas['ServiceOut'];
export type ServiceCreateDto = Schemas['ServiceCreate'];
export type ServiceUpdateDto = Schemas['ServiceUpdate'];

export type DepartmentDto = Schemas['DepartmentInfoResponse'];
export type DepartmentListResponseDto = Schemas['DepartmentListResponse'];
export type DepartmentUpdateDto = Schemas['DepartmentUpdate'];

export type DoctorDto = Schemas['app__schemas__clinic__DoctorOut'];
export type DoctorInfoResponseDto = Schemas['DoctorInfoResponse'];
export type DoctorListResponseDto = Schemas['DoctorListResponse'];

export type VisitDto = Schemas['VisitOut'];
export type VisitCreateDto = Schemas['VisitCreate'];
export type VisitWithServicesDto = Schemas['VisitWithServices'];

export type EMRDto = Schemas['EMR'];
export type EMRCreateDto = Schemas['EMRCreate'];
export type EMRSaveRequestDto = Schemas['EMRSaveRequest'];
export type EMRRecordOutDto = Schemas['EMRRecordOut'];
export type EMRHistoryOutDto = Schemas['EMRHistoryOut'];
export type EMRVersionOutDto = Schemas['EMRVersionOut'];

export type LabReportDto = Schemas['LabReportInstanceOut'];
export type LabReportCreateDto = Schemas['LabReportInstanceCreate'];
export type LabReportUpdateDto = Schemas['LabReportInstanceUpdate'];
export type LabOrderDto = Schemas['LabOrderOut'];
export type LabOrderCreateDto = Schemas['LabOrderCreate'];
export type LabResultDto = Schemas['LabResultOut'];

// ============================================================================
// Auth (raw shapes from OpenAPI — see auth.ts for 2FA-discriminated wrappers)
// ============================================================================

export type LoginRequest = Schemas['LoginRequest'];
export type LoginResponseRaw = Schemas['LoginResponse'];
export type JSONLoginRequest = Schemas['JSONLoginRequest'];
export type JSONLoginResponse = Schemas['JSONLoginResponse'];

export type TwoFactorVerifyRequestRaw = Schemas['TwoFactorVerifyRequest'];
export type TwoFactorVerifyResponseRaw = Schemas['TwoFactorVerifyResponse'];
export type TwoFactorSetupRequest = Schemas['TwoFactorSetupRequest'];
export type TwoFactorSetupResponse = Schemas['TwoFactorSetupResponse'];
export type TwoFactorStatusResponse = Schemas['TwoFactorStatusResponse'];
export type TwoFactorSuccessResponse = Schemas['TwoFactorSuccessResponse'];
export type TwoFactorDisableRequest = Schemas['TwoFactorDisableRequest'];
export type TwoFactorBackupCodesResponse = Schemas['TwoFactorBackupCodesResponse'];
export type TwoFactorRecoveryRequest = Schemas['TwoFactorRecoveryRequest'];
export type TwoFactorRecoveryResponse = Schemas['TwoFactorRecoveryResponse'];

export type RefreshTokenRequestRaw = Schemas['RefreshTokenRequest'];
export type RefreshTokenResponseRaw = Schemas['RefreshTokenResponse'];
export type AuthStatusResponse = Schemas['AuthStatusResponse'];
export type CSRFTokenResponse = Schemas['CSRFTokenResponse'];

// ============================================================================
// Queue (online queue + clinic queue)
// ============================================================================

export type QueueEntryResponse = Schemas['QueueEntryResponse'];
export type QueueGroupInfo = Schemas['QueueGroupInfo'];
export type QueueGroupsResponse = Schemas['QueueGroupsResponse'];
export type QueuePositionResponse = Schemas['QueuePositionResponse'];
export type QueueTokenResponse = Schemas['QueueTokenResponse'];
export type QueueStatusNotificationRequest = Schemas['QueueStatusNotificationRequest'];
export type QueueJoinRequest = Schemas['app__api__v1__endpoints__queue__QueueJoinRequest'];
export type QueueJoinResponse = Schemas['app__api__v1__endpoints__queue__QueueJoinResponse'];

// ============================================================================
// Payments
// ============================================================================

export type PaymentHistoryItem = Schemas['PaymentHistoryItem'];
export type PaymentInitRequest = Schemas['PaymentInitRequest'];
export type PaymentInitResponse = Schemas['PaymentInitResponse'];
export type PaymentStatusResponse = Schemas['PaymentStatusResponse'];
export type PaymentMethodDto = Schemas['PaymentMethod'];
export type PayMeConfig = Schemas['PayMeConfig'];
export type ClickConfig = Schemas['ClickConfig'];
export type PaymentProviderOut = Schemas['PaymentProviderOut'];
export type PaymentProviderSettings = Schemas['PaymentProviderSettings'];

// ============================================================================
// Notifications
// ============================================================================

export type NotificationInboxItem = Schemas['NotificationInboxItem'];
export type NotificationInboxResponse = Schemas['NotificationInboxResponse'];
export type NotificationResponse = Schemas['NotificationResponse'];
export type NotificationUnreadCountResponse = Schemas['NotificationUnreadCountResponse'];
export type NotificationTemplate = Schemas['NotificationTemplate'];

// ============================================================================
// Chat / Messages
// ============================================================================

export type ChatMessageResponse = Schemas['ChatMessageResponse'];
export type ChatSessionResponse = Schemas['ChatSessionResponse'];
export type MessageOut = Schemas['MessageOut'];
export type ConversationOut = Schemas['ConversationOut'];

// ============================================================================
// Generic helpers (re-export from generated; consumers can also import directly)
// ============================================================================

export type PaginatedResponse<T> = {
  data: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

export type HTTPValidationError = Schemas['HTTPValidationError'];
export type ValidationError = Schemas['ValidationError'];

// Re-export the full components/paths/operations types for advanced consumers
// (e.g. when a hook needs to type an axios response with the full operation shape).
export type { components, paths, operations } from './generated/api';
