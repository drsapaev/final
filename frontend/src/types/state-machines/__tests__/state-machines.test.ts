/**
 * Property-based tests for all 4 state machines.
 *
 * Per ADR-0017 + Track 3, verifies 4 properties for each machine:
 * 1. Reachability — every status reachable from initial state
 * 2. Forbidden-edge rejection — invalid transitions rejected
 * 3. No-dangling states — every status has ≥1 outgoing edge (or is terminal)
 * 4. Idempotency — self-loops always allowed
 *
 * Test style: table-driven (not property-based) because state spaces are small
 * (13 appointment + 8 queue + 5 payment + 4 refund + 5 EMR = 35 statuses total).
 */

import { describe, it, expect } from 'vitest';
import {
  isValidAppointmentTransition,
  applyAppointmentTransition,
  isTerminalAppointmentStatus,
  getReachableAppointmentStatuses,
  getAllAppointmentStatuses,
  ALLOWED_APPOINTMENT_TRANSITIONS,
  isValidQueueTransition,
  applyQueueTransition,
  isTerminalQueueStatus,
  getReachableQueueStatuses,
  getAllQueueStatuses,
  ALLOWED_QUEUE_TRANSITIONS,
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
  isValidEmrTransition,
  applyEmrTransition,
  isTerminalEmrStatus,
  getReachableEmrStatuses,
  getAllEmrStatuses,
  ALLOWED_EMR_TRANSITIONS,
} from '../index';
import type {
  AppointmentStatus,
} from '../../domain/clinic';
import type { QueueEntryStatus } from '../../domain/queue';
import type { PaymentStatus, RefundStatus } from '../../domain/billing';
import type { EmrStatus } from '../../features/emr';

// Helper: verify all 4 properties for a state machine
function verifyStateMachine<S extends string>(
  name: string,
  table: Record<S, readonly S[]>,
  isValid: (from: S, to: S) => boolean,
  apply: <T extends { status: S }>(state: T, next: S) => T,
  isTerminal: (status: S) => boolean,
  getReachable: (start: S) => Set<S>,
  getAll: () => S[],
  initialStatus: S,
) {
  const allStatuses = getAll();

  describe(`${name} state machine`, () => {
    // Property 1: Reachability
    it('every status is reachable from initial state', () => {
      const reachable = getReachable(initialStatus);
      for (const status of allStatuses) {
        expect(reachable.has(status), `${status} not reachable from ${initialStatus}`).toBe(true);
      }
    });

    // Property 2: Forbidden edges rejected
    it('forbidden transitions are rejected', () => {
      for (const from of allStatuses) {
        for (const to of allStatuses) {
          const allowed = table[from].includes(to);
          const result = isValid(from, to);
          if (from === to) {
            // Idempotent — always allowed
            expect(result, `${from} → ${to} (self-loop) should be allowed`).toBe(true);
          } else if (allowed) {
            expect(result, `${from} → ${to} should be allowed`).toBe(true);
          } else {
            expect(result, `${from} → ${to} should be rejected`).toBe(false);
          }
        }
      }
    });

    // Property 3: No-dangling states
    it('every status has outgoing edges or is terminal', () => {
      for (const status of allStatuses) {
        const outgoing = (table[status] ?? []).filter((s) => s !== status);
        if (outgoing.length === 0) {
          expect(isTerminal(status), `${status} has no edges but isTerminal=false`).toBe(true);
        } else {
          expect(isTerminal(status), `${status} has edges but isTerminal=true`).toBe(false);
        }
      }
    });

    // Property 4: Idempotency
    it('self-loops are always allowed and are no-ops', () => {
      for (const status of allStatuses) {
        expect(isValid(status, status), `${status} → ${status} should be allowed`).toBe(true);
        const state = { status };
        const next = apply(state, status);
        expect(next.status).toBe(status);
      }
    });

    // Property 5: apply() is a no-op on forbidden transitions
    it('apply() returns original state on forbidden transition', () => {
      for (const from of allStatuses) {
        for (const to of allStatuses) {
          if (from === to) continue; // skip self-loops
          if (!table[from].includes(to)) {
            const state = { status: from };
            const next = apply(state, to);
            expect(next.status, `${from} → ${to} should be no-op`).toBe(from);
            expect(next).toBe(state); // same reference
          }
        }
      }
    });

    // Property 6: apply() updates status on allowed transitions
    it('apply() updates status on allowed transitions', () => {
      for (const from of allStatuses) {
        for (const to of table[from] ?? []) {
          if (from === to) continue;
          const state = { status: from };
          const next = apply(state, to);
          expect(next.status).toBe(to);
          expect(next).not.toBe(state); // new reference
        }
      }
    });
  });
}

// Run all 5 state machines through the verifier
verifyStateMachine(
  'Appointment',
  ALLOWED_APPOINTMENT_TRANSITIONS,
  isValidAppointmentTransition,
  applyAppointmentTransition,
  isTerminalAppointmentStatus,
  getReachableAppointmentStatuses,
  getAllAppointmentStatuses,
  'pending' as AppointmentStatus,
);

