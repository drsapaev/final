/**
 * Barrel export for domain invariants.
 */

export { InvariantViolationError, ok, fail } from './base';
export type { InvariantResult } from './base';

export * as appointmentInvariants from './appointment';
export * as billingInvariants from './billing';
export * as queueInvariants from './queue';
export * as emrInvariants from './emr';

// Also export individual functions for direct import
export {
  isTerminalAppointmentStatus,
  checkAppointmentCanBeCompleted,
  checkAppointmentCanBeCancelled,
  checkAppointmentHasPatient,
  checkAppointmentPaymentAmount,
  assertAppointmentCanBeCompleted,
  assertAppointmentCanBeCancelled,
  assertAppointmentHasPatient,
} from './appointment';

export {
  checkPaymentAmount,
  checkInvoiceCanBePaid,
  checkInvoicePaidDoesNotExceedTotal,
  checkPaymentCanBeAppliedToInvoice,
  checkRefundDoesNotExceedPaid,
  assertPaymentAmount,
  assertInvoiceCanBePaid,
  assertRefundDoesNotExceedPaid,
} from './billing';

export {
  isTerminalQueueStatus,
  checkQueueEntryCanBeCalled,
  checkQueueEntryCanBeServed,
  checkQueueEntryCanBeSkipped,
  checkQueueEntryHasPatient,
  assertQueueEntryCanBeCalled,
  assertQueueEntryCanBeServed,
  assertQueueEntryCanBeSkipped,
} from './queue';

export {
  checkEmrCanBeSigned,
  checkEmrAmendmentHasReason,
  checkEmrRowVersionNotStale,
  assertEmrCanBeSigned,
  assertEmrAmendmentHasReason,
} from './emr';
