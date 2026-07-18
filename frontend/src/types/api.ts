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
// Domain entities (from OpenAPI)
// ============================================================================

export type User = Schemas['UserResponse'];
export type Patient = Schemas['Patient'];
export type PatientCreate = Schemas['PatientCreate'];
export type PatientUpdate = Schemas['PatientUpdate'];
export type PatientProfileOut = Schemas['PatientProfileOut'];
export type PatientSearchResult = Schemas['PatientSearchResult'];

export type Appointment = Schemas['Appointment'];
export type AppointmentCreate = Schemas['AppointmentCreate'];
export type AppointmentUpdate = Schemas['AppointmentUpdate'];
export type AppointmentUpcomingOut = Schemas['AppointmentUpcomingOut'];
export type AppointmentDoctorInfoResponse = Schemas['AppointmentDoctorInfoResponse'];

export type Service = Schemas['ServiceOut'];
export type ServiceCreate = Schemas['ServiceCreate'];
export type ServiceUpdate = Schemas['ServiceUpdate'];

export type Department = Schemas['DepartmentInfoResponse'];
export type DepartmentListResponse = Schemas['DepartmentListResponse'];
export type DepartmentUpdate = Schemas['DepartmentUpdate'];

export type Doctor = Schemas['app__schemas__clinic__DoctorOut'];
export type DoctorInfoResponse = Schemas['DoctorInfoResponse'];
export type DoctorListResponse = Schemas['DoctorListResponse'];

export type Visit = Schemas['VisitOut'];
export type VisitCreate = Schemas['VisitCreate'];
export type VisitWithServices = Schemas['VisitWithServices'];

export type EMR = Schemas['EMR'];
export type EMRCreate = Schemas['EMRCreate'];
export type EMRSaveRequest = Schemas['EMRSaveRequest'];
export type EMRRecordOut = Schemas['EMRRecordOut'];
export type EMRHistoryOut = Schemas['EMRHistoryOut'];
export type EMRVersionOut = Schemas['EMRVersionOut'];

export type LabReport = Schemas['LabReportInstanceOut'];
export type LabReportCreate = Schemas['LabReportInstanceCreate'];
export type LabReportUpdate = Schemas['LabReportInstanceUpdate'];
export type LabOrder = Schemas['LabOrderOut'];
export type LabOrderCreate = Schemas['LabOrderCreate'];
export type LabResult = Schemas['LabResultOut'];

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
export type PaymentMethod = Schemas['PaymentMethod'];
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