verifyStateMachine(
  'Queue',
  ALLOWED_QUEUE_TRANSITIONS,
  isValidQueueTransition,
  applyQueueTransition,
  isTerminalQueueStatus,
  getReachableQueueStatuses,
  getAllQueueStatuses,
  'waiting' as QueueEntryStatus,
);

verifyStateMachine(
  'Payment',
  ALLOWED_PAYMENT_TRANSITIONS,
  isValidPaymentTransition,
  applyPaymentTransition,
  isTerminalPaymentStatus,
  getReachablePaymentStatuses,
  getAllPaymentStatuses,
  'pending' as PaymentStatus,
);

verifyStateMachine(
  'Refund',
  ALLOWED_REFUND_TRANSITIONS,
  isValidRefundTransition,
  applyRefundTransition,
  isTerminalRefundStatus,
  getReachableRefundStatuses,
  getAllRefundStatuses,
  'requested' as RefundStatus,
);

verifyStateMachine(
  'EMR',
  ALLOWED_EMR_TRANSITIONS,
  isValidEmrTransition,
  applyEmrTransition,
  isTerminalEmrStatus,
  getReachableEmrStatuses,
  getAllEmrStatuses,
  'idle' as EmrStatus,
);

// === Specific scenario tests ===

describe('Appointment state machine scenarios', () => {
  it('pending → confirmed → paid → in_visit → completed (happy path)', () => {
    let state = { status: 'pending' as AppointmentStatus };
    state = applyAppointmentTransition(state, 'confirmed');
    state = applyAppointmentTransition(state, 'paid');
    state = applyAppointmentTransition(state, 'in_visit');
    state = applyAppointmentTransition(state, 'completed');
    expect(state.status).toBe('completed');
  });

  it('completed → pending is forbidden (cannot reopen)', () => {
    const state = { status: 'completed' as AppointmentStatus };
    const next = applyAppointmentTransition(state, 'pending');
    expect(next.status).toBe('completed'); // unchanged
  });

  it('cancelled → confirmed is forbidden', () => {
    const state = { status: 'cancelled' as AppointmentStatus };
    const next = applyAppointmentTransition(state, 'confirmed');
    expect(next.status).toBe('cancelled'); // unchanged
  });
});

describe('Queue state machine scenarios', () => {
  it('waiting → called → in_service → in_cabinet → served → completed', () => {
    let state = { status: 'waiting' as QueueEntryStatus };
    state = applyQueueTransition(state, 'called');
    state = applyQueueTransition(state, 'in_service');
    state = applyQueueTransition(state, 'in_cabinet');
    state = applyQueueTransition(state, 'served');
    state = applyQueueTransition(state, 'completed');
    expect(state.status).toBe('completed');
  });

  it('waiting → completed is forbidden (must go through called)', () => {
    const state = { status: 'waiting' as QueueEntryStatus };
    const next = applyQueueTransition(state, 'completed');
    expect(next.status).toBe('waiting'); // unchanged
  });
});

describe('Payment state machine scenarios', () => {
  it('pending → paid → refunded', () => {
    let state = { status: 'pending' as PaymentStatus };
    state = applyPaymentTransition(state, 'paid');
    state = applyPaymentTransition(state, 'refunded');
    expect(state.status).toBe('refunded');
  });

  it('refunded → paid is forbidden (terminal)', () => {
    const state = { status: 'refunded' as PaymentStatus };
    const next = applyPaymentTransition(state, 'paid');
    expect(next.status).toBe('refunded'); // unchanged
  });

  it('failed → pending (retry)', () => {
    let state = { status: 'failed' as PaymentStatus };
    state = applyPaymentTransition(state, 'pending');
    expect(state.status).toBe('pending');
  });
});

describe('Refund state machine scenarios', () => {
  it('requested → approved → processed', () => {
    let state = { status: 'requested' as RefundStatus };
    state = applyRefundTransition(state, 'approved');
    state = applyRefundTransition(state, 'processed');
    expect(state.status).toBe('processed');
  });

  it('requested → rejected (terminal)', () => {
    let state = { status: 'requested' as RefundStatus };
    state = applyRefundTransition(state, 'rejected');
    expect(state.status).toBe('rejected');
    // Cannot transition from rejected
    const next = applyRefundTransition(state, 'approved');
    expect(next.status).toBe('rejected');
  });
});

describe('EMR state machine scenarios', () => {
  it('idle → loading → idle (load success)', () => {
    let state = { status: 'idle' as EmrStatus };
    state = applyEmrTransition(state, 'loading');
    state = applyEmrTransition(state, 'idle');
    expect(state.status).toBe('idle');
  });

  it('idle → saving → conflict → saving → idle (conflict resolution)', () => {
    let state = { status: 'idle' as EmrStatus };
    state = applyEmrTransition(state, 'saving');
    state = applyEmrTransition(state, 'conflict');
    state = applyEmrTransition(state, 'saving');
    state = applyEmrTransition(state, 'idle');
    expect(state.status).toBe('idle');
  });

  it('idle → error is forbidden (must go through loading/saving)', () => {
    const state = { status: 'idle' as EmrStatus };
    const next = applyEmrTransition(state, 'error');
    expect(next.status).toBe('idle'); // unchanged
  });
});
