/**
 * DERMAHIST-FE-003 (owner registry #4063; fourteenth review group) —
 * newly saved examinations/procedures do not refresh the same-patient
 * history.
 *
 * The history hook exposes an explicit `reload` callback and refetches on
 * `normalizedPatientId`/`reloadVersion` only, but the dermatologist panel
 * never invokes it: on EMR persisted it calls only
 * `refreshCanonicalStatus(currentVisitContext, true)` for the selected
 * visit. A clinician who saves a new examination/procedure and returns to
 * the Patients/History tab without re-selecting the patient keeps seeing
 * the stale exam/procedure list and counts.
 *
 * Contract after the repair: the visit-tab EMRContainerV2 onPersisted
 * binding ALSO calls `patientHistory.reload()` (the hook's own
 * request-generation guard and patientId identity check make the refetch
 * safe), while the canonical status refresh is preserved; and the reload
 * fires only on successful EMR writes (EMRContainerV2 persists gating),
 * so a failed save retains the prior valid snapshot untouched.
 */
import fs from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';
import { fileURLToPath } from 'node:url';
import { normalizeSource } from '../../test/contracts/source-contract-helper';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../..');

function source(relativePath: string) {
  return normalizeSource(fs.readFileSync(path.join(ROOT, relativePath), 'utf8'));
}

const panel = source('pages/DermatologistPanelUnified.tsx');
const emr = source('components/emr-v2/EMRContainerV2.tsx');

describe('DERMAHIST-FE-003 — a persisted dermatology EMR refreshes the same-patient history', () => {
  it('the visit-tab EMR onPersisted binding also reloads the patient history hook', () => {
    const visitStart = panel.indexOf('{activeTab === \'visit\' && currentAppointment &&');
    const visitEnd = panel.indexOf('{/* Прием пациента - простая версия */}', visitStart);
    expect(visitStart).toBeGreaterThanOrEqual(0);
    expect(visitEnd).toBeGreaterThan(visitStart);

    const visitBlock = panel.slice(visitStart, visitEnd);
    expect(visitBlock).toContain('<EMRContainerV2');
    expect(visitBlock).toContain('patientHistory.reload()');
    // The canonical status refresh for the selected visit stays in place.
    expect(visitBlock).toContain('refreshCanonicalStatus(currentVisitContext, true)');
  });

  it('history reload fires only on successful EMR writes (failed saves retain the prior snapshot)', () => {
    // EMRContainerV2 invokes the parent onPersisted refresh only when the
    // write was not rejected — a failed save must never trigger a history
    // reload, so the prior valid snapshot is retained untouched.
    expect(emr).toContain('if (!isRejectedEMRWrite(result)) {');
    expect(emr).toContain('await onPersisted?.()');
  });
});
