/**
 * Payment / Invoice state machine — transition validators.
 *
 * State diagram:
 *
 *   pending ──▶ paid ──▶ refunded
 *      │        │
 *      │        ├──▶ partial ──▶ paid (complete payment)
 *      │        │           └──▶ refunded
 *      │        └──▶ refunded
 *      ├──▶ failed (terminal, can retry → pending)
 *      └──▶ cancelled (terminal, same as failed for invoice)
 *
 * Terminal states: refunded, failed (failed can retry via pending)
 *
 * Refund sub-machine:
 *   requested ──▶ approved ──▶ processed
 *            └──▶ rejected (terminal)
 */

import type { PaymentStatus, RefundStatus } from '../domain/billing';
import {
  isTransitionAllowed,
  applyTransition,
  isTerminalStatus,
  getReachableStatuses,
  getAllStatuses,
} from './base';

// === Payment / Invoice status machine ===

const ALLOWED_PAYMENT_TRANSITIONS: Record<PaymentStatus, readonly PaymentStatus[]> = {
  pending: ['paid', 'failed', 'partial'],
  partial: ['paid', 'refunded'],
  paid: ['refunded'],
  refunded: [], // terminal
  failed: ['pending'], // can retry
};

export function isValidPaymentTransition(
  from: PaymentStatus,
  to: PaymentStatus,
): boolean {
  return isTransitionAllowed(ALLOWED_PAYMENT_TRANSITIONS, from, to);
}

export function applyPaymentTransition<T extends { status: PaymentStatus }>(
  state: T,
  next: PaymentStatus,
): T {
  return applyTransition(ALLOWED_PAYMENT_TRANSITIONS, state, next, 'PaymentSM');
}

export function isTerminalPaymentStatus(status: PaymentStatus): boolean {
  return isTerminalStatus(ALLOWED_PAYMENT_TRANSITIONS, status);
}

export function getReachablePaymentStatuses(start: PaymentStatus): Set<PaymentStatus> {
  return getReachableStatuses(ALLOWED_PAYMENT_TRANSITIONS, start);
}

export function getAllPaymentStatuses(): PaymentStatus[] {
  return getAllStatuses(ALLOWED_PAYMENT_TRANSITIONS);
}

// === Refund status machine ===

const ALLOWED_REFUND_TRANSITIONS: Record<RefundStatus, readonly RefundStatus[]> = {
  requested: ['approved', 'rejected'],
  approved: ['processed'],
  processed: [], // terminal
  rejected: [], // terminal
};

export function isValidRefundTransition(
  from: RefundStatus,
  to: RefundStatus,
): boolean {
  return isTransitionAllowed(ALLOWED_REFUND_TRANSITIONS, from, to);
}

export function applyRefundTransition<T extends { status: RefundStatus }>(
  state: T,
  next: RefundStatus,
): T {
  return applyTransition(ALLOWED_REFUND_TRANSITIONS, state, next, 'RefundSM');
}

export function isTerminalRefundStatus(status: RefundStatus): boolean {
  return isTerminalStatus(ALLOWED_REFUND_TRANSITIONS, status);
}

export function getReachableRefundStatuses(start: RefundStatus): Set<RefundStatus> {
  return getReachableStatuses(ALLOWED_REFUND_TRANSITIONS, start);
}

export function getAllRefundStatuses(): RefundStatus[] {
  return getAllStatuses(ALLOWED_REFUND_TRANSITIONS);
}

export { ALLOWED_PAYMENT_TRANSITIONS, ALLOWED_REFUND_TRANSITIONS };
