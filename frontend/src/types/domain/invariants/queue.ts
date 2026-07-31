/**
 * Queue domain invariants.
 *
 * Business rules:
 * 1. Cannot call a queue entry that is already completed/served/skipped/cancelled (terminal)
 * 2. Cannot mark as served if not in 'in_cabinet' or 'in_service' state first
 * 3. Cannot skip an entry that is already being served (in_service/in_cabinet)
 * 4. Queue entry must have a patient reference (patient_id or patient_name)
 */

import type { QueueEntry, QueueEntryStatus } from '../queue';
import type { InvariantResult } from './base';
import { ok, fail } from './base';

/**
 * Terminal queue statuses — cannot transition out of these.
 */
const TERMINAL_QUEUE_STATUSES: ReadonlySet<QueueEntryStatus> = new Set([
  'completed',
  'served',
  'skipped',
  'cancelled',
]);

/**
 * Check if a queue status is terminal.
 */
export function isTerminalQueueStatus(status: QueueEntryStatus | undefined): boolean {
  return status != null && TERMINAL_QUEUE_STATUSES.has(status);
}

/**
 * Invariant: Queue entry can be called (moved to 'called' status).
 *
 * Violations:
 * - Entry is in a terminal status (completed/served/skipped/cancelled)
 */
export function checkQueueEntryCanBeCalled(entry: Pick<QueueEntry, 'status'>): InvariantResult {
  if (isTerminalQueueStatus(entry.status)) {
    return fail('queue.call_terminal', `Cannot call a queue entry with terminal status '${entry.status}'.`);
  }
  return ok();
}

/**
 * Invariant: Queue entry can be marked as served.
 *
 * Violations:
 * - Entry is not in 'in_cabinet' or 'in_service' state (must be seen first)
 * - Entry is in a terminal status
 */
export function checkQueueEntryCanBeServed(entry: Pick<QueueEntry, 'status'>): InvariantResult {
  if (isTerminalQueueStatus(entry.status)) {
    return fail('queue.serve_terminal', `Cannot serve a queue entry with terminal status '${entry.status}'.`);
  }
  if (entry.status !== 'in_cabinet' && entry.status !== 'in_service') {
    return fail('queue.serve_not_in_service', `Cannot serve a queue entry that is not in service (current: '${entry.status}').`);
  }
  return ok();
}

/**
 * Invariant: Queue entry can be skipped.
 *
 * Violations:
 * - Entry is already being served (in_service/in_cabinet) — cannot skip a patient being seen
 * - Entry is in a terminal status
 */
export function checkQueueEntryCanBeSkipped(entry: Pick<QueueEntry, 'status'>): InvariantResult {
  if (isTerminalQueueStatus(entry.status)) {
    return fail('queue.skip_terminal', `Cannot skip a queue entry with terminal status '${entry.status}'.`);
  }
  if (entry.status === 'in_service' || entry.status === 'in_cabinet') {
    return fail('queue.skip_in_service', 'Cannot skip a queue entry that is currently being served.');
  }
  return ok();
}

/**
 * Invariant: Queue entry has a patient reference.
 */
export function checkQueueEntryHasPatient(entry: Pick<QueueEntry, 'patient_id' | 'patient_name'>): InvariantResult {
  if (entry.patient_id == null && !entry.patient_name) {
    return fail('queue.missing_patient', 'Queue entry must reference a patient (patient_id or patient_name).');
  }
  return ok();
}

/**
 * Throwing variants.
 */
import { InvariantViolationError } from './base';

export function assertQueueEntryCanBeCalled(entry: Pick<QueueEntry, 'status'>): void {
  const result = checkQueueEntryCanBeCalled(entry);
  if (!result.ok) throw new InvariantViolationError(result.invariant, result.message);
}

export function assertQueueEntryCanBeServed(entry: Pick<QueueEntry, 'status'>): void {
  const result = checkQueueEntryCanBeServed(entry);
  if (!result.ok) throw new InvariantViolationError(result.invariant, result.message);
}

export function assertQueueEntryCanBeSkipped(entry: Pick<QueueEntry, 'status'>): void {
  const result = checkQueueEntryCanBeSkipped(entry);
  if (!result.ok) throw new InvariantViolationError(result.invariant, result.message);
}

export { InvariantViolationError } from './base';
