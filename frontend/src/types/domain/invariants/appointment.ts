/**
 * Appointment domain invariants.
 *
 * Business rules:
 * 1. Cannot complete an appointment that is already completed (terminal state)
 * 2. Cannot complete an appointment that is cancelled (terminal state)
 * 3. Cannot cancel an appointment that is already completed (terminal state)
 * 4. Appointment must have a patient_id (cannot reference null patient)
 * 5. Payment amount must be >= 0 (if present)
 */

import type { Appointment } from '../clinic';
import type { InvariantResult } from './base';
import { ok, fail } from './base';

/**
 * Check if an appointment status is terminal (cannot transition further).
 *
 * Terminal states: completed, cancelled, no_show, served
 */
export function isTerminalAppointmentStatus(status: string | undefined): boolean {
  return status === 'completed' || status === 'cancelled' || status === 'no_show' || status === 'served';
}

/**
 * Invariant: Appointment can be completed.
 *
 * Violations:
 * - Status is already 'completed' (cannot complete twice)
 * - Status is 'cancelled' (cannot complete a cancelled appointment)
 * - Status is 'no_show' (cannot complete a no-show)
 */
export function checkAppointmentCanBeCompleted(appointment: Pick<Appointment, 'status'>): InvariantResult {
  const status = appointment.status;
  if (status === 'completed') {
    return fail('appointment.completed_twice', 'Appointment is already completed — cannot complete twice.');
  }
  if (status === 'cancelled') {
    return fail('appointment.complete_cancelled', 'Cannot complete a cancelled appointment.');
  }
  if (status === 'no_show') {
    return fail('appointment.complete_no_show', 'Cannot complete a no-show appointment.');
  }
  return ok();
}

/**
 * Invariant: Appointment can be cancelled.
 *
 * Violations:
 * - Status is 'completed' (cannot cancel a completed appointment)
 */
export function checkAppointmentCanBeCancelled(appointment: Pick<Appointment, 'status'>): InvariantResult {
  if (appointment.status === 'completed') {
    return fail('appointment.cancel_completed', 'Cannot cancel a completed appointment.');
  }
  return ok();
}

/**
 * Invariant: Appointment has a valid patient reference.
 *
 * Violations:
 * - patient_id is null/undefined/empty
 */
export function checkAppointmentHasPatient(appointment: { patient_id?: string | number | null }): InvariantResult {
  if (appointment.patient_id == null || appointment.patient_id === '') {
    return fail('appointment.missing_patient', 'Appointment must reference a patient.');
  }
  return ok();
}

/**
 * Invariant: Appointment payment amount is non-negative (if present).
 */
export function checkAppointmentPaymentAmount(appointment: Pick<Appointment, 'payment_amount'>): InvariantResult {
  if (appointment.payment_amount != null && appointment.payment_amount < 0) {
    return fail('appointment.negative_payment', 'Payment amount cannot be negative.');
  }
  return ok();
}

/**
 * Throwing variants — for use in mappers/hooks where a violation should
 * halt the flow immediately.
 */
import { InvariantViolationError } from './base';

export function assertAppointmentCanBeCompleted(appointment: Pick<Appointment, 'status'>): void {
  const result = checkAppointmentCanBeCompleted(appointment);
  if (!result.ok) {
    throw new InvariantViolationError(result.invariant, result.message);
  }
}

export function assertAppointmentCanBeCancelled(appointment: Pick<Appointment, 'status'>): void {
  const result = checkAppointmentCanBeCancelled(appointment);
  if (!result.ok) {
    throw new InvariantViolationError(result.invariant, result.message);
  }
}

export function assertAppointmentHasPatient(appointment: { patient_id?: string | number | null }): void {
  const result = checkAppointmentHasPatient(appointment);
  if (!result.ok) {
    throw new InvariantViolationError(result.invariant, result.message);
  }
}

export { InvariantViolationError } from './base';
