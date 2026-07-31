/**
 * Queue state machine — transition validators.
 *
 * State diagram:
 *
 *   waiting ──▶ called ──▶ in_service ──▶ in_cabinet ──▶ served ──▶ completed
 *      │          │           │              │
 *      │          │           ├──▶ completed ─┘
 *      │          ├──▶ in_progress (alias for in_service in some flows)
 *      │          ├──▶ skipped (terminal)
 *      │          ├──▶ cancelled (terminal)
 *      ├──▶ skipped (terminal)
 *      ├──▶ cancelled (terminal)
 *
 * Terminal states: completed, served (→ completed), skipped, cancelled
 */

import type { QueueEntryStatus } from '../domain/queue';
import {
  isTransitionAllowed,
  applyTransition,
  isTerminalStatus,
  getReachableStatuses,
  getAllStatuses,
} from './base';

const ALLOWED_QUEUE_TRANSITIONS: Record<QueueEntryStatus, readonly QueueEntryStatus[]> = {
  waiting: ['called', 'skipped', 'cancelled'],
  called: ['in_service', 'in_cabinet', 'skipped', 'cancelled'],
  in_service: ['in_cabinet', 'completed', 'cancelled'],
  in_cabinet: ['served', 'completed'],
  served: ['completed'],
  completed: [], // terminal
  skipped: [], // terminal
  cancelled: [], // terminal
};

export function isValidQueueTransition(
  from: QueueEntryStatus,
  to: QueueEntryStatus,
): boolean {
  return isTransitionAllowed(ALLOWED_QUEUE_TRANSITIONS, from, to);
}

export function applyQueueTransition<T extends { status: QueueEntryStatus }>(
  state: T,
  next: QueueEntryStatus,
): T {
  return applyTransition(ALLOWED_QUEUE_TRANSITIONS, state, next, 'QueueSM');
}

export function isTerminalQueueStatus(status: QueueEntryStatus): boolean {
  return isTerminalStatus(ALLOWED_QUEUE_TRANSITIONS, status);
}

export function getReachableQueueStatuses(start: QueueEntryStatus): Set<QueueEntryStatus> {
  return getReachableStatuses(ALLOWED_QUEUE_TRANSITIONS, start);
}

export function getAllQueueStatuses(): QueueEntryStatus[] {
  return getAllStatuses(ALLOWED_QUEUE_TRANSITIONS);
}

export { ALLOWED_QUEUE_TRANSITIONS };
