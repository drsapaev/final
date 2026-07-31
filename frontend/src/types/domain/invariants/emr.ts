/**
 * EMR domain invariants.
 *
 * Business rules:
 * 1. EMR cannot be signed without required fields (complaints, diagnosis)
 * 2. EMR cannot be signed twice (terminal state)
 * 3. EMR amendment requires a reason
 * 4. EMR conflict resolution requires row_version check
 */

import type { EMRRecord } from '../emr';
import type { InvariantResult } from './base';
import { ok, fail } from './base';

/**
 * Required sections for EMR signing.
 * The backend enforces these, but the frontend should catch early.
 */
const REQUIRED_SECTIONS_FOR_SIGNING = ['complaints', 'diagnosis'] as const;

/**
 * Invariant: EMR can be signed.
 *
 * Violations:
 * - EMR is already signed (is_draft === false)
 * - Required sections (complaints, diagnosis) are empty or missing
 */
export function checkEmrCanBeSigned(
  record: Pick<EMRRecord, 'is_draft' | 'specialty_data'>,
): InvariantResult {
  if (record.is_draft === false) {
    return fail('emr.sign_already_signed', 'EMR is already signed — cannot sign twice.');
  }

  const data = record.specialty_data;
  if (!data || typeof data !== 'object') {
    return fail('emr.sign_no_data', 'EMR has no specialty data — cannot sign.');
  }

  for (const section of REQUIRED_SECTIONS_FOR_SIGNING) {
    const value = (data as Record<string, unknown>)[section];
    if (value == null || value === '' || (Array.isArray(value) && value.length === 0)) {
      return fail('emr.sign_missing_section', `EMR cannot be signed without required section '${section}'.`);
    }
  }

  return ok();
}

/**
 * Invariant: EMR amendment has a reason.
 *
 * Violations:
 * - reason is null/undefined/empty
 */
export function checkEmrAmendmentHasReason(reason: string | undefined | null): InvariantResult {
  if (!reason || !reason.trim()) {
    return fail('emr.amend_no_reason', 'EMR amendment requires a reason.');
  }
  return ok();
}

/**
 * Invariant: EMR row_version is not stale.
 *
 * Violations:
 * - client row_version < server row_version (concurrent edit detected)
 */
export function checkEmrRowVersionNotStale(
  clientRowVersion: number | undefined,
  serverRowVersion: number | undefined,
): InvariantResult {
  if (clientRowVersion == null || serverRowVersion == null) {
    // If either is unknown, cannot check — allow (backend will reject if stale)
    return ok();
  }
  if (clientRowVersion < serverRowVersion) {
    return fail('emr.row_version_stale', `EMR row_version is stale (client: ${clientRowVersion}, server: ${serverRowVersion}).`);
  }
  return ok();
}

/**
 * Throwing variants.
 */
import { InvariantViolationError } from './base';

export function assertEmrCanBeSigned(record: Pick<EMRRecord, 'is_draft' | 'specialty_data'>): void {
  const result = checkEmrCanBeSigned(record);
  if (!result.ok) throw new InvariantViolationError(result.invariant, result.message);
}

export function assertEmrAmendmentHasReason(reason: string | undefined | null): void {
  const result = checkEmrAmendmentHasReason(reason);
  if (!result.ok) throw new InvariantViolationError(result.invariant, result.message);
}

export { InvariantViolationError } from './base';
