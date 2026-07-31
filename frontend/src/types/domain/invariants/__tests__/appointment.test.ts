/**
 * Tests for appointment domain invariants.
 */

import { describe, it, expect } from 'vitest';
import {
  isTerminalAppointmentStatus,
  checkAppointmentCanBeCompleted,
  checkAppointmentCanBeCancelled,
  checkAppointmentHasPatient,
  checkAppointmentPaymentAmount,
  assertAppointmentCanBeCompleted,
  InvariantViolationError,
} from '../appointment';

describe('isTerminalAppointmentStatus', () => {
  it('returns true for terminal statuses', () => {
    expect(isTerminalAppointmentStatus('completed')).toBe(true);
    expect(isTerminalAppointmentStatus('cancelled')).toBe(true);
    expect(isTerminalAppointmentStatus('no_show')).toBe(true);
    expect(isTerminalAppointmentStatus('served')).toBe(true);
  });

  it('returns false for non-terminal statuses', () => {
    expect(isTerminalAppointmentStatus('pending')).toBe(false);
    expect(isTerminalAppointmentStatus('confirmed')).toBe(false);
    expect(isTerminalAppointmentStatus('paid')).toBe(false);
    expect(isTerminalAppointmentStatus('in_visit')).toBe(false);
    expect(isTerminalAppointmentStatus(undefined)).toBe(false);
  });
});

describe('checkAppointmentCanBeCompleted', () => {
  it('allows completing a pending appointment', () => {
    const result = checkAppointmentCanBeCompleted({ status: 'pending' });
    expect(result.ok).toBe(true);
  });

  it('allows completing a confirmed appointment', () => {
    const result = checkAppointmentCanBeCompleted({ status: 'confirmed' });
    expect(result.ok).toBe(true);
  });

  it('blocks completing an already-completed appointment', () => {
    const result = checkAppointmentCanBeCompleted({ status: 'completed' });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.invariant).toBe('appointment.completed_twice');
      expect(result.message).toContain('already completed');
    }
  });

  it('blocks completing a cancelled appointment', () => {
    const result = checkAppointmentCanBeCompleted({ status: 'cancelled' });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.invariant).toBe('appointment.complete_cancelled');
    }
  });

  it('blocks completing a no_show appointment', () => {
    const result = checkAppointmentCanBeCompleted({ status: 'no_show' });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.invariant).toBe('appointment.complete_no_show');
    }
  });
});

describe('checkAppointmentCanBeCancelled', () => {
  it('allows cancelling a pending appointment', () => {
    expect(checkAppointmentCanBeCancelled({ status: 'pending' }).ok).toBe(true);
  });

  it('blocks cancelling a completed appointment', () => {
    const result = checkAppointmentCanBeCancelled({ status: 'completed' });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.invariant).toBe('appointment.cancel_completed');
    }
  });
});

describe('checkAppointmentHasPatient', () => {
  it('passes when patient_id is a number', () => {
    expect(checkAppointmentHasPatient({ patient_id: 123 }).ok).toBe(true);
  });

  it('passes when patient_id is a string', () => {
    expect(checkAppointmentHasPatient({ patient_id: 'abc' }).ok).toBe(true);
  });

  it('fails when patient_id is null', () => {
    const result = checkAppointmentHasPatient({ patient_id: null });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.invariant).toBe('appointment.missing_patient');
  });

  it('fails when patient_id is undefined', () => {
    const result = checkAppointmentHasPatient({ patient_id: undefined });
    expect(result.ok).toBe(false);
  });

  it('fails when patient_id is empty string', () => {
    const result = checkAppointmentHasPatient({ patient_id: '' });
    expect(result.ok).toBe(false);
  });
});

describe('checkAppointmentPaymentAmount', () => {
  it('passes when amount is positive', () => {
    expect(checkAppointmentPaymentAmount({ payment_amount: 100 }).ok).toBe(true);
  });

  it('passes when amount is zero', () => {
    expect(checkAppointmentPaymentAmount({ payment_amount: 0 }).ok).toBe(true);
  });

  it('passes when amount is undefined', () => {
    expect(checkAppointmentPaymentAmount({ payment_amount: undefined }).ok).toBe(true);
  });

  it('fails when amount is negative', () => {
    const result = checkAppointmentPaymentAmount({ payment_amount: -50 });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.invariant).toBe('appointment.negative_payment');
  });
});

describe('assertAppointmentCanBeCompleted (throwing variant)', () => {
  it('does not throw for valid appointment', () => {
    expect(() => assertAppointmentCanBeCompleted({ status: 'pending' })).not.toThrow();
  });

  it('throws InvariantViolationError for completed appointment', () => {
    try {
      assertAppointmentCanBeCompleted({ status: 'completed' });
      expect.fail('Should have thrown');
    } catch (e) {
      expect(e).toBeInstanceOf(InvariantViolationError);
      expect((e as InvariantViolationError).invariant).toBe('appointment.completed_twice');
    }
  });
});
