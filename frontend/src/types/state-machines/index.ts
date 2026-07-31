/**
 * Barrel export for state machine transition validators.
 */

export {
  isTransitionAllowed,
  applyTransition,
  isTerminalStatus,
  getReachableStatuses,
  getAllStatuses,
} from './base';

export {
  isValidAppointmentTransition,
  applyAppointmentTransition,
  isTerminalAppointmentStatus,
  getReachableAppointmentStatuses,
  getAllAppointmentStatuses,
  ALLOWED_APPOINTMENT_TRANSITIONS,
} from './appointment';

export {
  isValidQueueTransition,
  applyQueueTransition,
  isTerminalQueueStatus,
  getReachableQueueStatuses,
  getAllQueueStatuses,
  ALLOWED_QUEUE_TRANSITIONS,
} from './queue';

export {
  isValidPaymentTransition,
  applyPaymentTransition,
  isTerminalPaymentStatus,
  getReachablePaymentStatuses,
  getAllPaymentStatuses,
  ALLOWED_PAYMENT_TRANSITIONS,
  isValidRefundTransition,
  applyRefundTransition,
  isTerminalRefundStatus,
  getReachableRefundStatuses,
  getAllRefundStatuses,
  ALLOWED_REFUND_TRANSITIONS,
} from './payment';

export {
  isValidEmrTransition,
  applyEmrTransition,
  isTerminalEmrStatus,
  getReachableEmrStatuses,
  getAllEmrStatuses,
  ALLOWED_EMR_TRANSITIONS,
} from './emr';
