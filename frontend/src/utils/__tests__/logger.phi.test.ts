/**
 * REG-FE-013 (registrar audit ledger 3803) — PHI-safe diagnostics.
 *
 * The registrar/wizard diagnostic paths logged patient-identifying facts in
 * development builds:
 * - object keys the scrubber does not know: bare `patient`, `fio`,
 *   `patient_fio`, `patient_phone`/`patientPhone` passed through unredacted;
 * - primitive strings interpolate raw phone numbers, which never pass the
 *   key-based scrubber at all.
 *
 * Contract under test:
 * - every patient-name/phone alias is redacted by sanitize();
 * - phone-literal-looking sequences inside primitive strings are masked to
 *   the phone-tail form (last 4 digits), while short digit runs, dates and
 *   amounts stay untouched.
 */
import { describe, it, expect } from 'vitest';

import { sanitize, maskPhoneLiterals } from '../logger';

const sanitizeTyped = sanitize as unknown as (input: unknown) => Record<string, unknown>;

describe('logger PHI aliases (REG-FE-013)', () => {
  it('redacts the bare patient alias used by registrar row logging', () => {
    const result = sanitizeTyped({ patient: 'Синтетов Синтет Синтетович' });
    expect(result.patient).toBe('[REDACTED]');
  });

  it('redacts the fio / patient_fio name aliases', () => {
    const result = sanitizeTyped({
      fio: 'Синтетов Синтет',
      patient_fio: 'Синтетов Синтет',
    });
    expect(result.fio).toBe('[REDACTED]');
    expect(result.patient_fio).toBe('[REDACTED]');
  });

  it('redacts the patient_phone / patientPhone contact aliases', () => {
    const result = sanitizeTyped({
      patient_phone: '+998 90 123 45 67',
      patientPhone: '+998 90 123 45 67',
    });
    expect(result.patient_phone).toBe('[REDACTED]');
    expect(result.patientPhone).toBe('[REDACTED]');
  });

  it('keeps redacting the pre-existing aliases (no regression)', () => {
    const result = sanitizeTyped({
      patient_name: 'X',
      phone: '+998901234567',
      birth_date: '2000-01-01',
      id: 7,
      status: 'waiting',
    });
    expect(result.patient_name).toBe('[REDACTED]');
    expect(result.phone).toBe('[REDACTED]');
    expect(result.birth_date).toBe('[REDACTED]');
    expect(result.id).toBe(7);
    expect(result.status).toBe('waiting');
  });
});

describe('maskPhoneLiterals (REG-FE-013 primitive-string defense)', () => {
  it('masks an Uzbek phone interpolated into a message string', () => {
    const masked = maskPhoneLiterals('Пациент с телефоном +998 90 123 45 67 не найден');
    expect(masked).not.toContain('90 123 45 67');
    expect(masked).not.toContain('+998');
    expect(masked).toMatch(/\*{3,}\d{4}/);
  });

  it('masks a bare 12-digit phone literal', () => {
    const masked = maskPhoneLiterals('lookup failed for 998901234567 twice');
    expect(masked).not.toContain('998901234567');
    expect(masked).toMatch(/\*{3,}4567/);
  });

  it('leaves short digit runs, dates and amounts untouched', () => {
    expect(maskPhoneLiterals('order 12345 for record 7')).toBe('order 12345 for record 7');
    expect(maskPhoneLiterals('date 2026-11-03')).toBe('date 2026-11-03');
    expect(maskPhoneLiterals('amount 30000 sum')).toBe('amount 30000 sum');
  });

  it('returns ordinary text unchanged', () => {
    const text = '[RegistrarPanel] Row action: view (record 9)';
    expect(maskPhoneLiterals(text)).toBe(text);
  });
});
