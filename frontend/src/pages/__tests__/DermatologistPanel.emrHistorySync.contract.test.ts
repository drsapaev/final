/**
 * DERMAHIST-FE-003 (audit #3892, round 9 — dermatology history plane) —
 * fail-first repo-precedent SOURCE-CONTRACT test (pattern:
 * CardiologistPanel.retro3969.contract.test.tsx, mounts nothing).
 *
 * Contract: saving an EMR (examination/procedures) inside the visit tab
 * MUST refresh the same-patient patient-history snapshot — the history
 * hook exposes `reload()` exactly for this purpose, and the panel holds
 * the hook instance (`patientHistory`) in scope at the EMR mount site.
 * Pre-fix, `onPersisted` called only `refreshCanonicalStatus` for the
 * selected visit, so the clinician who saves a new examination and
 * returns to the Patients/History tab keeps reading the stale snapshot
 * until a patient re-selection remounts the hook.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '../..');

const readSource = (relPath: string) =>
  fs.readFileSync(path.join(ROOT, relPath), 'utf8').replace(/\r\n/g, '\n');

const panel = readSource('pages/DermatologistPanelUnified.tsx');

describe('DERMAHIST-FE-003: EMR persist refreshes the same-patient history', () => {
  const emrMountIdx = panel.indexOf('<EMRContainerV2');
  const onPersistedIdx = panel.indexOf('onPersisted=', emrMountIdx);
  const onPersistedEnd = panel.indexOf('/>', onPersistedIdx);
  const onPersistedBody = panel.slice(onPersistedIdx, onPersistedEnd);

  it('the EMR mount site exists and holds the history hook in scope', () => {
    expect(emrMountIdx).toBeGreaterThan(-1);
    expect(panel).toContain('useDermatologyPatientHistory(');
  });

  it('onPersisted still refreshes the canonical visit status', () => {
    expect(onPersistedBody).toContain('refreshCanonicalStatus');
  });

  it('onPersisted also reloads the patient-history snapshot', () => {
    expect(onPersistedBody).toMatch(/patientHistory\.reload\(\)/);
  });
});
