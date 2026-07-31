/**
 * Appointment state machine — transition validators.
 *
 * Extends ADR-0017 pattern to the Appointment domain.
 *
 * State diagram:
 *
 *   pending ──▶ confirmed ──▶ paid ──▶ in_visit ──▶ completed
 *      │           │           │          │            ↑
 *      │           │           │          ├──▶ in_progress ─┘
 *      │           │           │          │
 *      │           │           ├──▶ cancelled (terminal)
 *      │           │           │
 *      │           ├──▶ queued ──▶ waiting ──▶ called ──▶ in_service ──▶ in_cabinet ──▶ served ──▶ completed
 *      │           │                          │           │              │              │
 *      │           │                          │           │              ├──▶ completed ─┘
 *      │           │                          │           ├──▶ in_progress
 *      │           │                          ├──▶ skipped (terminal)
 *      │           │                          ├──▶ cancelled (terminal)
 *      │           ├──▶ no_show (terminal)
 *      │           ├──▶ cancelled (terminal)
 *      ├──▶ cancelled (terminal)
 *      ├──▶ no_show (terminal)
 *      ├──▶ paid_pending ──▶ paid
 *                     └──▶ cancelled
 *
 * Terminal states: completed, cancelled, no_show, served (served → completed only)
 */

import type { AppointmentStatus } from '../domain/clinic';
import {
  isTransitionAllowed,
  applyTransition,
  isTerminalStatus,
  getReachableStatuses,
  getAllStatuses,
} from './base';

const ALLOWED_APPOINTMENT_TRANSITIONS: Record<AppointmentStatus, readonly AppointmentStatus[]> = {
  pending: ['confirmed', 'queued', 'cancelled', 'no_show', 'paid_pending'],
  confirmed: ['paid', 'queued', 'cancelled', 'no_show', 'in_visit'],
  paid: ['in_visit', 'cancelled'],
  paid_pending: ['paid', 'cancelled'],
  queued: ['waiting', 'cancelled'],
  waiting: ['called', 'cancelled'],
  called: ['in_progress', 'cancelled'],
  in_progress: ['served', 'completed', 'cancelled'],
  in_visit: ['served', 'completed', 'cancelled'],
  served: ['completed'],
  completed: [], // terminal
  cancelled: [], // terminal
  no_show: [], // terminal
};

export function isValidAppointmentTransition(
  from: AppointmentStatus,
  to: AppointmentStatus,
): boolean {
  return isTransitionAllowed(ALLOWED_APPOINTMENT_TRANSITIONS, from, to);
}

export function applyAppointmentTransition<T extends { status: AppointmentStatus }>(
  state: T,
  next: AppointmentStatus,
): T {
  return applyTransition(ALLOWED_APPOINTMENT_TRANSITIONS, state, next, 'AppointmentSM');
}

export function isTerminalAppointmentStatus(status: AppointmentStatus): boolean {
  return isTerminalStatus(ALLOWED_APPOINTMENT_TRANSITIONS, status);
}

export function getReachableAppointmentStatuses(start: AppointmentStatus): Set<AppointmentStatus> {
  return getReachableStatuses(ALLOWED_APPOINTMENT_TRANSITIONS, start);
}

export function getAllAppointmentStatuses(): AppointmentStatus[] {
  return getAllStatuses(ALLOWED_APPOINTMENT_TRANSITIONS);
}

export { ALLOWED_APPOINTMENT_TRANSITIONS };
