/**
 * Domain invariant validators — business rules, not type checks.
 *
 * Per Track 2 (Runtime Correctness Roadmap), these validators enforce
 * business invariants that types alone cannot express. They are pure
 * functions that return either the validated value (success) or throw
 * an InvariantViolationError (failure).
 *
 * Difference from zod schemas (Track 1):
 * - Zod validates DTO SHAPE (field presence, type correctness)
 * - Invariants validate BUSINESS SEMANTICS (state transitions, cross-entity
 *   references, sign constraints, required-field-for-state rules)
 *
 * Usage:
 *   import { assertAppointmentCanBeCompleted } from '../types/domain/invariants/appointment';
 *   try {
 *     assertAppointmentCanBeCompleted(appointment);
 *   } catch (e) {
 *     // InvariantViolationError — business rule violated
 *   }
 */

/**
 * Error thrown when a domain invariant is violated.
 *
 * Carries the invariant name (for logging/analytics) and a human-readable
 * message (for UI display).
 */
export class InvariantViolationError extends Error {
  readonly invariant: string;

  constructor(invariant: string, message: string) {
    super(message);
    this.name = 'InvariantViolationError';
    this.invariant = invariant;
  }
}

/**
 * Result type for invariant checks that prefer return-over-throw.
 */
export type InvariantResult =
  | { ok: true }
  | { ok: false; invariant: string; message: string };

export function ok(): InvariantResult {
  return { ok: true };
}

export function fail(invariant: string, message: string): InvariantResult {
  return { ok: false, invariant, message };
}
