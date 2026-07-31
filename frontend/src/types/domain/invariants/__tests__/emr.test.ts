/**
 * Tests for EMR domain invariants.
 */

import { describe, it, expect } from 'vitest';
import {
  checkEmrCanBeSigned,
  checkEmrAmendmentHasReason,
  checkEmrRowVersionNotStale,
  assertEmrCanBeSigned,
  assertEmrAmendmentHasReason,
  InvariantViolationError,
} from '../emr';
import type { EMRRecord } from '../../emr';

describe('checkEmrCanBeSigned', () => {
  it('passes for draft EMR with required sections', () => {
    const record: Pick<EMRRecord, 'is_draft' | 'specialty_data'> = {
      is_draft: true,
      specialty_data: {
        complaints: 'Patient reports chest pain',
        diagnosis: 'I10 Essential hypertension',
      },
    };
    expect(checkEmrCanBeSigned(record).ok).toBe(true);
  });

  it('fails for already-signed EMR', () => {
    const record: Pick<EMRRecord, 'is_draft' | 'specialty_data'> = {
      is_draft: false,
      specialty_data: {
        complaints: 'Patient reports chest pain',
        diagnosis: 'I10',
      },
    };
    const result = checkEmrCanBeSigned(record);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.invariant).toBe('emr.sign_already_signed');
  });

  it('fails when specialty_data is missing', () => {
    const result = checkEmrCanBeSigned({ is_draft: true, specialty_data: undefined });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.invariant).toBe('emr.sign_no_data');
  });

  it('fails when complaints section is empty', () => {
    const result = checkEmrCanBeSigned({
      is_draft: true,
      specialty_data: { complaints: '', diagnosis: 'I10' },
    });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.invariant).toBe('emr.sign_missing_section');
  });

  it('fails when diagnosis section is missing', () => {
    const result = checkEmrCanBeSigned({
      is_draft: true,
      specialty_data: { complaints: 'chest pain' },
    });
    expect(result.ok).toBe(false);
  });

  it('fails when complaints is empty array', () => {
    const result = checkEmrCanBeSigned({
      is_draft: true,
      specialty_data: { complaints: [], diagnosis: 'I10' },
    });
    expect(result.ok).toBe(false);
  });
});

describe('checkEmrAmendmentHasReason', () => {
  it('passes for non-empty reason', () => {
    expect(checkEmrAmendmentHasReason('Corrected diagnosis').ok).toBe(true);
  });

  it('fails for empty string', () => {
    const result = checkEmrAmendmentHasReason('');
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.invariant).toBe('emr.amend_no_reason');
  });

  it('fails for whitespace-only string', () => {
    expect(checkEmrAmendmentHasReason('   ').ok).toBe(false);
  });

  it('fails for undefined', () => {
    expect(checkEmrAmendmentHasReason(undefined).ok).toBe(false);
  });

  it('fails for null', () => {
    expect(checkEmrAmendmentHasReason(null).ok).toBe(false);
  });
});

describe('checkEmrRowVersionNotStale', () => {
  it('passes when client version equals server version', () => {
    expect(checkEmrRowVersionNotStale(5, 5).ok).toBe(true);
  });

  it('passes when client version is newer than server', () => {
    expect(checkEmrRowVersionNotStale(6, 5).ok).toBe(true);
  });

  it('fails when client version is older than server', () => {
    const result = checkEmrRowVersionNotStale(3, 5);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.invariant).toBe('emr.row_version_stale');
  });

  it('passes when either version is undefined (cannot check)', () => {
    expect(checkEmrRowVersionNotStale(undefined, 5).ok).toBe(true);
    expect(checkEmrRowVersionNotStale(5, undefined).ok).toBe(true);
  });
});

describe('throwing variants', () => {
  it('assertEmrCanBeSigned throws for signed EMR', () => {
    expect(() => assertEmrCanBeSigned({ is_draft: false, specialty_data: {} }))
      .toThrow(InvariantViolationError);
  });

  it('assertEmrAmendmentHasReason throws for empty reason', () => {
    expect(() => assertEmrAmendmentHasReason('')).toThrow(InvariantViolationError);
  });

  it('does not throw for valid inputs', () => {
    expect(() => assertEmrCanBeSigned({
      is_draft: true,
      specialty_data: { complaints: 'pain', diagnosis: 'I10' },
    })).not.toThrow();
    expect(() => assertEmrAmendmentHasReason('valid reason')).not.toThrow();
  });
});
