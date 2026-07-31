/**
 * EMR workflow state machine — transition validators.
 *
 * Extends ADR-0017 pattern to the EMR reducer state machine.
 *
 * State diagram (from types/features/emr.ts EmrStatus):
 *
 *   idle ──▶ loading ──▶ idle (loaded)
 *    │        │
 *    │        ├──▶ error
 *    │        └──▶ conflict (409 from backend)
 *    │
 *    ├──▶ saving ──▶ idle (saved)
 *    │      │
 *    │      ├──▶ error
 *    │      └──▶ conflict (concurrent edit)
 *    │
 *    ├──▶ error ──▶ saving (retry) / idle (reset)
 *    └──▶ conflict ──▶ saving (resolve) / idle (discard)
 *
 * Terminal: none — all states can transition back to idle.
 * This is a workflow machine, not a lifecycle machine.
 */

import type { EmrStatus } from '../features/emr';
import {
  isTransitionAllowed,
  applyTransition,
  isTerminalStatus,
  getReachableStatuses,
  getAllStatuses,
} from './base';

const ALLOWED_EMR_TRANSITIONS: Record<EmrStatus, readonly EmrStatus[]> = {
  idle: ['loading', 'saving'],
  loading: ['idle', 'error', 'conflict'],
  saving: ['idle', 'error', 'conflict'],
  error: ['idle', 'saving'], // retry or reset
  conflict: ['idle', 'saving'], // resolve or discard
};

export function isValidEmrTransition(
  from: EmrStatus,
  to: EmrStatus,
): boolean {
  return isTransitionAllowed(ALLOWED_EMR_TRANSITIONS, from, to);
}

export function applyEmrTransition<T extends { status: EmrStatus }>(
  state: T,
  next: EmrStatus,
): T {
  return applyTransition(ALLOWED_EMR_TRANSITIONS, state, next, 'EmrSM');
}

export function isTerminalEmrStatus(status: EmrStatus): boolean {
  return isTerminalStatus(ALLOWED_EMR_TRANSITIONS, status);
}

export function getReachableEmrStatuses(start: EmrStatus): Set<EmrStatus> {
  return getReachableStatuses(ALLOWED_EMR_TRANSITIONS, start);
}

export function getAllEmrStatuses(): EmrStatus[] {
  return getAllStatuses(ALLOWED_EMR_TRANSITIONS);
}

export { ALLOWED_EMR_TRANSITIONS };
