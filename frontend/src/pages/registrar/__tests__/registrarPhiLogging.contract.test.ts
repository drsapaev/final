/**
 * REG-FE-013 (registrar audit ledger 3803) — source contract: no PHI in
 * registrar diagnostic logging.
 *
 * The registrar row-action router, the Welcome table and the wizard QR path
 * used to dump whole appointment rows (patient_fio/patient_phone/…) and
 * interpolated phone numbers straight into logger calls. Development-only
 * or not, that violates the repository privacy discipline (AGENTS.md:
 * never expose PHI in logs, even masked audit needs are explicit).
 *
 * Contract: in the audited files, no logger.info/log/warn/debug call may
 * - pass a bare row/appointment/record object as its final argument, or
 * - interpolate patient name/phone/birth values into the message string.
 * Safe facts (ids, action names, counts, booleans) remain allowed.
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
// src/pages/registrar/__tests__ -> frontend/
const ROOT = path.resolve(__dirname, '../../../..');

const AUDITED_FILES = [
  'src/pages/registrar/useRegistrarRowActions.ts',
  'src/pages/registrar/views/WelcomeView.tsx',
  'src/components/wizard/AppointmentWizardV2.tsx',
] as const;

/** logger.info/log/warn/debug ending in a bare record-object argument. */
const ROW_DUMP_RE = /logger\.(?:info|log|warn|debug)\([^)]*,\s*(?:row|appointment|record|appt)\s*\)/;
/** logger call interpolating patient-identifying values into the string. */
const PHI_INTERPOLATION_RE = /logger\.(?:info|log|warn|debug)\([^)]*\$\{[^}]*(?:patient\.phone|patient\.fio|patient_fio|patient_name|patient_phone|birth_date)/i;
/** logger call passing patient-identifying values as object fields. */
const PHI_FIELD_RE = /logger\.(?:info|log|warn|debug)\([^)]*\{[^}]*(?:\bfio\s*:|\bpatient\s*:|patient_fio\s*:|patient_phone\s*:)/;

describe('registrar PHI logging source contract (REG-FE-013)', () => {
  for (const relPath of AUDITED_FILES) {
    it(`${relPath} does not log patient-identifying values`, () => {
      const source = fs.readFileSync(path.join(ROOT, relPath), 'utf8');
      const offenders = source.split('\n').filter(
        (line) => ROW_DUMP_RE.test(line) || PHI_INTERPOLATION_RE.test(line) || PHI_FIELD_RE.test(line),
      );
      expect(offenders, `PHI-bearing logger calls found:\n${offenders.join('\n')}`).toEqual([]);
    });
  }

  it('the row-action router logs safe facts instead of row dumps', () => {
    const source = fs.readFileSync(
      path.join(ROOT, 'src/pages/registrar/useRegistrarRowActions.ts'),
      'utf8',
    );
    expect(source).toContain('Row action:');
    expect(source).toContain('recordId');
  });
});
