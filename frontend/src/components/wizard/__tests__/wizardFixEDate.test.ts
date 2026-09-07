/**
 * Fix E — behavior tests for wizard birth-date validation.
 *
 * Audit finding (isolated check #2): 31.02.2020 passed validateStep(1)
 * because the wizard only checked numeric ranges. These tests pin the
 * corrected validation contract implemented in wizardUtils.validateBirthDateDisplay:
 *   - impossible calendar dates (31.02.2020, 30.02.2020) are rejected;
 *   - leap years are handled correctly (29.02.2024 valid, 29.02.2023 invalid);
 *   - future birth dates are rejected (incl. later in the current year);
 *   - partial input is rejected instead of silently becoming an empty date;
 *   - empty input stays valid (field is optional).
 *
 * These are behavior assertions on the real function (not source-text
 * toContain checks).
 */
import { describe, it, expect } from 'vitest';
import {
  validateBirthDateDisplay,
  BIRTH_DATE_MASK_SENTINEL,
} from '../wizardUtils';

// Fixed "today" so tests are deterministic regardless of run date.
// 2026-09-06 local time.
const NOW = new Date(2026, 8, 6, 12, 0, 0);

describe('validateBirthDateDisplay (Fix E)', () => {
  it('accepts a valid past date', () => {
    expect(validateBirthDateDisplay('15.05.1990', NOW)).toEqual({ valid: true });
  });

  it('accepts empty input (optional field)', () => {
    expect(validateBirthDateDisplay('', NOW)).toEqual({ valid: true });
  });

  it('accepts the mask sentinel 00.00.0000 (treated as empty)', () => {
    expect(validateBirthDateDisplay(BIRTH_DATE_MASK_SENTINEL, NOW)).toEqual({ valid: true });
  });

  it('rejects the audit repro 31.02.2020 — impossible calendar date', () => {
    // Regression: previously passed range checks and became ISO 2020-02-31.
    const result = validateBirthDateDisplay('31.02.2020', NOW);
    expect(result).toEqual({ valid: false, reason: 'impossible' });
  });

  it('rejects 30.02.2020 — impossible calendar date', () => {
    expect(validateBirthDateDisplay('30.02.2020', NOW)).toEqual({ valid: false, reason: 'impossible' });
  });

  it('rejects 31.04.2021 — April has 30 days', () => {
    expect(validateBirthDateDisplay('31.04.2021', NOW)).toEqual({ valid: false, reason: 'impossible' });
  });

  it('accepts 29.02.2024 — leap year', () => {
    expect(validateBirthDateDisplay('29.02.2024', NOW)).toEqual({ valid: true });
  });

  it('rejects 29.02.2023 — not a leap year', () => {
    expect(validateBirthDateDisplay('29.02.2023', NOW)).toEqual({ valid: false, reason: 'impossible' });
  });

  it('rejects a future date later in the current year (01.12.2026)', () => {
    // Regression: old check only compared the year, so future dates within
    // the current year passed.
    const result = validateBirthDateDisplay('01.12.2026', NOW);
    expect(result).toEqual({ valid: false, reason: 'future' });
  });

  it('rejects today as a birth date', () => {
    expect(validateBirthDateDisplay('06.09.2026', NOW)).toEqual({ valid: false, reason: 'future' });
  });

  it('rejects a future year', () => {
    expect(validateBirthDateDisplay('01.01.2030', NOW)).toEqual({ valid: false, reason: 'out_of_range' });
  });

  it('rejects a year before 1900', () => {
    expect(validateBirthDateDisplay('01.01.1899', NOW)).toEqual({ valid: false, reason: 'out_of_range' });
  });

  it('rejects partial input (31.02) instead of silently saving an empty date', () => {
    expect(validateBirthDateDisplay('31.02', NOW)).toEqual({ valid: false, reason: 'incomplete' });
  });

  it('rejects partial input with two-digit year (05.03.99)', () => {
    expect(validateBirthDateDisplay('05.03.99', NOW)).toEqual({ valid: false, reason: 'incomplete' });
  });

  it('rejects month 13', () => {
    expect(validateBirthDateDisplay('01.13.2000', NOW)).toEqual({ valid: false, reason: 'out_of_range' });
  });

  it('rejects day 32', () => {
    expect(validateBirthDateDisplay('32.01.2000', NOW)).toEqual({ valid: false, reason: 'out_of_range' });
  });
});
