/**
 * Tests for queue domain invariants.
 */

import { describe, it, expect } from 'vitest';
import {
  isTerminalQueueStatus,
  checkQueueEntryCanBeCalled,
  checkQueueEntryCanBeServed,
  checkQueueEntryCanBeSkipped,
  checkQueueEntryHasPatient,
  assertQueueEntryCanBeCalled,
  InvariantViolationError,
} from '../queue';

describe('isTerminalQueueStatus', () => {
  it('returns true for terminal statuses', () => {
    expect(isTerminalQueueStatus('completed')).toBe(true);
    expect(isTerminalQueueStatus('served')).toBe(true);
    expect(isTerminalQueueStatus('skipped')).toBe(true);
    expect(isTerminalQueueStatus('cancelled')).toBe(true);
  });

  it('returns false for non-terminal statuses', () => {
    expect(isTerminalQueueStatus('waiting')).toBe(false);
    expect(isTerminalQueueStatus('called')).toBe(false);
    expect(isTerminalQueueStatus('in_service')).toBe(false);
    expect(isTerminalQueueStatus('in_cabinet')).toBe(false);
    expect(isTerminalQueueStatus(undefined)).toBe(false);
  });
});

describe('checkQueueEntryCanBeCalled', () => {
  it('allows calling a waiting entry', () => {
    expect(checkQueueEntryCanBeCalled({ status: 'waiting' }).ok).toBe(true);
  });

  it('blocks calling a completed entry', () => {
    const result = checkQueueEntryCanBeCalled({ status: 'completed' });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.invariant).toBe('queue.call_terminal');
  });

  it('blocks calling a served entry', () => {
    expect(checkQueueEntryCanBeCalled({ status: 'served' }).ok).toBe(false);
  });

  it('blocks calling a skipped entry', () => {
    expect(checkQueueEntryCanBeCalled({ status: 'skipped' }).ok).toBe(false);
  });
});

describe('checkQueueEntryCanBeServed', () => {
  it('allows serving an in_cabinet entry', () => {
    expect(checkQueueEntryCanBeServed({ status: 'in_cabinet' }).ok).toBe(true);
  });

  it('allows serving an in_service entry', () => {
    expect(checkQueueEntryCanBeServed({ status: 'in_service' }).ok).toBe(true);
  });

  it('blocks serving a waiting entry (not in service yet)', () => {
    const result = checkQueueEntryCanBeServed({ status: 'waiting' });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.invariant).toBe('queue.serve_not_in_service');
  });

  it('blocks serving a called entry (not in service yet)', () => {
    expect(checkQueueEntryCanBeServed({ status: 'called' }).ok).toBe(false);
  });

  it('blocks serving a completed entry (terminal)', () => {
    const result = checkQueueEntryCanBeServed({ status: 'completed' });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.invariant).toBe('queue.serve_terminal');
  });
});

describe('checkQueueEntryCanBeSkipped', () => {
  it('allows skipping a waiting entry', () => {
    expect(checkQueueEntryCanBeSkipped({ status: 'waiting' }).ok).toBe(true);
  });

  it('allows skipping a called entry', () => {
    expect(checkQueueEntryCanBeSkipped({ status: 'called' }).ok).toBe(true);
  });

  it('blocks skipping an in_service entry (being seen)', () => {
    const result = checkQueueEntryCanBeSkipped({ status: 'in_service' });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.invariant).toBe('queue.skip_in_service');
  });

  it('blocks skipping an in_cabinet entry (being seen)', () => {
    expect(checkQueueEntryCanBeSkipped({ status: 'in_cabinet' }).ok).toBe(false);
  });

  it('blocks skipping a completed entry (terminal)', () => {
    expect(checkQueueEntryCanBeSkipped({ status: 'completed' }).ok).toBe(false);
  });
});

describe('checkQueueEntryHasPatient', () => {
  it('passes with patient_id', () => {
    expect(checkQueueEntryHasPatient({ patient_id: 123 }).ok).toBe(true);
  });

  it('passes with patient_name only', () => {
    expect(checkQueueEntryHasPatient({ patient_id: undefined, patient_name: 'John' }).ok).toBe(true);
  });

  it('fails when both are missing', () => {
    const result = checkQueueEntryHasPatient({ patient_id: undefined, patient_name: undefined });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.invariant).toBe('queue.missing_patient');
  });

  it('fails when patient_id is null and name is empty', () => {
    expect(checkQueueEntryHasPatient({ patient_id: null as unknown as string | number, patient_name: '' }).ok).toBe(false);
  });
});

describe('assertQueueEntryCanBeCalled (throwing)', () => {
  it('does not throw for waiting entry', () => {
    expect(() => assertQueueEntryCanBeCalled({ status: 'waiting' })).not.toThrow();
  });

  it('throws for completed entry', () => {
    expect(() => assertQueueEntryCanBeCalled({ status: 'completed' })).toThrow(InvariantViolationError);
  });
});
