// src/types/index.ts
// Phase 0.5 — Single re-export point for all type modules.
// Plan: JS-to-TS-Migration-Plan v3, section 0.5.6
//
// Import patterns:
//   import type { Patient } from '@/types/domain/clinic';  // domain (canonical)
//   import type { PatientDto } from '@/types';             // transport (mapper only)
//   import type { components } from '@/types/generated/api'; // ❌ forbidden (Phase 9 ESLint rule)
//
// ⚠️ DO NOT import directly from '@/types/generated/api' in app code.
//    Add re-exports here or in api.ts instead.
//
// Wave 3 note: previously this barrel did `export * from './api'`, which
// polluted the namespace with raw transport shapes that collided with
// domain names (Patient, Doctor, Appointment, etc.). The barrel now
// re-exports DTOs explicitly under their `*Dto` names so there is no
// ambiguity. Domain types live in '@/types/domain/*' and should be
// imported directly from there.

// ============================================================================
// Generated DTOs (read-only) — re-exported from api.ts with `*Dto` suffix
// ============================================================================
export type {
  UserDto,
  PatientDto,
  PatientCreateDto,
  PatientUpdateDto,
  PatientProfileOutDto,
  PatientSearchResultDto,
  AppointmentDto,
  AppointmentCreateDto,
  AppointmentUpdateDto,
  AppointmentUpcomingOutDto,
  AppointmentDoctorInfoResponseDto,
  ServiceDto,
  ServiceCreateDto,
  ServiceUpdateDto,
  DepartmentDto,
  DepartmentListResponseDto,
  DepartmentUpdateDto,
  DoctorDto,
  DoctorInfoResponseDto,
  DoctorListResponseDto,
  VisitDto,
  VisitCreateDto,
  VisitWithServicesDto,
  EMRDto,
  EMRCreateDto,
  EMRSaveRequestDto,
  EMRRecordOutDto,
  EMRHistoryOutDto,
  EMRVersionOutDto,
  LabReportDto,
  LabReportCreateDto,
  LabReportUpdateDto,
  LabOrderDto,
  LabOrderCreateDto,
  LabResultDto,
  LoginRequest,
  LoginResponseRaw,
  JSONLoginRequest,
  JSONLoginResponse,
  TwoFactorVerifyRequestRaw,
  TwoFactorVerifyResponseRaw,
  TwoFactorSetupRequest,
  TwoFactorSetupResponse,
  TwoFactorStatusResponse,
  TwoFactorSuccessResponse,
  TwoFactorDisableRequest,
  TwoFactorBackupCodesResponse,
  TwoFactorRecoveryRequest,
  TwoFactorRecoveryResponse,
  RefreshTokenRequestRaw,
  RefreshTokenResponseRaw,
  AuthStatusResponse,
  CSRFTokenResponse,
  QueueEntryResponse,
  QueueGroupInfo,
  QueueGroupsResponse,
  QueuePositionResponse,
  QueueTokenResponse,
  QueueStatusNotificationRequest,
  QueueJoinRequest,
  QueueJoinResponse,
  PaymentHistoryItem,
  PaymentInitRequest,
  PaymentInitResponse,
  PaymentStatusResponse,
  PaymentMethodDto,
  PayMeConfig,
  ClickConfig,
  PaymentProviderOut,
  PaymentProviderSettings,
  NotificationInboxItem,
  NotificationInboxResponse,
  NotificationResponse,
  NotificationUnreadCountResponse,
  NotificationTemplate,
  ChatMessageResponse,
  ChatSessionResponse,
  MessageOut,
  ConversationOut,
  PaginatedResponse,
  HTTPValidationError,
  ValidationError,
} from './api';
export type { components, paths, operations } from './generated/api';

// ============================================================================
// Manual — backend SSOT mirrors
// ============================================================================
// Wave G6: removed `export * from './auth'` and `export * from './auth-store'`.
// These were legacy shims. Login-flow types now live in types/domain/auth.ts
// (re-exported via `export * from './domain/auth'` below). AuthStore
// interface lives in types/auth-store.ts but is no longer barrel-exported —
// import directly from '@/types/auth-store' if needed.
export * from './roles';
export * from './domain/auth';
export * from './auth-mapper';
export * from './route';

// ============================================================================
// Manual — frontend-only UI types
// ============================================================================
// ADR-0016: types/ui.ts was deleted (zero importers — all UI types like
// FormState/ThemeState/ModalState were declared locally in components).
// If new cross-cutting UI types are needed, create a new file under types/
// and add the re-export here.

// ============================================================================
// Manual — i18next type augmentation
// ============================================================================
// audit/phase-5a, BS-10: removed `export type { TranslateFunction } from './i18n'`.
// The `types/i18n.ts` file was dead code (zero importers) — its `declare module`
// augmentations were never loaded as a side-effect, and `TranslateFunction` had
// zero external consumers. The live i18n type augmentation lives in
// `src/types/react-i18next-override.d.ts` (ambient). See that file for the
// current override policy.

// ============================================================================
// Manual — feature-based domain types
// ============================================================================
export * from './features/emr';
export * from './features/queue';
export * from './features/telegram';
export * from './features/lab';
export * from './features/payment';
export * from './features/chat';
export * from './features/notification';
export * from './features/wizard';
export * from './features/analytics';
export * from './features/admin';
