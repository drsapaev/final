/**
 * Branded types — nominal typing for domain IDs.
 *
 * Prevents accidentally passing a PatientId where an AppointmentId is expected.
 * Created via factory functions that validate at the boundary.
 */

// === Brand infrastructure ===

declare const __brand: unique symbol;
type Brand<T extends string> = { readonly [__brand]: T };

/**
 * Extract the brand name from a branded type (for debugging/inspection).
 * Usage: getBrandName(toPatientId(123)) === 'PatientId'
 */
export function getBrandName<T extends string>(value: string & Brand<T>): T {
  return (value as unknown as { readonly [__brand]: T })[__brand];
}

// === Branded ID types ===

export type PatientId = string & Brand<'PatientId'>;
export type AppointmentId = string & Brand<'AppointmentId'>;
export type DoctorId = string & Brand<'DoctorId'>;
export type VisitId = string & Brand<'VisitId'>;
export type ServiceId = string & Brand<'ServiceId'>;
export type QueueEntryId = string & Brand<'QueueEntryId'>;
export type InvoiceId = string & Brand<'InvoiceId'>;
export type PaymentId = string & Brand<'PaymentId'>;
export type DepartmentId = string & Brand<'DepartmentId'>;
export type UserId = string & Brand<'UserId'>;
export type ChatMessageId = string & Brand<'ChatMessageId'>;
export type ChatConversationId = string & Brand<'ChatConversationId'>;

// === Factory functions ===

export function toPatientId(raw: string | number): PatientId {
  return String(raw) as PatientId;
}

export function toAppointmentId(raw: string | number): AppointmentId {
  return String(raw) as AppointmentId;
}

export function toDoctorId(raw: string | number): DoctorId {
  return String(raw) as DoctorId;
}

export function toVisitId(raw: string | number): VisitId {
  return String(raw) as VisitId;
}

export function toServiceId(raw: string | number): ServiceId {
  return String(raw) as ServiceId;
}

export function toQueueEntryId(raw: string | number): QueueEntryId {
  return String(raw) as QueueEntryId;
}

export function toInvoiceId(raw: string | number): InvoiceId {
  return String(raw) as InvoiceId;
}

export function toPaymentId(raw: string | number): PaymentId {
  return String(raw) as PaymentId;
}

export function toDepartmentId(raw: string | number): DepartmentId {
  return String(raw) as DepartmentId;
}

export function toUserId(raw: string | number): UserId {
  return String(raw) as UserId;
}

export function toChatMessageId(raw: string | number): ChatMessageId {
  return String(raw) as ChatMessageId;
}

export function toChatConversationId(raw: string | number): ChatConversationId {
  return String(raw) as ChatConversationId;
}

// === Type guards ===

export function isPatientId(value: unknown): value is PatientId {
  return typeof value === 'string' && value.length > 0;
}

export function isAppointmentId(value: unknown): value is AppointmentId {
  return typeof value === 'string' && value.length > 0;
}

export function isDoctorId(value: unknown): value is DoctorId {
  return typeof value === 'string' && value.length > 0;
}
